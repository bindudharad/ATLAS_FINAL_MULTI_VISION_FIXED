"""Tests for bounded UIA discovery and target locking.

Covers the fix for the 30-90+ second attach hang caused by an unbounded
recursive UIA traversal when a flat walk finds 0 editable controls:

- ``_DiscoveryBudget`` caps wall-clock / node / depth cost
- ``walk_descendants`` / ``inspectable_nodes`` respect the budget
- ``editable_fields`` makes at most ONE bounded recursive retry, then
  reports "UIA insufficient" instead of re-crawling
- ``_editable_with_rect`` no longer performs a redundant second full walk
- ``probe_editable_roots`` shares one budget across every child HWND probe
- ``AttachedTarget`` immutable lock is recorded on attach
- ``_find_child_with_controls`` is confined to the target's own process

All UIA/Win32 layers are faked; no live window is required.
"""

from __future__ import annotations

import time

import pytest

from atlas.observe import uia as uia_mod
from atlas.observe.uia import (
    UiaBackend,
    UiaNode,
    _DiscoveryBudget,
    _DISCOVERY_BUDGET_S,
    _DISCOVERY_MAX_DEPTH,
)
from atlas.observe.window import AttachedTarget, WindowAttacher, WindowTarget
from atlas.vision.capture import WindowCapture
from atlas.vision.models import BBox


# ---------------------------------------------------------------------------
# _DiscoveryBudget
# ---------------------------------------------------------------------------


def test_budget_node_cap_exhausts() -> None:
    budget = _DiscoveryBudget(max_nodes=2)
    assert budget.enter() is True
    assert budget.enter() is True
    assert budget.exhausted is True
    assert budget.enter() is False  # over the cap - refused


def test_budget_deadline_exhausts() -> None:
    budget = _DiscoveryBudget(deadline=time.monotonic() - 1.0)
    assert budget.exhausted is True
    assert budget.enter() is False


def test_budget_defaults_are_bounded() -> None:
    budget = _DiscoveryBudget()
    assert budget.max_depth == _DISCOVERY_MAX_DEPTH
    assert budget.nodes_left > 0


# ---------------------------------------------------------------------------
# Fake UIA layer
# ---------------------------------------------------------------------------


class FakeInfo:
    def __init__(self, control_type: str = "Pane", name: str = "",
                 children: list["FakeInfo"] | None = None) -> None:
        self.control_type = control_type
        self.name = name
        self._children = children or []

    def children(self) -> list["FakeInfo"]:
        return list(self._children)


def _fake_flatten(info: FakeInfo) -> UiaNode | None:
    return UiaNode(
        name=info.name,
        control_type=info.control_type,
        rect=BBox(0, 0, 10, 10),
        enabled=True,
        visible=True,
    )


def _make_backend(monkeypatch) -> UiaBackend:
    backend = UiaBackend.__new__(UiaBackend)
    backend._available = True
    backend._desktop = None
    backend._scroll_container_cache = {}
    backend._option_cache = {}
    backend._probe_cache = {}
    monkeypatch.setattr(backend, "_flatten", _fake_flatten)
    return backend


# ---------------------------------------------------------------------------
# walk_descendants / inspectable_nodes bounded recursion
# ---------------------------------------------------------------------------


def test_walk_descendants_respects_depth_budget(monkeypatch) -> None:
    backend = _make_backend(monkeypatch)
    # A chain deeper than the depth cap; the budget caps recursion.
    root = FakeInfo(name="n0")
    cur = root
    for i in range(1, _DISCOVERY_MAX_DEPTH + 20):
        child = FakeInfo(name=f"n{i}")
        cur._children = [child]
        cur = child
    monkeypatch.setattr(backend, "uia_root", lambda handle: root)

    nodes = backend.walk_descendants(123)
    # depth 0.._DISCOVERY_MAX_DEPTH inclusive
    assert len(nodes) == _DISCOVERY_MAX_DEPTH + 1


def test_walk_descendants_respects_node_budget(monkeypatch) -> None:
    backend = _make_backend(monkeypatch)
    root = FakeInfo(name="root", children=[FakeInfo(name=f"c{i}") for i in range(50)])
    monkeypatch.setattr(backend, "uia_root", lambda handle: root)

    budget = _DiscoveryBudget(max_nodes=5)
    nodes = backend.walk_descendants(123, budget=budget)
    assert len(nodes) <= 5
    assert budget.exhausted is True


def test_inspectable_nodes_respects_depth_budget(monkeypatch) -> None:
    backend = _make_backend(monkeypatch)
    root = FakeInfo(name="n0")
    cur = root
    for i in range(1, _DISCOVERY_MAX_DEPTH + 20):
        child = FakeInfo(name=f"n{i}")
        cur._children = [child]
        cur = child
    window = type("W", (), {"element_info": root})()
    monkeypatch.setattr(backend, "_window_for", lambda handle: window)

    nodes = backend.inspectable_nodes(123)
    assert len(nodes) == _DISCOVERY_MAX_DEPTH + 1


# ---------------------------------------------------------------------------
# editable_fields: single bounded recursive retry
# ---------------------------------------------------------------------------


def test_editable_fields_single_retry_reports_insufficient(monkeypatch) -> None:
    """Flat walk finds nothing editable; ONE bounded retry finds nothing too.

    The result must be "UIA insufficient" (empty, fast) - never another
    re-crawl of the tree.
    """
    backend = _make_backend(monkeypatch)
    root = FakeInfo(name="root", children=[
        FakeInfo(control_type="Button", name="Upload"),
        FakeInfo(control_type="Text", name="some label"),
    ])
    window = type("W", (), {"element_info": root})()
    monkeypatch.setattr(backend, "_window_for", lambda handle: window)
    monkeypatch.setattr(backend, "descendants", lambda handle: [])  # flat: nothing

    calls: list[int] = []

    real_inspectable = backend.inspectable_nodes
    def _spy_inspectable(handle, budget=None):
        calls.append(1)
        return real_inspectable(handle, budget)

    monkeypatch.setattr(backend, "inspectable_nodes", _spy_inspectable)

    editable = backend.editable_fields(123)
    assert editable == []
    # Exactly one recursive retry (the flat walk is not a retry).
    assert len(calls) == 1


def test_editable_fields_retry_finds_nested_editables(monkeypatch) -> None:
    backend = _make_backend(monkeypatch)
    edit = FakeInfo(control_type="Edit", name="Full Name")
    root = FakeInfo(name="root", children=[FakeInfo(control_type="Pane", children=[edit])])
    window = type("W", (), {"element_info": root})()
    monkeypatch.setattr(backend, "_window_for", lambda handle: window)
    monkeypatch.setattr(backend, "descendants", lambda handle: [])

    editable = backend.editable_fields(123)
    assert len(editable) == 1
    assert editable[0].name == "Full Name"


def test_editable_fields_returns_flat_hit_without_retry(monkeypatch) -> None:
    backend = _make_backend(monkeypatch)
    edit = FakeInfo(control_type="Edit", name="Flat Edit")
    monkeypatch.setattr(backend, "descendants", lambda handle: [_fake_flatten(edit)])

    calls: list[int] = []
    def _spy(handle, budget=None):
        calls.append(1)
        return []
    monkeypatch.setattr(backend, "inspectable_nodes", _spy)

    editable = backend.editable_fields(123)
    assert len(editable) == 1
    assert calls == []  # flat hit - never touch the recursive walk


def test_editable_with_rect_does_not_double_walk(monkeypatch) -> None:
    """_editable_with_rect must not re-walk the tree after editable_fields."""
    backend = _make_backend(monkeypatch)
    monkeypatch.setattr(backend, "editable_fields", lambda handle, budget=None: [])
    monkeypatch.setattr(backend, "walk_descendants",
                        lambda handle, budget=None: pytest.fail("double walk!"))

    assert backend._editable_with_rect(123) == []


# ---------------------------------------------------------------------------
# probe_editable_roots: one shared budget across all child probes
# ---------------------------------------------------------------------------


def test_probe_editable_roots_stops_when_budget_exhausted(monkeypatch) -> None:
    backend = _make_backend(monkeypatch)
    monkeypatch.setattr(backend, "child_hwnds",
                        lambda handle, visible_only=True: [1001, 1002, 1003, 1004, 1005])

    # Drain the shared budget so the child-window scan must stop early.
    def _drain(h, budget=None):
        for _ in range(1000):
            if not budget.enter():
                break
        return []

    monkeypatch.setattr(backend, "_editable_with_rect", _drain)
    # The probe loop creates its own budget; force a tiny node cap.
    monkeypatch.setattr(uia_mod, "_DiscoveryBudget",
                        lambda *a, **k: _DiscoveryBudget(max_nodes=3))

    results = backend.probe_editable_roots(999)
    # handle + the children probed before the budget ran out
    assert len(results) < 6
    assert results[0]["hwnd"] == 999


def test_probe_editable_roots_probes_all_children_when_fast(monkeypatch) -> None:
    backend = _make_backend(monkeypatch)
    monkeypatch.setattr(backend, "child_hwnds",
                        lambda handle, visible_only=True: [1001, 1002])
    monkeypatch.setattr(backend, "_editable_with_rect",
                        lambda h, budget=None: [_fake_flatten(FakeInfo(control_type="Edit"))])

    results = backend.probe_editable_roots(999)
    assert {r["hwnd"] for r in results} == {999, 1001, 1002}
    assert all(r["count"] == 1 for r in results)


def test_probe_editable_roots_caches_per_handle(monkeypatch) -> None:
    """A second probe for the same window must NOT re-walk the UIA tree.

    Attach-by-title and attach-by-click can both probe the same MPF window
    back-to-back; the 15s TTL cache serves the second call so the form is not
    re-discovered (and re-budgeted) needlessly.
    """
    backend = _make_backend(monkeypatch)
    monkeypatch.setattr(backend, "child_hwnds",
                        lambda handle, visible_only=True: [1001])
    monkeypatch.setattr(backend, "_editable_with_rect",
                        lambda h, budget=None: [_fake_flatten(FakeInfo(control_type="Edit"))])

    first = backend.probe_editable_roots(999)
    calls = []
    def _spy(h, budget=None):
        calls.append(h)
        return []
    monkeypatch.setattr(backend, "_editable_with_rect", _spy)

    second = backend.probe_editable_roots(999)
    assert first == second
    assert calls == []  # served entirely from cache


# ---------------------------------------------------------------------------
# AttachedTarget immutable lock
# ---------------------------------------------------------------------------


def test_attached_target_frozen_and_dict() -> None:
    target = AttachedTarget(
        hwnd=1234,
        pid=5678,
        title="MPF",
        class_name="Chrome_WidgetWin_1",
        client_rect=(0, 0, 1024, 768),
        process_name="mpf.exe",
        attach_timestamp=1.0,
    )
    with pytest.raises(Exception):
        target.hwnd = 999  # frozen
    data = target.to_dict()
    assert data["hwnd"] == 1234
    assert data["pid"] == 5678
    assert data["process_name"] == "mpf.exe"


def test_attacher_records_attached_target(monkeypatch) -> None:
    attacher = WindowAttacher(WindowCapture())
    monkeypatch.setattr(attacher, "_verify_target_tree", lambda t: None)
    monkeypatch.setattr(attacher, "_dump_uia_diagnostics", lambda t: None)
    monkeypatch.setattr(WindowAttacher, "_canvas_rect",
                        staticmethod(lambda h: (0, 0, 1024, 768)))

    target = WindowTarget(
        handle=1234,
        title="MPF",
        process_id=5678,
        executable="mpf.exe",
        exe_path="C:\\App\\mpf.exe",
        class_name="Chrome_WidgetWin_1",
    )
    attacher._verify_and_attach(target)

    locked = attacher.attached_target
    assert locked is not None
    assert locked.hwnd == 1234
    assert locked.pid == 5678
    assert locked.client_rect == (0, 0, 1024, 768)
    assert locked.process_name == "mpf.exe"
    assert locked.title == "MPF"


# ---------------------------------------------------------------------------
# _find_child_with_controls is confined to the target's own process
# ---------------------------------------------------------------------------


def test_find_child_with_controls_skips_other_process_windows(monkeypatch) -> None:
    attacher = WindowAttacher(WindowCapture())
    backend = _make_backend(monkeypatch)
    from atlas.observe.uia import UiaBackend
    monkeypatch.setattr(UiaBackend, "_instance", backend)
    monkeypatch.setattr(UiaBackend, "instance", classmethod(lambda cls: backend))

    probed: list[int] = []
    monkeypatch.setattr(backend, "editable_fields",
                        lambda handle, nodes=None, budget=None: (probed.append(handle), [])[1])

    import win32gui
    def _enum(parent, callback, param=None):
        callback(100, None)  # pid 5555 -> same process, probed
        callback(200, None)  # pid 9999 -> other process, skipped
        return True
    monkeypatch.setattr(win32gui, "EnumChildWindows", _enum)
    monkeypatch.setattr(win32gui, "IsWindowVisible", lambda h: True)
    monkeypatch.setattr(WindowAttacher, "_winapi_query_window",
                        staticmethod(lambda h: (1, 5555 if h == 100 else 9999)))

    assert attacher._find_child_with_controls(999, parent_pid=5555) is None
    assert probed == [100]
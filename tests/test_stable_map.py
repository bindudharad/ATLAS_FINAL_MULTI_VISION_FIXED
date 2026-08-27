"""Tests for atlas.mapping.stable_map - the last-known-good field-map guard.

Covers the exact regression scenarios called out in the field-map explosion
bug report:

    uia map built: 31 left labels, 37 right fields, 5 scroll containers
    uia map built: 31 left labels, 79 right fields, 0 scroll containers
    uia map built: 31 left labels, 634 right fields, 0 scroll containers
"""

from __future__ import annotations

from atlas.mapping.stable_map import (
    LastKnownGoodMapGuard,
    dedupe_fields,
    duplicate_ratio,
    stable_field_id,
)
from atlas.mapping.uia_map import UiaFieldMap
from atlas.observe.uia import ScrollContainer, UiaNode
from atlas.vision.models import BBox


def _node(name: str, ctype: str = "Edit", x: int = 500, y: int = 40, automation_id: str = "", handle=None) -> UiaNode:
    return UiaNode(
        name=name, control_type=ctype, automation_id=automation_id, handle=handle,
        rect=BBox(x, y, 180, 24),
    )


def _left_labels(n: int) -> list[UiaNode]:
    return [_node(f"Label {i}", ctype="Text", x=20, y=20 + i * 30) for i in range(n)]


def _right_fields(n: int, automation_ids: bool = False) -> list[UiaNode]:
    fields = []
    for i in range(n):
        aid = f"field_{i}" if automation_ids else ""
        fields.append(_node(f"Field {i}", ctype="Edit", y=40 + i * 30, automation_id=aid))
    return fields


def _map(left_n: int, right_n: int, scroll_n: int = 0, automation_ids: bool = False) -> UiaFieldMap:
    return UiaFieldMap(
        left_labels=_left_labels(left_n),
        right_fields=_right_fields(right_n, automation_ids=automation_ids),
        scroll_containers=[ScrollContainer(handle=1000 + i) for i in range(scroll_n)],
    )


# ---------------------------------------------------------------------------
# stable_field_id / dedupe
# ---------------------------------------------------------------------------


def test_stable_id_uses_automation_id_when_present() -> None:
    a = _node("District", automation_id="district_combo", x=500, y=40)
    b = _node("District", automation_id="district_combo", x=500, y=340)  # scrolled
    assert stable_field_id(a) == stable_field_id(b)


def test_stable_id_uses_handle_when_no_automation_id() -> None:
    a = _node("District", handle=42, x=500, y=40)
    b = _node("District", handle=42, x=500, y=340)
    assert stable_field_id(a) == stable_field_id(b)


def test_stable_id_survives_vertical_scroll_via_label_fallback() -> None:
    """Same field, no automation id / handle: y moves under scroll, x doesn't -
    the field must still resolve to the same identity."""
    a = _node("District", x=500, y=40)
    b = _node("District", x=500, y=340)
    assert stable_field_id(a) == stable_field_id(b)


def test_stable_id_distinguishes_same_label_different_column() -> None:
    a = _node("Value", x=500, y=40)
    b = _node("Value", x=900, y=40)
    assert stable_field_id(a) != stable_field_id(b)


def test_dedupe_fields_collapses_repeated_observations() -> None:
    """A field observed 3 times (identical automation id) is still ONE field."""
    nodes = [_node("District", automation_id="district", y=40) for _ in range(3)]
    nodes += [_node("Taluk", automation_id="taluk", y=80)]
    deduped = dedupe_fields(nodes)
    assert len(deduped) == 2


def test_duplicate_ratio() -> None:
    nodes = [_node("A", automation_id="a")] * 4 + [_node("B", automation_id="b")]
    assert duplicate_ratio(nodes) == 3 / 5


# ---------------------------------------------------------------------------
# LastKnownGoodMapGuard - the actual explosion-rejection behaviour
# ---------------------------------------------------------------------------


def test_first_observation_is_seeded_unconditionally() -> None:
    guard = LastKnownGoodMapGuard()
    candidate = _map(left_n=31, right_n=37, scroll_n=5, automation_ids=True)
    accepted, report = guard.evaluate(candidate)
    assert report.accepted
    assert len(accepted.right_fields) == 37
    assert guard.last_known_good is accepted


def test_37_to_38_is_accepted() -> None:
    """A small, plausible growth (one more field revealed) passes."""
    guard = LastKnownGoodMapGuard()
    guard.evaluate(_map(left_n=31, right_n=37, scroll_n=5, automation_ids=True))
    accepted, report = guard.evaluate(_map(left_n=31, right_n=38, scroll_n=5, automation_ids=True))
    assert report.accepted
    assert len(accepted.right_fields) == 38


def test_37_to_634_is_rejected() -> None:
    """The exact reported explosion: right fields balloon while left labels
    (31) stay flat - this is rejected and the 37-field map is retained."""
    guard = LastKnownGoodMapGuard()
    guard.evaluate(_map(left_n=31, right_n=37, scroll_n=5, automation_ids=True))
    kept, report = guard.evaluate(_map(left_n=31, right_n=634, scroll_n=0, automation_ids=True))
    assert not report.accepted
    assert len(kept.right_fields) == 37
    assert guard.rejections == 1


def test_37_to_79_is_rejected() -> None:
    """The intermediate corruption step from the bug report is also rejected."""
    guard = LastKnownGoodMapGuard()
    guard.evaluate(_map(left_n=31, right_n=37, scroll_n=5, automation_ids=True))
    kept, report = guard.evaluate(_map(left_n=31, right_n=79, scroll_n=0, automation_ids=True))
    assert not report.accepted
    assert len(kept.right_fields) == 37


def test_explosion_with_genuine_left_growth_is_accepted() -> None:
    """If the LEFT panel also grew proportionally (a genuinely different,
    bigger form/screen), a big right-side jump is not automatically an
    explosion - the guard only fires when left stays flat."""
    guard = LastKnownGoodMapGuard()
    guard.evaluate(_map(left_n=31, right_n=37, scroll_n=5, automation_ids=True))
    accepted, report = guard.evaluate(_map(left_n=90, right_n=110, scroll_n=5, automation_ids=True))
    assert report.accepted


def test_scroll_containers_dropping_to_zero_is_patched_from_last_good() -> None:
    """5 -> 0 scroll containers on an otherwise-valid map must not destroy the
    known-good scroll state."""
    guard = LastKnownGoodMapGuard()
    guard.evaluate(_map(left_n=31, right_n=37, scroll_n=5, automation_ids=True))
    accepted, report = guard.evaluate(_map(left_n=31, right_n=38, scroll_n=0, automation_ids=True))
    assert report.accepted
    assert report.scroll_patched
    assert len(accepted.scroll_containers) == 5


def test_duplicate_heavy_candidate_is_rejected() -> None:
    """A candidate whose right_fields are mostly the same field repeated is
    rejected even without a raw count explosion."""
    guard = LastKnownGoodMapGuard()
    guard.evaluate(_map(left_n=10, right_n=10, automation_ids=True))
    dup_fields = [_node("District", automation_id="district", y=40)] * 20
    candidate = UiaFieldMap(left_labels=_left_labels(10), right_fields=dup_fields)
    kept, report = guard.evaluate(candidate)
    assert not report.accepted
    assert len(kept.right_fields) == 10


def test_internally_duplicated_first_map_is_rejected() -> None:
    guard = LastKnownGoodMapGuard()
    dup_fields = [_node("District", automation_id="district", y=40)] * 20
    candidate = UiaFieldMap(left_labels=_left_labels(10), right_fields=dup_fields)
    kept, report = guard.evaluate(candidate)
    assert not report.accepted
    assert kept is None
    assert guard.last_known_good is None


def test_none_candidate_returns_last_known_good_unchanged() -> None:
    guard = LastKnownGoodMapGuard()
    guard.evaluate(_map(left_n=31, right_n=37, scroll_n=5, automation_ids=True))
    kept, report = guard.evaluate(None)
    assert not report.accepted
    assert len(kept.right_fields) == 37


def test_reset_clears_state() -> None:
    guard = LastKnownGoodMapGuard()
    guard.evaluate(_map(left_n=31, right_n=37, scroll_n=5, automation_ids=True))
    guard.reset()
    assert guard.last_known_good is None
    assert guard.rejections == 0


def test_seed_primes_without_validation() -> None:
    guard = LastKnownGoodMapGuard()
    seed_map = _map(left_n=31, right_n=37, scroll_n=5, automation_ids=True)
    guard.seed(seed_map)
    assert guard.last_known_good is seed_map
    # A subsequent explosion is still rejected against the seeded baseline.
    kept, report = guard.evaluate(_map(left_n=31, right_n=634, automation_ids=True))
    assert not report.accepted
    assert len(kept.right_fields) == 37


def test_within_tolerance_candidate_deduped_before_acceptance() -> None:
    """Even an accepted candidate has its own internal duplicates collapsed."""
    guard = LastKnownGoodMapGuard()
    guard.evaluate(_map(left_n=10, right_n=10, automation_ids=True))
    fields = _right_fields(10, automation_ids=True) + [
        _node("Field 0", automation_id="field_0", y=40)  # duplicate of an existing id
    ]
    candidate = UiaFieldMap(left_labels=_left_labels(10), right_fields=fields)
    accepted, report = guard.evaluate(candidate)
    assert report.accepted
    assert len(accepted.right_fields) == 10  # duplicate collapsed, not 11

"""Tests for the merged perception stack (UIA + CV/OCR)."""

from __future__ import annotations

from types import SimpleNamespace

from atlas.observe.perception import PerceptionStack, from_uia_nodes, merge_fields, order_fields
from atlas.observe.uia import UiaNode
from atlas.understanding.target_field import FieldSource, TargetField
from atlas.vision.models import BBox


def _uia_field(handle: int, label: str, x: int, y: int, w: int = 200, h: int = 24) -> TargetField:
    node = UiaNode(
        name=label,
        control_type="Edit",
        automation_id=f"field_{handle}",
        handle=handle,
        rect=BBox(x, y, w, h),
        enabled=True,
    )
    return from_uia_nodes([node])[0]


def _cv_field(fid: str, label: str, x: int, y: int, w: int = 200, h: int = 24) -> TargetField:
    return TargetField(
        id=fid,
        label=label,
        normalized_label=label.lower(),
        bounds=BBox(x, y, w, h),
        source=FieldSource.CV,
    )


def test_from_uia_nodes_normalizes_fields() -> None:
    node = UiaNode(name="Full Name", control_type="Edit", automation_id="fn", rect=BBox(0, 0, 100, 20), enabled=True)
    fields = from_uia_nodes([node])
    assert len(fields) == 1
    field = fields[0]
    assert field.label == "Full Name"
    assert field.source is FieldSource.UIA
    assert field.confidence == 1.0
    assert field.bounds == BBox(0, 0, 100, 20)


def test_merge_fields_keeps_higher_priority_channel() -> None:
    uia = [_uia_field(1, "Full Name", 100, 100)]
    cv = [_cv_field("cv-0", "Full Name", 100, 100)]
    merged = merge_fields(uia, cv)
    assert len(merged) == 1
    assert merged[0].source is FieldSource.UIA


def test_merge_fields_enriches_labelless_uia_with_cv_label() -> None:
    uia = [_uia_field(1, "", 100, 100)]
    cv = [_cv_field("cv-0", "State", 100, 100)]
    merged = merge_fields(uia, cv)
    assert len(merged) == 1
    assert merged[0].label == "State"
    assert merged[0].source is FieldSource.UIA


def test_merge_fields_keeps_non_overlapping_extras() -> None:
    uia = [_uia_field(1, "Name", 100, 100)]
    cv = [_cv_field("cv-0", "Pincode", 400, 300)]
    merged = merge_fields(uia, cv)
    assert len(merged) == 2


def test_order_fields_sorts_reading_order() -> None:
    fields = [
        _cv_field("b", "Lower", 300, 200),
        _cv_field("a", "Upper", 100, 50),
    ]
    assert [f.id for f in order_fields(fields)] == ["a", "b"]


def test_perception_stack_discover_uses_uia_when_available() -> None:
    nodes = [
        UiaNode(name="Full Name", control_type="Edit", automation_id="fn", rect=BBox(0, 0, 100, 20), enabled=True),
    ]
    backend = SimpleNamespace(available=True, editable_fields=lambda handle: nodes)
    stack = PerceptionStack(backend=backend)
    fields = stack.discover(handle=123, image=None)
    assert len(fields) == 1
    assert fields[0].source is FieldSource.UIA
    assert fields[0].label == "Full Name"


def test_perception_stack_discover_empty_backend_returns_none() -> None:
    backend = SimpleNamespace(available=False, editable_fields=lambda handle: [])
    stack = PerceptionStack(backend=backend)
    assert stack.discover(handle=123, image=None) == []
    assert stack.discover(handle=None, image=None) == []
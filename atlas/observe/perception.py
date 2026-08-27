"""Merged multi-channel field perception.

The engine discovers target fields from every available channel - UIA
accessibility tree, DOM (web), and OCR/CV over the screenshot - and merges them
into one normalized ``TargetField`` list. No single channel is required: when
UIA reports zero editable controls (a real, intermittent MPF failure), the
OCR/CV channel still finds the form so the record can be filled and audited.

Priority per the engine contract: UIA > DOM > Win32 > keyboard/focus >
screenshot+CV > OCR > VLM > mouse/keyboard fallback. Higher-priority fields win
on overlap; lower-priority channels fill the gaps and can supply labels that a
higher-priority channel lacked.
"""

from __future__ import annotations

from typing import Any

from atlas.core.logging import logger, perception_logger
from atlas.understanding.target_field import (
    FieldSource,
    TargetControlType,
    TargetField,
    control_type_for_uia,
    interaction_strategy_for,
    verification_strategy_for,
)
from atlas.vision.field_cv import discover_fields_from_image
from atlas.vision.models import BBox

_MERGE_IOU = 0.55  # overlapping bounds = same control


def from_uia_nodes(nodes: list[Any]) -> list[TargetField]:
    """Convert UIA ``UiaNode`` objects into normalized ``TargetField`` objects."""
    fields: list[TargetField] = []
    for i, node in enumerate(nodes):
        rect = getattr(node, "rect", None)
        name = (getattr(node, "name", "") or "").strip()
        control_type_raw = getattr(node, "control_type", "") or ""
        kind = control_type_for_uia(control_type_raw)
        enabled = bool(getattr(node, "enabled", True))
        visible = bool(getattr(node, "visible", True))
        fields.append(
            TargetField(
                id=f"uia-{getattr(node, 'automation_id', None) or getattr(node, 'handle', None) or i}",
                label=name,
                normalized_label=name.lower().rstrip(":").strip(),
                control_type=kind,
                bounds=rect if isinstance(rect, BBox) and rect.width > 0 else None,
                value=getattr(node, "value", None),
                visible=visible,
                enabled=enabled,
                editable=enabled and visible,
                source=FieldSource.UIA,
                confidence=1.0,
                interaction_strategy=interaction_strategy_for(kind, FieldSource.UIA),
                verification_strategy=verification_strategy_for(kind, FieldSource.UIA),
                ref=node,
            )
        )
    return fields


def _iou(a: BBox, b: BBox) -> float:
    x = max(0, min(a.right, b.right) - max(a.left, b.left))
    y = max(0, min(a.bottom, b.bottom) - max(a.top, b.top))
    inter = x * y
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


def _overlap_any(box: BBox, others: list[TargetField]) -> TargetField | None:
    best = None
    best_iou = 0.0
    for other in others:
        ob = other.bounds
        if ob is None:
            continue
        ratio = _iou(box, ob)
        if ratio > best_iou:
            best_iou = ratio
            best = other
    return best if best_iou >= _MERGE_IOU else None


def merge_fields(*channels: list[TargetField]) -> list[TargetField]:
    """Merge field lists by spatial overlap; earlier channels take priority.

    A later-channel field overlapping an earlier-channel field is dropped
    UNLESS the earlier field has no label and the later one does (label
    enrichment). Fields without a bound overlap survive as extras.
    """
    merged: list[TargetField] = []
    for channel in channels:
        for field in channel:
            if field.bounds is None:
                merged.append(field)
                continue
            existing = _overlap_any(field.bounds, merged)
            if existing is None:
                merged.append(field)
                continue
            # Enrich a label-less higher-priority field with a found label.
            if not existing.label and field.label:
                existing.label = field.label
                existing.normalized_label = field.normalized_label
                existing.control_type = field.control_type
    return merged


def order_fields(fields: list[TargetField]) -> list[TargetField]:
    """Sort fields top-to-bottom, then left-to-right (reading order)."""
    return sorted(
        fields,
        key=lambda f: (f.bounds.top, f.bounds.left) if f.bounds else (10**9, 10**9),
    )


class PerceptionStack:
    """Combines all available field-discovery channels for one target window."""

    def __init__(self, backend: Any | None = None, ocr_reader: Any | None = None) -> None:
        self._backend = backend
        self._ocr_reader = ocr_reader

    @property
    def backend(self) -> Any | None:
        return self._backend

    def discover_uia(self, handle: int) -> list[TargetField]:
        """UIA channel: editable controls from the accessibility tree."""
        if self._backend is None or not getattr(self._backend, "available", False):
            return []
        try:
            nodes = self._backend.editable_fields(handle)
        except Exception as exc:
            logger.debug("perception: UIA editable_fields failed: {}", exc)
            nodes = []
        fields = from_uia_nodes(nodes)
        perception_logger.info(
            "[PERCEPTION] UIA fields: {} editable control(s)",
            len(fields),
        )
        return fields

    def discover_cv(self, image: Any, offset: tuple[int, int] = (0, 0)) -> list[TargetField]:
        """OCR/CV channel: bordered inputs + OCR labels from a screenshot."""
        if image is None:
            return []
        try:
            fields = discover_fields_from_image(image, self._ocr_reader, offset)
        except Exception as exc:
            logger.debug("perception: CV/OCR discovery failed: {}", exc)
            return []
        perception_logger.info(
            "[PERCEPTION] OCR/CV fields: {} input control(s)",
            len(fields),
        )
        return fields

    def discover(
        self,
        handle: int | None = None,
        image: Any | None = None,
        offset: tuple[int, int] = (0, 0),
    ) -> list[TargetField]:
        """Run every channel and merge into one ordered field list."""
        uia_fields = self.discover_uia(handle) if handle is not None else []
        cv_fields = self.discover_cv(image, offset)
        merged = merge_fields(uia_fields, cv_fields)
        ordered = order_fields(merged)
        by_source: dict[str, int] = {}
        for f in ordered:
            by_source[f.source.value] = by_source.get(f.source.value, 0) + 1
        perception_logger.info(
            "[MERGED] {} field(s) discovered: {} | UIA={} CV/OCR={}",
            len(ordered),
            ", ".join(f"{k}={v}" for k, v in by_source.items()),
            len(uia_fields),
            len(cv_fields),
        )
        return ordered


__all__ = ["PerceptionStack", "from_uia_nodes", "merge_fields", "order_fields"]
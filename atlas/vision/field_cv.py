"""CV + OCR field discovery.

The engine's field discovery must not depend on a single accessibility channel.
When UIA reports zero editable controls (a documented intermittent failure on
the real MPF app), the screenshot still contains the form: bordered input
rectangles, dropdown arrows, checkbox squares, date pickers and their printed
labels. This module finds those fields deterministically with OpenCV and
attaches OCR labels, producing the same :class:`~atlas.understanding.target_field.TargetField`
model the UIA channel produces - so the merged perception stack has something
real to fill even when UIA is empty.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from atlas.understanding.target_field import (
    TargetControlType,
    TargetField,
    FieldSource,
    interaction_strategy_for,
    verification_strategy_for,
)
from atlas.vision.models import BBox, OcrText

_MIN_INPUT_W = 24
_MIN_INPUT_H = 10
_MAX_INPUT_W_FRACTION = 0.7
_MAX_INPUT_H = 64
_CHECKBOX_MAX = 26  # checkbox / radio squares are small
_DATE_RE = re.compile(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}")
_NUMBER_RE = re.compile(r"^[0-9][0-9,\s]{2,}$")


@dataclass
class InputCandidate:
    """A bordered region that looks like a fillable control."""

    bbox: BBox
    kind: TargetControlType = TargetControlType.TEXT
    confidence: float = 0.45
    has_arrow: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"bbox": self.bbox.to_dict(), "kind": self.kind.value, "confidence": self.confidence}


def discover_input_candidates(image: np.ndarray) -> list[InputCandidate]:
    """Detect bordered input controls in a screenshot (capture coordinates).

    Detects: bordered input boxes, dropdown arrows (combo/dropdown), small
    square checkboxes, radio circles, date pickers and numeric fields. Runs a
    fixed OpenCV pipeline; never raises (empty list on failure).
    """
    try:
        import cv2
    except ImportError:  # pragma: no cover - opencv optional
        return []

    candidates: list[InputCandidate] = []
    try:
        if image is None or image.size == 0:
            return candidates
        height, width = image.shape[:2]
        if width == 0 or height == 0:
            return candidates
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        gray = cv2.medianBlur(gray, 3)

        edged = cv2.Canny(gray, 50, 150)
        dilated = cv2.dilate(edged, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if not (w >= 1 and h >= 1 and 0 <= x < width and 0 <= y < height):
                continue
            if w > int(width * _MAX_INPUT_W_FRACTION):
                continue
            if not (_MIN_INPUT_H <= h <= _MAX_INPUT_H):
                continue
            if w < _MIN_INPUT_W and not (8 <= w <= _CHECKBOX_MAX and abs(w - h) <= 8):
                continue
            box = BBox(int(x), int(y), int(w), int(h))

            # Small square -> checkbox; near-square small -> radio-ish toggle.
            if w <= _CHECKBOX_MAX and abs(w - h) <= 8:
                candidates.append(
                    InputCandidate(box, TargetControlType.CHECKBOX, confidence=0.4)
                )
                continue
            if w / max(h, 1) <= 1.2:
                # tall/narrow box (e.g. date part, spinner) - keep as custom input
                candidates.append(
                    InputCandidate(box, TargetControlType.CUSTOM, confidence=0.4)
                )
                continue

            kind = TargetControlType.TEXT
            has_arrow = _has_dropdown_arrow(gray, box)
            if has_arrow:
                kind = TargetControlType.COMBOBOX
            candidates.append(InputCandidate(box, kind, confidence=0.45, has_arrow=has_arrow))
    except Exception:
        return []

    # Drop boxes fully nested inside another candidate (outline + inner border).
    candidates = _drop_nested(candidates)
    return candidates


def _drop_nested(candidates: list[InputCandidate]) -> list[InputCandidate]:
    """Remove a candidate that is entirely inside another (duplicate border)."""
    kept: list[InputCandidate] = []
    for c in candidates:
        nested = False
        for other in candidates:
            if other is c:
                continue
            if _contains_box(other.bbox, c.bbox):
                nested = True
                break
        if not nested:
            kept.append(c)
    return kept


def _contains_box(outer: BBox, inner: BBox) -> bool:
    return (
        outer.left <= inner.left
        and outer.top <= inner.top
        and outer.right >= inner.right
        and outer.bottom >= inner.bottom
    )


def _has_dropdown_arrow(gray: np.ndarray, box: BBox) -> bool:
    """A dropdown arrow is a dark cluster near the box's right edge."""
    try:
        import cv2
    except ImportError:  # pragma: no cover
        return False
    try:
        w, h = box.width, box.height
        right_strip = gray[box.top + h // 4 : box.bottom - h // 4, box.right - max(6, w // 6) : box.right]
        body_strip = gray[box.top + h // 4 : box.bottom - h // 4, box.left : box.left + w // 2]
        if right_strip.size == 0 or body_strip.size == 0:
            return False
        right_dark = float(np.mean(cv2.threshold(right_strip, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]))
        body_dark = float(np.mean(cv2.threshold(body_strip, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]))
        return right_dark > max(2.0, body_dark * 1.8) and right_dark > 6.0
    except Exception:
        return False


def _texts_inside(box: BBox, texts: list[OcrText]) -> str:
    """Join OCR text that falls inside the box (the control's current value)."""
    parts = []
    for t in texts:
        b = t.bbox
        if b.left >= box.left and b.right <= box.right and b.top >= box.top and b.bottom <= box.bottom:
            parts.append(t.text.strip())
    return " ".join(parts).strip()


def associate_label(candidate: BBox, texts: list[OcrText]) -> str:
    """Associate the printed label that best names a candidate control.

    Preference order: (1) a text line directly above the box whose horizontal
    center overlaps the box, (2) a text line to the left of the box on the same
    row. The closest vertical/horizontal gap wins; longer labels score higher.
    """
    best_label = ""
    best_score = -1.0
    for t in texts:
        b = t.bbox
        label = t.text.strip()
        if not label or _texts_inside(candidate, [t]):
            continue
        # Directly above.
        if b.bottom <= candidate.top + 4:
            cx = b.left + b.width / 2
            if candidate.left - b.width <= cx <= candidate.right + b.width:
                gap = candidate.top - b.bottom
                score = 1.0 / (gap + 4.0) + min(1.0, len(label) / 20.0)
                if gap < 60 and score > best_score:
                    best_score = score
                    best_label = label
        # To the left, same row band.
        elif b.right <= candidate.left and abs(b.top - candidate.top) <= candidate.height:
            gap = candidate.left - b.right
            score = 1.0 / (gap + 4.0) + min(1.0, len(label) / 20.0)
            if gap < 120 and score > best_score:
                best_score = score
                best_label = label
    return best_label


def _refine_kind(candidate: InputCandidate, value: str) -> TargetControlType:
    """Upgrade TEXT candidates to DATE / NUMBER from their current value."""
    if candidate.kind != TargetControlType.TEXT:
        return candidate.kind
    if _DATE_RE.search(value):
        return TargetControlType.DATE
    if _NUMBER_RE.match(value):
        return TargetControlType.NUMBER
    return candidate.kind


def discover_fields_from_image(
    image: np.ndarray,
    ocr_reader: Any | None = None,
    offset: tuple[int, int] = (0, 0),
) -> list[TargetField]:
    """OCR a screenshot and produce ``TargetField`` objects for every control.

    ``offset`` is the capture origin on the physical screen; field bounds are
    translated to absolute screen coordinates (the executor's contract).
    """
    texts: list[OcrText] = []
    if ocr_reader is not None:
        try:
            texts = ocr_reader.read_image(image)
        except Exception:
            texts = []
    candidates = discover_input_candidates(image)
    dx, dy = offset
    fields: list[TargetField] = []
    for i, cand in enumerate(candidates):
        box = cand.bbox.shifted(dx, dy)
        value = _texts_inside(cand.bbox, texts)
        kind = _refine_kind(cand, value)
        label = associate_label(cand.bbox, texts)
        norm = label.strip().lower().rstrip(":").strip()
        source = FieldSource.OCR if ocr_reader is not None else FieldSource.CV
        confidence = cand.confidence if label else cand.confidence * 0.6
        fields.append(
            TargetField(
                id=f"cv-{i}",
                label=label,
                normalized_label=norm,
                control_type=kind,
                bounds=box,
                value=value or None,
                visible=True,
                enabled=True,
                editable=True,
                source=source,
                confidence=confidence,
                interaction_strategy=interaction_strategy_for(kind, source),
                verification_strategy=verification_strategy_for(kind, source),
                ref=cand,
            )
        )
    return fields


__all__ = ["InputCandidate", "discover_input_candidates", "associate_label", "discover_fields_from_image"]
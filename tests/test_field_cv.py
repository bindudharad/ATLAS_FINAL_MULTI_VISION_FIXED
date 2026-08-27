"""Tests for CV/OCR field discovery (pure-python parts)."""

from __future__ import annotations

import numpy as np

from atlas.understanding.target_field import TargetControlType
from atlas.vision.field_cv import (
    _drop_nested,
    _texts_inside,
    associate_label,
    discover_input_candidates,
)
from atlas.vision.models import BBox, OcrText


def _txt(text: str, x: int, y: int, w: int = 40, h: int = 14) -> OcrText:
    return OcrText(text=text, bbox=BBox(x, y, w, h))


def test_associate_label_prefers_directly_above() -> None:
    box = BBox(200, 100, 150, 22)
    texts = [_txt("State", 180, 60, 50), _txt("District", 180, 130, 50)]
    assert associate_label(box, texts) == "State"


def test_associate_label_falls_back_to_left_same_row() -> None:
    box = BBox(200, 100, 150, 22)
    texts = [_txt("Full Name", 60, 102, 80)]
    assert associate_label(box, texts) == "Full Name"


def test_associate_label_ignores_text_inside_the_box() -> None:
    box = BBox(200, 100, 150, 22)
    texts = [_txt("Karnataka", 210, 104, 70), _txt("State", 180, 60, 50)]
    assert associate_label(box, texts) == "State"


def test_associate_label_empty_when_no_candidate() -> None:
    box = BBox(200, 100, 150, 22)
    assert associate_label(box, [_txt("far away", 20, 400, 50)]) == ""


def test_texts_inside_joins_contained_text() -> None:
    box = BBox(100, 100, 100, 20)
    texts = [_txt("a", 110, 103, 10), _txt("b", 130, 103, 10), _txt("out", 300, 103, 10)]
    assert _texts_inside(box, texts) == "a b"


def test_drop_nested_removes_inner_border_duplicates() -> None:
    outer = BBox(100, 100, 200, 40)
    inner = BBox(110, 105, 100, 30)
    from atlas.vision.field_cv import InputCandidate

    kept = _drop_nested([
        InputCandidate(outer, TargetControlType.TEXT, 0.45),
        InputCandidate(inner, TargetControlType.TEXT, 0.45),
    ])
    assert len(kept) == 1
    assert kept[0].bbox is outer


def test_discover_input_candidates_never_raises() -> None:
    # Blank / tiny images must return an empty list (never raise), whether or
    # not OpenCV is installed.
    blank = np.zeros((10, 10, 3), dtype=np.uint8)
    assert discover_input_candidates(blank) == []
    assert discover_input_candidates(None) == []
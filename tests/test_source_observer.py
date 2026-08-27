"""Tests for ``atlas.observe.source_observer`` - the visual LEFT source-panel
reader that crops, OCRs and VLM-reads the record from the image so a record is
never rejected just because UIA exposed no label/value rows.

Also covers the vision provider factory fix (a single named API key must use a
real VLM, never the rule fallback) and the exact no-record reason codes.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from atlas.config import SourceConfig
from atlas.observe.source_observer import (
    ALL_PAIRS_EMPTY,
    CAPTURE_FAILED,
    HARD_FAILURE_CODES,
    NO_TEXT_DETECTED,
    SOURCE_NOT_FOUND,
    SourceObserver,
    VISION_FAILED,
)
from atlas.vision.models import BBox, OcrText
from atlas.vision.providers import (
    MockVisionProvider,
    OpenAIVisionProvider,
    RuleVisionProvider,
    create_vision_provider,
    vision_status_lines,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeVlm:
    """Minimal VLM stand-in with ``is_vlm`` + ``read_source_pairs``."""

    name = "fake-vlm"
    is_vlm = True

    def __init__(self, pairs, failure: Exception | None = None) -> None:
        self._pairs = list(pairs)
        self._failure = failure
        self.calls = 0

    def read_source_pairs(self, image, known_labels=None):
        self.calls += 1
        if self._failure is not None:
            raise self._failure
        return [tuple(p) for p in self._pairs]

    def describe(self, image, window_title="", url=None):
        return None


class FakeOcr:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self.calls = 0

    def __call__(self, image) -> list[OcrText]:
        self.calls += 1
        return [OcrText(text=line, bbox=BBox(0, 0, 10, 10)) for line in self._lines]


def _cfg(**overrides) -> SourceConfig:
    base = SourceConfig(panel_ratio=0.5, observe_timeout=2.0, retries=1, vlm_confidence=0.5)
    return dataclasses.replace(base, **overrides)


IMG = np.zeros((32, 64, 3), dtype=np.uint8)


def _observer(*, capture=None, ocr=None, vlm=None, cfg=None, left=None, client=None) -> SourceObserver:
    cfg = cfg or _cfg()
    # Default to a resolvable LEFT panel so most tests reach the crop path.
    default_left = BBox(0, 0, 64, 32)
    rect = left if left is not None else default_left
    client = client if client is not None else (0, 0, 200, 100)
    return SourceObserver(
        capture=capture or (lambda bbox: IMG),
        ocr=ocr or FakeOcr([]),
        vision_provider=vlm,
        config=cfg,
        left_rect_provider=(lambda: rect),
        client_rect_provider=(lambda: client),
        timeout=cfg.observe_timeout,
    )


# ---------------------------------------------------------------------------
# Failure reason codes (exact diagnostics, never a generic "no record")
# ---------------------------------------------------------------------------


def test_source_not_found_when_no_rect() -> None:
    obs = SourceObserver(
        capture=lambda bbox: IMG,
        ocr=FakeOcr([]),
        vision_provider=None,
        config=_cfg(),
    ).observe()
    assert obs.error_reason == SOURCE_NOT_FOUND
    assert not obs.ok
    assert obs.pairs == []


def test_client_rect_ratio_used_when_no_left_rect() -> None:
    obs = SourceObserver(
        capture=lambda bbox: IMG,
        ocr=FakeOcr(["App No:12345", "Full Name:ALICE"]),
        vision_provider=None,
        config=_cfg(panel_ratio=0.5),
        client_rect_provider=lambda: (100, 200, 900, 700),
    ).observe()
    assert obs.ok
    assert dict(obs.pairs).get("Full Name") == "ALICE"


def test_capture_failed() -> None:
    obs = _observer(capture=lambda bbox: None).observe()
    assert obs.error_reason == CAPTURE_FAILED


def test_no_text_detected() -> None:
    obs = _observer(ocr=FakeOcr([])).observe()
    assert obs.error_reason == NO_TEXT_DETECTED


def test_all_pairs_empty_when_ocr_text_has_no_colons() -> None:
    # OCR sees text lines but none parse into a label/value pair.
    obs = _observer(ocr=FakeOcr(["Member Basic Information"])).observe()
    assert obs.error_reason == ALL_PAIRS_EMPTY


def test_vlm_failure_reports_vision_failed_when_no_other_channel() -> None:
    obs = _observer(ocr=FakeOcr([]), vlm=FakeVlm([], failure=RuntimeError("boom"))).observe()
    assert obs.error_reason == VISION_FAILED


def test_hard_failure_codes_are_exposed() -> None:
    assert SOURCE_NOT_FOUND in HARD_FAILURE_CODES
    assert CAPTURE_FAILED in HARD_FAILURE_CODES
    assert NO_TEXT_DETECTED in HARD_FAILURE_CODES
    assert ALL_PAIRS_EMPTY in HARD_FAILURE_CODES
    assert VISION_FAILED in HARD_FAILURE_CODES


# ---------------------------------------------------------------------------
# Image-based reading: OCR + VLM merged
# ---------------------------------------------------------------------------


def test_ocr_colon_lines_are_paired() -> None:
    obs = _observer(ocr=FakeOcr(["App No:32394824", "Full Name:ABHISHEK ROY"])).observe()
    assert obs.ok
    pairs = dict(obs.pairs)
    assert pairs["App No"] == "32394824"
    assert pairs["Full Name"] == "ABHISHEK ROY"


def test_vlm_pairs_merged_when_ocr_empty() -> None:
    vlm = FakeVlm([("App No", "88888888", 0.99), ("Gender", "Male", 0.9)])
    obs = _observer(ocr=FakeOcr([]), vlm=vlm).observe()
    assert obs.ok
    pairs = dict(obs.pairs)
    assert pairs["App No"] == "88888888"
    assert obs.source in {"vision", "merged"}


def test_merge_priority_uia_over_ocr_over_vlm() -> None:
    # UIA value wins over a DIFFERENT OCR/VLM value for the same label.
    vlm = FakeVlm([("App No", "FROM_VLM", 0.99)])
    obs = _observer(
        ocr=FakeOcr(["App No:FROM_OCR"]),
        vlm=vlm,
    ).observe(uia_pairs=[("App No", "FROM_UIA")])
    assert dict(obs.pairs)["App No"] == "FROM_UIA"


def test_empty_high_priority_never_overwrites_nonempty_lower() -> None:
    vlm = FakeVlm([("App No", "88888888", 0.99)])
    obs = _observer(ocr=FakeOcr(["App No:FROM_OCR"]), vlm=vlm).observe(
        uia_pairs=[("App No", "")]
    )
    assert dict(obs.pairs)["App No"] == "FROM_OCR"


# ---------------------------------------------------------------------------
# No-hallucination grounding
# ---------------------------------------------------------------------------


def _label_node(name: str):
    from types import SimpleNamespace

    return SimpleNamespace(name=name, value=None, rect=None)


def test_vlm_label_grounded_to_known_schema() -> None:
    known = [_label_node("App No"), _label_node("Full Name"), _label_node("Gender")]
    vlm = FakeVlm([("App No", "12345", 0.9), ("Made Up Field", "XYZ", 0.99)])
    obs = _observer(ocr=FakeOcr([]), vlm=vlm).observe(known_labels=known)
    pairs = dict(obs.pairs)
    assert "App No" in pairs
    assert "Made Up Field" not in pairs  # hallucination rejected


def test_low_confidence_ungrounded_pair_rejected_without_schema() -> None:
    vlm = FakeVlm([("Ghost Field", "Invented Value", 0.55)])
    obs = _observer(ocr=FakeOcr([]), vlm=vlm).observe()
    assert "Ghost Field" not in dict(obs.pairs)


def test_high_confidence_ungrounded_pair_accepted_without_schema() -> None:
    vlm = FakeVlm([("Reliable Field", "Reliable Value", 0.95)])
    obs = _observer(ocr=FakeOcr([]), vlm=vlm).observe()
    assert dict(obs.pairs).get("Reliable Field") == "Reliable Value"


# ---------------------------------------------------------------------------
# Change detection: unchanged crop skips OCR + VLM
# ---------------------------------------------------------------------------


def test_unchanged_crop_uses_phash_cache() -> None:
    ocr = FakeOcr(["App No:12345", "Full Name:ALICE"])
    vlm = FakeVlm([])
    obs = _observer(ocr=ocr, vlm=vlm)

    first = obs.observe()
    assert first.ok and dict(first.pairs)["App No"] == "12345"
    assert ocr.calls == 1

    second = obs.observe()
    assert second.ok and dict(second.pairs)["App No"] == "12345"
    assert ocr.calls == 1  # not re-run
    assert second.source == "cached"


def test_changed_crop_re_observes() -> None:
    ocr = FakeOcr(["App No:12345"])
    obs = _observer(ocr=ocr)
    obs.observe()
    assert ocr.calls == 1
    obs.observe()
    # Same image hash -> cached; a NEW image forces a re-read.
    assert ocr.calls == 1
    obs._capture = lambda bbox: np.ones((32, 64, 3), dtype=np.uint8) * 7
    obs.observe()
    assert ocr.calls == 2


# ---------------------------------------------------------------------------
# VLM failure still falls back to OCR
# ---------------------------------------------------------------------------


def test_vlm_failure_falls_back_to_ocr() -> None:
    vlm = FakeVlm([], failure=TimeoutError("timed out"))
    obs = _observer(ocr=FakeOcr(["App No:5555", "MBI Code:MBI1"]), vlm=vlm).observe()
    assert obs.ok
    assert dict(obs.pairs)["App No"] == "5555"
    assert obs.source == "ocr"


# ---------------------------------------------------------------------------
# Vision factory fix: a single named key must use a real VLM
# ---------------------------------------------------------------------------


def test_factory_uses_vlm_for_single_named_key() -> None:
    from atlas.config import VisionConfig

    cfg = VisionConfig(provider="auto", groq_api_key="qk")
    provider = create_vision_provider(cfg)
    assert provider.is_vlm is True


def test_rule_provider_is_never_a_vlm() -> None:
    rule = RuleVisionProvider(ocr_reader=None) if False else None
    import atlas.vision.providers as p

    # Rule provider must return [] (never fabricate) and report is_vlm False.
    assert p.RuleVisionProvider.is_vlm is False
    assert p.MockVisionProvider.is_vlm is False
    assert p.OpenAIVisionProvider.is_vlm is True


def test_rule_provider_read_source_pairs_empty() -> None:
    from atlas.vision.providers import RuleVisionProvider

    try:
        rule = RuleVisionProvider(ocr_reader=None)
    except RuntimeError:
        pytest.skip("opencv not installed")
    assert rule.read_source_pairs(IMG) == []
    assert rule.is_vlm is False


def test_vision_status_lines_configured() -> None:
    from atlas.config import VisionConfig

    cfg = VisionConfig(provider="auto", groq_api_key="qk", google_api_key="gk")
    lines = vision_status_lines(cfg)
    assert any("Groq: CONFIGURED" in line for line in lines)
    assert any("multi-fallback" in line for line in lines)


def test_vision_status_lines_rule_fallback() -> None:
    from atlas.config import VisionConfig

    cfg = VisionConfig(provider="auto")
    lines = vision_status_lines(cfg)
    assert any("rule-based fallback" in line for line in lines)


def test_mock_provider_default_read_source_pairs() -> None:
    mock = MockVisionProvider()
    assert mock.read_source_pairs(IMG) == []
    assert mock.is_vlm is False
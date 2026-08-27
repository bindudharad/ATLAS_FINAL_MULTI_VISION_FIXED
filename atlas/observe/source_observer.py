"""Visual LEFT source-panel observer.

Reads the source record the way a human does: the LEFT panel is treated as an
IMAGE. The panel region is cropped from the screen, OCR'd and - when a real
VLM is configured - sent to the VLM with a structured no-hallucination prompt
that returns ``label/value`` pairs. UIA cheap reads, OCR and the VLM are
merged with priority UIA > OCR > VLM: a non-empty value from a higher-priority
channel never gets overwritten by an empty lower-priority one.

A perceptual hash of the crop skips redundant re-observation while the panel
is unchanged, and every channel is bounded (``SourceConfig.retries`` +
``observe_timeout``) so the observer can never block the loop for more than a
few seconds.

Every failure returns an exact reason code (SOURCE_NOT_FOUND, CAPTURE_FAILED,
OCR_FAILED, VISION_FAILED, NO_TEXT_DETECTED, ALL_PAIRS_EMPTY) instead of a
generic "no valid record", so a run that produces 0 records can be
root-caused from the diagnostics instead of guessed at.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from atlas.core.logging import logger
from atlas.mapping.uia_map import is_noise_label, pair_source_pairs
from atlas.vision.models import BBox, OcrText

#: Exact failure reason codes (surfaced in debug/no_record.json + events).
SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
CAPTURE_FAILED = "CAPTURE_FAILED"
OCR_FAILED = "OCR_FAILED"
VISION_FAILED = "VISION_FAILED"
NO_TEXT_DETECTED = "NO_TEXT_DETECTED"
ALL_PAIRS_EMPTY = "ALL_PAIRS_EMPTY"

#: Hard failures after which the await loop should stop instead of spinning
#: forever (a genuine, visible source panel that can never be read).
HARD_FAILURE_CODES = {
    SOURCE_NOT_FOUND,
    CAPTURE_FAILED,
    VISION_FAILED,
    NO_TEXT_DETECTED,
    ALL_PAIRS_EMPTY,
}

#: Threshold above which a VLM pair is trusted without visible-text grounding
#: (used only when no known field schema is available to ground against).
_UNGROUNDED_TRUST_CONFIDENCE = 0.85


def _clean_label(text: str) -> str:
    return re.sub(r"[:：\s]+$", "", (text or "")).strip()


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


@dataclass
class SourceObservation:
    """Result of one source-panel observation cycle."""

    pairs: list[tuple[str, str]] = field(default_factory=list)
    #: Dominant channel that produced the pairs: "uia" | "ocr" | "vision" |
    #: "merged" | "cached".
    source: str = "none"
    #: Active vision provider name ("" = none / rule-based).
    provider: str = ""
    confidence: float = 0.0
    error_reason: str | None = None
    channel_counts: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error_reason is None

    @property
    def valued_pairs(self) -> list[tuple[str, str]]:
        return [(label, value) for label, value in self.pairs if str(value).strip()]

    def to_dict(self) -> dict[str, Any]:
        return {
            "pairs": [{"label": label, "value": value} for label, value in self.pairs],
            "source": self.source,
            "provider": self.provider,
            "confidence": round(self.confidence, 3),
            "error_reason": self.error_reason,
            "channel_counts": dict(self.channel_counts),
        }


class SourceObserver:
    """Crops, OCRs and VLM-reads the LEFT source panel into label/value pairs.

    Constructed with injected callbacks so it is fully unit-testable without
    a live window, real OCR engine or network.
    """

    def __init__(
        self,
        *,
        capture: Callable[[BBox], np.ndarray | None],
        ocr: Callable[[np.ndarray], list[OcrText]],
        vision_provider: Any | None,
        config: Any,
        left_rect_provider: Callable[[], BBox | None] | None = None,
        client_rect_provider: Callable[[], tuple[int, int, int, int] | None] | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._capture = capture
        self._ocr = ocr
        self._vision = vision_provider
        self._config = config
        self._left_rect_provider = left_rect_provider
        self._client_rect_provider = client_rect_provider
        self._timeout = timeout
        self._cache_hash: str | None = None
        self._cache_pairs: list[tuple[str, str]] = []
        self._cache_confidence: float = 0.0
        self._cache_source: str = "cached"

    # -- public API ----------------------------------------------------------

    def observe(
        self,
        uia_pairs: list[tuple[str, str]] | None = None,
        known_labels: list[Any] | None = None,
        left_rect: BBox | None = None,
    ) -> SourceObservation:
        """Read the LEFT source panel and return merged label/value pairs.

        ``uia_pairs`` are already-paired UIA rows (if any) and ``known_labels``
        are the schema's UIA label nodes (used to ground VLM output against a
        known field set, preventing hallucinated fields). ``left_rect`` (when
        supplied by the caller) is the absolute-screen source-panel region.
        """
        left = left_rect or self._resolve_panel_rect()
        if left is None:
            return SourceObservation(error_reason=SOURCE_NOT_FOUND)

        crop = self._capture_crop(left)
        if crop is None:
            return SourceObservation(error_reason=CAPTURE_FAILED)

        if self._config.phash_cache:
            cached = self._cached_if_unchanged(crop)
            if cached is not None:
                merged = self._merge(uia_pairs or [], cached)
                if known_labels:
                    merged = self._gate_member_pairs(merged)
                return SourceObservation(
                    pairs=merged,
                    source="cached",
                    provider=self._provider_name(),
                    confidence=self._cache_confidence,
                    channel_counts={"cached": len(cached)},
                )

        ocr_lines = self._read_ocr(crop)
        ocr_pairs = pair_source_pairs(
            ocr_lines, known_labels or None, member_only=bool(known_labels)
        )

        vlm_pairs: list[tuple[str, str, float]] = []
        provider_name = ""
        if self._vision is not None and getattr(self._vision, "is_vlm", False):
            vlm_pairs, provider_name = self._read_vlm(crop, known_labels)
            vlm_pairs = self._ground_vlm(vlm_pairs, ocr_lines, known_labels)

        merged = self._merge(uia_pairs or [], ocr_pairs, [(l, v) for l, v, _ in vlm_pairs])
        if known_labels:
            merged = self._gate_member_pairs(merged)
        source, confidence = self._classify(uia_pairs or [], ocr_pairs, vlm_pairs, provider_name)

        if not merged:
            vlm_attempted = bool(provider_name) and not vlm_pairs
            if ocr_lines and not vlm_attempted:
                reason = ALL_PAIRS_EMPTY
            elif vlm_attempted:
                reason = VISION_FAILED
            else:
                reason = NO_TEXT_DETECTED
            return SourceObservation(error_reason=reason, provider=provider_name)

        if self._config.phash_cache:
            self._cache_hash = self._phash(crop)
            self._cache_pairs = list(merged)
            self._cache_confidence = confidence
            self._cache_source = source
        return SourceObservation(
            pairs=merged,
            source=source,
            provider=provider_name,
            confidence=confidence,
            channel_counts={
                "uia": len(uia_pairs or []),
                "ocr": len(ocr_pairs),
                "vision": len(vlm_pairs),
            },
        )

    # -- panel geometry -------------------------------------------------------

    def _resolve_panel_rect(self) -> BBox | None:
        if self._left_rect_provider is not None:
            try:
                rect = self._left_rect_provider()
            except Exception:
                rect = None
            if rect is not None and rect.width > 0 and rect.height > 0:
                return rect
        if self._client_rect_provider is not None:
            try:
                client = self._client_rect_provider()
            except Exception:
                client = None
            if client is not None:
                left, top, right, bottom = client
                width = max(0, right - left)
                height = max(0, bottom - top)
                if width > 0 and height > 0:
                    return BBox(left, top, max(1, int(width * float(getattr(self._config, "panel_ratio", 0.5)))), height)
        return None

    # -- capture + OCR ---------------------------------------------------------

    def _capture_crop(self, rect: BBox) -> np.ndarray | None:
        retries = max(0, int(getattr(self._config, "retries", 0)))
        for attempt in range(retries + 1):
            try:
                crop = self._capture(rect)
            except Exception as exc:
                logger.debug("source capture failed ({}): {}", attempt, exc)
                crop = None
            if crop is not None and int(getattr(crop, "size", 0) or 0) > 0:
                return crop
            if attempt < retries:
                time.sleep(0.2)
        return None

    def _read_ocr(self, crop: np.ndarray) -> list[OcrText]:
        try:
            lines = self._ocr(crop) or []
        except Exception as exc:
            logger.debug("source OCR failed: {}", exc)
            return []
        return [line for line in lines if getattr(line, "text", "")]

    # -- VLM --------------------------------------------------------------------

    def _read_vlm(
        self,
        crop: np.ndarray,
        known_labels: list[Any] | None,
    ) -> tuple[list[tuple[str, str, float]], str]:
        retries = max(0, int(getattr(self._config, "retries", 0)))
        known_names = [_clean_label(getattr(n, "name", "") or str(n)) for n in (known_labels or [])]
        for attempt in range(retries + 1):
            deadline = time.monotonic() + max(1.0, self._timeout)
            try:
                raw = self._vision.read_source_pairs(crop, known_labels=known_names or None)
                out = [
                    (label, value, conf)
                    for label, value, conf in raw
                    if conf >= float(getattr(self._config, "vlm_confidence", 0.5))
                ]
                return out, str(getattr(self._vision, "name", "vision"))
            except Exception as exc:
                logger.debug("source VLM read failed ({}): {}", attempt, exc)
                if attempt < retries and time.monotonic() < deadline:
                    time.sleep(0.3)
        return [], str(getattr(self._vision, "name", "vision"))

    def _ground_vlm(
        self,
        vlm_pairs: list[tuple[str, str, float]],
        ocr_lines: list[OcrText],
        known_labels: list[Any] | None,
    ) -> list[tuple[str, str, float]]:
        """No-hallucination guard for VLM output.

        With a known field schema the label must match a schema field name.
        Without a schema, the value/label must appear in the OCR-visible text
        (unless the VLM is highly confident) so invented rows are rejected.
        """
        if not vlm_pairs:
            return []
        known_set = {_normalize(_clean_label(getattr(n, "name", "") or str(n))) for n in (known_labels or [])}
        ocr_text = " ".join(getattr(line, "text", "") for line in ocr_lines).lower()
        out: list[tuple[str, str, float]] = []
        for label, value, conf in vlm_pairs:
            norm = _normalize(label)
            if known_set:
                if not any(norm and (norm == known or norm in known or known in norm) for known in known_set):
                    continue
            else:
                if not (
                    value.lower() in ocr_text
                    or _normalize(value) in ocr_text
                    or conf >= _UNGROUNDED_TRUST_CONFIDENCE
                ):
                    continue
            out.append((label, value, conf))
        return out

    # -- merge + classify ----------------------------------------------------------

    @staticmethod
    def _gate_member_pairs(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Drop every pair that is not a member field (FIX #8/10).

        The member schema is authoritative: Project Details / Shift Details /
        timer / progress / button rows must never become source data.
        """
        from atlas.mapping.member_fields import filter_member_pairs

        return filter_member_pairs(pairs)

    @staticmethod
    def _merge(*sources: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Merge (label, value) channels; first non-empty value per label wins."""
        merged: dict[str, str] = {}
        ordered: list[str] = []
        for source_pairs in sources:
            for raw_label, raw_value in source_pairs:
                label = _clean_label(raw_label)
                value = (raw_value or "").strip()
                if not label or is_noise_label(label):
                    continue
                if label not in merged:
                    merged[label] = value
                    ordered.append(label)
                elif not merged[label] and value:
                    merged[label] = value
        return [(label, merged[label]) for label in ordered]

    def _classify(
        self,
        uia_pairs: list[tuple[str, str]],
        ocr_pairs: list[tuple[str, str]],
        vlm_pairs: list[tuple[str, str, float]],
        provider_name: str,
    ) -> tuple[str, float]:
        channels = sum(1 for src in (uia_pairs, ocr_pairs, vlm_pairs) if src)
        if uia_pairs:
            confidence = 0.9
        elif ocr_pairs and vlm_pairs:
            confidence = min(0.95, max(0.6, sum(c for _, _, c in vlm_pairs) / len(vlm_pairs)))
        elif ocr_pairs:
            confidence = 0.6
        else:
            confidence = (
                min(0.95, sum(c for _, _, c in vlm_pairs) / len(vlm_pairs))
                if vlm_pairs
                else 0.0
            )
        if channels >= 2:
            source = "merged"
        elif uia_pairs:
            source = "uia"
        elif ocr_pairs:
            source = "ocr"
        elif vlm_pairs:
            source = "vision"
        else:
            source = "none"
        return source, float(confidence)

    def _provider_name(self) -> str:
        if self._vision is None:
            return ""
        return str(getattr(self._vision, "name", "vision"))

    # -- change detection ------------------------------------------------------------

    def _phash(self, image: np.ndarray) -> str:
        try:
            small = image[::8, ::8]
            return hashlib.md5(np.ascontiguousarray(small).tobytes()).hexdigest()
        except Exception:  # pragma: no cover - defensive
            return ""

    def _cached_if_unchanged(self, crop: np.ndarray) -> list[tuple[str, str]] | None:
        if self._cache_hash is None or not self._cache_pairs:
            return None
        current = self._phash(crop)
        if current and current == self._cache_hash:
            return list(self._cache_pairs)
        return None


__all__ = [
    "SourceObserver",
    "SourceObservation",
    "SOURCE_NOT_FOUND",
    "CAPTURE_FAILED",
    "OCR_FAILED",
    "VISION_FAILED",
    "NO_TEXT_DETECTED",
    "ALL_PAIRS_EMPTY",
    "HARD_FAILURE_CODES",
]
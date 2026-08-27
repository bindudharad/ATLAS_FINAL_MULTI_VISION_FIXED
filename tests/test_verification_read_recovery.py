"""Regression tests for the UNKNOWN read-recovery ladder.

Real runs showed SELECT-style fields (Height, Weight, Rashi, Annual Income -
custom/typed combo controls) repeatedly landing on UNKNOWN verification with
"vision read empty" / "uia read empty" on every recovery attempt. Two gaps
caused this:

1. No settle delay was inserted before a recovery read unless a refocus
   callback was supplied - and SELECT actions never get one (clicking again
   could re-open the popup) - so the retry re-read the exact same "still
   repainting" frame.
2. The bbox used for every recovery attempt was identical to the original,
   so a value that rendered just outside the original rect (common once a
   custom combo's popup closes and the control reflows) was never found.

These tests lock in the fix: a settle delay always happens before a
recovery read, and the final attempt widens the read region.
"""

from __future__ import annotations

import time

from atlas.act.verification import VerificationEngine, VerificationStatus
from atlas.act.verify import FieldVerifier
from atlas.vision.models import BBox


class _UnknownThenBboxSensitiveVerifier(FieldVerifier):
    """Always UNKNOWN unless it is asked to read a widened region."""

    name = "fixed"

    def __init__(self) -> None:
        self.seen_bboxes: list[BBox | None] = []
        self.call_times: list[float] = []

    def verify(self, bbox, expected, field_id=None):
        self.seen_bboxes.append(bbox)
        self.call_times.append(time.monotonic())
        # Simulate a value that only renders inside a padded region (e.g. a
        # custom combo's text overflowing its nominal rect slightly).
        if bbox is not None and bbox.width > 100:
            return True, f"vision matched ({expected!r})"
        return False, "vision read empty"


def test_recovery_widens_bbox_on_final_attempt() -> None:
    verifier = _UnknownThenBboxSensitiveVerifier()
    engine = VerificationEngine(verifier)
    bbox = BBox(x=10, y=10, width=90, height=20)

    result = engine.verify_with_read_recovery(
        bbox, "Kataka / Cancer", field_id="uia-rashi", max_attempts=3,
    )

    assert result.status is VerificationStatus.MATCH
    # First call uses the original (narrow) bbox; the final attempt must
    # widen it enough to find the value.
    assert verifier.seen_bboxes[0] == bbox
    assert verifier.seen_bboxes[-1].width > bbox.width
    assert verifier.seen_bboxes[-1].height > bbox.height


def test_recovery_inserts_settle_delay_even_without_refocus() -> None:
    verifier = _UnknownThenBboxSensitiveVerifier()
    # Force every attempt to stay UNKNOWN so all 3 attempts run.
    verifier.verify = lambda bbox, expected, field_id=None: (False, "vision read empty")  # type: ignore
    engine = VerificationEngine(verifier)
    bbox = BBox(x=10, y=10, width=90, height=20)

    start = time.monotonic()
    result = engine.verify_with_read_recovery(
        bbox, "68 Kg", field_id="uia-weight", max_attempts=3, refocus=None,
    )
    elapsed = time.monotonic() - start

    assert result.status is VerificationStatus.UNKNOWN
    # No refocus callback was supplied (the SELECT-action case) - the old
    # code never slept in this branch at all; the fix always sleeps a bit
    # before each recovery read regardless.
    assert elapsed > 0.25


def test_recovery_stops_as_soon_as_a_match_is_found() -> None:
    calls = {"n": 0}

    class _MatchesOnSecondTry(FieldVerifier):
        name = "fixed"

        def verify(self, bbox, expected, field_id=None):
            calls["n"] += 1
            if calls["n"] < 2:
                return False, "vision read empty"
            return True, f"vision matched ({expected!r})"

    engine = VerificationEngine(_MatchesOnSecondTry())
    bbox = BBox(x=0, y=0, width=50, height=20)
    result = engine.verify_with_read_recovery(bbox, "Hindu", max_attempts=4)

    assert result.status is VerificationStatus.MATCH
    assert calls["n"] == 2  # stopped immediately once matched, no extra reads

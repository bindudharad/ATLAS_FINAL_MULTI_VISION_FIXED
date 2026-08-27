"""Regression tests for the source-record extraction pipeline fix.

Covers the two root causes found while investigating the real MPF runtime log
(31/34 left labels discovered, but "no record: no valid record detected" and
"uia map built" repeating every ~9-10s for 377s with zero records processed):

1. ``_collect_source_pairs`` used to return the FIRST non-empty-length pairs
   list it found, even when every value in it was empty (``pair_source_pairs``
   always fills in a label with an empty string as a last resort, so "pairs
   is truthy" never meant "pairs are usable"). Fixed with an explicit
   UIA/OCR merge that prefers non-empty values (PHASE 3/4/16).
2. ``_read_source_uia_only`` called the full/light field-map rebuild
   (``_refresh_field_map_once``) on every single poll while waiting for a
   record. Fixed with a cheap per-label ``WM_GETTEXT``-style read
   (``UiaBackend.refresh_source_values``) and a throttled fallback
   (PHASE 7/8/9).
"""

from __future__ import annotations

from pathlib import Path

from atlas.act.controls import ControlOutcome
from atlas.act.executor import ActionExecutor
from atlas.core.events import get_event_bus
from atlas.core.record_builder import RecordBuilder
from atlas.mapping.mapper import SemanticMapper
from atlas.mapping.uia_map import (
    PairingDiagnostics,
    UiaFieldMap,
    pair_source_pairs,
    parse_multiline_colon_block,
)
from atlas.observe.uia import UiaNode
from atlas.reason.planner import ActionPlanner
from atlas.reason.recovery import RecoveryPlanner
from atlas.vision.models import BBox, OcrText
from atlas.workflow.loop import AgentLoop

from tests.test_mpf_integration import PassVerifier, RecordingControls, StubKeyboard, StubMouse


def _label(name: str, x: int, y: int, w: int = 100) -> UiaNode:
    return UiaNode(name=name, control_type="Text", rect=BBox(x, y, w, 20))


def _value(name: str, x: int, y: int, w: int = 120) -> UiaNode:
    return UiaNode(name=name, control_type="Text", rect=BBox(x, y, w, 20))


# ---------------------------------------------------------------------------
# The REAL MPF left-panel layout (confirmed from a live-application
# recording, 2026-08-15): a SINGLE scrollable text block rendered as
# "Label:Value" lines with section headers, not separate sibling controls
# per row. This is now the PRIMARY source-parsing strategy.
# ---------------------------------------------------------------------------

REAL_MPF_SOURCE_BLOCK = (
    "Member Basic Information\n"
    "App No:32394824\n"
    "MBI Code:MBI1062138570\n"
    "Full Name:ABHISHEK ROY\n"
    "Genlder:Male\n"
    "DOB:13 October 2001\n"
    "Marital Status:Never Married\n"
    "State:Bihar\n"
    "District:Patna\n"
    "Taluk:Phulwari\n"
    "Pincode:800001\n"
    "House Type:Lease\n"
    "\n"
    "Religious and Astro Information\n"
    "RAI Code:RAI1093293046\n"
    "Mother Tongue:Hindi\n"
    "Religion:Hindu\n"
    "Cast:Brahman\n"
    "SubCast:Tiwari\n"
    "Nakshatra:Pushya / Pusam\n"
    "Rashi:Kataka / Cancer\n"
    "Pada:4th Pada\n"
)


def test_parse_multiline_colon_block_reads_real_mpf_layout() -> None:
    pairs = parse_multiline_colon_block(REAL_MPF_SOURCE_BLOCK)
    result = dict(pairs)
    assert result["App No"] == "32394824"
    assert result["MBI Code"] == "MBI1062138570"
    assert result["Full Name"] == "ABHISHEK ROY"
    # Real app has a "Genlder" typo - preserved as-is; alias handles mapping.
    assert result["Genlder"] == "Male"
    assert result["DOB"] == "13 October 2001"
    assert result["District"] == "Patna"
    assert result["Cast"] == "Brahman"
    assert result["SubCast"] == "Tiwari"


def test_parse_multiline_colon_block_skips_section_headers() -> None:
    pairs = parse_multiline_colon_block(REAL_MPF_SOURCE_BLOCK)
    labels = {label for label, _ in pairs}
    assert "Member Basic Information" not in labels
    assert "Religious and Astro Information" not in labels


def test_pair_source_pairs_uses_colon_block_from_a_single_uia_node() -> None:
    """This is the real mechanism: ONE UIA node whose value/name is the
    entire multi-line source panel text - not many sibling nodes."""
    block_node = UiaNode(name=REAL_MPF_SOURCE_BLOCK, control_type="Text", rect=BBox(490, 220, 320, 300))
    diag = PairingDiagnostics()
    pairs = pair_source_pairs([], [block_node], diagnostics=diag)
    result = dict(pairs)
    assert result["Full Name"] == "ABHISHEK ROY"
    assert result["District"] == "Patna"
    assert len(pairs) >= 15
    report = diag.to_dict()
    assert report["non_empty_values"] >= 15


def test_pair_source_pairs_colon_block_short_circuits_geometric_fallback() -> None:
    """Once the colon block yields a confident record, the (much slower and
    less reliable) sibling-geometry fallback must not run at all."""
    block_node = UiaNode(name=REAL_MPF_SOURCE_BLOCK, control_type="Text", rect=BBox(490, 220, 320, 300))
    # A decoy sibling that WOULD wrongly pair under the old geometric
    # strategy - proves it was never reached.
    decoy_label = _label("Decoy", 10, 900)
    decoy_value = _value("WRONG", 200, 900)
    pairs = pair_source_pairs([], [block_node, decoy_label, decoy_value])
    result = dict(pairs)
    assert "Decoy" not in result


def test_short_single_line_label_is_not_misdetected_as_colon_block() -> None:
    """A plain one-line label like 'District:' must not be treated as a
    (single-row) colon block - falls through to normal row pairing."""
    label = _label("District:", 10, 40, w=90)
    value = _value("Seoni", 150, 40)
    pairs = pair_source_pairs([], [label, value])
    assert dict(pairs) == {"District": "Seoni"}


# ---------------------------------------------------------------------------
# PairingDiagnostics: "log why a row was rejected"
# ---------------------------------------------------------------------------


def test_pairing_diagnostics_records_accepted_row() -> None:
    diag = PairingDiagnostics()
    labels = [_label("Full Name", 10, 40), _value("KRISHNA", 200, 40)]
    pairs = pair_source_pairs([], labels, diagnostics=diag)
    assert pairs == [("Full Name", "KRISHNA")]
    report = diag.to_dict()
    assert report["paired_rows"] == 1
    assert report["non_empty_values"] == 1
    assert report["rows"][0]["accepted"] is True


def test_pairing_diagnostics_records_rejection_reason_for_wide_gap() -> None:
    diag = PairingDiagnostics()
    # Gap between label and value is far larger than any real MPF row.
    labels = [_label("District", 10, 40), _value("Seoni", 900, 40)]
    pair_source_pairs([], labels, diagnostics=diag)
    report = diag.to_dict()
    rejected = [r for r in report["rows"] if not r["accepted"]]
    assert rejected
    assert any("gap" in r["reason"] for r in rejected)


def test_pairing_diagnostics_records_rejection_for_noise_label() -> None:
    diag = PairingDiagnostics()
    labels = [_label("Collapse", 10, 40), _value("Something", 200, 40)]
    pairs = pair_source_pairs([], labels, diagnostics=diag)
    # "Collapse" must never surface as a source label, however it was reached.
    assert "Collapse" not in dict(pairs)
    report = diag.to_dict()
    assert any(
        "noise" in r["reason"] for r in report["rows"]
        if not r["accepted"] and r.get("label") == "Collapse"
    )


# ---------------------------------------------------------------------------
# AgentLoop._merge_source_pairs - PHASE 3 (UIA/OCR priority merge)
# ---------------------------------------------------------------------------


def test_merge_prefers_uia_value_over_ocr() -> None:
    uia = [("Full Name", "KRISHNA")]
    ocr = [("Full Name", "KRISHNA (ocr-noisy)")]
    merged = AgentLoop._merge_source_pairs(uia, ocr)
    assert merged == [("Full Name", "KRISHNA")]


def test_merge_rescues_empty_uia_value_with_ocr() -> None:
    """Test B: UIA gives a partial value (empty), OCR supplies the rest ->
    the merged record must be complete, not thrown away."""
    uia = [("Full Name", ""), ("Gender", "Male")]
    ocr = [("Full Name", "RAJESH KUMAR")]
    merged = AgentLoop._merge_source_pairs(uia, ocr)
    assert dict(merged) == {"Full Name": "RAJESH KUMAR", "Gender": "Male"}


def test_merge_preserves_uia_when_ocr_is_incomplete() -> None:
    """Test C: OCR only found a couple of lines; UIA's complete read for the
    other labels must survive the merge untouched."""
    uia = [("Full Name", "KRISHNA"), ("Gender", "Male"), ("District", "Seoni")]
    ocr = [("Full Name", "KRISHNA")]  # OCR missed Gender/District entirely
    merged = AgentLoop._merge_source_pairs(uia, ocr)
    assert dict(merged) == {"Full Name": "KRISHNA", "Gender": "Male", "District": "Seoni"}


def test_merge_label_order_is_first_seen() -> None:
    uia = [("B", "2"), ("A", "1")]
    ocr = [("C", "3")]
    merged = AgentLoop._merge_source_pairs(uia, ocr)
    assert [label for label, _ in merged] == ["B", "A", "C"]


# ---------------------------------------------------------------------------
# The actual "labels found, no record" bug: geometric pairing produces only
# empty values -> RecordBuilder must not silently accept that as success,
# and a real (even single-source) non-empty value must not be discarded.
# ---------------------------------------------------------------------------


def test_record_builder_rejects_all_empty_values() -> None:
    """RecordBuilder correctly refuses a record where every value is empty -
    this is the exact gate that fired 'no valid record detected' when
    pairing quietly returned label-only rows."""
    builder = RecordBuilder()
    result = builder.build([("Full Name", ""), ("Gender", "")])
    assert result.record is None
    assert "no values" in (result.reason or "")


def test_record_builder_accepts_when_merge_rescues_one_value() -> None:
    """After the UIA/OCR merge rescues even a single real value, the record
    must be accepted (previously an all-empty UIA-only pairs list was
    returned as-is and the record was rejected outright)."""
    uia_pairs = [("Full Name", ""), ("Gender", "")]
    ocr_pairs = [("Full Name", "KRISHNA")]
    merged = AgentLoop._merge_source_pairs(uia_pairs, ocr_pairs)
    builder = RecordBuilder()
    result = builder.build(merged)
    assert result.record is not None
    assert result.record.pairs["Full Name"] == "KRISHNA"


# ---------------------------------------------------------------------------
# Performance fix: _read_source_uia_only must not call field_map_refresh on
# every poll (Test D).
# ---------------------------------------------------------------------------


def _minimal_loop(field_map: UiaFieldMap, refresh_calls: list[int]) -> AgentLoop:
    get_event_bus().clear()

    class _StubTarget:
        def is_alive(self) -> bool:
            return True

    def refresh() -> UiaFieldMap:
        refresh_calls.append(1)
        return field_map

    controls = RecordingControls()
    executor = ActionExecutor(
        mouse=StubMouse(), keyboard=StubKeyboard(), controls=controls,
        verifier=PassVerifier(), recovery=RecoveryPlanner(),
        verify_after_action=True, max_retries=3, retry_delay=0.0,
    )
    from atlas.understanding.source import SourceReader

    return AgentLoop(
        target=_StubTarget(), source_reader=SourceReader(), mapper=SemanticMapper(),
        planner=ActionPlanner(verify_after_action=True), executor=executor,
        max_records=1, next_record_timeout=2.0, next_record_poll=0.05,
        field_map=field_map, field_map_refresh=refresh,
    )


def test_read_source_uia_only_does_not_call_field_map_refresh_when_cheap_read_available(monkeypatch) -> None:
    """Test D: while polling for a record, ``field_map_refresh`` must not be
    called at all as long as the cheap per-label read path can refresh
    values (simulated here since real WM_GETTEXT is Windows-only)."""
    labels = [_label("Full Name", 10, 40, w=90), _value("KRISHNA", 150, 40)]
    field_map = UiaFieldMap(left_labels=labels, right_fields=[])
    refresh_calls: list[int] = []
    loop = _minimal_loop(field_map, refresh_calls)

    from atlas.observe.uia import UiaBackend

    def fake_refresh_source_values(self, nodes):
        # Simulate every node being cheaply readable via handle.
        return nodes, len(nodes)

    monkeypatch.setattr(UiaBackend, "refresh_source_values", fake_refresh_source_values, raising=True)

    for _ in range(5):
        loop._read_source_uia_only()

    assert refresh_calls == [], (
        "field_map_refresh was called during ordinary source polling even "
        "though the cheap per-label read path succeeded"
    )


def test_read_source_uia_only_falls_back_and_throttles_when_no_cheap_read(monkeypatch) -> None:
    """When no cached label can be cheap-read (e.g. off Windows, or a control
    genuinely has no handle), the expensive rebuild is used as a fallback but
    THROTTLED - not called on every single poll."""
    labels = [_label("Full Name", 10, 40, w=90), _value("KRISHNA", 150, 40)]
    field_map = UiaFieldMap(left_labels=labels, right_fields=[])
    refresh_calls: list[int] = []
    loop = _minimal_loop(field_map, refresh_calls)
    loop._source_refresh_interval = 100.0  # never elapses within this test

    from atlas.observe.uia import UiaBackend

    def fake_refresh_source_values(self, nodes):
        return nodes, 0  # nothing cheap-readable

    monkeypatch.setattr(UiaBackend, "refresh_source_values", fake_refresh_source_values, raising=True)

    for _ in range(5):
        loop._read_source_uia_only()

    # Only the first poll should have crossed the (never-elapsing-again)
    # throttle window - i.e. at most one rebuild across 5 rapid polls.
    assert len(refresh_calls) <= 1


# ---------------------------------------------------------------------------
# debug/mpf/source_pairs.json writer
# ---------------------------------------------------------------------------


def test_source_pairs_debug_file_written(tmp_path: Path) -> None:
    labels = [_label("Full Name", 10, 40, w=90), _value("KRISHNA", 150, 40)]
    field_map = UiaFieldMap(left_labels=labels, right_fields=[])

    get_event_bus().clear()

    class _StubTarget:
        def is_alive(self) -> bool:
            return True

    controls = RecordingControls()
    executor = ActionExecutor(
        mouse=StubMouse(), keyboard=StubKeyboard(), controls=controls,
        verifier=PassVerifier(), recovery=RecoveryPlanner(),
        verify_after_action=True, max_retries=3, retry_delay=0.0,
    )
    from atlas.understanding.source import SourceReader

    loop = AgentLoop(
        target=_StubTarget(), source_reader=SourceReader(), mapper=SemanticMapper(),
        planner=ActionPlanner(verify_after_action=True), executor=executor,
        max_records=1, next_record_timeout=2.0, next_record_poll=0.05,
        field_map=field_map, field_map_refresh=lambda: field_map,
        debug_dir=tmp_path,
    )
    from atlas.vision.models import SceneDescription
    scene = SceneDescription(window_title="MPF", elements=[], screen_offset=(0, 0))
    loop._collect_source_pairs(scene)

    out = tmp_path / "mpf" / "source_pairs.json"
    assert out.exists()
    import json
    payload = json.loads(out.read_text())
    assert payload["left_labels"] == 2
    assert "pairing_diagnostics" in payload


# ---------------------------------------------------------------------------
# Visual source observer: clean self-termination on a hard failure code
# ---------------------------------------------------------------------------


def test_loop_terminates_cleanly_on_observer_hard_failure(tmp_path: Path) -> None:
    """When the visual source observer reports a hard failure (e.g. the source
    panel can never be read because a real VLM failed), the await loop must
    STOP CLEANLY with the exact reason code - not spin for minutes reporting
    the same no-record condition over and over (the historical
    "BATCH COMPLETE: 0 record(s)" symptom)."""
    from types import SimpleNamespace

    from atlas.observe.source_observer import SourceObservation, VISION_FAILED
    from atlas.understanding.source import SourceReader
    from atlas.vision.models import SceneDescription
    from atlas.vision.scene import SceneAnalysis

    get_event_bus().clear()

    class _StubTarget:
        name = "fake-observer-target"

        def is_alive(self) -> bool:
            return True

        def observe(self) -> SceneAnalysis | None:
            # A real (visible) scene: the loop must still terminate because the
            # source observer - the only channel that can read it - hard-fails.
            return SceneAnalysis(scene=SceneDescription(
                window_title="MPF (Download and Upload Form)",
                layout_summary="empty scene",
                screen_offset=(0, 0),
            ))

    # Observer that ALWAYS fails the read with a hard failure code.
    failing_observer = SimpleNamespace(
        observe=lambda *a, **k: SourceObservation(error_reason=VISION_FAILED),
    )

    controls = RecordingControls()
    executor = ActionExecutor(
        mouse=StubMouse(), keyboard=StubKeyboard(), controls=controls,
        verifier=PassVerifier(), recovery=RecoveryPlanner(),
        verify_after_action=True, max_retries=3, retry_delay=0.0,
    )

    loop = AgentLoop(
        target=_StubTarget(), source_reader=SourceReader(), mapper=SemanticMapper(),
        planner=ActionPlanner(verify_after_action=True), executor=executor,
        max_records=0, next_record_timeout=0.3, next_record_poll=0.02,
        debug_dir=tmp_path, source_observer=failing_observer,
        source_min_valued_pairs=2,
    )

    summary = loop.run()
    assert summary.records == []
    assert summary.stopped_reason == f"no source record readable [{VISION_FAILED}]", (
        f"expected a clean terminate with {VISION_FAILED}, got {summary.stopped_reason!r}"
    )

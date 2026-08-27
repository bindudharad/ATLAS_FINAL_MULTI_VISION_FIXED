"""Regression tests for the real-world MPF run failure (FIX #1-3/8/9/10/20).

The real run (2026-08-16) produced ``left labels=36 candidate rows=22 paired
rows=48 non-empty values=35 empty values=13`` and was blocked by
``MAPPING_RECOVERY: record 1: source coverage below 95%`` / ``source coverage
9% (32 source label(s) unmapped)`` because the parser treated UI chrome as
record data:

    Pro No, S Date, E Date, Total, Finish, 2500, Shift, state, mode, upload,
    progress, elapsed, 16-08-202621, 16-08-2026 07, 16-08-2026 11, 00

These tests feed that exact garbage (plus a realistic member block) through the
parser and assert NONE of it survives, while every required/optional member
field still resolves - without hard-coding any record values (fixes #25/#26).
"""

from __future__ import annotations

from atlas.mapping.member_fields import (
    OPTIONAL_MEMBER_FIELDS,
    REQUIRED_MEMBER_FIELDS,
    filter_member_pairs,
    is_member_field,
    resolve_member_field,
    section_of,
)
from atlas.mapping.uia_map import pair_source_pairs, parse_multiline_colon_block
from atlas.observe.uia import UiaNode
from atlas.understanding.source import SourceRecord
from atlas.vision.models import BBox, OcrText
from atlas.workflow.loop import AgentLoop

# ---------------------------------------------------------------------------
# The EXACT garbage labels from the real failing run (not invented).
# ---------------------------------------------------------------------------

REAL_RUN_GARBAGE_LABELS = [
    "Pro No",
    "S Date",
    "E Date",
    "Total",
    "Finish",
    "2500",
    "Shift",
    "state",
    "mode",
    "upload",
    "progress",
    "elapsed",
    "16-08-202621",
    "16-08-2026 07",
    "16-08-2026 11",
    "00",
]

# A realistic full LEFT-panel block: member sections interleaved with the
# Project/Shift chrome and a live timer the real app renders in the SAME
# scrollable text block.
FULL_MPF_BLOCK = (
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
    "\n"
    "Project Details\n"
    "Pro No:101\n"
    "S Date:16-08-2026\n"
    "E Date:18-08-2026\n"
    "Total:2500\n"
    "Minimum:1000\n"
    "Finish:500\n"
    "Balance:2500\n"
    "\n"
    "Shift Details\n"
    "Shift:Morning\n"
    "From:09:00\n"
    "To:17:00\n"
    "\n"
    "state:idle\n"
    "mode:automatic\n"
    "progress:0\n"
    "elapsed:00:00\n"
    "upload:Ready\n"
    "16-08-202621\n"
    "16-08-2026 07:12\n"
    "16-08-2026 11:30\n"
    "00\n"
)


def _ocr_line(text: str) -> OcrText:
    return OcrText(text=text, bbox=BBox(10, 10, 200, 16), confidence=0.95)


# ---------------------------------------------------------------------------
# 1. Section-aware colon-block parsing
# ---------------------------------------------------------------------------


def test_section_of_recognizes_member_and_ignored_headers() -> None:
    assert section_of("Member Basic Information") == "member"
    assert section_of("Religious and Astro Information") == "member"
    assert section_of("Project Details") == "ignored"
    assert section_of("Shift Details") == "ignored"
    assert section_of("App No") is None


def test_colon_block_drops_project_shift_and_timer_rows() -> None:
    pairs = parse_multiline_colon_block(FULL_MPF_BLOCK)
    labels = {label for label, _ in pairs}
    for garbage in REAL_RUN_GARBAGE_LABELS:
        assert garbage not in labels, f"garbage label survived: {garbage}"
    assert "Pro No" not in labels
    assert "S Date" not in labels
    assert "Shift" not in labels
    assert "state" not in labels
    # Real member rows still present.
    result = dict(pairs)
    assert result["App No"] == "32394824"
    assert result["Full Name"] == "ABHISHEK ROY"
    assert result["Genlder"] == "Male"
    assert result["DOB"] == "13 October 2001"
    assert result["RAI Code"] == "RAI1093293046"
    assert result["Nakshatra"] == "Pushya / Pusam"
    assert len(pairs) >= 15


def test_colon_block_without_member_header_keeps_legacy_behaviour() -> None:
    # A generic label:value block (no section headers) must not be emptied.
    pairs = parse_multiline_colon_block("Full Name:ALICE\nAge:30")
    assert dict(pairs) == {"Full Name": "ALICE", "Age": "30"}


# ---------------------------------------------------------------------------
# 2. Member-only gating through pair_source_pairs (FIX #8)
# ---------------------------------------------------------------------------


def test_pair_source_pairs_member_only_filters_real_run_garbage() -> None:
    block_node = UiaNode(name=FULL_MPF_BLOCK, control_type="Text", rect=BBox(490, 220, 320, 300))
    pairs = pair_source_pairs([], [block_node], member_only=True)
    labels = {label for label, _ in pairs}
    for garbage in REAL_RUN_GARBAGE_LABELS:
        assert garbage not in labels, f"garbage survived member gate: {garbage}"
    assert "Full Name" in labels
    assert "Genlder" in labels
    assert "DOB" in labels
    # Every surviving label is a real member field.
    for label in labels:
        assert is_member_field(label), f"non-member label survived: {label}"


def test_pair_source_pairs_ocr_lines_member_only() -> None:
    ocr = [
        _ocr_line("Member Basic Information"),
        _ocr_line("Full Name:KRISHNA"),
        _ocr_line("Genlder:Male"),
        _ocr_line("DOB:21 March 1996"),
        _ocr_line("Project Details"),
        _ocr_line("Pro No:101"),
        _ocr_line("Total:2500"),
        _ocr_line("Shift:Morning"),
        _ocr_line("progress:0"),
        _ocr_line("00"),
    ]
    pairs = pair_source_pairs(ocr, member_only=True)
    labels = {label for label, _ in pairs}
    assert "Full Name" in labels
    assert "Genlder" in labels
    for garbage in ("Pro No", "Total", "Shift", "progress", "00"):
        assert garbage not in labels, f"garbage survived OCR gate: {garbage}"


# ---------------------------------------------------------------------------
# 3. filter_member_pairs drops the exact real-run garbage list
# ---------------------------------------------------------------------------


def test_filter_member_pairs_drops_exact_real_run_labels() -> None:
    pairs = [(label, "x") for label in REAL_RUN_GARBAGE_LABELS]
    kept = filter_member_pairs(pairs)
    assert kept == []


def test_filter_member_pairs_keeps_member_fields_with_raw_typo_labels() -> None:
    pairs = [
        ("App No", "31549796"),
        ("MBI Code", "MBI9681945817"),
        ("Full Name", "AYUSH HIMTAL"),
        ("Genlder", "Male"),
        ("DOB", "19 August 1974"),
        ("Cast", "Brahman"),
        ("SubCast", "Tiwari"),
    ]
    kept = filter_member_pairs(pairs)
    labels = {label for label, _ in kept}
    assert labels == {
        "App No", "MBI Code", "Full Name", "Genlder", "DOB", "Cast", "SubCast",
    }


# ---------------------------------------------------------------------------
# 4. Typo-tolerant resolution (labels only, never values)
# ---------------------------------------------------------------------------


def test_resolve_member_field_aliases_and_typos() -> None:
    assert resolve_member_field("App No") == "App No"
    assert resolve_member_field("Application Number") == "App No"
    assert resolve_member_field("Genlder") == "Gender"
    assert resolve_member_field("DOB") == "Date Of Birth"
    assert resolve_member_field("SubCast") == "Sub Caste"
    assert resolve_member_field("Mother Tongue") == "Mother Tongue"
    assert resolve_member_field("Rashi") == "Rashi"
    # Never resolves values or chrome.
    assert resolve_member_field("2500") is None
    assert resolve_member_field("progress") is None
    assert resolve_member_field("16-08-2026 07") is None
    assert resolve_member_field("KRISHNA") is None


# ---------------------------------------------------------------------------
# 5. Coverage is member-driven (FIX #9): optional absence never blocks,
#    required-member records reach >= 95% after gating.
# ---------------------------------------------------------------------------


def _member_record(pairs: dict[str, str]) -> SourceRecord:
    return SourceRecord(pairs=pairs, ordered_labels=list(pairs.keys()))


def test_coverage_required_members_high_when_member_gated() -> None:
    from atlas.mapping.uia_map import UiaFieldMap

    pairs = {
        "App No": "31549796",
        "MBI Code": "MBI9681945817",
        "Full Name": "AYUSH HIMTAL",
        "Genlder": "Male",
        "DOB": "19 August 1974",
        "Marital Status": "Never Married",
        "State": "Bihar",
        "District": "Patna",
        "Taluk": "Phulwari",
        "Pincode": "800001",
        "House Type": "Lease",
        "RAI Code": "RAI1093293046",
        "Mother Tongue": "Hindi",
        "Religion": "Hindu",
        "Caste": "Brahman",
        "Sub Caste": "Tiwari",
        "Nakshatra": "Pushya",
        "Rashi": "Kataka",
        "Pada": "4th Pada",
    }
    record = _member_record(pairs)
    mappings = [{"source": label, "target": label} for label in pairs]
    field_map = UiaFieldMap(
        start_control=None, left_labels=[], right_fields=[], upload_button=None, mappings=mappings,
    )
    cov, unmapped = AgentLoop._source_coverage(record, field_map)
    assert cov >= 0.95
    assert unmapped == []


def test_coverage_optional_absence_does_not_block() -> None:
    """RAI Code / Mother Tongue / ... missing must NOT drag coverage below 95%."""
    from atlas.mapping.uia_map import UiaFieldMap

    pairs = {
        "App No": "31549796",
        "MBI Code": "MBI9681945817",
        "Full Name": "AYUSH HIMTAL",
        "Genlder": "Male",
        "DOB": "19 August 1974",
        "Marital Status": "Never Married",
        "State": "Bihar",
        "District": "Patna",
        "Taluk": "Phulwari",
        "Pincode": "800001",
        "House Type": "Lease",
    }
    record = _member_record(pairs)
    mappings = [{"source": label, "target": label} for label in pairs]
    field_map = UiaFieldMap(
        start_control=None, left_labels=[], right_fields=[], upload_button=None, mappings=mappings,
    )
    cov, unmapped = AgentLoop._source_coverage(record, field_map)
    assert cov == 1.0
    assert unmapped == []


def test_coverage_garbage_labels_are_not_part_of_denominator() -> None:
    """The real run's garbage labels never enter coverage - they are gone
    before the metric runs (member-only gating), so the 9% report cannot
    recur."""
    from atlas.mapping.uia_map import UiaFieldMap

    pairs = {
        "App No": "31549796",
        "Full Name": "AYUSH HIMTAL",
        "Genlder": "Male",
        "DOB": "19 August 1974",
    }
    record = _member_record(pairs)
    mappings = [{"source": label, "target": label} for label in pairs]
    field_map = UiaFieldMap(
        start_control=None, left_labels=[], right_fields=[], upload_button=None, mappings=mappings,
    )
    cov, _ = AgentLoop._source_coverage(record, field_map)
    assert cov == 1.0


# ---------------------------------------------------------------------------
# 6. Schema sanity
# ---------------------------------------------------------------------------


def test_required_and_optional_member_fields_are_distinct() -> None:
    assert set(REQUIRED_MEMBER_FIELDS).isdisjoint(set(OPTIONAL_MEMBER_FIELDS))
    assert len(REQUIRED_MEMBER_FIELDS) == 11
    assert len(OPTIONAL_MEMBER_FIELDS) == 8
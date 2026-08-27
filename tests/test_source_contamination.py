"""Regression tests: application UI chrome must never become source data.

Real runs showed strings such as "Collapse", "Exit", "[F12] Debug OFF",
section headers ("Member Basic Information"), and status/instructional text
("Upload completed — left side refreshed with a new random record; form
reset") ending up as "unmapped source labels". These are never part of the
record and must be rejected at the choke point (``is_noise_label``) and at
every place a (label, value) pair is about to enter a ``SourceRecord``.
"""

from __future__ import annotations

from atlas.core.record_builder import RecordBuilder
from atlas.mapping.uia_map import is_noise_label
from atlas.observe.uia import UiaNode
from atlas.mapping.uia_map import pair_source_pairs
from atlas.vision.models import BBox


def _node(name: str, left: int, top: int, width: int, height: int = 20) -> UiaNode:
    return UiaNode(
        name=name,
        control_type="Text",
        automation_id="",
        rect=BBox(x=left, y=top, width=width, height=height),
    )


class TestIsNoiseLabel:
    def test_rejects_known_chrome_words(self) -> None:
        for word in ["Collapse", "Exit", "Log", "collapse", "  Exit  "]:
            assert is_noise_label(word), word

    def test_rejects_section_headers(self) -> None:
        assert is_noise_label("Member Basic Information")
        assert is_noise_label("Religious and Astro Information")
        assert is_noise_label("Family Information")

    def test_rejects_instructional_sentences(self) -> None:
        assert is_noise_label(
            "Upload completed — left side refreshed with a new random record; form reset"
        )
        assert is_noise_label("Click the first blank field")
        assert is_noise_label("[F12] Debug OFF")

    def test_accepts_real_field_labels(self) -> None:
        for label in [
            "Full Name", "App No", "MBI Code", "Date Of Birth", "Mother Tongue",
            "Annual Income", "Sub Caste", "1st Pada", "Father Name",
        ]:
            assert not is_noise_label(label), label


class TestRecordBuilderFiltersNoise:
    def test_noise_pairs_never_enter_record(self) -> None:
        builder = RecordBuilder()
        pairs = [
            ("Full Name", "RAJESH KUMAR"),
            ("Collapse", ""),
            ("Exit", ""),
            ("Member Basic Information", ""),
            ("Upload completed — left side refreshed with a new random record; form reset", ""),
            ("App No", "75977158"),
        ]
        result = builder.build(pairs)
        assert result.ok
        assert "Full Name" in result.record.pairs
        assert "App No" in result.record.pairs
        assert "Collapse" not in result.record.pairs
        assert "Exit" not in result.record.pairs
        assert "Member Basic Information" not in result.record.pairs
        assert not any("Upload completed" in lbl for lbl in result.record.pairs)


class TestPairSourcePairsFiltersNoise:
    def test_ocr_colon_lines_reject_noise_labels(self) -> None:
        class _Line:
            def __init__(self, text: str) -> None:
                self.text = text

        lines = [
            _Line("Full Name: RAJESH KUMAR"),
            _Line("Collapse: "),
            _Line("App No: 75977158"),
        ]
        pairs = pair_source_pairs(lines, [])
        labels = {label for label, _ in pairs}
        assert "Full Name" in labels
        assert "App No" in labels
        assert "Collapse" not in labels

    def test_uia_label_fallback_rejects_noise_labels(self) -> None:
        uia_labels = [
            _node("Full Name", 10, 10, 80),
            _node("RAJESH KUMAR", 200, 10, 100),
            _node("Collapse", 10, 400, 60),
            _node("Exit", 10, 430, 40),
        ]
        pairs = pair_source_pairs([], uia_labels)
        labels = {label for label, _ in pairs}
        assert "Collapse" not in labels
        assert "Exit" not in labels

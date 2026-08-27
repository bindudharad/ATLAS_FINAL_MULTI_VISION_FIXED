"""Tests for the loop's audit wiring: ledger rebuild, submit guard, 0-records fix."""

from __future__ import annotations

from types import MethodType, SimpleNamespace

from atlas.observe.uia import UiaNode
from atlas.vision.models import BBox
from atlas.workflow.audit import AuditStatus, UploadStatus
from atlas.workflow.field_engine import FieldStatus, build_field_queue
from tests.test_workflow import FakeTarget, RecordingControls, _build_loop, make_scene


def _field_map():
    right = [
        UiaNode(name="Full Name", control_type="Edit", handle=2001, rect=BBox(500, 40, 200, 24)),
        UiaNode(name="State", control_type="ComboBox", handle=2002, rect=BBox(500, 80, 200, 24),
                options=["Karnataka", "Kerala"]),
    ]
    return SimpleNamespace(
        right_fields=right,
        mappings=[
            {"source": "Full Name", "target": "Full Name", "confidence": 0.98},
            {"source": "State", "target": "State", "confidence": 0.98},
        ],
        left_rect=BBox(0, 0, 200, 600),
        right_rect=BBox(300, 0, 400, 600),
        upload_button=None,
        has_form=True,
    )


def _record() -> SimpleNamespace:
    return SimpleNamespace(
        pairs={"Full Name": "RAVI KUMAR", "State": "Karnataka"},
        ordered_labels=["Full Name", "State"],
        record_key="MPF-100",
        title="test",
    )


def _loop() -> object:
    return _build_loop(FakeTarget([]), RecordingControls(), max_records=1)


def test_field_state_for_status_maps_terminal_statuses() -> None:
    loop = _loop()
    assert loop._field_state_for_status(FieldStatus.VERIFIED).value == "VERIFIED"
    assert loop._field_state_for_status(FieldStatus.ALREADY_CORRECT).value == "VERIFIED"
    assert loop._field_state_for_status(FieldStatus.FAILED).value == "FAILED"
    assert loop._field_state_for_status(FieldStatus.FILLED).value == "ENTERED"
    assert loop._field_state_for_status(FieldStatus.NOT_APPLICABLE).value == "SKIPPED"
    assert loop._field_state_for_status(FieldStatus.UNMAPPED).value == "UNMAPPED"
    assert loop._field_state_for_status(FieldStatus.PENDING).value == "DISCOVERED"


def test_queue_to_ledger_binds_source_backed_fields() -> None:
    loop = _loop()
    queue = build_field_queue(_field_map(), _record())
    ledger = loop._queue_to_ledger(queue, _record())
    ids = {f.id for f in ledger.fields}
    assert len(ids) == 2
    assert ledger.source_map == {"full name": queue.items[0].stable_id, "state": queue.items[1].stable_id}
    assert len(ledger.source_backed()) == 2


def test_audit_record_passes_when_all_verified() -> None:
    loop = _loop()
    record = _record()
    queue = build_field_queue(_field_map(), record)
    for item in queue.items:
        queue.mark_status(item, FieldStatus.VERIFIED)
    ledger = loop._queue_to_ledger(queue, record)
    audit = loop._audit_record(record, queue, ledger)
    assert audit.audit_status is AuditStatus.PASS
    assert audit.upload_status is UploadStatus.ALLOWED
    assert audit.allows_submit


def test_audit_record_blocks_when_a_field_only_filled() -> None:
    loop = _loop()
    record = _record()
    queue = build_field_queue(_field_map(), record)
    queue.mark_status(queue.items[0], FieldStatus.VERIFIED)
    queue.mark_status(queue.items[1], FieldStatus.FILLED)  # written, UNKNOWN
    ledger = loop._queue_to_ledger(queue, record)
    audit = loop._audit_record(record, queue, ledger)
    assert audit.audit_status is AuditStatus.FAIL
    assert audit.upload_status is UploadStatus.BLOCKED
    assert audit.missing == ["State"]


def test_submit_guard_rejects_without_pass_audit() -> None:
    loop = _loop()
    assert loop.allows_submit() is False
    assert loop.submit() is False

    record = _record()
    queue = build_field_queue(_field_map(), record)
    for item in queue.items:
        queue.mark_status(item, FieldStatus.VERIFIED)
    ledger = loop._queue_to_ledger(queue, record)
    loop._ledger = ledger
    loop._last_audit = loop._audit_record(record, queue, ledger)
    assert loop.allows_submit() is True
    assert loop.submit() is True


def test_run_reports_crashed_record_as_failed() -> None:
    """A per-record exception must never be swallowed into a 0-record batch."""
    loop = _build_loop(
        FakeTarget([make_scene("1001", "Ravi Kumar", "Yes")]),
        RecordingControls(),
        max_records=1,
        timeout=1.0,
    )
    loop._field_driven = True

    def _boom(self, analysis, record, index):
        raise RuntimeError("boom")

    loop._run_record_field_driven = MethodType(_boom, loop)
    summary = loop.run()
    assert len(summary.records) == 1
    assert summary.failed == 1
    assert not summary.records[0].success
    assert "exception" in summary.records[0].message
    assert summary.records[0].audit is None
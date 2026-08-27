"""Tests for the per-record field ledger and final audit gate."""

from __future__ import annotations

from atlas.understanding.target_field import FieldLedgerState, TargetField
from atlas.workflow.audit import AuditStatus, UploadStatus, build_audit
from atlas.workflow.ledger import FieldLedger
from atlas.vision.models import BBox


def _field(fid: str, label: str, state: FieldLedgerState = FieldLedgerState.DISCOVERED) -> TargetField:
    return TargetField(id=fid, label=label, bounds=BBox(0, 0, 100, 20), state=state)


def test_ledger_tracks_lifecycle_and_resolution() -> None:
    ledger = FieldLedger()
    ledger.register(_field("f1", "Full Name"))
    ledger.register(_field("f2", "State"))
    assert ledger.source_backed() == []

    ledger.register_mapping("full name", "f1")
    ledger.register_mapping("state", "f2")
    assert ledger.field("f1").state is FieldLedgerState.MAPPED
    assert [f.id for f in ledger.source_backed()] == ["f1", "f2"]

    ledger.mark_verified("f1")
    ledger.mark_failed("f2")
    assert [f.id for f in ledger.verified()] == ["f1"]
    assert not ledger.all_resolved()
    assert ledger.source_map == {"full name": "f1", "state": "f2"}


def test_ledger_mapping_never_downgrades_terminal_state() -> None:
    ledger = FieldLedger()
    ledger.register(_field("f1", "Full Name"))
    ledger.mark_verified("f1")
    ledger.register_mapping("full name", "f1")
    assert ledger.field("f1").state is FieldLedgerState.VERIFIED


def test_ledger_failed_state_is_terminal() -> None:
    ledger = FieldLedger()
    ledger.register(_field("f1", "Full Name"))
    ledger.mark_failed("f1")
    ledger.mark_verified("f1")
    assert ledger.field("f1").state is FieldLedgerState.FAILED


def test_audit_passes_when_every_source_field_verified() -> None:
    fields = [
        _field("f1", "Full Name", FieldLedgerState.VERIFIED),
        _field("f2", "State", FieldLedgerState.VERIFIED),
        _field("f3", "Gender", FieldLedgerState.SKIPPED),
    ]
    audit = build_audit(
        source_labels=["Full Name", "State"],
        fields=fields,
        source_map={"full name": "f1", "state": "f2"},
    )
    assert audit.audit_status is AuditStatus.PASS
    assert audit.upload_status is UploadStatus.ALLOWED
    assert audit.allows_submit


def test_audit_blocks_on_unmapped_source_label() -> None:
    fields = [_field("f1", "Full Name", FieldLedgerState.VERIFIED)]
    audit = build_audit(
        source_labels=["Full Name", "Pincode"],
        fields=fields,
        source_map={"full name": "f1"},
    )
    assert audit.audit_status is AuditStatus.FAIL
    assert audit.upload_status is UploadStatus.BLOCKED
    assert audit.unmapped == ["Pincode"]
    assert not audit.allows_submit


def test_audit_blocks_when_source_backed_field_unverified() -> None:
    fields = [_field("f1", "Full Name", FieldLedgerState.ENTERED)]
    audit = build_audit(
        source_labels=["Full Name"],
        fields=fields,
        source_map={"full name": "f1"},
    )
    assert audit.audit_status is AuditStatus.FAIL
    assert audit.missing == ["Full Name"]


def test_audit_blocks_on_failed_and_mismatched_fields() -> None:
    fields = [
        _field("f1", "Full Name", FieldLedgerState.VERIFIED),
        _field("f2", "State", FieldLedgerState.MISMATCH),
        _field("f3", "Pincode", FieldLedgerState.FAILED),
    ]
    audit = build_audit(
        source_labels=["Full Name", "State", "Pincode"],
        fields=fields,
        source_map={"full name": "f1", "state": "f2", "pincode": "f3"},
    )
    assert audit.audit_status is AuditStatus.FAIL
    assert audit.mismatch == ["State"]
    assert audit.failed == ["Pincode"]


def test_audit_tracks_required_unverified() -> None:
    fields = [_field("f1", "Full Name", FieldLedgerState.ENTERED)]
    audit = build_audit(
        source_labels=["Full Name"],
        fields=fields,
        source_map={"full name": "f1"},
        required_labels={"Full Name"},
    )
    assert audit.required_unverified == ["Full Name"]
    assert any("required field(s) unverified" in r for r in audit.reasons)
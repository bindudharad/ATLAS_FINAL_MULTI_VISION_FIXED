"""Final record audit and upload gate.

Before any submit, the engine audits the record against the source data and the
field ledger. The audit is the single source of truth for the two upload
protections:

* the engine's ``submit()`` rejects unless the audit status is PASS, and
* the UI upload button stays disabled while ``upload_status`` is BLOCKED.

Safety invariant: NO VERIFIED DATA = NO UPLOAD.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from atlas.core.logging import audit_logger
from atlas.understanding.target_field import FieldLedgerState, TargetField


class AuditStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class UploadStatus(str, Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"


@dataclass
class RecordAudit:
    """Result of auditing one filled record before upload."""

    source_fields: list[str] = field(default_factory=list)
    target_fields: list[str] = field(default_factory=list)
    verified: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    mismatch: list[str] = field(default_factory=list)
    unmapped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    required_unverified: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    audit_status: AuditStatus = AuditStatus.PASS
    upload_status: UploadStatus = UploadStatus.ALLOWED

    @property
    def allows_submit(self) -> bool:
        return self.upload_status == UploadStatus.ALLOWED

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_fields": self.source_fields,
            "target_fields": self.target_fields,
            "verified": self.verified,
            "missing": self.missing,
            "mismatch": self.mismatch,
            "unmapped": self.unmapped,
            "failed": self.failed,
            "blocked": self.blocked,
            "required_unverified": self.required_unverified,
            "reasons": self.reasons,
            "audit_status": self.audit_status.value,
            "upload_status": self.upload_status.value,
        }


def build_audit(
    *,
    source_labels: list[str],
    fields: list[TargetField],
    source_map: dict[str, str] | None = None,
    required_labels: set[str] | None = None,
) -> RecordAudit:
    """Audit one record: every source label must map to a VERIFIED target field.

    Parameters
    ----------
    source_labels:
        The source record's labels carrying a value (in order).
    fields:
        The target fields for this record, with their ledger states.
    source_map:
        normalized source label -> target field id (the confident mappings).
    required_labels:
        Source labels that are mandatory (from the declared field map).

    The audit FAILs (and upload is BLOCKED) when any source label is unmapped,
    any source-backed target is unverified, or any target is MISMATCH / FAILED.
    """
    source_map = source_map or {}
    required_labels = required_labels or set()
    by_id = {f.id: f for f in fields}

    verified_ids = {f.id for f in fields if f.state == FieldLedgerState.VERIFIED}

    missing: list[str] = []
    unmapped: list[str] = []
    required_unverified: list[str] = []
    for label in source_labels:
        norm = label.strip().lower()
        target_id = source_map.get(norm)
        if target_id is None or target_id not in by_id:
            unmapped.append(label)
            if norm in {r.strip().lower() for r in required_labels}:
                required_unverified.append(label)
            continue
        if target_id not in verified_ids:
            missing.append(label)
            if norm in {r.strip().lower() for r in required_labels}:
                required_unverified.append(label)

    verified = [f.label or f.id for f in fields if f.id in verified_ids]
    mismatch = [f.label or f.id for f in fields if f.state == FieldLedgerState.MISMATCH]
    failed = [f.label or f.id for f in fields if f.state == FieldLedgerState.FAILED]
    blocked = [f.label or f.id for f in fields if f.state == FieldLedgerState.BLOCKED]
    target_fields = [f.label or f.id for f in fields]

    reasons: list[str] = []
    if unmapped:
        reasons.append(f"{len(unmapped)} source field(s) unmapped")
    if missing:
        reasons.append(f"{len(missing)} source-backed field(s) not verified")
    if mismatch:
        reasons.append(f"{len(mismatch)} field(s) MISMATCH")
    if failed:
        reasons.append(f"{len(failed)} field(s) FAILED")
    if required_unverified:
        reasons.append(f"{len(required_unverified)} required field(s) unverified")

    audit_status = AuditStatus.PASS if not reasons else AuditStatus.FAIL
    upload_status = UploadStatus.ALLOWED if audit_status == AuditStatus.PASS else UploadStatus.BLOCKED

    audit = RecordAudit(
        source_fields=source_labels,
        target_fields=target_fields,
        verified=verified,
        missing=missing,
        mismatch=mismatch,
        unmapped=unmapped,
        failed=failed,
        blocked=blocked,
        required_unverified=required_unverified,
        reasons=reasons,
        audit_status=audit_status,
        upload_status=upload_status,
    )
    audit_logger.info(
        "[AUDIT] status={} upload={} verified={} missing={} mismatch={} failed={} unmapped={} reasons={}",
        audit_status.value,
        upload_status.value,
        len(verified),
        len(missing),
        len(mismatch),
        len(failed),
        len(unmapped),
        reasons or "-",
    )
    return audit


__all__ = ["RecordAudit", "AuditStatus", "UploadStatus", "build_audit"]
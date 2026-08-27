"""Field ledger.

Per-record, per-field state tracking with an explicit lifecycle and a zero-skip
rule. Every fillable target field discovered for a record is registered; its
state moves DISCOVERED -> MAPPED -> INTERACTING -> ENTERED -> VERIFYING ->
VERIFIED (or MISMATCH / FAILED / UNMAPPED / SKIPPED / BLOCKED). The audit gate
reads this ledger: any source-backed field left unresolved blocks upload, so a
record is never submitted half-filled.
"""

from __future__ import annotations

from typing import Any

from atlas.core.logging import logger
from atlas.understanding.target_field import (
    FieldLedgerState,
    RESOLVED_STATES,
    TargetField,
    UNRESOLVED_STATES,
)


class FieldLedger:
    """Tracks the lifecycle state of every target field in one record."""

    def __init__(self) -> None:
        self._fields: dict[str, TargetField] = {}
        #: normalized source label -> target field id
        self._source_map: dict[str, str] = {}

    # -- registration --------------------------------------------------------

    def register(self, field: TargetField) -> None:
        """Register or refresh a target field."""
        self._fields[field.id] = field

    def register_mapping(self, source_label: str, field_id: str) -> None:
        """Record that a source label maps onto a target field.

        Only upgrades DISCOVERED -> MAPPED; never downgrades a field that has
        already reached a terminal / resolved state (VERIFIED, FAILED, ...).
        """
        if field_id in self._fields:
            self._source_map[source_label.strip().lower()] = field_id
            if self._fields[field_id].state is FieldLedgerState.DISCOVERED:
                self._fields[field_id].state = FieldLedgerState.MAPPED

    # -- query ---------------------------------------------------------------

    @property
    def fields(self) -> list[TargetField]:
        return list(self._fields.values())

    def field(self, field_id: str) -> TargetField | None:
        return self._fields.get(field_id)

    def source_backed(self) -> list[TargetField]:
        """Fields that carry a source value (must be verified before submit)."""
        return [self._fields[i] for i in self._source_map.values() if i in self._fields]

    def unmapped_source(self) -> list[str]:
        """Source labels with no target field registered."""
        known = set(self._source_map.keys())
        return []  # source labels are learned at audit time; see audit.py

    @property
    def source_map(self) -> dict[str, str]:
        """normalized source label -> target field id bindings."""
        return dict(self._source_map)

    def resolved(self) -> list[TargetField]:
        return [f for f in self._fields.values() if f.state in RESOLVED_STATES]

    def unresolved(self) -> list[TargetField]:
        return [f for f in self._fields.values() if f.state in UNRESOLVED_STATES]

    def verified(self) -> list[TargetField]:
        return [f for f in self._fields.values() if f.state == FieldLedgerState.VERIFIED]

    def all_resolved(self) -> bool:
        return not self.unresolved()

    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self._fields.values():
            counts[f.state.value] = counts.get(f.state.value, 0) + 1
        return counts

    # -- transitions ---------------------------------------------------------

    def mark(self, field_id: str, state: FieldLedgerState, note: str = "") -> None:
        """Transition a field's state (no-op for unknown fields)."""
        field = self._fields.get(field_id)
        if field is None:
            return
        if field.state == FieldLedgerState.FAILED and state not in {FieldLedgerState.FAILED}:
            logger.debug("ledger: {} already FAILED; ignoring {}", field_id, state.value)
            return
        field.state = state
        if note:
            logger.debug("ledger: {} -> {} ({})", field_id, state.value, note)

    def mark_discovered(self, field_id: str) -> None:
        self.mark(field_id, FieldLedgerState.DISCOVERED)

    def mark_mapped(self, field_id: str) -> None:
        self.mark(field_id, FieldLedgerState.MAPPED)

    def mark_interacting(self, field_id: str) -> None:
        self.mark(field_id, FieldLedgerState.INTERACTING)

    def mark_entered(self, field_id: str) -> None:
        self.mark(field_id, FieldLedgerState.ENTERED)

    def mark_verifying(self, field_id: str) -> None:
        self.mark(field_id, FieldLedgerState.VERIFYING)

    def mark_verified(self, field_id: str) -> None:
        self.mark(field_id, FieldLedgerState.VERIFIED)

    def mark_mismatch(self, field_id: str) -> None:
        self.mark(field_id, FieldLedgerState.MISMATCH)

    def mark_failed(self, field_id: str) -> None:
        self.mark(field_id, FieldLedgerState.FAILED)

    def mark_unmapped(self, field_id: str) -> None:
        self.mark(field_id, FieldLedgerState.UNMAPPED)

    def mark_skipped(self, field_id: str, note: str = "") -> None:
        self.mark(field_id, FieldLedgerState.SKIPPED, note)

    def mark_blocked(self, field_id: str, note: str = "") -> None:
        self.mark(field_id, FieldLedgerState.BLOCKED, note)

    def to_dict(self) -> dict[str, Any]:
        return {
            "counts": self.counts(),
            "fields": [f.to_dict() for f in self.fields],
            "source_map": dict(self._source_map),
        }


__all__ = ["FieldLedger"]
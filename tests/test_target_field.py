"""Tests for the normalized target-field taxonomy helpers."""

from __future__ import annotations

from atlas.understanding.target_field import (
    RESOLVED_STATES,
    UNRESOLVED_STATES,
    FieldLedgerState,
    FieldSource,
    InteractionStrategy,
    TargetControlType,
    VerificationStrategy,
    control_type_for_uia,
    interaction_strategy_for,
    verification_strategy_for,
)


def test_control_type_for_uia_maps_known_controls() -> None:
    assert control_type_for_uia("Edit") is TargetControlType.TEXT
    assert control_type_for_uia("ComboBox") is TargetControlType.COMBOBOX
    assert control_type_for_uia("CheckBox") is TargetControlType.CHECKBOX
    assert control_type_for_uia("RadioButton") is TargetControlType.RADIO
    assert control_type_for_uia("Button") is TargetControlType.BUTTON
    assert control_type_for_uia("Document") is TargetControlType.TEXTAREA
    assert control_type_for_uia("") is TargetControlType.UNKNOWN
    assert control_type_for_uia(None) is TargetControlType.UNKNOWN


def test_interaction_strategy_for_selects_by_control() -> None:
    assert interaction_strategy_for(TargetControlType.COMBOBOX, FieldSource.UIA) is InteractionStrategy.SELECT
    assert interaction_strategy_for(TargetControlType.CHECKBOX, FieldSource.UIA) is InteractionStrategy.TOGGLE
    assert interaction_strategy_for(TargetControlType.DATE_PICKER, FieldSource.UIA) is InteractionStrategy.DATE_PICKER
    assert interaction_strategy_for(TargetControlType.BUTTON, FieldSource.UIA) is InteractionStrategy.CLICK
    assert interaction_strategy_for(TargetControlType.TEXTAREA, FieldSource.UIA) is InteractionStrategy.PASTE
    assert interaction_strategy_for(TargetControlType.TEXT, FieldSource.UIA) is InteractionStrategy.VALUE_PATTERN
    assert interaction_strategy_for(TargetControlType.TEXT, FieldSource.DECLARED) is InteractionStrategy.TYPE


def test_verification_strategy_for_selects_by_source() -> None:
    assert verification_strategy_for(TargetControlType.TEXT, FieldSource.UIA) is VerificationStrategy.UIA_READ
    assert verification_strategy_for(TargetControlType.TEXT, FieldSource.DOM) is VerificationStrategy.DOM_VALUE
    assert verification_strategy_for(TargetControlType.COMBOBOX, FieldSource.UIA) is VerificationStrategy.OCR
    assert verification_strategy_for(TargetControlType.BUTTON, FieldSource.UIA) is VerificationStrategy.NONE
    assert verification_strategy_for(TargetControlType.TEXTAREA, FieldSource.UIA) is VerificationStrategy.CLIPBOARD


def test_ledger_state_sets_are_complete() -> None:
    assert FieldLedgerState.VERIFIED in RESOLVED_STATES
    assert FieldLedgerState.SKIPPED in RESOLVED_STATES
    for state in (FieldLedgerState.MISMATCH, FieldLedgerState.FAILED, FieldLedgerState.ENTERED,
                  FieldLedgerState.BLOCKED, FieldLedgerState.UNMAPPED):
        assert state in UNRESOLVED_STATES
    assert not (RESOLVED_STATES & UNRESOLVED_STATES)
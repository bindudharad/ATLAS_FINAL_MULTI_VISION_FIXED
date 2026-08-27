"""Normalized target-field model.

Every discovered fillable control in the target application - regardless of
which perception channel found it (UIA, DOM, Win32, OCR, CV, VLM, declared
plugin data) - collapses into one :class:`TargetField`. The executor, mapper,
ledger, audit and dashboard all speak this single vocabulary, so the engine is
no longer coupled to "UIA editable controls or nothing".
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from atlas.vision.models import BBox, ElementType


class TargetControlType(str, Enum):
    """Universal widget taxonomy for fillable form controls."""

    TEXT = "TEXT"
    PASSWORD = "PASSWORD"
    COMBOBOX = "COMBOBOX"
    DROPDOWN = "DROPDOWN"
    CHECKBOX = "CHECKBOX"
    RADIO = "RADIO"
    DATE = "DATE"
    DATE_PICKER = "DATE_PICKER"
    NUMBER = "NUMBER"
    TEXTAREA = "TEXTAREA"
    BUTTON = "BUTTON"
    CUSTOM = "CUSTOM"
    UNKNOWN = "UNKNOWN"


class FieldSource(str, Enum):
    """Which perception channel produced this field."""

    UIA = "UIA"
    DOM = "DOM"
    WIN32 = "WIN32"
    KEYBOARD = "KEYBOARD"  # discovered via the tab-order navigation graph
    OCR = "OCR"
    CV = "CV"
    VLM = "VLM"
    DECLARED = "DECLARED"  # from a plugin's declared field map (e.g. MPF JSON)


class InteractionStrategy(str, Enum):
    """How the executor should fill this control."""

    VALUE_PATTERN = "VALUE_PATTERN"  # direct UIA/DOM value set
    TYPE = "TYPE"  # focused keyboard typing
    PASTE = "PASTE"  # clipboard paste for long values
    SELECT = "SELECT"  # open a dropdown and pick an option
    TOGGLE = "TOGGLE"  # checkbox / radio
    DATE_PICKER = "DATE_PICKER"  # calendar/date picker interaction
    UPLOAD = "UPLOAD"  # file-upload control
    CLICK = "CLICK"  # plain click (button / navigation)
    KEYBOARD_NAV = "KEYBOARD_NAV"  # reach via tab-order navigation
    NONE = "NONE"  # nothing to do


class VerificationStrategy(str, Enum):
    """How the executor should read back this control's value."""

    UIA_READ = "UIA_READ"  # UIA ValuePattern read
    DOM_VALUE = "DOM_VALUE"  # web DOM value read
    OCR = "OCR"  # OCR the control's bounding box
    CLIPBOARD = "CLIPBOARD"  # focused clipboard read-back
    KEYBOARD_NAV = "KEYBOARD_NAV"  # navigate and read via keyboard
    NONE = "NONE"  # not value-verifiable


class FieldLedgerState(str, Enum):
    """Lifecycle state of one target field during a record."""

    UNDISCOVERED = "UNDISCOVERED"
    DISCOVERED = "DISCOVERED"
    MAPPED = "MAPPED"
    INTERACTING = "INTERACTING"
    ENTERED = "ENTERED"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    MISMATCH = "MISMATCH"
    FAILED = "FAILED"
    UNMAPPED = "UNMAPPED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"


#: States in which a field is fully resolved and safe to leave alone.
RESOLVED_STATES = {FieldLedgerState.VERIFIED, FieldLedgerState.SKIPPED}
#: States that indicate the field still needs work before submit.
UNRESOLVED_STATES = {
    FieldLedgerState.DISCOVERED,
    FieldLedgerState.MAPPED,
    FieldLedgerState.INTERACTING,
    FieldLedgerState.ENTERED,
    FieldLedgerState.VERIFYING,
    FieldLedgerState.MISMATCH,
    FieldLedgerState.FAILED,
    FieldLedgerState.UNMAPPED,
    FieldLedgerState.BLOCKED,
}


@dataclass
class TargetField:
    """One normalized, fillable field in the target application.

    ``bounds`` is always in ABSOLUTE screen coordinates so the executor can act
    on it directly regardless of which perception channel produced it.
    """

    id: str  # stable identity for this session
    label: str = ""
    normalized_label: str = ""
    section: str = ""
    control_type: TargetControlType = TargetControlType.UNKNOWN
    bounds: BBox | None = None
    value: str | None = None
    options: list[str] = field(default_factory=list)
    visible: bool = True
    enabled: bool = True
    editable: bool = True
    source: FieldSource = FieldSource.UIA
    confidence: float = 1.0
    interaction_strategy: InteractionStrategy = InteractionStrategy.CLICK
    verification_strategy: VerificationStrategy = VerificationStrategy.OCR
    discovered_at: float = field(default_factory=time.time)
    state: FieldLedgerState = FieldLedgerState.DISCOVERED
    required: bool | None = None
    #: Opaque back-reference used by the adapter to act on the field
    #: (e.g. the UIA node's runtime id, a DOM selector, an OCR region id).
    ref: Any = None

    @property
    def click_point(self) -> tuple[int, int] | None:
        if self.bounds is None:
            return None
        return self.bounds.center

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "normalized_label": self.normalized_label,
            "section": self.section,
            "control_type": self.control_type.value,
            "bounds": self.bounds.to_dict() if self.bounds else None,
            "value": self.value,
            "options": list(self.options),
            "visible": self.visible,
            "enabled": self.enabled,
            "editable": self.editable,
            "source": self.source.value,
            "confidence": self.confidence,
            "interaction_strategy": self.interaction_strategy.value,
            "verification_strategy": self.verification_strategy.value,
            "discovered_at": self.discovered_at,
            "state": self.state.value,
            "required": self.required,
        }


# -- mapping helpers ---------------------------------------------------------

_TEXT_LIKE_TYPES = {
    TargetControlType.TEXT,
    TargetControlType.PASSWORD,
    TargetControlType.NUMBER,
    TargetControlType.TEXTAREA,
}
_SELECT_LIKE_TYPES = {TargetControlType.COMBOBOX, TargetControlType.DROPDOWN}
_DATE_LIKE_TYPES = {TargetControlType.DATE, TargetControlType.DATE_PICKER}
_TOGGLE_TYPES = {TargetControlType.CHECKBOX, TargetControlType.RADIO}

_ELEMENT_TO_CONTROL = {
    ElementType.TEXTBOX: TargetControlType.TEXT,
    ElementType.SEARCH_BOX: TargetControlType.TEXT,
    ElementType.PASSWORD: TargetControlType.PASSWORD,
    ElementType.TEXTAREA: TargetControlType.TEXTAREA,
    ElementType.COMBOBOX: TargetControlType.COMBOBOX,
    ElementType.LISTBOX: TargetControlType.DROPDOWN,
    ElementType.CHECKBOX: TargetControlType.CHECKBOX,
    ElementType.RADIO: TargetControlType.RADIO,
    ElementType.DATE_PICKER: TargetControlType.DATE_PICKER,
    ElementType.CALENDAR: TargetControlType.DATE,
    ElementType.BUTTON: TargetControlType.BUTTON,
    ElementType.FILE_UPLOAD: TargetControlType.CUSTOM,
}

#: UIA control-type strings -> normalized taxonomy.
_UIA_TO_CONTROL = {
    "Edit": TargetControlType.TEXT,
    "Document": TargetControlType.TEXTAREA,
    "ComboBox": TargetControlType.COMBOBOX,
    "DropDown": TargetControlType.DROPDOWN,
    "CheckBox": TargetControlType.CHECKBOX,
    "RadioButton": TargetControlType.RADIO,
    "Calendar": TargetControlType.DATE_PICKER,
    "Spinner": TargetControlType.NUMBER,
    "Button": TargetControlType.BUTTON,
    "SplitButton": TargetControlType.BUTTON,
    "Hyperlink": TargetControlType.CUSTOM,
    "Custom": TargetControlType.CUSTOM,
    "DataItem": TargetControlType.CUSTOM,
}


def control_type_for_element(element_type: ElementType | str | None) -> TargetControlType:
    """Map a vision ``ElementType`` onto the normalized taxonomy."""
    try:
        key = ElementType(element_type)
    except (ValueError, TypeError):
        return TargetControlType.UNKNOWN
    return _ELEMENT_TO_CONTROL.get(key, TargetControlType.UNKNOWN)


def control_type_for_uia(control_type: str | None) -> TargetControlType:
    """Map a UIA ``control_type`` string onto the normalized taxonomy."""
    return _UIA_TO_CONTROL.get(control_type or "", TargetControlType.UNKNOWN)


def interaction_strategy_for(
    control_type: TargetControlType, source: FieldSource
) -> InteractionStrategy:
    """Pick the primary interaction strategy for a control type."""
    if control_type in _TOGGLE_TYPES:
        return InteractionStrategy.TOGGLE
    if control_type in _SELECT_LIKE_TYPES:
        return InteractionStrategy.SELECT
    if control_type in _DATE_LIKE_TYPES:
        return InteractionStrategy.DATE_PICKER
    if control_type == TargetControlType.BUTTON:
        return InteractionStrategy.CLICK
    if control_type == TargetControlType.TEXTAREA:
        return InteractionStrategy.PASTE
    if control_type in _TEXT_LIKE_TYPES:
        if source == FieldSource.DECLARED:
            return InteractionStrategy.TYPE
        if source in {FieldSource.UIA, FieldSource.DOM}:
            return InteractionStrategy.VALUE_PATTERN
        return InteractionStrategy.TYPE
    if source == FieldSource.KEYBOARD:
        return InteractionStrategy.KEYBOARD_NAV
    return InteractionStrategy.CLICK


def verification_strategy_for(
    control_type: TargetControlType, source: FieldSource
) -> VerificationStrategy:
    """Pick the primary read-back strategy for a control type."""
    if control_type == TargetControlType.BUTTON:
        return VerificationStrategy.NONE
    if control_type in _SELECT_LIKE_TYPES or control_type in _DATE_LIKE_TYPES:
        return VerificationStrategy.OCR
    if control_type == TargetControlType.TEXTAREA:
        return VerificationStrategy.CLIPBOARD
    if source == FieldSource.DOM:
        return VerificationStrategy.DOM_VALUE
    if source in {FieldSource.UIA, FieldSource.WIN32}:
        return VerificationStrategy.UIA_READ
    return VerificationStrategy.OCR


__all__ = [
    "TargetControlType",
    "FieldSource",
    "InteractionStrategy",
    "VerificationStrategy",
    "FieldLedgerState",
    "TargetField",
    "RESOLVED_STATES",
    "UNRESOLVED_STATES",
    "control_type_for_element",
    "control_type_for_uia",
    "interaction_strategy_for",
    "verification_strategy_for",
]
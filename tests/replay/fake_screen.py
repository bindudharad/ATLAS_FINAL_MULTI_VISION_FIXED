"""Fake screen simulation for deterministic MPF replay testing."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from enum import Enum

from atlas.vision.models import BBox, ElementType, ScreenElement, SceneDescription


class ScrollContext(str, Enum):
    SOURCE = "source"
    FORM = "form"
    DROPDOWN = "dropdown"


@dataclass
class FakeDropdown:
    """A simulated dropdown control."""
    field_id: str
    label: str
    options: list[str]
    selected_index: int = -1
    is_open: bool = False
    scroll_offset: int = 0
    visible_count: int = 10
    bbox: BBox | None = None

    def open(self) -> None:
        self.is_open = True
        self.scroll_offset = 0

    def close(self) -> None:
        self.is_open = False

    def scroll(self, amount: int) -> bool:
        if not self.is_open: return False
        old_offset = self.scroll_offset
        self.scroll_offset = max(0, min(self.scroll_offset + amount, len(self.options) - self.visible_count))
        return self.scroll_offset != old_offset

    def get_visible_options(self) -> list[str]:
        if not self.is_open: return []
        end = min(self.scroll_offset + self.visible_count, len(self.options))
        return self.options[self.scroll_offset:end]

    def select_option(self, value: str) -> bool:
        try:
            idx = self.options.index(value)
            self.selected_index = idx
            self.is_open = False
            return True
        except ValueError: return False

    def get_selected_value(self) -> str | None:
        if self.selected_index >= 0 and self.selected_index < len(self.options): return self.options[self.selected_index]
        return None

    def is_at_end(self) -> bool:
        return self.scroll_offset >= len(self.options) - self.visible_count


@dataclass
class FakeField:
    """A simulated form field."""
    field_id: str
    label: str
    field_type: ElementType
    bbox: BBox
    value: str = ""
    required: bool = False
    dropdown: FakeDropdown | None = None
    is_visible: bool = True


@dataclass
class FakeSourceRecord:
    """A simulated source record from the LEFT panel."""
    pairs: dict[str, str]
    scroll_offset: int = 0
    max_scroll: int = 100
    is_complete: bool = True

    def scroll(self, amount: int) -> bool:
        old = self.scroll_offset
        self.scroll_offset = max(0, min(self.scroll_offset + amount, self.max_scroll))
        return self.scroll_offset != old


class FakeMPFScreen:
    """Complete fake MPF application screen for replay testing."""

    def __init__(self, scenario: str = "default"):
        self.scenario = scenario
        self.actions_log = []
        self.source_record = None
        self.fields = {}
        self.dropdowns = {}
        self.form_scroll_offset = 0
        self.form_max_scroll = 500
        self.upload_details_bbox = None
        self.upload_details_visible = False
        self.current_focus = None
        self._setup_scenario(scenario)

    def _setup_scenario(self, scenario: str) -> None:
        if scenario == "default": self._setup_default()
        elif scenario == "form_scroll": self._setup_form_scroll()
        elif scenario == "dropdown_scroll": self._setup_dropdown_scroll()
        elif scenario == "dropdown_not_found": self._setup_dropdown_not_found()
        elif scenario == "dropdown_closes": self._setup_dropdown_closes()
        elif scenario == "low_confidence": self._setup_low_confidence()
        elif scenario == "dependent_dropdowns": self._setup_dependent_dropdowns()
        else: self._setup_default()


    def _setup_default(self) -> None:
        self.source_record = FakeSourceRecord(
            pairs={
                "Full Name": "John Doe",
                "Gender": "Male",
                "Date of Birth": "15 January 1990",
                "Marital Status": "Single",
                "State": "Karnataka",
                "District": "Bangalore Urban",
                "Taluk": "Bangalore North",
                "Pincode": "560001",
                "Mobile Number": "9876543210",
                "Email Address": "john.doe@example.com",
                "Address": "123 Main Street",
                "Aadhaar Number": "123456789012",
            },
            max_scroll=0
        )

        y = 50
        for i, (label, field_type, required, options) in enumerate([
            ("Full Name", ElementType.TEXTBOX, True, None),
            ("Gender", ElementType.COMBOBOX, True, ["Male", "Female", "Other"]),
            ("Date of Birth", ElementType.TEXTBOX, True, None),
            ("Marital Status", ElementType.COMBOBOX, True, ["Single", "Married", "Divorced", "Widowed"]),
            ("State", ElementType.COMBOBOX, True, ["Karnataka", "Maharashtra", "Tamil Nadu", "Delhi"]),
            ("District", ElementType.COMBOBOX, True, ["Bangalore Urban", "Bangalore Rural", "Mysore"]),
            ("Taluk", ElementType.COMBOBOX, True, ["Bangalore North", "Bangalore South", "Anekal"]),
            ("Pincode", ElementType.TEXTBOX, False, None),
            ("Mobile Number", ElementType.TEXTBOX, False, None),
            ("Email Address", ElementType.TEXTBOX, False, None),
            ("Address", ElementType.TEXTAREA, False, None),
            ("Aadhaar Number", ElementType.TEXTBOX, False, None),
        ]):
            field_id = "field_" + str(i)
            bbox = BBox(500, y, 300, 30)
            field = FakeField(field_id, label, field_type, bbox, required=required)
            self.fields[field_id] = field

            if field_type == ElementType.COMBOBOX and options:
                dropdown = FakeDropdown(field_id, label, options, bbox=bbox)
                self.dropdowns[field_id] = dropdown
                field.dropdown = dropdown

            y += 40

        self.upload_details_bbox = BBox(500, y + 20, 150, 40)
        self.upload_details_visible = True


    def _setup_form_scroll(self) -> None:
        self._setup_default()
        y = 500
        for i in range(15):
            field_id = "field_extra_" + str(i)
            bbox = BBox(500, y, 300, 30)
            field = FakeField(field_id, "Extra Field " + str(i), ElementType.TEXTBOX, bbox)
            self.fields[field_id] = field
            y += 40
        self.form_max_scroll = y - 600
        self.upload_details_bbox = BBox(500, y + 20, 150, 40)

    def _setup_dropdown_scroll(self) -> None:
        self._setup_default()
        state_field = self.fields.get("field_4")
        if state_field and state_field.dropdown:
            state_field.dropdown.options = ["State " + str(i) for i in range(30)]
            state_field.dropdown.options[25] = "Karnataka"
            state_field.dropdown.visible_count = 8

    def _setup_dropdown_not_found(self) -> None:
        self._setup_default()
        state_field = self.fields.get("field_4")
        if state_field and state_field.dropdown:
            state_field.dropdown.options = ["State A", "State B", "State C"]

    def _setup_dropdown_closes(self) -> None:
        self._setup_default()
        self._dropdown_should_close = True

    def _setup_low_confidence(self) -> None:
        self._setup_default()
        self.source_record.pairs["Full Name"] = "JOHN DOE"
        self._low_confidence = True

    def _setup_dependent_dropdowns(self) -> None:
        self.source_record = FakeSourceRecord(
            pairs={
                "State": "Karnataka",
                "District": "Bangalore Urban",
                "Taluk": "Bangalore North",
            },
            max_scroll=0
        )

        state_bbox = BBox(500, 50, 300, 30)
        state_field = FakeField("state", "State", ElementType.COMBOBOX, state_bbox, required=True)
        state_dropdown = FakeDropdown("state", "State", 
            ["Karnataka", "Maharashtra", "Tamil Nadu", "Delhi", "Kerala"], bbox=state_bbox)
        state_field.dropdown = state_dropdown
        self.fields["state"] = state_field
        self.dropdowns["state"] = state_dropdown

        district_bbox = BBox(500, 100, 300, 30)
        district_field = FakeField("district", "District", ElementType.COMBOBOX, district_bbox, required=True)
        district_dropdown = FakeDropdown("district", "District", [], bbox=district_bbox)
        district_field.dropdown = district_dropdown
        self.fields["district"] = district_field
        self.dropdowns["district"] = district_dropdown

        taluk_bbox = BBox(500, 150, 300, 30)
        taluk_field = FakeField("taluk", "Taluk", ElementType.COMBOBOX, taluk_bbox, required=True)
        taluk_dropdown = FakeDropdown("taluk", "Taluk", [], bbox=taluk_bbox)
        taluk_field.dropdown = taluk_dropdown
        self.fields["taluk"] = taluk_field
        self.dropdowns["taluk"] = taluk_dropdown

        self._dependent_state = {
            "Karnataka": {"Bangalore Urban": ["Bangalore North", "Bangalore South", "Anekal"],
                         "Mysore": ["Mysore", "Nanjangud", "Hunsur"]},
            "Maharashtra": {"Mumbai": ["Mumbai City", "Mumbai Suburban"]},
        }
        self.upload_details_bbox = BBox(500, 200, 150, 40)
        self.upload_details_visible = True


    def log_action(self, action_type: str, details: dict[str, Any]) -> None:
        self.actions_log.append({
            "timestamp": time.time(),
            "type": action_type,
            "details": details
        })

    def get_scene(self) -> SceneDescription:
        elements = []

        if self.source_record:
            y = 50
            for label, value in self.source_record.pairs.items():
                elements.append(ScreenElement(
                    element_id="src_" + label.lower().replace(' ', '_'),
                    type=ElementType.TEXTBOX,
                    label=label,
                    name=label,
                    bbox=BBox(50, y, 400, 30),
                    confidence=0.95 if not getattr(self, '_low_confidence', False) else 0.3
                ))
                y += 35

        for field in self.fields.values():
            if field.is_visible or (field.bbox.top > self.form_scroll_offset and 
                                     field.bbox.top < self.form_scroll_offset + 600):
                elements.append(ScreenElement(
                    element_id=field.field_id,
                    type=field.field_type,
                    label=field.label,
                    name=field.label,
                    bbox=BBox(field.bbox.left, field.bbox.top - self.form_scroll_offset, 
                              field.bbox.width, field.bbox.height),
                    confidence=0.9
                ))

        for dropdown in self.dropdowns.values():
            if dropdown.is_open:
                y = dropdown.bbox.top + dropdown.bbox.height + 5 - self.form_scroll_offset
                for i, opt in enumerate(dropdown.get_visible_options()):
                    elements.append(ScreenElement(
                        element_id="{}_opt_{}".format(dropdown.field_id, i),
                        type=ElementType.TEXTBOX,
                        label=opt,
                        name=opt,
                        bbox=BBox(dropdown.bbox.left, y + i * 25, dropdown.bbox.width, 25),
                        confidence=0.95
                    ))

        if self.upload_details_visible:
            elements.append(ScreenElement(
                element_id="upload_details",
                type=ElementType.BUTTON,
                label="Upload Details",
                name="Upload Details",
                bbox=BBox(self.upload_details_bbox.left, 
                          self.upload_details_bbox.top - self.form_scroll_offset,
                          self.upload_details_bbox.width, self.upload_details_bbox.height),
                confidence=1.0
            ))

        return SceneDescription(elements=elements)


    def click(self, x: int, y: int) -> dict[str, Any]:
        self.log_action("click", {"x": x, "y": y})

        for dropdown in self.dropdowns.values():
            if dropdown.is_open:
                for i, opt in enumerate(dropdown.get_visible_options()):
                    opt_y = dropdown.bbox.top + dropdown.bbox.height + 5 + i * 25 - self.form_scroll_offset
                    if (dropdown.bbox.left <= x <= dropdown.bbox.left + dropdown.bbox.width and
                        opt_y <= y <= opt_y + 25):
                        dropdown.select_option(opt)
                        return {"success": True, "action": "dropdown_select", "value": opt}

        for field in self.fields.values():
            screen_y = field.bbox.top - self.form_scroll_offset
            if (field.bbox.left <= x <= field.bbox.left + field.bbox.width and
                screen_y <= y <= screen_y + field.bbox.height):
                self.current_focus = field.field_id
                if field.dropdown and not field.dropdown.is_open:
                    field.dropdown.open()
                    return {"success": True, "action": "dropdown_open", "field": field.field_id}
                return {"success": True, "action": "field_focus", "field": field.field_id}

        if self.upload_details_visible:
            upload_y = self.upload_details_bbox.top - self.form_scroll_offset
            if (self.upload_details_bbox.left <= x <= self.upload_details_bbox.left + self.upload_details_bbox.width and
                upload_y <= y <= upload_y + self.upload_details_bbox.height):
                self.log_action("upload_details_click", {"x": x, "y": y})
                return {"success": True, "action": "upload_click"}

        return {"success": False, "action": "no_target"}

    def type_text(self, text: str) -> dict[str, Any]:
        self.log_action("type", {"text": text, "field": self.current_focus})

        if self.current_focus and self.current_focus in self.fields:
            field = self.fields[self.current_focus]
            field.value = text
            return {"success": True, "field": field.field_id, "value": text}
        return {"success": False, "reason": "no_focus"}

    def scroll(self, context: ScrollContext, amount: int) -> bool:
        self.log_action("scroll", {"context": context.value, "amount": amount})

        if context == ScrollContext.SOURCE:
            if self.source_record:
                return self.source_record.scroll(amount)
        elif context == ScrollContext.FORM:
            old = self.form_scroll_offset
            self.form_scroll_offset = max(0, min(self.form_scroll_offset + amount, self.form_max_scroll))
            if self.upload_details_bbox:
                upload_y = self.upload_details_bbox.top - self.form_scroll_offset
                if 0 <= upload_y <= 600:
                    self.upload_details_visible = True
            return self.form_scroll_offset != old
        elif context == ScrollContext.DROPDOWN:
            for dropdown in self.dropdowns.values():
                if dropdown.is_open:
                    result = dropdown.scroll(amount)
                    if getattr(self, '_dropdown_should_close', False) and dropdown.scroll_offset > 0:
                        dropdown.close()
                        self._dropdown_should_close = False
                    return result
        return False

    def verify_field(self, field_id: str, expected: str) -> tuple[bool, str]:
        if field_id in self.fields:
            field = self.fields[field_id]
            actual = field.value
            if field.dropdown:
                actual = field.dropdown.get_selected_value() or ""
            matched = actual.strip().lower() == expected.strip().lower()
            return matched, actual
        return False, "field_not_found"

    def verify_upload_not_clicked(self) -> bool:
        for action in self.actions_log:
            if action["type"] == "upload_details_click":
                return False
        return True

    def get_action_summary(self) -> dict[str, int]:
        summary = {}
        for action in self.actions_log:
            summary[action["type"]] = summary.get(action["type"], 0) + 1
        return summary


class FakeUIABackend:
    """Fake UIA backend for testing without real UIA."""

    def __init__(self, fake_screen: FakeMPFScreen):
        self.fake_screen = fake_screen

    def find_element(self, **criteria) -> dict | None:
        return {"found": True}


def create_fake_mpf(scenario: str = "default") -> FakeMPFScreen:
    """Factory function to create a fake MPF screen for testing."""
    return FakeMPFScreen(scenario)


SCENARIOS = {
    "all_visible": "default",
    "form_scroll": "form_scroll",
    "dropdown_immediate": "default",
    "dropdown_3_scrolls": "dropdown_scroll",
    "dropdown_end": "dropdown_scroll",
    "dropdown_not_found": "dropdown_not_found",
    "dropdown_closes": "dropdown_closes",
    "low_confidence": "low_confidence",
    "dependent_dropdowns": "dependent_dropdowns",
    "upload_boundary": "default",
}
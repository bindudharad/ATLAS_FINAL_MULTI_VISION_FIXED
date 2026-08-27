"""Field control actions.

Defines the ``ControlInterface`` implemented by both the desktop control engine
(mouse/keyboard/clipboard) and the web DOM control engine (Playwright). The
action executor depends only on the interface, so swapping a target never
changes the executor.
"""

from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from atlas.act.keyboard import HumanKeyboard
from atlas.act.mouse import HumanMouse
from atlas.config import TypingConfig
from atlas.core.logging import logger
from atlas.vision.models import BBox

ValueSetter = Callable[[BBox, str], bool]

#: Direct UIA dropdown selection: (bbox, value, declared_options, field_id) -> bool.
#: Returns True when the option was selected without keyboard interaction.
OptionSetter = Callable[[BBox, str, list[str] | None, str | None], bool]
OptionLocator = Callable[[BBox, str, str | None], BBox | None]
#: Closes/inspects a selection panel. ``False`` means UIA still sees it open;
#: ``None`` means that control does not expose an observable panel state.
SelectionCloser = Callable[[BBox, str, str | None], bool | None]


@dataclass
class ControlOutcome:
    """Result of a control operation."""

    ok: bool
    evidence: str = ""


class ControlInterface(ABC):
    """Operations the executor can perform on a single field."""

    @abstractmethod
    def focus(self, bbox: BBox | None, field_id: str | None = None) -> ControlOutcome: ...

    @abstractmethod
    def click_field(self, bbox: BBox | None, field_id: str | None = None) -> ControlOutcome: ...

    @abstractmethod
    def type_value(self, bbox: BBox | None, value: str, field_id: str | None = None) -> ControlOutcome: ...

    @abstractmethod
    def clear(self, bbox: BBox | None, field_id: str | None = None) -> ControlOutcome: ...

    @abstractmethod
    def select_option(
        self, bbox: BBox | None, value: str, options: list[str] | None = None, field_id: str | None = None
    ) -> ControlOutcome: ...

    @abstractmethod
    def toggle(self, bbox: BBox | None, value: str, field_id: str | None = None) -> ControlOutcome: ...

    @abstractmethod
    def choose_date(
        self, bbox: BBox | None, value: str, date_format: str | None = None, field_id: str | None = None
    ) -> ControlOutcome: ...

    @abstractmethod
    def press_tab(self) -> ControlOutcome: ...

    @abstractmethod
    def press_enter(self) -> ControlOutcome: ...

    @abstractmethod
    def press_escape(self) -> ControlOutcome: ...

    @abstractmethod
    def scroll(self, direction: str, amount: int = 3) -> ControlOutcome: ...

    def scroll_by_keys(self, direction: str, amount: int = 3) -> ControlOutcome:
        """Scroll via keyboard (PageUp/PageDown/Home/End).

        Default implementation reports it is unsupported so the executor can
        fall through to the scroll-bar strategy. Engines that can scroll a
        focused container by keys override this.
        """
        return ControlOutcome(ok=False, evidence="keyboard scroll not supported")

    def scroll_bar(self, direction: str, amount: int = 3) -> ControlOutcome:
        """Scroll by dragging / clicking the window's scroll bar.

        Default implementation reports it is unsupported so the executor can
        give up cleanly. Engines that can reach a scroll bar override this.
        """
        return ControlOutcome(ok=False, evidence="scroll-bar scroll not supported")

    @abstractmethod
    @abstractmethod
    def scroll_dropdown(self, direction: str, amount: int = 3) -> ControlOutcome: ...
    def paste(self, value: str, field_id: str | None = None) -> ControlOutcome: ...

    @abstractmethod
    def upload_file(self, bbox: BBox | None, path: str, field_id: str | None = None) -> ControlOutcome: ...


class ControlEngine(ControlInterface):
    """Desktop control engine: mouse, keyboard and clipboard."""

    def __init__(
        self,
        mouse: HumanMouse,
        keyboard: HumanKeyboard,
        typing_config: TypingConfig | None = None,
        clipboard_use_long: bool = True,
        clipboard_min_length: int = 25,
        value_setter: ValueSetter | None = None,
        option_setter: OptionSetter | None = None,
        option_locator: OptionLocator | None = None,
        selection_closer: SelectionCloser | None = None,
        use_value_pattern: bool | None = None,
    ) -> None:
        self._mouse = mouse
        self._keyboard = keyboard
        self._typing = typing_config or TypingConfig()
        # CRITICAL FIX: clipboard paste is NEVER used for MPF - the app rejects
        # pasted/auto-filled text with "Auto-fill or pasted text is not allowed.
        # Please type manually." So clipboard is always disabled regardless of
        # config, and every text field is typed character-by-character.
        self._clipboard_long = False
        self._clipboard_min = clipboard_min_length
        self._value_setter = value_setter
        self._option_setter = option_setter
        self._option_locator = option_locator
        self._selection_closer = selection_closer
        self._selection_panel_open = False
        #: UIA ValuePattern bulk-injection is OFF by default (keyboard typing is
        #: the primary interaction). An explicit ``True`` re-enables it for
        #: targets that accept programmatic injection.
        self._use_value_pattern = (
            bool(self._typing.use_value_pattern)
            if use_value_pattern is None
            else use_value_pattern
        )

    def focus(self, bbox: BBox | None, field_id: str | None = None) -> ControlOutcome:
        if bbox is None:
            return ControlOutcome(ok=True, evidence="focus skipped (no bbox)")
        x, y = bbox.center
        self._mouse.click(x, y)
        time.sleep(0.15)
        return ControlOutcome(ok=True, evidence=f"focused ({x},{y})")

    def click_field(self, bbox: BBox | None, field_id: str | None = None) -> ControlOutcome:
        if bbox is None:
            return ControlOutcome(ok=False, evidence="no bbox for click")
        x, y = bbox.center
        self._mouse.click(x, y)
        time.sleep(0.1)
        return ControlOutcome(ok=True, evidence=f"clicked ({x},{y})")

    def type_value(self, bbox: BBox | None, value: str, field_id: str | None = None) -> ControlOutcome:
        # NEVER use UIA ValuePattern bulk injection - MPF rejects it with
        # "Auto-fill or pasted text is not allowed. Please type manually."
        # NEVER use clipboard paste - MPF rejects pasted text the same way.
        # ALWAYS use genuine character-by-character keyboard typing.
        if self._try_set_value(bbox, value, field_id):
            return ControlOutcome(ok=True, evidence=f"set via UIA ValuePattern {len(value)} chars")
        self._ensure_focus(bbox)
        self._keyboard.clear_field()
        time.sleep(0.1)
        # REAL KEYBOARD INPUT: type one character at a time, no paste ever.
        self._keyboard.type_text(value)
        return ControlOutcome(ok=True, evidence=f"typed {len(value)} chars character-by-character")

    def clear(self, bbox: BBox | None, field_id: str | None = None) -> ControlOutcome:
        if self._try_set_value(bbox, "", field_id):
            return ControlOutcome(ok=True, evidence="cleared via UIA ValuePattern")
        self._ensure_focus(bbox)
        self._keyboard.clear_field()
        return ControlOutcome(ok=True, evidence="cleared")

    def select_option(
        self, bbox: BBox | None, value: str, options: list[str] | None = None, field_id: str | None = None
    ) -> ControlOutcome:
        value_str = str(value or "").strip()
        logger.info("[SELECT] field={} option={!r} opening", field_id or "<unknown>", value_str)
        if not value_str:
            # Empty selection: typing nothing + Enter on an open native
            # dropdown just hangs (or mis-selects). Skip cleanly instead.
            return ControlOutcome(ok=True, evidence=f"select skipped (empty value) for {field_id!r}")
        # Restore the working interaction semantics: the field action opened
        # the list already, so click the actual visible option (as a user
        # does). UIA locates it precisely; the mouse click lets MPF commit and
        # dismiss its rendered popup. SelectionItem.Select() remains a
        # fallback for controls that do not expose option geometry.
        if self._option_locator is not None and bbox is not None:
            try:
                # Use the new scrolling locator to find the option by scrolling the dropdown
                option_bbox = self._locate_dropdown_option_with_scroll(bbox, value_str, field_id)
            except Exception as exc:
                logger.debug("selection option lookup failed for {}: {}", field_id, exc)
                option_bbox = None
            if option_bbox is not None:
                logger.info("[SELECT] field={} panel_open=YES option_found=YES", field_id or "<unknown>")
                self._mouse.click(*option_bbox.center)
                return self._selection_complete(field_id, value_str, "visible-option-click", bbox)
        # Direct UIA selection is a compatibility fallback only.
        if self._option_setter is not None and bbox is not None:
            try:
                if self._option_setter(bbox, value_str, options, field_id):
                    return self._selection_complete(field_id, value_str, "UIA direct", bbox)
            except Exception as exc:
                logger.debug("uia direct select failed: {}", exc)
        if options:
            idx = self._find_option_index(options, value_str)
            if idx is not None:
                # Ensure the combo has keyboard focus before arrow-navigating,
                # otherwise Down/Enter act on whatever control owns focus.
                logger.debug(
                    "select_option {} value={!r} options={} idx={} (arrow branch, bbox={})",
                    field_id, value_str, len(options), idx, bbox,
                )
                self._ensure_focus(bbox)
                # Let the dropdown animate open before arrow-navigating.
                time.sleep(self._typing.dropdown_wait)
                self._keyboard.press("down", idx + 1)
                self._keyboard.enter()
                return self._selection_complete(field_id, value_str, f"arrow-selected #{idx}", bbox)
        logger.debug(
            "select_option {} value={!r} options={} (typed branch, bbox={})",
            field_id, value_str, len(options or ()), bbox,
        )
        self._ensure_focus(bbox)
        self._keyboard.type_text(value_str)
        time.sleep(self._typing.dropdown_wait)
        self._keyboard.enter()
        return self._selection_complete(field_id, value_str, f"typed option {value_str!r}", bbox)

    def selection_panel_open(self) -> bool | None:
        """Return a known-open panel state for selection recovery, if known."""
        return self._selection_panel_open if self._selection_closer is not None else None


    def _locate_dropdown_option_with_scroll(self, bbox, value, field_id=None, max_scrolls=20):
        """Locate a dropdown option by scrolling the dropdown list until found.

        This implements the DROPDOWN_SCROLL context - scrolling only the
        dropdown option list, not the entire form. Returns the option bbox
        when found, or None if not found after max_scrolls.
        """
        # First try to find the option without scrolling
        if self._option_locator is not None:
            try:
                option_bbox = self._option_locator(bbox, value, field_id)
                if option_bbox is not None:
                    return option_bbox
            except Exception as exc:
                logger.debug("initial option lookup failed for {}: {}", field_id, exc)
        
        # Option not visible - scroll the dropdown to find it
        logger.info("[DROPDOWN] field={} option={!r} not visible, starting dropdown scroll", field_id or "<unknown>", value)
        
        # Click the dropdown to ensure it's open and focused
        if bbox is not None:
            self._mouse.click(*bbox.center)
            time.sleep(self._typing.dropdown_wait)
        
        for scroll_attempt in range(max_scrolls):
            # Try to find the option after each scroll
            if self._option_locator is not None:
                try:
                    option_bbox = self._option_locator(bbox, value, field_id)
                    if option_bbox is not None:
                        logger.info("[DROPDOWN] field={} option={!r} found after {} scrolls", field_id or "<unknown>", value, scroll_attempt)
                        return option_bbox
                except Exception as exc:
                    logger.debug("option lookup failed during scroll: {}", exc)
            
            # Scroll down in the dropdown
            self.scroll_dropdown("down", 3)
            time.sleep(0.15)  # Wait for UI to update
        
        logger.warning("[DROPDOWN] field={} option={!r} not found after {} scrolls", field_id or "<unknown>", value, max_scrolls)
        return None

    def _selection_complete(
        self, field_id: str | None, value: str, method: str, bbox: BBox | None,
    ) -> ControlOutcome:
        """Perform the control-specific close step before read-back verifies."""
        closed: bool | None = None
        if self._selection_closer is not None and bbox is not None:
            try:
                closed = self._selection_closer(bbox, value, field_id)
            except Exception as exc:
                logger.debug("selection close check failed for {}: {}", field_id, exc)
        self._selection_panel_open = closed is False
        logger.info(
            "[SELECT] field={} option={!r} option_clicked=YES panel_closed={}",
            field_id or "<unknown>", value,
            "NO" if closed is False else "YES" if closed is True else "UNKNOWN",
        )
        if closed is False:
            return ControlOutcome(ok=False, evidence=f"{method}; selection panel still open")
        return ControlOutcome(ok=True, evidence=f"{method}; panel_closed={closed is not False}")

    def toggle(self, bbox: BBox | None, value: str, field_id: str | None = None) -> ControlOutcome:
        if bbox is None:
            return ControlOutcome(ok=True, evidence="toggle skipped (no bbox)")
        x, y = bbox.center
        self._mouse.click(x, y)
        return ControlOutcome(ok=True, evidence=f"toggled {value!r} at ({x},{y})")

    def choose_date(
        self, bbox: BBox | None, value: str, date_format: str | None = None, field_id: str | None = None
    ) -> ControlOutcome:
        date_str = self._normalize_date(str(value or ""), date_format)
        if self._try_set_value(bbox, date_str, field_id):
            return ControlOutcome(ok=True, evidence=f"set date via UIA ValuePattern {date_str!r}")
        self._ensure_focus(bbox)
        self._keyboard.clear_field()
        time.sleep(0.1)
        self._keyboard.type_text(date_str)
        time.sleep(self._typing.dropdown_wait)
        self._keyboard.enter()
        return ControlOutcome(ok=True, evidence=f"typed date {date_str!r}")

    def press_tab(self) -> ControlOutcome:
        self._keyboard.tab()
        return ControlOutcome(ok=True, evidence="tab")

    def press_enter(self) -> ControlOutcome:
        self._keyboard.enter()
        return ControlOutcome(ok=True, evidence="enter")

    def press_escape(self) -> ControlOutcome:
        self._keyboard.escape()
        return ControlOutcome(ok=True, evidence="escape")

    def scroll(self, direction: str, amount: int = 3) -> ControlOutcome:
        self._mouse.scroll(direction, amount)
        return ControlOutcome(ok=True, evidence=f"scrolled {direction} {amount}")

    def scroll_by_keys(self, direction: str, amount: int = 3) -> ControlOutcome:
        """Scroll a focused container with PageUp/PageDown keys.

        Useful when the mouse wheel is over a region that does not capture the
        wheel (nested scroll panes, web iframes). Pressing PageUp/PageDown
        scrolls whatever control currently has focus.
        """
        key = "pagedown" if direction == "down" else "pageup"
        presses = max(1, abs(amount))
        self._keyboard.press(key, presses)
        return ControlOutcome(ok=True, evidence=f"key-scrolled {direction} {presses}")

    def scroll_bar(self, direction: str, amount: int = 3) -> ControlOutcome:
        """Scroll by pressing End/Home keys toward the desired edge.

        A true scroll-bar drag requires knowing the bar's geometry; End/Home
        jump to the end of the active scroll region, which covers the same
        goal for the common long-form case.
        """
        key = "end" if direction == "down" else "home"
        self._keyboard.press(key)
        return ControlOutcome(ok=True, evidence=f"scroll-bar jump {direction} ({key})")


    def scroll_dropdown(self, direction: str, amount: int = 3) -> ControlOutcome:
        """Scroll the currently open dropdown option list.

        This is a separate scroll context from form scrolling - the mouse
        must be positioned over the dropdown option list, then wheel events
        are sent to scroll the options. This prevents accidentally scrolling
        the entire form when a dropdown is open.
        """
        # Click near the dropdown to ensure focus is on the option list
        # then scroll with mouse wheel
        self._mouse.scroll(direction, amount)
        return ControlOutcome(ok=True, evidence=f"dropdown scrolled {direction} {amount}")

    def paste(self, value: str, field_id: str | None = None) -> ControlOutcome:
        # MPF REJECTS clipboard paste - "Auto-fill or pasted text is not allowed.
        # Please type manually." So we NEVER paste; we type character-by-character.
        logger.warning("[INPUT] clipboard paste rejected by MPF - using character-by-character keyboard typing instead")
        self._ensure_focus(None)
        self._keyboard.type_text(value)
        return ControlOutcome(ok=True, evidence=f"typed {len(value)} chars (paste converted to keyboard typing)")

    def upload_file(self, bbox: BBox | None, path: str, field_id: str | None = None) -> ControlOutcome:
        """Fill a file-upload control.

        Desktop file inputs (and their ``<input type=file>`` equivalents in
        Chromium/Electron) accept a file path once focused. Click the control
        then type the absolute path and confirm. Never raises.
        """
        if not path:
            return ControlOutcome(ok=False, evidence="no file path for upload")
        if bbox is not None:
            x, y = bbox.center
            self._mouse.click(x, y)
            time.sleep(self._typing.dropdown_wait)
        self._keyboard.clear_field()
        time.sleep(0.1)
        self._keyboard.type_text(path)
        time.sleep(self._typing.dropdown_wait)
        self._keyboard.enter()
        return ControlOutcome(ok=True, evidence=f"uploaded file {path!r}")

    # -- internal helpers ----------------------------------------------------

    def _try_set_value(self, bbox: BBox | None, value: str, field_id: str | None = None) -> bool:
        """Write ``value`` through the injected UIA ValuePattern setter.

        Returns True when the setter applied the value (no focus click, no
        clearing, no typing needed). Never raises - any failure means the
        caller should fall back to the click/clear/type path.

        The whole path is a no-op when UIA value injection is disabled
        (``use_value_pattern`` / ``TYPING_USE_VALUE_PATTERN``), which is the
        default: MPF rejects ``ValuePattern.SetValue`` with an "Auto-fill or
        pasted text is not allowed" popup, so genuine per-character keyboard
        typing is the only allowed input method.
        """
        if not self._use_value_pattern:
            return False
        if self._value_setter is None or bbox is None:
            return False
        try:
            return self._value_setter(bbox, str(value))
        except Exception:
            return False

    def _ensure_focus(self, bbox: BBox | None) -> None:
        """Re-focus the field before any operation that relies on keyboard focus.

        Ctrl+A / type / Enter all act on whatever control owns focus. A layout
        shift, popup or scroll between plan and execute can steal focus, so we
        defensively click the field (when geometry is known) before clearing or
        typing. No-ops safely when no bbox is available.
        """
        if bbox is None:
            return
        self._mouse.click(bbox.left + 1, bbox.top + 1)
        time.sleep(0.12)

    def _paste_value(self, value: str) -> None:
        from atlas.act.clipboard import ClipboardEngine

        ClipboardEngine(driver=self._keyboard.driver).paste_into_focused(value)
        time.sleep(0.15)

    @staticmethod
    def _find_option_index(options: list[str], value: str) -> int | None:
        target = value.strip().lower()
        normalized = re.sub(r"[^a-z0-9]", "", target)
        for i, option in enumerate(options):
            if option.strip().lower() == target:
                return i
        for i, option in enumerate(options):
            if re.sub(r"[^a-z0-9]", "", option.lower()) == normalized:
                return i
        best_i: int | None = None
        best_score: float = 0.0
        for i, option in enumerate(options):
            o = option.lower()
            if normalized and (normalized in o or o in normalized):
                score = min(len(normalized), len(o)) / max(len(normalized), len(o), 1)
                if score > best_score:
                    best_score, best_i = score, i
        return best_i

    @staticmethod
    def _normalize_date(value: str, date_format: str | None = None) -> str:
        value = value.strip()
        if not value:
            return value
        month_names = {
            "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
            "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
            "august": 8, "aug": 8, "september": 9, "sep": 9, "october": 10, "oct": 10,
            "november": 11, "nov": 11, "december": 12, "dec": 12,
        }
        m = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$", value)
        if m:
            a, b, year = int(m.group(1)), int(m.group(2)), m.group(3)
            if b > 12 and a <= 12:
                # e.g. 03/21/1996 (MM/DD) -> day=21, month=03
                day, month = b, a
            elif a > 12 and b <= 12:
                # e.g. 21/03/1996 (DD/MM) -> day=21, month=03
                day, month = a, b
            else:
                day, month = a, b
            return f"{day:02d}/{month:02d}/{year}"
        m = re.match(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$", value)
        if m:
            y_str, mo, d = m.groups()
            return f"{int(d):02d}/{int(mo):02d}/{y_str}"
        m = re.match(r"^(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})$", value)
        if m:
            d_str, month_name, y_str = m.groups()
            month_num = month_names.get(month_name.lower())
            if month_num:
                return f"{int(d_str):02d}/{month_num:02d}/{y_str}"
        if "/" in value and value.count("/") == 2:
            parts = value.split("/")
            if all(p.isdigit() for p in parts):
                return value
        return value


__all__ = ["ControlInterface", "ControlEngine", "ControlOutcome", "ValueSetter"]

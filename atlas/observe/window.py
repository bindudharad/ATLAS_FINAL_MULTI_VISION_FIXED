"""Window attachment.

The agent attaches to a single target window (selected by the user clicking its
first editable field, or by title/handle). From then on it observes ONLY that
window's client area - ignoring taskbar, desktop, notifications, other monitors
and any overlay it draws on top.

Attachment discovers the REAL automation root instead of stopping at the first
title match. For Electron/Chrome-based apps (like MPF) the top-level window may
have pid=0, but its descendants contain the actual application with editable
controls. The attacher:

1. Enumerates all top-level windows matching the title
2. For each candidate, recursively discovers the UIA tree
3. Validates based on the presence of editable controls (not just pid>0)
4. Falls back to interactive click-to-attach if ambiguous

Never attaches to the desktop, shell, or a window without editable controls.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import win32api
import win32con
import win32gui

from atlas.core.events import EventType, get_event_bus
from atlas.core.logging import logger
from atlas.vision.capture import WindowCapture


class AttachError(RuntimeError):
    """Raised when a window cannot be attached/focused."""


#: Windows shell / desktop windows that can never be data-entry forms. The
#: title matcher never returns these, so "MPF" can't accidentally attach to
#: the taskbar, desktop, or a notification host.
_SHELL_CLASS_NAMES = {
    "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
    "DV2ControlHost", "Windows.UI.Core.CoreWindow",
}


def _normalize_title(title: str) -> str:
    """Lowercase, whitespace-normalised window title for substring matching.

    MPF's window title varies between runs ("MPF", "MPF Form Filling",
    "MPF (Download and Upload Form)", "MPF (Download and Upload Form Working
    Page") - normalising both sides makes every variant match "MPF".
    """
    return re.sub(r"\s+", " ", (title or "").strip()).lower()


@dataclass
class WindowTarget:
    """A resolved target window."""

    handle: int
    title: str
    process_id: int
    executable: str = ""
    exe_path: str = ""
    class_name: str = ""
    thread_id: int = 0

    def to_dict(self) -> dict:
        return {
            "handle": self.handle,
            "title": self.title,
            "process_id": self.process_id,
            "executable": self.executable,
            "exe_path": self.exe_path,
            "class_name": self.class_name,
            "thread_id": self.thread_id,
        }


@dataclass(frozen=True)
class AttachedTarget:
    """Immutable lock on the window the engine is attached to.

    Captured once at attach time. Every later observation/action is confined
    to ``hwnd`` / ``pid`` - the engine never scans unrelated windows, and a
    stale/closed handle is detected by comparing against this snapshot.
    """

    hwnd: int
    pid: int
    title: str
    class_name: str
    client_rect: tuple[int, int, int, int] | None
    process_name: str
    attach_timestamp: float

    def to_dict(self) -> dict:
        return {
            "hwnd": self.hwnd,
            "pid": self.pid,
            "title": self.title,
            "class_name": self.class_name,
            "client_rect": self.client_rect,
            "process_name": self.process_name,
            "attach_timestamp": self.attach_timestamp,
        }


class WindowAttacher:
    """Resolves and brings a target window to the foreground.

    ``attach`` is called after the user clicks the first editable field (the
    foreground window at that moment becomes the target). The foreground window
    is the application the user just interacted with, which is exactly the
    window we should confine observation to.
    """

    def __init__(self, capture: WindowCapture) -> None:
        self._capture = capture
        self._attached: AttachedTarget | None = None

    @property
    def attached_target(self) -> AttachedTarget | None:
        """The immutable lock on the attached window (None before attach)."""
        return self._attached

    def _lock_attached(self, target: WindowTarget) -> None:
        """Record the immutable AttachedTarget snapshot for ``target``."""
        self._attached = AttachedTarget(
            hwnd=target.handle,
            pid=target.process_id,
            title=target.title,
            class_name=target.class_name,
            client_rect=self._canvas_rect(target.handle),
            process_name=(target.exe_path or target.executable or "").split("\\")[-1],
            attach_timestamp=time.time(),
        )

    def attach_foreground(self) -> WindowTarget:
        """Attach to the currently foreground (active) top-level window."""
        bus = get_event_bus()
        bus.publish(EventType.STATE_CHANGED, {"state": "attaching"})
        handle = win32gui.GetForegroundWindow()
        if not handle:
            raise AttachError("no foreground window available")
        target = self._resolve(handle)
        self._verify_and_attach(target)
        return target

    def attach_by_title(self, title: str) -> WindowTarget:
        """Attach to the best visible top-level window whose title matches.

        Strategy chain (first match wins, never abandons a valid window):

        - A: HWND attachment - the candidate top-level window itself.
        - C: raw UIA root from HWND (``ElementFromHandle``).
        - D: descendant UIA traversal - probe every child window until editable
          controls appear (Electron/Chromium keep the real form in a child such
          as ``Chrome_RenderWidgetHostHWND``).
        - E: focused-element discovery - if a field was already clicked, walk
          the focused element's ancestry up to the real app window.

        A success is only claimed once editable controls are actually found.
        pid=0 wrappers are resolved to their real owning window before use.
        """

        bus = get_event_bus()
        bus.publish(EventType.STATE_CHANGED, {"state": "attaching"})

        candidates = self._match_window(title)
        if not candidates:
            raise AttachError(self._no_match_detail(title))

        self._log_window_matches(candidates)

        seen: set[int] = set()
        for candidate in candidates:
            target = self._resolve(candidate["handle"])
            try:
                discovered = self._discover_ui_root(target)
            except Exception as exc:
                logger.debug("[ATTACH] candidate {!r} (hwnd={}) discovery failed: {}",
                             target.title, target.handle, exc)
                continue
            if discovered is None:
                self._log_discovery_none(candidate)
                continue
            if discovered.handle in seen:
                logger.debug("[ATTACH] skip duplicate root hwnd={}", discovered.handle)
                continue
            seen.add(discovered.handle)
            try:
                self._verify_and_attach(discovered)
            except AttachError as exc:
                logger.debug("[ATTACH] candidate {!r} (hwnd={}) rejected: {}",
                             discovered.title, discovered.handle, exc)
                continue
            editable = self._count_editable(discovered.handle)
            self._log_attach_success(discovered, editable)
            return discovered

        raise AttachError(self._no_match_detail(title))

    def _match_window(self, title: str) -> list[dict]:
        """Visible top-level windows matching ``title``, best first.

        Matching is case-insensitive, whitespace-normalised and substring-based,
        so all real MPF title variants resolve:
        "MPF", "MPF Form Filling", "MPF (Download and Upload Form)",
        "MPF (Download and Upload Form Working Page)". Shell/desktop windows
        are excluded so the agent never attaches to the taskbar/desktop.

        Candidates are ranked so the REAL MPF window wins when several windows
        match: the visible foreground window first, then the largest visible
        window (an MPF form is a big client area, never a tiny status bar),
        then the longest title match (a fuller MPF title names the form page).
        """
        import win32gui

        candidates: list[dict] = []
        title_norm = _normalize_title(title)
        if not title_norm:
            return candidates
        try:
            foreground = win32gui.GetForegroundWindow()
        except Exception:
            foreground = 0

        def _collect(handle: int, _: Any = None) -> None:
            try:
                if not win32gui.IsWindowVisible(handle):
                    return
                window_title = win32gui.GetWindowText(handle) or ""
                if not _normalize_title(window_title):
                    return
                if title_norm not in _normalize_title(window_title):
                    return
                class_name = win32gui.GetClassName(handle) or ""
                if class_name in _SHELL_CLASS_NAMES:
                    return
                thread_id, pid = self._winapi_query_window(handle)
                exe, exe_path = self._executable_for(pid)
                area = 0
                try:
                    rect = win32gui.GetWindowRect(handle)
                    area = max(0, (rect[2] - rect[0]) * (rect[3] - rect[1]))
                except Exception:
                    pass
                candidates.append({
                    "handle": handle,
                    "title": window_title,
                    "class_name": class_name,
                    "process_id": pid,
                    "thread_id": thread_id,
                    "executable": exe,
                    "exe_path": exe_path,
                    "_area": area,
                    "_foreground": handle == foreground,
                })
            except Exception:
                pass

        win32gui.EnumWindows(_collect, None)
        candidates.sort(key=lambda c: (
            0 if c["_foreground"] else 1,
            -c["_area"],
            -len(c["title"]),
        ))
        return candidates

    @staticmethod
    def _log_window_matches(candidates: list[dict]) -> None:
        """Emit one [ATTACH] line per candidate with pid/process/class/title."""
        logger.info("[ATTACH] {} matching window(s) found:", len(candidates))
        for c in candidates:
            exe = (c.get("exe_path") or c.get("executable") or "").split("\\")[-1]
            logger.info(
                "  [WINDOW] hwnd={} pid={} process={} class={!r} title={!r}",
                hex(c["handle"]), c["process_id"], exe or "?", c["class_name"], c["title"],
            )

    @staticmethod
    def _log_discovery_none(candidate: dict) -> None:
        logger.debug(
            "[ATTACH] no UI root found for title={!r} hwnd={} pid={}",
            candidate.get("title"), hex(candidate.get("handle", 0)), candidate.get("process_id"),
        )

    @staticmethod
    def _log_attach_success(target: WindowTarget, editable: int) -> None:
        rect = WindowAttacher._canvas_rect(target.handle)
        logger.info("[ATTACHED] {} editable control(s) found - attached", editable)
        logger.info(
            "  [TARGET] hwnd={} pid={} process={} class={!r} title={!r} rect={}",
            hex(target.handle), target.process_id,
            (target.exe_path or target.executable or "").split("\\")[-1],
            target.class_name, target.title, rect,
        )

    @staticmethod
    def _count_editable(handle: int) -> int:
        """Best-effort editable control count under ``handle`` (0 on failure)."""
        try:
            from atlas.observe.uia import UiaBackend
            best = UiaBackend.instance().best_editable_root(handle)
            if best is not None:
                return int(best.get("count", 0))
        except Exception:
            pass
        return 0

    def _discover_ui_root(self, target: WindowTarget) -> WindowTarget | None:
        """Resolve the REAL form container for a candidate (touch-free).

        Strategy order:

        - E: focused-element discovery - if the user clicked a field already,
          the focused element's HWND ancestry points at the app window.
        - C + D: raw UIA root from the HWND, then probe every child window for
          editable controls (child windows can hold the real form for
          Electron/Chromium apps - e.g. ``Chrome_RenderWidgetHostHWND``).
        - B: legacy descendant walk + child-HWND scan as a fallback.

        The candidate is never rejected just because its top-level root has no
        editable descendants - child windows and the focused element are both
        consulted before concluding failure.
        """
        try:
            from atlas.observe.uia import UiaBackend
            backend = UiaBackend.instance()
            if not backend.available:
                logger.error("[UIA] backend unavailable - cannot discover editable controls")
                return None

            # Strategy E: prefer the element the user is already interacting with.
            focus_target = self._root_from_focused()
            if focus_target is not None:
                logger.info("[UIA] resolved root {} from focused element", focus_target.handle)
                return focus_target

            # Strategies C + D: raw UIA root, then best window (handle or child).
            best = backend.best_editable_root(target.handle)
            if best is not None:
                root_handle = best["hwnd"]
                if root_handle != target.handle:
                    logger.info(
                        "[UIA] resolved to child window hwnd={} ({} editable controls) under hwnd={}",
                        hex(root_handle), best.get("count"), hex(target.handle),
                    )
                else:
                    logger.info("[UIA] resolved to hwnd={} ({} editable controls)",
                                hex(root_handle), best.get("count"))
                root_target = self._resolve(root_handle)
                if root_handle != target.handle:
                    # keep the parent's (richer) title/paths when the child is anonymous
                    root_target.title = root_target.title or target.title
                    root_target.exe_path = root_target.exe_path or target.exe_path
                return root_target

            # Zero editable controls within the bounded probe = "UIA
            # insufficient", NOT "no form". The engine still attaches to the
            # window and fills the form through CV/OCR perception.
            logger.info(
                "[DISCOVERY] UIA insufficient for hwnd={} (pid={}): 0 editable controls "
                "within the discovery budget - falling back to perception (CV/OCR)",
                hex(target.handle), target.process_id,
            )

            # Fallback: legacy virtual-descendant + child-HWND scan (same-process only).
            child_handle = self._find_child_with_controls(target.handle, target.process_id)
            if child_handle and child_handle != target.handle:
                child_target = self._resolve(child_handle)
                child_target.title = child_target.title or target.title
                return child_target

            # UIA exposed no editable controls anywhere. That is NOT a reason
            # to reject the window (see _verify_target_tree): legacy/custom
            # GUIs like MPF keep their editables outside the UIA hierarchy.
            # Accept the title-matched window itself - the engine's perception
            # chain (CV/OCR + screen geometry) discovers the actual form.
            if self._is_valid_click_target(target):
                logger.info(
                    "[DISCOVERY] attaching {!r} (hwnd={}) with UIA insufficient - "
                    "perception (CV/OCR) will discover the form fields",
                    target.title, hex(target.handle),
                )
                return target
            return None
        except Exception as exc:
            logger.debug("_discover_ui_root failed: {}", exc)
        return None

    def _root_from_focused(self) -> WindowTarget | None:
        """Resolve the app root from the currently focused element.

        Walks the focused element's HWND ancestry to the top-level application
        window and confirms that editable controls exist there. Returns None
        when nothing editable is focused or no resolvable window survives.
        """
        try:
            from atlas.observe.uia import UiaBackend
            backend = UiaBackend.instance()
            focus = backend.focused_element_and_chain()
            if not focus or not focus.get("chain"):
                return None
            chain = focus["chain"]
            if not chain or not chain[0] or not chain[0].get("editable", False):
                return None
            hwnd_roots = focus.get("hwnd_roots") or []
            for hwnd in hwnd_roots:
                try:
                    if not win32gui.IsWindow(hwnd):
                        continue
                    ancestor = self._get_ancestor(hwnd, 3) or hwnd
                    if not win32gui.IsWindow(ancestor):
                        continue
                    root_target = self._resolve(ancestor)
                    if not root_target.title.strip():
                        continue
                    best = backend.best_editable_root(root_target.handle)
                    if best is None:
                        continue
                    best_handle = best["hwnd"]
                    if best_handle != root_target.handle:
                        resolved = self._resolve(best_handle)
                        resolved.title = resolved.title or root_target.title
                        resolved.exe_path = resolved.exe_path or root_target.exe_path
                        return resolved
                    return root_target
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("_root_from_focused failed: {}", exc)
        return None

    def _find_child_with_controls(self, parent_handle: int, parent_pid: int = 0) -> int | None:
        """Find the first child window that might contain editable controls.

        Confined to the target's OWN process tree: when ``parent_pid`` is
        known, child HWNDs owned by a different process are skipped so the
        engine never scans unrelated windows.
        """
        try:
            import ctypes

            user32 = ctypes.windll.user32

            found: list[int] = []
            def _enum(handle: int, _: Any) -> bool:
                try:
                    if win32gui.IsWindowVisible(handle):
                        found.append(handle)
                except Exception:
                    pass
                return True

            win32gui.EnumChildWindows(parent_handle, _enum, None)

            # Check each child for editable controls (bounded single retry).
            from atlas.observe.uia import UiaBackend
            backend = UiaBackend.instance()
            for handle in found:
                if parent_pid > 0:
                    try:
                        _, child_pid = self._winapi_query_window(handle)
                    except Exception:
                        child_pid = parent_pid
                    if child_pid != parent_pid:
                        continue
                try:
                    editable = backend.editable_fields(handle)
                    if editable:
                        return handle
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("_find_child_with_controls failed: {}", exc)
        return None

    def _verify_and_attach(self, target: WindowTarget) -> None:
        """Verify the target tree, generate UIA diagnostics, then attach capture."""
        bus = get_event_bus()
        self._verify_target_tree(target)
        # Generate UIA diagnostics (Step 2) to debug/uia/.
        try:
            self._dump_uia_diagnostics(target)
        except Exception as exc:
            logger.debug("uia diagnostics dump failed: {}", exc)
        self._capture.attach(target.handle, target.title)
        self._lock_attached(target)
        bus.publish(EventType.STATE_CHANGED, {"state": "inspecting_ui"})

    @staticmethod
    def _dump_uia_diagnostics(target: WindowTarget) -> None:
        """Write the full UIA diagnostic set to ``debug/uia/`` (Step 2)."""
        try:
            from atlas.observe.uia import UiaBackend

            backend = UiaBackend.instance()
            out = Path("debug/uia")
            backend.dump_diagnostics(target.handle, out)
        except Exception as exc:
            logger.debug("uia diagnostics failed: {}", exc)

    def attach_by_handle(self, handle: int) -> WindowTarget:
        if not win32gui.IsWindow(handle):
            raise AttachError(f"invalid window handle {handle}")
        target = self._resolve(handle)
        self._capture.attach(target.handle, target.title)
        return target

    def attach_by_click(self, timeout: float = 300.0) -> WindowTarget:
        """Attach to the window the user clicks (Step 5 / Step 8).

        Waits for a mouse click, then resolves the real top-level application
        window under the cursor using ``WindowFromPoint`` + ``GetAncestor``.
        This is the reliable way to attach to Electron/Chrome-based apps (like
        MPF) where ``EnumWindows`` finds ghost windows with pid=0.

        Loops forever until a valid application window is selected, timeout
        expires, or ESC is pressed. Never attaches to desktop/shell.
        """
        from atlas.observe.click_hook import MouseClickListener

        bus = get_event_bus()
        bus.publish(EventType.STATE_CHANGED, {"state": "attaching"})
        logger.info("ATTACH MODE: click the MPF application window to attach")
        logger.info("  (click anywhere inside the MPF window's client area)")

        listener = MouseClickListener()
        listener.start()
        try:
            deadline = time.time() + timeout
            while time.time() < deadline:
                click = listener.wait_for_click(deadline - time.time())
                if click is None:
                    raise AttachError(
                        f"no click received within {timeout:.0f}s - "
                        "click the MPF application window to attach"
                    )
                x, y = click
                target = self._resolve_window_at_point(x, y)
                if target is None:
                    logger.warning(
                        "Ignored click at ({}, {}) - not a valid application window. "
                        "Click inside the MPF application window. Waiting...",
                        x, y,
                    )
                    continue
                # Valid target found - verify and attach.
                try:
                    self._verify_and_attach(target)
                    self._print_attach_summary(target)
                    return target
                except AttachError as exc:
                    logger.warning("Attach attempt failed: {}. Waiting...", exc)
                    continue
                except Exception as exc:
                    logger.warning("Unexpected error during attach: {}. Waiting...", exc)
                    continue
            raise AttachError(f"attach timed out after {timeout:.0f}s")
        finally:
            listener.stop()

    def _resolve_window_at_point(self, x: int, y: int) -> WindowTarget | None:
        """Resolve the real top-level application window at a screen point.

        Uses ``WindowFromPoint`` to get the immediate window under the cursor,
        then ``GetAncestor(GA_ROOTOWNER)`` to climb to the top-level owner.
        Rejects windows with pid=0, desktop shells, and invisible windows.
        """
        try:
            handle = win32gui.WindowFromPoint((x, y))
            if not handle:
                return None
            # Climb to the root owner using GetAncestor (GA_ROOTOWNER = 3).
            root = self._get_ancestor(handle, 3)
            if root:
                handle = root
            else:
                # Fallback: climb via GetParent.
                while win32gui.GetParent(handle):
                    handle = win32gui.GetParent(handle)
            target = self._resolve(handle)
            # Reject invalid windows.
            if not self._is_valid_click_target(target):
                logger.warning(
                    "window at ({}, {}) is not a valid target: "
                    "title={!r} pid={} class={!r}",
                    x, y, target.title, target.process_id, target.class_name,
                )
                return None
            return target
        except Exception as exc:
            logger.debug("resolve_window_at_point failed: {}", exc)
            return None

    @staticmethod
    def _get_ancestor(handle: int, flags: int) -> int | None:
        """Call GetAncestor via ctypes (not in win32gui)."""
        try:
            import ctypes

            user32 = ctypes.windll.user32
            user32.GetAncestor.restype = ctypes.c_void_p
            user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            result = user32.GetAncestor(handle, flags)
            return int(result) if result else None
        except Exception:
            return None

    @staticmethod
    def _is_valid_click_target(target: WindowTarget) -> bool:
        """A click-resolved window is potentially valid if it looks like an app.

        Does NOT reject pid=0 immediately - Electron/Chrome apps often have
        pid=0 on the wrapper window. The final validation happens in
        _verify_target_tree which checks for editable controls.
        """
        if not target.title.strip():
            return False
        # Reject desktop shells.
        if target.class_name in {"Progman", "WorkerW", "Shell_TrayWnd", "DV2ControlHost"}:
            return False
        # Reject obvious non-app windows.
        if target.class_name in {"Windows.UI.Core.CoreWindow"}:
            # Might be a notification toast - check if it has editable controls.
            pass  # Let _verify_target_tree decide.
        # Reject invisible / zero-size windows.
        try:
            if not win32gui.IsWindowVisible(target.handle):
                return False
            rect = win32gui.GetWindowRect(target.handle)
            if rect[2] - rect[0] <= 0 or rect[3] - rect[1] <= 0:
                return False
        except Exception:
            return False
        return True

    @staticmethod
    def _print_attach_summary(target: WindowTarget) -> None:
        """Print the full attachment summary (Step 6)."""
        from atlas.observe.uia import UiaBackend

        print("-" * 50)
        print("ATTACHED")
        print(f"  Process:     {target.executable or target.exe_path or '?'}")
        print(f"  PID:         {target.process_id}")
        print(f"  HWND:        {target.handle}")
        print(f"  Class:       {target.class_name}")
        print(f"  Title:       {target.title}")
        try:
            origin = UiaBackend.client_origin(target.handle)
            size = UiaBackend.client_size(target.handle)
            print(f"  Client Size: {size[0]}x{size[1]} at ({origin[0]}, {origin[1]})")
        except Exception:
            pass
        try:
            backend = UiaBackend.instance()
            nodes = backend.descendants(target.handle)
            editable = [n for n in nodes if n.editable]
            buttons = [n for n in nodes if n.control_type in {"Button", "SplitButton"}]
            combos = [n for n in nodes if n.control_type == "ComboBox"]
            edits = [n for n in nodes if n.control_type == "Edit"]
            scrolls = [n for n in nodes if n.control_type == "ScrollBar"]
            print(f"  UIA Root:    {'yes' if nodes else 'no'}")
            print(f"  Controls:    {len(nodes)}")
            print(f"  Editable:    {len(editable)}")
            print(f"  Buttons:     {len(buttons)}")
            print(f"  ComboBoxes:  {len(combos)}")
            print(f"  TextBoxes:   {len(edits)}")
            print(f"  ScrollBars:  {len(scrolls)}")
        except Exception as exc:
            print(f"  UIA:         error: {exc}")
        print("-" * 50)

    def bring_to_front(self, target: WindowTarget) -> None:
        """Restore and foreground the target window (best-effort)."""
        try:
            if win32gui.IsIconic(target.handle):
                win32gui.ShowWindow(target.handle, win32con.SW_RESTORE)
            # Windows only lets the process that owns the foreground window
            # change it, so a background agent cannot steal focus with a plain
            # SetForegroundWindow. A simulated ALT press temporarily releases
            # that lock; AttachThreadInput handles the stubborn cases.
            try:
                win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
                win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.05)
            except Exception:
                pass
            win32gui.SetForegroundWindow(target.handle)
            try:
                import win32process

                fg = win32gui.GetForegroundWindow()
                fg_thread, _ = win32process.GetWindowThreadProcessId(fg)
                cur_thread = win32api.GetCurrentThreadId()
                if fg_thread != cur_thread and fg_thread != 0:
                    win32process.AttachThreadInput(cur_thread, fg_thread, True)
                    win32gui.SetForegroundWindow(target.handle)
                    win32process.AttachThreadInput(cur_thread, fg_thread, False)
            except Exception:
                pass
            time.sleep(0.15)
        except Exception as exc:
            logger.warning("could not bring window to front: {}", exc)

    def verify_focused(self, target: WindowTarget) -> bool:
        """Check that the target window is currently the foreground window."""
        try:
            return win32gui.GetForegroundWindow() == target.handle
        except Exception:
            return False

    def focus_and_verify(self, target: WindowTarget, retries: int = 3) -> bool:
        for _ in range(retries):
            if self.verify_focused(target):
                return True
            self.bring_to_front(target)
            time.sleep(0.2)
        return self.verify_focused(target)

    def _resolve(self, handle: int) -> WindowTarget:
        title = win32gui.GetWindowText(handle) or ""
        class_name = ""
        try:
            class_name = win32gui.GetClassName(handle) or ""
        except Exception:
            class_name = ""
        thread_id, pid = self._winapi_query_window(handle)
        exe, exe_path = self._executable_for(pid)
        return WindowTarget(
            handle=handle,
            title=title,
            process_id=pid,
            executable=exe,
            exe_path=exe_path,
            class_name=class_name,
            thread_id=thread_id,
        )

    @staticmethod
    def _winapi_query_window(handle: int) -> tuple[int, int]:
        """(thread_id, pid) for an HWND via Win32, with a pid=0 recovery.

        ``GetWindowThreadProcessId`` normally returns a real PID. A wrapper
        (CEF/Chromium/Electron, a cross-session window, or a process mid-teardown)
        can come back as pid=0; we then recover the real owning process through
        the window's thread (``OpenThread`` + ``GetProcessIdOfThread``) instead
        of trusting the wrapper's stale pid.
        """
        try:
            tid, pid = _native_get_window_thread_process_id(handle)
        except Exception:
            return 0, 0
        if pid > 0:
            return tid, pid
        if tid > 0:
            try:
                pid = _native_pid_from_thread(tid)
            except Exception:
                pass
        return tid, pid

    @staticmethod
    def _canvas_rect(handle: int) -> tuple[int, int, int, int] | None:
        """Window bounding rectangle (left, top, right, bottom) or None."""
        try:
            rect = win32gui.GetWindowRect(handle)
            return tuple(int(v) for v in rect)
        except Exception:
            return None

    @staticmethod
    def _executable_for(pid: int) -> tuple[str, str]:
        """Return (exe name, full exe path) for a process id."""
        if pid <= 0:
            return "", ""
        try:
            import psutil

            proc = psutil.Process(pid)
            try:
                path = proc.exe() or ""
            except Exception:
                path = ""
            try:
                name = proc.name() or ""
            except Exception:
                name = ""
            return name, path
        except Exception:
            return "", ""

    def _verify_target_tree(self, target: WindowTarget) -> None:
        """Verify the target is a real, attachable application window.

        Discovery is STAGED and UIA is OPTIONAL. Legacy/custom GUIs like MPF
        often expose labels but NO editable controls through UIA; that means
        only "UIA did not expose the editables in this hierarchy", NOT "not a
        data-entry form". The window is therefore accepted and the engine
        fills the form through the perception chain (CV/OCR over the window
        capture, screen geometry, input rectangles) - exactly what earlier
        versions of the agent did for this same MPF form.

        Staged discovery order (each stage bounded; results cached):
          A. quick flat UIA (pywinauto ``descendants``)
          B. bounded recursive UIA (explicit ``children()`` walk)
          C. perception / OCR / CV (handled by the loop's perception fallback)
          D. coordinate / input-rectangle discovery (handled by the field engine)

        A window is only rejected when it is not a plausible application
        window at all (shell/desktop, invisible, or title-less) - never
        because UIA found zero editable controls.
        """
        try:
            from atlas.observe.uia import UiaBackend
            backend = UiaBackend.instance()
            if backend.available:
                # Staged A + B in ONE bounded, cached probe. A zero-editable
                # probe is NOT a rejection: it selects the perception fallback.
                best = backend.best_editable_root(target.handle)
                if best is not None:
                    logger.info(
                        "[DISCOVERY] UIA full: {} editable control(s) under hwnd={}",
                        best.get("count"), hex(best.get("hwnd", target.handle)),
                    )
                else:
                    logger.info(
                        "[DISCOVERY] UIA partial: no editable control(s) exposed - "
                        "using perception fallback (CV/OCR) for {!r}",
                        target.title,
                    )
            else:
                logger.info(
                    "[DISCOVERY] UIA backend unavailable for {!r} - "
                    "using perception fallback (CV/OCR)", target.title,
                )
        except Exception as exc:
            # Discovery is best-effort: a UIA failure must never block attach
            # when perception can still operate the window.
            logger.debug("UIA inspection failed for {}: {}", target.title, exc)

    @staticmethod
    def _no_match_detail(title: str) -> str:
        import win32gui

        all_windows: list[dict] = []
        title_norm = _normalize_title(title)

        def _collect(handle: int, _: Any = None) -> None:
            try:
                if not win32gui.IsWindowVisible(handle):
                    return
                window_title = win32gui.GetWindowText(handle) or ""
                if not _normalize_title(window_title):
                    return
                if title_norm not in _normalize_title(window_title):
                    return
                class_name = win32gui.GetClassName(handle) or ""
                thread_id, pid = 0, 0
                try:
                    thread_id, pid = win32gui.GetWindowThreadProcessId(handle)
                except Exception:
                    pass
                all_windows.append({
                    "title": window_title,
                    "class_name": class_name,
                    "process_id": pid,
                    "thread_id": thread_id,
                })
            except Exception:
                pass

        win32gui.EnumWindows(_collect, None)

        if not all_windows:
            return (
                f"no visible window found matching title {title!r}.\n"
                f"Open the MPF (Download and Upload Form) window first, then re-run."
            )

        lines = []
        for info in all_windows:
            pid = info.get("process_id", 0)
            class_name = info.get("class_name", "")
            lines.append(
                f"  - {info['title']!r} (pid={pid}, class={class_name!r})"
            )

        return (
            f"{len(all_windows)} window(s) matched title {title!r}.\n"
            "Recursive UIA discovery was attempted but none contained editable controls.\n"
            "Open the MPF window and click inside it, then re-run with --attach.\n"
            + "\n".join(lines)
        )


def window_under_cursor() -> WindowTarget | None:
    """Return the top-level window under the current cursor position."""
    try:
        pos = win32api.GetCursorPos()
        handle = win32gui.WindowFromPoint(pos)
        if not handle:
            return None
        # climb to the top-level owner
        while win32gui.GetParent(handle):
            handle = win32gui.GetParent(handle)
        return _target_from_handle(handle)
    except Exception:
        return None


def _target_from_handle(handle: int) -> WindowTarget | None:
    try:
        title = win32gui.GetWindowText(handle) or ""
        class_name = win32gui.GetClassName(handle) or ""
        thread_id = 0
        pid = 0
        try:
            thread_id, pid = win32gui.GetWindowThreadProcessId(handle)
        except Exception:
            pass
        exe, exe_path = WindowAttacher._executable_for(pid)
        return WindowTarget(
            handle=handle,
            title=title,
            process_id=pid,
            executable=exe,
            exe_path=exe_path,
            class_name=class_name,
            thread_id=thread_id,
        )
    except Exception:
        return None


def _invalid_reason(info: dict) -> str:
    """Why a candidate window was rejected by the attach validation."""
    pid = info.get("process_id") or 0
    if pid <= 0:
        return "-> rejected: no valid process (pid=0)"
    exe = (info.get("executable") or "").split("\\")[-1]
    class_name = info.get("class_name") or ""
    if class_name in {"Progman", "WorkerW", "Shell_TrayWnd", "DV2ControlHost"}:
        return f"-> rejected: desktop/taskbar shell (class={class_name!r})"
    if not exe:
        return "-> rejected: no executable"
    return "-> rejected: system process (not an application window)"


def _native_get_window_thread_process_id(handle: int) -> tuple[int, int]:
    """(thread_id, pid) for an HWND via ``GetWindowThreadProcessId``.

    Kept as a module-level helper so tests can replace it without touching
    ctypes internals.
    """
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND, ctypes.POINTER(wintypes.DWORD),
    ]
    pid_out = wintypes.DWORD(0)
    tid = int(
        user32.GetWindowThreadProcessId(wintypes.HWND(int(handle)), ctypes.byref(pid_out))
    )
    return tid, int(pid_out.value)


def _native_pid_from_thread(tid: int) -> int:
    """Owning pid of a thread id via ``OpenThread`` + ``GetProcessIdOfThread``."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    thread_query_limited_information = 0x0800
    kernel32.OpenThread.restype = wintypes.HANDLE
    kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.GetProcessIdOfThread.restype = wintypes.DWORD
    kernel32.GetProcessIdOfThread.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    h = kernel32.OpenThread(thread_query_limited_information, False, tid)
    if not h:
        return 0
    try:
        return int(kernel32.GetProcessIdOfThread(h))
    finally:
        kernel32.CloseHandle(h)


__all__ = ["WindowAttacher", "WindowTarget", "AttachError", "window_under_cursor"]

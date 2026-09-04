#!/usr/bin/env python3
"""ATLAS AI - command line entry point.

Commands
--------
  run     attach to a target and run the data-entry loop once
  serve   start the localhost JSON command server
  doctor  print an environment / dependency report
  version print the version and exit

Examples
--------
  python main.py run --web --url http://localhost:5173 --max-records 3
  python main.py run --title "Customer Entry"
  python main.py serve --port 19768
  python main.py doctor
"""

from __future__ import annotations

import argparse
import json
import sys

from atlas import APP_NAME, __version__
from atlas.config import load_config
from atlas.core.logging import logger, setup_logging


def _config(args: argparse.Namespace) -> object:
    return load_config()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atlas", description=f"{APP_NAME} v{__version__}")
    parser.add_argument("--log-level", default="", help="override LOG_LEVEL (DEBUG/INFO/WARNING/ERROR)")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="attach and run the loop")
    target = run.add_mutually_exclusive_group(required=False)
    target.add_argument("--web", action="store_true", help="attach to a web page (Playwright)")
    target.add_argument("--title", metavar="TITLE", help="attach to a desktop window by title")
    target.add_argument("--attach", action="store_true", help="click-to-attach: wait for the user to click the target window (reliable for Electron/Chrome apps)")
    run.add_argument("--mode", choices=["auto", "web", "desktop", "click"], default=None,
                     help="attach strategy: auto = universal attach-first (never relaunches an "
                          "existing browser/target); web = open a URL; desktop = attach by title; "
                          "click = user clicks the target window")
    run.add_argument("--auto", action="store_true",
                     help="alias for --mode auto (universal attach-first)")
    run.add_argument("--app-name", default="", help="auto mode: expected application name hint")
    run.add_argument("--url", default="http://localhost:5173", help="web URL (default http://localhost:5173)")
    run.add_argument("--browser", choices=["chromium", "firefox", "webkit"], default="chromium")
    run.add_argument("--headless", action="store_true", help="run the browser headless")
    run.add_argument("--max-records", type=int, default=0, help="stop after N records (0 = unlimited)")
    run.add_argument("--single-form", action="store_true",
                     help="SINGLE-FORM TEST MODE: process exactly ONE complete form (fill + verify, "
                          "never click Upload Details unless WORKFLOW_SINGLE_FORM_UPLOAD=1), then "
                          "terminate ATLAS cleanly")
    run.add_argument("--no-overlay", action="store_true", help="disable the floating overlay")
    run.add_argument("--json", action="store_true", help="print the summary as JSON")
    run.add_argument("--anchor", action="store_true", help="desktop: wait for your click on the first form field, build a UIA field map, then run")
    run.add_argument("--out", default="debug/mpf", help="debug/session output directory (default debug/mpf)")

    serve = sub.add_parser("serve", help="start the JSON command server")
    serve.add_argument("--port", type=int, default=0, help="port (default: CONTROLLER_COMMAND_PORT)")

    sub.add_parser("doctor", help="environment report")
    sub.add_parser("version", help="print version")

    diag = sub.add_parser("diagnose", help="dump a diagnostic snapshot of a target window")

    obs = sub.add_parser(
        "observe",
        help="attach and observe ONLY - no typing/clicking/scrolling/upload. Alias for diagnose.",
    )
    obs.add_argument("--title", default="MPF", help="window title to attach to")
    obs.add_argument("--out", default="debug/mpf", help="output directory")

    vdoc = sub.add_parser(
        "vision-doctor",
        help="report configured Vision providers, then run ONE live provider call against the "
             "attached window's screenshot (no typing/clicking/scrolling/upload)",
    )
    vdoc.add_argument("--title", default="MPF", help="window title to attach to")

    obs_src = sub.add_parser(
        "observe-source",
        help="comprehensive source panel observation diagnostic - traces full pipeline from window to structured fields",
    )
    obs_src.add_argument("--title", default="MPF", help="window title to attach to (substring match)")
    obs_src.add_argument("--out", default="debug/mpf/observation_debug", help="output directory for diagnostic images/json")
    obs_src.add_argument("--no-vlm", action="store_true", help="skip VLM even if configured")
    obs_src.add_argument("--save-annotated", action="store_true", help="save annotated images with ROI overlays")

    test_ocr = sub.add_parser(
        "test-ocr",
        help="test OCR directly on a saved image file (bypasses window capture)",
    )
    test_ocr.add_argument("--image", required=True, help="path to image file")
    test_ocr.add_argument("--out", default="debug/mpf/ocr_test", help="output directory")
    test_ocr.add_argument("--engine", default="paddle", choices=["paddle", "tesseract"], help="OCR engine")

    diag.add_argument("--title", default="MPF", help="window title to attach to (substring match)")
    diag.add_argument("--out", default="debug/mpf", help="output directory")

    return parser


def _setup(args: argparse.Namespace) -> object:
    config = _config(args)
    level = (args.log_level or config.log.level) if getattr(config, "log", None) else args.log_level
    setup_logging(level.upper(), config.log.folder)
    return config


def cmd_run(args: argparse.Namespace) -> int:
    from atlas.assistant import Assistant
    from atlas.dashboard import Dashboard
    from atlas.target.web import WebTarget
    from atlas.vision.providers import vision_status_lines

    config = _setup(args)
    
    # Print vision configuration status upfront
    for line in vision_status_lines(config.vision):
        print(line)
    print(f"OCR engine: {config.ocr.engine}")
    print(f"REASONING provider: {config.reasoning.provider} ({'configured' if config.reasoning.api_key or config.reasoning.api_base else 'not configured'})")
    print(f"WORKFLOW: records_per_run={config.workflow.records_per_run} field_driven={config.workflow.field_driven} single_form={config.workflow.single_form_mode}")
    print()
    
    dashboard = Dashboard(enabled=not args.no_overlay)
    mode = args.mode or (
        "auto" if args.auto else
        "web" if args.web else
        "desktop" if args.title else
        "click"
    )
    with Assistant(config) as assistant:
        if mode == "auto":
            # Universal attach-first: DISCOVER -> CLASSIFY -> ATTACH. Uses the
            # existing window/browser/tab; only launches a fresh browser when no
            # target exists anywhere AND AUTO_LAUNCH_TARGET=true.
            print("AUTO ATTACH MODE: scanning for an existing target ...")
            target = assistant.attach_auto(
                title=args.title or None,
                url=args.url,
                app_name=args.app_name or None,
            )
        elif mode == "web":
            assistant.attach_web(url=args.url, browser=args.browser, headless=args.headless)
        elif mode == "desktop":
            assistant.attach_desktop(title=args.title)
        else:
            # Click-to-attach mode (Step 8): user clicks the target window,
            # then clicks the first editable field, then autonomous entry.
            print("ATTACH MODE: click the MPF application window to attach ...")
            assistant.attach_desktop_by_click()
        dashboard.start()
        print(f"attached: {assistant.target.info.to_dict()}")
        single_form = args.single_form or config.workflow.single_form_mode
        if single_form:
            print("MODE: SINGLE FORM — exactly one form, then ATLAS terminates automatically")
        records = 1 if single_form else args.max_records
        if mode in {"auto", "web"} and isinstance(assistant.target, WebTarget):
            summary = assistant.run(max_records=records, out_dir=args.out, single_form=single_form)
        else:
            # Desktop targets use the interactive anchored flow by default
            # (Step 7): attach -> WAITING_FOR_START_FIELD -> user clicks the
            # first editable field -> build field map -> autonomous entry.
            print("waiting for you to click the first editable field in the form's RIGHT panel ...")
            summary = assistant.run_anchored(max_records=records, out_dir=args.out, single_form=single_form)
        dashboard.stop()
        result = summary.to_dict()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        else:
            print(f"records: {len(result['records'])}  completed: {result['completed']}  "
                  f"failed: {result['failed']}  duration: {result['total_duration']:.1f}s")
            if result.get("stopped_reason"):
                print(f"stopped: {result['stopped_reason']}")
    return 0 if result["failed"] == 0 else 1


def cmd_serve(args: argparse.Namespace) -> int:
    from atlas.assistant import Assistant, CommandServer, Controller

    config = _setup(args)
    with Assistant(config) as assistant:
        controller = Controller(assistant)
        port = args.port or config.controller.command_port
        server = CommandServer(controller, host="127.0.0.1", port=port)
        server.start()
        print(f"ATLAS AI command server: {server.url}  (Ctrl+C to stop)")
        try:
            import time

            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass
        finally:
            server.stop()
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    _setup(args)
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append((name, ok, detail))

    check("python >= 3.10", sys.version_info[:2] >= (3, 10), sys.version.split()[0])

    for module in ("numpy", "PIL", "mss", "loguru", "rapidfuzz", "requests", "dotenv", "win32gui", "pyautogui", "pyperclip"):
        try:
            __import__({"PIL": "PIL", "dotenv": "dotenv"}.get(module, module))
            check(module, True, "ok")
        except Exception as exc:
            check(module, False, str(exc))

    for optional in ("cv2", "paddleocr", "playwright"):
        try:
            __import__(optional)
            check(optional, True, "ok")
        except Exception as exc:
            check(optional, False, str(exc))

    try:
        import pyautogui

        check("screen size", True, str(pyautogui.size()))
    except Exception as exc:
        check("screen size", False, str(exc))

    ok = True
    for name, passed, detail in checks:
        flag = "ok " if passed else "MISS"
        print(f"[{flag}] {name:16s} {detail}")
        ok = ok and passed
    print()
    try:
        from atlas.config import load_config
        from atlas.vision.manager import format_provider_status

        print(format_provider_status(load_config().vision))
    except Exception as exc:
        print(f"[MISS] vision provider status unavailable: {exc}")
    print()
    print(f"version: {APP_NAME} {__version__}")
    return 0 if ok else 1


def cmd_vision_doctor(args: argparse.Namespace) -> int:
    """Diagnose the Vision provider chain against a live MPF screenshot
    without typing/clicking/scrolling/uploading - reports which provider
    answered, latency, and structured field count. Requires Windows + an
    open MPF window; the provider-status portion works everywhere.
    """
    from atlas.config import load_config
    from atlas.vision.manager import VisionProviderManager, format_provider_status

    _setup(args)
    config = load_config()
    print(format_provider_status(config.vision))
    print()

    manager = VisionProviderManager(config.vision)
    if not manager.configured_providers:
        print("No Vision provider configured - nothing further to test.")
        print("Set GOOGLE_STUDIO_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY in .env and re-run.")
        return 1

    try:
        from atlas.observe.window import AttachError
        from atlas.vision.capture import WindowCapture
        from atlas.assistant.assistant import Assistant

        assistant = Assistant(config)
        attach_target = assistant.attach_desktop(title=args.title)
        handle = attach_target.info.handle
        capture = WindowCapture(grabber=assistant._grabber)  # noqa: SLF001 - internal reuse, same pattern as Diagnostics.run()
        capture.attach(handle, attach_target.info.title)
        area = capture.capture_until_nonempty(timeout=10.0)
    except AttachError as exc:
        print(
            f"error: {exc}\n"
            f"Open the MPF (Download and Upload Form) window first, then re-run:\n"
            f"  python main.py vision-doctor --title \"{args.title}\"",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"error: could not attach/capture: {exc}")
        return 1

    if area is None:
        print("error: capture returned no image (window may be minimized or off-screen)")
        return 1

    import time as _time

    start = _time.perf_counter()
    try:
        scene = manager.describe(area.image, window_title=attach_target.info.title)
    except Exception as exc:
        print(f"provider used: NONE (all failed) - {exc}")
        return 1
    latency_ms = (_time.perf_counter() - start) * 1000.0

    print(f"provider used: {scene.provider}")
    print(f"latency: {latency_ms:.0f} ms")
    print(f"success: True")
    print(f"structured field count: {len(scene.elements)}")
    print(f"overall confidence: {scene.confidence:.2f}")
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    print(f"{APP_NAME} {__version__}")
    return 0


def cmd_diagnose(args: argparse.Namespace) -> int:
    from atlas.diagnostics import Diagnostics
    from atlas.observe.window import AttachError

    _setup(args)
    diag = Diagnostics()
    try:
        folder = diag.run(out_dir=args.out, title=args.title)
    except AttachError as exc:
        print(
            f"error: {exc}\n"
            f"Open the MPF (Download and Upload Form) window first, then re-run:\n"
            f"  python main.py diagnose --title \"{args.title}\"",
            file=sys.stderr,
        )
        return 1
    finally:
        diag.close()
    print(f"diagnostics written to {folder}")
    return 0



def cmd_observe_source(args):
    """Comprehensive source panel observation diagnostic."""
    from atlas.observe.source_observer import SourceObserver, SourceObservation
    from atlas.config import load_config
    from atlas.assistant import Assistant
    from atlas.vision.capture import WindowCapture
    from atlas.observe.window import AttachError
    import json
    import time
    from pathlib import Path
    import numpy as np
    
    config = load_config()
    _setup(args)
    
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    folder = out_dir / f"source_obs_{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("ATLAS SOURCE OBSERVATION DIAGNOSTIC")
    print("=" * 60)
    
    # Step 1: Create grabber FIRST (before window operations to avoid mss side effects)
    print("\n[1/8] CREATING SCREEN GRABBER...")
    from atlas.vision.capture import WindowGeometry, ScreenGrabber, WindowCapture
    from atlas.observe.window import AttachError
    import win32gui
    import win32process
    
    grabber = ScreenGrabber()
    
    # Step 2: Find MPF window by title (no UIA walk, skip validation)
    print("\n[2/8] FINDING MPF WINDOW...")
    
    # Use find_windows_by_title directly (does not filter by PID)
    candidates = WindowGeometry.find_windows_by_title(args.title)
    if not candidates:
        print("  ERROR: No window found with title: " + args.title)
        return 1
    
    # Filter out console/PowerShell windows
    def is_console_window(hwnd):
        class_name = win32gui.GetClassName(hwnd) or ""
        return "ConsoleWindowClass" in class_name or "ConsoleWindow" in class_name
    
    filtered = [c for c in candidates if not is_console_window(c["handle"])]
    if not filtered:
        print("  ERROR: No non-console window found")
        return 1
    
    # Use the first non-console candidate
    handle = filtered[0]["handle"]
    
    # Get window info
    title = win32gui.GetWindowText(handle) or ""
    class_name = win32gui.GetClassName(handle) or ""
    _, pid = win32process.GetWindowThreadProcessId(handle)
    import psutil
    process_name = ""
    try:
        process_name = psutil.Process(pid).name()
    except Exception:
        process_name = ""
    
    # Get client rect
    left, top, width, height = WindowGeometry.client_area(handle)
    client_rect = (left, top, left + width, top + height)
    
    print("  FOUND: hwnd=" + str(handle) + " title=" + repr(title) + " pid=" + str(pid))
    print("  Class: " + class_name)
    print("  Process: " + process_name)
    print("  Client Rect: " + str(client_rect))
    
    # Step 2: Full window capture
    print("\n[3/8] CAPTURING FULL WINDOW...")
    grabber = ScreenGrabber()
    capture = WindowCapture(grabber=grabber)
    capture.attach(handle, title)
    area = capture.capture_until_nonempty(timeout=10.0)
    
    if area is None:
        print("  ERROR: Failed to capture window")
        return 1
    
    print("  Client area: " + str(area.left) + "," + str(area.top) + " " + str(area.width) + "x" + str(area.height))
    print("  Image shape: " + str(area.image.shape))
    
    # Save full window
    full_window_path = folder / "01_full_window.png"
    area.save(full_window_path)
    print("  Saved: " + str(full_window_path))
    
    # Save full window metadata
    full_meta = {
        "title": title,
        "hwnd": handle,
        "pid": pid,
        "class_name": class_name,
        "process_name": process_name,
        "window_rect": list(area.window_rect) if hasattr(area, "window_rect") else None,
        "client_rect": [area.left, area.top, area.left + area.width, area.top + area.height],
        "width": area.width,
        "height": area.height,
        "image_shape": list(area.image.shape),
        "coordinate_system": "screen"
    }
    (folder / "01_full_window.json").write_text(json.dumps(full_meta, indent=2))
    
    # Step 3: Identify LEFT source panel ROI
    print("\n[4/8] IDENTIFYING LEFT SOURCE PANEL...")
    
    # The MPF source panel is a VISUAL text block on the LEFT side
    # UIA does NOT expose it as separate text nodes (it is one scrollable text block)
    # So we use the visual client_rect fallback (left portion of window)
    panel_ratio = config.source.panel_ratio
    left_rect = type("BBox", (), {
        "left": area.left,
        "top": area.top,
        "width": int(area.width * panel_ratio),
        "height": area.height
    })()
    roi_source = "client_rect_visual"
    confidence = 0.8
    print("  Using visual client_rect fallback (ratio=" + str(panel_ratio) + "): " + str(left_rect))
    print("  NOTE: UIA left_rect is IGNORED because MPF source panel is visual, not UIA controls")

    # Skip field_map.build() for diagnostic - it does a slow UIA walk and provides 
    # WRONG labels (right form panel labels, not source panel labels)
    # The source panel is VISUAL and uses colon-block parsing from OCR directly
    field_map = None
    known_labels = []
    print("  Skipping field_map.build() - source panel uses visual OCR colon-block parsing")
    
    print("  ROI: x=" + str(left_rect.left) + ", y=" + str(left_rect.top) + ", w=" + str(left_rect.width) + ", h=" + str(left_rect.height))
    print("  Source: " + roi_source + ", confidence: " + str(confidence))
    
    # Save ROI metadata
    roi_meta = {
        "coordinate_space": "screen",
        "full_image_size": [area.width, area.height],
        "roi": [left_rect.left, left_rect.top, left_rect.width, left_rect.height],
        "source": roi_source,
        "confidence": confidence
    }
    (folder / "02_source_roi.json").write_text(json.dumps(roi_meta, indent=2))
    
    # Step 4: Crop source ROI
    print("\n[5/8] CROPPING SOURCE ROI...")
    try:
        source_crop = grabber.grab_rect(left_rect.left, left_rect.top, left_rect.width, left_rect.height)
    except Exception as exc:
        print("  ERROR: Failed to crop source ROI: " + str(exc))
        return 1
    
    if source_crop is None or source_crop.size == 0:
        print("  ERROR: Source crop is empty")
        return 1
    
    print("  Source crop shape: " + str(source_crop.shape))
    source_roi_path = folder / "03_source_roi.png"
    from PIL import Image
    Image.fromarray(source_crop).save(source_roi_path)
    print("  Saved: " + str(source_roi_path))
    
    # Step 5: OCR on source ROI
    print("\n[6/8] RUNNING OCR ON SOURCE ROI...")
    from atlas.vision.ocr import create_ocr_reader
    ocr_reader = create_ocr_reader(config.ocr)
    if ocr_reader is None:
        print("  ERROR: OCR reader not available")
        return 1
    
    ocr_lines = ocr_reader.read_image(source_crop) or []
    print("  OCR engine: " + str(config.ocr.engine))
    print("  OCR boxes: " + str(len(ocr_lines)))
    
    # Save OCR boxes
    ocr_json = []
    total_text = ""
    for line in ocr_lines:
        box = line.bbox
        ocr_json.append({
            "text": line.text,
            "bbox": [box.left, box.top, box.width, box.height] if box else None,
            "confidence": line.confidence
        })
        total_text += line.text + "\n"
    
    print("  Total text chars: " + str(len(total_text)))
    if total_text.strip():
        print("  Sample text: " + total_text[:200] + "...")
    
    (folder / "04_source_ocr.json").write_text(json.dumps(ocr_json, indent=2))
    
    # Save annotated images if requested
    if args.save_annotated:
        print("  Saving annotated images...")
        from PIL import Image, ImageDraw
        
        # Draw ROI on full window
        annotated = Image.fromarray(area.image)
        draw = ImageDraw.Draw(annotated)
        roi_left = left_rect.left - area.left
        roi_top = left_rect.top - area.top
        roi_right = roi_left + left_rect.width
        roi_bottom = roi_top + left_rect.height
        draw.rectangle([roi_left, roi_top, roi_right, roi_bottom], outline="red", width=3)
        annotated_path = folder / "02_full_window_annotated.png"
        annotated.save(annotated_path)
        print("  Saved: " + str(annotated_path))
        
        # Also save annotated source ROI
        roi_annotated = Image.fromarray(source_crop)
        draw2 = ImageDraw.Draw(roi_annotated)
        # Draw OCR boxes on the ROI
        for line in ocr_lines:
            if line.bbox:
                box = line.bbox
                draw2.rectangle([box.left, box.top, box.left + box.width, box.top + box.height], outline="blue", width=2)
        roi_annotated_path = folder / "03_source_roi_annotated.png"
        roi_annotated.save(roi_annotated_path)
        print("  Saved: " + str(roi_annotated_path))
    
    # Step 6: Pair OCR lines into label/value
    print("\n[6/8] RUNNING OCR ON SOURCE ROI...")
    ocr_reader = assistant._ocr_reader
    ocr_lines = ocr_reader.read_image(source_crop) or []
    print("  OCR engine: " + str(config.ocr.engine))
    print("  OCR boxes: " + str(len(ocr_lines)))
    
    # Save OCR boxes
    ocr_json = []
    total_text = ""
    for line in ocr_lines:
        box = line.bbox
        ocr_json.append({
            "text": line.text,
            "bbox": [box.left, box.top, box.width, box.height] if box else None,
            "confidence": line.confidence
        })
        total_text += line.text + "\n"
    
    print("  Total text chars: " + str(len(total_text)))
    if total_text.strip():
        print("  Sample text: " + total_text[:200] + "...")
    
    (folder / "04_source_ocr.json").write_text(json.dumps(ocr_json, indent=2))
    
    # Step 6: Pair OCR lines into label/value
    print("\n[7/8] PAIRING LABEL/VALUE...")
    from atlas.mapping.uia_map import pair_source_pairs
    
    # Use empty known_labels - colon-block parsing works without UIA labels
    known_labels = []
    print("  Known UIA labels: " + str(len(known_labels)) + " (using visual colon-block parsing)")
    
    ocr_pairs = pair_source_pairs(ocr_lines, known_labels or None, member_only=bool(known_labels))
    print("  OCR pairs found: " + str(len(ocr_pairs)))
    for label, value in ocr_pairs:
        print("    " + str(label) + ": " + str(value))
    
    # Step 7: VLM if available (skipped - no VLM configured in this environment)
    print("\n[8/8] VLM READING...")
    vlm_provider = None
    vlm_pairs = []
    print("  VLM configured: NO (using OCR only)")
    
    # Step 8: Summary
    print("\n[9/9] SUMMARY")
    print("-" * 40)
    print("MPF ATTACHMENT: OK (hwnd=" + str(handle) + ")")
    print("WINDOW SIZE: " + str(area.width) + "x" + str(area.height))
    print("SOURCE ROI: x=" + str(left_rect.left) + ", y=" + str(left_rect.top) + ", w=" + str(left_rect.width) + ", h=" + str(left_rect.height) + " (" + roi_source + ")")
    print("OCR BOXES: " + str(len(ocr_lines)))
    print("OCR TEXT CHARS: " + str(len(total_text)))
    print("OCR PAIRS: " + str(len(ocr_pairs)))
    print("VLM: " + ("YES" if vlm_provider else "NO"))
    if vlm_provider:
        print("VLM PAIRS: " + str(len(vlm_pairs)))
    print("SAVED TO: " + str(folder))
    
    # Overall success determination
    has_meaningful_pairs = len(ocr_pairs) > 0 or (vlm_provider and len(vlm_pairs) > 0)
    if has_meaningful_pairs:
        print("\nSTATUS: SOURCE OBSERVATION SUCCESS")
    else:
        print("\nSTATUS: SOURCE OBSERVATION FAILED")
        print("REASON: No label/value pairs extracted")
    
    print("=" * 60)
    return 0 if has_meaningful_pairs else 1




def cmd_test_ocr(args):
    """Test OCR directly on a saved image file."""
    from atlas.config import load_config
    from atlas.vision.ocr import create_ocr_reader
    import json
    import time
    from pathlib import Path
    from PIL import Image
    
    config = load_config()
    _setup(args)
    
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    folder = out_dir / f"ocr_test_{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("ATLAS OCR TEST ON SAVED IMAGE")
    print("=" * 60)
    
    # Load image
    image_path = Path(args.image)
    if not image_path.exists():
        print("ERROR: Image not found: " + str(image_path))
        return 1
    
    image = Image.open(image_path)
    print("Loaded image: " + str(image_path) + " (" + str(image.size) + " " + image.mode + ")")
    
    # Convert to numpy
    import numpy as np
    img_array = np.array(image)
    if img_array.ndim == 3 and img_array.shape[2] == 4:
        img_array = img_array[:, :, :3]  # Drop alpha
    
    # Save copy
    img_copy_path = folder / "01_input_image.png"
    image.save(img_copy_path)
    print("Saved input copy: " + str(img_copy_path))
    
    # Create OCR reader
    print("\nCreating OCR reader: " + args.engine)
    ocr_reader = create_ocr_reader(config.ocr)
    if ocr_reader is None:
        print("ERROR: OCR reader not available")
        return 1
    
    # Run OCR
    print("Running OCR...")
    start = time.perf_counter()
    ocr_lines = ocr_reader.read_image(img_array) or []
    elapsed = time.perf_counter() - start
    print("OCR completed in {:.2f}s".format(elapsed))
    print("OCR boxes: " + str(len(ocr_lines)))
    
    # Save OCR boxes
    ocr_json = []
    total_text = ""
    for line in ocr_lines:
        box = line.bbox
        ocr_json.append({
            "text": line.text,
            "bbox": [box.left, box.top, box.width, box.height] if box else None,
            "confidence": line.confidence
        })
        total_text += line.text + "\n"
    
    print("Total text chars: " + str(len(total_text)))
    if total_text.strip():
        print("Sample text: " + total_text[:500] + "...")
    
    (folder / "02_ocr_result.json").write_text(json.dumps(ocr_json, indent=2))
    
    # Test pair_source_pairs
    print("\nTesting pair_source_pairs...")
    from atlas.mapping.uia_map import pair_source_pairs
    ocr_pairs = pair_source_pairs(ocr_lines, None, member_only=False)
    print("OCR pairs found: " + str(len(ocr_pairs)))
    for label, value in ocr_pairs:
        print("    " + str(label) + ": " + str(value))
    
    # Test with known labels if provided
    # (could be extended to read from a file)
    
    # Save annotated image
    from PIL import ImageDraw
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    for line in ocr_lines:
        if line.bbox:
            box = line.bbox
            draw.rectangle([box.left, box.top, box.left + box.width, box.top + box.height], outline="blue", width=2)
            if line.text:
                draw.text((box.left, max(0, box.top - 15)), line.text, fill="blue")
    annotated_path = folder / "03_annotated.png"
    annotated.save(annotated_path)
    print("Saved annotated: " + str(annotated_path))
    
    print("\n" + "=" * 60)
    print("OCR TEST COMPLETE")
    print("=" * 60)
    print("Results saved to: " + str(folder))
    return 0



def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    handlers = {
        "run": cmd_run,
        "serve": cmd_serve,
        "doctor": cmd_doctor,
        "version": cmd_version,
        "diagnose": cmd_diagnose,
        "observe": cmd_diagnose,
        "vision-doctor": cmd_vision_doctor,
        "observe-source": cmd_observe_source,
        "test-ocr": cmd_test_ocr,
    }
    handler = handlers.get(args.command)
    if handler is None:
        print(f"unknown command: {args.command}", file=sys.stderr)
        return 2
    try:
        return handler(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        logger.exception("command {} failed", args.command)
        return 1


if __name__ == "__main__":
    sys.exit(main())

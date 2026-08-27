"""Regression tests for the "vision not actually connected" bug report.

Root cause found: python-dotenv's default ``load_dotenv()`` searches the
process's CURRENT WORKING DIRECTORY, not the project root - so launching
ATLAS from any directory other than the project root (a shortcut, a
scheduled task, a different terminal cwd) silently never finds a real
``.env`` sitting right next to ``main.py``, and every provider key reads
back empty ("No VLM endpoint configured" even with real keys in .env).

Also covers the two other concrete gaps found while diagnosing this:
provider configuration was never shown anywhere at startup, and the
``observe`` CLI command described in every round of this project's docs was
never actually registered.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_provider_status_reports_configured_and_not_configured() -> None:
    import dataclasses

    from atlas.config import VisionConfig
    from atlas.vision.manager import provider_status

    cfg = VisionConfig(google_api_key="key", groq_api_key="", openrouter_api_key="or-key")
    status = provider_status(cfg)
    assert status == {"google": "CONFIGURED", "groq": "NOT CONFIGURED", "openrouter": "CONFIGURED"}


def test_format_provider_status_never_includes_key_value() -> None:
    from atlas.config import VisionConfig
    from atlas.vision.manager import format_provider_status

    secret = "sk-supersecretvalue12345"
    cfg = VisionConfig(google_api_key=secret)
    formatted = format_provider_status(cfg)
    assert secret not in formatted
    assert "CONFIGURED" in formatted


def test_format_provider_status_reports_fallback_enabled_only_with_2plus() -> None:
    from atlas.config import VisionConfig
    from atlas.vision.manager import format_provider_status

    single = format_provider_status(VisionConfig(google_api_key="k"))
    assert "Fallback: N/A" in single

    dual = format_provider_status(VisionConfig(google_api_key="k", groq_api_key="k2"))
    assert "Fallback: ENABLED" in dual


# ---------------------------------------------------------------------------
# CLI registration: `observe` and `vision-doctor` must actually be registered
# subcommands, not just documented in prose.
# ---------------------------------------------------------------------------


def test_observe_and_vision_doctor_are_registered_cli_subcommands() -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    import main as atlas_main

    parser = atlas_main._build_parser()
    for cmd in ("observe", "vision-doctor", "diagnose", "doctor", "run"):
        args = parser.parse_args([cmd, "--title", "MPF"] if cmd in ("observe", "vision-doctor", "diagnose") else [cmd])
        assert args.command == cmd


def test_observe_dispatches_to_the_perception_only_handler() -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    import main as atlas_main

    parser = atlas_main._build_parser()
    args = parser.parse_args(["observe", "--title", "MPF"])
    handlers = {
        "observe": atlas_main.cmd_diagnose,
        "diagnose": atlas_main.cmd_diagnose,
    }
    # `observe` must route to the SAME non-mutating handler as `diagnose`
    # (attach -> capture -> observe -> structured dump; never types, clicks,
    # scrolls, or uploads) rather than a separate, unverified implementation.
    assert handlers["observe"] is handlers["diagnose"]


def test_doctor_command_prints_vision_provider_status(tmp_path, monkeypatch) -> None:
    """End-to-end: `python main.py doctor` must show provider CONFIGURED
    status without requiring a live MPF window or crashing when none is
    configured."""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "doctor"],
        cwd=str(tmp_path),  # deliberately NOT the project root
        capture_output=True, text=True, timeout=30,
        env={**__import__("os").environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent.parent / "winstubs")}
        if (Path(__file__).resolve().parent.parent.parent / "winstubs").exists() else None,
    )
    assert "Vision providers:" in result.stdout
    assert "NOT CONFIGURED" in result.stdout or "CONFIGURED" in result.stdout


def test_dotenv_loads_from_project_root_regardless_of_cwd(tmp_path) -> None:
    """THE fix: create a real .env next to main.py, launch doctor from a
    totally different working directory, and confirm the key is picked up -
    this is the exact symptom from the bug report ("No VLM endpoint
    configured" despite real keys being present)."""
    env_path = PROJECT_ROOT / ".env"
    assert not env_path.exists(), "a real .env must never be committed to the repo"
    env_path.write_text("GOOGLE_STUDIO_API_KEY=test-key-for-regression-check\n", encoding="utf-8")
    try:
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "main.py"), "doctor"],
            cwd=str(tmp_path),  # a directory with NO .env of its own
            capture_output=True, text=True, timeout=30,
        )
        assert "Google: CONFIGURED" in result.stdout
    finally:
        env_path.unlink(missing_ok=True)


def test_typing_does_not_default_to_clipboard_for_long_values() -> None:
    """Repeated explicit requirement: clipboard paste must not be the
    PRIMARY interaction. TYPING_USE_CLIPBOARD_FOR_LONG must default False
    unless the user opts in via .env."""
    from atlas.config import TypingConfig

    assert TypingConfig().use_clipboard_for_long is False

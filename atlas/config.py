"""ATLAS AI - typed configuration.

All settings load from environment variables (a `.env` file is optional) with
sensible defaults. Values are evaluated at instantiation (via ``default_factory``)
so environment overrides take effect at ``load_config()`` time - not just at
import time. Directories are created eagerly so config failures surface at
startup, not mid-run.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# python-dotenv's load_dotenv() with no arguments searches from the current
# WORKING DIRECTORY, not from this file's location - if ATLAS is launched
# from a shortcut, scheduled task, or any working directory other than the
# project root, a real .env sitting right next to main.py is silently never
# found and every provider key reads back empty (symptom: "No VLM endpoint
# configured" even though .env has real keys). Resolve the project root
# explicitly (this file is atlas/config.py, so its parent's parent is the
# root) and load from there first; fall back to the default search so a
# non-standard layout / .env elsewhere on the path still works too.
_PROJECT_ROOT_ENV = Path(__file__).resolve().parent.parent / ".env"
if _PROJECT_ROOT_ENV.exists():
    load_dotenv(dotenv_path=_PROJECT_ROOT_ENV)
else:
    load_dotenv()


class ConfigError(RuntimeError):
    """Raised when configuration is invalid."""


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"{name} must be an integer, got {os.getenv(name)!r}") from exc


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"{name} must be a number, got {os.getenv(name)!r}") from exc


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _clamp(name: str, value: float, low: float, high: float) -> float:
    if not (low <= value <= high):
        raise ConfigError(f"{name} must be between {low} and {high}, got {value}")
    return value


# Field factories - read the environment when the dataclass is instantiated.
def _f(name: str, default: str) -> Any:
    return lambda: _env(name, default)


def _fi(name: str, default: int) -> Any:
    return lambda: _env_int(name, default)


def _ff(name: str, default: float) -> Any:
    return lambda: _env_float(name, default)


def _fb(name: str, default: bool) -> Any:
    return lambda: _env_bool(name, default)


def _fclamp(name: str, default: float, low: float, high: float) -> Any:
    return lambda: _clamp(name, _env_float(name, default), low, high)


def _env_int_list(name: str, default: list[int]) -> list[int]:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return list(default)
    out: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError as exc:
            raise ConfigError(f"{name} must be a comma-separated list of integers, got {raw!r}") from exc
    return out


def _fi_list(name: str, default: list[int]) -> Any:
    return lambda: _env_int_list(name, default)


@dataclass(frozen=True)
class VisionConfig:
    """Vision Language Model (VLM) configuration - the primary channel."""

    provider: str = field(default_factory=_f("VISION_PROVIDER", "auto"))
    model: str = field(default_factory=_f("VISION_MODEL", ""))
    api_key: str = field(default_factory=_f("VISION_API_KEY", ""))
    api_base: str = field(default_factory=_f("VISION_API_BASE", ""))
    timeout: float = field(default_factory=_fclamp("VISION_TIMEOUT", 60.0, 1.0, 600.0))
    confidence_threshold: float = field(
        default_factory=_fclamp("VISION_CONFIDENCE_THRESHOLD", 0.4, 0.0, 1.0)
    )

    # --- Multi-provider fast-fallback (VisionProviderManager) ---
    # Named provider API keys/models. A provider is only used if its key is
    # non-empty; the manager silently skips unconfigured providers rather
    # than erroring, per "the system must skip providers whose API key is
    # missing."
    groq_api_key: str = field(default_factory=_f("GROQ_API_KEY", ""))
    groq_model: str = field(default_factory=_f("GROQ_VISION_MODEL", "llama-3.2-11b-vision-preview"))
    google_api_key: str = field(default_factory=_f("GOOGLE_STUDIO_API_KEY", ""))
    google_model: str = field(default_factory=_f("GOOGLE_VISION_MODEL", "gemini-1.5-flash"))
    openrouter_api_key: str = field(default_factory=_f("OPENROUTER_API_KEY", ""))
    openrouter_model: str = field(default_factory=_f("OPENROUTER_VISION_MODEL", "openrouter/free"))
    provider_order: str = field(default_factory=_f("VISION_PROVIDER_ORDER", "google,groq,openrouter"))
    selection_mode: str = field(default_factory=_f("VISION_SELECTION_MODE", "priority"))
    max_retries: int = field(default_factory=_fi("VISION_MAX_RETRIES", 1))
    provider_cooldown_seconds: float = field(
        default_factory=_ff("VISION_PROVIDER_COOLDOWN_SECONDS", 60.0)
    )


@dataclass(frozen=True)
class SourceConfig:
    """LEFT source-panel visual observer configuration.

    The source panel is treated as an IMAGE: cropped, OCR'd and sent to the
    VLM, so records are read even when UIA exposes no label/value rows. All
    values are read from the environment at instantiation time.
    """

    #: Fraction of the client width occupied by the LEFT panel. Used only when
    #: the UIA field map has no ``left_rect`` to crop by.
    panel_ratio: float = field(default_factory=_fclamp("SOURCE_PANEL_RATIO", 0.5, 0.1, 0.9))
    #: Max seconds one source observation (OCR + VLM) may take.
    observe_timeout: float = field(default_factory=_ff("SOURCE_OBSERVE_TIMEOUT", 10.0))
    #: Retries on OCR/VLM failure before giving up.
    retries: int = field(default_factory=_fi("SOURCE_OBSERVE_RETRIES", 2))
    #: Minimum confidence to accept a VLM label/value pair.
    vlm_confidence: float = field(default_factory=_fclamp("SOURCE_VLM_CONFIDENCE", 0.5, 0.0, 1.0))
    #: Skip re-observation when the cropped source panel is unchanged (phash).
    phash_cache: bool = field(default_factory=_fb("SOURCE_PHASH_CACHE", True))
    #: Minimum valued pairs for a partial record to count as a valid record.
    min_valued_pairs: int = field(default_factory=_fi("SOURCE_MIN_VALUED_PAIRS", 2))


@dataclass(frozen=True)
class ReasoningConfig:
    """LLM configuration for planning/decisioning."""

    provider: str = field(default_factory=_f("REASONING_PROVIDER", "auto"))
    model: str = field(default_factory=_f("REASONING_MODEL", ""))
    api_key: str = field(default_factory=_f("REASONING_API_KEY", ""))
    api_base: str = field(default_factory=_f("REASONING_API_BASE", ""))
    timeout: float = field(default_factory=_fclamp("REASONING_TIMEOUT", 60.0, 1.0, 600.0))
    confidence_threshold: float = field(
        default_factory=_fclamp("REASONING_CONFIDENCE_THRESHOLD", 0.5, 0.0, 1.0)
    )


@dataclass(frozen=True)
class OcrConfig:
    """OCR fallback configuration (explicit AI request only)."""

    engine: str = field(default_factory=_f("OCR_ENGINE", "paddle"))
    lang: str = field(default_factory=_f("OCR_LANG", "en"))
    confidence_threshold: float = field(
        default_factory=_fclamp("OCR_CONFIDENCE_THRESHOLD", 0.4, 0.0, 1.0)
    )
    preprocess: bool = field(default_factory=_fb("OCR_PREPROCESS", True))


@dataclass(frozen=True)
class MouseConfig:
    """Human-like mouse behaviour."""

    bezier_steps: int = field(default_factory=_fi("MOUSE_BEZIER_STEPS", 35))
    speed: float = field(default_factory=_ff("MOUSE_SPEED", 0.35))
    min_delay: float = field(default_factory=_ff("MOUSE_MIN_DELAY", 0.05))
    max_delay: float = field(default_factory=_ff("MOUSE_MAX_DELAY", 0.25))
    pause_before_click: float = field(default_factory=_ff("MOUSE_PAUSE_BEFORE_CLICK", 0.08))
    pause_after_click: float = field(default_factory=_ff("MOUSE_PAUSE_AFTER_CLICK", 0.10))
    jitter_px: int = field(default_factory=_fi("MOUSE_JITTER_PX", 3))
    double_click_interval: float = field(default_factory=_ff("MOUSE_DOUBLE_CLICK_INTERVAL", 0.30))


@dataclass(frozen=True)
class TypingConfig:
    """Human-like typing behaviour."""

    min_delay: float = field(default_factory=_ff("TYPING_MIN_DELAY", 0.05))
    max_delay: float = field(default_factory=_ff("TYPING_MAX_DELAY", 0.25))
    pause_after: float = field(default_factory=_ff("TYPING_PAUSE_AFTER", 0.15))
    #: Write text through UIA ``ValuePattern.SetValue`` (bulk injection) instead
    #: of genuine per-character keyboard typing. The MPF app REJECTS programmatic
    #: value injection with an explicit "Auto-fill or pasted text is not allowed.
    #: Please type manually." popup, so this must be False for MPF - every field
    #: is typed one character at a time via the keyboard. Defaults to False (the
    #: project's iron rule: real human keyboard typing is the interaction).
    use_value_pattern: bool = field(default_factory=_fb("TYPING_USE_VALUE_PATTERN", False))
    # Default changed to False: repeated explicit requirement across every
    # round of this project is that clipboard paste must NOT be the primary
    # interaction - real human keyboard typing is. Clipboard remains
    # available as an opt-in (set TYPING_USE_CLIPBOARD_FOR_LONG=true) for
    # genuinely very long strings where character-by-character typing would
    # be needlessly slow, but it is no longer silently used by default.
    use_clipboard_for_long: bool = field(default_factory=_fb("TYPING_USE_CLIPBOARD_FOR_LONG", False))
    clipboard_min_length: int = field(default_factory=_fi("TYPING_CLIPBOARD_MIN_LENGTH", 25))
    simulate_typos: bool = field(default_factory=_fb("TYPING_SIMULATE_TYPOS", False))
    typo_rate: float = field(default_factory=_fclamp("TYPING_TYPO_RATE", 0.02, 0.0, 1.0))
    dropdown_wait: float = field(default_factory=_ff("DROPDOWN_ANIMATION_WAIT", 0.35))


@dataclass(frozen=True)
class ObserveConfig:
    """Observation loop configuration."""

    poll_interval: float = field(
        default_factory=_fclamp("OBSERVE_POLL_INTERVAL", 0.8, 0.05, 60.0)
    )
    capture_format: str = field(default_factory=_f("OBSERVE_CAPTURE_FORMAT", "png"))
    screenshot_dir: Path = field(default_factory=lambda: Path(_env("OBSERVE_SCREENSHOT_DIR", "screenshots")))


@dataclass(frozen=True)
class WorkflowConfig:
    """Agent workflow / loop configuration."""

    verify_after_action: bool = field(default_factory=_fb("WORKFLOW_VERIFY_AFTER_ACTION", True))
    max_retries_per_action: int = field(default_factory=_fi("WORKFLOW_MAX_RETRIES_PER_ACTION", 3))
    retry_delay: float = field(default_factory=_ff("WORKFLOW_RETRY_DELAY", 0.8))
    next_record_timeout: float = field(default_factory=_ff("WORKFLOW_NEXT_RECORD_TIMEOUT", 120.0))
    next_record_poll: float = field(default_factory=_ff("WORKFLOW_NEXT_RECORD_POLL", 1.5))
    max_records: int = field(default_factory=_fi("WORKFLOW_MAX_RECORDS", 0))
    #: How many records a normal (non single-form) run processes before
    #: stopping cleanly. 0 = unlimited (drive until the user stops it). This
    #: is the "exactly ONE record, then clean stop" knob.
    records_per_run: int = field(default_factory=_fi("WORKFLOW_RECORDS_PER_RUN", 1))
    #: SINGLE-FORM TEST MODE: process exactly ONE complete form/record, then
    #: terminate ATLAS cleanly (never advances to record 2, never restarts).
    #: When enabled, max_records is forced to 1.
    single_form_mode: bool = field(default_factory=_fb("WORKFLOW_SINGLE_FORM_MODE", False))
    #: Whether single-form mode may click "Upload Details". Default FALSE =
    #: the fill+verify test mode: NEVER click the upload button - leave the
    #: completed form on screen and terminate. Set TRUE only for the run that
    #: must also submit the record.
    single_form_upload: bool = field(default_factory=_fb("WORKFLOW_SINGLE_FORM_UPLOAD", False))
    log_screenshots: bool = field(default_factory=_fb("WORKFLOW_LOG_SCREENSHOTS", True))
    scan_reveal_fields: bool = field(default_factory=_fb("WORKFLOW_SCAN_REVEAL_FIELDS", True))
    # Field-driven (performance) path: fill from the full UIA field map in one
    # ordered queue, scroll RIGHT-panel-only with UIA-only position refresh,
    # and reserve full VLM observes for the post-submit check.
    # NOTE (reliability fix): field_driven now defaults to True. This is the
    # path with the hard completion gate (queue.blockers()), the two-pass
    # completeness retry, and a submit that is blocked whenever any
    # source-backed field is not VERIFIED/ALREADY_CORRECT. The legacy
    # viewport path (_run_record) has no such gate - it built its action plan
    # once from a possibly-partial mapping and always executed the submit
    # action, which is the root cause of records completing with many fields
    # silently missing. Set WORKFLOW_FIELD_DRIVEN=0 to opt back into the
    # legacy path (not recommended).
    field_driven: bool = field(default_factory=_fb("WORKFLOW_FIELD_DRIVEN", True))
    field_driven_scroll: bool = field(default_factory=_fb("WORKFLOW_FIELD_DRIVEN_SCROLL", True))
    field_timeout: float = field(default_factory=_ff("WORKFLOW_FIELD_TIMEOUT", 20.0))
    field_scroll_attempts: int = field(default_factory=_fi("WORKFLOW_FIELD_SCROLL_ATTEMPTS", 6))
    field_retries: int = field(default_factory=_fi("WORKFLOW_FIELD_RETRIES", 1))
    #: Skip a write entirely when the field already holds the target value
    #: (no-op ALREADY_CORRECT detection). Costs one pre-write read per field.
    noop_detect: bool = field(default_factory=_fb("WORKFLOW_NOOP_DETECT", True))
    #: Minimum share of right-form fields that must be backed by a source value
    #: before the record is filled. Below this the loop enters MAPPING_RECOVERY
    #: and re-reads the source instead of blindly filling (bug #5: never
    #: interpret a missing OCR value as "no value to enter").
    mapping_coverage_threshold: float = field(
        default_factory=_ff("WORKFLOW_MAPPING_COVERAGE_THRESHOLD", 0.95)
    )
    #: Per-record attempts (including success) to get source coverage back above
    #: the threshold before the record is abandoned rather than half-filled.
    mapping_recovery_max_attempts: int = field(
        default_factory=_fi("WORKFLOW_MAPPING_RECOVERY_MAX_ATTEMPTS", 2)
    )
    #: Optional path to a persistent Excel workbook for per-record results.
    #: When set, every submitted record is appended as a row. Columns are
    #: Record Number, App No, MBI Code, Full Name + every source field, plus
    #: status, timestamp, verification status and error/retry count.
    excel_path: str = field(default_factory=_f("WORKFLOW_EXCEL_PATH", ""))


@dataclass(frozen=True)
class OverlayConfig:
    """Floating assistant overlay configuration."""

    enabled: bool = field(default_factory=_fb("OVERLAY_ENABLED", True))
    animation_fps: int = field(default_factory=_fi("OVERLAY_ANIMATION_FPS", 30))
    command_port: int = field(default_factory=_fi("OVERLAY_COMMAND_PORT", 19765))


@dataclass(frozen=True)
class ControllerConfig:
    """Controller (command server) configuration."""

    command_port: int = field(default_factory=_fi("CONTROLLER_COMMAND_PORT", 19768))


@dataclass(frozen=True)
class MemoryConfig:
    """Persistent memory configuration."""

    db_path: str = field(default_factory=_f("MEMORY_DB_PATH", "memory.db"))
    alias_learning: bool = field(default_factory=_fb("MEMORY_ALIAS_LEARNING", True))


@dataclass(frozen=True)
class LogConfig:
    """Logging configuration."""

    level: str = field(default_factory=lambda: _env("LOG_LEVEL", "DEBUG").upper())
    folder: Path = field(default_factory=lambda: Path(_env("LOG_FOLDER", "logs")))


@dataclass(frozen=True)
class PluginsConfig:
    """User plugin loading configuration."""

    enabled: bool = field(default_factory=_fb("PLUGINS_ENABLED", True))
    directory: Path = field(default_factory=lambda: Path(_env("PLUGINS_DIR", "plugins")))


@dataclass(frozen=True)
class UniversalConfig:
    """Universal attach-first / smart computer-use agent configuration.

    The defaults encode the iron rule: an EXISTING target is always preferred
    over a fresh launch, the agent never launches a browser automatically, and
    it only escalates to OCR/vision when DOM/UIA are genuinely unavailable.
    """

    #: Operation mode: "AUTO" (smart detection) / "ATTACH" (user picks) /
    #: "WEB" (force web) / "DESKTOP" (force desktop).
    target_mode: str = field(default_factory=_f("TARGET_MODE", "AUTO"))
    #: Permit a fresh launch ONLY when no target exists anywhere.
    auto_launch_target: bool = field(default_factory=_fb("AUTO_LAUNCH_TARGET", False))
    prefer_existing_target: bool = field(default_factory=_fb("PREFER_EXISTING_TARGET", True))
    allow_browser_launch: bool = field(default_factory=_fb("ALLOW_BROWSER_LAUNCH", False))
    max_recovery_attempts: int = field(default_factory=_fi("MAX_RECOVERY_ATTEMPTS", 3))
    field_timeout: float = field(default_factory=_ff("FIELD_TIMEOUT", 5.0))
    target_discovery_timeout: float = field(default_factory=_ff("TARGET_DISCOVERY_TIMEOUT", 5.0))
    ocr_fallback: bool = field(default_factory=_fb("OCR_FALLBACK", True))
    vision_fallback: bool = field(default_factory=_fb("VISION_FALLBACK", True))
    smart_wait: bool = field(default_factory=_fb("SMART_WAIT", True))
    learn_methods: bool = field(default_factory=_fb("LEARN_METHODS", True))
    strict_focus_guard: bool = field(default_factory=_fb("STRICT_FOCUS_GUARD", True))
    #: CDP ports probed when looking for an already-running Chromium/Electron.
    cdp_ports: list[int] = field(default_factory=_fi_list("CDP_PORTS", [9222, 9229, 9230]))


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""

    debug: bool = field(default_factory=_fb("DEBUG_MODE", False))
    vision: VisionConfig = field(default_factory=VisionConfig)
    source: SourceConfig = field(default_factory=SourceConfig)
    reasoning: ReasoningConfig = field(default_factory=ReasoningConfig)
    ocr: OcrConfig = field(default_factory=OcrConfig)
    mouse: MouseConfig = field(default_factory=MouseConfig)
    typing: TypingConfig = field(default_factory=TypingConfig)
    observe: ObserveConfig = field(default_factory=ObserveConfig)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    controller: ControllerConfig = field(default_factory=ControllerConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    log: LogConfig = field(default_factory=LogConfig)
    plugins: PluginsConfig = field(default_factory=PluginsConfig)
    universal: UniversalConfig = field(default_factory=UniversalConfig)

    def __post_init__(self) -> None:
        self.ensure_directories()

    def ensure_directories(self) -> None:
        """Create runtime directories without mutating the frozen object."""
        for path in (self.observe.screenshot_dir, self.log.folder):
            path.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "debug": self.debug,
            "vision": _asdict(self.vision),
            "source": _asdict(self.source),
            "reasoning": _asdict(self.reasoning),
            "ocr": _asdict(self.ocr),
            "mouse": _asdict(self.mouse),
            "typing": _asdict(self.typing),
            "observe": _asdict(self.observe),
            "workflow": _asdict(self.workflow),
            "overlay": _asdict(self.overlay),
            "controller": _asdict(self.controller),
            "memory": _asdict(self.memory),
            "log": _asdict(self.log),
            "plugins": _asdict(self.plugins),
            "universal": _asdict(self.universal),
        }


def _asdict(obj: Any) -> dict[str, Any]:
    return {k: str(v) if isinstance(v, Path) else v for k, v in obj.__dict__.items()}


def load_config() -> AppConfig:
    """Build the application configuration."""
    return AppConfig()

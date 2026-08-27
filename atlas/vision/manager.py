"""``VisionProviderManager`` - fast, health-aware fallback across multiple
Vision API providers (Google AI Studio/Gemini, Groq, OpenRouter).

Reuses the existing ``OpenAIVisionProvider`` (Groq and OpenRouter are both
OpenAI-compatible chat-completions endpoints) and ``GeminiVisionProvider``
(native Google generateContent API) rather than duplicating HTTP/parsing
logic - this manager is purely an ORDERING + HEALTH + FAILOVER layer on top
of providers that already exist.

The rest of ATLAS never sees which concrete provider answered a request:
this class implements the same ``VisionProvider`` interface
(``describe()`` / ``read_text()``), so it drops in anywhere a single
provider was used before (``SceneAnalyzer(provider=...)``).

Failure classification -> behaviour:

- TIMEOUT / NETWORK_ERROR / SERVER_ERROR / RATE_LIMIT: transient - failover
  immediately, provider goes into a short cooldown so it isn't retried on
  every single request (``VISION_PROVIDER_COOLDOWN_SECONDS``).
- AUTH_ERROR / MODEL_UNAVAILABLE: not transient - provider is marked
  unavailable for the rest of the process (config problem, not a blip).
- INVALID_JSON / INVALID_RESPONSE / EMPTY_RESPONSE: the call succeeded but
  the content was unusable - failover immediately, short cooldown.

If every configured provider fails, the manager raises the LAST exception
(never a fabricated success) - callers already handle a raising
``describe()`` by falling back to cache/OCR/deterministic paths (see
``AgentLoop._observe`` and ``SceneAnalyzer.analyze``'s documented contract).
"""

from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from atlas.config import VisionConfig
from atlas.core.logging import logger
from atlas.vision.models import OcrText, SceneDescription
from atlas.vision.providers import GeminiVisionProvider, OpenAIVisionProvider, VisionProvider

# ---------------------------------------------------------------------------
# Failure classification
# ---------------------------------------------------------------------------

TRANSIENT_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
NON_TRANSIENT_STATUS_CODES = {401, 403, 404}


def classify_failure(exc: Exception) -> str:
    """Map an exception to a coarse failure-type label used for provider
    health decisions. Never raises."""
    try:
        import requests

        if isinstance(exc, requests.exceptions.Timeout):
            return "TIMEOUT"
        if isinstance(exc, requests.exceptions.ConnectionError):
            return "NETWORK_ERROR"
        if isinstance(exc, requests.exceptions.HTTPError):
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status == 429:
                return "RATE_LIMIT"
            if status in NON_TRANSIENT_STATUS_CODES:
                return "AUTH_ERROR"
            if status is not None and status >= 500:
                return "SERVER_ERROR"
            return "SERVER_ERROR"
    except ImportError:
        pass
    if isinstance(exc, TimeoutError):
        return "TIMEOUT"
    if isinstance(exc, (ConnectionError, OSError)):
        return "NETWORK_ERROR"
    if isinstance(exc, ValueError):
        return "INVALID_RESPONSE"
    return "NETWORK_ERROR"


#: Failure types that permanently disable a provider for this process
#: (a config problem, not a transient blip - retrying won't help).
NON_TRANSIENT_FAILURE_TYPES = {"AUTH_ERROR", "MODEL_UNAVAILABLE"}


@dataclass
class ProviderHealth:
    name: str
    status: str = "UNKNOWN"  # HEALTHY | COOLDOWN | UNAVAILABLE | UNKNOWN
    last_success: float | None = None
    last_failure: float | None = None
    failure_count: int = 0
    success_count: int = 0
    cooldown_until: float = 0.0
    latency_ms: float | None = None
    last_error_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class _Slot:
    name: str
    provider: VisionProvider
    health: ProviderHealth = field(init=False)

    def __post_init__(self) -> None:
        self.health = ProviderHealth(name=self.name)


def provider_status(config: VisionConfig) -> dict[str, str]:
    """CONFIGURED/NOT CONFIGURED per named provider, without constructing any
    provider or ever touching the actual key value (never printed/logged) -
    used by ``python main.py doctor`` and ``vision-doctor`` for the loud
    startup visibility this project's runtime evidence showed was missing.
    """
    return {
        "google": "CONFIGURED" if config.google_api_key else "NOT CONFIGURED",
        "groq": "CONFIGURED" if config.groq_api_key else "NOT CONFIGURED",
        "openrouter": "CONFIGURED" if config.openrouter_api_key else "NOT CONFIGURED",
    }


def format_provider_status(config: VisionConfig) -> str:
    status = provider_status(config)
    order = [p.strip() for p in (config.provider_order or "").split(",") if p.strip()]
    lines = ["Vision providers:"]
    for name, state in status.items():
        lines.append(f"  {name.capitalize()}: {state}")
    lines.append("")
    lines.append("Provider order:")
    lines.append("  " + " -> ".join(p.capitalize() for p in order) if order else "  (none configured)")
    lines.append("")
    n_configured = sum(1 for v in status.values() if v == "CONFIGURED")
    lines.append(f"Vision: {'ENABLED' if n_configured else 'DISABLED (no provider configured)'}")
    lines.append(f"Fallback: {'ENABLED' if n_configured >= 2 else 'N/A (single or no provider)'}")
    return "\n".join(lines)


class VisionProviderManager(VisionProvider):
    """Tries configured providers in priority order (with success-stickiness
    and cooldown-aware skipping) until one succeeds.
    """

    name = "multi"

    #: The manager only ever wraps real VLM providers (OpenAI-compatible /
    #: Gemini), so it is always a VLM channel for the source observer.
    is_vlm = True

    def __init__(self, config: VisionConfig, ocr_reader: Any | None = None) -> None:
        self._config = config
        self._cooldown_seconds = max(0.0, config.provider_cooldown_seconds)
        self._slots: dict[str, _Slot] = {}
        self._order: list[str] = []
        self._sticky: str | None = None
        self._build_slots(config, ocr_reader)

    # -- construction ------------------------------------------------

    def _build_slots(self, config: VisionConfig, ocr_reader: Any | None) -> None:
        order = [p.strip().lower() for p in (config.provider_order or "").split(",") if p.strip()]
        if not order:
            order = ["google", "groq", "openrouter"]

        def add(name: str, provider: VisionProvider | None) -> None:
            if provider is None:
                return
            self._slots[name] = _Slot(name=name, provider=provider)

        if config.google_api_key:
            add("google", GeminiVisionProvider(
                dataclasses.replace(config, api_key=config.google_api_key, model=config.google_model)
            ))
        if config.groq_api_key:
            add("groq", OpenAIVisionProvider(dataclasses.replace(
                config, api_key=config.groq_api_key, model=config.groq_model,
                api_base=config.api_base or "https://api.groq.com/openai/v1",
            )))
        if config.openrouter_api_key:
            add("openrouter", OpenAIVisionProvider(dataclasses.replace(
                config, api_key=config.openrouter_api_key, model=config.openrouter_model,
                api_base="https://openrouter.ai/api/v1",
            )))

        self._order = [name for name in order if name in self._slots]
        # Any configured provider not mentioned in VISION_PROVIDER_ORDER still
        # gets used, just after the explicitly ordered ones.
        self._order += [name for name in self._slots if name not in self._order]

        configured = len(self._slots)
        if configured == 0:
            logger.info("No Vision API configured (Google/Groq/OpenRouter) - using OCR/mock fallback.")
        else:
            logger.info(
                "{} Vision provider(s) configured: {}",
                configured, ", ".join(f"{n}=CONFIGURED" for n in self._slots),
            )

    @property
    def configured_providers(self) -> list[str]:
        return list(self._slots)

    def health(self, name: str) -> ProviderHealth | None:
        slot = self._slots.get(name)
        return slot.health if slot else None

    # -- ordering ------------------------------------------------------

    def _candidate_order(self) -> list[str]:
        order = list(self._order)
        if self._sticky and self._sticky in order:
            order.remove(self._sticky)
            order.insert(0, self._sticky)
        return order

    def _is_available(self, name: str) -> bool:
        slot = self._slots[name]
        if slot.health.status == "UNAVAILABLE":
            return False
        if slot.health.status == "COOLDOWN" and time.monotonic() < slot.health.cooldown_until:
            return False
        return True

    def _record_success(self, name: str, latency_ms: float) -> None:
        h = self._slots[name].health
        h.status = "HEALTHY"
        h.last_success = time.time()
        h.success_count += 1
        h.failure_count = 0
        h.latency_ms = latency_ms
        h.last_error_type = None
        self._sticky = name

    def _record_failure(self, name: str, exc: Exception) -> str:
        h = self._slots[name].health
        failure_type = classify_failure(exc)
        h.last_failure = time.time()
        h.failure_count += 1
        h.last_error_type = failure_type
        if failure_type in NON_TRANSIENT_FAILURE_TYPES:
            h.status = "UNAVAILABLE"
        else:
            h.status = "COOLDOWN"
            h.cooldown_until = time.monotonic() + self._cooldown_seconds
        if self._sticky == name:
            self._sticky = None
        return failure_type

    # -- VisionProvider interface --------------------------------------

    def describe(self, image: np.ndarray, window_title: str = "", url: str | None = None) -> SceneDescription:
        last_exc: Exception | None = None
        tried: list[str] = []
        for name in self._candidate_order():
            if not self._is_available(name):
                continue
            tried.append(name)
            slot = self._slots[name]
            start = time.perf_counter()
            try:
                scene = slot.provider.describe(image, window_title=window_title, url=url)
            except Exception as exc:  # noqa: BLE001 - deliberately broad, classified below
                failure_type = self._record_failure(name, exc)
                logger.warning("vision provider {} failed ({}): {}", name, failure_type, exc)
                last_exc = exc
                continue
            latency_ms = (time.perf_counter() - start) * 1000.0
            self._record_success(name, latency_ms)
            scene.provider = name
            return scene
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(
            f"No Vision provider available (configured: {list(self._slots)}, tried: {tried})"
        )

    def read_text(self, image: np.ndarray) -> list[OcrText]:
        for name in self._candidate_order():
            if not self._is_available(name):
                continue
            try:
                return self._slots[name].provider.read_text(image)
            except Exception as exc:
                self._record_failure(name, exc)
                continue
        return []

    def read_source_pairs(
        self,
        image: np.ndarray,
        known_labels: list[str] | None = None,
    ) -> list[tuple[str, str, float]]:
        """Forward a source-panel read to the first healthy configured provider."""
        for name in self._candidate_order():
            if not self._is_available(name):
                continue
            try:
                return self._slots[name].provider.read_source_pairs(image, known_labels=known_labels)
            except Exception as exc:
                self._record_failure(name, exc)
                continue
        return []

    def close(self) -> None:
        for slot in self._slots.values():
            close = getattr(slot.provider, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

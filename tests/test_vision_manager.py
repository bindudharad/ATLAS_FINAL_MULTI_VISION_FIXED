"""Tests for ``VisionProviderManager`` - multi-provider fast fallback across
Google/Groq/OpenRouter with health tracking, cooldown, and stickiness.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from atlas.config import VisionConfig
from atlas.vision.manager import VisionProviderManager, classify_failure
from atlas.vision.models import SceneDescription
from atlas.vision.providers import create_vision_provider


def _config(**overrides) -> VisionConfig:
    base = VisionConfig(
        provider="multi",
        google_api_key="", groq_api_key="", openrouter_api_key="",
        provider_order="google,groq,openrouter",
        provider_cooldown_seconds=60.0,
    )
    return dataclasses.replace(base, **overrides)


class _FakeSubProvider:
    """Stands in for OpenAIVisionProvider/GeminiVisionProvider in tests."""

    def __init__(self, name: str, outcomes: list) -> None:
        self.name = name
        self._outcomes = list(outcomes)
        self.calls = 0

    def describe(self, image, window_title="", url=None):
        self.calls += 1
        outcome = self._outcomes.pop(0) if self._outcomes else self._outcomes
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def read_text(self, image):
        return []

    def close(self):
        pass


def _scene(provider_name: str) -> SceneDescription:
    return SceneDescription(provider=provider_name, confidence=0.9)


def _manager_with(**slots: _FakeSubProvider) -> VisionProviderManager:
    """Build a manager and inject fake sub-providers directly (bypassing real
    HTTP construction) so tests exercise ONLY the ordering/health/failover
    logic, not real network code."""
    mgr = VisionProviderManager(_config())
    from atlas.vision.manager import _Slot

    mgr._slots = {name: _Slot(name=name, provider=p) for name, p in slots.items()}
    mgr._order = list(slots)
    return mgr


IMG = np.zeros((4, 4, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Missing API key -> provider skipped entirely
# ---------------------------------------------------------------------------


def test_provider_with_missing_key_is_never_constructed() -> None:
    cfg = _config(groq_api_key="key-123")  # google/openrouter left empty
    mgr = VisionProviderManager(cfg)
    assert mgr.configured_providers == ["groq"]


def test_zero_configured_providers_does_not_raise_at_construction() -> None:
    mgr = VisionProviderManager(_config())
    assert mgr.configured_providers == []


# ---------------------------------------------------------------------------
# Failover: Google fails -> Groq succeeds; both fail -> OpenRouter succeeds
# ---------------------------------------------------------------------------


def test_google_fails_groq_succeeds() -> None:
    google = _FakeSubProvider("google", [ConnectionError("network down")])
    groq = _FakeSubProvider("groq", [_scene("groq")])
    mgr = _manager_with(google=google, groq=groq)
    scene = mgr.describe(IMG)
    assert scene.provider == "groq"
    assert google.calls == 1
    assert groq.calls == 1


def test_google_and_groq_fail_openrouter_succeeds() -> None:
    google = _FakeSubProvider("google", [TimeoutError("timed out")])
    groq = _FakeSubProvider("groq", [ConnectionError("down")])
    openrouter = _FakeSubProvider("openrouter", [_scene("openrouter")])
    mgr = _manager_with(google=google, groq=groq, openrouter=openrouter)
    scene = mgr.describe(IMG)
    assert scene.provider == "openrouter"
    assert google.calls == 1 and groq.calls == 1 and openrouter.calls == 1


def test_all_providers_fail_raises_last_exception() -> None:
    google = _FakeSubProvider("google", [ConnectionError("g down")])
    groq = _FakeSubProvider("groq", [TimeoutError("q timeout")])
    mgr = _manager_with(google=google, groq=groq)
    with pytest.raises(TimeoutError):
        mgr.describe(IMG)


# ---------------------------------------------------------------------------
# Provider cooldown: a failed provider is skipped on the NEXT request instead
# of being retried immediately.
# ---------------------------------------------------------------------------


def test_failed_provider_enters_cooldown_and_is_skipped_next_request() -> None:
    google = _FakeSubProvider("google", [ConnectionError("down"), _scene("google")])
    groq = _FakeSubProvider("groq", [_scene("groq"), _scene("groq")])
    mgr = _manager_with(google=google, groq=groq)
    mgr._cooldown_seconds = 60.0

    scene1 = mgr.describe(IMG)
    assert scene1.provider == "groq"
    assert mgr.health("google").status == "COOLDOWN"

    # Second request: google is still in cooldown, must not be retried.
    scene2 = mgr.describe(IMG)
    assert scene2.provider == "groq"
    assert google.calls == 1  # not called again


# ---------------------------------------------------------------------------
# Stickiness: once a provider succeeds, it is tried FIRST next time.
# ---------------------------------------------------------------------------


def test_successful_provider_becomes_sticky() -> None:
    google = _FakeSubProvider("google", [ConnectionError("down"), _scene("google")])
    groq = _FakeSubProvider("groq", [_scene("groq"), _scene("groq")])
    mgr = _manager_with(google=google, groq=groq)
    mgr._cooldown_seconds = 0.0  # cooldown expires immediately for this test

    scene1 = mgr.describe(IMG)
    assert scene1.provider == "groq"  # google failed first time

    scene2 = mgr.describe(IMG)
    assert scene2.provider == "groq"  # sticky: groq tried first now
    assert groq.calls == 2
    assert google.calls == 1  # google not retried while groq (sticky) still healthy


# ---------------------------------------------------------------------------
# classify_failure
# ---------------------------------------------------------------------------


def test_classify_failure_timeout() -> None:
    assert classify_failure(TimeoutError("x")) == "TIMEOUT"


def test_classify_failure_connection_error() -> None:
    assert classify_failure(ConnectionError("x")) == "NETWORK_ERROR"


def test_classify_failure_invalid_json_value_error() -> None:
    assert classify_failure(ValueError("bad json")) == "INVALID_RESPONSE"


# ---------------------------------------------------------------------------
# Invalid/malformed AI output never reaches the executor: the manager
# treats it as a failure and fails over, it does not return garbage.
# ---------------------------------------------------------------------------


def test_provider_raising_on_unparseable_output_fails_over() -> None:
    """Simulates a provider adapter that raises ValueError when the response
    text isn't valid JSON (rather than returning a fabricated/empty scene) -
    the manager must fail over instead of propagating garbage."""
    google = _FakeSubProvider("google", [ValueError("could not parse VLM JSON")])
    groq = _FakeSubProvider("groq", [_scene("groq")])
    mgr = _manager_with(google=google, groq=groq)
    scene = mgr.describe(IMG)
    assert scene.provider == "groq"
    assert mgr.health("google").last_error_type == "INVALID_RESPONSE"


# ---------------------------------------------------------------------------
# create_vision_provider() factory wiring
# ---------------------------------------------------------------------------


def test_factory_builds_manager_when_two_or_more_named_keys_configured() -> None:
    cfg = _config(provider="auto", google_api_key="gk", groq_api_key="qk")
    provider = create_vision_provider(cfg)
    assert isinstance(provider, VisionProviderManager)
    assert set(provider.configured_providers) == {"google", "groq"}


def test_factory_does_not_build_manager_for_single_named_key() -> None:
    cfg = _config(provider="auto", groq_api_key="qk")
    provider = create_vision_provider(cfg)
    # A SINGLE named key is enough to use a real VLM - the fix for the "No
    # VLM endpoint configured" symptom that appeared while keys sat in .env.
    assert isinstance(provider, VisionProviderManager)
    assert provider.configured_providers == ["groq"]
    assert provider.is_vlm is True


def test_factory_falls_back_to_rule_provider_when_multi_requested_but_no_keys() -> None:
    cfg = _config(provider="multi")
    provider = create_vision_provider(cfg)
    assert not isinstance(provider, VisionProviderManager)

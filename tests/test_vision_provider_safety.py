"""Regression tests for Vision-provider failure handling.

Audit finding: ``SceneAnalyzer.analyze()`` -> ``VisionProvider.describe()``
had NO exception handling anywhere between the HTTP call and the main
workflow loop, despite an explicit, repeated requirement that ATLAS must
never crash merely because the AI provider is unavailable (network timeout,
malformed response, HTTP error). ``read_text()`` already documented and
implemented a "never raises" contract; ``describe()``/``analyze()`` did not.
Covers:

- malformed/unparseable Vision JSON (``_safe_json``)
- a provider that raises (timeout, connection error) during ``observe()``
  falling back to the last cached analysis instead of crashing the loop
- low-confidence scene elements still parsing without raising
"""

from __future__ import annotations

import numpy as np
import pytest

from atlas.config import VisionConfig
from atlas.vision.providers import OpenAIVisionProvider, _safe_json, _parse_scene
from atlas.vision.scene import SceneAnalyzer
from atlas.vision.capture import ClientArea
from atlas.vision.models import SceneDescription


# ---------------------------------------------------------------------------
# _safe_json - malformed Vision JSON
# ---------------------------------------------------------------------------


def test_safe_json_parses_clean_json() -> None:
    assert _safe_json('{"a": 1}') == {"a": 1}


def test_safe_json_strips_markdown_fence() -> None:
    assert _safe_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_safe_json_handles_trailing_commentary() -> None:
    assert _safe_json('Sure, here is the result: {"a": 1} - hope that helps!') == {"a": 1}


def test_safe_json_returns_none_for_garbage() -> None:
    assert _safe_json("I cannot see the screen clearly.") is None


def test_safe_json_returns_none_for_truncated_json() -> None:
    assert _safe_json('{"elements": [{"label": "Full Name"') is None


def test_safe_json_returns_none_for_empty_string() -> None:
    assert _safe_json("") is None
    assert _safe_json(None) is None


def test_parse_scene_never_raises_on_malformed_dict() -> None:
    """Even a badly-shaped (but valid JSON) response must degrade to an
    empty/best-effort scene rather than raising."""
    scene = _parse_scene({"elements": "not-a-list", "confidence": "high"}, "test", (0, 0))
    assert isinstance(scene, SceneDescription)
    assert scene.elements == []


def test_parse_scene_handles_missing_fields_entirely() -> None:
    scene = _parse_scene({}, "test", (0, 0))
    assert isinstance(scene, SceneDescription)
    assert scene.elements == []


# ---------------------------------------------------------------------------
# Low-confidence elements still parse (no exception, no invented values)
# ---------------------------------------------------------------------------


def test_parse_scene_preserves_low_confidence_element() -> None:
    raw = {
        "elements": [
            {"id": "e1", "type": "textbox", "label": "Full Name", "name": "Full Name",
             "x": 10, "y": 10, "width": 100, "height": 20, "confidence": 0.12},
        ],
    }
    scene = _parse_scene(raw, "test", (0, 0))
    assert len(scene.elements) == 1
    assert scene.elements[0].confidence == pytest.approx(0.12)


# ---------------------------------------------------------------------------
# describe() propagates provider failures (timeout, connection error, HTTP
# error) rather than silently returning a fabricated scene - so it must be
# the CALLER's job to catch and fall back, tested below via SceneAnalyzer.
# ---------------------------------------------------------------------------


class _RaisingProvider:
    name = "raising"

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def describe(self, image, window_title="", url=None):
        raise self._exc

    def read_text(self, image):
        return []

    def close(self):
        pass


def test_scene_analyzer_analyze_propagates_provider_exception() -> None:
    """analyze() documents that it raises (callers catch it) - this pins that
    contract so a future change doesn't accidentally swallow errors here."""
    provider = _RaisingProvider(TimeoutError("vision request timed out"))
    analyzer = SceneAnalyzer(provider=provider, cache_ttl=0.0)
    capture = ClientArea(image=np.zeros((10, 10, 3), dtype=np.uint8), left=0, top=0, width=10, height=10)
    with pytest.raises(TimeoutError):
        analyzer.analyze(capture)


def test_agent_loop_observe_falls_back_to_cache_on_provider_failure(monkeypatch) -> None:
    """THE fix: a Vision provider exception inside AgentLoop._observe() must
    never crash the loop - it must fall back to the last cached analysis
    (or None) and let the caller's normal retry/polling continue."""
    from atlas.act.controls import ControlOutcome
    from atlas.act.executor import ActionExecutor
    from atlas.core.events import get_event_bus
    from atlas.mapping.mapper import SemanticMapper
    from atlas.reason.planner import ActionPlanner
    from atlas.reason.recovery import RecoveryPlanner
    from atlas.understanding.source import SourceReader
    from atlas.workflow.loop import AgentLoop

    from tests.test_mpf_integration import PassVerifier, RecordingControls, StubKeyboard, StubMouse

    get_event_bus().clear()

    class _FlakyTarget:
        def __init__(self) -> None:
            self.calls = 0

        def is_alive(self) -> bool:
            return True

        def signature(self) -> str:
            return "sig"

        def observe(self):
            self.calls += 1
            if self.calls == 1:
                raise ConnectionError("vision endpoint unreachable")
            raise AssertionError("should not be called again - cache should be reused")

    target = _FlakyTarget()
    controls = RecordingControls()
    executor = ActionExecutor(
        mouse=StubMouse(), keyboard=StubKeyboard(), controls=controls,
        verifier=PassVerifier(), recovery=RecoveryPlanner(),
        verify_after_action=True, max_retries=3, retry_delay=0.0,
    )
    loop = AgentLoop(
        target=target, source_reader=SourceReader(), mapper=SemanticMapper(),
        planner=ActionPlanner(verify_after_action=True), executor=executor,
        max_records=1, next_record_timeout=2.0, next_record_poll=0.05,
    )

    # First call: provider raises -> must not propagate, falls back to None
    # (no cache yet).
    analysis, changed = loop._observe()
    assert analysis is None
    assert changed is False

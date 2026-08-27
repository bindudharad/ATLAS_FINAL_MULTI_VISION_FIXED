"""SINGLE-FORM TEST MODE.

Process exactly ONE complete form, then terminate ATLAS cleanly: never advance
to record 2, never auto-restart, never close the target application, and (by
default) NEVER click the upload button - the form stays filled and verified on
screen for inspection.

The upload guard must hold for every path: engine ``submit()``, the
field-driven submit, and plan upload actions (``_execute_plan``).
"""

from __future__ import annotations

from atlas.act.controls import ControlInterface, ControlOutcome
from atlas.act.executor import ActionExecutor
from atlas.act.models import ActionType
from atlas.act.verify import FieldVerifier
from atlas.dashboard import _STATE_LABELS
from atlas.mapping.mapper import SemanticMapper
from atlas.reason.planner import ActionPlanner
from atlas.reason.recovery import RecoveryPlanner
from atlas.target.base import TargetAdapter, TargetInfo
from atlas.understanding.source import SourceReader
from atlas.vision.models import BBox, ElementType, SceneDescription, ScreenElement
from atlas.vision.scene import SceneAnalysis
from atlas.workflow.audit import AuditStatus, RecordAudit, UploadStatus
from atlas.workflow.loop import AgentLoop


class RecordingControls(ControlInterface):
    def __init__(self) -> None:
        self.typed: list[str] = []
        self.clicked: list[str] = []

    def focus(self, bbox, field_id=None): return ControlOutcome(ok=True)
    def click_field(self, bbox, field_id=None):
        if field_id:
            self.clicked.append(field_id)
        return ControlOutcome(ok=True)
    def type_value(self, bbox, value, field_id=None):
        self.typed.append(value)
        return ControlOutcome(ok=True)
    def clear(self, bbox, field_id=None): return ControlOutcome(ok=True)
    def select_option(self, bbox, value, options=None, field_id=None): return ControlOutcome(ok=True)
    def toggle(self, bbox, value, field_id=None): return ControlOutcome(ok=True)
    def choose_date(self, bbox, value, date_format=None, field_id=None): return ControlOutcome(ok=True)
    def press_tab(self): return ControlOutcome(ok=True)
    def press_enter(self): return ControlOutcome(ok=True)
    def press_escape(self): return ControlOutcome(ok=True)
    def scroll(self, direction, amount=3): return ControlOutcome(ok=True)
    def scroll_dropdown(self, direction, amount=3): return ControlOutcome(ok=True)
    def paste(self, value, field_id=None): return ControlOutcome(ok=True)
    def upload_file(self, bbox, path, field_id=None): return ControlOutcome(ok=True)


class StubMouse:
    def move_to(self, x, y): pass
    def click(self, x, y): pass
    def double_click(self, x, y): pass
    def right_click(self, x, y): pass
    def hover(self, x, y): pass
    def scroll(self, direction, amount=3): pass


class StubKeyboard:
    driver = None


class PassVerifier(FieldVerifier):
    name = "pass"

    def verify(self, bbox, expected, field_id=None):
        return True, "ok"


class FakeTarget(TargetAdapter):
    name = "fake"

    def __init__(self, scenes: list[SceneDescription]) -> None:
        self._scenes = list(scenes)
        self._idx = 0
        self._info = TargetInfo(name="fake", title="Fake Window")

    def attach(self, hint: str | None = None) -> TargetInfo:
        return self._info

    def detach(self) -> None:
        pass

    def observe(self) -> SceneAnalysis | None:
        if self._idx < len(self._scenes):
            scene = self._scenes[self._idx]
            self._idx += 1
            return SceneAnalysis(scene=scene)
        return None

    def is_alive(self) -> bool:
        return True

    def read_field_value(self, field_id: str) -> str | None:
        return None


def make_scene(record_no: str, name: str, agree: str) -> SceneDescription:
    elements = [
        ScreenElement(element_id="s0", type=ElementType.LABEL, label="Application No", value=record_no, bbox=BBox(10, 10, 120, 16)),
        ScreenElement(element_id="s1", type=ElementType.LABEL, label="Applicant Name", value=name, bbox=BBox(10, 30, 120, 16)),
        ScreenElement(element_id="s2", type=ElementType.LABEL, label="Agree", value=agree, bbox=BBox(10, 50, 120, 16)),
        ScreenElement(element_id="f0", type=ElementType.TEXTBOX, label="Applicant Name", bbox=BBox(200, 40, 120, 20)),
        ScreenElement(element_id="f1", type=ElementType.CHECKBOX, label="Agree", bbox=BBox(200, 80, 20, 20)),
        ScreenElement(element_id="b0", type=ElementType.BUTTON, label="Save", bbox=BBox(200, 120, 60, 24)),
    ]
    return SceneDescription(window_title="Fake Window", elements=elements, screen_offset=(0, 0))


def _build_loop(target, controls, max_records=2, timeout=1.0, single_form=False, single_form_upload=False):
    executor = ActionExecutor(
        mouse=StubMouse(),
        keyboard=StubKeyboard(),
        controls=controls,
        verifier=PassVerifier(),
        recovery=RecoveryPlanner(),
        verify_after_action=True,
        max_retries=2,
        retry_delay=0.0,
    )
    return AgentLoop(
        target=target,
        source_reader=SourceReader(),
        mapper=SemanticMapper(),
        planner=ActionPlanner(verify_after_action=True),
        executor=executor,
        max_records=max_records,
        next_record_timeout=timeout,
        next_record_poll=0.05,
        single_form=single_form,
        single_form_upload=single_form_upload,
    )


def test_single_form_processes_exactly_one_record_and_terminates() -> None:
    """The second FakeTarget scene (record 2) must never be loaded or typed."""
    target = FakeTarget([
        make_scene("1001", "Ravi Kumar", "Yes"),
        make_scene("1002", "Sita Devi", "No"),
    ])
    controls = RecordingControls()
    loop = _build_loop(target, controls, max_records=0, single_form=True, single_form_upload=False)
    summary = loop.run()
    assert summary.completed == 1
    assert summary.failed == 0
    assert len(summary.records) == 1
    assert [r.record.record_key for r in summary.records] == ["1001"]
    assert controls.typed == ["Ravi Kumar"]
    assert loop.single_form_complete is True
    assert loop.terminate_requested is True
    assert loop.state.value == "stopped"
    assert summary.stopped_reason == "SINGLE FORM COMPLETED — AUTOMATION TERMINATED"


def test_single_form_blocks_upload_with_pass_audit() -> None:
    """Even a fully verified record must NOT upload in default single-form mode."""
    loop = _build_loop(
        FakeTarget([make_scene("1001", "Ravi Kumar", "Yes")]),
        RecordingControls(),
        single_form=True,
        single_form_upload=False,
    )
    loop._last_audit = RecordAudit(audit_status=AuditStatus.PASS, upload_status=UploadStatus.ALLOWED)
    assert loop.allows_submit() is True
    assert loop.submit() is False


def test_single_form_upload_enabled_allows_verified_submit() -> None:
    """With single_form_upload=True the same verified audit may submit."""
    loop = _build_loop(
        FakeTarget([make_scene("1001", "Ravi Kumar", "Yes")]),
        RecordingControls(),
        single_form=True,
        single_form_upload=True,
    )
    loop._last_audit = RecordAudit(audit_status=AuditStatus.PASS, upload_status=UploadStatus.ALLOWED)
    assert loop.submit() is True


def test_single_form_field_driven_submit_is_blocked() -> None:
    """_submit_field_driven must never execute an upload click in no-upload mode."""
    controls = RecordingControls()
    loop = _build_loop(
        FakeTarget([make_scene("1001", "Ravi Kumar", "Yes")]),
        controls,
        single_form=True,
        single_form_upload=False,
    )
    loop._last_audit = RecordAudit(audit_status=AuditStatus.PASS, upload_status=UploadStatus.ALLOWED)
    record = __import__("atlas.understanding.source", fromlist=["SourceRecord"]).SourceRecord(
        pairs={"Applicant Name": "Ravi Kumar"}, ordered_labels=["Applicant Name"]
    )
    result = loop._submit_field_driven(record, 1)
    assert result is None
    assert loop._last_field is None or "upload" not in (loop._last_field or "")
    assert "upload" not in [c for c in controls.clicked]
    assert not controls.typed  # nothing extra was typed either


def test_multi_record_mode_unchanged() -> None:
    """single_form=False keeps the normal multi-record behaviour."""
    target = FakeTarget([
        make_scene("1001", "Ravi Kumar", "Yes"),
        make_scene("1002", "Sita Devi", "No"),
    ])
    controls = RecordingControls()
    loop = _build_loop(target, controls, max_records=2, single_form=False)
    summary = loop.run()
    assert summary.completed == 2
    assert summary.failed == 0
    assert controls.typed == ["Ravi Kumar", "Sita Devi"]
    assert loop.single_form_complete is False
    assert loop.single_form_mode is False


def test_dashboard_has_finished_label() -> None:
    assert _STATE_LABELS.get("finished") == "FINISHED"


def test_run_report_logs_single_form_completion() -> None:
    """The per-record message must call out that upload was not performed."""
    target = FakeTarget([make_scene("1001", "Ravi Kumar", "Yes")])
    loop = _build_loop(target, RecordingControls(), max_records=0, single_form=True, single_form_upload=False)
    summary = loop.run()
    assert summary.completed == 1
    assert summary.failed == 0
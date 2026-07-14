from __future__ import annotations

import curses
from enum import Enum
from types import SimpleNamespace
from typing import Any

import pytest

from nebula_agents.domain.enums import DecisionKind, Role, ValidatorKey
from nebula_agents.domain.models import Actor
from nebula_agents.presentation import tui
from nebula_agents.presentation.tui import CockpitUI, PendingAction, Screen


RUN_A = "2026-07-13-deadbeef"
RUN_B = "2026-07-13-feedface"


class FakeWindow:
    def __init__(
        self,
        *,
        size: tuple[int, int] = (30, 120),
        keys: list[int | BaseException] | None = None,
        inputs: list[bytes] | None = None,
        reject_writes: bool = False,
    ) -> None:
        self.size = size
        self.keys = list(keys or [])
        self.inputs = list(inputs or [])
        self.reject_writes = reject_writes
        self.writes: list[tuple[int, int, str, int, int]] = []
        self.refresh_count = 0
        self.erased = 0
        self.keypad_value: bool | None = None
        self.timeout_value: int | None = None
        self.moves: list[tuple[int, int]] = []
        self.cleared = 0

    def keypad(self, value: bool) -> None:
        self.keypad_value = value

    def timeout(self, value: int) -> None:
        self.timeout_value = value

    def getch(self) -> int:
        value = self.keys.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value

    def getmaxyx(self) -> tuple[int, int]:
        return self.size

    def erase(self) -> None:
        self.erased += 1

    def refresh(self) -> None:
        self.refresh_count += 1

    def addnstr(self, row: int, column: int, text: str, limit: int, attribute: int) -> None:
        if self.reject_writes:
            raise curses.error("edge")
        self.writes.append((row, column, text, limit, attribute))

    def move(self, row: int, column: int) -> None:
        self.moves.append((row, column))

    def clrtoeol(self) -> None:
        self.cleared += 1

    def getstr(self, _row: int, _column: int, _limit: int) -> bytes:
        return self.inputs.pop(0)

    @property
    def text(self) -> str:
        return "\n".join(item[2] for item in self.writes)


class Calls:
    def __init__(self) -> None:
        self.values: list[tuple[str, dict[str, Any]]] = []

    def method(self, name: str, result: object = None):
        def call(**kwargs: Any) -> object:
            self.values.append((name, kwargs))
            if isinstance(result, BaseException):
                raise result
            return result

        return call


def _detail(run_id: str = RUN_A) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "feature_id": "F0001",
        "story_id": "F0001-S0001",
        "provider_key": "codex",
        "tmux_session": "nebula-f0001-deadbeef",
        "status": "Active",
        "revision": 7,
        "updated_at": "2026-07-13T18:00:00Z",
        "last_seen_at": "2026-07-13T18:01:00Z",
        "last_event_sequence": 9,
        "can_attach": True,
        "can_recover": True,
        "recovery_available": False,
        "can_decide_gate": True,
        "can_configure_transcript": True,
        "gate": {
            "gate_id": "G4",
            "status": "Pending",
            "evidence_ready": True,
            "required_evidence": ["test-results.md", "security-review.md"],
            "decision": {
                "decision": "Hold",
                "reason": "inspect evidence",
                "actor": {"username": "operator", "display_label": "Local Operator"},
                "decided_at": "2026-07-13T18:00:00Z",
            },
        },
        "latest_validator": {
            "validator_key": "stories",
            "exit_code": 0,
            "completed_at": "2026-07-13T18:00:00Z",
            "summary": "passed",
            "artifact_path": "evidence/validator.log",
        },
        "transcript": {
            "status": "Active",
            "redaction_status": "Redacted",
            "redaction_findings": 2,
            "path": "transcript.redacted.log",
            "preview": "first line\nsecond line",
        },
    }


def _evidence() -> dict[str, Any]:
    return {
        "artifacts": [
            {"relative_path": "test-results.md", "status": "Available"},
            {"relative_path": "security-review.md", "status": "Missing"},
            "ignored",
        ]
    }


def _application(calls: Calls | None = None) -> SimpleNamespace:
    calls = calls or Calls()
    actor = Actor(1000, "operator", Role.LOCAL_OPERATOR)
    sessions = {
        "sessions": [
            {
                "run_id": RUN_A,
                "provider_key": "codex",
                "status": "Active",
                "tmux_session": "nebula-f0001-deadbeef",
                "gate": {"status": "Pending"},
                "can_attach": True,
                "can_recover": True,
                "recovery_available": False,
                "can_decide_gate": True,
                "can_configure_transcript": True,
            },
            {
                "run_id": RUN_B,
                "provider_key": "claude",
                "status": "Failed",
                "gate": "Unknown",
                "can_attach": False,
                "can_recover": False,
                "recovery_available": True,
                "can_decide_gate": False,
                "can_configure_transcript": False,
            },
        ]
    }
    return SimpleNamespace(
        current_actor=lambda: actor,
        queries=SimpleNamespace(
            sessions=calls.method("sessions", sessions),
            status=calls.method("status", _detail()),
            evidence=calls.method("evidence", _evidence()),
        ),
        runs=SimpleNamespace(
            attach=calls.method("attach", 4),
            reconcile=calls.method("reconcile", {"status": "Active"}),
            launch=calls.method("launch", {"run_id": RUN_B}),
        ),
        gates=SimpleNamespace(
            run_validator=calls.method("validator", {"exit_code": 0}),
            decide=calls.method("decide", {"gate": "G4"}),
            resume=calls.method("resume", {"gate": "G4"}),
        ),
        transcripts=SimpleNamespace(enable=calls.method("transcript", {"status": "Active"})),
    )


def _loaded_ui(calls: Calls | None = None) -> CockpitUI:
    ui = CockpitUI(_application(calls), RUN_A)
    ui.state.sessions = [
        {
            "run_id": RUN_A,
            "provider_key": "codex",
            "status": "Active",
            "tmux_session": "nebula-f0001-deadbeef",
            "gate": {"status": "Pending"},
            "can_attach": True,
            "can_recover": True,
            "recovery_available": False,
            "can_decide_gate": True,
            "can_configure_transcript": True,
        },
        {
            "run_id": RUN_B,
            "provider_key": "claude",
            "status": "Failed",
            "gate": "Unknown",
            "can_attach": False,
            "can_recover": False,
            "recovery_available": True,
            "can_decide_gate": False,
            "can_configure_transcript": False,
        },
    ]
    ui.state.detail = _detail()
    ui.state.evidence = _evidence()
    return ui


def test_run_drives_keyboard_navigation_resize_help_and_quit(monkeypatch: pytest.MonkeyPatch) -> None:
    window = FakeWindow(keys=[curses.KEY_RESIZE, curses.KEY_DOWN, 10, ord("?"), ord("b"), ord("q")])
    monkeypatch.setattr(curses, "has_colors", lambda: False)
    monkeypatch.setattr(curses, "curs_set", lambda _value: 0)
    ui = CockpitUI(_application())

    assert ui.run(window) == 0
    assert window.keypad_value is True
    assert window.timeout_value == 500
    assert window.erased == 6
    assert RUN_B in window.text
    assert "Move session selection" in window.text


def test_run_returns_interrupt_exit_and_configures_colors(monkeypatch: pytest.MonkeyPatch) -> None:
    window = FakeWindow(keys=[KeyboardInterrupt()])
    configured: list[tuple[int, int, int]] = []
    monkeypatch.setattr(curses, "has_colors", lambda: True)
    monkeypatch.setattr(curses, "start_color", lambda: None)
    monkeypatch.setattr(curses, "use_default_colors", lambda: None)
    monkeypatch.setattr(curses, "init_pair", lambda *args: configured.append(args))
    monkeypatch.setattr(curses, "color_pair", lambda value: value * 10)
    monkeypatch.setattr(curses, "curs_set", lambda _value: (_ for _ in ()).throw(curses.error()))

    assert CockpitUI(_application()).run(window) == 130
    assert configured == [(1, curses.COLOR_GREEN, -1), (2, curses.COLOR_YELLOW, -1), (3, curses.COLOR_CYAN, -1)]


def test_refresh_preserves_selection_loads_initial_detail_and_handles_missing_or_failure() -> None:
    ui = CockpitUI(_application(), RUN_B)
    ui._refresh_data(open_initial=True)
    assert ui.state.selection == 1
    assert ui.state.selected_run_id == RUN_B
    assert ui.state.screen is Screen.DETAIL
    assert ui.state.detail and ui.state.detail["run_id"] == RUN_A

    missing = CockpitUI(_application(), "2026-07-13-aaaaaaaa")
    missing._refresh_data(open_initial=True)
    assert missing.state.selected_run_id == RUN_A
    assert "was not found" in missing.state.message

    calls = Calls()
    app = _application(calls)
    app.queries.sessions = calls.method("sessions-error", RuntimeError("secret detail"))
    failed = CockpitUI(app)
    failed._refresh_data()
    assert failed.state.message == "COMMAND_FAILED: The operation failed safely."


def test_tui_merges_loads_and_recovers_corrupt_snapshot_with_exact_revision() -> None:
    calls = Calls()
    application = _application(calls)
    candidate = {
        "run_id": RUN_B,
        "recoverable_revision": 11,
        "recovery_available": True,
        "can_recover": True,
        "last_gate": {"gate_id": "G3", "status": "Held"},
        "last_audit_event": {
            "sequence": 12,
            "event_type": "TranscriptCompleted",
            "occurred_at": "2026-07-13T18:00:00Z",
        },
        "transcript_path": None,
        "recovery_command": (
            f"nebula-agents recover --run-id {RUN_B} --expected-revision 11"
        ),
    }
    application.queries.recovery_candidates = calls.method(
        "recovery_candidates", [candidate]
    )
    application.queries.recovery_status = calls.method("recovery_status", candidate)
    application.runs.recover = calls.method("recover", {"run_id": RUN_B})
    ui = CockpitUI(application, RUN_B)

    ui._refresh_data(open_initial=True)

    assert ui.state.selected_run_id == RUN_B
    assert ui.state.detail is not None
    assert ui.state.detail["status"] == "Corrupt"
    assert ui.state.detail["revision"] == 11
    assert ui.state.detail["recovery_command"].endswith("--expected-revision 11")
    assert ui._can_recover() is True
    assert ui._recover() == {"run_id": RUN_B}
    recovery_call = next(kwargs for name, kwargs in calls.values if name == "recover")
    assert recovery_call["run_id"] == RUN_B
    assert recovery_call["expected_revision"] == 11
    assert not any(name in {"status", "evidence"} for name, _ in calls.values)


def test_selection_and_load_normalize_empty_and_non_mapping_projections() -> None:
    ui = _loaded_ui()
    ui.state.selection = 99
    ui._select_current()
    assert ui.state.selection == 1
    ui.state.selection = -3
    ui._select_current()
    assert ui.state.selection == 0
    ui.state.sessions = []
    ui.state.screen = Screen.SESSIONS
    ui._select_current()
    assert ui.state.selected_run_id is None
    ui._load_selected()
    assert ui.state.detail is None and ui.state.evidence is None

    app = _application()
    app.queries.status = lambda **_kwargs: "plain detail"
    app.queries.evidence = lambda **_kwargs: 42
    ui = CockpitUI(app, RUN_A)
    ui._load_selected()
    assert ui.state.detail == {"value": "plain detail"}
    assert ui.state.evidence == {"value": 42}


def test_render_all_views_and_small_terminal_with_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(curses, "has_colors", lambda: False)
    ui = _loaded_ui()
    window = FakeWindow()
    expected = {
        Screen.SESSIONS: "RUN ID",
        Screen.DETAIL: "nebula-agents attach",
        Screen.GATE: "approve or hold explicitly",
        Screen.EVIDENCE: "Transcript: [OK] Active",
        Screen.HELP: "Move session selection",
    }
    for screen, marker in expected.items():
        window.writes.clear()
        ui.state.screen = screen
        ui.state.message = "operator notice"
        ui._render(window)
        assert marker in window.text
        assert "operator notice" in window.text
        assert "q quit" in window.text

    ui._confirm("Run stories validator", lambda: 0)
    window.writes.clear()
    ui._render(window)
    assert "Confirm explicit mutation" in window.text
    assert "1/2 observed artifact(s) available" in window.text

    small = FakeWindow(size=(8, 30))
    ui._render(small)
    assert "resize to at least 40x12" in small.text
    assert "q quit" in small.text


def test_render_empty_and_irregular_views_remains_accessible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(curses, "has_colors", lambda: False)
    ui = _loaded_ui()
    window = FakeWindow(size=(25, 70))
    ui.state.sessions = []
    ui.state.screen = Screen.SESSIONS
    ui._render(window)
    assert "No recorded sessions" in window.text

    ui.state.detail = {"gate": "invalid", "latest_validator": "invalid", "transcript": "invalid"}
    ui.state.evidence = ["ignored", {"relative_path": "a", "status": "Stale"}]
    ui.state.screen = Screen.GATE
    window.writes.clear()
    ui._render(window)
    assert "No active gate" in window.text
    assert "refresh/reconcile blocked state" in window.text
    ui.state.screen = Screen.EVIDENCE
    window.writes.clear()
    ui._render(window)
    assert "[!] Stale" in window.text


def test_handle_session_keys_prepare_expected_confirmations(monkeypatch: pytest.MonkeyPatch) -> None:
    ui = _loaded_ui()
    window = FakeWindow()
    assert ui._handle_key(window, ord("Q")) is True
    assert ui._handle_key(window, -1) is False
    ui._handle_key(window, ord("?"))
    assert ui.state.screen is Screen.HELP
    ui._handle_key(window, 27)
    assert ui.state.screen is Screen.SESSIONS
    ui.state.selection = 1
    ui._handle_key(window, curses.KEY_UP)
    assert ui.state.selection == 0

    ui.state.sessions = ui.state.sessions or []
    ui.state.selected_run_id = RUN_A
    ui._handle_key(window, ord("R"))
    assert ui.state.pending and ui.state.pending.label.startswith("Reconcile")
    ui._handle_key(window, ord("n"))
    assert ui.state.pending is None

    ui._handle_key(window, ord("a"))
    assert ui.state.pending and ui.state.pending.label.startswith("Attach")
    ended: list[bool] = []
    monkeypatch.setattr(curses, "endwin", lambda: ended.append(True))
    ui._handle_key(window, ord("y"))
    assert ended == [True]
    assert "returned 4" in ui.state.message


def test_validator_transcript_gate_and_refresh_keys_cover_valid_and_invalid_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    ui = _loaded_ui()
    window = FakeWindow()
    prompts = iter(["bogus", "templates"])
    monkeypatch.setattr(ui, "_prompt", lambda _window, _label: next(prompts))
    ui._handle_key(window, ord("v"))
    assert "Validator must be" in ui.state.message
    ui._handle_key(window, ord("v"))
    assert ui.state.pending and ui.state.pending.label == "Run templates validator"
    ui._handle_confirmation(window, 27)

    ui.state.detail = _detail()
    ui.state.detail["transcript"] = {"status": "Disabled"}
    ui._handle_key(window, ord("t"))
    assert ui.state.pending and ui.state.pending.label.startswith("Enable")
    ui._handle_confirmation(window, ord("n"))
    ui.state.detail = _detail()
    ui._handle_key(window, ord("t"))
    assert ui.state.screen is Screen.EVIDENCE

    ui.state.screen = Screen.DETAIL
    ui._handle_key(window, ord("g"))
    assert ui.state.screen is Screen.GATE
    ui.state.detail = {"gate": {"status": "Blocked", "evidence_ready": False}, "latest_validator": {"exit_code": 1}}
    ui._handle_gate_key(window, ord("p"))
    assert "Approval is unavailable" in ui.state.message
    ui.state.screen = Screen.DETAIL
    ui._handle_key(window, ord("r"))
    assert ui.state.message == "View refreshed."


def test_gate_keys_prepare_approve_hold_resume_and_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    ui = _loaded_ui()
    ui.state.screen = Screen.GATE
    window = FakeWindow()
    ui._handle_key(window, ord("p"))
    assert ui.state.pending and ui.state.pending.label == "Approve current gate"
    ui._handle_confirmation(window, ord("n"))

    prompts = iter(["maintenance", "", "trackers", "invalid"])
    monkeypatch.setattr(ui, "_prompt", lambda _window, _label: next(prompts))
    ui._handle_gate_key(window, ord("h"))
    assert ui.state.pending and ui.state.pending.label == "Hold current gate"
    ui._handle_confirmation(window, ord("n"))
    ui._handle_gate_key(window, ord("h"))
    assert ui.state.pending is None
    ui._handle_gate_key(window, ord("u"))
    assert ui.state.pending and ui.state.pending.label == "Resume held gate"
    ui._handle_confirmation(window, ord("n"))
    ui._handle_gate_key(window, ord("v"))
    assert ui.state.pending and ui.state.pending.label == "Run trackers validator"
    ui._handle_confirmation(window, ord("n"))
    ui._handle_gate_key(window, ord("v"))
    assert "Validator must be" in ui.state.message


def test_mutation_helpers_bind_actor_revision_enums_and_requests() -> None:
    calls = Calls()
    ui = _loaded_ui(calls)
    assert ui._attach() == 4
    assert ui._validate("stories") == {"exit_code": 0}
    assert ui._enable_transcript() == {"status": "Active"}
    assert ui._reconcile() == {"status": "Active"}
    assert ui._resume_gate() == {"gate": "G4"}
    assert ui._decide_gate("Hold", "review") == {"gate": "G4"}
    assert ui._decide_gate("Approve", None) == {"gate": "G4"}
    validator = next(kwargs for name, kwargs in calls.values if name == "validator")
    assert validator["key"] is ValidatorKey.STORIES
    decisions = [kwargs["request"] for name, kwargs in calls.values if name == "decide"]
    assert decisions[0].decision is DecisionKind.HOLD and decisions[0].confirmed is False
    assert decisions[1].decision is DecisionKind.APPROVE and decisions[1].confirmed is True
    assert all(request.expected_revision == 7 for request in decisions)


def test_mutation_guard_errors_and_confirmation_failures_are_safe() -> None:
    ui = _loaded_ui()
    ui.state.detail = {}
    with pytest.raises(RuntimeError, match="revision is unavailable"):
        ui._revision()
    with pytest.raises(RuntimeError, match="No current gate"):
        ui._decide_gate("Approve", None)
    ui.state.detail = {"gate": {"status": "Pending", "evidence_ready": True}, "latest_validator": "invalid"}
    assert ui._gate_approval_available() is False

    ui.application.queries.status = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("hidden"))
    ui.state.selected_run_id = RUN_A
    ui._load_selected_safely()
    assert ui.state.message == "COMMAND_FAILED: The operation failed safely."

    ui.state.selected_run_id = RUN_A
    ui.state.screen = Screen.DETAIL
    ui._confirm("Fail safely", lambda: (_ for _ in ()).throw(RuntimeError("sensitive")))
    ui._handle_confirmation(FakeWindow(), ord("Y"))
    assert ui.state.message == "COMMAND_FAILED: The operation failed safely."
    assert ui.state.pending is None


@pytest.mark.parametrize(
    ("gate", "validator", "expected"),
    [
        ({"status": "Unknown"}, {}, "refresh/reconcile blocked state"),
        ({"status": "Blocked"}, {}, "refresh/reconcile blocked state"),
        ({"status": "Held"}, {}, "resume when hold is resolved"),
        ({"status": "Approved"}, {}, "await next lifecycle stage"),
        ({"status": "Pending", "evidence_ready": False}, {}, "provide required evidence"),
        ({"status": "Pending", "evidence_ready": True}, {"exit_code": 2}, "run a required validator"),
        ({"status": "Pending", "evidence_ready": True}, {"exit_code": 0}, "approve or hold explicitly"),
    ],
)
def test_next_gate_action_explains_each_lifecycle_state(
    gate: dict[str, Any], validator: dict[str, Any], expected: str
) -> None:
    assert _loaded_ui()._next_gate_action(gate, validator) == expected


def test_prepare_launch_collects_inputs_and_defers_native_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = Calls()
    ui = _loaded_ui(calls)
    answers = iter(["F0002", "CLAUDE", "BUILD", "F0002-S0003"])
    monkeypatch.setattr(ui, "_prompt", lambda _window, _label: next(answers))
    ui._handle_key(FakeWindow(), ord("l"))
    assert ui.state.selected_run_id is None
    assert ui.state.pending and ui.state.pending.label == "Launch F0002 with claude/build"
    result = ui.state.pending.callback()
    assert result == {"run_id": RUN_B}
    request = next(kwargs["request"] for name, kwargs in calls.values if name == "launch")
    assert request.feature_id == "F0002"
    assert request.story_id == "F0002-S0003"
    assert request.provider_key.value == "claude"
    assert request.prompt_action.value == "build"


def test_prompt_controls_curses_and_sanitizes_input(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[object] = []
    monkeypatch.setattr(curses, "echo", lambda: events.append("echo"))
    monkeypatch.setattr(curses, "noecho", lambda: events.append("noecho"))
    monkeypatch.setattr(curses, "curs_set", lambda value: events.append(value))
    window = FakeWindow(inputs=[b"  hello\x00\nworld  "])
    assert _loaded_ui()._prompt(window, "Label: ") == "hello world"
    assert events == ["echo", 1, "noecho", 0]
    assert window.cleared == 1 and window.refresh_count == 1

    events.clear()
    monkeypatch.setattr(curses, "curs_set", lambda value: (_ for _ in ()).throw(curses.error()) if value == 0 else None)
    window = FakeWindow(inputs=[b"value"])
    assert _loaded_ui()._prompt(window, "Label: ") == "value"
    assert window.moves


def test_run_tui_and_low_level_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(curses, "wrapper", lambda callback: callback(FakeWindow(keys=[ord("q")])))
    monkeypatch.setattr(curses, "has_colors", lambda: False)
    monkeypatch.setattr(curses, "curs_set", lambda _value: 0)
    assert tui.run_tui(_application(), RUN_A) == 0

    assert tui._artifact_list([{"status": "Available"}, "bad"]) == [{"status": "Available"}]
    assert tui._artifact_list({"observations": [{"status": "Missing"}]}) == [{"status": "Missing"}]
    assert tui._artifact_list(object()) == []

    class Code(Enum):
        BAD = "BAD"

    error = RuntimeError("hidden")
    error.code = Code.BAD  # type: ignore[attr-defined]
    error.message = "visible\nmessage"  # type: ignore[attr-defined]
    assert tui._safe_error(error) == "BAD: visible message"
    assert tui._safe_error(RuntimeError("hidden")) == "COMMAND_FAILED: The operation failed safely."

    monkeypatch.setattr(curses, "has_colors", lambda: True)
    monkeypatch.setattr(curses, "color_pair", lambda value: value * 10)
    assert tui._color(3) == 30
    assert tui._status_color("Ready") == 10
    assert tui._status_color("Blocked") == 20
    assert tui._status_color("Unknown") == 0

    ui = _loaded_ui()
    ui.state.pending = None
    ui._render_confirm(FakeWindow(), 20, 80)

    rejecting = FakeWindow(reject_writes=True)
    tui._safe_add(rejecting, 0, 0, "ignored", 0, 10)
    tui._safe_add(rejecting, 0, 0, "ignored", 0, 0)
    assert rejecting.writes == []

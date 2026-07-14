from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from nebula_agents.domain.enums import (
    DecisionKind,
    GateStatus,
    PromptAction,
    ProviderKey,
    RedactionStatus,
    Role,
    RunStatus,
    TranscriptStatus,
    ValidatorKey,
)
from nebula_agents.domain.errors import ErrorCode, NebulaError
from nebula_agents.domain.models import (
    Actor,
    GateSnapshot,
    RunRecord,
    TranscriptState,
    ValidatorResult,
)
from nebula_agents.domain.transitions import (
    decide_gate,
    mark_session_missing,
    mark_session_present,
    require_revision,
    resume_gate,
    with_transcript,
)


NOW = datetime(2026, 7, 13, 18, 0, tzinfo=UTC)
LATER = datetime(2026, 7, 13, 18, 1, tzinfo=UTC)
ACTOR = Actor(1000, "operator", Role.LOCAL_OPERATOR)


def _run(
    *,
    status: RunStatus = RunStatus.ACTIVE,
    gate_status: GateStatus = GateStatus.PENDING,
    evidence_ready: bool = True,
    validator_exit: int | None = 0,
) -> RunRecord:
    validator = None
    if validator_exit is not None:
        validator = ValidatorResult(
            ValidatorKey.STORIES,
            validator_exit,
            10,
            "test result",
            None,
            NOW,
        )
    return RunRecord(
        "1.0",
        2,
        "2026-07-13-deadbeef",
        "F0001",
        None,
        ProviderKey.CODEX,
        "nebula-F0001-deadbeef",
        "/workspace",
        "/workspace/feature-operator-friendly.md",
        PromptAction.FEATURE,
        status,
        ACTOR,
        None,
        GateSnapshot("G1", gate_status, evidence_ready, ("required.md",), None),
        validator,
        (),
        TranscriptState(TranscriptStatus.DISABLED, RedactionStatus.NOT_RUN, None, None, 0),
        "/runtime/events.jsonl",
        3,
        NOW,
        NOW,
        NOW,
    )


def test_revision_guard_accepts_exact_revision_and_rejects_stale() -> None:
    run = _run()
    require_revision(run, 2)
    with pytest.raises(NebulaError) as caught:
        require_revision(run, 1)
    assert caught.value.code is ErrorCode.STALE_REVISION
    assert caught.value.exit_code == 6


def test_active_session_becomes_detached_and_recovery_restores_same_run() -> None:
    missing = mark_session_missing(_run(), LATER)
    assert missing.status is RunStatus.DETACHED_OR_EXITED
    assert missing.revision == 3
    assert missing.last_event_sequence == 4
    recovered = mark_session_present(missing, LATER)
    assert recovered.status is RunStatus.ACTIVE
    assert recovered.run_id == missing.run_id
    assert recovered.tmux_session == missing.tmux_session


@pytest.mark.parametrize("terminal", [RunStatus.FAILED, RunStatus.EXITED])
def test_terminal_run_cannot_be_reactivated_by_observation(terminal: RunStatus) -> None:
    run = _run(status=terminal)
    result = mark_session_present(run, LATER)
    assert result is run


def test_missing_observation_does_not_rewrite_terminal_run() -> None:
    run = _run(status=RunStatus.FAILED)
    assert mark_session_missing(run, LATER) is run


def test_gate_approval_requires_ready_evidence_and_passing_validator() -> None:
    approved = decide_gate(
        _run(),
        gate_id="G1",
        decision=DecisionKind.APPROVE,
        reason=None,
        actor=ACTOR,
        now=LATER,
    )
    assert approved.gate.status is GateStatus.APPROVED
    assert approved.gate.decision is not None
    assert approved.gate.decision.record_revision == 2
    assert approved.revision == 3

    for blocked in (
        _run(evidence_ready=False),
        _run(validator_exit=1),
        _run(validator_exit=None),
    ):
        with pytest.raises(NebulaError) as caught:
            decide_gate(
                blocked,
                gate_id="G1",
                decision=DecisionKind.APPROVE,
                reason=None,
                actor=ACTOR,
                now=LATER,
            )
        assert caught.value.code is ErrorCode.GATE_BLOCKED


def test_unknown_gate_state_fails_closed_for_decisions() -> None:
    with pytest.raises(NebulaError) as caught:
        decide_gate(
            _run(gate_status=GateStatus.UNKNOWN),
            gate_id="G1",
            decision=DecisionKind.HOLD,
            reason="reconcile first",
            actor=ACTOR,
            now=LATER,
        )
    assert caught.value.code is ErrorCode.GATE_BLOCKED


@pytest.mark.parametrize(
    ("gate_id", "current_gate"),
    [("not-a-gate", "G1"), ("G2", "G1")],
)
def test_gate_decision_rejects_invalid_or_noncurrent_gate_identifier(
    gate_id: str, current_gate: str
) -> None:
    run = replace(_run(), gate=replace(_run().gate, gate_id=current_gate))

    with pytest.raises(NebulaError) as caught:
        decide_gate(
            run,
            gate_id=gate_id,
            decision=DecisionKind.HOLD,
            reason="bounded reason",
            actor=ACTOR,
            now=LATER,
        )

    assert caught.value.code is ErrorCode.GATE_BLOCKED


@pytest.mark.parametrize("reason", [None, "", "   ", "\t\r\n"])
def test_hold_requires_nonblank_reason(reason: str | None) -> None:
    with pytest.raises(NebulaError) as caught:
        decide_gate(
            _run(),
            gate_id="G1",
            decision=DecisionKind.HOLD,
            reason=reason,
            actor=ACTOR,
            now=LATER,
        )
    assert caught.value.code is ErrorCode.GATE_BLOCKED


def test_hold_reason_is_control_character_stripped() -> None:
    held = decide_gate(
        _run(),
        gate_id="G1",
        decision=DecisionKind.HOLD,
        reason="\x00 investigate\x1b[31m failure \x7f",
        actor=ACTOR,
        now=LATER,
    )
    assert held.gate.decision is not None
    assert held.gate.decision.reason == "investigate failure"


def test_only_held_gate_can_resume() -> None:
    held = decide_gate(
        _run(),
        gate_id="G1",
        decision=DecisionKind.HOLD,
        reason="investigate",
        actor=ACTOR,
        now=LATER,
    )
    resumed = resume_gate(held, LATER)
    assert resumed.gate.status is GateStatus.PENDING
    assert resumed.gate.decision is None
    with pytest.raises(NebulaError):
        resume_gate(_run(), LATER)


@pytest.mark.parametrize("status", [RunStatus.ACTIVE, RunStatus.DETACHED_OR_EXITED])
def test_transcript_can_activate_only_for_recoverable_session(status: RunStatus) -> None:
    state = TranscriptState(
        TranscriptStatus.ACTIVE,
        RedactionStatus.PASSED,
        "/runtime/transcript.log",
        None,
        0,
    )
    updated = with_transcript(_run(status=status), state, LATER)
    assert updated.transcript is state


@pytest.mark.parametrize(
    "status",
    [RunStatus.PREFLIGHT_PENDING, RunStatus.LAUNCHING, RunStatus.FAILED, RunStatus.EXITED, RunStatus.UNKNOWN],
)
def test_transcript_activation_fails_for_nonrecoverable_session(status: RunStatus) -> None:
    state = TranscriptState(
        TranscriptStatus.ACTIVE,
        RedactionStatus.PASSED,
        "/runtime/transcript.log",
        None,
        0,
    )
    with pytest.raises(NebulaError) as caught:
        with_transcript(_run(status=status), state, LATER)
    assert caught.value.code is ErrorCode.TRANSCRIPT_UNAVAILABLE

from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime

from .enums import DecisionKind, GateStatus, RunStatus, TranscriptStatus
from .errors import ErrorCode, error
from .models import GateDecision, GateSnapshot, RunRecord, TranscriptState, ValidatorResult
from .redaction import StreamingRedactor, sanitize_terminal_text


_GATE_ID = re.compile(r"^G\d+$")


def require_revision(run: RunRecord, expected_revision: int) -> None:
    if run.revision != expected_revision:
        raise error(
            ErrorCode.STALE_REVISION,
            "The run changed after it was displayed",
            "conflict",
            "Refresh the run and retry with its current revision.",
            expected_revision=expected_revision,
            current_revision=run.revision,
        )


def advance(
    run: RunRecord,
    *,
    now: datetime,
    status: RunStatus | None = None,
    sequence_increment: int = 1,
    **changes: object,
) -> RunRecord:
    return replace(
        run,
        revision=run.revision + 1,
        last_event_sequence=run.last_event_sequence + sequence_increment,
        updated_at=now,
        status=status if status is not None else run.status,
        **changes,
    )


def mark_session_present(run: RunRecord, now: datetime) -> RunRecord:
    if run.status in (RunStatus.FAILED, RunStatus.EXITED):
        return run
    target = RunStatus.ACTIVE
    return advance(run, now=now, status=target, last_seen_at=now)


def mark_session_missing(run: RunRecord, now: datetime) -> RunRecord:
    if run.status in (RunStatus.FAILED, RunStatus.EXITED):
        return run
    return advance(run, now=now, status=RunStatus.DETACHED_OR_EXITED)


def with_validator(run: RunRecord, result: ValidatorResult, now: datetime) -> RunRecord:
    return advance(run, now=now, latest_validator=result)


def decide_gate(
    run: RunRecord,
    *,
    gate_id: str,
    decision: DecisionKind,
    reason: str | None,
    actor,
    now: datetime,
) -> RunRecord:
    if not _GATE_ID.fullmatch(gate_id):
        raise error(ErrorCode.GATE_BLOCKED, "Gate identifier is invalid", "gate-blocked", "Select a known lifecycle gate.")
    if run.gate.gate_id not in (None, gate_id):
        raise error(ErrorCode.GATE_BLOCKED, "The requested gate is not current", "gate-blocked", "Refresh the gate state.")
    if run.gate.status is not GateStatus.PENDING:
        raise error(ErrorCode.GATE_BLOCKED, "The gate is not pending", "gate-blocked", "Resume a held gate or refresh its state.")
    clean_reason = None
    if reason:
        redactor = StreamingRedactor()
        redacted = redactor.feed(reason.encode("utf-8", errors="replace")) + redactor.finalize()
        clean_reason = sanitize_terminal_text(
            redacted.decode("utf-8", errors="replace"), max_chars=2_000, max_lines=40,
        )[0].strip()
    if decision is DecisionKind.HOLD and not clean_reason:
        raise error(ErrorCode.GATE_BLOCKED, "A hold requires a reason", "gate-blocked", "Provide a concise hold reason.")
    if decision is DecisionKind.APPROVE:
        if not run.gate.evidence_ready or run.latest_validator is None or run.latest_validator.exit_code != 0:
            raise error(ErrorCode.GATE_BLOCKED, "Required evidence or validator results are not ready", "gate-blocked", "Run the required validators and resolve evidence findings.")
    snapshot = GateSnapshot(
        gate_id=gate_id,
        status=GateStatus.APPROVED if decision is DecisionKind.APPROVE else GateStatus.HELD,
        evidence_ready=run.gate.evidence_ready,
        required_evidence=run.gate.required_evidence,
        decision=GateDecision(decision, clean_reason, actor, now, run.revision),
    )
    return advance(run, now=now, gate=snapshot)


def resume_gate(run: RunRecord, now: datetime) -> RunRecord:
    if run.gate.status is not GateStatus.HELD:
        raise error(ErrorCode.GATE_BLOCKED, "Only a held gate can be resumed", "gate-blocked", "Refresh the gate state.")
    return advance(run, now=now, gate=replace(run.gate, status=GateStatus.PENDING, decision=None))


def with_transcript(run: RunRecord, state: TranscriptState, now: datetime) -> RunRecord:
    if state.status is TranscriptStatus.ACTIVE and run.status not in (RunStatus.ACTIVE, RunStatus.DETACHED_OR_EXITED):
        raise error(ErrorCode.TRANSCRIPT_UNAVAILABLE, "Transcript capture requires a recoverable session", "conflict", "Launch or recover the session first.")
    return advance(run, now=now, transcript=state)

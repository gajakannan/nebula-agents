from __future__ import annotations

import os
import re
import stat
import time
from pathlib import Path

from nebula_agents.domain.enums import Action, RedactionStatus, Role, TranscriptStatus
from nebula_agents.domain.errors import ErrorCode, error
from nebula_agents.domain.models import Actor, AuthorizationResource, RunRecord, TranscriptProjection, TranscriptState
from nebula_agents.domain.redaction import REDACTION_MARKER, sanitize_terminal_text
from nebula_agents.domain.transitions import with_transcript

from .authorization import AuthorizationService
from .ports import Clock, RunRepository, TranscriptPipePort
from .runs import (
    authoritative_after_commit_error,
    capture_compensation_error,
    commit_authorized,
    persist_truthful_capture_active,
    require_authorized,
    runtime_event,
    stop_and_verify_capture,
    terminate_and_verify_owning_session,
    unresolved_commit_outcome,
)


_FAILURE_CATEGORY = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


def _failure_reason(value: object, fallback: str) -> str:
    candidate = str(value) if value is not None else fallback
    return candidate if _FAILURE_CATEGORY.fullmatch(candidate) else fallback


class TranscriptService:
    def __init__(self, *, repository: RunRepository, authorization: AuthorizationService, pipe: TranscriptPipePort, clock: Clock) -> None:
        self._repository = repository
        self._authorization = authorization
        self._pipe = pipe
        self._clock = clock

    @staticmethod
    def _resource(run: RunRecord) -> AuthorizationResource:
        return AuthorizationResource(run.workspace_root, run.owner.uid, run.run_id)

    def _reconcile_pipe_after_commit_error(
        self,
        run_id: str,
        *,
        pipe_may_be_active: bool,
        restore_if_active: bool,
        actor: Actor | None = None,
        active_path: Path | None = None,
        fallback_current: RunRecord | None = None,
        operation: str = "transcript-commit",
    ) -> RunRecord:
        """Make external capture agree with the recovered durable transition."""
        try:
            authoritative = authoritative_after_commit_error(self._repository, run_id)
        except Exception as exc:
            if pipe_may_be_active and fallback_current is not None:
                terminated = terminate_and_verify_owning_session(
                    self._pipe,
                    fallback_current,
                )
                if not terminated.verified_absent:
                    raise unresolved_commit_outcome(
                        run_id,
                        f"{operation}-recovery-session-termination",
                    ) from (terminated.cause or exc)
                raise unresolved_commit_outcome(
                    run_id,
                    f"{operation}-recovery",
                ) from exc
            raise unresolved_commit_outcome(run_id, "transcript-reconciliation") from exc

        if authoritative.transcript.status is TranscriptStatus.ACTIVE:
            if restore_if_active and authoritative.transcript.path is not None:
                try:
                    self._pipe.configure(
                        run=authoritative,
                        output_path=Path(authoritative.transcript.path),
                    )
                except Exception:
                    # The durable Active fact is authoritative. Startup/status
                    # reconciliation will consume the terminal sidecar if the
                    # bounded pipe restoration is unavailable.
                    pass
        elif pipe_may_be_active:
            stopped = stop_and_verify_capture(self._pipe, authoritative)
            if not stopped.verified_stopped:
                if actor is None or active_path is None:
                    raise unresolved_commit_outcome(
                        run_id,
                        f"{operation}-missing-active-compensation-context",
                    )
                persist_truthful_capture_active(
                    self._repository,
                    self._authorization,
                    self._pipe,
                    current=authoritative,
                    actor=actor,
                    path=active_path,
                    now=self._clock.now(),
                    operation=operation,
                )
                raise capture_compensation_error(run_id, operation) from stopped.cause
        return authoritative

    def _commit_terminal(
        self,
        *,
        current: RunRecord,
        changed: RunRecord,
        event,
        actor: Actor,
    ) -> RunRecord:
        try:
            return commit_authorized(
                self._repository,
                self._authorization,
                expected_revision=current.revision,
                next_record=changed,
                event=event,
                actor=actor,
                action=Action.CONFIGURE_TRANSCRIPT,
            )
        except Exception:
            # Completion/failure stops the pipe before committing. A recovered
            # terminal fact must never be overwritten externally by restarting
            # capture; only a provably Active current snapshot is restored.
            self._reconcile_pipe_after_commit_error(
                current.run_id,
                pipe_may_be_active=False,
                restore_if_active=True,
            )
            raise

    def enable(self, run_id: str, actor: Actor, expected_revision: int) -> RunRecord:
        run = self._repository.load(run_id)
        require_authorized(self._repository, self._authorization, run, actor, Action.CONFIGURE_TRANSCRIPT)
        if run.revision != expected_revision:
            raise error(ErrorCode.STALE_REVISION, "The run changed after it was displayed", "conflict", "Refresh and retry.")
        path = self._repository.run_directory(run_id) / "transcript.redacted.log"
        now = self._clock.now()
        state = TranscriptState(TranscriptStatus.ACTIVE, RedactionStatus.NOT_RUN, str(path), None, 0)
        changed = with_transcript(run, state, now)
        try:
            self._pipe.configure(run=run, output_path=path)
        except Exception as exc:
            stopped = stop_and_verify_capture(self._pipe, run)
            if not stopped.verified_stopped:
                persist_truthful_capture_active(
                    self._repository,
                    self._authorization,
                    self._pipe,
                    current=run,
                    actor=actor,
                    path=path,
                    now=self._clock.now(),
                    operation="transcript-configure-failure",
                )
                raise capture_compensation_error(
                    run_id,
                    "transcript-configure-failure",
                ) from (stopped.cause or exc)
            failed_at = self._clock.now()
            reason = _failure_reason(getattr(exc, "category", None), "capture-configuration-failed")
            failed_state = TranscriptState(TranscriptStatus.FAILED, RedactionStatus.FAILED, str(path), None, 0, reason)
            failed = with_transcript(run, failed_state, failed_at)
            try:
                self._commit_terminal(
                    current=run,
                    changed=failed,
                    event=runtime_event(
                        run,
                        actor,
                        "TranscriptFailed",
                        failed_at,
                        {"status": failed_state.status.value, "error_category": reason},
                    ),
                    actor=actor,
                )
            except Exception:
                # Preserve the capture failure after the ambiguous durable
                # outcome has been reconciled. Capture was already verified
                # stopped before this failure transition was attempted.
                pass
            raise
        try:
            return commit_authorized(
                self._repository,
                self._authorization,
                expected_revision=run.revision,
                next_record=changed,
                event=runtime_event(run, actor, "TranscriptEnabled", now, {"path": path.name, "status": state.status.value}),
                actor=actor,
                action=Action.CONFIGURE_TRANSCRIPT,
            )
        except Exception:
            self._reconcile_pipe_after_commit_error(
                run_id,
                pipe_may_be_active=True,
                restore_if_active=False,
                actor=actor,
                active_path=path,
                fallback_current=run,
                operation="transcript-enable-commit",
            )
            raise

    def complete(self, run_id: str, actor: Actor, expected_revision: int) -> RunRecord:
        run = self._repository.load(run_id)
        require_authorized(self._repository, self._authorization, run, actor, Action.CONFIGURE_TRANSCRIPT)
        if run.revision != expected_revision:
            raise error(ErrorCode.STALE_REVISION, "The run changed after it was displayed", "conflict", "Refresh and retry.")
        if run.transcript.status is not TranscriptStatus.ACTIVE:
            return run
        capture_status = getattr(self._pipe, "capture_status", None)
        observed = None
        if callable(capture_status):
            try:
                observed = capture_status(run=run)
            except Exception:
                observed = TranscriptState(
                    TranscriptStatus.FAILED,
                    RedactionStatus.FAILED,
                    run.transcript.path,
                    None,
                    run.transcript.redaction_findings,
                    "capture-status-unavailable",
                )
        if observed is not None and observed.status is TranscriptStatus.FAILED:
            stopped = stop_and_verify_capture(self._pipe, run)
            if not stopped.verified_stopped:
                raise capture_compensation_error(
                    run_id,
                    "transcript-observed-failure",
                ) from stopped.cause
            failed_at = self._clock.now()
            failed = with_transcript(run, observed, failed_at)
            return self._commit_terminal(
                current=run,
                changed=failed,
                event=runtime_event(
                    run,
                    actor,
                    "TranscriptFailed",
                    failed_at,
                    {"status": observed.status.value, "error_category": observed.failure_reason or "filter-process-failed"},
                ),
                actor=actor,
            )
        # Stop the writer before inspecting its durable output so the findings
        # count includes the redactor's finalized tail.
        stopped = stop_and_verify_capture(self._pipe, run)
        if not stopped.verified_stopped:
            raise capture_compensation_error(
                run_id,
                "transcript-completion",
            ) from stopped.cause
        now = self._clock.now()
        if callable(capture_status):
            terminal = None
            for attempt in range(21):
                try:
                    terminal = capture_status(run=run)
                except Exception:
                    terminal = TranscriptState(
                        TranscriptStatus.FAILED,
                        RedactionStatus.FAILED,
                        run.transcript.path,
                        None,
                        run.transcript.redaction_findings,
                        "capture-status-unavailable",
                    )
                if terminal is not None and terminal.status in (TranscriptStatus.COMPLETED, TranscriptStatus.FAILED):
                    break
                if attempt < 20:
                    time.sleep(0.025)
            if terminal is None or terminal.status is not TranscriptStatus.COMPLETED:
                failed_state = TranscriptState(
                    TranscriptStatus.FAILED,
                    RedactionStatus.FAILED,
                    run.transcript.path,
                    None,
                    max(run.transcript.redaction_findings, terminal.redaction_findings if terminal else 0),
                    terminal.failure_reason if terminal is not None else "capture-completion-timeout",
                )
                failed = with_transcript(run, failed_state, now)
                return self._commit_terminal(
                    current=run,
                    changed=failed,
                    event=runtime_event(
                        run,
                        actor,
                        "TranscriptFailed",
                        now,
                        {"status": failed_state.status.value, "error_category": failed_state.failure_reason or "filter-process-failed"},
                    ),
                    actor=actor,
                )
            findings = max(self._findings(run), terminal.redaction_findings)
            state = TranscriptState(
                TranscriptStatus.COMPLETED,
                terminal.redaction_status,
                run.transcript.path,
                None,
                findings,
            )
            changed = with_transcript(run, state, now)
            return self._commit_terminal(
                current=run,
                changed=changed,
                event=runtime_event(
                    run,
                    actor,
                    "TranscriptCompleted",
                    now,
                    {"status": state.status.value, "redaction_findings": state.redaction_findings},
                ),
                actor=actor,
            )
        findings = self._findings(run)
        redaction = RedactionStatus.REDACTED if findings else RedactionStatus.PASSED
        state = TranscriptState(TranscriptStatus.COMPLETED, redaction, run.transcript.path, None, findings)
        changed = with_transcript(run, state, now)
        return self._commit_terminal(
            current=run,
            changed=changed,
            event=runtime_event(
                run,
                actor,
                "TranscriptCompleted",
                now,
                {"status": state.status.value, "redaction_findings": state.redaction_findings},
            ),
            actor=actor,
        )

    @staticmethod
    def _findings(run: RunRecord) -> int:
        """Recover persisted redaction markers without trusting an unsafe path."""
        if run.transcript.path is None:
            return run.transcript.redaction_findings
        path = Path(run.transcript.path)
        if path.is_symlink() or not path.exists():
            return run.transcript.redaction_findings
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                details = os.fstat(fd)
                if not stat.S_ISREG(details.st_mode) or details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) != 0o600:
                    return run.transcript.redaction_findings
                findings = 0
                overlap = b""
                while True:
                    chunk = os.read(fd, 64 * 1024)
                    if not chunk:
                        break
                    payload = overlap + chunk
                    findings += payload.count(REDACTION_MARKER)
                    overlap = payload[-(len(REDACTION_MARKER) - 1):]
                return max(run.transcript.redaction_findings, findings)
            finally:
                os.close(fd)
        except OSError:
            return run.transcript.redaction_findings

    def preview(self, run_id: str, actor: Actor) -> TranscriptProjection:
        run = self._repository.load(run_id)
        require_authorized(self._repository, self._authorization, run, actor, Action.READ_STATE)
        state = run.transcript
        if state.status is not TranscriptStatus.COMPLETED or state.redaction_status not in (RedactionStatus.PASSED, RedactionStatus.REDACTED) or state.path is None:
            raise error(ErrorCode.TRANSCRIPT_UNAVAILABLE, "A safely completed transcript is not available", "not-found", "Complete redacted capture before previewing it.")
        path = Path(state.path)
        run_dir = self._repository.run_directory(run_id).resolve()
        if path.is_symlink() or path.name != "transcript.redacted.log":
            raise error(ErrorCode.PATH_DENIED, "Transcript path is outside the run directory", "state-io", "Restore the contained owner-only transcript.")
        try:
            resolved_parent = path.parent.resolve(strict=True)
        except OSError as exc:
            raise error(ErrorCode.TRANSCRIPT_UNAVAILABLE, "Transcript file is unavailable", "not-found", "Complete capture again before previewing it.") from exc
        if resolved_parent != run_dir:
            raise error(ErrorCode.PATH_DENIED, "Transcript path is outside the run directory", "state-io", "Restore the contained owner-only transcript.")
        resolved = resolved_parent / path.name
        try:
            fd = os.open(resolved, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        except FileNotFoundError as exc:
            raise error(ErrorCode.TRANSCRIPT_UNAVAILABLE, "Transcript file is unavailable", "not-found", "Complete capture again before previewing it.") from exc
        except OSError as exc:
            raise error(ErrorCode.PATH_DENIED, "Transcript file cannot be opened safely", "state-io", "Restore the contained owner-only transcript.") from exc
        try:
            details = os.fstat(fd)
            if not stat.S_ISREG(details.st_mode) or details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) != 0o600:
                raise error(ErrorCode.PATH_DENIED, "Transcript permissions are unsafe", "state-io", "Set the owner-only transcript mode to 0600.")
            payload = os.read(fd, 262_145)
        finally:
            os.close(fd)
        raw = payload[:262_144].decode("utf-8", errors="replace")
        preview, truncated = sanitize_terminal_text(raw)
        may_disclose_path = actor.role is Role.LOCAL_OPERATOR and actor.uid == run.owner.uid
        if not may_disclose_path:
            may_disclose_path = self._authorization.authorize(
                actor, Action.CONFIGURE_TRANSCRIPT, self._resource(run),
            ).allowed
        return TranscriptProjection(
            run_id,
            state.status,
            state.redaction_status,
            preview,
            str(resolved) if may_disclose_path else None,
            truncated or len(payload) > 262_144 or details.st_size > 262_144,
        )

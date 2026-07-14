from __future__ import annotations

import json
import os
import re
import secrets
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Mapping
from collections.abc import Callable
from uuid import uuid4

from nebula_agents.domain.enums import (
    Action,
    ArtifactStatus,
    GateStatus,
    PromptAction,
    RedactionStatus,
    Role,
    RunStatus,
    TranscriptStatus,
)
from nebula_agents.domain.errors import ErrorCode, NebulaError, error
from nebula_agents.domain.path_contracts import governed_feature_root, governed_story_file
from nebula_agents.domain.models import (
    Actor,
    AuthorizationContext,
    AuthorizationResource,
    GateSnapshot,
    JsonValue,
    LaunchDescriptor,
    LaunchRequest,
    RunProjection,
    RunRecord,
    RuntimeEvent,
    TranscriptState,
    serialize_record,
)
from nebula_agents.domain.transitions import advance, mark_session_missing, mark_session_present, with_transcript

from .authorization import AuthorizationService, safe_run_projection
from .ports import Clock, EvidenceWatcher, ProviderAdapter, RunRepository, SchemaPort, TmuxPort, TranscriptPipePort
from .preflight import PreflightService, read_committed_prompt


_FEATURE = re.compile(r"^F\d{4}$")
_STORY = re.compile(r"^(F\d{4})-S\d{4}$")
_RUN = re.compile(r"^\d{4}-\d{2}-\d{2}-[0-9a-f]{8}$")
_LABEL_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_PROMPT_FEATURE = re.compile(r"FEATURE_ID=\{F(?:####|\d{4})\}")
_PROMPT_BUILD_SCOPE = re.compile(r"BUILD_SCOPE=\[\{F####\}(?:,\s*\{F####\})*[^\]]*\]")


def runtime_event(
    run: RunRecord,
    actor: Actor,
    event_type: str,
    now: datetime,
    payload: Mapping[str, JsonValue] | None = None,
    *,
    sequence: int | None = None,
) -> RuntimeEvent:
    return RuntimeEvent("1.0", run.run_id, sequence or run.last_event_sequence + 1, event_type, now, actor, uuid4(), payload or {})


def require_authorized(
    repository: RunRepository,
    authorization: AuthorizationService,
    run: RunRecord,
    actor: Actor,
    action: Action,
    context: AuthorizationContext | None = None,
) -> None:
    """Authorize an existing run and audit denials when the repository supports it."""
    resource = AuthorizationResource(run.workspace_root, run.owner.uid, run.run_id)
    try:
        authorization.require(actor, action, resource, context)
    except NebulaError:
        recorder = getattr(repository, "record_authorization_denied", None)
        if callable(recorder):
            try:
                recorder(run.run_id, actor, action, datetime.now().astimezone())
            except Exception:
                # An audit persistence failure must not turn a denial into access.
                pass
        raise


def commit_authorized(
    repository: RunRepository,
    authorization: AuthorizationService,
    *,
    expected_revision: int,
    next_record: RunRecord,
    event: RuntimeEvent,
    actor: Actor,
    action: Action,
    context: AuthorizationContext | None = None,
    validate_current: Callable[[RunRecord], None] | None = None,
    validation_record: RunRecord | None = None,
) -> RunRecord:
    """Re-authorize under the concrete repository lock when that seam is available."""
    method = getattr(repository, "commit_authorized", None)
    if not callable(method):
        if validate_current is not None:
            validate_current(validation_record or next_record)
        return repository.commit(expected_revision=expected_revision, next_record=next_record, event=event)

    def authorize(current: RunRecord) -> None:
        authorization.require(
            actor,
            action,
            AuthorizationResource(current.workspace_root, current.owner.uid, current.run_id),
            context,
        )
        if validate_current is not None:
            validate_current(current)

    return method(
        expected_revision=expected_revision,
        next_record=next_record,
        event=event,
        authorize=authorize,
        denied_actor=actor,
        denied_action=action,
    )


def authoritative_after_commit_error(repository: RunRepository, run_id: str) -> RunRecord:
    """Resolve an ambiguous commit against the event log and recovery images.

    Filesystem commits publish an event and a matching state image before the
    latest snapshot is replaced.  A plain snapshot reload can therefore be one
    transition behind after an I/O exception.  Recovery is the authoritative
    read at this boundary; lightweight repository test doubles may fall back to
    their current in-memory snapshot.
    """
    recover = getattr(repository, "recover", None)
    if callable(recover):
        return recover(run_id)
    return repository.load(run_id)


def unresolved_commit_outcome(run_id: str, operation: str) -> NebulaError:
    return error(
        ErrorCode.STATE_IO,
        "The durable operation outcome could not be established safely",
        "state-io",
        "Inspect the recovered run timeline before retrying the operation.",
        run_id=run_id,
        operation=operation,
    )


def capture_compensation_error(run_id: str, operation: str) -> NebulaError:
    return error(
        ErrorCode.STATE_IO,
        "Transcript capture could not be stopped safely",
        "state-io",
        "Treat capture as active and inspect the run before retrying.",
        run_id=run_id,
        operation=operation,
    )


@dataclass(frozen=True, slots=True)
class CaptureStopResult:
    active: bool | None
    disable_error: Exception | None = None
    probe_error: Exception | None = None

    @property
    def verified_stopped(self) -> bool:
        return self.disable_error is None and self.probe_error is None and self.active is False

    @property
    def cause(self) -> Exception | None:
        return self.disable_error or self.probe_error


def stop_and_verify_capture(pipe: TranscriptPipePort, run: RunRecord) -> CaptureStopResult:
    """Stop capture and prove tmux no longer has an active pane pipe."""
    disable_error: Exception | None = None
    try:
        pipe.disable(run=run)
    except Exception as exc:
        disable_error = exc

    probe = getattr(pipe, "is_active", None)
    if not callable(probe):
        return CaptureStopResult(None, disable_error=disable_error)
    try:
        active = bool(probe(run=run))
    except Exception as exc:
        return CaptureStopResult(None, disable_error=disable_error, probe_error=exc)
    return CaptureStopResult(active, disable_error=disable_error)


@dataclass(frozen=True, slots=True)
class SessionTerminationResult:
    present: bool | None
    termination_error: Exception | None = None
    probe_error: Exception | None = None

    @property
    def verified_absent(self) -> bool:
        return self.probe_error is None and self.present is False

    @property
    def cause(self) -> Exception | None:
        return self.termination_error or self.probe_error


def terminate_and_verify_owning_session(
    pipe: TranscriptPipePort,
    run: RunRecord,
) -> SessionTerminationResult:
    """Last-resort capture compensation through the immutable owning session."""
    terminate = getattr(pipe, "terminate_session", None)
    present = getattr(pipe, "session_present", None)
    if not callable(terminate) or not callable(present):
        return SessionTerminationResult(None)
    termination_error: Exception | None = None
    try:
        terminate(run=run)
    except Exception as exc:
        termination_error = exc
    try:
        is_present = bool(present(run=run))
    except Exception as exc:
        return SessionTerminationResult(
            None,
            termination_error=termination_error,
            probe_error=exc,
        )
    return SessionTerminationResult(is_present, termination_error=termination_error)


def persist_truthful_capture_active(
    repository: RunRepository,
    authorization: AuthorizationService,
    pipe: TranscriptPipePort,
    *,
    current: RunRecord,
    actor: Actor,
    path: Path,
    now: datetime,
    operation: str,
) -> RunRecord:
    """Record possibly-live capture after external stop compensation failed."""
    state = TranscriptState(
        TranscriptStatus.ACTIVE,
        RedactionStatus.NOT_RUN,
        str(path),
        None,
        current.transcript.redaction_findings,
    )
    changed = with_transcript(current, state, now)
    try:
        return commit_authorized(
            repository,
            authorization,
            expected_revision=current.revision,
            next_record=changed,
            event=runtime_event(
                current,
                actor,
                "TranscriptEnabled",
                now,
                {
                    "status": state.status.value,
                    "path": path.name,
                    "compensation": "disable-unverified",
                    "commit_outcome": "compensating-active",
                    "external_capture": "possibly-active",
                    "operation": operation,
                },
            ),
            actor=actor,
            action=Action.CONFIGURE_TRANSCRIPT,
        )
    except Exception as exc:
        try:
            authoritative = authoritative_after_commit_error(repository, current.run_id)
        except Exception as reconciliation_exc:
            terminated = terminate_and_verify_owning_session(pipe, current)
            if not terminated.verified_absent:
                raise unresolved_commit_outcome(
                    current.run_id,
                    f"{operation}-active-compensation-session-termination",
                ) from (terminated.cause or reconciliation_exc)
            raise unresolved_commit_outcome(
                current.run_id,
                f"{operation}-active-compensation-reconciliation",
            ) from reconciliation_exc
        if authoritative.transcript.status is TranscriptStatus.ACTIVE:
            return authoritative
        terminated = terminate_and_verify_owning_session(pipe, authoritative)
        if not terminated.verified_absent:
            raise unresolved_commit_outcome(
                current.run_id,
                f"{operation}-active-compensation-session-termination",
            ) from (terminated.cause or exc)
        raise unresolved_commit_outcome(
            current.run_id,
            f"{operation}-active-compensation",
        ) from exc


def bind_prompt(prompt_text: str, request: LaunchRequest) -> str:
    """Bind committed prompt placeholders without interpreting the prompt as shell text."""
    bound, feature_replacements = _PROMPT_FEATURE.subn(f"FEATURE_ID={request.feature_id}", prompt_text)
    scope_replacements = 0
    if request.prompt_action is PromptAction.BUILD:
        bound, scope_replacements = _PROMPT_BUILD_SCOPE.subn(f"BUILD_SCOPE=[{request.feature_id}]", bound)
    if request.story_id is not None and (feature_replacements or scope_replacements):
        bound = f"{bound.rstrip()}\n\nCOCKPIT_STORY_FOCUS={request.story_id}\n"
    return bound


class RunService:
    def __init__(
        self,
        *,
        workspace_root: Path,
        preflight: PreflightService,
        authorization: AuthorizationService,
        repository: RunRepository,
        providers: Mapping,
        tmux: TmuxPort,
        schema: SchemaPort,
        clock: Clock,
        watcher: EvidenceWatcher | None = None,
        transcript_pipe: TranscriptPipePort | None = None,
    ) -> None:
        self._workspace = workspace_root.expanduser().resolve()
        self._preflight = preflight
        self._authorization = authorization
        self._repository = repository
        self._providers: dict = dict(providers)
        self._tmux = tmux
        self._schema = schema
        self._clock = clock
        self._watcher = watcher
        self._transcript_pipe = transcript_pipe

    def _resolve_feature(self, feature_id: str, story_id: str | None) -> Path:
        if not _FEATURE.fullmatch(feature_id):
            raise error(ErrorCode.USAGE_ERROR, "Feature identifier is invalid", "usage", "Use an F followed by four digits.")
        feature_root = governed_feature_root(self._workspace, feature_id)
        if feature_root is None:
            raise error(ErrorCode.PROMPT_NOT_FOUND, "Feature folder was not found uniquely", "not-found", "Check the feature registry and folder name.")
        if story_id is not None:
            match = _STORY.fullmatch(story_id)
            if match is None or match.group(1) != feature_id:
                raise error(ErrorCode.USAGE_ERROR, "Story identifier does not belong to the feature", "usage", "Use the full feature-prefixed story ID.")
            if governed_story_file(feature_root, story_id) is None:
                raise error(ErrorCode.PROMPT_NOT_FOUND, "Story file was not found", "not-found", "Select a committed story.")
        return feature_root

    def _run_id(self, requested: str | None, now: datetime) -> str:
        value = requested or f"{now.astimezone().date().isoformat()}-{secrets.token_hex(4)}"
        if not _RUN.fullmatch(value):
            raise error(ErrorCode.USAGE_ERROR, "Run identifier is invalid", "usage", "Use YYYY-MM-DD-8hex.")
        return value

    def launch(self, request: LaunchRequest, actor: Actor) -> RunRecord:
        now = self._clock.now()
        self._resolve_feature(request.feature_id, request.story_id)
        if request.run_label is not None:
            clean = _LABEL_CONTROL.sub("", request.run_label).strip()
            if clean != request.run_label.strip() or not clean or len(clean) > 80:
                raise error(ErrorCode.USAGE_ERROR, "Run label contains unsupported characters", "usage", "Use 1-80 printable characters.")
        self._authorization.require(actor, Action.LAUNCH, AuthorizationResource(str(self._workspace), actor.uid))
        if request.transcript_enabled:
            self._authorization.require(actor, Action.CONFIGURE_TRANSCRIPT, AuthorizationResource(str(self._workspace), actor.uid))
        preflight = self._preflight.require_ready(self._workspace, self._repository.runtime_root, request.provider_key, request.prompt_action)
        provider: ProviderAdapter | None = self._providers.get(request.provider_key)
        if provider is None:
            raise error(ErrorCode.PROVIDER_NOT_FOUND, "Provider is not registered", "preflight", "Choose codex or claude.")

        run_id = self._run_id(request.requested_run_id, now)
        suffix = run_id.rsplit("-", 1)[1]
        tmux_name = f"nebula-{request.feature_id}-{suffix}"
        if self._tmux.has_session(tmux_name):
            raise error(
                ErrorCode.CONFLICT,
                "The generated tmux session already exists",
                "conflict",
                "Choose a different run identifier.",
                colliding_session=tmux_name[:80],
            )
        try:
            prompt_path, prompt_text = read_committed_prompt(
                self._workspace,
                request.prompt_action,
                preflight.prompt_contract_path,
            )
        except (OSError, UnicodeDecodeError) as exc:
            raise error(ErrorCode.PROMPT_NOT_FOUND, "Prompt contract cannot be read", "preflight", "Restore the committed prompt contract.") from exc
        provider_argv = provider.build_interactive_argv(self._workspace, bind_prompt(prompt_text, request))
        executable = str(Path(provider_argv[0]).resolve(strict=True))
        if executable != provider_argv[0]:
            provider_argv = (executable, *provider_argv[1:])

        evidence_candidate = self._workspace / "planning-mds" / "operations" / "evidence" / "runs" / run_id
        evidence_root = str(evidence_candidate) if evidence_candidate.is_dir() else None
        run_directory = self._repository.run_directory(run_id)
        transcript_path = run_directory / "transcript.redacted.log"
        transcript = TranscriptState(
            TranscriptStatus.DISABLED,
            RedactionStatus.NOT_RUN,
            str(transcript_path) if request.transcript_enabled else None,
            None,
            0,
        )
        record = RunRecord(
            schema_version="1.0",
            revision=0,
            run_id=run_id,
            feature_id=request.feature_id,
            story_id=request.story_id,
            provider_key=request.provider_key,
            tmux_session=tmux_name,
            workspace_root=str(self._workspace),
            prompt_contract=str(prompt_path),
            prompt_action=request.prompt_action,
            status=RunStatus.LAUNCHING,
            owner=actor,
            evidence_root=evidence_root,
            gate=GateSnapshot("G0", GateStatus.PENDING, False, ("g0-assembly-plan-validation.md",), None),
            latest_validator=None,
            artifacts=(),
            transcript=transcript,
            audit_log_path=str(run_directory / "events.jsonl"),
            last_event_sequence=1,
            created_at=now,
            updated_at=now,
            last_seen_at=None,
        )
        requested_event = runtime_event(record, actor, "LaunchRequested", now, {
            "provider_key": request.provider_key.value,
            "feature_id": request.feature_id,
            "story_id": request.story_id,
            "action": request.prompt_action.value,
            "tmux_session": tmux_name,
            "command_template": f"{request.provider_key.value} <committed-action-prompt>",
        }, sequence=1)
        self._repository.create(record, requested_event)

        descriptor_path = run_directory / "launch-descriptor.json"
        session_created = False
        launch_commit_attempted = False
        launched_candidate: RunRecord | None = None
        try:
            descriptor = LaunchDescriptor(
                "1.0", run_id, request.provider_key, executable, tuple(provider_argv), str(self._workspace),
                ("PATH", "HOME", "SHELL", "USER", "LOGNAME", "TERM", "COLORTERM", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "CODEX_HOME", "CLAUDE_CONFIG_DIR"),
                actor.uid, uuid4(), now,
            )
            descriptor_doc = serialize_record(descriptor)
            self._schema.validate("f0001-launch-descriptor.schema.json", descriptor_doc)
            fd = os.open(
                descriptor_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                remaining = memoryview((json.dumps(descriptor_doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())
                while remaining:
                    written = os.write(fd, remaining)
                    if written <= 0:
                        raise OSError("launch descriptor write did not progress")
                    remaining = remaining[written:]
                os.fsync(fd)
            finally:
                os.close(fd)
            self._tmux.create_session(tmux_name, descriptor_path)
            session_created = True
            if not self._tmux.has_session(tmux_name):
                raise error(ErrorCode.COMMAND_FAILED, "Provider session exited before launch completed", "command-failed", "Run doctor and inspect the sanitized run timeline.")
            launched_at = self._clock.now()
            launched = advance(record, now=launched_at, status=RunStatus.ACTIVE, last_seen_at=launched_at)
            launched_candidate = launched
            launch_commit_attempted = True
            launched = self._repository.commit(
                expected_revision=record.revision,
                next_record=launched,
                event=runtime_event(record, actor, "RunLaunched", launched_at, {"tmux_session": tmux_name, "provider_key": request.provider_key.value}),
            )
        except Exception as exc:
            try:
                authoritative = authoritative_after_commit_error(self._repository, run_id)
            except Exception as reconciliation_exc:
                raise unresolved_commit_outcome(run_id, "launch-reconciliation") from reconciliation_exc

            launched_published = bool(
                launch_commit_attempted
                and launched_candidate is not None
                and authoritative.revision >= launched_candidate.revision
                and authoritative.last_event_sequence >= launched_candidate.last_event_sequence
                and authoritative.status is not RunStatus.LAUNCHING
            )
            failed_at = self._clock.now()
            compensation = "not-required"
            try:
                if session_created or self._tmux.has_session(tmux_name):
                    compensation = "failed"
                    self._tmux.kill_session(tmux_name)
                    compensation = "completed" if not self._tmux.has_session(tmux_name) else "failed"
            except Exception:
                compensation = "failed"
            if compensation == "failed":
                # Keep an already-published Active fact consistent with the
                # still-live session.  Terminalizing it here would create an
                # untracked provider process.
                raise unresolved_commit_outcome(run_id, "launch-session-compensation") from exc

            if authoritative.status not in (RunStatus.FAILED, RunStatus.EXITED):
                failed = advance(authoritative, now=failed_at, status=RunStatus.FAILED)
                payload: dict[str, JsonValue] = {
                    "error_category": getattr(exc, "category", "command-failed"),
                    "session_compensation": compensation,
                    "commit_outcome": "published" if launched_published else "not-published",
                }
                if launched_published:
                    payload["compensated_event"] = "RunLaunched"
                try:
                    self._repository.commit(
                        expected_revision=authoritative.revision,
                        next_record=failed,
                        event=runtime_event(authoritative, actor, "LaunchFailed", failed_at, payload),
                    )
                except Exception as compensation_exc:
                    try:
                        reconciled = authoritative_after_commit_error(self._repository, run_id)
                    except Exception as reconciliation_exc:
                        raise unresolved_commit_outcome(run_id, "launch-failure-reconciliation") from reconciliation_exc
                    if reconciled.status not in (RunStatus.FAILED, RunStatus.EXITED):
                        if launched_published:
                            raise unresolved_commit_outcome(run_id, "launch-terminal-compensation") from compensation_exc
                        # Launching plus an absent session is a durable,
                        # attach-disabled fact. Preserve the primary failure.
            if descriptor_path.exists():
                descriptor_path.unlink(missing_ok=True)
            raise
        if not request.transcript_enabled:
            return launched
        transcript_at = self._clock.now()
        if self._transcript_pipe is None:
            transcript_state = TranscriptState(TranscriptStatus.FAILED, RedactionStatus.FAILED, str(transcript_path), None, 0, "adapter-unavailable")
            transcript_run = with_transcript(launched, transcript_state, transcript_at)
            return commit_authorized(
                self._repository,
                self._authorization,
                expected_revision=launched.revision,
                next_record=transcript_run,
                event=runtime_event(launched, actor, "TranscriptFailed", transcript_at, {"status": transcript_state.status.value, "error_category": "adapter-unavailable"}),
                actor=actor,
                action=Action.CONFIGURE_TRANSCRIPT,
            )
        pipe_configured = False
        try:
            self._transcript_pipe.configure(run=launched, output_path=transcript_path)
            pipe_configured = True
            transcript_state = TranscriptState(TranscriptStatus.ACTIVE, RedactionStatus.NOT_RUN, str(transcript_path), None, 0)
            event_type = "TranscriptEnabled"
            payload = {"status": transcript_state.status.value, "path": transcript_path.name}
        except Exception as exc:
            # Capture failure is isolated from the already-active provider session.
            stopped = stop_and_verify_capture(self._transcript_pipe, launched)
            if not stopped.verified_stopped:
                persist_truthful_capture_active(
                    self._repository,
                    self._authorization,
                    self._transcript_pipe,
                    current=launched,
                    actor=actor,
                    path=transcript_path,
                    now=self._clock.now(),
                    operation="launch-transcript-configure-failure",
                )
                raise capture_compensation_error(
                    run_id,
                    "launch-transcript-configure-failure",
                ) from (stopped.cause or exc)
            failure_reason = getattr(exc, "category", "command-failed")
            if not isinstance(failure_reason, str) or re.fullmatch(r"[a-z][a-z0-9-]{0,63}", failure_reason) is None:
                failure_reason = "command-failed"
            transcript_state = TranscriptState(TranscriptStatus.FAILED, RedactionStatus.FAILED, str(transcript_path), None, 0, failure_reason)
            event_type = "TranscriptFailed"
            payload = {"status": transcript_state.status.value, "error_category": failure_reason}
        transcript_run = with_transcript(launched, transcript_state, transcript_at)
        try:
            return commit_authorized(
                self._repository,
                self._authorization,
                expected_revision=launched.revision,
                next_record=transcript_run,
                event=runtime_event(launched, actor, event_type, transcript_at, payload),
                actor=actor,
                action=Action.CONFIGURE_TRANSCRIPT,
            )
        except Exception:
            try:
                authoritative = authoritative_after_commit_error(
                    self._repository,
                    run_id,
                )
            except Exception as reconciliation_exc:
                if pipe_configured:
                    terminated = terminate_and_verify_owning_session(
                        self._transcript_pipe,
                        launched,
                    )
                    if not terminated.verified_absent:
                        raise unresolved_commit_outcome(
                            run_id,
                            "launch-transcript-enable-commit-recovery-session-termination",
                        ) from (terminated.cause or reconciliation_exc)
                    raise unresolved_commit_outcome(
                        run_id,
                        "launch-transcript-enable-commit-recovery",
                    ) from reconciliation_exc
                raise unresolved_commit_outcome(
                    run_id,
                    "launch-transcript-failure-commit-recovery",
                ) from reconciliation_exc
            if pipe_configured and authoritative.transcript.status is not TranscriptStatus.ACTIVE:
                stopped = stop_and_verify_capture(self._transcript_pipe, authoritative)
                if not stopped.verified_stopped:
                    persist_truthful_capture_active(
                        self._repository,
                        self._authorization,
                        self._transcript_pipe,
                        current=authoritative,
                        actor=actor,
                        path=transcript_path,
                        now=self._clock.now(),
                        operation="launch-transcript-enable-commit",
                    )
                    raise capture_compensation_error(
                        run_id,
                        "launch-transcript-enable-commit",
                    ) from stopped.cause
            raise

    def attach(self, run_id: str, actor: Actor) -> int:
        run = self._repository.load(run_id)
        require_authorized(self._repository, self._authorization, run, actor, Action.ATTACH)
        if run.status is not RunStatus.ACTIVE:
            raise error(ErrorCode.SESSION_NOT_FOUND, "The run is not attachable", "not-found", "Use status/recovery; terminal runs never advertise attach.")
        if not self._tmux.has_session(run.tmux_session):
            raise error(ErrorCode.SESSION_NOT_FOUND, "The recorded tmux session is not available", "not-found", "Use status/recovery; attach never launches a replacement.")
        now = self._clock.now()
        attached = advance(run, now=now, last_seen_at=now)
        commit_authorized(
            self._repository,
            self._authorization,
            expected_revision=run.revision,
            next_record=attached,
            event=runtime_event(run, actor, "SessionAttached", now, {"tmux_session": run.tmux_session}),
            actor=actor,
            action=Action.ATTACH,
        )
        return self._tmux.attach(run.tmux_session)

    def reconcile(self, run_id: str, actor: Actor) -> RunProjection:
        run = self._repository.load(run_id)
        require_authorized(self._repository, self._authorization, run, actor, Action.READ_STATE)
        persist = actor.role is Role.LOCAL_OPERATOR and actor.uid == run.owner.uid
        present = self._tmux.has_session(run.tmux_session)
        if not present:
            time.sleep(1.0)
            present = self._tmux.has_session(run.tmux_session)
        now = self._clock.now()
        if present:
            if run.status not in (RunStatus.ACTIVE, RunStatus.FAILED, RunStatus.EXITED):
                changed = mark_session_present(run, now)
                if persist:
                    run = commit_authorized(
                        self._repository,
                        self._authorization,
                        expected_revision=run.revision,
                        next_record=changed,
                        event=runtime_event(run, actor, "SessionRecovered", now, {"tmux_session": run.tmux_session, "status": changed.status.value}),
                        actor=actor,
                        action=Action.ATTACH,
                    )
                else:
                    run = replace(run, status=changed.status, last_seen_at=changed.last_seen_at)
        else:
            changed = mark_session_missing(run, now)
            if changed is not run:
                if persist:
                    run = commit_authorized(
                        self._repository,
                        self._authorization,
                        expected_revision=run.revision,
                        next_record=changed,
                        event=runtime_event(run, actor, "SessionMissing", now, {"tmux_session": run.tmux_session, "status": changed.status.value}),
                        actor=actor,
                        action=Action.ATTACH,
                    )
                else:
                    run = replace(run, status=changed.status, last_seen_at=changed.last_seen_at)

        capture_status = getattr(self._transcript_pipe, "capture_status", None)
        if run.transcript.status is TranscriptStatus.ACTIVE and callable(capture_status):
            try:
                observed_transcript = capture_status(run=run)
            except Exception:
                observed_transcript = TranscriptState(
                    TranscriptStatus.FAILED,
                    RedactionStatus.FAILED,
                    run.transcript.path,
                    None,
                    run.transcript.redaction_findings,
                    "filter-status-unavailable",
                )
            if observed_transcript is not None and observed_transcript.status in (TranscriptStatus.COMPLETED, TranscriptStatus.FAILED):
                if observed_transcript.status is TranscriptStatus.FAILED and observed_transcript.failure_reason is None:
                    observed_transcript = replace(observed_transcript, failure_reason="filter-process-failed")
                if persist:
                    stopped = stop_and_verify_capture(self._transcript_pipe, run)
                    if not stopped.verified_stopped:
                        raise capture_compensation_error(
                            run_id,
                            "transcript-status-reconciliation",
                        ) from stopped.cause
                transcript_at = self._clock.now()
                transcript_changed = with_transcript(run, observed_transcript, transcript_at)
                event_type = "TranscriptCompleted" if observed_transcript.status is TranscriptStatus.COMPLETED else "TranscriptFailed"
                payload: dict[str, JsonValue] = {
                    "status": observed_transcript.status.value,
                    "redaction_findings": observed_transcript.redaction_findings,
                }
                if observed_transcript.failure_reason is not None:
                    payload["error_category"] = observed_transcript.failure_reason
                if persist:
                    run = commit_authorized(
                        self._repository,
                        self._authorization,
                        expected_revision=run.revision,
                        next_record=transcript_changed,
                        event=runtime_event(
                            run,
                            actor,
                            event_type,
                            transcript_at,
                            payload,
                        ),
                        actor=actor,
                        action=Action.CONFIGURE_TRANSCRIPT,
                    )
                else:
                    run = replace(run, transcript=observed_transcript)

        reconcile_evidence = getattr(self._watcher, "reconcile", None)
        if not callable(reconcile_evidence):
            return safe_run_projection(run, actor, self._authorization)
        snapshot = reconcile_evidence(run)
        if snapshot.error_category is not None:
            # A malformed manifest blocks the live view and fresh approval
            # checks, but cannot overwrite the last valid evidence registry.
            projected = replace(run, gate=snapshot.gate)
            return safe_run_projection(projected, actor, self._authorization)
        gate = run.gate if run.gate.status in (GateStatus.APPROVED, GateStatus.HELD) else snapshot.gate
        if snapshot.evidence_root == run.evidence_root and snapshot.artifacts == run.artifacts and gate == run.gate:
            return safe_run_projection(run, actor, self._authorization)
        observed_at = self._clock.now()
        changed = (
            advance(
                run,
                now=observed_at,
                evidence_root=snapshot.evidence_root,
                artifacts=snapshot.artifacts,
                gate=gate,
            )
            if persist
            else replace(run, evidence_root=snapshot.evidence_root, artifacts=snapshot.artifacts, gate=gate)
        )
        ready = gate.evidence_ready
        if persist:
            changed = commit_authorized(
                self._repository,
                self._authorization,
                expected_revision=run.revision,
                next_record=changed,
                event=runtime_event(run, actor, "ArtifactObserved" if ready else "ArtifactUnavailable", observed_at, {
                    "artifact_count": len(snapshot.artifacts),
                    "all_available": ready,
                    "gate_id": gate.gate_id,
                }),
                actor=actor,
                action=Action.DECIDE_GATE,
            )
        return safe_run_projection(changed, actor, self._authorization)

    def observe_evidence(self, run_id: str, paths: tuple[str, ...], actor: Actor) -> RunProjection:
        if self._watcher is None:
            raise error(ErrorCode.COMMAND_FAILED, "Evidence watcher is unavailable", "command-failed", "Rebuild the application composition.")
        run = self._repository.load(run_id)
        require_authorized(self._repository, self._authorization, run, actor, Action.READ_STATE)
        reconcile_paths = getattr(self._watcher, "reconcile_paths", None)
        if callable(reconcile_paths):
            snapshot = reconcile_paths(run, paths)
            if snapshot.error_category is not None:
                projected = replace(run, gate=snapshot.gate)
                return safe_run_projection(projected, actor, self._authorization)
            observed = snapshot.artifacts
            next_gate = snapshot.gate
        else:
            observed = self._watcher.observe_once(run, paths)
            ready = bool(observed) and all(item.status is ArtifactStatus.AVAILABLE for item in observed)
            next_gate = replace(run.gate, evidence_ready=ready, status=GateStatus.PENDING if ready else GateStatus.BLOCKED)
        if observed == run.artifacts:
            projected = run if next_gate == run.gate else replace(run, gate=next_gate)
            return safe_run_projection(projected, actor, self._authorization)
        now = self._clock.now()
        ready = bool(observed) and all(item.status is ArtifactStatus.AVAILABLE for item in observed)
        may_persist = actor.role is Role.LOCAL_OPERATOR and actor.uid == run.owner.uid
        changed = (
            advance(run, now=now, artifacts=observed, gate=next_gate)
            if may_persist
            else replace(run, artifacts=observed, gate=next_gate)
        )
        event_type = "ArtifactObserved" if ready else "ArtifactUnavailable"
        if may_persist:
            changed = commit_authorized(
                self._repository,
                self._authorization,
                expected_revision=run.revision,
                next_record=changed,
                event=runtime_event(run, actor, event_type, now, {"artifact_count": len(observed), "all_available": ready}),
                actor=actor,
                action=Action.DECIDE_GATE,
            )
        return safe_run_projection(changed, actor, self._authorization)

    def recover(self, run_id: str, actor: Actor, expected_revision: int | None = None) -> RunProjection:
        if actor.role is not Role.LOCAL_OPERATOR or actor.uid != os.getuid():
            raise error(ErrorCode.FORBIDDEN, "Run recovery requires the owning local operator", "forbidden", "Use the owning OS account.")
        # Deny before repository recovery even when the latest snapshot is too
        # corrupt to construct its exact resource tuple.
        self._authorization.require(
            actor,
            Action.ATTACH,
            AuthorizationResource(str(self._workspace), actor.uid, run_id),
        )
        try:
            current = self._repository.load(run_id)
        except NebulaError as exc:
            if exc.code not in (ErrorCode.STATE_CORRUPT, ErrorCode.STATE_IO):
                raise
            current = None
        if current is not None and expected_revision is not None and current.revision != expected_revision:
            raise error(ErrorCode.STALE_REVISION, "The run changed after it was displayed", "conflict", "Refresh and retry.", current_revision=current.revision)

        recovered = self._repository.recover(run_id)
        require_authorized(self._repository, self._authorization, recovered, actor, Action.ATTACH)
        if expected_revision is not None and recovered.revision != expected_revision:
            raise error(ErrorCode.STALE_REVISION, "The recoverable snapshot has a different revision", "conflict", "Refresh the recovered run.", current_revision=recovered.revision)

        attempted_at = self._clock.now()
        attempted = advance(recovered, now=attempted_at)
        attempted = commit_authorized(
            self._repository,
            self._authorization,
            expected_revision=recovered.revision,
            next_record=attempted,
            event=runtime_event(recovered, actor, "RecoveryAttempted", attempted_at, {"source": "validated-state-image"}),
            actor=actor,
            action=Action.ATTACH,
        )
        applied_at = self._clock.now()
        applied = advance(attempted, now=applied_at)
        applied = commit_authorized(
            self._repository,
            self._authorization,
            expected_revision=attempted.revision,
            next_record=applied,
            event=runtime_event(attempted, actor, "StateRecoveryApplied", applied_at, {"recovered_revision": recovered.revision}),
            actor=actor,
            action=Action.ATTACH,
        )
        return safe_run_projection(applied, actor, self._authorization)

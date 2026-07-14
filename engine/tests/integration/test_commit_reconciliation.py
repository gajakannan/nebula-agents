from __future__ import annotations

import json
import os
import stat
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from nebula_agents.application.runs import RunService, runtime_event
from nebula_agents.application.transcripts import TranscriptService
from nebula_agents.domain.enums import (
    Action,
    GateStatus,
    PromptAction,
    ProviderKey,
    RedactionStatus,
    Role,
    RunStatus,
    TranscriptStatus,
)
from nebula_agents.domain.errors import ErrorCode, NebulaError, error
from nebula_agents.domain.models import (
    Actor,
    AuthorizationDecision,
    GateSnapshot,
    LaunchRequest,
    RunRecord,
    TranscriptState,
)
from nebula_agents.domain.transitions import advance, with_transcript
from nebula_agents.infrastructure.filesystem_store import FilesystemRunRepository
from nebula_agents.infrastructure import filesystem_store
from nebula_agents.infrastructure.schema_registry import JsonSchemaRegistry


NOW = datetime(2026, 7, 14, 18, 0, tzinfo=UTC)
RUN_ID = "2026-07-14-b885d64c"


class Authorization:
    def require(self, actor, action, resource, context=None) -> None:
        return None

    def authorize(self, actor, action, resource, context=None) -> AuthorizationDecision:
        return AuthorizationDecision(True, "test-policy")


class DenyFallbackAuthorization(Authorization):
    def __init__(self) -> None:
        self.configure_checks = 0

    def require(self, actor, action, resource, context=None) -> None:
        if action is Action.CONFIGURE_TRANSCRIPT:
            self.configure_checks += 1
            if self.configure_checks > 1:
                raise error(
                    ErrorCode.FORBIDDEN,
                    "fallback denied",
                    "forbidden",
                    "use owner",
                )


class Clock:
    def __init__(self) -> None:
        self._now = NOW

    def now(self) -> datetime:
        value = self._now
        self._now += timedelta(seconds=1)
        return value


class Preflight:
    def __init__(self, prompt: Path) -> None:
        self.prompt = prompt

    def require_ready(self, *args):
        return type("Ready", (), {"prompt_contract_path": str(self.prompt)})()


class Provider:
    key = ProviderKey.CODEX

    def build_interactive_argv(self, workspace_root: Path, prompt_text: str):
        return (str(Path(sys.executable).resolve()), "-c", "pass")


class Tmux:
    def __init__(self) -> None:
        self.present = False
        self.killed: list[str] = []

    def has_session(self, session_name: str) -> bool:
        return self.present

    def create_session(self, session_name: str, descriptor_path: Path) -> None:
        self.present = True

    def kill_session(self, session_name: str) -> None:
        self.killed.append(session_name)
        self.present = False


class Pipe:
    def __init__(
        self,
        *,
        active: bool = False,
        configure_failure: Exception | None = None,
        disable_failure: Exception | None = None,
        probe_failure: Exception | None = None,
        tmux: Tmux | None = None,
        session_present: bool = True,
        termination_failure: Exception | None = None,
        session_probe_failure: Exception | None = None,
    ) -> None:
        self.configured: list[tuple[RunRecord, Path]] = []
        self.disabled: list[RunRecord] = []
        self.active = active
        self.configure_failure = configure_failure
        self.disable_failure = disable_failure
        self.probe_failure = probe_failure
        self.tmux = tmux
        self.owning_session_present = session_present
        self.termination_failure = termination_failure
        self.session_probe_failure = session_probe_failure

    def configure(self, *, run: RunRecord, output_path: Path) -> None:
        self.configured.append((run, output_path))
        self.active = True
        if self.configure_failure is not None:
            raise self.configure_failure

    def disable(self, *, run: RunRecord) -> None:
        self.disabled.append(run)
        if self.disable_failure is not None:
            raise self.disable_failure
        self.active = False

    def is_active(self, *, run: RunRecord) -> bool:
        if self.probe_failure is not None:
            raise self.probe_failure
        return self.active

    def terminate_session(self, *, run: RunRecord) -> None:
        if self.termination_failure is not None:
            raise self.termination_failure
        self.owning_session_present = False
        self.active = False
        if self.tmux is not None:
            self.tmux.kill_session(run.tmux_session)

    def session_present(self, *, run: RunRecord) -> bool:
        if self.session_probe_failure is not None:
            raise self.session_probe_failure
        if self.tmux is not None:
            return self.tmux.has_session(run.tmux_session)
        return self.owning_session_present

class StatusPipe(Pipe):
    def __init__(
        self,
        *statuses: TranscriptState | None,
        active: bool = False,
        disable_failure: Exception | None = None,
    ) -> None:
        super().__init__(active=active, disable_failure=disable_failure)
        self.statuses = list(statuses)

    def capture_status(self, *, run: RunRecord) -> TranscriptState | None:
        if len(self.statuses) > 1:
            return self.statuses.pop(0)
        return self.statuses[0] if self.statuses else None


class LegacyPipe:
    """Lightweight older adapter with no liveness proof method."""

    def __init__(self) -> None:
        self.active = False

    def configure(self, *, run: RunRecord, output_path: Path) -> None:
        self.active = True

    def disable(self, *, run: RunRecord) -> None:
        self.active = False


class CommitFaultRepository:
    """Fault seam around production repository publication/replacement."""

    def __init__(
        self,
        repository: FilesystemRunRepository,
        *,
        event_type: str,
        timing: str,
        failures: int = 1,
    ) -> None:
        self.repository = repository
        self.event_type = event_type
        self.timing = timing
        self.triggered = False
        self.remaining_failures = failures

    def __getattr__(self, name: str):
        return getattr(self.repository, name)

    def _matches(self, event) -> bool:
        if self.remaining_failures <= 0 or event.event_type != self.event_type:
            return False
        self.triggered = True
        self.remaining_failures -= 1
        return True

    def commit(self, *, expected_revision: int, next_record: RunRecord, event):
        fault = self._matches(event)
        if fault and self.timing == "before":
            raise RuntimeError(f"pre-publication {event.event_type}")
        result = self.repository.commit(
            expected_revision=expected_revision,
            next_record=next_record,
            event=event,
        )
        if fault and self.timing == "after":
            raise RuntimeError(f"post-publication {event.event_type}")
        return result

    def commit_authorized(self, **kwargs):
        event = kwargs["event"]
        fault = self._matches(event)
        if fault and self.timing == "before":
            raise RuntimeError(f"pre-publication {event.event_type}")
        result = self.repository.commit_authorized(**kwargs)
        if fault and self.timing == "after":
            raise RuntimeError(f"post-publication {event.event_type}")
        return result


class RecoveryFaultRepository(CommitFaultRepository):
    def __init__(self, *args, fail_on_recover: int = 2, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.recover_calls = 0
        self.fail_on_recover = fail_on_recover

    def recover(self, run_id: str) -> RunRecord:
        self.recover_calls += 1
        if self.recover_calls >= self.fail_on_recover:
            raise RuntimeError("recovery unavailable")
        return self.repository.recover(run_id)


def _inject_post_replace_fsync_fault(
    monkeypatch: pytest.MonkeyPatch,
    *,
    predicate,
) -> list[bool]:
    """Raise after run.json replacement at the production directory fsync."""
    real_fsync = os.fsync
    triggered = [False]

    def fault(fd: int) -> None:
        if not triggered[0] and stat.S_ISDIR(os.fstat(fd).st_mode):
            snapshot = Path(f"/proc/self/fd/{fd}") / "run.json"
            if snapshot.is_file():
                document = json.loads(snapshot.read_text(encoding="utf-8"))
                if predicate(document):
                    triggered[0] = True
                    raise OSError("post-replace directory fsync failure")
        real_fsync(fd)

    monkeypatch.setattr(filesystem_store.os, "fsync", fault)
    return triggered


def _repository(tmp_path: Path, schema_root: Path) -> FilesystemRunRepository:
    return FilesystemRunRepository(
        tmp_path / "runtime",
        JsonSchemaRegistry(schema_root),
    )


def _events(repository: FilesystemRunRepository) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (repository.run_directory(RUN_ID) / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]


def _active_run(
    repository: FilesystemRunRepository,
    workspace: Path,
    actor: Actor,
    *,
    transcript_active: bool = False,
) -> RunRecord:
    run_directory = repository.run_directory(RUN_ID)
    record = RunRecord(
        "1.0",
        0,
        RUN_ID,
        "F0001",
        None,
        ProviderKey.CODEX,
        "nebula-F0001-b885d64c",
        str(workspace),
        str(workspace / "agents/templates/prompts/evidence-contract/feature-operator-friendly.md"),
        PromptAction.FEATURE,
        RunStatus.LAUNCHING,
        actor,
        None,
        GateSnapshot("G0", GateStatus.PENDING, False, ("g0-assembly-plan-validation.md",), None),
        None,
        (),
        TranscriptState(TranscriptStatus.DISABLED, RedactionStatus.NOT_RUN, None, None, 0),
        str(run_directory / "events.jsonl"),
        1,
        NOW,
        NOW,
        None,
    )
    repository.create(record, runtime_event(record, actor, "LaunchRequested", NOW, sequence=1))
    active = advance(
        record,
        now=NOW + timedelta(seconds=1),
        status=RunStatus.ACTIVE,
        last_seen_at=NOW + timedelta(seconds=1),
    )
    active = repository.commit(
        expected_revision=record.revision,
        next_record=active,
        event=runtime_event(record, actor, "RunLaunched", NOW + timedelta(seconds=1)),
    )
    if not transcript_active:
        return active
    path = repository.run_directory(RUN_ID) / "transcript.redacted.log"
    state = TranscriptState(TranscriptStatus.ACTIVE, RedactionStatus.NOT_RUN, str(path), None, 0)
    enabled = with_transcript(active, state, NOW + timedelta(seconds=2))
    return repository.commit(
        expected_revision=active.revision,
        next_record=enabled,
        event=runtime_event(active, actor, "TranscriptEnabled", NOW + timedelta(seconds=2)),
    )


@pytest.mark.parametrize("timing", ["before", "after"])
def test_launch_reconciles_real_repository_fault_before_external_compensation(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    timing: str,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    triggered = [False]
    if timing == "before":
        repository = CommitFaultRepository(base, event_type="RunLaunched", timing=timing)
    else:
        repository = base
        triggered = _inject_post_replace_fsync_fault(
            monkeypatch,
            predicate=lambda document: document["revision"] == 1
            and document["status"] == "Active",
        )
    tmux = Tmux()
    schema = JsonSchemaRegistry(schema_root)
    service = RunService(
        workspace_root=workspace,
        preflight=Preflight(workspace / "agents/templates/prompts/evidence-contract/feature-operator-friendly.md"),
        authorization=Authorization(),
        repository=repository,
        providers={ProviderKey.CODEX: Provider()},
        tmux=tmux,
        schema=schema,
        clock=Clock(),
    )

    expected_fault = (
        "pre-publication RunLaunched"
        if timing == "before"
        else "post-replace directory fsync failure"
    )
    with pytest.raises((RuntimeError, OSError), match=expected_fault):
        service.launch(
            LaunchRequest(
                "F0001",
                None,
                ProviderKey.CODEX,
                PromptAction.FEATURE,
                RUN_ID,
            ),
            actor,
        )

    assert triggered[0] is (timing == "after")
    persisted = base.recover(RUN_ID)
    events = [
        json.loads(line)
        for line in (base.run_directory(RUN_ID) / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert persisted.status is RunStatus.FAILED
    assert tmux.present is False
    assert tmux.killed == ["nebula-F0001-b885d64c"]
    assert [event["event_type"] for event in events] == (
        ["LaunchRequested", "LaunchFailed"]
        if timing == "before"
        else ["LaunchRequested", "RunLaunched", "LaunchFailed"]
    )
    assert events[-1]["payload"]["commit_outcome"] == (
        "not-published" if timing == "before" else "published"
    )
    if timing == "after":
        assert events[-1]["payload"]["compensated_event"] == "RunLaunched"


@pytest.mark.parametrize("timing", ["before", "after"])
def test_transcript_completion_restarts_only_recovered_active_real_state(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    timing: str,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    active = _active_run(base, workspace, actor, transcript_active=True)
    triggered = [False]
    if timing == "before":
        repository = CommitFaultRepository(base, event_type="TranscriptCompleted", timing=timing)
    else:
        repository = base
        triggered = _inject_post_replace_fsync_fault(
            monkeypatch,
            predicate=lambda document: document["transcript"]["status"]
            == "Completed",
        )
    pipe = Pipe(active=True)
    service = TranscriptService(
        repository=repository,
        authorization=Authorization(),
        pipe=pipe,
        clock=Clock(),
    )

    expected_fault = (
        "pre-publication TranscriptCompleted"
        if timing == "before"
        else "post-replace directory fsync failure"
    )
    with pytest.raises((RuntimeError, OSError), match=expected_fault):
        service.complete(RUN_ID, actor, active.revision)

    assert triggered[0] is (timing == "after")
    persisted = base.recover(RUN_ID)
    expected_status = TranscriptStatus.ACTIVE if timing == "before" else TranscriptStatus.COMPLETED
    assert persisted.transcript.status is expected_status
    assert pipe.disabled == [active]
    assert len(pipe.configured) == (1 if timing == "before" else 0)
    assert pipe.active is (timing == "before")
    if pipe.configured:
        assert pipe.configured[0][0].transcript.status is TranscriptStatus.ACTIVE


@pytest.mark.parametrize("timing", ["before", "after"])
def test_transcript_enable_compensates_only_when_real_transition_is_absent(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    timing: str,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    active = _active_run(base, workspace, actor)
    triggered = [False]
    if timing == "before":
        repository = CommitFaultRepository(base, event_type="TranscriptEnabled", timing=timing)
    else:
        repository = base
        triggered = _inject_post_replace_fsync_fault(
            monkeypatch,
            predicate=lambda document: document["transcript"]["status"] == "Active",
        )
    pipe = Pipe()
    service = TranscriptService(
        repository=repository,
        authorization=Authorization(),
        pipe=pipe,
        clock=Clock(),
    )

    expected_fault = (
        "pre-publication TranscriptEnabled"
        if timing == "before"
        else "post-replace directory fsync failure"
    )
    with pytest.raises((RuntimeError, OSError), match=expected_fault):
        service.enable(RUN_ID, actor, active.revision)

    assert triggered[0] is (timing == "after")
    persisted = base.recover(RUN_ID)
    expected_status = TranscriptStatus.DISABLED if timing == "before" else TranscriptStatus.ACTIVE
    assert persisted.transcript.status is expected_status
    assert len(pipe.configured) == 1
    assert len(pipe.disabled) == (1 if timing == "before" else 0)
    assert pipe.active is (timing == "after")


def test_enable_disable_failure_persists_truthful_active_compensation(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    run = _active_run(base, workspace, actor)
    repository = CommitFaultRepository(
        base,
        event_type="TranscriptEnabled",
        timing="before",
    )
    triggered = _inject_post_replace_fsync_fault(
        monkeypatch,
        predicate=lambda document: document["transcript"]["status"] == "Active",
    )
    pipe = Pipe(disable_failure=RuntimeError("disable failed"))
    service = TranscriptService(
        repository=repository,
        authorization=Authorization(),
        pipe=pipe,
        clock=Clock(),
    )

    with pytest.raises(NebulaError) as caught:
        service.enable(RUN_ID, actor, run.revision)

    persisted = base.recover(RUN_ID)
    events = _events(base)
    assert triggered == [True]
    assert caught.value.code is ErrorCode.STATE_IO
    assert persisted.transcript.status is TranscriptStatus.ACTIVE
    assert persisted.revision == run.revision + 1
    assert pipe.active is True
    assert [event["event_type"] for event in events] == [
        "LaunchRequested",
        "RunLaunched",
        "TranscriptEnabled",
    ]
    assert events[-1]["payload"]["compensation"] == "disable-unverified"
    assert events[-1]["payload"]["operation"] == "transcript-enable-commit"


def test_enable_without_liveness_probe_conservatively_records_active(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    run = _active_run(base, workspace, actor)
    repository = CommitFaultRepository(
        base,
        event_type="TranscriptEnabled",
        timing="before",
    )
    pipe = LegacyPipe()
    service = TranscriptService(
        repository=repository,
        authorization=Authorization(),
        pipe=pipe,  # type: ignore[arg-type]
        clock=Clock(),
    )

    with pytest.raises(NebulaError) as caught:
        service.enable(RUN_ID, actor, run.revision)

    persisted = base.recover(RUN_ID)
    assert caught.value.code is ErrorCode.STATE_IO
    assert pipe.active is False
    assert persisted.transcript.status is TranscriptStatus.ACTIVE
    assert _events(base)[-1]["payload"]["external_capture"] == (
        "possibly-active"
    )


def test_double_prepublication_enable_failure_terminates_owning_session(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    run = _active_run(base, workspace, actor)
    repository = CommitFaultRepository(
        base,
        event_type="TranscriptEnabled",
        timing="before",
        failures=2,
    )
    pipe = Pipe(disable_failure=RuntimeError("disable failed"))
    service = TranscriptService(
        repository=repository,
        authorization=Authorization(),
        pipe=pipe,
        clock=Clock(),
    )

    with pytest.raises(NebulaError) as caught:
        service.enable(RUN_ID, actor, run.revision)

    persisted = base.recover(RUN_ID)
    assert caught.value.code is ErrorCode.STATE_IO
    assert persisted.transcript.status is TranscriptStatus.DISABLED
    assert pipe.active is False
    assert pipe.owning_session_present is False
    assert [event["event_type"] for event in _events(base)] == [
        "LaunchRequested",
        "RunLaunched",
    ]


def test_double_prepublication_failure_surfaces_unverified_session_termination(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    run = _active_run(base, workspace, actor)
    repository = CommitFaultRepository(
        base,
        event_type="TranscriptEnabled",
        timing="before",
        failures=2,
    )
    pipe = Pipe(
        disable_failure=RuntimeError("disable failed"),
        termination_failure=RuntimeError("termination failed"),
    )
    service = TranscriptService(
        repository=repository,
        authorization=Authorization(),
        pipe=pipe,
        clock=Clock(),
    )

    with pytest.raises(NebulaError) as caught:
        service.enable(RUN_ID, actor, run.revision)

    assert caught.value.code is ErrorCode.STATE_IO
    assert caught.value.details[0]["operation"] == (
        "transcript-enable-commit-active-compensation-session-termination"
    )
    assert base.recover(RUN_ID).transcript.status is TranscriptStatus.DISABLED
    assert pipe.active is True
    assert pipe.owning_session_present is True


def test_unavailable_compensation_recovery_still_terminates_owning_session(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    run = _active_run(base, workspace, actor)
    repository = RecoveryFaultRepository(
        base,
        event_type="TranscriptEnabled",
        timing="before",
        failures=2,
    )
    pipe = Pipe(disable_failure=RuntimeError("disable failed"))
    service = TranscriptService(
        repository=repository,
        authorization=Authorization(),
        pipe=pipe,
        clock=Clock(),
    )

    with pytest.raises(NebulaError) as caught:
        service.enable(RUN_ID, actor, run.revision)

    assert caught.value.code is ErrorCode.STATE_IO
    assert caught.value.details[0]["operation"] == (
        "transcript-enable-commit-active-compensation-reconciliation"
    )
    assert base.load(RUN_ID).transcript.status is TranscriptStatus.DISABLED
    assert pipe.active is False
    assert pipe.owning_session_present is False


def test_first_enable_recovery_failure_terminates_owning_session(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    run = _active_run(base, workspace, actor)
    repository = RecoveryFaultRepository(
        base,
        event_type="TranscriptEnabled",
        timing="before",
        fail_on_recover=1,
    )
    pipe = Pipe()
    service = TranscriptService(
        repository=repository,
        authorization=Authorization(),
        pipe=pipe,
        clock=Clock(),
    )

    with pytest.raises(NebulaError) as caught:
        service.enable(RUN_ID, actor, run.revision)

    persisted = base.load(RUN_ID)
    assert caught.value.code is ErrorCode.STATE_IO
    assert caught.value.details[0]["operation"] == (
        "transcript-enable-commit-recovery"
    )
    assert persisted.transcript.status is TranscriptStatus.DISABLED
    assert pipe.active is False
    assert pipe.owning_session_present is False
    assert [event["event_type"] for event in _events(base)] == [
        "LaunchRequested",
        "RunLaunched",
    ]


def test_first_enable_recovery_and_termination_failure_is_stable_state_io(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    run = _active_run(base, workspace, actor)
    repository = RecoveryFaultRepository(
        base,
        event_type="TranscriptEnabled",
        timing="before",
        fail_on_recover=1,
    )
    pipe = Pipe(termination_failure=RuntimeError("termination failed"))
    service = TranscriptService(
        repository=repository,
        authorization=Authorization(),
        pipe=pipe,
        clock=Clock(),
    )

    with pytest.raises(NebulaError) as caught:
        service.enable(RUN_ID, actor, run.revision)

    assert caught.value.code is ErrorCode.STATE_IO
    assert caught.value.details[0]["operation"] == (
        "transcript-enable-commit-recovery-session-termination"
    )
    assert base.load(RUN_ID).transcript.status is TranscriptStatus.DISABLED
    assert pipe.active is True
    assert pipe.owning_session_present is True


def test_fallback_authorization_denial_terminates_owning_session(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    run = _active_run(base, workspace, actor)
    repository = CommitFaultRepository(
        base,
        event_type="TranscriptEnabled",
        timing="before",
    )
    pipe = Pipe(disable_failure=RuntimeError("disable failed"))
    authorization = DenyFallbackAuthorization()
    service = TranscriptService(
        repository=repository,
        authorization=authorization,
        pipe=pipe,
        clock=Clock(),
    )

    with pytest.raises(NebulaError) as caught:
        service.enable(RUN_ID, actor, run.revision)

    persisted = base.recover(RUN_ID)
    assert caught.value.code is ErrorCode.STATE_IO
    assert persisted.transcript.status is TranscriptStatus.DISABLED
    assert pipe.active is False
    assert pipe.owning_session_present is False
    assert [event["event_type"] for event in _events(base)] == [
        "LaunchRequested",
        "RunLaunched",
        "AuthorizationDenied",
    ]


def test_launch_with_transcript_disable_failure_persists_active_compensation(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    repository = CommitFaultRepository(
        base,
        event_type="TranscriptEnabled",
        timing="before",
    )
    pipe = Pipe(disable_failure=RuntimeError("disable failed"))
    tmux = Tmux()
    service = RunService(
        workspace_root=workspace,
        preflight=Preflight(
            workspace
            / "agents/templates/prompts/evidence-contract/feature-operator-friendly.md"
        ),
        authorization=Authorization(),
        repository=repository,
        providers={ProviderKey.CODEX: Provider()},
        tmux=tmux,
        schema=JsonSchemaRegistry(schema_root),
        clock=Clock(),
        transcript_pipe=pipe,
    )

    with pytest.raises(NebulaError) as caught:
        service.launch(
            LaunchRequest(
                "F0001",
                None,
                ProviderKey.CODEX,
                PromptAction.FEATURE,
                RUN_ID,
                transcript_enabled=True,
            ),
            actor,
        )

    persisted = base.recover(RUN_ID)
    events = _events(base)
    assert caught.value.code is ErrorCode.STATE_IO
    assert persisted.status is RunStatus.ACTIVE
    assert persisted.transcript.status is TranscriptStatus.ACTIVE
    assert tmux.present is True
    assert pipe.active is True
    assert [event["event_type"] for event in events] == [
        "LaunchRequested",
        "RunLaunched",
        "TranscriptEnabled",
    ]
    assert events[-1]["payload"]["operation"] == (
        "launch-transcript-enable-commit"
    )


def test_launch_double_prepublication_failure_terminates_owning_session(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    repository = CommitFaultRepository(
        base,
        event_type="TranscriptEnabled",
        timing="before",
        failures=2,
    )
    tmux = Tmux()
    pipe = Pipe(
        disable_failure=RuntimeError("disable failed"),
        tmux=tmux,
    )
    service = RunService(
        workspace_root=workspace,
        preflight=Preflight(
            workspace
            / "agents/templates/prompts/evidence-contract/feature-operator-friendly.md"
        ),
        authorization=Authorization(),
        repository=repository,
        providers={ProviderKey.CODEX: Provider()},
        tmux=tmux,
        schema=JsonSchemaRegistry(schema_root),
        clock=Clock(),
        transcript_pipe=pipe,
    )

    with pytest.raises(NebulaError) as caught:
        service.launch(
            LaunchRequest(
                "F0001",
                None,
                ProviderKey.CODEX,
                PromptAction.FEATURE,
                RUN_ID,
                transcript_enabled=True,
            ),
            actor,
        )

    persisted = base.recover(RUN_ID)
    assert caught.value.code is ErrorCode.STATE_IO
    assert persisted.transcript.status is TranscriptStatus.DISABLED
    assert tmux.present is False
    assert pipe.active is False
    assert tmux.killed == ["nebula-F0001-b885d64c"]
    assert [event["event_type"] for event in _events(base)] == [
        "LaunchRequested",
        "RunLaunched",
    ]


def test_launch_first_enable_recovery_failure_terminates_owning_session(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    repository = RecoveryFaultRepository(
        base,
        event_type="TranscriptEnabled",
        timing="before",
        fail_on_recover=1,
    )
    tmux = Tmux()
    pipe = Pipe(tmux=tmux)
    service = RunService(
        workspace_root=workspace,
        preflight=Preflight(
            workspace
            / "agents/templates/prompts/evidence-contract/feature-operator-friendly.md"
        ),
        authorization=Authorization(),
        repository=repository,
        providers={ProviderKey.CODEX: Provider()},
        tmux=tmux,
        schema=JsonSchemaRegistry(schema_root),
        clock=Clock(),
        transcript_pipe=pipe,
    )

    with pytest.raises(NebulaError) as caught:
        service.launch(
            LaunchRequest(
                "F0001",
                None,
                ProviderKey.CODEX,
                PromptAction.FEATURE,
                RUN_ID,
                transcript_enabled=True,
            ),
            actor,
        )

    persisted = base.load(RUN_ID)
    assert caught.value.code is ErrorCode.STATE_IO
    assert caught.value.details[0]["operation"] == (
        "launch-transcript-enable-commit-recovery"
    )
    assert persisted.transcript.status is TranscriptStatus.DISABLED
    assert pipe.active is False
    assert tmux.present is False
    assert tmux.killed == ["nebula-F0001-b885d64c"]
    assert [event["event_type"] for event in _events(base)] == [
        "LaunchRequested",
        "RunLaunched",
    ]


def test_launch_transcript_failure_recovery_error_does_not_kill_stopped_session(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    repository = RecoveryFaultRepository(
        base,
        event_type="TranscriptFailed",
        timing="before",
        fail_on_recover=1,
    )
    tmux = Tmux()
    pipe = Pipe(
        configure_failure=RuntimeError("configuration failed"),
        tmux=tmux,
    )
    service = RunService(
        workspace_root=workspace,
        preflight=Preflight(
            workspace
            / "agents/templates/prompts/evidence-contract/feature-operator-friendly.md"
        ),
        authorization=Authorization(),
        repository=repository,
        providers={ProviderKey.CODEX: Provider()},
        tmux=tmux,
        schema=JsonSchemaRegistry(schema_root),
        clock=Clock(),
        transcript_pipe=pipe,
    )

    with pytest.raises(NebulaError) as caught:
        service.launch(
            LaunchRequest(
                "F0001",
                None,
                ProviderKey.CODEX,
                PromptAction.FEATURE,
                RUN_ID,
                transcript_enabled=True,
            ),
            actor,
        )

    assert caught.value.code is ErrorCode.STATE_IO
    assert caught.value.details[0]["operation"] == (
        "launch-transcript-failure-commit-recovery"
    )
    assert base.load(RUN_ID).transcript.status is TranscriptStatus.DISABLED
    assert pipe.active is False
    assert tmux.present is True
    assert tmux.killed == []


def test_launch_postpublication_active_does_not_attempt_disable(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    triggered = _inject_post_replace_fsync_fault(
        monkeypatch,
        predicate=lambda document: document["transcript"]["status"] == "Active",
    )
    pipe = Pipe(disable_failure=RuntimeError("disable must not be called"))
    tmux = Tmux()
    service = RunService(
        workspace_root=workspace,
        preflight=Preflight(
            workspace
            / "agents/templates/prompts/evidence-contract/feature-operator-friendly.md"
        ),
        authorization=Authorization(),
        repository=base,
        providers={ProviderKey.CODEX: Provider()},
        tmux=tmux,
        schema=JsonSchemaRegistry(schema_root),
        clock=Clock(),
        transcript_pipe=pipe,
    )

    with pytest.raises(OSError, match="post-replace directory fsync failure"):
        service.launch(
            LaunchRequest(
                "F0001",
                None,
                ProviderKey.CODEX,
                PromptAction.FEATURE,
                RUN_ID,
                transcript_enabled=True,
            ),
            actor,
        )

    persisted = base.recover(RUN_ID)
    assert triggered == [True]
    assert persisted.status is RunStatus.ACTIVE
    assert persisted.transcript.status is TranscriptStatus.ACTIVE
    assert pipe.active is True
    assert pipe.disabled == []
    assert [event["event_type"] for event in _events(base)] == [
        "LaunchRequested",
        "RunLaunched",
        "TranscriptEnabled",
    ]


def test_observed_failed_completion_does_not_publish_failed_when_disable_fails(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    run = _active_run(base, workspace, actor, transcript_active=True)
    observed = TranscriptState(
        TranscriptStatus.FAILED,
        RedactionStatus.FAILED,
        run.transcript.path,
        None,
        0,
        "filter-process-failed",
    )
    pipe = StatusPipe(
        observed,
        active=True,
        disable_failure=RuntimeError("disable failed"),
    )
    service = TranscriptService(
        repository=base,
        authorization=Authorization(),
        pipe=pipe,
        clock=Clock(),
    )

    with pytest.raises(NebulaError) as caught:
        service.complete(RUN_ID, actor, run.revision)

    persisted = base.recover(RUN_ID)
    events = _events(base)
    assert caught.value.code is ErrorCode.STATE_IO
    assert persisted == run
    assert persisted.transcript.status is TranscriptStatus.ACTIVE
    assert pipe.active is True
    assert [event["event_type"] for event in events] == [
        "LaunchRequested",
        "RunLaunched",
        "TranscriptEnabled",
    ]


def test_status_reconciliation_does_not_publish_failed_when_disable_fails(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    run = _active_run(base, workspace, actor, transcript_active=True)
    observed = TranscriptState(
        TranscriptStatus.FAILED,
        RedactionStatus.FAILED,
        run.transcript.path,
        None,
        0,
        "filter-process-failed",
    )
    pipe = StatusPipe(
        observed,
        active=True,
        disable_failure=RuntimeError("disable failed"),
    )
    tmux = Tmux()
    tmux.present = True
    service = RunService(
        workspace_root=workspace,
        preflight=Preflight(workspace / "prompt"),
        authorization=Authorization(),
        repository=base,
        providers={},
        tmux=tmux,
        schema=JsonSchemaRegistry(schema_root),
        clock=Clock(),
        transcript_pipe=pipe,
    )

    with pytest.raises(NebulaError) as caught:
        service.reconcile(RUN_ID, actor)

    persisted = base.recover(RUN_ID)
    assert caught.value.code is ErrorCode.STATE_IO
    assert persisted == run
    assert persisted.transcript.status is TranscriptStatus.ACTIVE
    assert pipe.active is True
    assert [event["event_type"] for event in _events(base)] == [
        "LaunchRequested",
        "RunLaunched",
        "TranscriptEnabled",
    ]


def test_configure_failure_cleanup_persists_active_when_disable_fails(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    run = _active_run(base, workspace, actor)
    pipe = Pipe(
        configure_failure=RuntimeError("configure failed after activation"),
        disable_failure=RuntimeError("disable failed"),
    )
    service = TranscriptService(
        repository=base,
        authorization=Authorization(),
        pipe=pipe,
        clock=Clock(),
    )

    with pytest.raises(NebulaError) as caught:
        service.enable(RUN_ID, actor, run.revision)

    persisted = base.recover(RUN_ID)
    events = _events(base)
    assert caught.value.code is ErrorCode.STATE_IO
    assert persisted.transcript.status is TranscriptStatus.ACTIVE
    assert pipe.active is True
    assert [event["event_type"] for event in events] == [
        "LaunchRequested",
        "RunLaunched",
        "TranscriptEnabled",
    ]
    assert events[-1]["payload"]["operation"] == (
        "transcript-configure-failure"
    )


def test_launch_configure_failure_cleanup_persists_active_when_disable_fails(
    tmp_path: Path,
    workspace: Path,
    schema_root: Path,
) -> None:
    actor = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    base = _repository(tmp_path, schema_root)
    pipe = Pipe(
        configure_failure=RuntimeError("configure failed after activation"),
        disable_failure=RuntimeError("disable failed"),
    )
    tmux = Tmux()
    service = RunService(
        workspace_root=workspace,
        preflight=Preflight(
            workspace
            / "agents/templates/prompts/evidence-contract/feature-operator-friendly.md"
        ),
        authorization=Authorization(),
        repository=base,
        providers={ProviderKey.CODEX: Provider()},
        tmux=tmux,
        schema=JsonSchemaRegistry(schema_root),
        clock=Clock(),
        transcript_pipe=pipe,
    )

    with pytest.raises(NebulaError) as caught:
        service.launch(
            LaunchRequest(
                "F0001",
                None,
                ProviderKey.CODEX,
                PromptAction.FEATURE,
                RUN_ID,
                transcript_enabled=True,
            ),
            actor,
        )

    persisted = base.recover(RUN_ID)
    events = _events(base)
    assert caught.value.code is ErrorCode.STATE_IO
    assert persisted.status is RunStatus.ACTIVE
    assert persisted.transcript.status is TranscriptStatus.ACTIVE
    assert tmux.present is True
    assert pipe.active is True
    assert [event["event_type"] for event in events] == [
        "LaunchRequested",
        "RunLaunched",
        "TranscriptEnabled",
    ]
    assert events[-1]["payload"]["operation"] == (
        "launch-transcript-configure-failure"
    )

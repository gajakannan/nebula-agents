from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from nebula_agents.application.authorization import (
    AuthorizationService,
    safe_run_projection,
)
from nebula_agents.application.gates import GateService
from nebula_agents.application.preflight import PreflightService, contained
from nebula_agents.application.queries import QueryService
from nebula_agents.application.runs import RunService, runtime_event
from nebula_agents.application.transcripts import TranscriptService
from nebula_agents.domain.enums import (
    Action,
    ArtifactStatus,
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
from nebula_agents.domain.errors import ErrorCode, NebulaError, error
from nebula_agents.domain.models import (
    Actor,
    AuditEventSummary,
    ArtifactObservation,
    AuthorizationDecision,
    GateDecisionRequest,
    GateSnapshot,
    LaunchRequest,
    RunRecord,
    TranscriptState,
    ValidatorResult,
    Probe,
    RecoverableRun,
)
from nebula_agents.infrastructure.watcher import PollingEvidenceWatcher


NOW = datetime(2026, 7, 13, 18, 0, tzinfo=UTC)
RUN_ID = "2026-07-13-deadbeef"
OWNER = Actor(1000, "operator", Role.LOCAL_OPERATOR)
REVIEWER = Actor(1001, "reviewer", Role.REVIEWER)


def _run(
    root: Path,
    *,
    revision: int = 2,
    status: RunStatus = RunStatus.ACTIVE,
    gate_status: GateStatus = GateStatus.PENDING,
    evidence_ready: bool = False,
    artifacts: tuple[ArtifactObservation, ...] = (),
    validator: ValidatorResult | None = None,
    transcript: TranscriptState | None = None,
    owner: Actor = OWNER,
) -> RunRecord:
    run_dir = root / "runs" / RUN_ID
    run_dir.mkdir(parents=True, exist_ok=True)
    return RunRecord(
        "1.0",
        revision,
        RUN_ID,
        "F0001",
        "F0001-S0001",
        ProviderKey.CODEX,
        "nebula-F0001-deadbeef",
        str(root),
        str(root / "feature-operator-friendly.md"),
        PromptAction.FEATURE,
        status,
        owner,
        None,
        GateSnapshot("G1", gate_status, evidence_ready, ("required.md",), None),
        validator,
        artifacts,
        transcript
        or TranscriptState(
            TranscriptStatus.DISABLED, RedactionStatus.NOT_RUN, None, None, 0
        ),
        str(run_dir / "events.jsonl"),
        revision + 1,
        NOW,
        NOW,
        NOW,
    )


class Clock:
    def __init__(self, *values: datetime) -> None:
        self.values = list(values or (NOW,))

    def now(self) -> datetime:
        if len(self.values) > 1:
            return self.values.pop(0)
        return self.values[0]


class Authorization:
    def __init__(self, *, denied: Action | None = None) -> None:
        self.denied = denied
        self.required: list[tuple[Actor, Action, object, object]] = []
        self.authorized: list[tuple[Actor, Action, object]] = []

    def require(self, actor, action, resource, context=None) -> None:
        self.required.append((actor, action, resource, context))
        if action is self.denied:
            raise error(ErrorCode.FORBIDDEN, "denied", "forbidden", "use owner")

    def authorize(self, actor, action, resource, context=None) -> AuthorizationDecision:
        self.authorized.append((actor, action, resource))
        return AuthorizationDecision(actor.uid == resource.owner_uid, "test-policy")


class Repository:
    def __init__(self, root: Path, records: tuple[RunRecord, ...] = ()) -> None:
        self._runtime_root = root
        self.records = {item.run_id: item for item in records}
        self.created: list[tuple[RunRecord, object]] = []
        self.commits: list[tuple[int, RunRecord, object]] = []
        self.fail_event_type: str | None = None

    @property
    def runtime_root(self) -> Path:
        return self._runtime_root

    def run_directory(self, run_id: str) -> Path:
        path = self._runtime_root / "runs" / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def list(self, status=None):
        values = tuple(self.records.values())
        return tuple(item for item in values if status is None or item.status is status)

    def load(self, run_id: str) -> RunRecord:
        return self.records[run_id]

    def create(self, record: RunRecord, event) -> RunRecord:
        self.created.append((record, event))
        self.records[record.run_id] = record
        return record

    def commit(self, *, expected_revision: int, next_record: RunRecord, event):
        self.commits.append((expected_revision, next_record, event))
        if event.event_type == self.fail_event_type:
            raise RuntimeError(f"failed {event.event_type}")
        self.records[next_record.run_id] = next_record
        return next_record


class AuthorizedRepository(Repository):
    """Exercises the authorization/validation callback under the repository lock seam."""

    def __init__(self, root: Path, records: tuple[RunRecord, ...] = ()) -> None:
        super().__init__(root, records)
        self.locked_record: RunRecord | None = None

    def commit_authorized(
        self,
        *,
        expected_revision: int,
        next_record: RunRecord,
        event,
        authorize,
        denied_actor,
        denied_action,
    ) -> RunRecord:
        current = self.locked_record or self.records[next_record.run_id]
        if current.revision != expected_revision:
            raise error(
                ErrorCode.STALE_REVISION,
                "stale under lock",
                "conflict",
                "refresh",
                current_revision=current.revision,
            )
        authorize(current)
        return self.commit(
            expected_revision=expected_revision,
            next_record=next_record,
            event=event,
        )


class RecoverRepository(AuthorizedRepository):
    def __init__(
        self,
        root: Path,
        record: RunRecord,
        *,
        corrupt_latest: bool = False,
    ) -> None:
        super().__init__(root, (record,))
        self.recover_result = record
        self.corrupt_latest = corrupt_latest
        self.recover_calls: list[str] = []

    def load(self, run_id: str) -> RunRecord:
        if self.corrupt_latest:
            raise error(
                ErrorCode.STATE_CORRUPT,
                "corrupt latest",
                "state-io",
                "recover",
            )
        return super().load(run_id)

    def recover(self, run_id: str) -> RunRecord:
        self.recover_calls.append(run_id)
        return self.recover_result


class RecoveryListingRepository(Repository):
    def __init__(self, root: Path, recoverable: RecoverableRun) -> None:
        super().__init__(root)
        self.recoverable = recoverable

    def list_recoverable(self) -> tuple[RecoverableRun, ...]:
        return (self.recoverable,)


class Preflight:
    def __init__(self, prompt_path: Path) -> None:
        self.prompt_path = prompt_path
        self.calls: list[tuple[object, ...]] = []

    def require_ready(self, *args):
        self.calls.append(args)
        return SimpleNamespace(prompt_contract_path=str(self.prompt_path))


class Provider:
    key = ProviderKey.CODEX

    def __init__(self, executable: str = str(Path(sys.executable).resolve())) -> None:
        self.executable = executable
        self.calls: list[tuple[Path, str]] = []

    def build_interactive_argv(self, workspace_root: Path, prompt_text: str):
        self.calls.append((workspace_root, prompt_text))
        return (self.executable, "-c", "pass")


class Tmux:
    def __init__(
        self,
        *presence: bool,
        create_failure: Exception | None = None,
        attach_code: int = 0,
    ) -> None:
        self.presence = list(presence or (False, True))
        self.create_failure = create_failure
        self.attach_code = attach_code
        self.created: list[tuple[str, Path]] = []
        self.attached: list[str] = []
        self.killed: list[str] = []

    def has_session(self, name: str) -> bool:
        if len(self.presence) > 1:
            return self.presence.pop(0)
        return self.presence[0]

    def create_session(self, name: str, descriptor: Path) -> None:
        self.created.append((name, descriptor))
        if self.create_failure is not None:
            raise self.create_failure

    def attach(self, name: str) -> int:
        self.attached.append(name)
        return self.attach_code

    def kill_session(self, name: str) -> None:
        self.killed.append(name)
        self.presence = [False]


class Schema:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def validate(self, name, document) -> None:
        self.calls.append((name, document))


class Pipe:
    def __init__(
        self,
        failure: Exception | None = None,
        *,
        disable_failure: Exception | None = None,
        active: bool = False,
        probe_failure: Exception | None = None,
        session_present: bool = True,
        termination_failure: Exception | None = None,
        session_probe_failure: Exception | None = None,
    ) -> None:
        self.failure = failure
        self.disable_failure = disable_failure
        self.active = active
        self.probe_failure = probe_failure
        self.owning_session_present = session_present
        self.termination_failure = termination_failure
        self.session_probe_failure = session_probe_failure
        self.configured: list[tuple[RunRecord, Path]] = []
        self.disabled: list[RunRecord] = []

    def configure(self, *, run: RunRecord, output_path: Path) -> None:
        self.configured.append((run, output_path))
        self.active = True
        if self.failure is not None:
            raise self.failure

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

    def session_present(self, *, run: RunRecord) -> bool:
        if self.session_probe_failure is not None:
            raise self.session_probe_failure
        return self.owning_session_present


class CapturePipe(Pipe):
    def __init__(self, *statuses: TranscriptState | None) -> None:
        super().__init__(active=True)
        self.statuses = list(statuses)
        self.status_calls: list[RunRecord] = []

    def capture_status(self, *, run: RunRecord) -> TranscriptState | None:
        self.status_calls.append(run)
        if len(self.statuses) > 1:
            return self.statuses.pop(0)
        return self.statuses[0] if self.statuses else None


class Watcher:
    def __init__(self, observed, *, semantic_ready: bool = True) -> None:
        self.observed = observed
        self.semantic_ready = semantic_ready
        self.calls: list[tuple[RunRecord, tuple[str, ...]]] = []

    def observe_once(self, run, paths):
        self.calls.append((run, tuple(paths)))
        return self.observed

    def semantic_gate_ready(self, run, gate_id) -> bool:
        return self.semantic_ready


class Runner:
    def __init__(self, result: ValidatorResult) -> None:
        self.result = result
        self.calls: list[tuple[object, ...]] = []

    def run(self, key, **kwargs):
        self.calls.append((key, kwargs))
        return self.result


class Identity:
    def __init__(self, actor: Actor) -> None:
        self.actor = actor
        self.calls = 0

    def current_actor(self) -> Actor:
        self.calls += 1
        return self.actor


def _launch_service(
    workspace: Path,
    runtime_root: Path,
    *,
    tmux: Tmux | None = None,
    provider: Provider | None = None,
    providers=None,
    authorization: Authorization | None = None,
    watcher: Watcher | None = None,
    pipe: Pipe | None = None,
    clock: Clock | None = None,
):
    prompt = workspace / "agents/templates/prompts/evidence-contract/feature-operator-friendly.md"
    repository = Repository(runtime_root)
    schema = Schema()
    provider = provider or Provider()
    service = RunService(
        workspace_root=workspace,
        preflight=Preflight(prompt),
        authorization=authorization or Authorization(),
        repository=repository,
        providers={ProviderKey.CODEX: provider} if providers is None else providers,
        tmux=tmux or Tmux(),
        schema=schema,
        clock=clock or Clock(NOW, NOW + timedelta(seconds=1), NOW + timedelta(seconds=2)),
        watcher=watcher,
        transcript_pipe=pipe,
    )
    return service, repository, schema, provider


def _request(**changes) -> LaunchRequest:
    values = {
        "feature_id": "F0001",
        "story_id": None,
        "provider_key": ProviderKey.CODEX,
        "prompt_action": PromptAction.FEATURE,
        "requested_run_id": RUN_ID,
    }
    values.update(changes)
    return LaunchRequest(**values)


def test_runtime_event_assigns_next_or_explicit_sequence(tmp_path: Path) -> None:
    run = _run(tmp_path)
    automatic = runtime_event(run, OWNER, "Observed", NOW)
    explicit = runtime_event(run, OWNER, "Initial", NOW, {"safe": True}, sequence=1)
    assert automatic.sequence == run.last_event_sequence + 1
    assert automatic.payload == {}
    assert explicit.sequence == 1
    assert explicit.payload == {"safe": True}
    assert explicit.correlation_id != automatic.correlation_id


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"feature_id": "1"}, ErrorCode.USAGE_ERROR),
        ({"feature_id": "F9999"}, ErrorCode.PROMPT_NOT_FOUND),
        ({"story_id": "F0002-S0001"}, ErrorCode.USAGE_ERROR),
        ({"story_id": "F0001-S9999"}, ErrorCode.PROMPT_NOT_FOUND),
        ({"requested_run_id": "unsafe"}, ErrorCode.USAGE_ERROR),
        ({"run_label": "\x00unsafe"}, ErrorCode.USAGE_ERROR),
        ({"run_label": " "}, ErrorCode.USAGE_ERROR),
        ({"run_label": "x" * 81}, ErrorCode.USAGE_ERROR),
    ],
)
def test_launch_rejects_invalid_governed_identifiers_and_labels(
    workspace: Path, runtime_root: Path, changes, code
) -> None:
    service, repository, _, _ = _launch_service(workspace, runtime_root)
    with pytest.raises(NebulaError) as caught:
        service.launch(_request(**changes), OWNER)
    assert caught.value.code is code
    assert repository.created == []


def test_launch_accepts_committed_story_and_persists_private_descriptor(
    workspace: Path, runtime_root: Path
) -> None:
    story = workspace / "planning-mds/features/F0001-test-feature/stories/F0001-S0001-test.md"
    story.parent.mkdir()
    story.write_text("# Story\n", encoding="utf-8")
    evidence = workspace / "planning-mds/operations/evidence/runs" / RUN_ID
    evidence.mkdir(parents=True)
    tmux = Tmux(False, True)
    service, repository, schema, provider = _launch_service(
        workspace, runtime_root, tmux=tmux
    )

    result = service.launch(_request(story_id="F0001-S0001", run_label=" accepted "), OWNER)

    assert result.status is RunStatus.ACTIVE
    assert result.revision == 1
    assert result.evidence_root == str(evidence)
    assert result.transcript.status is TranscriptStatus.DISABLED
    assert repository.created[0][1].event_type == "LaunchRequested"
    requested_payload = repository.created[0][1].payload
    assert requested_payload["command_template"] == (
        "codex <committed-action-prompt>"
    )
    assert str(workspace) not in requested_payload["command_template"]
    assert "# Safe feature test prompt" not in requested_payload["command_template"]
    assert [item[2].event_type for item in repository.commits] == ["RunLaunched"]
    assert provider.calls[0][1] == "# Safe feature test prompt\n"
    descriptor = tmux.created[0][1]
    assert descriptor.stat().st_mode & 0o777 == 0o600
    assert schema.calls[0][0] == "f0001-launch-descriptor.schema.json"
    assert schema.calls[0][1]["executable_path"] == str(Path(sys.executable).resolve())


def test_launch_canonicalizes_provider_executable_symlink(
    workspace: Path, runtime_root: Path
) -> None:
    executable_link = runtime_root / "provider"
    executable_link.symlink_to(sys.executable)
    provider = Provider(str(executable_link))
    service, _, schema, _ = _launch_service(
        workspace,
        runtime_root,
        provider=provider,
        tmux=Tmux(False, True),
    )
    service.launch(_request(), OWNER)
    assert schema.calls[0][1]["executable_path"] == str(Path(sys.executable).resolve())
    assert schema.calls[0][1]["argv"][0] == str(Path(sys.executable).resolve())


def test_launch_checks_both_mutation_permissions_when_transcript_requested(
    workspace: Path, runtime_root: Path
) -> None:
    authorization = Authorization(denied=Action.CONFIGURE_TRANSCRIPT)
    service, repository, _, _ = _launch_service(
        workspace, runtime_root, authorization=authorization
    )
    with pytest.raises(NebulaError) as caught:
        service.launch(_request(transcript_enabled=True), OWNER)
    assert caught.value.code is ErrorCode.FORBIDDEN
    assert [item[1] for item in authorization.required] == [
        Action.LAUNCH,
        Action.CONFIGURE_TRANSCRIPT,
    ]
    assert repository.created == []


def test_launch_rejects_unregistered_provider_after_preflight(
    workspace: Path, runtime_root: Path
) -> None:
    service, _, _, _ = _launch_service(workspace, runtime_root, providers={})
    with pytest.raises(NebulaError) as caught:
        service.launch(_request(), OWNER)
    assert caught.value.code is ErrorCode.PROVIDER_NOT_FOUND


def test_launch_rejects_existing_tmux_session(
    workspace: Path, runtime_root: Path
) -> None:
    service, repository, _, _ = _launch_service(
        workspace, runtime_root, tmux=Tmux(True)
    )
    with pytest.raises(NebulaError) as caught:
        service.launch(_request(), OWNER)
    assert caught.value.code is ErrorCode.CONFLICT
    assert caught.value.details == (
        {"colliding_session": "nebula-F0001-deadbeef"},
    )
    assert len(caught.value.details[0]["colliding_session"]) <= 80
    assert repository.created == []


def test_launch_rejects_symlinked_feature_directory_before_authorization(
    workspace: Path, runtime_root: Path
) -> None:
    feature = workspace / "planning-mds" / "features" / "F0001-test-feature"
    feature.rmdir()
    outside = workspace.parent / "outside-feature"
    outside.mkdir()
    feature.symlink_to(outside, target_is_directory=True)
    service, repository, _, _ = _launch_service(workspace, runtime_root)

    with pytest.raises(NebulaError) as caught:
        service.launch(_request(), OWNER)

    assert caught.value.code is ErrorCode.PROMPT_NOT_FOUND
    assert repository.created == []


def test_launch_rejects_symlinked_story_file(
    workspace: Path, runtime_root: Path
) -> None:
    feature = workspace / "planning-mds" / "features" / "F0001-test-feature"
    stories = feature / "stories"
    stories.mkdir()
    outside = workspace.parent / "outside-story.md"
    outside.write_text("untrusted story", encoding="utf-8")
    (stories / "F0001-S0001-link.md").symlink_to(outside)
    service, repository, _, _ = _launch_service(workspace, runtime_root)

    with pytest.raises(NebulaError) as caught:
        service.launch(_request(story_id="F0001-S0001"), OWNER)

    assert caught.value.code is ErrorCode.PROMPT_NOT_FOUND
    assert repository.created == []


def test_launch_maps_unreadable_prompt_to_stable_error(
    workspace: Path, runtime_root: Path
) -> None:
    prompt = workspace / "agents/templates/prompts/evidence-contract/feature-operator-friendly.md"
    prompt.unlink()
    service, _, _, _ = _launch_service(workspace, runtime_root)
    with pytest.raises(NebulaError) as caught:
        service.launch(_request(), OWNER)
    assert caught.value.code is ErrorCode.PROMPT_NOT_FOUND


@pytest.mark.parametrize("failure", [RuntimeError("tmux failed"), None])
def test_launch_failure_is_audited_and_removes_descriptor(
    workspace: Path, runtime_root: Path, failure: Exception | None
) -> None:
    tmux = Tmux(False, False, create_failure=failure)
    service, repository, _, _ = _launch_service(
        workspace, runtime_root, tmux=tmux
    )
    with pytest.raises((RuntimeError, NebulaError)) as caught:
        service.launch(_request(), OWNER)
    if failure is None:
        assert caught.value.code is ErrorCode.COMMAND_FAILED
    assert repository.commits[-1][1].status is RunStatus.FAILED
    assert repository.commits[-1][2].event_type == "LaunchFailed"
    assert not tmux.created[0][1].exists()


def test_launch_preserves_original_failure_when_failure_audit_cannot_commit(
    workspace: Path, runtime_root: Path
) -> None:
    service, repository, _, _ = _launch_service(
        workspace,
        runtime_root,
        tmux=Tmux(False, create_failure=ValueError("provider failed")),
    )
    repository.fail_event_type = "LaunchFailed"
    with pytest.raises(ValueError, match="provider failed"):
        service.launch(_request(), OWNER)
    assert repository.commits[-1][2].event_type == "LaunchFailed"


def test_launch_commit_failure_kills_created_session_and_persists_terminal_state(
    workspace: Path, runtime_root: Path
) -> None:
    tmux = Tmux(False, True)
    service, repository, _, _ = _launch_service(
        workspace, runtime_root, tmux=tmux
    )
    repository.fail_event_type = "RunLaunched"

    with pytest.raises(RuntimeError, match="failed RunLaunched"):
        service.launch(_request(), OWNER)

    assert tmux.killed == ["nebula-F0001-deadbeef"]
    assert tmux.presence == [False]
    persisted = repository.records[RUN_ID]
    assert persisted.status is RunStatus.FAILED
    assert safe_run_projection(persisted, OWNER, Authorization()).can_attach is False
    assert [item[2].event_type for item in repository.commits] == [
        "RunLaunched",
        "LaunchFailed",
    ]
    assert repository.commits[-1][2].payload["session_compensation"] == "completed"
    assert not tmux.created[0][1].exists()


def test_descriptor_validation_failure_is_audited_as_failed_launch(
    workspace: Path, runtime_root: Path
) -> None:
    service, repository, schema, _ = _launch_service(workspace, runtime_root)

    def reject_descriptor(_name, _document) -> None:
        raise RuntimeError("descriptor contract unavailable")

    schema.validate = reject_descriptor
    with pytest.raises(RuntimeError, match="descriptor contract unavailable"):
        service.launch(_request(), OWNER)
    assert repository.created[0][1].event_type == "LaunchRequested"
    assert repository.commits[-1][1].status is RunStatus.FAILED
    assert repository.commits[-1][2].event_type == "LaunchFailed"


@pytest.mark.parametrize(
    ("pipe", "expected_status", "event_type"),
    [
        (None, TranscriptStatus.FAILED, "TranscriptFailed"),
        (Pipe(), TranscriptStatus.ACTIVE, "TranscriptEnabled"),
        (Pipe(RuntimeError("pipe failed")), TranscriptStatus.FAILED, "TranscriptFailed"),
    ],
)
def test_launch_isolates_transcript_configuration_from_active_session(
    workspace: Path,
    runtime_root: Path,
    pipe: Pipe | None,
    expected_status: TranscriptStatus,
    event_type: str,
) -> None:
    service, repository, _, _ = _launch_service(
        workspace, runtime_root, pipe=pipe, tmux=Tmux(False, True)
    )
    result = service.launch(_request(transcript_enabled=True), OWNER)
    assert result.status is RunStatus.ACTIVE
    assert result.transcript.status is expected_status
    assert repository.commits[-1][2].event_type == event_type


def test_attach_commits_observation_before_delegating_to_tmux(tmp_path: Path) -> None:
    run = _run(tmp_path)
    repository = Repository(tmp_path, (run,))
    tmux = Tmux(True, attach_code=17)
    service = RunService(
        workspace_root=tmp_path,
        preflight=Preflight(tmp_path / "prompt"),
        authorization=Authorization(),
        repository=repository,
        providers={},
        tmux=tmux,
        schema=Schema(),
        clock=Clock(NOW + timedelta(minutes=1)),
    )
    assert service.attach(run.run_id, OWNER) == 17
    assert repository.commits[0][1].last_seen_at == NOW + timedelta(minutes=1)
    assert repository.commits[0][2].event_type == "SessionAttached"
    assert tmux.attached == [run.tmux_session]


def test_attach_never_relaunches_missing_session(tmp_path: Path) -> None:
    run = _run(tmp_path)
    repository = Repository(tmp_path, (run,))
    tmux = Tmux(False)
    service = RunService(
        workspace_root=tmp_path,
        preflight=Preflight(tmp_path / "prompt"),
        authorization=Authorization(),
        repository=repository,
        providers={},
        tmux=tmux,
        schema=Schema(),
        clock=Clock(),
    )
    with pytest.raises(NebulaError) as caught:
        service.attach(run.run_id, OWNER)
    assert caught.value.code is ErrorCode.SESSION_NOT_FOUND
    assert tmux.created == []
    assert repository.commits == []


@pytest.mark.parametrize("status", [RunStatus.FAILED, RunStatus.EXITED])
def test_attach_rejects_terminal_run_even_when_tmux_name_is_still_present(
    tmp_path: Path, status: RunStatus
) -> None:
    run = _run(tmp_path, status=status)
    repository = Repository(tmp_path, (run,))
    tmux = Tmux(True)
    service = RunService(
        workspace_root=tmp_path,
        preflight=Preflight(tmp_path / "prompt"),
        authorization=Authorization(),
        repository=repository,
        providers={},
        tmux=tmux,
        schema=Schema(),
        clock=Clock(),
    )

    with pytest.raises(NebulaError) as caught:
        service.attach(run.run_id, OWNER)

    assert caught.value.code is ErrorCode.SESSION_NOT_FOUND
    assert tmux.attached == []
    assert repository.commits == []
    projection = safe_run_projection(run, OWNER, Authorization())
    assert projection.can_attach is False
    assert projection.tmux_session is None


@pytest.mark.parametrize(
    ("status", "presence", "expected_status", "event_type", "committed"),
    [
        (RunStatus.ACTIVE, (True,), RunStatus.ACTIVE, None, False),
        (
            RunStatus.DETACHED_OR_EXITED,
            (False, True),
            RunStatus.ACTIVE,
            "SessionRecovered",
            True,
        ),
        (
            RunStatus.ACTIVE,
            (False, False),
            RunStatus.DETACHED_OR_EXITED,
            "SessionMissing",
            True,
        ),
        (RunStatus.FAILED, (False, False), RunStatus.FAILED, None, False),
    ],
)
def test_reconcile_preserves_terminal_state_and_recovers_same_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status,
    presence,
    expected_status,
    event_type,
    committed,
) -> None:
    run = _run(tmp_path, status=status)
    repository = Repository(tmp_path, (run,))
    monkeypatch.setattr("nebula_agents.application.runs.time.sleep", lambda _: None)
    service = RunService(
        workspace_root=tmp_path,
        preflight=Preflight(tmp_path / "prompt"),
        authorization=Authorization(),
        repository=repository,
        providers={},
        tmux=Tmux(*presence),
        schema=Schema(),
        clock=Clock(NOW + timedelta(minutes=1)),
    )
    result = service.reconcile(run.run_id, OWNER)
    assert result.status is expected_status
    assert bool(repository.commits) is committed
    if committed:
        assert repository.commits[0][2].event_type == event_type


def test_reviewer_reconcile_returns_private_projection_without_persisting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _run(tmp_path, status=RunStatus.ACTIVE)
    repository = Repository(tmp_path, (run,))
    monkeypatch.setattr("nebula_agents.application.runs.time.sleep", lambda _: None)
    service = RunService(
        workspace_root=tmp_path,
        preflight=Preflight(tmp_path / "prompt"),
        authorization=Authorization(),
        repository=repository,
        providers={},
        tmux=Tmux(False, False),
        schema=Schema(),
        clock=Clock(NOW + timedelta(minutes=1)),
    )

    projection = service.reconcile(run.run_id, REVIEWER)

    assert projection.status is RunStatus.DETACHED_OR_EXITED
    assert projection.revision == run.revision
    assert projection.workspace_root is None
    assert projection.prompt_contract is None
    assert projection.audit_log_path is None
    assert projection.tmux_session is None
    assert projection.can_recover is False
    assert projection.recovery_available is True
    assert repository.records[RUN_ID] is run
    assert repository.commits == []


def test_reconcile_persists_ongoing_filter_failure_without_losing_attach(
    tmp_path: Path,
) -> None:
    transcript_path = tmp_path / "runs" / RUN_ID / "transcript.redacted.log"
    active = TranscriptState(
        TranscriptStatus.ACTIVE,
        RedactionStatus.NOT_RUN,
        str(transcript_path),
        None,
        1,
    )
    failed = TranscriptState(
        TranscriptStatus.FAILED,
        RedactionStatus.FAILED,
        str(transcript_path),
        None,
        1,
        "filter-process-failed",
    )
    run = _run(tmp_path, transcript=active)
    repository = Repository(tmp_path, (run,))
    pipe = CapturePipe(failed)
    service = RunService(
        workspace_root=tmp_path,
        preflight=Preflight(tmp_path / "prompt"),
        authorization=Authorization(),
        repository=repository,
        providers={},
        tmux=Tmux(True),
        schema=Schema(),
        clock=Clock(NOW + timedelta(minutes=1)),
        transcript_pipe=pipe,
    )

    projection = service.reconcile(run.run_id, OWNER)

    assert projection.status is RunStatus.ACTIVE
    assert projection.transcript.status is TranscriptStatus.FAILED
    assert projection.transcript.redaction_status is RedactionStatus.FAILED
    assert projection.can_attach is True
    assert projection.tmux_session == run.tmux_session
    assert repository.records[RUN_ID].transcript == failed
    assert projection.transcript.failure_reason == "filter-process-failed"
    assert repository.commits[-1][2].event_type == "TranscriptFailed"
    assert repository.commits[-1][2].payload["error_category"] == (
        "filter-process-failed"
    )


def test_reconcile_persists_completed_sidecar_after_restart(tmp_path: Path) -> None:
    transcript_path = tmp_path / "runs" / RUN_ID / "transcript.redacted.log"
    active = TranscriptState(
        TranscriptStatus.ACTIVE,
        RedactionStatus.NOT_RUN,
        str(transcript_path),
        None,
        1,
    )
    completed = TranscriptState(
        TranscriptStatus.COMPLETED,
        RedactionStatus.REDACTED,
        str(transcript_path),
        None,
        3,
    )
    run = _run(tmp_path, transcript=active)
    repository = Repository(tmp_path, (run,))
    service = RunService(
        workspace_root=tmp_path,
        preflight=Preflight(tmp_path / "prompt"),
        authorization=Authorization(),
        repository=repository,
        providers={},
        tmux=Tmux(True),
        schema=Schema(),
        clock=Clock(NOW + timedelta(minutes=1)),
        transcript_pipe=CapturePipe(completed),
    )

    projection = service.reconcile(run.run_id, OWNER)

    assert projection.transcript == completed
    assert repository.records[RUN_ID].transcript == completed
    assert repository.commits[-1][2].event_type == "TranscriptCompleted"
    assert repository.commits[-1][2].payload == {
        "status": "Completed",
        "redaction_findings": 3,
    }


def test_observe_evidence_requires_composed_watcher(tmp_path: Path) -> None:
    run = _run(tmp_path)
    service = RunService(
        workspace_root=tmp_path,
        preflight=Preflight(tmp_path / "prompt"),
        authorization=Authorization(),
        repository=Repository(tmp_path, (run,)),
        providers={},
        tmux=Tmux(),
        schema=Schema(),
        clock=Clock(),
    )
    with pytest.raises(NebulaError) as caught:
        service.observe_evidence(run.run_id, ("required.md",), OWNER)
    assert caught.value.code is ErrorCode.COMMAND_FAILED


def test_public_observe_evidence_preserves_last_valid_artifact_on_malformed_update(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    evidence = workspace / "evidence"
    evidence.mkdir(parents=True)
    report = evidence / "review.md"
    report.write_text("# Valid review\n", encoding="utf-8")
    watcher = PollingEvidenceWatcher(Clock())
    base = replace(_run(workspace), evidence_root=str(evidence))
    valid = watcher.observe_once(base, ("review.md",))
    run = replace(
        base,
        artifacts=valid,
        gate=replace(base.gate, evidence_ready=True, status=GateStatus.PENDING),
    )
    repository = Repository(tmp_path / "runtime", (run,))
    service = RunService(
        workspace_root=workspace,
        preflight=Preflight(workspace / "prompt"),
        authorization=Authorization(),
        repository=repository,
        providers={},
        tmux=Tmux(),
        schema=Schema(),
        clock=Clock(NOW + timedelta(minutes=1)),
        watcher=watcher,
    )
    report.write_text("```unterminated", encoding="utf-8")

    projection = service.observe_evidence(
        run.run_id, ("review.md",), OWNER
    )

    assert projection.gate.status is GateStatus.BLOCKED
    assert projection.gate.evidence_ready is False
    assert projection.artifacts == valid
    assert repository.records[RUN_ID] is run
    assert repository.commits == []


def test_malformed_manifest_blocks_projection_preserves_last_valid_g3_and_restores(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    evidence = (
        workspace
        / "planning-mds"
        / "operations"
        / "evidence"
        / "runs"
        / RUN_ID
    )
    evidence.mkdir(parents=True)
    manifest_document = {
        "feature_id": "F0001",
        "status": "in-progress",
        "runtime_bearing": False,
        "required_roles": ["Code Reviewer", "Security Reviewer"],
        "gate_results": {
            "assembly_plan_validation": {"result": "PASS"},
            "self_review": {"result": "PASS"},
        },
        "role_results": {
            "Code Reviewer": {"result": "PASS"},
            "Security Reviewer": {"result": "PASS"},
        },
    }
    manifest = evidence / "evidence-manifest.json"
    manifest.write_text(json.dumps(manifest_document), encoding="utf-8")
    for name in (
        "code-review-report.md",
        "security-review-report.md",
        "gate-decisions.md",
    ):
        (evidence / name).write_text("valid", encoding="utf-8")
    artifacts = tuple(
        ArtifactObservation(
            name,
            ArtifactStatus.AVAILABLE,
            NOW,
            (evidence / name).stat().st_size,
        )
        for name in (
            "evidence-manifest.json",
            "code-review-report.md",
            "security-review-report.md",
        )
    )
    base = _run(workspace, artifacts=artifacts)
    validator = replace(
        _validator(),
        gate_id="G3",
        validated_revision=base.revision,
        evidence_digest="a" * 64,
    )
    persisted = replace(
        base,
        evidence_root=str(evidence.resolve()),
        gate=GateSnapshot(
            "G3",
            GateStatus.PENDING,
            True,
            (
                "evidence-manifest.json",
                "code-review-report.md",
                "security-review-report.md",
            ),
            None,
        ),
        latest_validator=validator,
    )
    watcher = PollingEvidenceWatcher(Clock())
    repository = Repository(tmp_path / "runtime", (persisted,))
    service = RunService(
        workspace_root=workspace,
        preflight=Preflight(workspace / "prompt"),
        authorization=Authorization(),
        repository=repository,
        providers={},
        tmux=Tmux(True),
        schema=Schema(),
        clock=Clock(NOW + timedelta(minutes=1)),
        watcher=watcher,
    )
    manifest.write_text("{", encoding="utf-8")

    blocked_projection = service.reconcile(persisted.run_id, OWNER)

    assert blocked_projection.gate.gate_id == "G3"
    assert blocked_projection.gate.status is GateStatus.BLOCKED
    assert blocked_projection.gate.evidence_ready is False
    assert repository.records[RUN_ID] is persisted
    assert repository.records[RUN_ID].gate.status is GateStatus.PENDING
    assert repository.records[RUN_ID].artifacts == artifacts
    assert repository.records[RUN_ID].evidence_root == str(evidence.resolve())
    assert repository.commits == []

    approval_repository = AuthorizedRepository(tmp_path / "approval", (persisted,))
    gate_service = GateService(
        repository=approval_repository,
        authorization=Authorization(),
        runner=Runner(_validator()),
        clock=Clock(NOW + timedelta(minutes=2)),
        watcher=watcher,
    )
    with pytest.raises(NebulaError) as caught:
        gate_service.decide(
            GateDecisionRequest(
                RUN_ID,
                "G3",
                DecisionKind.APPROVE,
                None,
                None,
                persisted.revision,
                True,
            ),
            OWNER,
        )
    assert caught.value.code is ErrorCode.GATE_BLOCKED
    assert approval_repository.commits[-1][2].event_type == "GateDecisionBlocked"

    manifest.write_text(json.dumps(manifest_document), encoding="utf-8")
    restored = service.reconcile(persisted.run_id, OWNER)

    assert restored.gate.gate_id == "G4"
    assert restored.gate.status is GateStatus.PENDING
    assert restored.gate.evidence_ready is True
    assert repository.records[RUN_ID].gate.gate_id == "G4"
    assert repository.records[RUN_ID].evidence_root == str(evidence.resolve())
    assert repository.commits[-1][2].event_type == "ArtifactObserved"


@pytest.mark.parametrize(
    ("observed", "expected_status", "ready", "event_type"),
    [
        (
            (
                ArtifactObservation(
                    "required.md", ArtifactStatus.AVAILABLE, NOW, 10
                ),
            ),
            GateStatus.PENDING,
            True,
            "ArtifactObserved",
        ),
        (
            (ArtifactObservation("required.md", ArtifactStatus.MISSING, NOW, None),),
            GateStatus.BLOCKED,
            False,
            "ArtifactUnavailable",
        ),
    ],
)
def test_observe_evidence_updates_gate_from_all_artifacts(
    tmp_path: Path, observed, expected_status, ready, event_type
) -> None:
    run = _run(tmp_path)
    repository = Repository(tmp_path, (run,))
    watcher = Watcher(observed)
    service = RunService(
        workspace_root=tmp_path,
        preflight=Preflight(tmp_path / "prompt"),
        authorization=Authorization(),
        repository=repository,
        providers={},
        tmux=Tmux(),
        schema=Schema(),
        clock=Clock(NOW + timedelta(minutes=1)),
        watcher=watcher,
    )
    result = service.observe_evidence(run.run_id, ("required.md",), OWNER)
    assert result.artifacts == observed
    assert result.gate.status is expected_status
    assert result.gate.evidence_ready is ready
    assert repository.commits[0][2].event_type == event_type


def test_observe_evidence_is_pure_when_projection_is_unchanged(tmp_path: Path) -> None:
    artifact = ArtifactObservation("required.md", ArtifactStatus.AVAILABLE, NOW, 10)
    run = _run(tmp_path, artifacts=(artifact,))
    repository = Repository(tmp_path, (run,))
    service = RunService(
        workspace_root=tmp_path,
        preflight=Preflight(tmp_path / "prompt"),
        authorization=Authorization(),
        repository=repository,
        providers={},
        tmux=Tmux(),
        schema=Schema(),
        clock=Clock(),
        watcher=Watcher((artifact,)),
    )
    projection = service.observe_evidence(run.run_id, ("required.md",), OWNER)
    assert projection.run_id == run.run_id
    assert projection.artifacts == run.artifacts
    assert projection.revision == run.revision
    assert repository.commits == []


def test_reviewer_observe_evidence_projects_fresh_state_without_persisting(
    tmp_path: Path,
) -> None:
    observed = (
        ArtifactObservation("required.md", ArtifactStatus.AVAILABLE, NOW, 8),
    )
    run = _run(tmp_path)
    repository = Repository(tmp_path, (run,))
    service = RunService(
        workspace_root=tmp_path,
        preflight=Preflight(tmp_path / "prompt"),
        authorization=Authorization(),
        repository=repository,
        providers={},
        tmux=Tmux(),
        schema=Schema(),
        clock=Clock(NOW + timedelta(minutes=1)),
        watcher=Watcher(observed),
    )

    projection = service.observe_evidence(
        run.run_id, ("required.md",), REVIEWER
    )

    assert projection.artifacts == observed
    assert projection.gate.evidence_ready is True
    assert projection.revision == run.revision
    assert projection.workspace_root is None
    assert projection.evidence_root is None
    assert repository.records[RUN_ID] is run
    assert repository.commits == []


def test_recovery_commits_attempted_then_applied_audit_events(tmp_path: Path) -> None:
    owner = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    recovered = _run(tmp_path, status=RunStatus.DETACHED_OR_EXITED, owner=owner)
    repository = RecoverRepository(tmp_path, recovered)
    service = RunService(
        workspace_root=tmp_path,
        preflight=Preflight(tmp_path / "prompt"),
        authorization=Authorization(),
        repository=repository,
        providers={},
        tmux=Tmux(),
        schema=Schema(),
        clock=Clock(NOW + timedelta(minutes=1), NOW + timedelta(minutes=2)),
    )

    projection = service.recover(
        recovered.run_id, owner, expected_revision=recovered.revision
    )

    assert repository.recover_calls == [RUN_ID]
    assert [item[2].event_type for item in repository.commits] == [
        "RecoveryAttempted",
        "StateRecoveryApplied",
    ]
    assert repository.commits[0][2].payload == {
        "source": "validated-state-image"
    }
    assert repository.commits[1][2].payload == {
        "recovered_revision": recovered.revision
    }
    assert projection.revision == recovered.revision + 2
    assert projection.run_id == recovered.run_id
    assert projection.can_recover is True


def test_recovery_rejects_stale_latest_revision_before_restore(tmp_path: Path) -> None:
    owner = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    current = _run(tmp_path, status=RunStatus.DETACHED_OR_EXITED, owner=owner)
    repository = RecoverRepository(tmp_path, current)
    service = RunService(
        workspace_root=tmp_path,
        preflight=Preflight(tmp_path / "prompt"),
        authorization=Authorization(),
        repository=repository,
        providers={},
        tmux=Tmux(),
        schema=Schema(),
        clock=Clock(),
    )

    with pytest.raises(NebulaError) as caught:
        service.recover(current.run_id, owner, expected_revision=current.revision - 1)

    assert caught.value.code is ErrorCode.STALE_REVISION
    assert caught.value.details == ({"current_revision": current.revision},)
    assert repository.recover_calls == []
    assert repository.commits == []


def test_recovery_rejects_stale_recovered_image_after_corrupt_latest(
    tmp_path: Path,
) -> None:
    owner = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    recovered = _run(tmp_path, status=RunStatus.DETACHED_OR_EXITED, owner=owner)
    repository = RecoverRepository(tmp_path, recovered, corrupt_latest=True)
    service = RunService(
        workspace_root=tmp_path,
        preflight=Preflight(tmp_path / "prompt"),
        authorization=Authorization(),
        repository=repository,
        providers={},
        tmux=Tmux(),
        schema=Schema(),
        clock=Clock(),
    )

    with pytest.raises(NebulaError) as caught:
        service.recover(
            recovered.run_id, owner, expected_revision=recovered.revision - 1
        )

    assert caught.value.code is ErrorCode.STALE_REVISION
    assert caught.value.details == ({"current_revision": recovered.revision},)
    assert repository.recover_calls == [RUN_ID]
    assert repository.commits == []


def test_recovery_denies_reviewer_before_repository_access(tmp_path: Path) -> None:
    run = _run(tmp_path, status=RunStatus.DETACHED_OR_EXITED)
    repository = RecoverRepository(tmp_path, run)
    service = RunService(
        workspace_root=tmp_path,
        preflight=Preflight(tmp_path / "prompt"),
        authorization=Authorization(),
        repository=repository,
        providers={},
        tmux=Tmux(),
        schema=Schema(),
        clock=Clock(),
    )

    with pytest.raises(NebulaError) as caught:
        service.recover(run.run_id, REVIEWER, expected_revision=run.revision)

    assert caught.value.code is ErrorCode.FORBIDDEN
    assert repository.recover_calls == []
    assert repository.commits == []


def test_recovery_projection_contains_exact_safe_operator_guidance(
    tmp_path: Path,
) -> None:
    owner = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    path = tmp_path / "runs" / RUN_ID / "transcript.redacted.log"
    path.parent.mkdir(parents=True)
    path.write_text("safe", encoding="utf-8")
    path.chmod(0o600)
    run = replace(
        _run(tmp_path, status=RunStatus.DETACHED_OR_EXITED, owner=owner),
        gate=GateSnapshot("G3", GateStatus.HELD, True, ("review.md",), None),
        transcript=TranscriptState(
            TranscriptStatus.COMPLETED,
            RedactionStatus.PASSED,
            str(path),
            None,
            0,
        ),
    )
    last_event = AuditEventSummary(7, "TranscriptCompleted", NOW)
    repository = RecoveryListingRepository(
        tmp_path, RecoverableRun(run, last_event)
    )
    service = QueryService(
        repository=repository,
        authorization=Authorization(),
        identity=Identity(owner),
    )

    projection = service.recovery_status(RUN_ID, owner)

    assert projection.run_id == RUN_ID
    assert projection.recoverable_revision == run.revision
    assert projection.recovery_available is True
    assert projection.can_recover is True
    assert projection.last_gate == run.gate
    assert projection.last_audit_event == last_event
    assert projection.transcript_path == str(path)
    assert projection.recovery_command == (
        f"nebula-agents recover --run-id {RUN_ID} "
        f"--expected-revision {run.revision}"
    )


def test_recovery_projection_hides_private_path_and_mutation_from_reviewer(
    tmp_path: Path,
) -> None:
    owner = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)
    path = tmp_path / "runs" / RUN_ID / "transcript.redacted.log"
    path.parent.mkdir(parents=True)
    run = replace(
        _run(tmp_path, status=RunStatus.FAILED, owner=owner),
        transcript=TranscriptState(
            TranscriptStatus.FAILED,
            RedactionStatus.FAILED,
            str(path),
            None,
            0,
            "capture-process-not-running",
        ),
    )
    reviewer = Actor(owner.uid, "reviewer", Role.REVIEWER)
    repository = RecoveryListingRepository(
        tmp_path, RecoverableRun(run, AuditEventSummary(4, "TranscriptFailed", NOW))
    )
    service = QueryService(
        repository=repository,
        authorization=Authorization(),
        identity=Identity(reviewer),
    )

    projection = service.recovery_status(RUN_ID, reviewer)

    assert projection.can_recover is False
    assert projection.transcript_path is None
    assert projection.recovery_command is None


def _validator(exit_code: int = 0) -> ValidatorResult:
    return ValidatorResult(
        ValidatorKey.STORIES,
        exit_code,
        25,
        "safe summary",
        "validator.md",
        NOW,
        "python3 validate-stories.py --product-root {workspace} {feature}",
    )


@pytest.mark.parametrize(
    ("exit_code", "artifact_status", "gate_status", "event_type"),
    [
        (0, ArtifactStatus.AVAILABLE, GateStatus.PENDING, "ValidatorCompleted"),
        (1, ArtifactStatus.AVAILABLE, GateStatus.BLOCKED, "ValidatorCompleted"),
        (0, ArtifactStatus.MISSING, GateStatus.BLOCKED, "ValidatorCompleted"),
        (124, ArtifactStatus.AVAILABLE, GateStatus.BLOCKED, "ValidatorTimedOut"),
    ],
)
def test_validator_result_and_required_evidence_jointly_control_gate(
    tmp_path: Path, exit_code, artifact_status, gate_status, event_type
) -> None:
    artifact = ArtifactObservation("required.md", artifact_status, NOW, 1)
    run = _run(tmp_path, artifacts=(artifact,))
    if artifact_status is ArtifactStatus.AVAILABLE:
        (tmp_path / "required.md").write_text("evidence", encoding="utf-8")
    repository = Repository(tmp_path, (run,))
    runner = Runner(_validator(exit_code))
    watcher = Watcher((artifact,))
    service = GateService(
        repository=repository,
        authorization=Authorization(),
        runner=runner,
        clock=Clock(NOW, NOW + timedelta(seconds=1)),
        watcher=watcher,
    )
    result = service.run_validator(run.run_id, ValidatorKey.STORIES, OWNER)
    assert result.gate.status is gate_status
    assert result.gate.evidence_ready is (exit_code == 0 and artifact_status is ArtifactStatus.AVAILABLE)
    assert [item[2].event_type for item in repository.commits] == [
        "ValidatorStarted",
        event_type,
    ]
    assert result.latest_validator is not None
    assert result.latest_validator.command_template.startswith("python3 validate-stories.py")
    assert result.latest_validator.gate_id == "G1"
    assert result.latest_validator.validated_revision == result.revision
    assert (result.latest_validator.evidence_digest is not None) is (
        exit_code == 0 and artifact_status is ArtifactStatus.AVAILABLE
    )
    assert runner.calls == [
        (
            ValidatorKey.STORIES,
            {
                "workspace_root": Path(run.workspace_root),
                "feature_id": "F0001",
                "run_id": RUN_ID,
                "timeout_seconds": 120.0,
            },
        )
    ]


def test_validator_requires_semantic_gate_verdict_not_only_available_files(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "required.md"
    evidence.write_text("present but verdict failed", encoding="utf-8")
    artifact = ArtifactObservation("required.md", ArtifactStatus.AVAILABLE, NOW, 26)
    run = _run(tmp_path, artifacts=(artifact,))
    repository = Repository(tmp_path, (run,))
    service = GateService(
        repository=repository,
        authorization=Authorization(),
        runner=Runner(_validator()),
        clock=Clock(NOW, NOW + timedelta(seconds=1)),
        watcher=Watcher((artifact,), semantic_ready=False),
    )

    result = service.run_validator(run.run_id, ValidatorKey.STORIES, OWNER)

    assert result.gate.status is GateStatus.BLOCKED
    assert result.gate.evidence_ready is False
    assert result.latest_validator is not None
    assert result.latest_validator.exit_code == 0
    assert result.latest_validator.evidence_digest is None


def _validated_gate(
    tmp_path: Path,
) -> tuple[GateService, AuthorizedRepository, RunRecord, Path]:
    evidence = tmp_path / "required.md"
    evidence.write_text("stable evidence", encoding="utf-8")
    artifact = ArtifactObservation(
        "required.md", ArtifactStatus.AVAILABLE, NOW, evidence.stat().st_size
    )
    run = _run(tmp_path, artifacts=(artifact,))
    repository = AuthorizedRepository(tmp_path, (run,))
    service = GateService(
        repository=repository,
        authorization=Authorization(),
        runner=Runner(_validator()),
        clock=Clock(
            NOW,
            NOW + timedelta(seconds=1),
            NOW + timedelta(seconds=2),
        ),
        watcher=Watcher((artifact,)),
    )
    validated = service.run_validator(run.run_id, ValidatorKey.STORIES, OWNER)
    assert validated.gate.evidence_ready is True
    return service, repository, validated, evidence


def test_gate_approval_rechecks_deleted_evidence_under_repository_lock(
    tmp_path: Path,
) -> None:
    service, repository, validated, evidence = _validated_gate(tmp_path)
    evidence.unlink()

    with pytest.raises(NebulaError) as caught:
        service.decide(
            GateDecisionRequest(
                RUN_ID,
                "G1",
                DecisionKind.APPROVE,
                None,
                None,
                validated.revision,
                True,
            ),
            OWNER,
        )

    assert caught.value.code is ErrorCode.GATE_BLOCKED
    assert repository.commits[-1][2].event_type == "GateDecisionBlocked"
    assert repository.records[RUN_ID].gate.status is GateStatus.PENDING


def test_gate_approval_rejects_required_evidence_replaced_by_symlink(
    tmp_path: Path,
) -> None:
    service, repository, validated, evidence = _validated_gate(tmp_path)
    evidence.unlink()
    outside = tmp_path.parent / f"{tmp_path.name}-outside-evidence.md"
    outside.write_text("replacement", encoding="utf-8")
    evidence.symlink_to(outside)

    with pytest.raises(NebulaError) as caught:
        service.decide(
            GateDecisionRequest(
                RUN_ID,
                "G1",
                DecisionKind.APPROVE,
                None,
                None,
                validated.revision,
                True,
            ),
            OWNER,
        )

    assert caught.value.code is ErrorCode.GATE_BLOCKED
    assert repository.commits[-1][2].event_type == "GateDecisionBlocked"


@pytest.mark.parametrize(
    "changes",
    [
        {"gate_id": "G0"},
        {"validated_revision": 1},
        {"evidence_digest": "0" * 64},
    ],
)
def test_gate_approval_rejects_prior_or_mismatched_validator_binding(
    tmp_path: Path, changes: dict[str, object]
) -> None:
    service, repository, validated, _ = _validated_gate(tmp_path)
    assert validated.latest_validator is not None
    mismatched = replace(validated.latest_validator, **changes)
    repository.records[RUN_ID] = replace(validated, latest_validator=mismatched)

    with pytest.raises(NebulaError) as caught:
        service.decide(
            GateDecisionRequest(
                RUN_ID,
                "G1",
                DecisionKind.APPROVE,
                None,
                None,
                validated.revision,
                True,
            ),
            OWNER,
        )

    assert caught.value.code is ErrorCode.GATE_BLOCKED
    assert repository.commits[-1][2].event_type == "GateDecisionBlocked"


def test_gate_approval_rejects_revision_that_changes_under_repository_lock(
    tmp_path: Path,
) -> None:
    service, repository, validated, _ = _validated_gate(tmp_path)
    repository.locked_record = replace(
        validated,
        revision=validated.revision + 1,
        last_event_sequence=validated.last_event_sequence + 1,
    )
    commits_before = len(repository.commits)

    with pytest.raises(NebulaError) as caught:
        service.decide(
            GateDecisionRequest(
                RUN_ID,
                "G1",
                DecisionKind.APPROVE,
                None,
                None,
                validated.revision,
                True,
            ),
            OWNER,
        )

    assert caught.value.code is ErrorCode.STALE_REVISION
    assert caught.value.details == ({"current_revision": validated.revision + 1},)
    assert len(repository.commits) == commits_before


def test_validator_rejects_non_enum_key_before_state_access(tmp_path: Path) -> None:
    repository = Repository(tmp_path)
    service = GateService(
        repository=repository,
        authorization=Authorization(),
        runner=Runner(_validator()),
        clock=Clock(),
    )
    with pytest.raises(NebulaError) as caught:
        service.run_validator(RUN_ID, "shell", OWNER)  # type: ignore[arg-type]
    assert caught.value.code is ErrorCode.VALIDATOR_UNKNOWN
    assert repository.commits == []


def _gate_service(tmp_path: Path, run: RunRecord):
    repository = Repository(tmp_path, (run,))
    authorization = Authorization()
    return (
        GateService(
            repository=repository,
            authorization=authorization,
            runner=Runner(_validator()),
            clock=Clock(NOW + timedelta(minutes=1)),
        ),
        repository,
        authorization,
    )


def test_gate_approval_requires_explicit_confirmation_before_loading_state(
    tmp_path: Path,
) -> None:
    service, repository, _ = _gate_service(tmp_path, _run(tmp_path))
    request = GateDecisionRequest(
        RUN_ID, "G1", DecisionKind.APPROVE, None, None, 2, False
    )
    with pytest.raises(NebulaError) as caught:
        service.decide(request, OWNER)
    assert caught.value.code is ErrorCode.USAGE_ERROR
    assert repository.commits == []


def test_gate_decision_rejects_stale_projection(tmp_path: Path) -> None:
    service, repository, _ = _gate_service(tmp_path, _run(tmp_path, revision=3))
    request = GateDecisionRequest(
        RUN_ID, "G1", DecisionKind.HOLD, "pause", None, 2
    )
    with pytest.raises(NebulaError) as caught:
        service.decide(request, OWNER)
    assert caught.value.code is ErrorCode.STALE_REVISION
    assert caught.value.details == ({"current_revision": 3},)
    assert repository.commits == []


@pytest.mark.parametrize(
    ("decision", "reason", "event_type", "status"),
    [
        (DecisionKind.APPROVE, None, "GateApproved", GateStatus.APPROVED),
        (DecisionKind.HOLD, "review finding", "GateHeld", GateStatus.HELD),
    ],
)
def test_gate_decision_records_display_identity_and_audit_event(
    tmp_path: Path, decision, reason, event_type, status
) -> None:
    run = _run(
        tmp_path,
        evidence_ready=True,
        validator=_validator(),
    )
    service, repository, _ = _gate_service(tmp_path, run)
    request = GateDecisionRequest(
        RUN_ID,
        "G1",
        decision,
        reason,
        "Human Reviewer",
        run.revision,
        decision is DecisionKind.APPROVE,
    )
    result = service.decide(request, OWNER)
    assert result.gate.status is status
    assert result.gate.decision.actor.display_label == "Human Reviewer"
    assert repository.commits[0][2].event_type == event_type
    assert repository.commits[0][2].payload["record_revision"] == run.revision


def test_blocked_gate_decision_is_audited_without_changing_gate(tmp_path: Path) -> None:
    run = _run(tmp_path, evidence_ready=False)
    service, repository, _ = _gate_service(tmp_path, run)
    request = GateDecisionRequest(
        RUN_ID, "G1", DecisionKind.APPROVE, None, None, run.revision, True
    )
    with pytest.raises(NebulaError) as caught:
        service.decide(request, OWNER)
    assert caught.value.code is ErrorCode.GATE_BLOCKED
    assert repository.commits[0][1].gate is run.gate
    assert repository.commits[0][2].event_type == "GateDecisionBlocked"


def test_resume_held_gate_uses_revision_guard_and_clears_decision(
    tmp_path: Path,
) -> None:
    base = _run(tmp_path, evidence_ready=True, validator=_validator())
    held_service, held_repository, _ = _gate_service(tmp_path, base)
    held = held_service.decide(
        GateDecisionRequest(
            RUN_ID, "G1", DecisionKind.HOLD, "pause", None, base.revision
        ),
        OWNER,
    )
    service, repository, authorization = _gate_service(tmp_path, held)
    with pytest.raises(NebulaError) as caught:
        service.resume(RUN_ID, OWNER, held.revision - 1)
    assert caught.value.code is ErrorCode.STALE_REVISION
    resumed = service.resume(RUN_ID, OWNER, held.revision)
    assert resumed.gate.status is GateStatus.PENDING
    assert resumed.gate.decision is None
    assert repository.commits[-1][2].event_type == "GateResumed"
    assert authorization.required[-1][3].decision is DecisionKind.HOLD
    assert held_repository.commits[0][2].event_type == "GateHeld"


def _transcript_service(tmp_path: Path, run: RunRecord, pipe: Pipe | None = None):
    repository = Repository(tmp_path, (run,))
    pipe = pipe or Pipe()
    service = TranscriptService(
        repository=repository,
        authorization=Authorization(),
        pipe=pipe,
        clock=Clock(NOW + timedelta(minutes=1)),
    )
    return service, repository, pipe


def test_transcript_enable_uses_revision_guard(tmp_path: Path) -> None:
    run = _run(tmp_path)
    service, repository, pipe = _transcript_service(tmp_path, run)
    with pytest.raises(NebulaError) as caught:
        service.enable(RUN_ID, OWNER, run.revision - 1)
    assert caught.value.code is ErrorCode.STALE_REVISION
    assert pipe.configured == []
    assert repository.commits == []


def test_transcript_enable_commits_active_owner_only_target(tmp_path: Path) -> None:
    run = _run(tmp_path)
    service, repository, pipe = _transcript_service(tmp_path, run)
    result = service.enable(RUN_ID, OWNER, run.revision)
    assert result.transcript.status is TranscriptStatus.ACTIVE
    assert result.transcript.path == str(
        tmp_path / "runs" / RUN_ID / "transcript.redacted.log"
    )
    assert pipe.configured[0][0] is run
    assert repository.commits[0][2].event_type == "TranscriptEnabled"


def test_transcript_enable_failure_is_persisted_then_propagated(tmp_path: Path) -> None:
    run = _run(tmp_path)
    pipe = Pipe(error(ErrorCode.COMMAND_FAILED, "pipe", "command-failed", "retry"))
    service, repository, _ = _transcript_service(tmp_path, run, pipe)
    with pytest.raises(NebulaError) as caught:
        service.enable(RUN_ID, OWNER, run.revision)
    assert caught.value.code is ErrorCode.COMMAND_FAILED
    assert repository.commits[0][1].transcript.status is TranscriptStatus.FAILED
    assert repository.commits[0][2].event_type == "TranscriptFailed"
    assert repository.commits[0][2].payload["error_category"] == "command-failed"


def test_transcript_preserves_pipe_failure_when_failure_audit_cannot_commit(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path)
    pipe = Pipe(ValueError("capture failed"))
    service, repository, _ = _transcript_service(tmp_path, run, pipe)
    repository.fail_event_type = "TranscriptFailed"
    with pytest.raises(ValueError, match="capture failed"):
        service.enable(RUN_ID, OWNER, run.revision)
    assert repository.commits[0][2].event_type == "TranscriptFailed"


def test_transcript_complete_guards_revision_and_is_idempotent_when_inactive(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path)
    service, repository, pipe = _transcript_service(tmp_path, run)
    with pytest.raises(NebulaError) as caught:
        service.complete(RUN_ID, OWNER, run.revision - 1)
    assert caught.value.code is ErrorCode.STALE_REVISION
    assert service.complete(RUN_ID, OWNER, run.revision) is run
    assert pipe.disabled == []
    assert repository.commits == []


@pytest.mark.parametrize(
    ("findings", "redaction"),
    [(0, RedactionStatus.PASSED), (2, RedactionStatus.REDACTED)],
)
def test_transcript_complete_finalizes_redaction_status(
    tmp_path: Path, findings: int, redaction: RedactionStatus
) -> None:
    path = tmp_path / "runs" / RUN_ID / "transcript.redacted.log"
    run = _run(
        tmp_path,
        transcript=TranscriptState(
            TranscriptStatus.ACTIVE,
            RedactionStatus.NOT_RUN,
            str(path),
            None,
            findings,
        ),
    )
    service, repository, pipe = _transcript_service(tmp_path, run)
    result = service.complete(RUN_ID, OWNER, run.revision)
    assert result.transcript.status is TranscriptStatus.COMPLETED
    assert result.transcript.redaction_status is redaction
    assert pipe.disabled == [run]
    assert repository.commits[0][2].event_type == "TranscriptCompleted"


def test_transcript_complete_waits_for_delayed_terminal_filter_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "runs" / RUN_ID / "transcript.redacted.log"
    active = TranscriptState(
        TranscriptStatus.ACTIVE,
        RedactionStatus.NOT_RUN,
        str(path),
        None,
        1,
    )
    completed = TranscriptState(
        TranscriptStatus.COMPLETED,
        RedactionStatus.REDACTED,
        str(path),
        None,
        3,
    )
    run = _run(tmp_path, transcript=active)
    pipe = CapturePipe(None, None, completed)
    service, repository, _ = _transcript_service(tmp_path, run, pipe)
    monkeypatch.setattr("nebula_agents.application.transcripts.time.sleep", lambda _: None)

    result = service.complete(RUN_ID, OWNER, run.revision)

    assert pipe.disabled == [run]
    assert len(pipe.status_calls) == 3
    assert result.transcript.status is TranscriptStatus.COMPLETED
    assert result.transcript.redaction_status is RedactionStatus.REDACTED
    assert result.transcript.redaction_findings == 3
    assert repository.commits[-1][2].event_type == "TranscriptCompleted"


def test_transcript_commit_and_compensation_failure_reconciles_completed_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "runs" / RUN_ID / "transcript.redacted.log"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"safe")
    path.chmod(0o600)
    active = TranscriptState(
        TranscriptStatus.ACTIVE,
        RedactionStatus.NOT_RUN,
        str(path),
        None,
        0,
    )
    completed = TranscriptState(
        TranscriptStatus.COMPLETED,
        RedactionStatus.PASSED,
        str(path),
        None,
        0,
    )
    run = _run(tmp_path, transcript=active)
    pipe = CapturePipe(None, completed)
    service, repository, _ = _transcript_service(tmp_path, run, pipe)
    repository.fail_event_type = "TranscriptCompleted"
    pipe.failure = RuntimeError("capture compensation unavailable")
    monkeypatch.setattr(
        "nebula_agents.application.transcripts.time.sleep", lambda _: None
    )

    with pytest.raises(RuntimeError, match="failed TranscriptCompleted"):
        service.complete(RUN_ID, OWNER, run.revision)

    assert pipe.disabled == [run]
    assert pipe.configured == [(run, path)]
    assert repository.records[RUN_ID] is run

    repository.fail_event_type = None
    restarted = RunService(
        workspace_root=tmp_path,
        preflight=Preflight(tmp_path / "prompt"),
        authorization=Authorization(),
        repository=repository,
        providers={},
        tmux=Tmux(True),
        schema=Schema(),
        clock=Clock(NOW + timedelta(minutes=2)),
        transcript_pipe=CapturePipe(completed),
    )

    projection = restarted.reconcile(RUN_ID, OWNER)

    assert projection.transcript == completed
    assert repository.records[RUN_ID].transcript == completed
    assert repository.commits[-1][2].event_type == "TranscriptCompleted"


def test_transcript_complete_persists_post_disable_filter_failure(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runs" / RUN_ID / "transcript.redacted.log"
    active = TranscriptState(
        TranscriptStatus.ACTIVE,
        RedactionStatus.NOT_RUN,
        str(path),
        None,
        2,
    )
    failed = TranscriptState(
        TranscriptStatus.FAILED,
        RedactionStatus.FAILED,
        str(path),
        None,
        4,
    )
    run = _run(tmp_path, transcript=active)
    pipe = CapturePipe(None, failed)
    service, repository, _ = _transcript_service(tmp_path, run, pipe)

    result = service.complete(RUN_ID, OWNER, run.revision)

    assert pipe.disabled == [run]
    assert result.transcript.status is TranscriptStatus.FAILED
    assert result.transcript.redaction_status is RedactionStatus.FAILED
    assert result.transcript.redaction_findings == 4
    assert repository.records[RUN_ID].transcript == result.transcript
    assert repository.commits[-1][2].event_type == "TranscriptFailed"
    assert repository.commits[-1][2].payload["error_category"] == (
        "filter-process-failed"
    )


@pytest.mark.parametrize(
    "state",
    [
        TranscriptState(TranscriptStatus.ACTIVE, RedactionStatus.PASSED, None, None, 0),
        TranscriptState(TranscriptStatus.COMPLETED, RedactionStatus.NOT_RUN, None, None, 0),
        TranscriptState(TranscriptStatus.COMPLETED, RedactionStatus.PASSED, None, None, 0),
    ],
)
def test_transcript_preview_requires_safely_completed_capture(
    tmp_path: Path, state: TranscriptState
) -> None:
    run = _run(tmp_path, transcript=state)
    service, _, _ = _transcript_service(tmp_path, run)
    with pytest.raises(NebulaError) as caught:
        service.preview(RUN_ID, OWNER)
    assert caught.value.code is ErrorCode.TRANSCRIPT_UNAVAILABLE


def test_transcript_preview_denies_path_outside_run_directory(tmp_path: Path) -> None:
    outside = tmp_path / "outside.log"
    outside.write_text("safe", encoding="utf-8")
    outside.chmod(0o600)
    run = _run(
        tmp_path,
        transcript=TranscriptState(
            TranscriptStatus.COMPLETED,
            RedactionStatus.PASSED,
            str(outside),
            None,
            0,
        ),
    )
    service, _, _ = _transcript_service(tmp_path, run)
    with pytest.raises(NebulaError) as caught:
        service.preview(RUN_ID, OWNER)
    assert caught.value.code is ErrorCode.PATH_DENIED


def test_transcript_preview_denies_unsafe_permissions(tmp_path: Path) -> None:
    path = tmp_path / "runs" / RUN_ID / "transcript.redacted.log"
    path.parent.mkdir(parents=True)
    path.write_text("safe", encoding="utf-8")
    path.chmod(0o644)
    run = _run(
        tmp_path,
        transcript=TranscriptState(
            TranscriptStatus.COMPLETED,
            RedactionStatus.PASSED,
            str(path),
            None,
            0,
        ),
    )
    service, _, _ = _transcript_service(tmp_path, run)
    with pytest.raises(NebulaError) as caught:
        service.preview(RUN_ID, OWNER)
    assert caught.value.code is ErrorCode.PATH_DENIED


def test_transcript_preview_rejects_same_directory_symlink(tmp_path: Path) -> None:
    run_root = tmp_path / "runs" / RUN_ID
    run_root.mkdir(parents=True)
    target = run_root / "target.log"
    target.write_text("safe", encoding="utf-8")
    target.chmod(0o600)
    link = run_root / "transcript.redacted.log"
    link.symlink_to(target)
    run = _run(
        tmp_path,
        transcript=TranscriptState(
            TranscriptStatus.COMPLETED,
            RedactionStatus.PASSED,
            str(link),
            None,
            0,
        ),
    )
    service, _, _ = _transcript_service(tmp_path, run)
    with pytest.raises(NebulaError) as caught:
        service.preview(RUN_ID, OWNER)
    assert caught.value.code is ErrorCode.PATH_DENIED


def test_transcript_preview_maps_missing_file_to_stable_domain_error(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "runs" / RUN_ID / "transcript.redacted.log"
    run = _run(
        tmp_path,
        transcript=TranscriptState(
            TranscriptStatus.COMPLETED,
            RedactionStatus.PASSED,
            str(missing),
            None,
            0,
        ),
    )
    service, _, _ = _transcript_service(tmp_path, run)
    with pytest.raises(NebulaError) as caught:
        service.preview(RUN_ID, OWNER)
    assert caught.value.code in {ErrorCode.PATH_DENIED, ErrorCode.TRANSCRIPT_UNAVAILABLE}


def test_transcript_preview_is_sanitized_and_bounded(tmp_path: Path) -> None:
    path = tmp_path / "runs" / RUN_ID / "transcript.redacted.log"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\x1b[31msafe\x00\n" + b"x" * 300_000)
    path.chmod(0o600)
    run = _run(
        tmp_path,
        transcript=TranscriptState(
            TranscriptStatus.COMPLETED,
            RedactionStatus.REDACTED,
            str(path),
            None,
            3,
        ),
    )
    service, _, _ = _transcript_service(tmp_path, run)
    result = service.preview(RUN_ID, OWNER)
    assert result.preview.startswith("safe\n")
    assert "\x1b" not in result.preview
    assert len(result.preview) == 16_000
    assert result.truncated is True
    assert result.path == str(path.resolve())


def test_queries_filter_unauthorized_runs_and_use_identity_by_default(
    tmp_path: Path,
) -> None:
    owned = _run(tmp_path, owner=OWNER)
    foreign = replace(
        _run(tmp_path, owner=REVIEWER),
        run_id="2026-07-13-cafebabe",
        tmux_session="nebula-F0001-cafebabe",
    )
    repository = Repository(tmp_path, (owned, foreign))
    identity = Identity(OWNER)
    authorization = Authorization()
    service = QueryService(
        repository=repository, authorization=authorization, identity=identity
    )
    projections = service.sessions()
    assert tuple(item.run_id for item in projections) == (owned.run_id,)
    assert projections[0].workspace_root == owned.workspace_root
    assert identity.calls == 1
    assert sum(
        1 for _actor, action, _resource in authorization.authorized
        if action is Action.READ_STATE
    ) == 2


def test_query_session_limit_is_clamped_to_one_and_one_hundred(tmp_path: Path) -> None:
    records = tuple(
        replace(
            _run(tmp_path),
            run_id=f"2026-07-13-{number:08x}",
            tmux_session=f"nebula-F0001-{number:08x}",
        )
        for number in range(105)
    )
    repository = Repository(tmp_path, records)
    service = QueryService(
        repository=repository,
        authorization=Authorization(),
        identity=Identity(OWNER),
    )
    assert len(service.sessions(limit=0)) == 1
    assert len(service.sessions(limit=1000)) == 100


def test_query_passes_status_filter_and_explicit_actor_without_identity(
    tmp_path: Path,
) -> None:
    active = _run(tmp_path)
    exited = replace(
        active,
        run_id="2026-07-13-cafebabe",
        status=RunStatus.EXITED,
        tmux_session="nebula-F0001-cafebabe",
    )
    repository = Repository(tmp_path, (active, exited))
    identity = Identity(REVIEWER)
    service = QueryService(
        repository=repository,
        authorization=Authorization(),
        identity=identity,
    )
    projections = service.sessions(RunStatus.EXITED, actor=OWNER)
    assert tuple(item.run_id for item in projections) == (exited.run_id,)
    assert projections[0].status is RunStatus.EXITED
    assert identity.calls == 0


def test_status_and_evidence_are_read_only_projections(tmp_path: Path) -> None:
    artifact = ArtifactObservation("required.md", ArtifactStatus.AVAILABLE, NOW, 4)
    run = _run(tmp_path, artifacts=(artifact,))
    repository = Repository(tmp_path, (run,))
    identity = Identity(OWNER)
    authorization = Authorization()
    service = QueryService(
        repository=repository, authorization=authorization, identity=identity
    )
    projection = service.status(RUN_ID)
    assert projection.run_id == run.run_id
    assert projection.revision == run.revision
    assert projection.workspace_root == run.workspace_root
    assert service.evidence(RUN_ID, OWNER) == (artifact,)
    assert repository.commits == []
    assert [item[1] for item in authorization.required] == [
        Action.READ_STATE,
        Action.READ_STATE,
    ]


def test_reviewer_query_projection_hides_paths_and_exposes_only_capabilities(
    tmp_path: Path,
) -> None:
    secret_summary = (
        "validator failed at "
        + str(tmp_path / "private-feature" / "story.md")
        + " with Bearer test-only-token-0123456789abcdef"
    )
    validator = replace(
        _validator(),
        artifact_path=str(tmp_path / "private-validator.log"),
        summary=secret_summary,
    )
    transcript = TranscriptState(
        TranscriptStatus.COMPLETED,
        RedactionStatus.REDACTED,
        str(tmp_path / "private-transcript.log"),
        "private preview",
        2,
    )
    run = _run(
        tmp_path,
        status=RunStatus.DETACHED_OR_EXITED,
        validator=validator,
        transcript=transcript,
    )
    policy = {
        "default_effect": "deny",
        "bindings": [
            {
                "subject_type": "uid",
                "subject_id": REVIEWER.uid,
                "role": Role.REVIEWER.value,
            }
        ],
        "reviewer_grants": {},
        "validator_allowlist": ["stories", "trackers", "templates"],
    }
    service = QueryService(
        repository=Repository(tmp_path, (run,)),
        authorization=AuthorizationService(SimpleNamespace(load=lambda: policy)),
        identity=Identity(REVIEWER),
    )

    projection = service.status(run.run_id, REVIEWER)

    assert projection.workspace_root is None
    assert projection.prompt_contract is None
    assert projection.evidence_root is None
    assert projection.audit_log_path is None
    assert projection.tmux_session is None
    assert projection.latest_validator is not None
    assert projection.latest_validator.artifact_path is None
    assert projection.latest_validator.summary == (
        "Validator output is hidden in this non-owner view."
    )
    assert secret_summary not in projection.latest_validator.summary
    assert str(tmp_path) not in projection.latest_validator.summary
    assert "Bearer" not in projection.latest_validator.summary
    assert projection.latest_validator.command_template == validator.command_template
    assert projection.transcript.path is None
    assert projection.transcript.preview is None
    assert projection.can_attach is False
    assert projection.can_recover is False
    assert projection.recovery_available is True
    assert projection.can_decide_gate is False
    assert projection.can_configure_transcript is False


def test_authorization_system_role_is_restricted_to_owned_internal_reads() -> None:
    policy = {
        "default_effect": "deny",
        "bindings": [],
        "reviewer_grants": {},
    }
    service = AuthorizationService(SimpleNamespace(load=lambda: policy))
    system = Actor(0, "system", Role.SYSTEM)
    owned = SimpleNamespace(workspace_root="/workspace", owner_uid=0, run_id=RUN_ID)
    foreign = SimpleNamespace(workspace_root="/workspace", owner_uid=1, run_id=RUN_ID)
    assert service.authorize(system, Action.PROBE, owned).allowed
    assert service.authorize(system, Action.READ_STATE, owned).allowed
    assert not service.authorize(system, Action.LAUNCH, owned).allowed
    assert not service.authorize(system, Action.READ_STATE, foreign).allowed


def test_authorization_rejects_malformed_bindings_and_reviewer_grants() -> None:
    reviewer = Actor(1000, "reviewer", Role.REVIEWER)
    resource = SimpleNamespace(workspace_root="/workspace", owner_uid=1000, run_id=RUN_ID)
    malformed_bindings = AuthorizationService(
        SimpleNamespace(
            load=lambda: {
                "default_effect": "deny",
                "bindings": "not-a-list",
                "reviewer_grants": {},
            }
        )
    )
    assert not malformed_bindings.authorize(reviewer, Action.READ_STATE, resource).allowed
    malformed_grants = AuthorizationService(
        SimpleNamespace(
            load=lambda: {
                "default_effect": "deny",
                "bindings": [
                    {
                        "subject_type": "uid",
                        "subject_id": 1000,
                        "role": Role.REVIEWER.value,
                    }
                ],
                "reviewer_grants": "allow-all",
            }
        )
    )
    assert not malformed_grants.authorize(reviewer, Action.LAUNCH, resource).allowed


def test_authorization_unknown_bound_role_fails_closed_and_require_can_succeed() -> None:
    owner_policy = {
        "default_effect": "deny",
        "bindings": [
            {
                "subject_type": "uid",
                "subject_id": OWNER.uid,
                "role": Role.LOCAL_OPERATOR.value,
            }
        ],
    }
    owner_service = AuthorizationService(SimpleNamespace(load=lambda: owner_policy))
    resource = SimpleNamespace(
        workspace_root="/workspace", owner_uid=OWNER.uid, run_id=RUN_ID
    )
    owner_service.require(OWNER, Action.READ_STATE, resource)

    alien_role = SimpleNamespace(value="Alien")
    alien = Actor(77, "alien", alien_role)  # type: ignore[arg-type]
    alien_policy = {
        "default_effect": "deny",
        "bindings": [
            {"subject_type": "uid", "subject_id": 77, "role": "Alien"}
        ],
    }
    decision = AuthorizationService(
        SimpleNamespace(load=lambda: alien_policy)
    ).authorize(alien, Action.READ_STATE, resource)
    assert decision == AuthorizationDecision(False, "role_unknown")


class PreflightTmux:
    def probe(self) -> Probe:
        return Probe("tmux", "ready", "/usr/bin/tmux", "3.4")


class PreflightProvider:
    key = ProviderKey.CODEX

    def probe(self, workspace_root: Path) -> Probe:
        return Probe("codex", "ready", "/usr/bin/codex", "1.0")


def test_preflight_containment_rejects_sibling_path(tmp_path: Path) -> None:
    assert contained(tmp_path, tmp_path / "child") is True
    assert contained(tmp_path / "workspace", tmp_path / "sibling") is False


def test_preflight_does_not_attempt_runtime_creation_during_read_only_doctor(
    workspace: Path,
    fixed_now: datetime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = workspace / "cannot-create"
    original_mkdir = Path.mkdir

    def fail_runtime_mkdir(path: Path, *args, **kwargs):
        if path == runtime:
            raise OSError("read only")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_runtime_mkdir)
    schema = Schema()
    service = PreflightService(
        clock=Clock(fixed_now),
        tmux=PreflightTmux(),
        providers={ProviderKey.CODEX: PreflightProvider()},
        schema=schema,
    )
    result = service.run(
        workspace,
        runtime_dir_override=runtime,
        provider_hint=ProviderKey.CODEX,
    )
    assert result.overall_status == "ready"
    check = next(item for item in result.checks if item.key == "runtime_directory")
    assert check.status == "ready"
    assert "first authorized mutation" in check.message
    assert not runtime.exists()


def test_preflight_missing_requested_adapter_and_prompt_are_blocking(
    workspace: Path, fixed_now: datetime
) -> None:
    prompt = workspace / "agents/templates/prompts/evidence-contract/review-operator-friendly.md"
    prompt.unlink()
    service = PreflightService(
        clock=Clock(fixed_now),
        tmux=PreflightTmux(),
        providers={ProviderKey.CODEX: PreflightProvider()},
        schema=Schema(),
    )
    result = service.run(
        workspace,
        provider_hint=ProviderKey.CLAUDE,
        prompt_action=PromptAction.REVIEW,
    )
    assert result.overall_status == "blocked"
    assert result.providers == (
        Probe("claude", "missing", remediation_category="install_provider"),
    )
    assert next(item for item in result.checks if item.key == "prompt_contract").status == "missing"


def test_preflight_require_ready_returns_ready_projection(
    workspace: Path, fixed_now: datetime
) -> None:
    service = PreflightService(
        clock=Clock(fixed_now),
        tmux=PreflightTmux(),
        providers={ProviderKey.CODEX: PreflightProvider()},
        schema=Schema(),
    )
    result = service.require_ready(
        workspace, None, ProviderKey.CODEX, PromptAction.FEATURE
    )
    assert result.overall_status == "ready"

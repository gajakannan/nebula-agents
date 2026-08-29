from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from nebula_agents.application.authorization import AuthorizationService
from nebula_agents.application.commands import CommandService
from nebula_agents.application.evidence import EvidenceService
from nebula_agents.application.gates import GateService
from nebula_agents.application.preflight import PreflightService
from nebula_agents.application.queries import QueryService
from nebula_agents.application.runs import RunService
from nebula_agents.application.transcripts import TranscriptService
from nebula_agents.domain.enums import ProviderKey
from nebula_agents.domain.errors import ErrorCode, error
from nebula_agents.domain.models import Actor, JsonValue
from nebula_agents.infrastructure.config import resolve_config
from nebula_agents.infrastructure.artifact_index import FilesystemArtifactIndex
from nebula_agents.infrastructure.filesystem_store import FilesystemRunRepository
from nebula_agents.infrastructure.identity import OsIdentity
from nebula_agents.infrastructure.policy_store import LocalPolicyStore
from nebula_agents.infrastructure.process import SubprocessRunner
from nebula_agents.infrastructure.providers import ClaudeAdapter, CodexAdapter
from nebula_agents.infrastructure.schema_registry import JsonSchemaRegistry
from nebula_agents.infrastructure.tmux import TmuxAdapter
from nebula_agents.infrastructure.transcript import TmuxTranscriptAdapter
from nebula_agents.infrastructure.watcher import AllowlistedValidatorRunner, PollingEvidenceWatcher


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class DeferredLocalPolicy:
    """Expose the safe default policy without writing until the first mutation."""

    def __init__(self, store: LocalPolicyStore) -> None:
        self._store = store

    def initialize(self, owner_uid: int) -> None:
        self._store.initialize(owner_uid)

    def load(self) -> Mapping[str, JsonValue]:
        if self._store.path.is_symlink() or self._store.path.exists():
            return self._store.load()
        runtime = self._store.path.parent
        if runtime.exists():
            try:
                details = runtime.lstat()
            except OSError as exc:
                raise error(ErrorCode.RUNTIME_DIR_DENIED, "Runtime directory cannot be inspected", "preflight", "Restore an owner-only runtime directory.") from exc
            if runtime.is_symlink() or not stat.S_ISDIR(details.st_mode) or details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) != 0o700:
                raise error(ErrorCode.RUNTIME_DIR_DENIED, "Runtime directory ownership or permissions are unsafe", "preflight", "Restore owner-only mode 0700.")
        return {
            "schema_version": "1.0",
            "policy_version": 1,
            "default_effect": "deny",
            "bindings": [{"subject_type": "uid", "subject_id": os.getuid(), "role": "LocalOperator"}],
            "reviewer_grants": {
                "reviewer_can_launch": False,
                "reviewer_can_attach": False,
                "reviewer_can_hold": False,
                "reviewer_can_approve": False,
                "reviewer_can_configure_transcript": False,
            },
            "validator_allowlist": ["stories", "trackers", "templates"],
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }


@dataclass(frozen=True, slots=True)
class Application:
    """Composition root, split into a read side and a write side (F0003-S0007).

    `queries` and `preflight` never write; `commands` holds every mutating service.
    The MCP adapter added in S0003 is constructed with `queries` alone, which is what
    makes its read-only guarantee structural — passing `commands` to it would be a
    visible architectural edit rather than a forgotten check (ADR-007).

    `preflight` sits on the read side because `PreflightService.run` only inspects: it
    stats the workspace, runtime root, and providers and reports. The runtime directory
    is created by the first authorized mutation, not by probing it.

    `runs`, `gates`, and `transcripts` remain reachable as properties. They are the same
    objects `commands` holds — delegation, not a second path — so a caller written
    against the F0001 shape keeps working and the existing engine suite passes without
    a single test being rewritten to accommodate the split.
    """

    queries: QueryService
    commands: CommandService
    preflight: PreflightService
    identity: OsIdentity

    def current_actor(self) -> Actor:
        return self.identity.current_actor()

    @property
    def runs(self) -> RunService:
        return self.commands.runs

    @property
    def gates(self) -> GateService:
        return self.commands.gates

    @property
    def transcripts(self) -> TranscriptService:
        return self.commands.transcripts

    @property
    def evidence(self) -> EvidenceService:
        return self.commands.evidence


def build_application(workspace_root: Path, runtime_override: Path | None = None) -> Application:
    config = resolve_config(workspace_root, runtime_override)
    schema = JsonSchemaRegistry(config.schema_root)
    policy = DeferredLocalPolicy(LocalPolicyStore(config.runtime_root, schema))
    identity = OsIdentity(policy)
    authorization = AuthorizationService(policy)
    clock = SystemClock()
    process = SubprocessRunner()
    tmux = TmuxAdapter(process)
    providers = {
        ProviderKey.CODEX: CodexAdapter(process),
        ProviderKey.CLAUDE: ClaudeAdapter(process),
    }
    repository = FilesystemRunRepository(config.runtime_root, schema, config.lock_timeout_seconds)
    watcher = PollingEvidenceWatcher(clock)
    validator = AllowlistedValidatorRunner(process, clock)
    transcript_pipe = TmuxTranscriptAdapter(tmux)
    preflight = PreflightService(clock=clock, tmux=tmux, providers=providers, schema=schema)
    runs = RunService(
        workspace_root=config.workspace_root,
        preflight=preflight,
        authorization=authorization,
        repository=repository,
        providers=providers,
        tmux=tmux,
        schema=schema,
        clock=clock,
        watcher=watcher,
        transcript_pipe=transcript_pipe,
    )
    gates = GateService(repository=repository, authorization=authorization, runner=validator, clock=clock, watcher=watcher)
    transcripts = TranscriptService(repository=repository, authorization=authorization, pipe=transcript_pipe, clock=clock)
    artifact_index = FilesystemArtifactIndex(config.runs_root, schema, config.lock_timeout_seconds)
    evidence = EvidenceService(
        repository=repository,
        index=artifact_index,
        authorization=authorization,
        clock=clock,
        roots=config.approved_roots,
    )
    queries = QueryService(
        repository=repository, authorization=authorization, identity=identity,
        tmux=tmux, index=artifact_index,
    )
    commands = CommandService(runs=runs, gates=gates, transcripts=transcripts, evidence=evidence)
    return Application(queries=queries, commands=commands, preflight=preflight, identity=identity)

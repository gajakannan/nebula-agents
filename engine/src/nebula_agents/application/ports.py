from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Mapping, Protocol, Sequence

from nebula_agents.domain.enums import ProviderKey, RedactionStatus, RunStatus, ValidatorKey
from nebula_agents.domain.models import (
    Actor,
    ArtifactObservation,
    EvidenceReconciliation,
    JsonValue,
    Probe,
    ProcessResult,
    RecoverableRun,
    RunRecord,
    RuntimeEvent,
    TranscriptState,
    ValidatorResult,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdentityPort(Protocol):
    def current_actor(self) -> Actor: ...


class SchemaPort(Protocol):
    def validate(self, schema_name: str, document: Mapping[str, JsonValue]) -> None: ...


class ProcessPort(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        timeout_seconds: float,
        capture_limit: int,
        env_names: Sequence[str] = (),
        pass_fds: Sequence[int] = (),
    ) -> ProcessResult: ...


class ProviderAdapter(Protocol):
    @property
    def key(self) -> ProviderKey: ...

    def probe(self, workspace_root: Path) -> Probe: ...

    def build_interactive_argv(self, workspace_root: Path, prompt_text: str) -> tuple[str, ...]: ...

    def classify_early_exit(self, exit_code: int, redacted_output: str) -> str: ...


class TmuxPort(Protocol):
    def probe(self) -> Probe: ...

    def has_session(self, session_name: str) -> bool: ...

    def create_session(self, session_name: str, descriptor_path: Path) -> None: ...

    def kill_session(self, session_name: str) -> None: ...

    def attach(self, session_name: str) -> int: ...

    def configure_pipe(self, session_name: str, filter_argv: Sequence[str] | None) -> None: ...

    def pipe_active(self, session_name: str) -> bool: ...


class RunRepository(Protocol):
    @property
    def runtime_root(self) -> Path: ...

    def run_directory(self, run_id: str) -> Path: ...

    def list(self, status: RunStatus | None = None) -> tuple[RunRecord, ...]: ...

    def list_recoverable(self) -> tuple[RecoverableRun, ...]: ...

    def load(self, run_id: str) -> RunRecord: ...

    def create(self, record: RunRecord, event: RuntimeEvent) -> RunRecord: ...

    def commit(self, *, expected_revision: int, next_record: RunRecord, event: RuntimeEvent) -> RunRecord: ...

    def recover(self, run_id: str) -> RunRecord: ...


class PolicyPort(Protocol):
    def load(self) -> Mapping[str, JsonValue]: ...


class EvidenceWatcher(Protocol):
    def observe_once(self, run: RunRecord, paths: Sequence[str]) -> tuple[ArtifactObservation, ...]: ...

    def reconcile(self, run: RunRecord) -> EvidenceReconciliation: ...


class ValidatorRunner(Protocol):
    def run(
        self,
        key: ValidatorKey,
        *,
        workspace_root: Path,
        feature_id: str,
        run_id: str,
        timeout_seconds: float,
    ) -> ValidatorResult: ...


class TranscriptPipePort(Protocol):
    def configure(self, *, run: RunRecord, output_path: Path) -> None: ...

    def disable(self, *, run: RunRecord) -> None: ...

    def is_active(self, *, run: RunRecord) -> bool: ...

    def terminate_session(self, *, run: RunRecord) -> None: ...

    def session_present(self, *, run: RunRecord) -> bool: ...

    def filter_stream(self, source: BinaryIO, output_path: Path) -> tuple[RedactionStatus, int]: ...

    def capture_status(self, *, run: RunRecord) -> TranscriptState | None: ...

from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from nebula_agents.domain.enums import Action, Role, RunStatus
from nebula_agents.domain.errors import ErrorCode, error
from nebula_agents.domain.models import (
    Actor,
    ArtifactObservation,
    AuthorizationResource,
    RecoverableRun,
    RecoveryProjection,
    RunProjection,
    RunRecord,
)

from .authorization import AuthorizationService, safe_run_projection
from .ports import IdentityPort, RunRepository, TmuxPort
from .runs import require_authorized


class QueryService:
    def __init__(self, *, repository: RunRepository, authorization: AuthorizationService, identity: IdentityPort, tmux: TmuxPort | None = None) -> None:
        self._repository = repository
        self._authorization = authorization
        self._identity = identity
        self._tmux = tmux

    def _actor(self, actor: Actor | None) -> Actor:
        return actor or self._identity.current_actor()

    @staticmethod
    def _resource(run: RunRecord) -> AuthorizationResource:
        return AuthorizationResource(run.workspace_root, run.owner.uid, run.run_id)

    def _fresh(self, run: RunRecord) -> RunRecord:
        if self._tmux is None or run.status in (RunStatus.FAILED, RunStatus.EXITED):
            return run
        try:
            present = self._tmux.has_session(run.tmux_session)
        except Exception:
            return replace(run, status=RunStatus.UNKNOWN)
        if present:
            return run if run.status is RunStatus.ACTIVE else replace(run, status=RunStatus.ACTIVE)
        if run.status is RunStatus.ACTIVE:
            return replace(run, status=RunStatus.DETACHED_OR_EXITED)
        return run

    def sessions(self, status: RunStatus | None = None, actor: Actor | None = None, limit: int = 100) -> tuple[RunProjection, ...]:
        subject = self._actor(actor)
        records: list[RunProjection] = []
        for run in self._repository.list(None):
            if self._authorization.authorize(subject, Action.READ_STATE, self._resource(run)).allowed:
                projected = self._fresh(run)
                if status is None or projected.status is status:
                    records.append(safe_run_projection(projected, subject, self._authorization))
            else:
                recorder = getattr(self._repository, "record_authorization_denied", None)
                if callable(recorder):
                    try:
                        recorder(run.run_id, subject, Action.READ_STATE, datetime.now().astimezone())
                    except Exception:
                        pass
            if len(records) >= max(1, min(limit, 100)):
                break
        return tuple(records)

    def status(self, run_id: str, actor: Actor | None = None) -> RunProjection:
        run = self._repository.load(run_id)
        subject = self._actor(actor)
        require_authorized(self._repository, self._authorization, run, subject, Action.READ_STATE)
        return safe_run_projection(self._fresh(run), subject, self._authorization)

    def evidence(self, run_id: str, actor: Actor | None = None) -> tuple[ArtifactObservation, ...]:
        return self.status(run_id, actor).artifacts

    def recovery_candidates(self, actor: Actor | None = None) -> tuple[RecoveryProjection, ...]:
        subject = self._actor(actor)
        candidates: list[RecoveryProjection] = []
        for recoverable in self._repository.list_recoverable():
            run = recoverable.record
            resource = self._resource(run)
            if not self._authorization.authorize(subject, Action.READ_STATE, resource).allowed:
                continue
            candidates.append(self._recovery_projection(recoverable, subject))
        return tuple(candidates)

    def recovery_status(self, run_id: str, actor: Actor | None = None) -> RecoveryProjection:
        for candidate in self.recovery_candidates(actor):
            if candidate.run_id == run_id:
                return candidate
        raise error(
            ErrorCode.RUN_NOT_FOUND,
            "A recoverable corrupt run was not found",
            "not-found",
            "List recovery candidates and select an available run.",
            run_id=run_id,
        )

    def _recovery_projection(self, recoverable: RecoverableRun, subject: Actor) -> RecoveryProjection:
        run = recoverable.record
        resource = self._resource(run)
        can_recover = (
            subject.role is Role.LOCAL_OPERATOR
            and subject.uid == run.owner.uid
            and subject.uid == os.getuid()
            and self._authorization.authorize(subject, Action.ATTACH, resource).allowed
        )
        transcript_path = self._safe_transcript_path(run) if can_recover else None
        return RecoveryProjection(
            run_id=run.run_id,
            recoverable_revision=run.revision,
            recovery_available=True,
            can_recover=can_recover,
            last_gate=run.gate,
            last_audit_event=recoverable.last_audit_event,
            transcript_path=transcript_path,
            recovery_command=(
                f"nebula-agents recover --run-id {run.run_id} --expected-revision {run.revision}"
                if can_recover
                else None
            ),
        )

    def _safe_transcript_path(self, run: RunRecord) -> str | None:
        if run.transcript.path is None:
            return None
        requested = Path(run.transcript.path).expanduser()
        expected = self._repository.run_directory(run.run_id) / "transcript.redacted.log"
        try:
            if (
                not requested.is_absolute()
                or requested.name != expected.name
                or requested.is_symlink()
                or requested.parent.resolve(strict=True) != expected.parent.resolve(strict=True)
            ):
                return None
        except OSError:
            return None
        return str(expected)

from __future__ import annotations

import os
from dataclasses import replace
from typing import ClassVar
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


class _EmptyIndex:
    revision = 0
    entries: tuple = ()


_EMPTY_INDEX = _EmptyIndex()


class QueryService:
    """The query facade (F0003-S0007).

    Read-only projections over persisted state. No method here may write to the
    filesystem, append a runtime event, or change run, gate, transcript, artifact, or
    proposal state. That is not a convention: `QUERY_SURFACE` below is the declared
    public surface, and `tests/contract/test_facade_split.py` fails the build when a
    method is added that is not declared, when a declared name reads as a mutation, or
    when executing the surface leaves any trace on disk.

    `_fresh` reconciles a stale session reference *in memory* to report an accurate
    status. It deliberately does not commit that correction — a probe that only reports
    is a query; reconciliation that persists is `CommandService.runs.reconcile`.

    A query must not lazily initialize state either. Against an absent runtime root the
    surface returns empty projections rather than creating the directory; the first
    authorized mutation creates it.
    """

    QUERY_SURFACE: ClassVar[frozenset[str]] = frozenset({
        "sessions",
        "status",
        "evidence",
        "recovery_candidates",
        "recovery_status",
        "artifacts",
        "artifact",
        "metrics",
        "proposals",
        "proposal",
    })

    def __init__(self, *, repository: RunRepository, authorization: AuthorizationService, identity: IdentityPort, tmux: TmuxPort | None = None, index: object | None = None, proposals: object | None = None) -> None:
        self._repository = repository
        self._authorization = authorization
        self._identity = identity
        self._tmux = tmux
        # The artifact index is optional so a composition without F0003 wiring still
        # builds. An absent index reads as an empty one, never as an error.
        self._index = index
        self._proposals = proposals

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

    def artifacts(self, run_id: str, actor: Actor | None = None, kind: str | None = None) -> tuple:
        """List indexed artifacts for a run. Reads the index; never creates it."""
        subject = self._actor(actor)
        run = self._repository.load(run_id)
        require_authorized(self._repository, self._authorization, run, subject, Action.READ_STATE)
        if self._index is None:
            return ()
        entries = self._index.load(run_id).entries
        if kind is not None:
            entries = tuple(e for e in entries if e.artifact_kind.value == kind)
        return entries

    def artifact(self, artifact_id: str, actor: Actor | None = None):
        """Resolve one artifact by its opaque id.

        The run id is the first ID segment, so no scan is needed. `root_key` is *not*
        parsed -- it identifies which root the digest is relative to, and reconstructing
        a path from it would defeat the point of an opaque identifier.
        """
        parts = artifact_id.split("/")
        if len(parts) != 3 or not parts[0]:
            raise error(
                ErrorCode.USAGE_ERROR, "Malformed artifact id.", "usage",
                "Pass an artifact id exactly as `evidence list` reported it.",
                artifact_id=artifact_id,
            )
        for entry in self.artifacts(parts[0], actor):
            if entry.artifact_id == artifact_id:
                return entry
        raise error(
            ErrorCode.ARTIFACT_NOT_FOUND, "Artifact is not indexed.", "not-found",
            "Run evidence index for this run, then retry.", artifact_id=artifact_id,
        )

    def metrics(self, run_id: str, actor: Actor | None = None):
        """Recompute the metric snapshot. Derived, never stored, never authoritative."""
        from .metrics import derive

        subject = self._actor(actor)
        run = self._repository.load(run_id)
        require_authorized(self._repository, self._authorization, run, subject, Action.READ_STATE)
        document = self._index.load(run_id) if self._index is not None else _EMPTY_INDEX
        return derive(self._fresh(run), document, datetime.now().astimezone())

    def proposals(self, run_id: str, actor: Actor | None = None, status: str | None = None) -> tuple:
        subject = self._actor(actor)
        run = self._repository.load(run_id)
        require_authorized(self._repository, self._authorization, run, subject, Action.READ_STATE)
        if self._proposals is None:
            return ()
        found = self._proposals.list(run_id)
        if status is not None:
            found = tuple(p for p in found if p.proposal_status.value.lower() == status.lower())
        return found

    def proposal(self, run_id: str, proposal_id: str, actor: Actor | None = None):
        for candidate in self.proposals(run_id, actor):
            if candidate.proposal_id == proposal_id:
                return candidate
        raise error(
            ErrorCode.PROPOSAL_NOT_FOUND, "Proposal is not recorded for this run.",
            "not-found", "List proposals with `learn list`.", proposal_id=proposal_id,
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

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import replace
from pathlib import Path

from nebula_agents.domain.enums import Action, ArtifactStatus, DecisionKind, GateStatus, ValidatorKey
from nebula_agents.domain.errors import ErrorCode, NebulaError, error
from nebula_agents.domain.models import Actor, AuthorizationContext, AuthorizationResource, GateDecisionRequest, RunRecord, ValidatorResult
from nebula_agents.domain.transitions import advance, decide_gate, resume_gate, with_validator

from .authorization import AuthorizationService
from .ports import Clock, EvidenceWatcher, RunRepository, ValidatorRunner
from .runs import commit_authorized, require_authorized, runtime_event


_VALIDATOR_COMMAND_TEMPLATES = {
    ValidatorKey.STORIES: "python3 validate-stories.py --product-root {workspace} {feature}",
    ValidatorKey.TRACKERS: "python3 validate-trackers.py --product-root {workspace} --skip-feature-evidence",
    ValidatorKey.TEMPLATES: "python3 validate_templates.py",
}


class GateService:
    def __init__(self, *, repository: RunRepository, authorization: AuthorizationService, runner: ValidatorRunner, clock: Clock, watcher: EvidenceWatcher | None = None) -> None:
        self._repository = repository
        self._authorization = authorization
        self._runner = runner
        self._clock = clock
        self._watcher = watcher

    @staticmethod
    def _resource(run: RunRecord) -> AuthorizationResource:
        return AuthorizationResource(run.workspace_root, run.owner.uid, run.run_id)

    def _fresh_evidence(self, run: RunRecord) -> tuple[bool, str | None]:
        if self._watcher is None:
            ready = all(
                any(item.relative_path == required and item.status is ArtifactStatus.AVAILABLE for item in run.artifacts)
                for required in run.gate.required_evidence
            )
            return ready, None
        observations = self._watcher.observe_once(run, run.gate.required_evidence)
        semantic_check = getattr(self._watcher, "semantic_gate_ready", None)
        semantic_ready = bool(callable(semantic_check) and run.gate.gate_id and semantic_check(run, run.gate.gate_id))
        if (
            not semantic_ready
            or tuple(item.relative_path for item in observations) != run.gate.required_evidence
            or any(item.status is not ArtifactStatus.AVAILABLE for item in observations)
        ):
            return False, None

        requested_root = Path(run.evidence_root) if run.evidence_root else Path(run.workspace_root)
        if requested_root.is_symlink():
            return False, None
        root = requested_root.resolve()
        digest = hashlib.sha256()
        digest.update((run.gate.gate_id or "").encode("ascii", errors="ignore"))
        for relative in run.gate.required_evidence:
            if not relative or Path(relative).is_absolute():
                return False, None
            requested = root / relative
            current = root
            if any((current := current / part).is_symlink() for part in Path(relative).parts):
                return False, None
            candidate = requested.resolve()
            try:
                candidate.relative_to(root)
                fd = os.open(candidate, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            except (OSError, ValueError):
                return False, None
            try:
                details = os.fstat(fd)
                if not stat.S_ISREG(details.st_mode) or details.st_size > 16 * 1024 * 1024:
                    return False, None
                digest.update(relative.encode("utf-8", errors="replace"))
                digest.update(b"\0")
                while True:
                    chunk = os.read(fd, 64 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                final_details = os.fstat(fd)
                if final_details.st_size != details.st_size or final_details.st_mtime_ns != details.st_mtime_ns:
                    return False, None
                digest.update(b"\0")
            finally:
                os.close(fd)
        return True, digest.hexdigest()

    def _require_fresh_approval(self, current: RunRecord) -> None:
        if current.gate.status is not GateStatus.PENDING or current.gate.gate_id is None:
            raise error(ErrorCode.GATE_BLOCKED, "The gate is no longer pending", "gate-blocked", "Refresh the gate state.")
        ready, digest = self._fresh_evidence(current)
        validator = current.latest_validator
        if (
            not ready
            or digest is None
            or validator is None
            or validator.exit_code != 0
            or validator.gate_id != current.gate.gate_id
            or validator.validated_revision != current.revision
            or validator.evidence_digest != digest
        ):
            raise error(
                ErrorCode.GATE_BLOCKED,
                "Required evidence or validator results are stale",
                "gate-blocked",
                "Reconcile evidence and rerun the required validator for the current gate revision.",
            )

    def run_validator(self, run_id: str, key: ValidatorKey, actor: Actor) -> RunRecord:
        if not isinstance(key, ValidatorKey):
            raise error(ErrorCode.VALIDATOR_UNKNOWN, "Validator is not allowlisted", "usage", "Choose stories, trackers, or templates.")
        run = self._repository.load(run_id)
        context = AuthorizationContext(validator_key=key)
        require_authorized(self._repository, self._authorization, run, actor, Action.RUN_VALIDATOR, context)
        started_at = self._clock.now()
        started = advance(run, now=started_at)
        started = commit_authorized(
            self._repository,
            self._authorization,
            expected_revision=run.revision,
            next_record=started,
            event=runtime_event(run, actor, "ValidatorStarted", started_at, {"validator_key": key.value}),
            actor=actor,
            action=Action.RUN_VALIDATOR,
            context=context,
        )
        try:
            result = self._runner.run(
                key,
                workspace_root=Path(run.workspace_root),
                feature_id=run.feature_id,
                run_id=run.run_id,
                timeout_seconds=120.0,
            )
        except BaseException:
            cancelled_at = self._clock.now()
            duration_ms = max(0, int((cancelled_at - started_at).total_seconds() * 1000))
            cancelled_result = ValidatorResult(
                key,
                125,
                duration_ms,
                "Validator execution did not complete",
                None,
                cancelled_at,
                _VALIDATOR_COMMAND_TEMPLATES[key],
                started.gate.gate_id,
                None,
                None,
            )
            cancelled = with_validator(started, cancelled_result, cancelled_at)
            cancelled = replace(cancelled, gate=replace(cancelled.gate, evidence_ready=False, status=GateStatus.BLOCKED))
            try:
                commit_authorized(
                    self._repository,
                    self._authorization,
                    expected_revision=started.revision,
                    next_record=cancelled,
                    event=runtime_event(started, actor, "ValidatorCancelled", cancelled_at, {
                        "validator_key": key.value,
                        "exit_code": cancelled_result.exit_code,
                        "duration_ms": duration_ms,
                    }),
                    actor=actor,
                    action=Action.RUN_VALIDATOR,
                    context=context,
                )
            except Exception:
                pass
            raise
        completed_at = self._clock.now()
        required_ready, evidence_digest = self._fresh_evidence(started)
        terminal_revision = started.revision + 1
        result = replace(
            result,
            gate_id=started.gate.gate_id,
            validated_revision=terminal_revision,
            evidence_digest=evidence_digest if result.exit_code == 0 and required_ready else None,
        )
        complete = with_validator(started, result, completed_at)
        evidence_ready = result.exit_code == 0 and required_ready and result.evidence_digest is not None
        complete = replace(
            complete,
            gate=replace(complete.gate, evidence_ready=evidence_ready, status=GateStatus.PENDING if evidence_ready else GateStatus.BLOCKED),
        )
        event_type = "ValidatorTimedOut" if result.exit_code == 124 else "ValidatorCompleted"
        return commit_authorized(
            self._repository,
            self._authorization,
            expected_revision=started.revision,
            next_record=complete,
            event=runtime_event(started, actor, event_type, completed_at, {
                "validator_key": key.value,
                "exit_code": result.exit_code,
                "duration_ms": result.duration_ms,
                "artifact_path": result.artifact_path,
                "command_template": result.command_template,
                "gate_id": result.gate_id,
                "validated_revision": result.validated_revision,
                "evidence_digest": result.evidence_digest,
            }),
            actor=actor,
            action=Action.RUN_VALIDATOR,
            context=context,
        )

    def decide(self, request: GateDecisionRequest, actor: Actor) -> RunRecord:
        if request.decision is DecisionKind.APPROVE and not request.confirmed:
            raise error(ErrorCode.USAGE_ERROR, "Gate approval requires explicit confirmation", "usage", "Confirm the displayed gate, revision, and evidence summary.")
        run = self._repository.load(request.run_id)
        context = AuthorizationContext(decision=request.decision)
        require_authorized(self._repository, self._authorization, run, actor, Action.DECIDE_GATE, context)
        if run.revision != request.expected_revision:
            raise error(ErrorCode.STALE_REVISION, "The run changed after it was displayed", "conflict", "Refresh and retry.", current_revision=run.revision)
        now = self._clock.now()
        try:
            changed = decide_gate(
                run,
                gate_id=request.gate_id,
                decision=request.decision,
                reason=request.reason,
                actor=replace(actor, display_label=request.display_label) if request.display_label is not None else actor,
                now=now,
            )
        except NebulaError:
            blocked = advance(run, now=now)
            commit_authorized(
                self._repository,
                self._authorization,
                expected_revision=run.revision,
                next_record=blocked,
                event=runtime_event(run, actor, "GateDecisionBlocked", now, {"gate_id": request.gate_id, "decision": request.decision.value}),
                actor=actor,
                action=Action.DECIDE_GATE,
                context=context,
            )
            raise
        event_type = "GateApproved" if request.decision is DecisionKind.APPROVE else "GateHeld"
        try:
            return commit_authorized(
                self._repository,
                self._authorization,
                expected_revision=run.revision,
                next_record=changed,
                event=runtime_event(run, actor, event_type, now, {"gate_id": request.gate_id, "decision": request.decision.value, "record_revision": run.revision}),
                actor=actor,
                action=Action.DECIDE_GATE,
                context=context,
                validate_current=self._require_fresh_approval if request.decision is DecisionKind.APPROVE and self._watcher is not None else None,
                validation_record=run,
            )
        except NebulaError as exc:
            if exc.code is not ErrorCode.GATE_BLOCKED:
                raise
            blocked = advance(run, now=now)
            try:
                commit_authorized(
                    self._repository,
                    self._authorization,
                    expected_revision=run.revision,
                    next_record=blocked,
                    event=runtime_event(run, actor, "GateDecisionBlocked", now, {"gate_id": request.gate_id, "decision": request.decision.value}),
                    actor=actor,
                    action=Action.DECIDE_GATE,
                    context=context,
                )
            except NebulaError:
                pass
            raise

    def resume(self, run_id: str, actor: Actor, expected_revision: int) -> RunRecord:
        run = self._repository.load(run_id)
        context = AuthorizationContext(decision=DecisionKind.HOLD)
        require_authorized(self._repository, self._authorization, run, actor, Action.DECIDE_GATE, context)
        if run.revision != expected_revision:
            raise error(ErrorCode.STALE_REVISION, "The run changed after it was displayed", "conflict", "Refresh and retry.")
        now = self._clock.now()
        changed = resume_gate(run, now)
        return commit_authorized(
            self._repository,
            self._authorization,
            expected_revision=run.revision,
            next_record=changed,
            event=runtime_event(run, actor, "GateResumed", now, {"gate_id": run.gate.gate_id}),
            actor=actor,
            action=Action.DECIDE_GATE,
            context=context,
        )

from __future__ import annotations

import os
from dataclasses import replace
from typing import Mapping

from nebula_agents.domain.enums import Action, DecisionKind, Role, RunStatus
from nebula_agents.domain.errors import ErrorCode, error
from nebula_agents.domain.models import (
    Actor,
    AuthorizationContext,
    AuthorizationDecision,
    AuthorizationResource,
    JsonValue,
    RunProjection,
    RunRecord,
)

from .ports import PolicyPort


class AuthorizationService:
    """Default-deny local authorization over a schema-validated policy."""

    def __init__(self, policy: PolicyPort) -> None:
        self._policy = policy

    def authorize(
        self,
        subject: Actor,
        action: Action,
        resource: AuthorizationResource,
        context: AuthorizationContext | None = None,
    ) -> AuthorizationDecision:
        context = context or AuthorizationContext()
        try:
            policy = self._policy.load()
        except Exception:
            return AuthorizationDecision(False, "policy_unavailable")
        if policy.get("default_effect") != "deny":
            return AuthorizationDecision(False, "policy_default_invalid")

        if subject.role is Role.SYSTEM:
            allowed = action in (Action.PROBE, Action.READ_STATE) and (
                resource.owner_uid is None or subject.uid == resource.owner_uid
            )
            return AuthorizationDecision(allowed, "system_internal" if allowed else "system_action_denied")

        if not self._has_binding(policy, subject):
            return AuthorizationDecision(False, "subject_not_bound")

        owned = resource.owner_uid is None or resource.owner_uid == subject.uid
        if subject.role is Role.LOCAL_OPERATOR:
            return AuthorizationDecision(owned, "owner" if owned else "run_not_owned")

        if subject.role is not Role.REVIEWER:
            return AuthorizationDecision(False, "role_unknown")
        if action in (Action.PROBE, Action.READ_STATE):
            return AuthorizationDecision(True, "reviewer_read")
        if action is Action.RUN_VALIDATOR:
            allowlist = policy.get("validator_allowlist", ["stories", "trackers", "templates"])
            allowed = context.validator_key is not None and context.validator_key.value in allowlist
            return AuthorizationDecision(allowed, "validator_allowlisted" if allowed else "validator_denied")

        grants = policy.get("reviewer_grants", {})
        if not isinstance(grants, Mapping):
            return AuthorizationDecision(False, "reviewer_grants_invalid")
        grant_key = {
            Action.LAUNCH: "reviewer_can_launch",
            Action.ATTACH: "reviewer_can_attach",
            Action.CONFIGURE_TRANSCRIPT: "reviewer_can_configure_transcript",
        }.get(action)
        if action is Action.DECIDE_GATE:
            if context.decision is DecisionKind.HOLD:
                grant_key = "reviewer_can_hold"
            elif context.decision is DecisionKind.APPROVE:
                grant_key = "reviewer_can_approve"
            else:
                return AuthorizationDecision(False, "gate_decision_missing")
        allowed = bool(grant_key and grants.get(grant_key, False))
        return AuthorizationDecision(allowed, grant_key if allowed else "reviewer_grant_missing")

    @staticmethod
    def _has_binding(policy: Mapping[str, JsonValue], subject: Actor) -> bool:
        bindings = policy.get("bindings", [])
        if not isinstance(bindings, list):
            return False
        groups = (set(os.getgroups()) | {os.getgid()}) if subject.uid == os.getuid() else set()
        uid_roles: set[str] = set()
        group_roles: set[str] = set()
        for item in bindings:
            if not isinstance(item, dict) or not isinstance(item.get("role"), str):
                continue
            if item.get("subject_type") == "uid" and item.get("subject_id") == subject.uid:
                uid_roles.add(item["role"])
            if item.get("subject_type") == "gid" and item.get("subject_id") in groups:
                group_roles.add(item["role"])
        effective = uid_roles or group_roles
        return len(effective) == 1 and subject.role.value in effective

    def require(
        self,
        subject: Actor,
        action: Action,
        resource: AuthorizationResource,
        context: AuthorizationContext | None = None,
    ) -> None:
        decision = self.authorize(subject, action, resource, context)
        if not decision.allowed:
            raise error(
                ErrorCode.FORBIDDEN,
                "The local policy denied this operation",
                "forbidden",
                "Use the owning OS account or request an explicit reviewer grant.",
                reason=decision.reason,
                action=action.value,
            )
        if action not in (Action.PROBE, Action.READ_STATE):
            initializer = getattr(self._policy, "initialize", None)
            if callable(initializer):
                initializer(subject.uid)
                # The persisted, schema-validated policy is authoritative. A
                # race or conflicting pre-existing policy must fail closed.
                decision = self.authorize(subject, action, resource, context)
                if not decision.allowed:
                    raise error(
                        ErrorCode.FORBIDDEN,
                        "The persisted local policy denied this operation",
                        "forbidden",
                        "Use the owning OS account or request an explicit reviewer grant.",
                        reason=decision.reason,
                        action=action.value,
                    )


def safe_run_projection(run: RunRecord, subject: Actor, authorization: AuthorizationService) -> RunProjection:
    """Produce the only externally authorized run view, with explicit capabilities."""
    resource = AuthorizationResource(run.workspace_root, run.owner.uid, run.run_id)
    attach_authorized = authorization.authorize(subject, Action.ATTACH, resource).allowed
    # Attach is both an authorization and a lifecycle capability. Terminal or
    # verified-missing sessions must never advertise an actionable attach.
    can_attach = attach_authorized and run.status is RunStatus.ACTIVE
    can_configure = authorization.authorize(subject, Action.CONFIGURE_TRANSCRIPT, resource).allowed
    can_decide = any(
        authorization.authorize(
            subject,
            Action.DECIDE_GATE,
            resource,
            AuthorizationContext(decision=decision),
        ).allowed
        for decision in (DecisionKind.HOLD, DecisionKind.APPROVE)
    )
    owner = subject.role is Role.LOCAL_OPERATOR and subject.uid == run.owner.uid
    validator = run.latest_validator
    if not owner and validator is not None:
        validator = replace(
            validator,
            summary="Validator output is hidden in this non-owner view.",
            artifact_path=None,
        )
    transcript = run.transcript if owner or can_configure else replace(run.transcript, path=None, preview=None)
    return RunProjection(
        run.schema_version,
        run.revision,
        run.run_id,
        run.feature_id,
        run.story_id,
        run.provider_key,
        run.prompt_action,
        run.status,
        run.owner,
        run.gate,
        validator,
        run.artifacts,
        transcript,
        run.created_at,
        run.updated_at,
        run.last_seen_at,
        run.tmux_session if (owner and run.status is RunStatus.ACTIVE) or can_attach else None,
        run.workspace_root if owner else None,
        run.prompt_contract if owner else None,
        run.evidence_root if owner else None,
        run.audit_log_path if owner else None,
        can_attach,
        owner,
        run.status in (RunStatus.DETACHED_OR_EXITED, RunStatus.UNKNOWN, RunStatus.FAILED),
        can_decide,
        can_configure,
    )

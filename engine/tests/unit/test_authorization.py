from __future__ import annotations

from dataclasses import dataclass

import pytest

from nebula_agents.application.authorization import AuthorizationService
from nebula_agents.domain.enums import Action, DecisionKind, Role, ValidatorKey
from nebula_agents.domain.errors import ErrorCode, NebulaError
from nebula_agents.domain.models import (
    Actor,
    AuthorizationContext,
    AuthorizationResource,
)


class Policy:
    def __init__(self, document=None, failure: Exception | None = None) -> None:
        self.document = document
        self.failure = failure

    def load(self):
        if self.failure is not None:
            raise self.failure
        return self.document


def _policy(role: Role, *, grants: dict[str, bool] | None = None) -> dict[str, object]:
    reviewer_grants = {
        "reviewer_can_launch": False,
        "reviewer_can_attach": False,
        "reviewer_can_hold": False,
        "reviewer_can_approve": False,
        "reviewer_can_configure_transcript": False,
    }
    reviewer_grants.update(grants or {})
    return {
        "default_effect": "deny",
        "bindings": [{"subject_type": "uid", "subject_id": 1000, "role": role.value}],
        "reviewer_grants": reviewer_grants,
        "validator_allowlist": ["stories", "trackers", "templates"],
    }


RESOURCE = AuthorizationResource("/workspace", owner_uid=1000, run_id="2026-07-13-deadbeef")


@pytest.mark.parametrize("action", tuple(Action))
def test_local_operator_can_act_only_on_owned_run(action: Action) -> None:
    service = AuthorizationService(Policy(_policy(Role.LOCAL_OPERATOR)))
    owner = Actor(1000, "operator", Role.LOCAL_OPERATOR)
    context = AuthorizationContext(
        validator_key=ValidatorKey.STORIES if action is Action.RUN_VALIDATOR else None,
        decision=DecisionKind.APPROVE if action is Action.DECIDE_GATE else None,
    )
    assert service.authorize(owner, action, RESOURCE, context).allowed is True
    foreign = AuthorizationResource("/workspace", owner_uid=1001)
    assert service.authorize(owner, action, foreign, context).allowed is False


@pytest.mark.parametrize("action", [Action.PROBE, Action.READ_STATE])
def test_reviewer_can_read_by_default(action: Action) -> None:
    service = AuthorizationService(Policy(_policy(Role.REVIEWER)))
    reviewer = Actor(1000, "reviewer", Role.REVIEWER)
    assert service.authorize(reviewer, action, RESOURCE).allowed is True


def test_reviewer_can_run_only_allowlisted_validator() -> None:
    service = AuthorizationService(Policy(_policy(Role.REVIEWER)))
    reviewer = Actor(1000, "reviewer", Role.REVIEWER)
    assert service.authorize(
        reviewer,
        Action.RUN_VALIDATOR,
        RESOURCE,
        AuthorizationContext(validator_key=ValidatorKey.STORIES),
    ).allowed
    assert not service.authorize(
        reviewer, Action.RUN_VALIDATOR, RESOURCE, AuthorizationContext()
    ).allowed


@pytest.mark.parametrize(
    ("action", "decision"),
    [
        (Action.LAUNCH, None),
        (Action.ATTACH, None),
        (Action.DECIDE_GATE, DecisionKind.HOLD),
        (Action.DECIDE_GATE, DecisionKind.APPROVE),
        (Action.CONFIGURE_TRANSCRIPT, None),
    ],
)
def test_reviewer_mutations_are_denied_by_default(
    action: Action, decision: DecisionKind | None
) -> None:
    service = AuthorizationService(Policy(_policy(Role.REVIEWER)))
    reviewer = Actor(1000, "reviewer", Role.REVIEWER)
    assert not service.authorize(
        reviewer, action, RESOURCE, AuthorizationContext(decision=decision)
    ).allowed


@pytest.mark.parametrize(
    ("grant", "action", "decision"),
    [
        ("reviewer_can_launch", Action.LAUNCH, None),
        ("reviewer_can_attach", Action.ATTACH, None),
        ("reviewer_can_hold", Action.DECIDE_GATE, DecisionKind.HOLD),
        ("reviewer_can_approve", Action.DECIDE_GATE, DecisionKind.APPROVE),
        ("reviewer_can_configure_transcript", Action.CONFIGURE_TRANSCRIPT, None),
    ],
)
def test_reviewer_grants_enable_only_named_operation(
    grant: str, action: Action, decision: DecisionKind | None
) -> None:
    service = AuthorizationService(Policy(_policy(Role.REVIEWER, grants={grant: True})))
    reviewer = Actor(1000, "reviewer", Role.REVIEWER)
    assert service.authorize(
        reviewer, action, RESOURCE, AuthorizationContext(decision=decision)
    ).allowed


def test_reviewer_gate_grant_requires_explicit_decision_kind() -> None:
    service = AuthorizationService(
        Policy(_policy(Role.REVIEWER, grants={"reviewer_can_approve": True}))
    )
    reviewer = Actor(1000, "reviewer", Role.REVIEWER)
    assert not service.authorize(
        reviewer, Action.DECIDE_GATE, RESOURCE, AuthorizationContext(decision=None)
    ).allowed


@pytest.mark.parametrize(
    "document",
    [
        {"default_effect": "allow", "bindings": []},
        {"default_effect": "deny", "bindings": []},
    ],
)
def test_invalid_or_unbound_policy_fails_closed(document: dict[str, object]) -> None:
    service = AuthorizationService(Policy(document))
    subject = Actor(1000, "operator", Role.LOCAL_OPERATOR)
    assert not service.authorize(subject, Action.LAUNCH, RESOURCE).allowed


def test_policy_load_failure_fails_closed_and_require_raises_forbidden() -> None:
    service = AuthorizationService(Policy(failure=ValueError("malformed")))
    subject = Actor(1000, "operator", Role.LOCAL_OPERATOR)
    assert not service.authorize(subject, Action.LAUNCH, RESOURCE).allowed
    with pytest.raises(NebulaError) as caught:
        service.require(subject, Action.LAUNCH, RESOURCE)
    assert caught.value.code is ErrorCode.FORBIDDEN
    assert caught.value.exit_code == 5


def test_binding_resolution_ignores_malformed_entries_and_uses_matching_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subject = Actor(1000, "reviewer", Role.REVIEWER)
    document = _policy(Role.REVIEWER)
    document["bindings"] = [
        "malformed",
        {"subject_type": "gid", "subject_id": 20, "role": 7},
        {"subject_type": "gid", "subject_id": 10, "role": Role.REVIEWER.value},
    ]
    monkeypatch.setattr("nebula_agents.application.authorization.os.getuid", lambda: 1000)
    monkeypatch.setattr("nebula_agents.application.authorization.os.getgid", lambda: 9)
    monkeypatch.setattr("nebula_agents.application.authorization.os.getgroups", lambda: [10])

    decision = AuthorizationService(Policy(document)).authorize(
        subject, Action.READ_STATE, RESOURCE
    )

    assert decision.allowed is True
    assert decision.reason == "reviewer_read"


def test_conflicting_effective_uid_roles_fail_closed_independent_of_groups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subject = Actor(1000, "operator", Role.LOCAL_OPERATOR)
    document = _policy(Role.LOCAL_OPERATOR)
    document["bindings"] = [
        {"subject_type": "uid", "subject_id": 1000, "role": "LocalOperator"},
        {"subject_type": "uid", "subject_id": 1000, "role": "Reviewer"},
        {"subject_type": "gid", "subject_id": 10, "role": "LocalOperator"},
    ]
    monkeypatch.setattr("nebula_agents.application.authorization.os.getuid", lambda: 1000)
    monkeypatch.setattr("nebula_agents.application.authorization.os.getgid", lambda: 10)
    monkeypatch.setattr("nebula_agents.application.authorization.os.getgroups", lambda: [])

    decision = AuthorizationService(Policy(document)).authorize(
        subject, Action.LAUNCH, RESOURCE
    )

    assert decision.allowed is False
    assert decision.reason == "subject_not_bound"


def test_require_rechecks_initialized_policy_and_denies_policy_race() -> None:
    class InitializingPolicy:
        def __init__(self) -> None:
            self.initialized = False

        def load(self):
            return (
                {"default_effect": "deny", "bindings": []}
                if self.initialized
                else _policy(Role.LOCAL_OPERATOR)
            )

        def initialize(self, owner_uid: int) -> None:
            assert owner_uid == 1000
            self.initialized = True

    service = AuthorizationService(InitializingPolicy())
    subject = Actor(1000, "operator", Role.LOCAL_OPERATOR)

    with pytest.raises(NebulaError) as caught:
        service.require(subject, Action.LAUNCH, RESOURCE)

    assert caught.value.code is ErrorCode.FORBIDDEN
    assert "persisted" in caught.value.message.lower()


def test_require_accepts_stable_initialized_policy() -> None:
    class StablePolicy(Policy):
        def __init__(self) -> None:
            super().__init__(_policy(Role.LOCAL_OPERATOR))
            self.initialized: list[int] = []

        def initialize(self, owner_uid: int) -> None:
            self.initialized.append(owner_uid)

    policy = StablePolicy()
    service = AuthorizationService(policy)
    subject = Actor(1000, "operator", Role.LOCAL_OPERATOR)

    service.require(subject, Action.LAUNCH, RESOURCE)

    assert policy.initialized == [1000]


def test_require_accepts_authorized_mutation_without_optional_initializer() -> None:
    service = AuthorizationService(Policy(_policy(Role.LOCAL_OPERATOR)))
    subject = Actor(1000, "operator", Role.LOCAL_OPERATOR)

    service.require(subject, Action.LAUNCH, RESOURCE)

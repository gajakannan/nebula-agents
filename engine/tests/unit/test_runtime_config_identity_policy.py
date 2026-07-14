from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from nebula_agents.domain.enums import Role
from nebula_agents.domain.errors import ErrorCode, NebulaError
from nebula_agents.infrastructure.config import resolve_config
from nebula_agents.infrastructure.identity import OsIdentity, system_actor
from nebula_agents.infrastructure.policy_store import LocalPolicyStore
from nebula_agents.infrastructure.schema_registry import JsonSchemaRegistry


class PolicyDocument:
    def __init__(self, bindings: list[object]) -> None:
        self.bindings = bindings

    def load(self):
        return {"bindings": self.bindings}


def test_config_resolves_default_runtime_and_contract_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("NEBULA_AGENTS_RUNTIME_DIR", raising=False)
    config = resolve_config(tmp_path / "." / "workspace")
    assert config.workspace_root == (tmp_path / "workspace").resolve()
    assert config.runtime_root == config.workspace_root / ".nebula-agents" / "runtime"
    assert config.runs_root == config.runtime_root / "runs"
    assert config.schema_root == config.workspace_root / "planning-mds" / "schemas"
    assert config.watch_interval_seconds == 0.5
    assert config.debounce_seconds == 0.1


def test_explicit_runtime_override_wins_over_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEBULA_AGENTS_RUNTIME_DIR", str(tmp_path / "environment"))
    explicit = tmp_path / "explicit"
    assert resolve_config(tmp_path, explicit).runtime_root == explicit.resolve()
    assert resolve_config(tmp_path).runtime_root == (tmp_path / "environment").resolve()


def test_identity_prefers_exact_uid_binding_over_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("nebula_agents.infrastructure.identity.os.getuid", lambda: 1000)
    monkeypatch.setattr("nebula_agents.infrastructure.identity.os.getgid", lambda: 10)
    monkeypatch.setattr("nebula_agents.infrastructure.identity.os.getgroups", lambda: [20])
    monkeypatch.setattr(
        "nebula_agents.infrastructure.identity.pwd.getpwuid",
        lambda _uid: SimpleNamespace(pw_name="operator"),
    )
    policy = PolicyDocument(
        [
            {"subject_type": "gid", "subject_id": 20, "role": "Reviewer"},
            "malformed",
            {"subject_type": "uid", "subject_id": 1000, "role": "LocalOperator"},
        ]
    )
    actor = OsIdentity(policy).current_actor()  # type: ignore[arg-type]
    assert actor.uid == 1000
    assert actor.username == "operator"
    assert actor.role is Role.LOCAL_OPERATOR


def test_identity_uses_group_binding_and_unbound_fails_to_reviewer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("nebula_agents.infrastructure.identity.os.getuid", lambda: 1000)
    monkeypatch.setattr("nebula_agents.infrastructure.identity.os.getgid", lambda: 10)
    monkeypatch.setattr("nebula_agents.infrastructure.identity.os.getgroups", lambda: [20])
    monkeypatch.setattr(
        "nebula_agents.infrastructure.identity.pwd.getpwuid",
        lambda _uid: SimpleNamespace(pw_name="operator"),
    )
    group_actor = OsIdentity(
        PolicyDocument([{"subject_type": "gid", "subject_id": 20, "role": "LocalOperator"}])  # type: ignore[arg-type]
    ).current_actor()
    assert group_actor.role is Role.LOCAL_OPERATOR
    unbound = OsIdentity(PolicyDocument([])).current_actor()  # type: ignore[arg-type]
    assert unbound.role is Role.REVIEWER


@pytest.mark.parametrize(
    "bindings",
    [
        [
            {"subject_type": "gid", "subject_id": 10, "role": "Reviewer"},
            {"subject_type": "gid", "subject_id": 20, "role": "LocalOperator"},
        ],
        [
            {"subject_type": "gid", "subject_id": 20, "role": "LocalOperator"},
            {"subject_type": "gid", "subject_id": 10, "role": "Reviewer"},
        ],
    ],
)
def test_identity_denies_conflicting_group_roles_regardless_of_binding_order(
    monkeypatch: pytest.MonkeyPatch, bindings: list[object]
) -> None:
    monkeypatch.setattr("nebula_agents.infrastructure.identity.os.getuid", lambda: 1000)
    monkeypatch.setattr("nebula_agents.infrastructure.identity.os.getgid", lambda: 10)
    monkeypatch.setattr("nebula_agents.infrastructure.identity.os.getgroups", lambda: [20])
    monkeypatch.setattr(
        "nebula_agents.infrastructure.identity.pwd.getpwuid",
        lambda _uid: SimpleNamespace(pw_name="operator"),
    )

    with pytest.raises(NebulaError) as caught:
        OsIdentity(PolicyDocument(bindings)).current_actor()  # type: ignore[arg-type]

    assert caught.value.code is ErrorCode.FORBIDDEN


@pytest.mark.parametrize(
    "bindings",
    [
        [
            {"subject_type": "gid", "subject_id": 10, "role": "Reviewer"},
            {"subject_type": "gid", "subject_id": 20, "role": "Reviewer"},
        ],
        [
            {"subject_type": "gid", "subject_id": 20, "role": "Reviewer"},
            {"subject_type": "gid", "subject_id": 10, "role": "Reviewer"},
        ],
    ],
)
def test_identity_same_role_groups_resolve_deterministically(
    monkeypatch: pytest.MonkeyPatch, bindings: list[object]
) -> None:
    monkeypatch.setattr("nebula_agents.infrastructure.identity.os.getuid", lambda: 1000)
    monkeypatch.setattr("nebula_agents.infrastructure.identity.os.getgid", lambda: 10)
    monkeypatch.setattr("nebula_agents.infrastructure.identity.os.getgroups", lambda: [20])
    monkeypatch.setattr(
        "nebula_agents.infrastructure.identity.pwd.getpwuid",
        lambda _uid: SimpleNamespace(pw_name="operator"),
    )

    actor = OsIdentity(PolicyDocument(bindings)).current_actor()  # type: ignore[arg-type]
    assert actor.role is Role.REVIEWER


@pytest.mark.parametrize(
    "bindings",
    [
        [
            {"subject_type": "uid", "subject_id": 1000, "role": "Reviewer"},
            {"subject_type": "uid", "subject_id": 1000, "role": "Reviewer"},
        ],
        [
            {"subject_type": "uid", "subject_id": 1000, "role": "Reviewer"},
            {"subject_type": "uid", "subject_id": 1000, "role": "LocalOperator"},
        ],
        [
            {"subject_type": "gid", "subject_id": 20, "role": "Reviewer"},
            {"subject_type": "gid", "subject_id": 20, "role": "Reviewer"},
        ],
        [
            {"subject_type": "gid", "subject_id": 20, "role": "Reviewer"},
            {"subject_type": "gid", "subject_id": 20, "role": "LocalOperator"},
        ],
    ],
)
def test_policy_load_rejects_duplicate_or_contradictory_uid_gid_bindings(
    tmp_path: Path, schema_root: Path, bindings: list[dict[str, object]]
) -> None:
    store = LocalPolicyStore(tmp_path / "runtime", JsonSchemaRegistry(schema_root))
    store.initialize(os.getuid())
    document = json.loads(store.path.read_text(encoding="utf-8"))
    document["bindings"] = bindings
    store.path.write_text(json.dumps(document), encoding="utf-8")
    store.path.chmod(0o600)

    with pytest.raises(NebulaError) as caught:
        store.load()

    assert caught.value.code is ErrorCode.FORBIDDEN


def test_system_actor_is_explicit_non_root_bypass_identity() -> None:
    actor = system_actor(1234)
    assert actor.uid == 1234
    assert actor.username == "nebula-system"
    assert actor.role is Role.SYSTEM


def test_policy_initialization_is_private_valid_and_idempotent(
    tmp_path: Path, schema_root: Path
) -> None:
    runtime = tmp_path / "runtime"
    store = LocalPolicyStore(runtime, JsonSchemaRegistry(schema_root))
    store.initialize(1000)
    original = store.path.read_bytes()
    store.initialize(2000)
    document = store.load()
    assert store.path.read_bytes() == original
    assert runtime.stat().st_mode & 0o777 == 0o700
    assert store.path.stat().st_mode & 0o777 == 0o600
    assert document["default_effect"] == "deny"
    assert document["bindings"] == [
        {"subject_type": "uid", "subject_id": 1000, "role": "LocalOperator"}
    ]


@pytest.mark.parametrize("payload", ["{", "[]"])
def test_policy_load_rejects_malformed_or_non_object_document(
    tmp_path: Path, schema_root: Path, payload: str
) -> None:
    store = LocalPolicyStore(tmp_path / "runtime", JsonSchemaRegistry(schema_root))
    store.initialize(os.getuid())
    store.path.write_text(payload, encoding="utf-8")
    store.path.chmod(0o600)
    with pytest.raises(NebulaError) as caught:
        store.load()
    assert caught.value.code is ErrorCode.FORBIDDEN


def test_policy_load_rejects_unsafe_mode(tmp_path: Path, schema_root: Path) -> None:
    store = LocalPolicyStore(tmp_path / "runtime", JsonSchemaRegistry(schema_root))
    store.initialize(os.getuid())
    store.path.chmod(0o644)
    with pytest.raises(NebulaError) as caught:
        store.load()
    assert caught.value.code is ErrorCode.FORBIDDEN


def test_schema_registry_caches_validators_and_rejects_unallowlisted_names(
    schema_root: Path,
) -> None:
    registry = JsonSchemaRegistry(schema_root)
    first = registry._load("f0001-local-policy.schema.json")
    assert registry._load("f0001-local-policy.schema.json") is first
    for name in ("../escape.json", "other.schema.json", "f0001-policy.txt"):
        with pytest.raises(NebulaError) as caught:
            registry._load(name)
        assert caught.value.code is ErrorCode.SCHEMA_INVALID


def test_schema_registry_rejects_missing_invalid_schema_and_document(
    tmp_path: Path,
) -> None:
    registry = JsonSchemaRegistry(tmp_path)
    with pytest.raises(NebulaError):
        registry._load("f0001-missing.schema.json")
    invalid_schema = tmp_path / "f0001-invalid.schema.json"
    invalid_schema.write_text("{", encoding="utf-8")
    with pytest.raises(NebulaError):
        registry._load(invalid_schema.name)
    schema = tmp_path / "f0001-simple.schema.json"
    schema.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
                "required": ["value"],
                "properties": {"value": {"type": "integer"}},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(NebulaError) as caught:
        registry.validate(schema.name, {"value": "wrong"})
    assert caught.value.code is ErrorCode.SCHEMA_INVALID
    assert caught.value.details[0]["location"] == "value"

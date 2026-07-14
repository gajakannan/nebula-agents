from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

jsonschema = pytest.importorskip("jsonschema")
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


SCHEMAS = (
    "f0001-launch-descriptor.schema.json",
    "f0001-local-policy.schema.json",
    "f0001-preflight-result.schema.json",
    "f0001-run-record.schema.json",
    "f0001-runtime-event.schema.json",
)


def _validate(schema: dict[str, Any], document: dict[str, Any]) -> None:
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(document)


@pytest.fixture
def valid_actor() -> dict[str, Any]:
    return {
        "uid": 1000,
        "username": "operator",
        "role": "LocalOperator",
        "display_label": None,
    }


@pytest.fixture
def valid_run(valid_actor: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "revision": 1,
        "run_id": "2026-07-13-deadbeef",
        "feature_id": "F0001",
        "story_id": "F0001-S0002",
        "provider_key": "codex",
        "tmux_session": "nebula-F0001-deadbeef",
        "workspace_root": "/workspace",
        "prompt_contract": "/workspace/agents/templates/prompts/evidence-contract/feature-operator-friendly.md",
        "prompt_action": "feature",
        "status": "Active",
        "owner": valid_actor,
        "evidence_root": "/workspace/planning-mds/operations/evidence/runs/2026-07-13-deadbeef",
        "gate": {
            "gate_id": "G1",
            "status": "Pending",
            "evidence_ready": False,
            "required_evidence": ["runtime-preflight.md"],
            "decision": None,
        },
        "latest_validator": None,
        "artifacts": [],
        "transcript": {
            "status": "Disabled",
            "redaction_status": "NotRun",
            "path": None,
            "preview": None,
            "redaction_findings": 0,
            "failure_reason": None,
        },
        "audit_log_path": "/runtime/2026-07-13-deadbeef/events.jsonl",
        "last_event_sequence": 2,
        "created_at": "2026-07-13T18:00:00Z",
        "updated_at": "2026-07-13T18:00:01Z",
        "last_seen_at": "2026-07-13T18:00:01Z",
    }


def test_all_public_schemas_are_valid_draft_2020_12(load_schema) -> None:
    for name in SCHEMAS:
        Draft202012Validator.check_schema(load_schema(name))


def test_valid_run_record_matches_contract(load_schema, valid_run) -> None:
    _validate(load_schema("f0001-run-record.schema.json"), valid_run)


def test_transcript_failure_reason_is_nullable_and_bounded(load_schema, valid_run) -> None:
    schema = load_schema("f0001-run-record.schema.json")
    failed = deepcopy(valid_run)
    failed["transcript"].update(
        {
            "status": "Failed",
            "redaction_status": "Failed",
            "failure_reason": "capture-process-not-running",
        }
    )
    _validate(schema, failed)

    failed["transcript"]["failure_reason"] = "x" * 257
    with pytest.raises(ValidationError):
        _validate(schema, failed)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("run_id", "../../escape"),
        ("feature_id", "f1"),
        ("provider_key", "shell"),
        ("status", "DefinitelyActive"),
        ("tmux_session", "nebula-F0001-deadbeef; touch /tmp/pwned"),
    ],
)
def test_run_record_rejects_invalid_public_values(
    load_schema, valid_run, field: str, value: object
) -> None:
    invalid = deepcopy(valid_run)
    invalid[field] = value
    with pytest.raises(ValidationError):
        _validate(load_schema("f0001-run-record.schema.json"), invalid)


def test_run_record_rejects_additive_fields(load_schema, valid_run) -> None:
    invalid = deepcopy(valid_run)
    invalid["provider_auth_token"] = "must never be persisted"
    with pytest.raises(ValidationError):
        _validate(load_schema("f0001-run-record.schema.json"), invalid)


def test_launch_descriptor_preserves_metacharacters_as_one_argv_item(load_schema) -> None:
    prompt = "review $(touch /tmp/not-created); 'quoted' && echo nope"
    descriptor = {
        "schema_version": "1.0",
        "run_id": "2026-07-13-deadbeef",
        "provider_key": "codex",
        "executable_path": "/usr/bin/codex",
        "argv": ["/usr/bin/codex", prompt],
        "cwd": "/workspace",
        "inherited_env_names": ["HOME", "PATH", "TERM"],
        "owner_uid": 1000,
        "correlation_id": "6fddeba4-7f25-4bf1-a298-70c095235f4f",
        "created_at": "2026-07-13T18:00:00Z",
    }
    _validate(load_schema("f0001-launch-descriptor.schema.json"), descriptor)
    assert descriptor["argv"] == ["/usr/bin/codex", prompt]


@pytest.mark.parametrize("name", ["PATH;BAD", "HOME=value", "lowercase", "9START"])
def test_launch_descriptor_rejects_invalid_environment_names(load_schema, name) -> None:
    descriptor = {
        "schema_version": "1.0",
        "run_id": "2026-07-13-deadbeef",
        "provider_key": "claude",
        "executable_path": "/usr/bin/claude",
        "argv": ["/usr/bin/claude"],
        "cwd": "/workspace",
        "inherited_env_names": [name],
        "owner_uid": 1000,
        "correlation_id": "6fddeba4-7f25-4bf1-a298-70c095235f4f",
        "created_at": "2026-07-13T18:00:00Z",
    }
    with pytest.raises(ValidationError):
        _validate(load_schema("f0001-launch-descriptor.schema.json"), descriptor)


def test_policy_contract_is_default_deny(load_schema) -> None:
    policy = {
        "schema_version": "1.0",
        "policy_version": 1,
        "default_effect": "deny",
        "bindings": [{"subject_type": "uid", "subject_id": 1000, "role": "Reviewer"}],
        "reviewer_grants": {
            "reviewer_can_launch": False,
            "reviewer_can_attach": False,
            "reviewer_can_hold": False,
            "reviewer_can_approve": False,
            "reviewer_can_configure_transcript": False,
        },
        "validator_allowlist": ["stories", "trackers", "templates"],
        "updated_at": "2026-07-13T18:00:00Z",
    }
    _validate(load_schema("f0001-local-policy.schema.json"), policy)
    policy["default_effect"] = "allow"
    with pytest.raises(ValidationError):
        _validate(load_schema("f0001-local-policy.schema.json"), policy)


def test_runtime_event_rejects_unknown_event_type(load_schema, valid_actor) -> None:
    event = {
        "schema_version": "1.0",
        "run_id": "2026-07-13-deadbeef",
        "sequence": 1,
        "event_type": "ProviderSecretCaptured",
        "occurred_at": "2026-07-13T18:00:00Z",
        "actor": valid_actor,
        "correlation_id": "6fddeba4-7f25-4bf1-a298-70c095235f4f",
        "payload": {},
    }
    with pytest.raises(ValidationError):
        _validate(load_schema("f0001-runtime-event.schema.json"), event)

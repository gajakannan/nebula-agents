from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from nebula_agents.domain.enums import (
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
from nebula_agents.domain.errors import ErrorCode, NebulaError
from nebula_agents.domain.models import (
    Actor,
    GateSnapshot,
    GateDecision,
    ArtifactObservation,
    RunRecord,
    TranscriptState,
    ValidatorResult,
    deserialize_run_record,
    serialize_record,
)


def _run(now: datetime) -> RunRecord:
    actor = Actor(uid=1000, username="operator", role=Role.LOCAL_OPERATOR)
    return RunRecord(
        schema_version="1.0",
        revision=3,
        run_id="2026-07-13-deadbeef",
        feature_id="F0001",
        story_id="F0001-S0003",
        provider_key=ProviderKey.CODEX,
        tmux_session="nebula-F0001-deadbeef",
        workspace_root="/workspace",
        prompt_contract="/workspace/agents/templates/prompts/evidence-contract/feature-operator-friendly.md",
        prompt_action=PromptAction.FEATURE,
        status=RunStatus.ACTIVE,
        owner=actor,
        evidence_root="/workspace/planning-mds/operations/evidence/runs/2026-07-13-deadbeef",
        gate=GateSnapshot("G1", GateStatus.PENDING, False, ("runtime-preflight.md",), None),
        latest_validator=None,
        artifacts=(),
        transcript=TranscriptState(
            TranscriptStatus.DISABLED,
            RedactionStatus.NOT_RUN,
            None,
            None,
            0,
        ),
        audit_log_path="/runtime/2026-07-13-deadbeef/events.jsonl",
        last_event_sequence=4,
        created_at=now,
        updated_at=now,
        last_seen_at=now,
    )


def test_run_record_round_trips_without_contract_drift(fixed_now: datetime) -> None:
    expected = _run(fixed_now)
    document = serialize_record(expected)
    assert document["provider_key"] == "codex"
    assert document["created_at"] == "2026-07-13T18:00:00Z"
    assert document["artifacts"] == []
    assert deserialize_run_record(document) == expected


def test_legacy_transcript_without_failure_reason_defaults_to_none(
    fixed_now: datetime,
) -> None:
    document = serialize_record(_run(fixed_now))
    document["transcript"].pop("failure_reason", None)

    restored = deserialize_run_record(document)

    assert restored.transcript.failure_reason is None


def test_deserializer_rejects_unknown_major_schema(fixed_now: datetime) -> None:
    document = serialize_record(_run(fixed_now))
    document["schema_version"] = "2.0"
    with pytest.raises(NebulaError) as caught:
        deserialize_run_record(document)
    assert caught.value.code is ErrorCode.SCHEMA_UNSUPPORTED
    assert caught.value.exit_code == 9


def test_deserializer_rejects_missing_required_field(fixed_now: datetime) -> None:
    document = serialize_record(_run(fixed_now))
    document.pop("run_id")
    with pytest.raises(NebulaError) as caught:
        deserialize_run_record(document)
    assert caught.value.code is ErrorCode.STATE_CORRUPT


def test_deserializer_fails_closed_on_additive_field(fixed_now: datetime) -> None:
    document = serialize_record(_run(fixed_now))
    document["unapproved_addition"] = "must be rejected while additionalProperties is false"
    with pytest.raises(NebulaError) as caught:
        deserialize_run_record(document)
    assert caught.value.code is ErrorCode.STATE_CORRUPT


def test_serialize_record_rejects_non_record() -> None:
    with pytest.raises(TypeError, match="record serialization"):
        serialize_record(("not", "a", "record"))


@pytest.mark.parametrize(
    ("category", "exit_code"),
    [
        ("usage", 2),
        ("preflight", 3),
        ("not-found", 4),
        ("forbidden", 5),
        ("conflict", 6),
        ("gate-blocked", 7),
        ("command-failed", 8),
        ("state-io", 9),
        ("timeout", 10),
        ("interrupted", 130),
    ],
)
def test_expected_error_categories_have_stable_exit_codes(
    category: str, exit_code: int
) -> None:
    exc = NebulaError(ErrorCode.INTERNAL_ERROR, "safe", category, "safe remediation")
    assert exc.exit_code == exit_code


def test_serializer_normalizes_offset_timestamp_to_utc(fixed_now: datetime) -> None:
    run = replace(_run(fixed_now), updated_at=datetime.fromisoformat("2026-07-13T14:00:00-04:00"))
    assert serialize_record(run)["updated_at"] == "2026-07-13T18:00:00Z"


def test_complete_nested_run_contract_round_trips(fixed_now: datetime) -> None:
    actor = Actor(1000, "operator", Role.LOCAL_OPERATOR, "Local reviewer")
    decision = GateDecision(
        DecisionKind.HOLD,
        "investigate",
        actor,
        fixed_now,
        3,
    )
    validator = ValidatorResult(
        ValidatorKey.STORIES,
        0,
        12,
        "passed",
        "/workspace/validator.log",
        fixed_now,
    )
    artifact = ArtifactObservation(
        "runtime-preflight.md", ArtifactStatus.AVAILABLE, fixed_now, 42
    )
    complete = replace(
        _run(fixed_now),
        owner=actor,
        gate=GateSnapshot(
            "G4", GateStatus.HELD, True, ("runtime-preflight.md",), decision
        ),
        latest_validator=validator,
        artifacts=(artifact,),
        transcript=TranscriptState(
            TranscriptStatus.COMPLETED,
            RedactionStatus.REDACTED,
            "/runtime/transcript.log",
            "safe preview",
            2,
        ),
    )
    assert deserialize_run_record(serialize_record(complete)) == complete


def test_validator_template_and_gate_binding_round_trip_as_stable_contract(
    fixed_now: datetime,
) -> None:
    validator = ValidatorResult(
        ValidatorKey.TRACKERS,
        0,
        19,
        "passed",
        "/workspace/validator.log",
        fixed_now,
        "python3 validate-trackers.py --product-root {workspace} --skip-feature-evidence",
        "G4",
        7,
        "a" * 64,
    )
    run = replace(_run(fixed_now), revision=7, latest_validator=validator)

    document = serialize_record(run)

    assert document["latest_validator"] == {
        "validator_key": "trackers",
        "exit_code": 0,
        "duration_ms": 19,
        "summary": "passed",
        "artifact_path": "/workspace/validator.log",
        "completed_at": "2026-07-13T18:00:00Z",
        "command_template": validator.command_template,
        "gate_id": "G4",
        "validated_revision": 7,
        "evidence_digest": "a" * 64,
    }
    assert deserialize_run_record(document) == run


@pytest.mark.parametrize(
    ("path", "extra"),
    [
        (("owner",), {"extra": True}),
        (("gate",), {"extra": True}),
        (("gate", "decision"), {"extra": True}),
        (("latest_validator",), {"extra": True}),
        (("artifacts", 0), {"extra": True}),
        (("transcript",), {"extra": True}),
    ],
)
def test_nested_contracts_reject_additive_fields(
    fixed_now: datetime, path: tuple[object, ...], extra: dict[str, object]
) -> None:
    complete = replace(
        _run(fixed_now),
        gate=GateSnapshot(
            "G4",
            GateStatus.HELD,
            True,
            (),
            GateDecision(DecisionKind.HOLD, "reason", _run(fixed_now).owner, fixed_now, 3),
        ),
        latest_validator=ValidatorResult(
            ValidatorKey.STORIES, 0, 1, "ok", None, fixed_now
        ),
        artifacts=(
            ArtifactObservation("a.md", ArtifactStatus.AVAILABLE, fixed_now, 1),
        ),
    )
    document = serialize_record(complete)
    target = document
    for part in path:
        target = target[part]  # type: ignore[index,assignment]
    target.update(extra)  # type: ignore[union-attr]
    with pytest.raises(NebulaError) as caught:
        deserialize_run_record(document)
    assert caught.value.code is ErrorCode.STATE_CORRUPT


def test_serializer_supports_naive_utc_path_uuid_and_mapping() -> None:
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class Carrier:
        timestamp: datetime
        path: Path
        correlation_id: UUID
        values: tuple[object, ...]

    document = serialize_record(
        Carrier(
            datetime(2026, 7, 13, 18, 0),
            Path("/tmp/safe"),
            UUID("6fddeba4-7f25-4bf1-a298-70c095235f4f"),
            ({"safe": True},),
        )
    )
    assert document == {
        "timestamp": "2026-07-13T18:00:00Z",
        "path": "/tmp/safe",
        "correlation_id": "6fddeba4-7f25-4bf1-a298-70c095235f4f",
        "values": [{"safe": True}],
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [("created_at", 123), ("updated_at", "2026-07-13T18:00:00")],
)
def test_deserializer_rejects_non_rfc3339_timestamps(
    fixed_now: datetime, field: str, value: object
) -> None:
    document = serialize_record(_run(fixed_now))
    document[field] = value
    with pytest.raises(NebulaError) as caught:
        deserialize_run_record(document)
    assert caught.value.code is ErrorCode.STATE_CORRUPT

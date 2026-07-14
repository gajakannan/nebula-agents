from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, TypeAlias
from uuid import UUID

from .enums import (
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
from .errors import ErrorCode, error

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True, slots=True)
class Actor:
    uid: int
    username: str
    role: Role
    display_label: str | None = None


@dataclass(frozen=True, slots=True)
class GateDecision:
    decision: DecisionKind
    reason: str | None
    actor: Actor
    decided_at: datetime
    record_revision: int


@dataclass(frozen=True, slots=True)
class GateSnapshot:
    gate_id: str | None
    status: GateStatus
    evidence_ready: bool
    required_evidence: tuple[str, ...]
    decision: GateDecision | None


@dataclass(frozen=True, slots=True)
class ValidatorResult:
    validator_key: ValidatorKey
    exit_code: int
    duration_ms: int
    summary: str
    artifact_path: str | None
    completed_at: datetime
    command_template: str = ""
    gate_id: str | None = None
    validated_revision: int | None = None
    evidence_digest: str | None = None


@dataclass(frozen=True, slots=True)
class ArtifactObservation:
    relative_path: str
    status: ArtifactStatus
    observed_at: datetime
    size_bytes: int | None


@dataclass(frozen=True, slots=True)
class TranscriptState:
    status: TranscriptStatus
    redaction_status: RedactionStatus
    path: str | None
    preview: str | None
    redaction_findings: int
    failure_reason: str | None = None


@dataclass(frozen=True, slots=True)
class AuditEventSummary:
    sequence: int
    event_type: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class RecoverableRun:
    record: RunRecord
    last_audit_event: AuditEventSummary | None


@dataclass(frozen=True, slots=True)
class RecoveryProjection:
    run_id: str
    recoverable_revision: int | None
    recovery_available: bool
    can_recover: bool
    last_gate: GateSnapshot | None
    last_audit_event: AuditEventSummary | None
    transcript_path: str | None
    recovery_command: str | None


@dataclass(frozen=True, slots=True)
class RunRecord:
    schema_version: str
    revision: int
    run_id: str
    feature_id: str
    story_id: str | None
    provider_key: ProviderKey
    tmux_session: str
    workspace_root: str
    prompt_contract: str
    prompt_action: PromptAction
    status: RunStatus
    owner: Actor
    evidence_root: str | None
    gate: GateSnapshot
    latest_validator: ValidatorResult | None
    artifacts: tuple[ArtifactObservation, ...]
    transcript: TranscriptState
    audit_log_path: str
    last_event_sequence: int
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    schema_version: str
    run_id: str
    sequence: int
    event_type: str
    occurred_at: datetime
    actor: Actor
    correlation_id: UUID
    payload: Mapping[str, JsonValue]


@dataclass(frozen=True, slots=True)
class Probe:
    key: str
    status: str
    executable_path: str | None = None
    version: str | None = None
    remediation_category: str | None = None


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    key: str
    status: str
    message: str


@dataclass(frozen=True, slots=True)
class PreflightResult:
    schema_version: str
    probed_at: datetime
    workspace_root: str
    runtime_dir: str
    prompt_contract_path: str | None
    overall_status: str
    tmux: Probe
    providers: tuple[Probe, ...]
    checks: tuple[PreflightCheck, ...]
    planning_docs_path: str | None = None
    missing_paths: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProcessResult:
    argv0: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class LaunchDescriptor:
    schema_version: str
    run_id: str
    provider_key: ProviderKey
    executable_path: str
    argv: tuple[str, ...]
    cwd: str
    inherited_env_names: tuple[str, ...]
    owner_uid: int
    correlation_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class LaunchRequest:
    feature_id: str
    story_id: str | None
    provider_key: ProviderKey
    prompt_action: PromptAction
    requested_run_id: str | None = None
    run_label: str | None = None
    transcript_enabled: bool = False
    expected_revision: int | None = None


@dataclass(frozen=True, slots=True)
class GateDecisionRequest:
    run_id: str
    gate_id: str
    decision: DecisionKind
    reason: str | None
    display_label: str | None
    expected_revision: int
    confirmed: bool = False


@dataclass(frozen=True, slots=True)
class AuthorizationResource:
    workspace_root: str
    owner_uid: int | None = None
    run_id: str | None = None


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    validator_key: ValidatorKey | None = None
    decision: DecisionKind | None = None


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allowed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class TranscriptProjection:
    run_id: str
    status: TranscriptStatus
    redaction_status: RedactionStatus
    preview: str | None
    path: str | None
    truncated: bool


@dataclass(frozen=True, slots=True)
class EvidenceReconciliation:
    evidence_root: str | None
    artifacts: tuple[ArtifactObservation, ...]
    gate: GateSnapshot
    error_category: str | None = None


@dataclass(frozen=True, slots=True)
class RunProjection:
    schema_version: str
    revision: int
    run_id: str
    feature_id: str
    story_id: str | None
    provider_key: ProviderKey
    prompt_action: PromptAction
    status: RunStatus
    owner: Actor
    gate: GateSnapshot
    latest_validator: ValidatorResult | None
    artifacts: tuple[ArtifactObservation, ...]
    transcript: TranscriptState
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None
    tmux_session: str | None
    workspace_root: str | None
    prompt_contract: str | None
    evidence_root: str | None
    audit_log_path: str | None
    can_attach: bool
    can_recover: bool
    recovery_available: bool
    can_decide_gate: bool
    can_configure_transcript: bool


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_value(value: Any) -> JsonValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime):
        return _utc_text(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: _json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    raise TypeError(f"Unsupported JSON value type: {type(value).__name__}")


def serialize_record(value: object) -> dict[str, JsonValue]:
    document = _json_value(value)
    if not isinstance(document, dict):
        raise TypeError("record serialization must produce an object")
    return document


def _datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an RFC 3339 string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _actor(value: Mapping[str, Any]) -> Actor:
    _require_fields(value, {"uid", "username", "role", "display_label"}, "actor")
    return Actor(int(value["uid"]), str(value["username"]), Role(value["role"]), value.get("display_label"))


def _require_fields(value: Mapping[str, Any], allowed: set[str], name: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{name} contains unsupported fields")


def deserialize_run_record(document: Mapping[str, Any]) -> RunRecord:
    try:
        _require_fields(document, {
            "schema_version", "revision", "run_id", "feature_id", "story_id", "provider_key",
            "tmux_session", "workspace_root", "prompt_contract", "prompt_action", "status", "owner",
            "evidence_root", "gate", "latest_validator", "artifacts", "transcript", "audit_log_path",
            "last_event_sequence", "created_at", "updated_at", "last_seen_at",
        }, "run record")
        version = str(document["schema_version"])
        if version.split(".", 1)[0] != "1":
            raise error(ErrorCode.SCHEMA_UNSUPPORTED, "Unsupported run schema version", "state-io", "Upgrade the runtime.")
        gate_doc = document["gate"]
        _require_fields(gate_doc, {"gate_id", "status", "evidence_ready", "required_evidence", "decision"}, "gate")
        decision_doc = gate_doc.get("decision")
        decision = None
        if decision_doc is not None:
            _require_fields(decision_doc, {"decision", "reason", "actor", "decided_at", "record_revision"}, "gate decision")
            decision = GateDecision(
                DecisionKind(decision_doc["decision"]),
                decision_doc.get("reason"),
                _actor(decision_doc["actor"]),
                _datetime(decision_doc["decided_at"], "decided_at"),
                int(decision_doc["record_revision"]),
            )
        latest_doc = document.get("latest_validator")
        latest = None
        if latest_doc is not None:
            _require_fields(latest_doc, {
                "validator_key", "exit_code", "duration_ms", "summary", "artifact_path", "completed_at",
                "command_template", "gate_id", "validated_revision", "evidence_digest",
            }, "validator")
            latest = ValidatorResult(
                ValidatorKey(latest_doc["validator_key"]),
                int(latest_doc["exit_code"]),
                int(latest_doc["duration_ms"]),
                str(latest_doc["summary"]),
                latest_doc.get("artifact_path"),
                _datetime(latest_doc["completed_at"], "completed_at"),
                str(latest_doc.get("command_template", "")),
                latest_doc.get("gate_id"),
                int(latest_doc["validated_revision"]) if latest_doc.get("validated_revision") is not None else None,
                latest_doc.get("evidence_digest"),
            )
        artifacts = tuple(
            ArtifactObservation(
                str(item["relative_path"]),
                ArtifactStatus(item["status"]),
                _datetime(item["observed_at"], "observed_at"),
                item.get("size_bytes"),
            )
            for item in document.get("artifacts", [])
        )
        for item in document.get("artifacts", []):
            _require_fields(item, {"relative_path", "status", "observed_at", "size_bytes"}, "artifact")
        transcript_doc = document["transcript"]
        _require_fields(transcript_doc, {"status", "redaction_status", "path", "preview", "redaction_findings", "failure_reason"}, "transcript")
        return RunRecord(
            schema_version=version,
            revision=int(document["revision"]),
            run_id=str(document["run_id"]),
            feature_id=str(document["feature_id"]),
            story_id=document.get("story_id"),
            provider_key=ProviderKey(document["provider_key"]),
            tmux_session=str(document["tmux_session"]),
            workspace_root=str(document["workspace_root"]),
            prompt_contract=str(document["prompt_contract"]),
            prompt_action=PromptAction(document["prompt_action"]),
            status=RunStatus(document["status"]),
            owner=_actor(document["owner"]),
            evidence_root=document.get("evidence_root"),
            gate=GateSnapshot(
                gate_doc.get("gate_id"), GateStatus(gate_doc["status"]), bool(gate_doc["evidence_ready"]),
                tuple(str(item) for item in gate_doc.get("required_evidence", [])), decision,
            ),
            latest_validator=latest,
            artifacts=artifacts,
            transcript=TranscriptState(
                TranscriptStatus(transcript_doc["status"]),
                RedactionStatus(transcript_doc["redaction_status"]),
                transcript_doc.get("path"), transcript_doc.get("preview"),
                int(transcript_doc["redaction_findings"]),
                transcript_doc.get("failure_reason"),
            ),
            audit_log_path=str(document["audit_log_path"]),
            last_event_sequence=int(document["last_event_sequence"]),
            created_at=_datetime(document["created_at"], "created_at"),
            updated_at=_datetime(document["updated_at"], "updated_at"),
            last_seen_at=_datetime(document["last_seen_at"], "last_seen_at") if document.get("last_seen_at") else None,
        )
    except NebulaError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise error(ErrorCode.STATE_CORRUPT, "Run state is malformed", "state-io", "Recover the run from its audit history.") from exc


# Avoid an import cycle in the deserializer while preserving the public exception type.
from .errors import NebulaError  # noqa: E402

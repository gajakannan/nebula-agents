"""Stable machine and human output for the local cockpit."""

from __future__ import annotations

import dataclasses
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

CONTRACT_VERSION = "1.0"
MAX_LIST_RECORDS = 100

_ANSI_ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")


def utc_timestamp(value: datetime | None = None) -> str:
    """Return a normalized RFC 3339 UTC timestamp."""

    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    normalized = current.astimezone(timezone.utc).isoformat(timespec="seconds")
    return normalized.replace("+00:00", "Z")


def clean_text(value: object, *, single_line: bool = False) -> str:
    """Remove terminal/control framing without exposing or interpreting it."""

    text = _ANSI_ESCAPE.sub("", str(value))
    cleaned: list[str] = []
    for character in text:
        if character in "\n\r\t":
            cleaned.append(" " if single_line else character)
        elif unicodedata.category(character) not in {"Cc", "Cf", "Cs"}:
            cleaned.append(character)
    return "".join(cleaned)


def to_data(value: Any) -> Any:
    """Convert records to JSON-compatible values without importing the domain."""

    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Enum):
        return to_data(value.value)
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, datetime):
        return utc_timestamp(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (UUID, Path)):
        return str(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: to_data(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, Mapping):
        return {str(key): to_data(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [to_data(item) for item in value]
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return to_data(value.to_dict())
    if hasattr(value, "__dict__"):
        return {
            str(key): to_data(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    return clean_text(value)


def recovery_view_data(candidate: object) -> dict[str, Any]:
    """Normalize an application-owned recovery projection for all surfaces."""

    document = to_data(candidate)
    if not isinstance(document, Mapping) or not document.get("run_id"):
        return {}
    result = dict(document)
    result["is_recovery_candidate"] = True
    result["status"] = "Corrupt"
    result.setdefault("provider_key", "-")
    result.setdefault("feature_id", "-")
    result.setdefault("story_id", None)
    result.setdefault("tmux_session", None)
    result.setdefault("can_attach", False)
    result.setdefault("can_decide_gate", False)
    result.setdefault("can_configure_transcript", False)
    result["revision"] = result.get("recoverable_revision")
    last_gate = result.get("last_gate")
    result["gate"] = last_gate if isinstance(last_gate, Mapping) else {"status": "Unknown"}
    transcript_path = result.get("transcript_path")
    result["transcript"] = {
        "status": "Unknown",
        "path": transcript_path,
    }
    last_event = result.get("last_audit_event")
    if isinstance(last_event, Mapping):
        result.setdefault("updated_at", last_event.get("occurred_at"))
    return result


def success_envelope(command: str, data: object, *, generated_at: datetime | None = None) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "command": clean_text(command, single_line=True),
        "generated_at": utc_timestamp(generated_at),
        "data": to_data(data),
    }


def error_envelope(
    command: str,
    *,
    code: object,
    message: object,
    category: object,
    details: object,
    remediation: object,
    correlation_id: object,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "command": clean_text(command, single_line=True),
        "generated_at": utc_timestamp(generated_at),
        "error": {
            "code": _enum_text(code),
            "message": clean_text(message, single_line=True),
            "category": _enum_text(category),
            "details": to_data(details) if details is not None else [],
            "remediation": clean_text(remediation, single_line=True),
            "correlation_id": clean_text(correlation_id, single_line=True),
        },
    }


def render_json(document: Mapping[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def render_success_table(command: str, data: object, *, width: int = 120) -> str:
    """Render a deterministic accessible view over the same machine data."""

    document = to_data(data)
    if command == "sessions":
        records = _records_from(document)
        return _render_records(
            records,
            ("run_id", "feature_id", "provider_key", "status", "gate", "updated_at"),
            width=width,
        )
    if command == "evidence":
        artifacts = document if isinstance(document, list) else _find_list(document, ("artifacts", "observations", "evidence"))
        return _render_records(
            artifacts,
            ("relative_path", "status", "size_bytes", "observed_at"),
            width=width,
        )
    if command == "doctor":
        return _render_doctor(document, width=width)
    if command in {"status", "recover"} and isinstance(document, Mapping):
        return _render_status(document, width=width)
    if command == "launch" and isinstance(document, Mapping):
        return _render_launch(document, width=width)
    if command == "validate" and isinstance(document, Mapping):
        return _render_validator(document, width=width)
    if isinstance(document, list):
        return _render_records(document[:MAX_LIST_RECORDS], (), width=width)
    if isinstance(document, Mapping):
        return _render_detail(document, width=width)
    return clean_text(document, single_line=False) + "\n"


def render_error_table(document: Mapping[str, Any]) -> str:
    error = document.get("error", {})
    if not isinstance(error, Mapping):
        return "[ERROR] An internal error occurred.\n"
    lines = [f"[ERROR] {_cell(error.get('code', 'ERROR'))}: {_cell(error.get('message', 'Command failed.'))}"]
    details = error.get("details", [])
    if isinstance(details, list):
        for detail in details[:10]:
            if isinstance(detail, Mapping):
                rendered = ", ".join(f"{_cell(key)}={_cell(value)}" for key, value in detail.items())
                if rendered:
                    lines.append(f"Details: {rendered}")
    remediation = _cell(error.get("remediation", ""))
    if remediation:
        lines.append(f"Remediation: {remediation}")
    correlation_id = _cell(error.get("correlation_id", ""))
    if correlation_id:
        lines.append(f"Correlation: {correlation_id}")
    return "\n".join(lines) + "\n"


def status_marker(value: object) -> str:
    text = _cell(value)
    normalized = text.lower().replace("_", "").replace("-", "")
    if normalized in {"ready", "active", "available", "approved", "passed", "completed", "ok", "success", "0"}:
        return f"[OK] {text}"
    if normalized in {"failed", "blocked", "denied", "missing", "malformed", "stale", "held", "error"}:
        return f"[!] {text}"
    return f"[?] {text}"


def _enum_text(value: object) -> str:
    if isinstance(value, Enum):
        value = value.value
    return clean_text(value, single_line=True)


def _cell(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, Mapping):
        if "status" in value:
            return status_marker(value["status"])
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if isinstance(value, list):
        return ", ".join(_cell(item) for item in value)
    return clean_text(value, single_line=True)


def _records_from(document: Any) -> list[Mapping[str, Any]]:
    if isinstance(document, list):
        records = document
    elif isinstance(document, Mapping):
        records = _find_list(document, ("sessions", "runs", "items", "records"))
    else:
        records = []
    return [item for item in records[:MAX_LIST_RECORDS] if isinstance(item, Mapping)]


def _find_list(document: Any, keys: tuple[str, ...]) -> list[Any]:
    if not isinstance(document, Mapping):
        return []
    for key in keys:
        value = document.get(key)
        if isinstance(value, list):
            return value[:MAX_LIST_RECORDS]
    return []


def _lookup(record: Mapping[str, Any], key: str) -> Any:
    value = record.get(key)
    if key == "gate" and isinstance(value, Mapping):
        return value.get("status")
    return value


def _render_records(records: list[Any], columns: tuple[str, ...], *, width: int) -> str:
    mappings = [record for record in records if isinstance(record, Mapping)][:MAX_LIST_RECORDS]
    if not mappings:
        return "No records.\n"
    selected = list(columns) if columns else list(mappings[0].keys())[:6]
    headers = [column.replace("_", " ").upper() for column in selected]
    rows = [[_cell(_lookup(record, column)) for column in selected] for record in mappings]
    return _table(headers, rows, width=width)


def _render_detail(document: Mapping[str, Any], *, width: int) -> str:
    rows: list[list[str]] = []
    for key, value in document.items():
        if isinstance(value, Mapping):
            rows.append([key.replace("_", " "), _cell(value)])
        elif isinstance(value, list):
            rows.append([key.replace("_", " "), f"{len(value)} item(s)"])
        else:
            display = status_marker(value) if key.endswith("status") or key == "status" else _cell(value)
            rows.append([key.replace("_", " "), display])
    return _table(["FIELD", "VALUE"], rows, width=width)


def _render_doctor(document: Any, *, width: int) -> str:
    if not isinstance(document, Mapping):
        return _cell(document) + "\n"
    rows: list[list[str]] = []
    overall = document.get("overall_status")
    if overall is not None:
        rows.append(["overall", status_marker(overall), ""])
    rows.extend(
        [
            ["workspace root", _path_status(document.get("workspace_root")), _cell(document.get("workspace_root"))],
            ["planning docs", _path_status(document.get("planning_docs_path")), _cell(document.get("planning_docs_path"))],
            ["runtime directory", _path_status(document.get("runtime_dir")), _cell(document.get("runtime_dir"))],
            ["prompt contract", _path_status(document.get("prompt_contract_path")), _cell(document.get("prompt_contract_path"))],
        ]
    )
    tmux = document.get("tmux")
    if isinstance(tmux, Mapping):
        rows.extend(
            [
                ["tmux", status_marker(tmux.get("status", "unknown")), _cell(tmux.get("version"))],
                ["tmux executable", _path_status(tmux.get("executable_path")), _cell(tmux.get("executable_path"))],
            ]
        )
    providers = document.get("providers", [])
    if isinstance(providers, list):
        for provider in providers[:MAX_LIST_RECORDS]:
            if isinstance(provider, Mapping):
                rows.append([
                    _cell(provider.get("key", "provider")),
                    status_marker(provider.get("status", "unknown")),
                    _cell(provider.get("version")),
                ])
                rows.append([
                    f"{_cell(provider.get('key', 'provider'))} executable",
                    _path_status(provider.get("executable_path")),
                    _cell(provider.get("executable_path")),
                ])
    checks = document.get("checks", [])
    if isinstance(checks, list):
        for check in checks[:MAX_LIST_RECORDS]:
            if isinstance(check, Mapping):
                rows.append([
                    _cell(check.get("key", "check")),
                    status_marker(check.get("status", "unknown")),
                    _cell(check.get("message")),
                ])
    path_rows = [
        ("workspace root", document.get("workspace_root")),
        ("planning docs", document.get("planning_docs_path")),
        ("runtime directory", document.get("runtime_dir")),
        ("prompt contract", document.get("prompt_contract_path")),
    ]
    if isinstance(tmux, Mapping):
        path_rows.append(("tmux executable", tmux.get("executable_path")))
    if isinstance(providers, list):
        path_rows.extend(
            (f"{_cell(provider.get('key', 'provider'))} executable", provider.get("executable_path"))
            for provider in providers[:MAX_LIST_RECORDS]
            if isinstance(provider, Mapping)
        )
    missing_paths = document.get("missing_paths", [])
    if isinstance(missing_paths, list):
        path_rows.extend(("missing path", path) for path in missing_paths[:MAX_LIST_RECORDS])
    exact_paths = ["", "PATHS"]
    exact_paths.extend(f"{label}: {_cell(path)}" for label, path in path_rows)
    return _table(["CHECK", "STATUS", "DETAIL"], rows, width=width) + "\n".join(exact_paths) + "\n"


def _path_status(value: object) -> str:
    return status_marker("available" if value else "missing")


def _render_launch(document: Mapping[str, Any], *, width: int) -> str:
    rendered = _render_detail(document, width=width)
    run_id = _cell(document.get("run_id"))
    if not run_id or run_id == "-":
        return rendered
    return (
        rendered
        + "\nNext steps:\n"
        + f"  nebula-agents tui --run-id {run_id}\n"
        + f"  nebula-agents attach --run-id {run_id}\n"
    )


def _render_status(document: Mapping[str, Any], *, width: int) -> str:
    gate = document.get("gate", {})
    gate_status = gate.get("status", "Unknown") if isinstance(gate, Mapping) else "Unknown"
    transcript = document.get("transcript", {})
    validator = document.get("latest_validator", {})
    recovery_available = document.get("recovery_available") is True
    can_recover = document.get("can_recover") is True
    rows: list[list[str]] = [
        ["run", _cell(document.get("run_id"))],
        ["feature / story", f"{_cell(document.get('feature_id'))} / {_cell(document.get('story_id'))}"],
        ["provider", _cell(document.get("provider_key"))],
        ["status", status_marker(document.get("status", "Unknown"))],
        ["gate", status_marker(gate_status)],
        ["revision", _cell(document.get("revision"))],
        ["recovery status", "available" if recovery_available else "not available"],
        ["recovery action", "allowed" if can_recover and recovery_available else "unavailable"],
    ]
    last_gate = document.get("last_gate", gate)
    if isinstance(last_gate, Mapping):
        gate_summary = " / ".join(
            item
            for item in (_cell(last_gate.get("gate_id")), _cell(last_gate.get("status")))
            if item != "-"
        )
        if gate_summary:
            rows.append(["last gate", gate_summary])
    elif last_gate is not None:
        rows.append(["last gate", _cell(last_gate)])
    last_event = document.get("last_audit_event")
    if last_event is not None:
        rows.append(["last audit event", _audit_event_summary(last_event)])
    if document.get("recovery_command"):
        rows.append(["recovery command", _cell(document.get("recovery_command"))])
    if document.get("can_attach") is True and document.get("run_id"):
        rows.append(["attach", f"nebula-agents attach --run-id {_cell(document['run_id'])}"])
    if isinstance(validator, Mapping):
        rows.extend(
            [
                ["validator command", _cell(validator.get("command_template"))],
                ["validator exit", _cell(validator.get("exit_code"))],
                ["validator summary", _cell(validator.get("summary"))],
            ]
        )
    if isinstance(transcript, Mapping):
        rows.extend(
            [
                ["transcript", status_marker(transcript.get("status", "Unknown"))],
                ["redaction", _cell(transcript.get("redaction_status"))],
                ["redaction findings", _cell(transcript.get("redaction_findings"))],
            ]
        )
        if transcript.get("path"):
            rows.append(["transcript path", _cell(transcript.get("path"))])
        if transcript.get("failure_reason"):
            rows.append(["transcript failure", _cell(transcript.get("failure_reason"))])
    elif document.get("transcript_path"):
        rows.append(["transcript path", _cell(document.get("transcript_path"))])
    rows.extend(
        [
            ["updated", _cell(document.get("updated_at"))],
            ["last seen", _cell(document.get("last_seen_at"))],
        ]
    )
    return _table(["FIELD", "VALUE"], rows, width=width)


def _audit_event_summary(value: object) -> str:
    if not isinstance(value, Mapping):
        return _cell(value)
    event_type = value.get("event_type", value.get("type"))
    sequence = value.get("sequence")
    occurred_at = value.get("occurred_at", value.get("timestamp"))
    parts = []
    if sequence is not None:
        parts.append(f"#{_cell(sequence)}")
    if event_type is not None:
        parts.append(_cell(event_type))
    if occurred_at is not None:
        parts.append(_cell(occurred_at))
    return " ".join(parts) or "-"


def _render_validator(document: Mapping[str, Any], *, width: int) -> str:
    validator = document.get("latest_validator", document)
    if not isinstance(validator, Mapping):
        return "No validator result.\n"
    rows = [
        ["command", _cell(validator.get("command_template"))],
        ["validator", _cell(validator.get("validator_key"))],
        ["exit", _cell(validator.get("exit_code"))],
        ["summary", _cell(validator.get("summary"))],
        ["completed", _cell(validator.get("completed_at"))],
    ]
    if validator.get("artifact_path"):
        rows.append(["artifact", _cell(validator.get("artifact_path"))])
    return _table(["VALIDATOR RESULT", "VALUE"], rows, width=width)


def _table(headers: list[str], rows: list[list[str]], *, width: int) -> str:
    if not rows:
        return "No records.\n"
    column_count = len(headers)
    normalized = [[_cell(value) for value in row[:column_count]] for row in rows]
    minimums = [max(3, len(header)) for header in headers]
    maximum = max(12, min(48, max(width, 40) // max(column_count, 1)))
    column_widths = []
    for index, minimum in enumerate(minimums):
        content_width = max((len(row[index]) if index < len(row) else 0 for row in normalized), default=0)
        column_widths.append(min(max(minimum, content_width), maximum))

    def line(values: list[str]) -> str:
        cells = []
        for index, cell in enumerate(values):
            clipped = cell if len(cell) <= column_widths[index] else cell[: max(column_widths[index] - 1, 1)] + "…"
            cells.append(clipped.ljust(column_widths[index]))
        return "  ".join(cells).rstrip()

    separator = "  ".join("-" * item for item in column_widths)
    output = [line(headers), separator]
    output.extend(line(row + [""] * (column_count - len(row))) for row in normalized)
    return "\n".join(output) + "\n"

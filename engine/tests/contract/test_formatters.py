from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from nebula_agents.domain.enums import Role
from nebula_agents.domain.errors import ErrorCode
from nebula_agents.domain.models import Actor
from nebula_agents.presentation.formatters import (
    clean_text,
    error_envelope,
    render_error_table,
    render_json,
    render_success_table,
    success_envelope,
    to_data,
)


NOW = datetime(2026, 7, 13, 18, 0, tzinfo=UTC)
CORRELATION_ID = UUID("6fddeba4-7f25-4bf1-a298-70c095235f4f")


def test_success_envelope_is_stable_json_contract() -> None:
    actor = Actor(1000, "operator", Role.LOCAL_OPERATOR, None)
    envelope = success_envelope("status", actor, generated_at=NOW)
    assert envelope == {
        "contract_version": "1.0",
        "command": "status",
        "generated_at": "2026-07-13T18:00:00Z",
        "data": {
            "uid": 1000,
            "username": "operator",
            "role": "LocalOperator",
            "display_label": None,
        },
    }
    assert json.loads(render_json(envelope)) == envelope


def test_error_envelope_and_table_strip_terminal_controls() -> None:
    envelope = error_envelope(
        "launch\x00",
        code=ErrorCode.PREFLIGHT_BLOCKED,
        message="blocked\x1b[31mSECRETISH\x1b[0m\nnext",
        category="preflight",
        details=[{"check": "provider\x00"}],
        remediation="login\rthen retry",
        correlation_id=CORRELATION_ID,
        generated_at=NOW,
    )
    serialized = render_json(envelope)
    table = render_error_table(envelope)
    assert "\x00" not in serialized
    assert "\x1b" not in serialized
    assert "\nnext" not in envelope["error"]["message"]
    assert "[ERROR] PREFLIGHT_BLOCKED" in table
    assert str(CORRELATION_ID) in table


def test_table_and_json_are_projections_of_same_session_data() -> None:
    sessions = {
        "sessions": [
            {
                "run_id": "2026-07-13-deadbeef",
                "feature_id": "F0001",
                "provider_key": "codex",
                "status": "Active",
                "gate": {"status": "Pending"},
                "updated_at": "2026-07-13T18:00:00Z",
            }
        ]
    }
    machine = success_envelope("sessions", sessions, generated_at=NOW)
    table = render_success_table("sessions", sessions, width=120)
    assert "2026-07-13-deadbeef" in table
    assert "F0001" in table
    assert "codex" in table
    assert "Active" in table
    assert machine["data"] == sessions


def test_session_table_bounds_output_at_one_hundred_records() -> None:
    sessions = {
        "sessions": [
            {
                "run_id": f"2026-07-13-{index:08x}",
                "feature_id": "F0001",
                "provider_key": "codex",
                "status": "Active",
                "gate": {"status": "Pending"},
                "updated_at": "2026-07-13T18:00:00Z",
            }
            for index in range(101)
        ]
    }
    table = render_success_table("sessions", sessions, width=160)
    assert "2026-07-13-00000063" in table
    assert "2026-07-13-00000064" not in table


def test_clean_text_removes_osc_and_c0_controls() -> None:
    dirty = "safe\x1b]0;owned\x07 text\x00\x08\x7f"
    assert clean_text(dirty) == "safe text"


def test_to_data_does_not_expose_private_attributes() -> None:
    class Projection:
        def __init__(self) -> None:
            self.visible = "yes"
            self._secret = "no"

    assert to_data(Projection()) == {"visible": "yes"}

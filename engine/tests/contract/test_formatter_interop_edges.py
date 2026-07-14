from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from nebula_agents.domain.enums import PromptAction, ProviderKey, Role
from nebula_agents.domain.models import Actor
from nebula_agents.presentation import formatters
from nebula_agents.presentation.formatters import render_error_table, render_success_table, status_marker, to_data
from nebula_agents.presentation.interop import IntegrationError, current_actor, invoke, launch_request


ACTOR = Actor(1000, "operator", Role.LOCAL_OPERATOR)


@dataclass
class Record:
    when: datetime
    path: Path


def test_to_data_covers_temporal_path_sequence_protocol_and_fallback_values() -> None:
    identifier = UUID("6fddeba4-7f25-4bf1-a298-70c095235f4f")

    class DictProjection:
        def to_dict(self) -> dict[str, object]:
            return {"day": date(2026, 7, 13), "values": (ProviderKey.CODEX, identifier)}

    class Opaque:
        __slots__ = ()

        def __str__(self) -> str:
            return "opaque\x00value"

    assert to_data(datetime(2026, 7, 13, 18, 0)) == "2026-07-13T18:00:00Z"
    assert to_data(date(2026, 7, 13)) == "2026-07-13"
    assert to_data(Path("relative/path")) == "relative/path"
    assert to_data(Record(datetime(2026, 7, 13, 18, 0), Path("run.json"))) == {
        "when": "2026-07-13T18:00:00Z",
        "path": "run.json",
    }
    assert to_data(DictProjection()) == {
        "day": "2026-07-13",
        "values": ["codex", str(identifier)],
    }
    assert to_data(Opaque()) == "opaquevalue"


def test_success_rendering_handles_evidence_doctor_generic_and_scalar_shapes() -> None:
    evidence = [
        {"relative_path": "test-results.md", "status": "Available", "size_bytes": 12, "observed_at": "now"}
    ]
    assert "test-results.md" in render_success_table("evidence", evidence)

    doctor = {
        "overall_status": "Ready",
        "tmux": {"status": "Available", "version": "tmux 3.5"},
        "providers": [{"key": "codex", "status": "Missing", "version": None}, "ignored"],
        "checks": [{"key": "workspace", "status": "Passed", "message": "valid"}, 42],
    }
    rendered = render_success_table("doctor", doctor)
    assert "[OK] Ready" in rendered
    assert "tmux 3.5" in rendered
    assert "[!] Missing" in rendered
    assert "workspace" in rendered
    assert render_success_table("doctor", "unavailable") == "unavailable\n"

    generic = render_success_table("custom", [{"very_long_field": "x" * 80, "flag": True}], width=40)
    assert "xxxxxxxxxxxxxxxxxxx…" in generic
    assert "yes" in generic
    detail = render_success_table("custom", {"status": "Held", "gate": {"status": "Pending"}, "items": [1, 2]})
    assert "[!] Held" in detail
    assert "[?] Pending" in detail
    assert "2 item(s)" in detail
    assert render_success_table("custom", 7) == "7\n"


def test_doctor_human_output_exposes_every_checked_runtime_path() -> None:
    doctor = {
        "overall_status": "ready",
        "workspace_root": "/srv/nebula",
        "planning_docs_path": "/srv/nebula/planning-mds",
        "runtime_dir": "/tmp/nebula-runtime",
        "prompt_contract_path": "/srv/nebula/agents/prompts/feature.md",
        "tmux": {
            "status": "ready",
            "version": "tmux 3.6",
            "executable_path": "/usr/bin/tmux",
        },
        "providers": [
            {
                "key": "codex",
                "status": "ready",
                "version": "0.144.3",
                "executable_path": "/opt/bin/codex",
            }
        ],
        "checks": [],
    }

    rendered = render_success_table("doctor", doctor, width=180)

    for expected in (
        "/srv/nebula",
        "/srv/nebula/planning-mds",
        "/tmp/nebula-runtime",
        "/srv/nebula/agents/prompts/feature.md",
        "/usr/bin/tmux",
        "/opt/bin/codex",
    ):
        assert expected in rendered


def test_launch_human_output_prints_exact_nonautomatic_next_steps() -> None:
    run_id = "2026-07-14-deadbeef"
    rendered = render_success_table(
        "launch",
        {"run_id": run_id, "status": "Active", "provider_key": "codex"},
    )

    assert f"nebula-agents tui --run-id {run_id}" in rendered
    assert f"nebula-agents attach --run-id {run_id}" in rendered
    assert rendered.count("nebula-agents tui --run-id") == 1
    assert rendered.count("nebula-agents attach --run-id") == 1


def test_empty_and_malformed_tables_have_deterministic_accessible_fallbacks() -> None:
    assert render_success_table("sessions", object()) == "No records.\n"
    assert render_success_table("evidence", {"observations": ["invalid"]}) == "No records.\n"
    assert render_success_table("custom", []) == "No records.\n"
    assert render_success_table("custom", {}) == "No records.\n"
    assert render_error_table({"error": "invalid"}) == "[ERROR] An internal error occurred.\n"
    assert status_marker(None) == "[?] -"
    assert status_marker(False) == "[?] no"
    assert status_marker(["ready", "held"]) == "[?] ready, held"


def test_current_actor_resolves_each_supported_composition_shape() -> None:
    assert current_actor(SimpleNamespace(current_actor=lambda: ACTOR)) is ACTOR
    assert current_actor(SimpleNamespace(identity=SimpleNamespace(current_actor=lambda: ACTOR))) is ACTOR
    application = SimpleNamespace(runs=SimpleNamespace(_identity=SimpleNamespace(current_actor=lambda: ACTOR)))
    assert current_actor(application) is ACTOR
    with pytest.raises(IntegrationError, match="current local actor"):
        current_actor(SimpleNamespace())


def test_invoke_filters_optional_values_supports_kwargs_and_reports_missing_bindings() -> None:
    def selected(*, run_id: str, limit: int = 1) -> tuple[str, int]:
        return run_id, limit

    def accepts_all(**kwargs: object) -> dict[str, object]:
        return kwargs

    assert invoke(selected, run_id="run", limit=5, ignored="value") == ("run", 5)
    assert invoke(accepts_all, run_id="run", ignored="value") == {"run_id": "run", "ignored": "value"}
    with pytest.raises(IntegrationError, match="run_id"):
        invoke(selected, limit=2)


def test_launch_request_maps_public_values_to_typed_domain_contract() -> None:
    request = launch_request(
        {
            "feature": "F0001",
            "story": "F0001-S0001",
            "provider": "claude",
            "action": "review",
            "run_id": "2026-07-13-deadbeef",
            "label": "security review",
            "transcript": True,
            "expected_revision": 3,
        }
    )
    assert request.feature_id == "F0001"
    assert request.provider_key is ProviderKey.CLAUDE
    assert request.prompt_action is PromptAction.REVIEW
    assert request.transcript_enabled is True
    assert request.expected_revision == 3

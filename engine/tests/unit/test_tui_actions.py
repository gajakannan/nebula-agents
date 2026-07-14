from __future__ import annotations

from types import SimpleNamespace

from nebula_agents.domain.enums import DecisionKind, Role
from nebula_agents.domain.models import Actor
from nebula_agents.presentation.tui import CockpitUI


def test_confirmed_tui_gate_approval_sets_domain_confirmation_flag() -> None:
    captured: dict[str, object] = {}

    def decide(*, request, actor):
        captured["request"] = request
        captured["actor"] = actor
        return request

    actor = Actor(1000, "operator", Role.LOCAL_OPERATOR)
    application = SimpleNamespace(
        gates=SimpleNamespace(decide=decide),
        current_actor=lambda: actor,
    )
    ui = CockpitUI(application, "2026-07-13-deadbeef")
    ui.state.detail = {
        "revision": 4,
        "gate": {"gate_id": "G4", "status": "Pending", "evidence_ready": True},
        "latest_validator": {"exit_code": 0},
    }
    ui._decide_gate("Approve", None)
    request = captured["request"]
    assert request.decision is DecisionKind.APPROVE
    assert request.expected_revision == 4
    assert request.confirmed is True


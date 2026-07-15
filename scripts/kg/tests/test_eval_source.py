from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "kg"))

import eval as kg_eval  # noqa: E402


def _ev(tool: str, source=None, tokens: int = 0) -> dict:
    e: dict = {"tool": tool, "payload": {"tokens_estimated": tokens}}
    if source is not None:
        e["source"] = source
    return e


def test_groups_mcp_vs_cli() -> None:
    events = [
        _ev("kg_context", source="mcp", tokens=100),
        _ev("kg_hint", source="mcp", tokens=50),
        _ev("lookup", tokens=200),            # no source key -> cli
        _ev("hint", source=None, tokens=10),  # explicit None -> cli
        {"tool": "turn", "payload": {}},       # harness usage turn -> excluded
    ]
    g = kg_eval.retrieval_by_source(events)
    assert set(g) == {"mcp", "cli"}
    assert g["mcp"]["events"] == 2 and g["mcp"]["tokens_estimated"] == 150
    assert g["mcp"]["by_tool"] == {"kg_context": 1, "kg_hint": 1}
    assert g["cli"]["events"] == 2 and g["cli"]["tokens_estimated"] == 210


def test_empty_events() -> None:
    assert kg_eval.retrieval_by_source([]) == {}


def test_render_includes_source_block() -> None:
    base_tel = {"empty_lookup_rate": None, "ambiguous_match_rate": None, "escalation_rate": None,
                "tier_escalation_rate": None, "token_cost_per_successful_run": {"mean": None, "p95": None},
                "tier_vs_outcome": []}
    report = {"commits": [], "node_precision": 0.0, "node_recall": 0.0, "telemetry": base_tel,
              "cache": kg_eval.cache_metrics([]),
              "retrieval_by_source": {"mcp": {"events": 2, "tokens_estimated": 150,
                                              "by_tool": {"kg_context": 2}}}}
    out = kg_eval.render_human(report)
    assert "Retrieval by source:" in out and "mcp:" in out


def test_render_omits_block_when_empty() -> None:
    base_tel = {"empty_lookup_rate": None, "ambiguous_match_rate": None, "escalation_rate": None,
                "tier_escalation_rate": None, "token_cost_per_successful_run": {"mean": None, "p95": None},
                "tier_vs_outcome": []}
    report = {"commits": [], "node_precision": 0.0, "node_recall": 0.0, "telemetry": base_tel,
              "cache": kg_eval.cache_metrics([]), "retrieval_by_source": {}}
    assert "Retrieval by source:" not in kg_eval.render_human(report)

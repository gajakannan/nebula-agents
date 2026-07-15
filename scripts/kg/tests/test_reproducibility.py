"""Tests for reproducibility.py — reproducibility + git-policy enforcement (F0006-S0008)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "kg"))

import reproducibility as repro  # noqa: E402


# ── the gate is green on the committed repo ──
def test_reproducibility_green():
    assert repro.check_reproducible() == []


def test_gitattributes_matches_committed():
    assert repro.check_gitattributes() == []


# ── manifest + .gitattributes generation ──
def test_manifest_shape():
    entries = repro.load_manifest()
    gran = {}
    for e in entries:
        gran[e["granularity"]] = gran.get(e["granularity"], 0) + 1
    assert gran == {"whole-file": 9, "fenced-region": 2}


def test_gitattributes_whole_file_only():
    text = repro.render_gitattributes()
    assert "canonical-nodes.yaml linguist-generated=true merge=ours" in text
    # fenced-region trackers get neither linguist-generated nor the driver
    assert "REGISTRY.md" not in text
    assert "ROADMAP.md" not in text


def test_gitattributes_drift_detected(tmp_path, monkeypatch):
    fake = tmp_path / ".gitattributes"
    fake.write_text("stale\n", encoding="utf-8")
    monkeypatch.setattr(repro, "GITATTRIBUTES", fake)
    assert repro.check_gitattributes(), "expected drift"


# ── enforcement rules ──
def test_binding_glob_rule_green():
    assert repro.rule_binding_glob_matches() == []


def test_archived_no_stale_path_green():
    assert repro.rule_archived_no_stale_path() == []


def test_suppression_rule_flags_missing_rationale(tmp_path, monkeypatch):
    (tmp_path / "exclusions").mkdir()
    (tmp_path / "exclusions" / "suppressions.yaml").write_text(
        "suppressions:\n  - kind: name-similarity\n    ids: [capability:a, capability:b]\n", encoding="utf-8")
    monkeypatch.setattr(repro, "KG_SOURCE", tmp_path)
    errs = repro.rule_suppression_rationale()
    assert errs and "no rationale" in errs[0]


def test_suppression_rule_passes_with_rationale(tmp_path, monkeypatch):
    (tmp_path / "exclusions").mkdir()
    (tmp_path / "exclusions" / "suppressions.yaml").write_text(
        "suppressions:\n  - kind: name-similarity\n    ids: [capability:a, capability:b]\n"
        "    rationale: intentional\n", encoding="utf-8")
    monkeypatch.setattr(repro, "KG_SOURCE", tmp_path)
    assert repro.rule_suppression_rationale() == []


# ── override trailer ──
def test_override_downgrades_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(repro, "check_reproducible", lambda: ["synthetic violation"])
    monkeypatch.setattr(repro, "_override_reason", lambda: "emergency hotfix")
    rc = repro.main([])
    assert rc == 0  # downgraded to a logged warning
    assert "DOWNGRADED by override" in capsys.readouterr().out


def test_no_override_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(repro, "check_reproducible", lambda: ["synthetic violation"])
    monkeypatch.setattr(repro, "_override_reason", lambda: None)
    assert repro.main([]) == 1

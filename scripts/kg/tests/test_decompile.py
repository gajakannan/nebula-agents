"""Tests for decompile.py — decompiler-first migration + round-trip proof (F0006-S0006)."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "kg"))

import compile as kgc  # noqa: E402
import decompile  # noqa: E402

KG_DIR = REPO_ROOT / "planning-mds" / "knowledge-graph"


def _copied_kg(tmp_path: Path) -> Path:
    """Copy the repository's current compiled graph into an isolated test directory."""
    kg = tmp_path / "kg"
    kg.mkdir()
    for f in ("canonical-nodes.yaml", "feature-mappings.yaml", "code-index.yaml", "solution-ontology.yaml"):
        shutil.copy(KG_DIR / f, kg / f)
    return kg


# ── the headline gate: compile(decompile(graph)) == graph, on the REAL graph ──
def test_real_graph_roundtrip_byte_identical(tmp_path):
    kg = _copied_kg(tmp_path)
    src = tmp_path / "kg-source"
    res = decompile.decompile_to(src, kg_dir=kg)
    decompile.write_shards(res, src)
    decompile.verify_roundtrip(src, res, kg_dir=kg)
    assert res.anomalies == [], res.anomalies[:5]
    assert res.roundtrip_drift == [], res.roundtrip_drift
    assert res.ok


def test_counts_reconcile(tmp_path):
    kg = _copied_kg(tmp_path)
    res = decompile.decompile_to(tmp_path / "kg-source", kg_dir=kg)
    report = "\n".join(res.report)
    canonical = yaml.safe_load((kg / "canonical-nodes.yaml").read_text())
    mappings = yaml.safe_load((kg / "feature-mappings.yaml").read_text())
    code_index = yaml.safe_load((kg / "code-index.yaml").read_text())
    node_total = sum(len(v) for v in canonical.values() if isinstance(v, list))
    mapped = len(mappings.get("features", []))
    excluded = len(mappings.get("coverage", {}).get("excluded_features", []))
    stories = len(mappings.get("stories", []))
    bindings = len(code_index.get("node_bindings", []))
    assert f"nodes: {node_total}" in report
    assert f"features: {mapped + excluded} ({mapped} mapped + {excluded} coverage-excluded)" in report
    assert f"stories: {stories}" in report
    assert f"bindings: {bindings}" in report


def test_decompile_idempotent(tmp_path):
    kg = _copied_kg(tmp_path)
    a = decompile.decompile_to(tmp_path / "a", kg_dir=kg).shards
    b = decompile.decompile_to(tmp_path / "b", kg_dir=kg).shards
    assert a == b


def test_logical_ref_rewrite(tmp_path):
    kg = _copied_kg(tmp_path)
    res = decompile.decompile_to(tmp_path / "kg-source", kg_dir=kg)
    # No shard may carry a physical feature-doc path; refs into features are logical F####/…
    for rel, text in res.shards.items():
        if rel.startswith("nodes/") or rel.startswith("policies/"):
            assert "planning-mds/features/" not in text, f"{rel} still has a physical feature path"


def test_ontology_moved_verbatim(tmp_path):
    kg = _copied_kg(tmp_path)
    res = decompile.decompile_to(tmp_path / "kg-source", kg_dir=kg)
    assert res.shards["ontology/solution-ontology.yaml"] == (kg / "solution-ontology.yaml").read_text(encoding="utf-8")


# ── anomaly gate: a node kind with no shard home fails loudly, writes nothing ──
def test_unknown_node_kind_is_anomaly(tmp_path):
    kg = tmp_path / "kg"
    kg.mkdir()
    (kg / "canonical-nodes.yaml").write_text("version: 0\nstatus: seed\nwidgets:\n  - id: widget:x\n", encoding="utf-8")
    (kg / "feature-mappings.yaml").write_text("version: 0\nstatus: seed\nfeatures: []\n", encoding="utf-8")
    (kg / "code-index.yaml").write_text("version: 0\nstatus: seed\nnode_bindings: []\n", encoding="utf-8")
    (kg / "solution-ontology.yaml").write_text("version: 0\n", encoding="utf-8")
    res = decompile.decompile_to(tmp_path / "kg-source", kg_dir=kg)
    assert any("widgets" in a and "no shard-kind home" in a for a in res.anomalies)

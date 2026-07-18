"""Tests for contract-conformance.py (F0007-S0002).

Covers the golden baseline matrix on unchanged policy, independent invariant
failures on seeded weakening (that schema validation would not catch), and
historical-immutability enforcement via the baseline.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "agents" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_action_specs as vas  # noqa: E402


def _load_hyphenated(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cc = _load_hyphenated("contract_conformance", SCRIPTS_DIR / "contract-conformance.py")

REAL_SPEC = REPO_ROOT / "agents" / "actions" / "spec"
REAL_BASELINE = SCRIPTS_DIR / "conformance-baseline.yaml"


def copy_real(dst: Path) -> Path:
    shutil.copytree(REAL_SPEC, dst)
    return dst


def load(dst: Path, name: str) -> dict:
    return yaml.safe_load((dst / name).read_text(encoding="utf-8"))


def dump(dst: Path, name: str, data: dict) -> None:
    (dst / name).write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def rules(result: vas.Result) -> set[str]:
    return {f.rule for f in result.findings}


def test_real_policy_conformant():
    result, report = cc.run_conformance(REAL_SPEC, REAL_BASELINE)
    assert result.ok, [f.as_dict() for f in result.sorted_findings()]
    assert all(r["verdict"] == "pass" for r in report["baseline_matrix"])
    assert len(report["baseline_matrix"]) == 5


def test_removing_g7_artifact_fails_independently(tmp_path):
    # Schema/structure stay valid, but the independent invariant must fire.
    spec_dir = copy_real(tmp_path / "spec")
    spec = load(spec_dir, "feature.yaml")
    g7 = next(g for g in spec["gates"] if g["id"] == "G7")
    g7["artifacts"] = [a for a in g7.get("artifacts", []) if a != "kg-reconciliation.md"]
    dump(spec_dir, "feature.yaml", spec)

    # Structural validation still passes — proves the check is independent.
    struct_result, _ = vas.validate_policy(spec_dir)
    assert struct_result.ok, "spec should remain structurally valid after the weakening edit"

    result, _ = cc.run_conformance(spec_dir, REAL_BASELINE)
    assert not result.ok
    assert "missing_required_gate_artifact" in rules(result)


def test_removing_uuid4_forbid_fails(tmp_path):
    spec_dir = copy_real(tmp_path / "spec")
    contract = load(spec_dir, "_contract.yaml")
    contract["shared"]["run_id_forbidden"] = []
    dump(spec_dir, "_contract.yaml", contract)
    result, _ = cc.run_conformance(spec_dir, REAL_BASELINE)
    assert "run_id_forbidden_missing" in rules(result)


def test_weakening_published_bundle_fails_baseline(tmp_path):
    spec_dir = copy_real(tmp_path / "spec")
    bundle = load(spec_dir, "history/2026-06-01.yaml")
    bundle["shared"]["requirements"]["kg_reconciliation_required"] = False
    dump(spec_dir, "history/2026-06-01.yaml", bundle)
    result, report = cc.run_conformance(spec_dir, REAL_BASELINE)
    assert not result.ok
    found = rules(result)
    assert "baseline_requirements_mismatch" in found
    assert "historical_expectation_changed" in found
    row = next(r for r in report["baseline_matrix"] if r["version"] == "2026-06-01")
    assert row["verdict"] == "fail"


def test_dropping_bundle_artifact_fails_baseline(tmp_path):
    spec_dir = copy_real(tmp_path / "spec")
    bundle = load(spec_dir, "history/2026-07-11.yaml")
    g7 = next(g for g in bundle["actions"]["feature"]["gates"] if g["id"] == "G7")
    g7["required_artifacts"] = []
    dump(spec_dir, "history/2026-07-11.yaml", bundle)
    result, _ = cc.run_conformance(spec_dir, REAL_BASELINE)
    assert "baseline_artifacts_mismatch" in rules(result)


def test_report_is_read_only_and_audited():
    _, report = cc.run_conformance(REAL_SPEC, REAL_BASELINE)
    assert report["audit_log"], "baseline audit log must be surfaced in the report"
    # No secret-bearing content: findings carry rule/path/message only.
    for f in report["findings"]:
        assert set(f) == {"rule", "path", "message"}

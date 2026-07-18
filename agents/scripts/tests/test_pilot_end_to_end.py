"""Governed-pilot rehearsal + rollback immutability (F0007-S0009).

Drives a full run end-to-end through the spec-driven toolchain against a
scaffolded fixture product root — init-run stamps the contract version, run-gate
sequences typed operations and a hashed manual checkpoint, and telemetry is
complete. This is the rehearsal; the LIVE governed product feature run (real
feature spec + product KG scripts + role-owner signoffs) is human-gated.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "agents" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_action_specs as vas  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ir = _load("init_run", SCRIPTS_DIR / "init-run.py")
rg = _load("run_gate", SCRIPTS_DIR / "run-gate.py")
rp = _load("render_prompts", SCRIPTS_DIR / "render-prompts.py")

DRIVER_SPEC = Path(__file__).resolve().parent / "fixtures" / "action-specs" / "driver"
REAL_SPEC_DIR = REPO_ROOT / "agents" / "actions" / "spec"


def test_governed_pilot_rehearsal_reaches_closeout(tmp_path):
    product = tmp_path / "product"
    (product / "planning-mds").mkdir(parents=True)

    # 1) Initialize a version-stamped run (contract version fixed at creation).
    rep = ir.init_run(product_root=product, feature_id="F9999", action="drive", mode="clean",
                      feature_slug="pilot", run_id=None, rerun_of=None, resume=False,
                      force_unlock=False, spec_dir=DRIVER_SPEC)
    assert rep["ok"] and rep["contract_version"] == "2025-02-01"
    run_folder = Path(rep["run_folder"])
    manifest = json.loads((run_folder / "evidence-manifest.json").read_text())
    assert manifest["contract_version"] == "2025-02-01"

    def drive(stage):
        return rg.run_stage(spec_dir=DRIVER_SPEC, action="drive", stage=stage, product_root=product,
                            feature_id="F9999", slug="pilot", run_id=rep["run_id"], run_folder=run_folder)

    # 2) Gate operations run through the driver / shared runtime.
    assert drive("G0")["status"] == "pass"

    # 3) Manual checkpoint pauses; attest with hashed evidence; resume to completion.
    assert drive("G2")["status"] == "paused"
    (run_folder / "note.md").write_text("reviewed by pilot", encoding="utf-8")
    att = rg.attest_checkpoint(spec_dir=DRIVER_SPEC, action="drive", stage="G2", product_root=product,
                               run_id=rep["run_id"], run_folder=run_folder, checkpoint_id="cp-review",
                               evidence=[], actor="pilot", role="product-manager")
    assert att["ok"]
    assert drive("G2")["status"] == "pass"

    # 4) Telemetry is complete and durable.
    commands = [json.loads(line) for line in (run_folder / "commands.log").read_text().splitlines() if line.strip()]
    assert commands and all(c["schema_version"] == 1 for c in commands)
    lifecycle = (run_folder / "lifecycle-gates.log").read_text()
    assert "### G0" in lifecycle and "### G2" in lifecycle
    journal = json.loads((run_folder / "gate-state.json").read_text())
    g2 = journal["stages"]["G2"]
    assert g2["status"] == "completed"
    assert g2["attestations"][0]["checkpoint_id"] == "cp-review"
    assert g2["attestations"][0]["evidence"][0]["sha256"]  # evidence is hashed


def test_inflight_run_cannot_change_contract_version(tmp_path):
    # A run's contract version is fixed at creation; init never restamps a resumed run.
    product = tmp_path / "product"
    (product / "planning-mds").mkdir(parents=True)
    rep = ir.init_run(product_root=product, feature_id="F9999", action="drive", mode="clean",
                      feature_slug="pilot", run_id="2026-07-18-cccccccc", rerun_of=None,
                      resume=False, force_unlock=False, spec_dir=DRIVER_SPEC)
    manifest_path = Path(rep["run_folder"]) / "evidence-manifest.json"
    original = manifest_path.read_text()
    ir.init_run(product_root=product, feature_id="F9999", action="drive", mode="clean",
                feature_slug="pilot", run_id="2026-07-18-cccccccc", rerun_of=None,
                resume=True, force_unlock=False, spec_dir=DRIVER_SPEC)
    assert manifest_path.read_text() == original  # manifest preserved, version unchanged


def test_rollback_preserves_immutable_history(tmp_path, monkeypatch):
    # Rollback is configuration/generated-output based; no tool ever mutates a published bundle.
    spec_dir = tmp_path / "spec"
    shutil.copytree(REAL_SPEC_DIR, spec_dir)
    history = spec_dir / "history"
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in history.glob("*.yaml")}

    monkeypatch.setattr(rp, "GENERATED_DIR", tmp_path / "generated")
    rp.generate(spec_dir, "feature")
    result, _ = vas.validate_policy(spec_dir)
    assert result.ok

    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in history.glob("*.yaml")}
    assert before == after

"""Tests for run-gate.py (F0007-S0005) — the durable gate driver."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "agents" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rg = _load("run_gate", SCRIPTS_DIR / "run-gate.py")
DRIVER_SPEC = Path(__file__).resolve().parent / "fixtures" / "action-specs" / "driver"
RUN_ID = "2026-07-18-aaaaaaaa"


@pytest.fixture()
def env(tmp_path):
    product = tmp_path / "product"
    run_folder = product / "planning-mds" / "operations" / "evidence" / f"F0007-drive/{RUN_ID}"
    run_folder.mkdir(parents=True)
    return product, run_folder


def run(product, run_folder, stage, **kw):
    return rg.run_stage(spec_dir=DRIVER_SPEC, action="drive", stage=stage, product_root=product,
                        feature_id="F0007", slug="drive", run_id=RUN_ID, run_folder=run_folder, **kw)


def journal(run_folder):
    return json.loads((run_folder / "gate-state.json").read_text())


def test_ordered_run_passes_and_journals(env):
    product, rf = env
    verdict = run(product, rf, "G0")
    assert verdict["status"] == "pass"
    assert (rf / "g0.txt").read_text() == "g0"
    assert "r0" in journal(rf)["stages"]["G0"]["completed_operations"]
    assert (rf / "commands.log").exists()
    log = (rf / "lifecycle-gates.log").read_text()
    assert "### G0" in log and "Result: PASS" in log


def test_stops_on_first_failure(env):
    product, rf = env
    verdict = run(product, rf, "G1")
    assert verdict["status"] == "fail"
    assert verdict["failed_step"] == "r1"
    assert verdict["exit_code"] == 1


def test_forbidden_flag_rejected(env):
    product, rf = env
    with pytest.raises(rg.GateDriverError) as exc:
        run(product, rf, "G3")
    assert exc.value.code == "forbidden_flag"


def test_checkpoint_pauses_before_tail(env):
    product, rf = env
    verdict = run(product, rf, "G2")
    assert verdict["status"] == "paused"
    assert verdict["pending_checkpoint"] == "cp-review"
    assert (rf / "counter.txt").read_text() == "x"      # r2a ran once
    assert not (rf / "g2-after.txt").exists()            # r2b did not run


def test_checkpoint_attest_then_resume(env):
    product, rf = env
    run(product, rf, "G2")                                # pause at cp-review
    (rf / "note.md").write_text("reviewed by hand")
    att = rg.attest_checkpoint(spec_dir=DRIVER_SPEC, action="drive", stage="G2",
                               product_root=product, run_id=RUN_ID, run_folder=rf,
                               checkpoint_id="cp-review", evidence=[], actor="pat",
                               role="product-manager", note="ok")
    assert att["ok"] and att["evidence"][0]["path"] == "note.md"
    verdict = run(product, rf, "G2")                      # resume
    assert verdict["status"] == "pass"
    assert (rf / "g2-after.txt").read_text() == "after"
    assert (rf / "counter.txt").read_text() == "x"        # r2a NOT re-run (no duplicate side effect)


def test_from_cannot_skip_unattested_checkpoint(env):
    product, rf = env
    run(product, rf, "G2")                                # pause at cp-review (unattested)
    with pytest.raises(rg.GateDriverError) as exc:
        run(product, rf, "G2", from_op="r2b")             # would jump past cp-review
    assert exc.value.code == "cannot_skip_unattested_checkpoint"


def test_tampered_checkpoint_evidence_rejected(env):
    product, rf = env
    run(product, rf, "G2")
    (rf / "note.md").write_text("original")
    rg.attest_checkpoint(spec_dir=DRIVER_SPEC, action="drive", stage="G2", product_root=product,
                         run_id=RUN_ID, run_folder=rf, checkpoint_id="cp-review", evidence=[],
                         actor="pat", role="product-manager")
    (rf / "note.md").write_text("TAMPERED")               # change after attestation
    with pytest.raises(rg.GateDriverError) as exc:
        run(product, rf, "G2")
    assert exc.value.code == "checkpoint_output_changed"


def test_attest_missing_output_rejected(env):
    product, rf = env
    run(product, rf, "G2")                                # note.md not created
    with pytest.raises(rg.GateDriverError) as exc:
        rg.attest_checkpoint(spec_dir=DRIVER_SPEC, action="drive", stage="G2", product_root=product,
                             run_id=RUN_ID, run_folder=rf, checkpoint_id="cp-review", evidence=[],
                             actor="pat", role="product-manager")
    assert exc.value.code == "checkpoint_output_missing"


def test_stale_journal_version_rejected(env):
    product, rf = env
    (rf / "gate-state.json").write_text(json.dumps({"schema_version": 999, "run_id": RUN_ID, "stages": {}}))
    with pytest.raises(rg.GateDriverError) as exc:
        run(product, rf, "G0")
    assert exc.value.code == "stale_journal_version"


def test_wrong_run_rejected(env):
    product, rf = env
    (rf / "gate-state.json").write_text(json.dumps(
        {"schema_version": 1, "run_id": "2026-01-01-zzzzzzzz", "stages": {}}))
    with pytest.raises(rg.GateDriverError) as exc:
        run(product, rf, "G0")
    assert exc.value.code == "wrong_run"


def test_idempotent_completed_replay(env):
    product, rf = env
    assert run(product, rf, "G4")["status"] == "pass"
    again = run(product, rf, "G4")
    assert again["status"] == "completed" and "idempotent" in again["note"]
    forced = run(product, rf, "G4", force=True)
    assert forced["status"] == "pass"


def test_concurrent_operation_rejected(env):
    product, rf = env
    (rf / rg.LOCK_NAME).write_text("held by another process")
    with pytest.raises(rg.GateDriverError) as exc:
        run(product, rf, "G0", lock_timeout=0.3)
    assert exc.value.code == "concurrent_operation"


def test_dry_run_executes_nothing(env):
    product, rf = env
    verdict = run(product, rf, "G0", dry_run=True)
    assert verdict["status"] == "dry-run"
    assert not (rf / "g0.txt").exists()
    assert not (rf / "gate-state.json").exists()


def test_list_runbook_marks_manual_checkpoint():
    book = rg.list_runbook(DRIVER_SPEC, "drive")
    stages = {s["stage"]: s for s in book["stages"]}
    assert set(stages) == {"G0", "G1", "G2", "G3", "G4", "G5"}
    g2_kinds = [o["kind"] for o in stages["G2"]["operations"]]
    assert any("MANUAL" in k for k in g2_kinds)


def test_write_latest_run_resolves_under_feature_index_root(env):
    # A `write: latest-run.json` op is satisfied only when latest-run.json exists under
    # FEATURE_INDEX_ROOT (where the contract publishes it) — NOT under the run folder.
    product, rf = env

    # Nothing published yet -> the write op pauses for the manual publish.
    verdict = run(product, rf, "G5")
    assert verdict["status"] == "paused"
    assert verdict["pending_write"] == "latest-run.json"

    # Regression: latest-run.json in the RUN FOLDER must not satisfy the op.
    (rf / "latest-run.json").write_text("{}")
    verdict = run(product, rf, "G5")
    assert verdict["status"] == "paused"

    # Published under FEATURE_INDEX_ROOT -> op is idempotently skipped and the stage passes.
    index_root = product / "planning-mds" / "operations" / "evidence" / "features" / "F0007-drive"
    index_root.mkdir(parents=True, exist_ok=True)
    (index_root / "latest-run.json").write_text("{}")
    verdict = run(product, rf, "G5")
    assert verdict["status"] == "pass"

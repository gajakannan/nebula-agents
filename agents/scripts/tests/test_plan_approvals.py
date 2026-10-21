"""Regression coverage for cross-session planning approval lifecycle and scope."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import approval_history as history


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


approve = load("approve_plan", "approve-plan.py")
checker = load("check_plan_approvals", "check-plan-approvals.py")
driver = load("approval_test_driver", "run-gate.py")
OLD = "2026-10-15-1111aaaa"
NEW = "2026-10-17-2222bbbb"
COMPLETION = "2026-10-16-3333cccc"


def manifest(product, rid, *, scope=history.PLAN_SCOPE, status="approved", feature="F0004", **extra):
    path = product / "planning-mds/operations/evidence/runs" / rid / "evidence-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(feature_id=feature, run_id=rid, status=status, **extra)
    if scope is not None:
        data["run_scope"] = scope
    history.atomic_write_json(path, data)
    return path


def evidence(run, checkpoint):
    path = run / f"{checkpoint}.md"
    path.write_text(f"Operator explicitly approved {checkpoint}.")
    return dict(checkpoint_id=checkpoint, actor="operator", role="architect",
                timestamp="2026-10-17T15:00:00+00:00",
                evidence=[dict(path=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())])


def ready(product, phase="A+B", stage="G5"):
    path = manifest(product, NEW, status="in-progress", action="plan", plan_phase=phase)
    run = path.parent
    gates = yaml.safe_load(approve.SPEC.read_text())["gates"]
    states = {g["id"]: dict(status="completed", completed_operations=[], attestations=[]) for g in gates}
    for sid, cp in (("G3", "approve-phase-a"), ("G5", "approve-phase-b")):
        gate = next(g for g in gates if g["id"] == sid)
        states[sid]["attestations"] = [evidence(run, cp)]
        for op in gate["operations"][:-1]:
            kind, body = next(iter(op.items()))
            states[sid]["completed_operations"].append(f"checkpoint:{body['id']}" if kind == "checkpoint" else body["id"])
    states[stage]["status"] = "in-progress"
    history.atomic_write_json(run / "gate-state.json", dict(action="plan", run_id=NEW, stages=states))
    return path


def read(path):
    return json.loads(path.read_text())


def test_rework_supersedes_plans_only_and_preserves_history(tmp_path):
    old = manifest(tmp_path, OLD, approved_by="operator", original_decision="approve-phase-b")
    completion = manifest(tmp_path, COMPLETION, scope=None)  # legacy completion
    current = ready(tmp_path)
    original_completion = completion.read_bytes()
    result = approve.approve(tmp_path, "F0004", NEW, "G5")
    assert result["status"] == "approved"
    assert read(current)["supersedes"] == [OLD]
    assert read(old)["status"] == "superseded"
    assert read(old)["superseded_by"] == NEW
    assert read(old)["original_decision"] == "approve-phase-b"
    assert read(current)["approval"]["actor"] == "operator"
    assert completion.read_bytes() == original_completion
    assert not (tmp_path / "planning-mds/operations/evidence/features").exists()
    snapshot = {p: p.read_bytes() for p in (old, completion, current)}
    approve.approve(tmp_path, "F0004", NEW, "G5")
    assert {p: p.read_bytes() for p in snapshot} == snapshot


@pytest.mark.parametrize("phase,stage,status", [("A", "G3", "approved"), ("A+B", "G3", "pending-phase-b"), ("B", "G5", "approved")])
def test_phase_specific_publication(tmp_path, phase, stage, status):
    old = manifest(tmp_path, OLD)
    path = ready(tmp_path, phase, stage)
    assert approve.approve(tmp_path, "F0004", NEW, stage)["status"] == status
    assert read(old)["status"] == ("approved" if status == "pending-phase-b" else "superseded")
    assert read(path)["status"] == ("in-progress" if status == "pending-phase-b" else "approved")


@pytest.mark.parametrize("defect", ["missing-attestation", "changed-evidence", "failed-prior-stage", "missing-exit-operation", "superseded-run", "wrong-root"])
def test_failed_approval_never_supersedes_existing_plan(tmp_path, defect):
    old = manifest(tmp_path, OLD)
    path = ready(tmp_path)
    journal = path.parent / "gate-state.json"
    data = read(journal)
    if defect == "missing-attestation":
        data["stages"]["G5"]["attestations"] = []
    elif defect == "changed-evidence":
        (path.parent / "approve-phase-b.md").write_text("changed after approval")
    elif defect == "failed-prior-stage":
        data["stages"]["G4"]["status"] = "failed"
    elif defect == "missing-exit-operation":
        data["stages"]["G5"]["completed_operations"].remove("validate-trackers-post-approval")
    elif defect == "superseded-run":
        m = read(path); m["status"] = "superseded"; history.atomic_write_json(path, m)
    else:
        data["project_context"] = {"product_root": str(tmp_path / "another-product")}
    history.atomic_write_json(journal, data)
    before = old.read_bytes()
    with pytest.raises(ValueError):
        approve.approve(tmp_path, "F0004", NEW, "G5")
    assert old.read_bytes() == before
    assert read(path)["status"] != "approved"


def test_interrupted_publication_resumes_without_losing_supersession_links(tmp_path, monkeypatch):
    old = manifest(tmp_path, OLD)
    path = ready(tmp_path)
    real_write = approve.atomic_write_json

    def fail_publish(target, data):
        if data.get("status") == "approved":
            raise OSError("simulated final approval write failure")
        real_write(target, data)

    monkeypatch.setattr(approve, "atomic_write_json", fail_publish)
    with pytest.raises(OSError):
        approve.approve(tmp_path, "F0004", NEW, "G5")
    assert read(old)["status"] == "superseded"
    assert read(path)["status"] == "in-progress"
    assert checker.check(tmp_path, "F0004")["errors"]
    monkeypatch.setattr(approve, "atomic_write_json", real_write)
    approve.approve(tmp_path, "F0004", NEW, "G5")
    assert read(path)["supersedes"] == [OLD]
    assert not checker.check(tmp_path, "F0004")["errors"]


def test_phase_b_allows_gate_decisions_appended_after_phase_a_approval(tmp_path):
    path = ready(tmp_path)
    # Real runs append later gates to the same decisions file; Phase A's
    # historical hash is not the current Phase B approval's hash.
    (path.parent / "approve-phase-a.md").write_text("Phase A approved; Phase B now approved too")
    assert approve.approve(tmp_path, "F0004", NEW, "G5")["status"] == "approved"


def test_review_detects_duplicate_plans_without_mutation(tmp_path):
    paths = [manifest(tmp_path, OLD), manifest(tmp_path, NEW), manifest(tmp_path, COMPLETION, scope=history.FEATURE_SCOPE)]
    before = {p: p.read_bytes() for p in paths}
    result = checker.check(tmp_path, "F0004")
    assert "found 2" in result["errors"][0]
    assert {p: p.read_bytes() for p in paths} == before


def test_review_accepts_independent_completion_and_legacy_superseded_plan(tmp_path):
    manifest(tmp_path, OLD, status="superseded")
    manifest(tmp_path, NEW)
    manifest(tmp_path, COMPLETION, scope=None)
    result = checker.check(tmp_path, "F0004")
    assert result["approved_plan_run_id"] == NEW
    assert result["errors"] == []


def test_review_blocks_missing_approval_and_active_rework(tmp_path):
    manifest(tmp_path, OLD, status="in-progress")
    result = checker.check(tmp_path, "F0004")
    assert any("found 0" in e for e in result["errors"])
    assert any("still active" in e for e in result["errors"])
    manifest(tmp_path, NEW)
    assert any("still active" in e for e in checker.check(tmp_path, "F0004")["errors"])


def test_review_rejects_inconsistent_predecessor_link(tmp_path):
    manifest(tmp_path, OLD, status="superseded")
    manifest(tmp_path, NEW, supersedes=[OLD])
    assert any("inconsistent supersession link" in e for e in checker.check(tmp_path, "F0004")["errors"])


@pytest.mark.parametrize("successor", [OLD, COMPLETION, "2026-10-17-9999eeee"])
def test_review_rejects_cyclic_missing_or_wrong_scope_successor(tmp_path, successor):
    manifest(tmp_path, OLD, status="superseded", superseded_by=successor)
    manifest(tmp_path, NEW)
    manifest(tmp_path, COMPLETION, scope=history.FEATURE_SCOPE)
    assert checker.check(tmp_path, "F0004")["errors"]


def test_corrupt_manifest_does_not_partially_supersede(tmp_path):
    old = manifest(tmp_path, OLD)
    ready(tmp_path)
    broken = manifest(tmp_path, COMPLETION)
    broken.write_text("{")
    with pytest.raises(ValueError, match="cannot parse"):
        approve.approve(tmp_path, "F0004", NEW, "G5")
    assert read(old)["status"] == "approved"


def test_plan_approval_lock_fails_closed(tmp_path):
    path = ready(tmp_path)
    with history.approval_lock(tmp_path, "F0004", history.PLAN_SCOPE):
        with pytest.raises(ValueError, match="approval lock"):
            approve.approve(tmp_path, "F0004", NEW, "G5")
    assert read(path)["status"] == "in-progress"


def test_g5_driver_publishes_only_after_approval_and_exit_checks(tmp_path, monkeypatch):
    """Exercise the real gate driver/finalizer, stubbing only product validators."""
    old = manifest(tmp_path, OLD)
    path = ready(tmp_path)
    journal = read(path.parent / "gate-state.json")
    journal["schema_version"] = 1
    journal["stages"]["G5"] = dict(status="pending", completed_operations=[], attestations=[], pending_checkpoint=None)
    history.atomic_write_json(path.parent / "gate-state.json", journal)
    original = driver.gr.run_operation
    fail_exit = False

    def operation(op, **kwargs):
        if op["run"]["id"] == "approve-plan":
            return original(op, **kwargs)
        failed = fail_exit and op["run"]["id"] == "validate-trackers-post-approval"
        return dict(ok=not failed, exit_code=int(failed), timed_out=False)

    monkeypatch.setattr(driver.gr, "run_operation", operation)
    kwargs = dict(spec_dir=approve.SPEC.parent, action="plan", stage="G5", product_root=tmp_path,
                  feature_id="F0004", slug="example", run_id=NEW, run_folder=path.parent)
    assert driver.run_stage(**kwargs)["status"] == "paused"
    assert read(old)["status"] == "approved"
    (path.parent / "gate-decisions.md").write_text("Operator: approve-phase-b")
    driver.attest_checkpoint(spec_dir=approve.SPEC.parent, action="plan", stage="G5", product_root=tmp_path,
                             run_id=NEW, run_folder=path.parent, checkpoint_id="approve-phase-b",
                             evidence=["gate-decisions.md"], actor="operator", role="architect")
    fail_exit = True
    assert driver.run_stage(**kwargs)["status"] == "fail"
    assert read(old)["status"] == "approved"
    fail_exit = False
    assert driver.run_stage(**kwargs)["status"] == "pass"
    assert read(path)["status"] == "approved"
    assert read(old)["superseded_by"] == NEW


@pytest.mark.parametrize("scope,target", [("feature-set", "F0004,F0005"), ("project", "project")])
def test_review_cli_checks_feature_set_read_only(tmp_path, scope, target):
    features = tmp_path / "planning-mds/features"
    (features / "F0004-example").mkdir(parents=True)
    (features / "F0005-other").mkdir()
    for folder in ("F0004-example", "F0005-other"):
        (features / folder / "PRD.md").write_text("Approved requirements")
    (features / "REGISTRY.md").write_text("| F0004 | Example | Planned | F0004-example/ |\n| F0005 | Other | Planned | F0005-other/ |\n")
    paths = [manifest(tmp_path, OLD), manifest(tmp_path, NEW, feature="F0005")]
    before = {p: p.read_bytes() for p in paths}
    result = subprocess.run([sys.executable, str(SCRIPTS / "check-plan-approvals.py"), "--product-root", str(tmp_path),
                             "--plan-scope", scope, "--target", target], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(json.loads(result.stdout)["features"]) == 2
    assert {p: p.read_bytes() for p in paths} == before


def test_review_driver_blocks_duplicate_approvals_without_project_manifest(tmp_path):
    features = tmp_path / "planning-mds/features"
    (features / "F0004-example").mkdir(parents=True)
    (features / "REGISTRY.md").write_text("| F0004 | Example | Planned | F0004-example/ |\n")
    paths = [manifest(tmp_path, OLD), manifest(tmp_path, NEW)]
    before = {p: p.read_bytes() for p in paths}
    folder = tmp_path / "planning-mds/operations/evidence/runs" / COMPLETION
    folder.mkdir()
    result = driver.run_stage(spec_dir=approve.SPEC.parent, action="plan-review", stage="PR2",
                              product_root=tmp_path, feature_id="F0004", slug="example", run_id=COMPLETION,
                              run_folder=folder, plan_scope="feature", target="F0004")
    assert result["status"] == "fail"
    assert result["failed_step"] == "pr2-check-plan-approvals"
    assert {p: p.read_bytes() for p in paths} == before

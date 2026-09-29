"""Product isolation and required check enforcement at the real gate boundary."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import project_context as ctx
import project_checks as checks

spec = importlib.util.spec_from_file_location("project_test_driver", SCRIPTS / "run-gate.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def write(root, path, content):
    p = root / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


@pytest.fixture
def product(tmp_path):
    root = tmp_path / "product"
    write(root, "planning-mds/BLUEPRINT.md", "# Product\nLocal scope\n")
    write(root, "docs/instructions.md", "Local instruction A\n")
    write(root, "planning-mds/features/REGISTRY.md", "| F0001 | Example | `F0001-example/` |\n| F0002 | Other | `F0002-other/` |\n")
    write(root, "planning-mds/features/F0001-example/PRD.md", "A valid plan\n")
    write(root, "planning-mds/features/F0002-other/PRD.md", "Another plan\n")
    write(root, "scripts/check.py", '''import json, sys
from pathlib import Path
ok = "bad" not in Path("planning-mds/features/F0001-example/PRD.md").read_text()
print(json.dumps({"schema_version":1,"check_id":"example","status":"pass" if ok else "fail","findings":[]}))
sys.exit(0 if ok else 1)
''')
    manifest = {"version": 1, "instructions": [{"path": "docs/instructions.md"}], "checks": [
        {"id": "example", "action": "plan-review", "stage": "PR2", "event": "before_stage_complete",
         "argv": ["python3", "{NEBULA_PRODUCT_ROOT}/scripts/check.py"], "cwd": "product", "timeout_seconds": 2,
         "inputs": ["planning-mds/features/**/*.md", "scripts/*.py"]}]}
    write(root, ctx.MANIFEST, yaml.safe_dump(manifest))
    return root


@pytest.fixture
def policy(tmp_path):
    p = tmp_path / "spec"
    shutil.copytree(ctx.SPEC_DIR, p)
    spec_path = p / "plan-review.yaml"
    data = yaml.safe_load(spec_path.read_text())
    for gate in data["gates"]:
        gate["operations"] = []
    spec_path.write_text(yaml.safe_dump(data))
    return p


def run(root, policy, stage="PR2", **kw):
    folder = root / "planning-mds/operations/evidence/runs/2026-09-06-aabbccdd"
    folder.mkdir(parents=True, exist_ok=True)
    return driver.run_stage(spec_dir=policy, action="plan-review", stage=stage, product_root=root,
                            feature_id="F0001", slug="example", run_id="2026-09-06-aabbccdd", run_folder=folder, **kw)


def test_isolation_and_cwd(product, tmp_path, monkeypatch):
    other = tmp_path / "other"
    shutil.copytree(product, other)
    write(other, "docs/instructions.md", "Local instruction B\n")
    monkeypatch.chdir(tmp_path)
    a = ctx.load_context(product, "plan-review")
    b = ctx.load_context(other, "plan-review")
    assert a["instructions"][-1]["text"] == "Local instruction A\n"
    assert b["instructions"][-1]["text"] == "Local instruction B\n"
    monkeypatch.chdir(product / "docs")
    assert ctx.load_context(product, "plan-review") == a


def test_no_default_product(monkeypatch):
    monkeypatch.delenv("NEBULA_PRODUCT_ROOT", raising=False)
    with pytest.raises(ctx.ProjectError, match="no product is selected"):
        ctx.explicit_root(None)


def test_no_manifest_is_compatible(tmp_path):
    assert ctx.load_context(tmp_path, "plan-review")["checks"] == []


@pytest.mark.parametrize("change", ["version", "unknown", "duplicate", "stage", "missing_instruction"])
def test_invalid_manifest_fails(product, change):
    p = product / ctx.MANIFEST
    data = yaml.safe_load(p.read_text())
    if change == "version": data["version"] = 99
    if change == "unknown": data["override"] = True
    if change == "duplicate": data["checks"] *= 2
    if change == "stage": data["checks"][0]["stage"] = "PR4"
    if change == "missing_instruction": data["instructions"][0]["path"] = "missing.md"
    p.write_text(yaml.safe_dump(data))
    with pytest.raises(ctx.ProjectError):
        ctx.load_context(product, "plan-review")


def test_symlink_escape(product, tmp_path):
    outside = write(tmp_path, "outside.md", "secret")
    (product / "docs/instructions.md").unlink()
    (product / "docs/instructions.md").symlink_to(outside)
    with pytest.raises(ctx.ProjectError, match="inside the product"):
        ctx.load_context(product, "plan-review")


def test_scopes_resolve_every_feature(product):
    assert len(ctx.resolve_scope(product, "feature-set", "F0001,F0002")["features"]) == 2
    assert len(ctx.resolve_scope(product, "project", "project")["features"]) == 2
    with pytest.raises(ctx.ProjectError):
        ctx.resolve_scope(product, "feature", "F9999")


def test_required_failure_blocks_readiness_then_resume(product, policy):
    write(product, "planning-mds/features/F0001-example/PRD.md", "bad plan")
    assert run(product, policy)["status"] == "fail"
    with pytest.raises(ctx.ProjectError, match="lacks a current passing result"):
        run(product, policy, "PR4", force=True)
    write(product, "planning-mds/features/F0001-example/PRD.md", "good plan")
    assert run(product, policy)["status"] == "pass"
    assert run(product, policy, "PR4")["status"] == "pass"
    assert run(product, policy)["status"] == "completed"


def test_changed_input_and_evidence_invalidate_pass(product, policy):
    assert run(product, policy)["status"] == "pass"
    write(product, "planning-mds/features/F0002-other/new.md", "new input")
    with pytest.raises(ctx.ProjectError): run(product, policy, "PR4")
    assert run(product, policy)["status"] == "pass"
    folder = product / "planning-mds/operations/evidence/runs/2026-09-06-aabbccdd"
    journal = json.loads((folder / "gate-state.json").read_text())
    evidence = folder / journal["stages"]["PR2"]["project_checks"]["example"]["evidence"][0]["path"]
    evidence.write_text("tampered")
    with pytest.raises(ctx.ProjectError): run(product, policy, "PR4")


def test_manifest_deletion_cannot_disable_checks(product, policy):
    assert run(product, policy)["status"] == "pass"
    (product / ctx.MANIFEST).unlink()
    with pytest.raises(ctx.ProjectError, match="changed during this run"):
        run(product, policy, "PR4")


def test_dry_run_writes_nothing_and_does_not_execute(product, policy):
    before = {str(p): p.read_bytes() for p in product.rglob("*") if p.is_file()}
    assert run(product, policy, dry_run=True)["status"] == "dry-run"
    after = {str(p): p.read_bytes() for p in product.rglob("*") if p.is_file()}
    assert before == after


@pytest.mark.parametrize("source", ["print('not JSON')", "raise RuntimeError('failed')", "import time; time.sleep(5)",
    "import json; print(json.dumps({'schema_version':1,'check_id':'example','status':'fail','findings':[]}))"])
def test_invalid_output_crash_timeout_and_exit_mismatch_fail(product, policy, source):
    write(product, "scripts/check.py", source)
    assert run(product, policy)["status"] == "fail"
    with pytest.raises(ctx.ProjectError): run(product, policy, "PR4")


def test_framework_failure_is_preserved(product, policy):
    p = policy / "plan-review.yaml"
    data = yaml.safe_load(p.read_text())
    gate = next(g for g in data["gates"] if g["id"] == "PR2")
    gate["operations"] = [{"run": {"id": "core-failure", "argv": [sys.executable, "-c", "raise SystemExit(1)"], "cwd": "product"}}]
    p.write_text(yaml.safe_dump(data))
    result = run(product, policy)
    assert result["status"] == "fail" and result["failed_step"] == "core-failure"


def test_missing_script_fails_without_readiness(product, policy):
    (product / "scripts/check.py").unlink()
    with pytest.raises(ctx.ProjectError): run(product, policy)


def test_argv_metacharacters_are_literal(product, policy):
    p = product / ctx.MANIFEST
    data = yaml.safe_load(p.read_text())
    data["checks"][0]["argv"].append("$(touch injected); echo bad")
    p.write_text(yaml.safe_dump(data))
    assert run(product, policy)["status"] == "pass"
    assert not (product / "injected").exists()


def test_cannot_resume_past_incomplete_core_operation(product, policy):
    p = policy / "plan-review.yaml"
    data = yaml.safe_load(p.read_text())
    gate = next(g for g in data["gates"] if g["id"] == "PR2")
    gate["operations"] = [{"run": {"id": name, "argv": [sys.executable, "-c", "pass"], "cwd": "product"}}
                          for name in ["first", "second"]]
    p.write_text(yaml.safe_dump(data))
    with pytest.raises(driver.GateDriverError, match="skip required framework operation"):
        run(product, policy, from_op="second")


def test_retries_preserve_previous_evidence(product, policy):
    assert run(product, policy)["status"] == "pass"
    folder = product / "planning-mds/operations/evidence/runs/2026-09-06-aabbccdd/artifacts/project-checks"
    previous = {p: p.read_bytes() for p in folder.iterdir()}
    assert run(product, policy, force=True)["status"] == "pass"
    assert len(list(folder.iterdir())) == 6
    assert previous == {p: p.read_bytes() for p in previous}


def test_input_mutation_during_check_cannot_pass(product, policy):
    path = product / "scripts/check.py"
    path.write_text(path.read_text().replace('sys.exit(0 if ok else 1)',
                    'Path("planning-mds/features/F0002-other/PRD.md").write_text("modified")'))
    assert run(product, policy)["status"] == "fail"
    with pytest.raises(ctx.ProjectError):
        run(product, policy, "PR4")


def test_active_plan_cannot_disappear_from_project_scope(product):
    write(product, "planning-mds/features/REGISTRY.md", "| F0001 | Example | Active | `F0001-example/` |\n")
    (product / "planning-mds/features/F0001-example/PRD.md").unlink()
    assert ctx.resolve_scope(product, "project", "project")["features"][0]["id"] == "F0001"


def test_malformed_status_is_a_reported_failure(product, policy):
    write(product, "scripts/check.py", 'print(\'{"schema_version":1,"check_id":"example","status":[],"findings":[]}\')')
    assert run(product, policy)["status"] == "fail"


def test_extension_points_are_in_behavioral_diff(policy):
    data = yaml.safe_load((policy / "plan-review.yaml").read_text())
    model = driver.vas._action_model(data)
    assert model["gates"]["PR2"]["project_checks"] == ["before_stage_complete"]


def test_explicit_product_overrides_inherited_environment(product, policy, monkeypatch):
    monkeypatch.setenv("NEBULA_PRODUCT_ROOT", "/wrong-product")
    path = product / "scripts/check.py"
    path.write_text('import os\nassert os.environ["NEBULA_PRODUCT_ROOT"] == ' + repr(str(product)) + '\n' + path.read_text())
    assert run(product, policy)["status"] == "pass"


def test_conflicting_feature_identity_is_rejected(product, policy):
    with pytest.raises(ctx.ProjectError, match="same feature"):
        run(product, policy, target="F0002")


@pytest.mark.parametrize("scope,target", [("feature", "F0001"), ("feature-set", "F0001,F0002"), ("project", "project")])
def test_ci_cli_pass_failure_and_journal_are_not_review_approval(product, scope, target):
    argv = [sys.executable, str(SCRIPTS / "project_checks.py"), "--product-root", str(product),
            "--plan-scope", scope, "--target", target, "--run-id", "2026-09-07-aabbccdd"]
    result = subprocess.run(argv, cwd=product / "docs", capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] and report["review_approval"] is False
    folder = Path(report["run_folder"])
    assert (folder / "project-check-state.json").is_file()
    assert not (folder / "gate-state.json").exists()
    write(product, "planning-mds/features/F0001-example/PRD.md", "bad plan")
    result = subprocess.run(argv, cwd=product / "docs", capture_output=True, text=True)
    assert result.returncode == 1 and not json.loads(result.stdout)["ok"]
    record = json.loads((folder / "project-check-state.json").read_text())["results"]["example"]
    assert not record["ok"] and all((folder / a["path"]).exists() for a in record["evidence"])


def test_generated_variants_require_product_instruction_loading():
    spec = importlib.util.spec_from_file_location("project_test_renderer", SCRIPTS / "render-prompts.py")
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    action = yaml.safe_load((ctx.SPEC_DIR / "plan-review.yaml").read_text())
    shared = yaml.safe_load((ctx.SPEC_DIR / "_contract.yaml").read_text())["shared"]
    outputs = renderer.render_action(action, shared, "2026-07-11")
    for output in outputs.values():
        assert "project_context.py --product-root {NEBULA_PRODUCT_ROOT} --action plan-review" in output
        assert "before_stage_complete" in output
        assert "resume" in output and "returned" in output

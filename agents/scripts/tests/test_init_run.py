"""Tests for init-run.py (F0007-S0003).

Covers version-stamped happy path, concurrent-creator conflict, resume
idempotency, malformed input / path escape, rollback on failure, and the
JSON audit shape.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
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


ir = _load("init_run", SCRIPTS_DIR / "init-run.py")

SLUG = "spec-driven-orchestration"


def do_init(product_root: Path, **kw):
    params = dict(product_root=product_root, feature_id="F0007", action="feature",
                  mode="clean", feature_slug=SLUG, run_id=None, rerun_of=None,
                  resume=False, force_unlock=False, spec_dir=ir.vas.DEFAULT_SPEC_DIR)
    params.update(kw)
    return ir.init_run(**params)


def test_happy_path_creates_stamped_skeleton(tmp_path):
    report = do_init(tmp_path)
    assert report["ok"]
    run_folder = Path(report["run_folder"])
    assert run_folder.is_dir()
    manifest = json.loads((run_folder / "evidence-manifest.json").read_text())
    assert manifest["contract_version"] == "2026-07-11"
    assert manifest["contract_effective_date"] == "2026-07-11"
    assert manifest["status"] == "draft"
    for base in ("README.md", "action-context.md", "commands.log", "lifecycle-gates.log"):
        assert (run_folder / base).exists()
    assert (run_folder / "artifacts" / "coverage").is_dir()
    assert "evidence-manifest.json" in report["created"]


def test_plan_base_run_does_not_create_feature_index(tmp_path):
    report = do_init(tmp_path, action="plan")
    assert Path(report["run_folder"]).is_dir()
    assert not Path(report["feature_index_root"]).exists()
    assert not (Path(report["run_folder"]).parent / ".F0007.init.lock").exists()


def test_rerun_linkage_recorded(tmp_path):
    report = do_init(tmp_path, rerun_of="2026-01-01-abcdef12")
    manifest = json.loads((Path(report["run_folder"]) / "evidence-manifest.json").read_text())
    assert manifest["rerun_of"] == "2026-01-01-abcdef12"


def test_second_active_run_conflicts(tmp_path):
    do_init(tmp_path)
    with pytest.raises(ir.InitError) as exc:
        do_init(tmp_path)
    assert exc.value.code == 3


def test_plan_base_run_does_not_block_feature_init(tmp_path):
    # A base-run (plan) draft for the same feature must NOT count as an active feature run,
    # so a subsequent feature init succeeds (frickle b).
    plan = do_init(tmp_path, action="plan", run_id="2026-07-18-0000aaaa")
    assert plan["ok"]
    plan_manifest = json.loads((Path(plan["run_folder"]) / "evidence-manifest.json").read_text())
    assert plan_manifest["run_scope"] == "base-run-only"
    feat = do_init(tmp_path, action="feature")  # same feature id, feature-completion scope
    assert feat["ok"]
    feat_manifest = json.loads((Path(feat["run_folder"]) / "evidence-manifest.json").read_text())
    assert feat_manifest["run_scope"] == "feature-completion"


def test_resume_same_run_is_idempotent(tmp_path):
    first = do_init(tmp_path, run_id="2026-07-18-aaaaaaaa")
    assert first["ok"]
    again = do_init(tmp_path, run_id="2026-07-18-aaaaaaaa", resume=True)
    assert again["ok"]
    assert "evidence-manifest.json" in again["preserved"]
    assert again["created"] == []  # everything already present


def test_existing_run_folder_without_resume_is_rejected(tmp_path):
    first = do_init(tmp_path, run_id="2026-07-18-bbbbbbbb")
    # Close the first run so it is not an *active* conflict, isolating the folder-exists path.
    manifest = Path(first["run_folder"]) / "evidence-manifest.json"
    data = json.loads(manifest.read_text()); data["status"] = "superseded"
    manifest.write_text(json.dumps(data))
    with pytest.raises(ir.InitError) as exc:
        do_init(tmp_path, run_id="2026-07-18-bbbbbbbb")
    assert exc.value.code == 4


def test_malformed_feature_id_rejected(tmp_path):
    with pytest.raises(ir.InitError) as exc:
        do_init(tmp_path, feature_id="NOTAFEATURE")
    assert exc.value.code == 5


def test_slug_path_escape_rejected(tmp_path):
    with pytest.raises(ir.InitError) as exc:
        do_init(tmp_path, feature_slug="../evil")
    assert exc.value.code == 5


def test_rollback_leaves_no_partial_skeleton(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("simulated failure after folder creation")
    monkeypatch.setattr(ir, "_write_manifest", boom)
    with pytest.raises(RuntimeError):
        do_init(tmp_path)
    runs = tmp_path / "planning-mds" / "operations" / "evidence" / "runs"
    run_dirs = [p for p in runs.iterdir() if p.is_dir()] if runs.is_dir() else []
    assert run_dirs == [], "partial run folder must be rolled back"


def test_concurrent_initializers_yield_one_success(tmp_path):
    def launch():
        return subprocess.Popen(
            [sys.executable, str(SCRIPTS_DIR / "init-run.py"), "--feature", "F0007",
             "--feature-slug", SLUG, "--product-root", str(tmp_path), "--json"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    p1, p2 = launch(), launch()
    rc = sorted([p1.wait(), p2.wait()])
    assert rc[0] == 0 and rc[1] == 3, f"expected one success and one conflict, got {rc}"

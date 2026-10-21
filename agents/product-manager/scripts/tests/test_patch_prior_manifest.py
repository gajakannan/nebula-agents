"""Unit tests for `patch-prior-manifest.py` (§17 step 4, §24)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "agents" / "product-manager" / "scripts" / "patch-prior-manifest.py"
RUN_NEW = "2026-05-20-1111aaaa"
RUN_PRIOR_A = "2026-05-15-2222bbbb"
RUN_PRIOR_B = "2026-05-18-3333cccc"


def write_manifest(folder: Path, feature_id: str, run_id: str, status: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "feature_id": feature_id,
        "run_id": run_id,
        "status": status,
        "recorded_on": "2026-05-19",
    }
    (folder / "evidence-manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def make_evidence_root(tmp_path: Path, feature_id: str = "F0036") -> Path:
    root = tmp_path / "product" / "planning-mds" / "operations" / "evidence" / "runs"
    root.mkdir(parents=True)
    return root


def run_patch(product_root: Path, feature: str, new_run_id: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT), "--product-root", str(product_root), "--feature", feature, "--new-run-id", new_run_id],
        capture_output=True,
        text=True,
        check=False,
    )


def status_of(root: Path, run_id: str) -> str:
    return json.loads((root / run_id / "evidence-manifest.json").read_text(encoding="utf-8"))["status"]


def test_single_prior_approved_is_patched(tmp_path: Path) -> None:
    root = make_evidence_root(tmp_path)
    write_manifest(root / RUN_PRIOR_A, "F0036", RUN_PRIOR_A, "approved")
    write_manifest(root / RUN_NEW, "F0036", RUN_NEW, "approved")

    result = run_patch(tmp_path / "product", "F0036", RUN_NEW)
    assert result.returncode == 0, result.stdout + result.stderr
    assert status_of(root, RUN_PRIOR_A) == "superseded"
    assert status_of(root, RUN_NEW) == "approved"


def test_multi_prior_approved_all_patched(tmp_path: Path) -> None:
    root = make_evidence_root(tmp_path)
    write_manifest(root / RUN_PRIOR_A, "F0036", RUN_PRIOR_A, "approved")
    write_manifest(root / RUN_PRIOR_B, "F0036", RUN_PRIOR_B, "approved")
    write_manifest(root / RUN_NEW, "F0036", RUN_NEW, "approved")

    result = run_patch(tmp_path / "product", "F0036", RUN_NEW)
    assert result.returncode == 0
    assert status_of(root, RUN_PRIOR_A) == "superseded"
    assert status_of(root, RUN_PRIOR_B) == "superseded"
    assert status_of(root, RUN_NEW) == "approved"


def test_idempotent_rerun_is_noop(tmp_path: Path) -> None:
    root = make_evidence_root(tmp_path)
    write_manifest(root / RUN_PRIOR_A, "F0036", RUN_PRIOR_A, "superseded")
    write_manifest(root / RUN_NEW, "F0036", RUN_NEW, "approved")

    result = run_patch(tmp_path / "product", "F0036", RUN_NEW)
    assert result.returncode == 0
    assert status_of(root, RUN_PRIOR_A) == "superseded"
    assert "no prior approved manifests to patch" in result.stdout


def test_first_run_no_priors_exits_zero(tmp_path: Path) -> None:
    root = make_evidence_root(tmp_path)
    write_manifest(root / RUN_NEW, "F0036", RUN_NEW, "approved")

    result = run_patch(tmp_path / "product", "F0036", RUN_NEW)
    assert result.returncode == 0
    assert status_of(root, RUN_NEW) == "approved"


def test_non_run_id_folders_ignored(tmp_path: Path) -> None:
    root = make_evidence_root(tmp_path)
    (root / "junk-folder").mkdir()
    write_manifest(root / "junk-folder", "F0036", "junk-folder", "approved")
    write_manifest(root / RUN_PRIOR_A, "F0036", RUN_PRIOR_A, "approved")
    write_manifest(root / RUN_NEW, "F0036", RUN_NEW, "approved")

    result = run_patch(tmp_path / "product", "F0036", RUN_NEW)
    assert result.returncode == 0
    assert status_of(root, RUN_PRIOR_A) == "superseded"
    junk = json.loads((root / "junk-folder" / "evidence-manifest.json").read_text(encoding="utf-8"))
    assert junk["status"] == "approved", "junk folder must not have been touched"


def test_missing_new_manifest_exits_one(tmp_path: Path) -> None:
    root = make_evidence_root(tmp_path)
    write_manifest(root / RUN_PRIOR_A, "F0036", RUN_PRIOR_A, "approved")

    result = run_patch(tmp_path / "product", "F0036", RUN_NEW)
    assert result.returncode == 1
    assert "missing" in result.stderr
    assert status_of(root, RUN_PRIOR_A) == "approved", "prior must not be touched when new manifest is missing"


def test_unparseable_new_manifest_exits_one(tmp_path: Path) -> None:
    root = make_evidence_root(tmp_path)
    (root / RUN_NEW).mkdir()
    (root / RUN_NEW / "evidence-manifest.json").write_text("{", encoding="utf-8")

    result = run_patch(tmp_path / "product", "F0036", RUN_NEW)
    assert result.returncode == 1
    assert "parse" in result.stderr


def test_bad_run_id_rejected(tmp_path: Path) -> None:
    root = make_evidence_root(tmp_path)
    write_manifest(root / RUN_NEW, "F0036", RUN_NEW, "approved")

    result = run_patch(tmp_path / "product", "F0036", "not-a-run-id")
    assert result.returncode == 1


def test_bad_feature_id_rejected(tmp_path: Path) -> None:
    result = run_patch(tmp_path, "bad-id", RUN_NEW)
    assert result.returncode == 1


def test_missing_feature_evidence_root_exits_one(tmp_path: Path) -> None:
    (tmp_path / "product" / "planning-mds" / "operations" / "evidence").mkdir(parents=True)
    result = run_patch(tmp_path / "product", "F9999", RUN_NEW)
    assert result.returncode == 1
    assert "not found" in result.stderr


def test_completion_closeout_preserves_planning_approval(tmp_path: Path) -> None:
    root = make_evidence_root(tmp_path)
    write_manifest(root / RUN_PRIOR_A, "F0036", RUN_PRIOR_A, "approved")
    plan = root / RUN_PRIOR_A / "evidence-manifest.json"
    data = json.loads(plan.read_text()); data["run_scope"] = "base-run-only"
    plan.write_text(json.dumps(data))
    before = plan.read_bytes()
    write_manifest(root / RUN_PRIOR_B, "F0036", RUN_PRIOR_B, "approved")
    write_manifest(root / RUN_NEW, "F0036", RUN_NEW, "in-progress")
    result = run_patch(tmp_path / "product", "F0036", RUN_NEW)
    assert result.returncode == 0, result.stderr
    assert plan.read_bytes() == before
    assert status_of(root, RUN_PRIOR_B) == "superseded"
    current = json.loads((root / RUN_NEW / "evidence-manifest.json").read_text())
    prior = json.loads((root / RUN_PRIOR_B / "evidence-manifest.json").read_text())
    assert current["status"] == "in-progress"  # approval/pointer publication remains the caller's job
    assert current["supersedes"] == [RUN_PRIOR_B]
    assert prior["superseded_by"] == RUN_NEW


def test_completion_helper_rejects_planning_successor_without_mutation(tmp_path: Path) -> None:
    root = make_evidence_root(tmp_path)
    write_manifest(root / RUN_PRIOR_A, "F0036", RUN_PRIOR_A, "approved")
    write_manifest(root / RUN_NEW, "F0036", RUN_NEW, "approved")
    path = root / RUN_NEW / "evidence-manifest.json"
    data = json.loads(path.read_text()); data["run_scope"] = "base-run-only"
    path.write_text(json.dumps(data))
    result = run_patch(tmp_path / "product", "F0036", RUN_NEW)
    assert result.returncode == 1
    assert "feature-completion scope" in result.stderr
    assert status_of(root, RUN_PRIOR_A) == "approved"

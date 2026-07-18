"""Tests for the behavioral contract diff (F0007-S0002).

Covers reorder-insensitivity, breaking-change detection, the version-bump policy
rule, historical immutability, and the git-ref CLI path.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "agents" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_action_specs as vas  # noqa: E402

FIXTURE_VALID = Path(__file__).resolve().parent / "fixtures" / "action-specs" / "valid"


def copy_valid(dst: Path) -> Path:
    shutil.copytree(FIXTURE_VALID, dst)
    return dst


def load(dst: Path, name: str) -> dict:
    return yaml.safe_load((dst / name).read_text(encoding="utf-8"))


def dump(dst: Path, name: str, data: dict, sort_keys: bool = False) -> None:
    (dst / name).write_text(yaml.safe_dump(data, sort_keys=sort_keys), encoding="utf-8")


def test_identical_dirs_empty_diff(tmp_path):
    base = copy_valid(tmp_path / "base")
    head = copy_valid(tmp_path / "head")
    diff = vas.diff_spec_dirs(base, head)
    assert diff["ok"] and diff["compatibility_class"] == "identical"
    assert not (diff["added"] or diff["removed"] or diff["changed"])


def test_key_and_orderless_list_reorder_is_empty(tmp_path):
    base = copy_valid(tmp_path / "base")
    head = copy_valid(tmp_path / "head")
    contract = load(head, "_contract.yaml")
    contract["shared"]["base_run_files"] = list(reversed(contract["shared"]["base_run_files"]))
    dump(head, "_contract.yaml", contract, sort_keys=True)  # also reorders mapping keys
    diff = vas.diff_spec_dirs(base, head)
    assert diff["compatibility_class"] == "identical", diff
    assert diff["ok"]


def test_gate_reorder_is_a_change(tmp_path):
    base = copy_valid(tmp_path / "base")
    head = copy_valid(tmp_path / "head")
    spec = load(head, "sample.yaml")
    spec["gates"] = list(reversed(spec["gates"]))
    dump(head, "sample.yaml", spec)
    diff = vas.diff_spec_dirs(base, head)
    assert diff["changed"], "gate order is behavior; reorder must surface"


def test_removed_gate_artifact_is_breaking(tmp_path):
    base = copy_valid(tmp_path / "base")
    head = copy_valid(tmp_path / "head")
    spec = load(head, "sample.yaml")
    spec["gates"][0]["artifacts"] = []
    dump(head, "sample.yaml", spec)
    diff = vas.diff_spec_dirs(base, head)
    changed = [c for c in diff["changed"] if "artifacts" in c["path"]]
    assert changed and all(c["compatibility"] == "breaking" for c in changed)


def test_behavioral_change_without_version_bump_is_rejected(tmp_path):
    base = copy_valid(tmp_path / "base")
    head = copy_valid(tmp_path / "head")
    contract = load(head, "_contract.yaml")
    contract["shared"]["coverage_min_pct"] = 70  # behavioral change, active_version untouched
    dump(head, "_contract.yaml", contract)
    diff = vas.diff_spec_dirs(base, head)
    assert not diff["ok"]
    assert diff["requires_version_bump"] and not diff["version_bumped"]
    assert any(v["rule"] == "behavioral_change_without_version_bump" for v in diff["violations"])


def test_version_bump_clears_the_violation(tmp_path):
    base = copy_valid(tmp_path / "base")
    head = copy_valid(tmp_path / "head")
    contract = load(head, "_contract.yaml")
    contract["shared"]["coverage_min_pct"] = 70
    contract["active_version"] = "2025-03-01"  # bump accompanies the behavioral change
    dump(head, "_contract.yaml", contract)
    diff = vas.diff_spec_dirs(base, head)
    assert diff["version_bumped"]
    assert not any(v["rule"] == "behavioral_change_without_version_bump" for v in diff["violations"])


def test_history_mutation_is_rejected(tmp_path):
    base = copy_valid(tmp_path / "base")
    head = copy_valid(tmp_path / "head")
    bundle = load(head, "history/2025-02-01.yaml")
    bundle["shared"]["requirements"]["kg_reconciliation_required"] = False  # weaken a published bundle
    dump(head, "history/2025-02-01.yaml", bundle)
    diff = vas.diff_spec_dirs(base, head)
    assert not diff["ok"]
    assert any(v["rule"] == "historical_bundle_mutated" for v in diff["violations"])


def test_cli_git_head_identical():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "validate_action_specs.py"), "--contract-diff", "HEAD..HEAD"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    diff = json.loads(proc.stdout)
    assert diff["compatibility_class"] == "identical" and diff["ok"]


def test_cli_markdown_format():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "validate_action_specs.py"),
         "--contract-diff", "HEAD..HEAD", "--format", "md"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("# Behavioral contract diff")

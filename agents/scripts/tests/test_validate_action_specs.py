"""Tests for validate_action_specs.py (F0007-S0001).

Covers the happy path on both the shipped policy and an isolated fixture, every
rejection rule, manifest-version resolution (explicit + legacy-date), the audit
report shape, determinism, and the CLI.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "agents" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_action_specs as vas  # noqa: E402

REAL_SPEC_DIR = REPO_ROOT / "agents" / "actions" / "spec"
FIXTURE_VALID = Path(__file__).resolve().parent / "fixtures" / "action-specs" / "valid"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def make_policy(tmp_path: Path) -> Path:
    """Assemble an isolated spec dir: fixture policy + the real schemas."""
    dst = tmp_path / "spec"
    shutil.copytree(FIXTURE_VALID, dst)
    shutil.copytree(REAL_SPEC_DIR / "schema", dst / "schema")
    return dst


def rules(result: vas.Result) -> set[str]:
    return {f.rule for f in result.findings}


def load(dst: Path, name: str) -> dict:
    return yaml.safe_load((dst / name).read_text(encoding="utf-8"))


def dump(dst: Path, name: str, data: dict) -> None:
    (dst / name).write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def validate(dst: Path) -> vas.Result:
    result, _ = vas.validate_policy(dst)
    return result


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #
def test_real_policy_validates():
    result, _ = vas.validate_policy(REAL_SPEC_DIR)
    assert result.ok, [f.as_dict() for f in result.sorted_findings()]


def test_fixture_policy_validates(tmp_path):
    result = validate(make_policy(tmp_path))
    assert result.ok, [f.as_dict() for f in result.sorted_findings()]


def test_validation_is_deterministic(tmp_path):
    dst = make_policy(tmp_path)
    r1, p1 = vas.validate_policy(dst)
    r2, p2 = vas.validate_policy(dst)
    assert vas.build_report(r1, p1) == vas.build_report(r2, p2)


# --------------------------------------------------------------------------- #
# Report shape / audit record (AC: reports versions, actions, gates, shared)
# --------------------------------------------------------------------------- #
def test_report_reports_versions_actions_gates_shared():
    result, policy = vas.validate_policy(REAL_SPEC_DIR)
    report = vas.build_report(result, policy)
    assert [v["version"] for v in report["versions"]] == [
        "2026-05-19", "2026-05-25", "2026-06-01", "2026-07-05", "2026-07-11",
    ]
    feature = next(a for a in report["actions"] if a["action"] == "feature")
    assert [g["id"] for g in feature["gates"]] == [f"G{i}" for i in range(9)]
    assert report["shared"]["coverage_min_pct"] == 80
    assert report["audit"]["selection_source"] == "active"
    assert report["audit"]["selected_version"] == report["audit"]["newest_history_version"] == "2026-07-11"


# --------------------------------------------------------------------------- #
# Rejection cases
# --------------------------------------------------------------------------- #
def test_string_form_command_rejected(tmp_path):
    dst = make_policy(tmp_path)
    spec = load(dst, "sample.yaml")
    spec["gates"][0]["operations"] = ["python3 agents/scripts/foo.py --do-it"]
    dump(dst, "sample.yaml", spec)
    result = validate(dst)
    assert not result.ok
    assert "shell_form_command" in rules(result)


def test_unknown_placeholder_rejected(tmp_path):
    dst = make_policy(tmp_path)
    spec = load(dst, "sample.yaml")
    spec["gates"][0]["operations"][0]["run"]["argv"].append("{BOGUS_VAR}")
    dump(dst, "sample.yaml", spec)
    assert "unknown_placeholder" in rules(validate(dst))


def test_path_escape_rejected(tmp_path):
    dst = make_policy(tmp_path)
    spec = load(dst, "sample.yaml")
    spec["gates"][0]["operations"][0]["run"]["argv"].append("{PRODUCT_ROOT}/../secrets")
    dump(dst, "sample.yaml", spec)
    assert "path_escapes_root" in rules(validate(dst))


def test_absolute_path_argv_rejected(tmp_path):
    dst = make_policy(tmp_path)
    spec = load(dst, "sample.yaml")
    spec["gates"][0]["operations"][0]["run"]["argv"].append("/etc/passwd")
    dump(dst, "sample.yaml", spec)
    assert "path_escapes_root" in rules(validate(dst))


def test_duplicate_gate_id_rejected(tmp_path):
    dst = make_policy(tmp_path)
    spec = load(dst, "sample.yaml")
    dupe = {"id": "G0", "title": "Dupe", "role": "devops"}
    spec["gates"].append(dupe)
    dump(dst, "sample.yaml", spec)
    assert "duplicate_gate_id" in rules(validate(dst))


def test_duplicate_operation_id_rejected(tmp_path):
    dst = make_policy(tmp_path)
    spec = load(dst, "sample.yaml")
    spec["gates"][1]["operations"].append({
        "run": {"id": "validate-g0", "argv": ["python3", "agents/scripts/foo.py"],
                "cwd": "framework"}
    })
    dump(dst, "sample.yaml", spec)
    assert "duplicate_operation_id" in rules(validate(dst))


def test_undeclared_mutation_class_rejected(tmp_path):
    dst = make_policy(tmp_path)
    spec = load(dst, "sample.yaml")
    spec["gates"][0]["operations"][0]["run"]["mutates"] = ["bogus-mutation"]
    dump(dst, "sample.yaml", spec)
    assert "undeclared_mutation_class" in rules(validate(dst))


def test_checkpoint_missing_postcondition_rejected(tmp_path):
    dst = make_policy(tmp_path)
    spec = load(dst, "sample.yaml")
    del spec["gates"][1]["operations"][0]["checkpoint"]["produces"]
    dump(dst, "sample.yaml", spec)
    result = validate(dst)
    assert not result.ok
    # Schema requires produces; a checkpoint without postconditions is rejected.
    assert "action_spec_schema" in rules(result)


def test_action_contract_version_mismatch_rejected(tmp_path):
    dst = make_policy(tmp_path)
    spec = load(dst, "sample.yaml")
    spec["contract"]["version"] = "2025-01-01"  # exists but not the active version
    dump(dst, "sample.yaml", spec)
    assert "action_contract_version_mismatch" in rules(validate(dst))


def test_active_version_not_newest_rejected(tmp_path):
    dst = make_policy(tmp_path)
    contract = load(dst, "_contract.yaml")
    contract["active_version"] = "2025-01-01"
    dump(dst, "_contract.yaml", contract)
    assert "active_version_not_newest" in rules(validate(dst))


def test_active_version_missing_bundle_rejected(tmp_path):
    dst = make_policy(tmp_path)
    contract = load(dst, "_contract.yaml")
    contract["active_version"] = "2025-09-09"
    dump(dst, "_contract.yaml", contract)
    assert "active_version_missing_bundle" in rules(validate(dst))


def test_duplicate_policy_version_rejected(tmp_path):
    dst = make_policy(tmp_path)
    dupe = load(dst, "history/2025-02-01.yaml")
    (dst / "history" / "2025-03-01.yaml").write_text(
        yaml.safe_dump(dupe, sort_keys=False), encoding="utf-8")
    assert "duplicate_policy_version" in rules(validate(dst))


def test_bundle_effective_from_mismatch_rejected(tmp_path):
    dst = make_policy(tmp_path)
    bundle = load(dst, "history/2025-02-01.yaml")
    bundle["effective_from"] = "2025-02-02"
    dump(dst, "history/2025-02-01.yaml", bundle)
    assert "bundle_effective_from_mismatch" in rules(validate(dst))


# --------------------------------------------------------------------------- #
# Manifest resolution
# --------------------------------------------------------------------------- #
@pytest.fixture()
def policy(tmp_path):
    result = vas.Result()
    return vas.load_policy(make_policy(tmp_path), result)


def test_resolve_explicit_hit(policy):
    rec = vas.resolve_manifest(policy, version="2025-01-01")
    assert rec["ok"] and rec["selected_version"] == "2025-01-01"
    assert rec["selection_source"] == "explicit"


def test_resolve_explicit_unknown(policy):
    rec = vas.resolve_manifest(policy, version="2099-01-01")
    assert not rec["ok"] and rec["rule"] == "manifest_unknown_version"


def test_resolve_legacy_date_maps_to_newest_eligible(policy):
    rec = vas.resolve_manifest(policy, effective_date="2025-01-15")
    assert rec["ok"] and rec["selected_version"] == "2025-01-01"
    assert rec["selection_source"] == "legacy-date"


def test_resolve_legacy_date_boundary_inclusive(policy):
    rec = vas.resolve_manifest(policy, effective_date="2025-02-01")
    assert rec["ok"] and rec["selected_version"] == "2025-02-01"


def test_resolve_date_before_first_policy(policy):
    rec = vas.resolve_manifest(policy, effective_date="2024-01-01")
    assert not rec["ok"] and rec["rule"] == "manifest_date_before_first_policy"


def test_resolve_requires_a_selector(policy):
    rec = vas.resolve_manifest(policy)
    assert not rec["ok"] and rec["rule"] == "manifest_no_selector"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "validate_action_specs.py"), *args],
        capture_output=True, text=True,
    )


def test_cli_validates_real_policy():
    proc = _run("--json")
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] and data["active_version"] == "2026-07-11"


def test_cli_resolves_legacy_date():
    proc = _run("--resolve-manifest", "--effective-date", "2026-06-15")
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["selected_version"] == "2026-06-01"
    assert data["selection_source"] == "legacy-date"


def test_cli_unknown_version_exits_nonzero():
    proc = _run("--resolve-manifest", "--version", "1999-01-01")
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["rule"] == "manifest_unknown_version"

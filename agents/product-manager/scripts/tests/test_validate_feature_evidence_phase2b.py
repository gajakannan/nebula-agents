"""Phase 2b tests: SCM diff parsing, §21 cross-artifact rules, §22 downgrade."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_validate_feature_evidence import (
    RUN_ID,
    ROLE_FILES,
    json_result,
    latest_run_path,
    run_validator,
    write_manifest_run,
    write_registry,
)


def write_future_kg_closeout_run(product: Path, commands: list[dict[str, object]]) -> Path:
    write_registry(product, archived="| F0001 | New Feature | 2026-07-05 |  | `archive/F0001-new/` |")
    gate_results = {
        "assembly_plan_validation": {"required": True, "result": "PASS", "artifact": "g0-assembly-plan-validation.md"},
        "self_review": {"required": True, "result": "PASS", "artifact": "g2-self-review.md"},
        "deployability": {"required": True, "result": "PASS", "artifact": "deployability-check.md"},
        "signoff": {"required": True, "result": "PASS", "artifact": "signoff-ledger.md"},
        "kg_reconciliation": {"required": True, "result": "PASS", "artifact": "kg-reconciliation.md"},
        "pm_closeout": {"required": True, "result": "APPROVED", "artifact": "pm-closeout.md"},
        "tracker_sync": {"required": True, "result": "PASS", "artifact": "lifecycle-gates.log"},
    }
    run_folder = write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        status="approved",
        latest=True,
        stage="closeout",
        manifest_updates={
            "contract_effective_date": "2026-07-05",
            "status": "approved",
            "feature_state": "Archived",
            "feature_path_at_closeout": "planning-mds/features/archive/F0001-new",
            "gate_results": gate_results,
        },
    )
    gate_rows = "\n".join(
        f"| {gate} | PASS | role | 2026-07-05 | ok | No | - |"
        for gate in ("G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8")
    )
    (run_folder / "gate-decisions.md").write_text(
        "# Gate Decisions\n\n"
        "| Gate | Decision | Decider | Timestamp | Rationale | Blocking | Follow-up |\n"
        "|---|---|---|---|---|---|---|\n"
        f"{gate_rows}\n",
        encoding="utf-8",
    )
    (run_folder / "kg-reconciliation.md").write_text(
        "# KG Reconciliation\n\n"
        "## Binding Delta\n\nAs-built source bindings reconciled.\n\n"
        "## Canonical Nodes\n\nNo new canonical nodes.\n\n"
        "## Validator Results\n\nSymbol and drift validators recorded in commands.log.\n\n"
        "## Handoff to Closeout\n\nReady for PM closeout.\n",
        encoding="utf-8",
    )
    (run_folder / "commands.log").write_text(
        "\n".join(json.dumps(record) for record in commands) + "\n",
        encoding="utf-8",
    )
    return run_folder


# --------------------------------------------------------------------------- #
# SCM diff parsing + changed_paths_missing_diff_entry + boolean contradictions
# --------------------------------------------------------------------------- #


def test_changed_paths_missing_diff_entry_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        manifest_updates={"changed_paths": ["planning-mds/features/F0001-new"]},
    )
    # Write a diff artifact with paths NOT covered by changed_paths.
    diff_path = run_folder / "artifacts" / "diffs" / "changed-files.txt"
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff_path.write_text("engine/src/runtime.cs\nexperience/src/ui.tsx\n", encoding="utf-8")

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "changed_paths_missing_diff_entry_fails" in rules


def test_scope_boolean_false_with_changed_paths_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        manifest_updates={
            # engine/** forces runtime_bearing, but we declare it false.
            "changed_paths": ["engine/src/Feature.cs"],
            "runtime_bearing": False,
        },
    )

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "scope_boolean_false_with_changed_paths_fails" in rules


# --------------------------------------------------------------------------- #
# §21 identity rules
# --------------------------------------------------------------------------- #


def test_feature_identity_mismatch_via_latest_run_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        status="approved",
        latest=True,
        stage="closeout",
        manifest_updates={
            "status": "approved",
            "feature_state": "Archived",
            "feature_path_at_closeout": "planning-mds/features/archive/F0001-new",
        },
    )
    # Corrupt latest-run.json to refer to a different feature_id.
    latest = latest_run_path(product, "F0001-new")
    data = json.loads(latest.read_text(encoding="utf-8"))
    data["feature_id"] = "F9999"
    latest.write_text(json.dumps(data, indent=2), encoding="utf-8")

    result = run_validator(product, "--feature", "F0001", "--stage", "closeout", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "feature_identity_mismatch_fails" in rules


def test_closeout_path_mismatch_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        status="approved",
        latest=True,
        stage="closeout",
        manifest_updates={
            "status": "approved",
            "feature_state": "Archived",
            "feature_path_at_closeout": "planning-mds/features/archive/F9999-wrong",
        },
    )

    result = run_validator(product, "--feature", "F0001", "--stage", "closeout", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "closeout_path_mismatch_fails" in rules


# --------------------------------------------------------------------------- #
# §21 ledger / coverage / omission / command rules
# --------------------------------------------------------------------------- #


def test_signoff_ledger_stale_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        status="approved",
        latest=True,
        stage="closeout",
        manifest_updates={
            "status": "approved",
            "feature_state": "Archived",
            "feature_path_at_closeout": "planning-mds/features/archive/F0001-new",
        },
    )
    # Reset signoff-ledger.md back to the bare template — no row references.
    (run_folder / "signoff-ledger.md").write_text(ROLE_FILES["signoff-ledger.md"], encoding="utf-8")

    result = run_validator(product, "--feature", "F0001", "--stage", "closeout", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "signoff_ledger_stale_fails" in rules


def test_coverage_waiver_mismatch_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        status="approved",
        latest=True,
        stage="closeout",
        manifest_updates={
            "status": "approved",
            "feature_state": "Archived",
            "feature_path_at_closeout": "planning-mds/features/archive/F0001-new",
            "waivers": {
                "coverage": {
                    "required": False,
                    "reason": "documentation-only feature",
                    "owner": "QualityEngineerJane",
                    "approved_on": "2026-05-19",
                    "follow_up": "None",
                }
            },
        },
    )
    # coverage-report.md exists from the helper but doesn't mention the owner/date/reason.
    (run_folder / "coverage-report.md").write_text(
        "# Coverage\n\nCoverage is waived.\n\nResult: PASS\n",
        encoding="utf-8",
    )
    pm = run_folder / "pm-closeout.md"
    pm.write_text(
        ROLE_FILES["pm-closeout.md"] + "\n- Accepted: coverage — Waived; 2026-05-19\n",
        encoding="utf-8",
    )

    result = run_validator(product, "--feature", "F0001", "--stage", "closeout", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "coverage_waiver_mismatch_fails" in rules


def test_omission_filesystem_mismatch_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(product, "F0001-new", "F0001", stage="G3")
    # Inject an omission entry pointing at a file that exists.
    manifest_path = run_folder / "evidence-manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["omissions"] = [{
        "artifact": "code-review-report.md",
        "reason": "skipped",
        "approved_by": "PM",
        "approved_on": "2026-05-19",
    }]
    # Also drop Code Reviewer from required_roles to avoid manifest_required_artifact_omitted.
    data["required_roles"] = ["Quality Engineer"]
    data["role_results"].pop("Code Reviewer", None)
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G3", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "omission_filesystem_mismatch_fails" in rules


def test_command_artifact_missing_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(product, "F0001-new", "F0001")
    (run_folder / "commands.log").write_text(
        json.dumps({
            "schema_version": 1,
            "timestamp": "2026-05-19T12:00:00Z",
            "cwd": "{NEBULA_PRODUCT_ROOT}",
            "command": "pnpm test",
            "exit_code": 0,
            "artifacts": ["planning-mds/operations/evidence/runs/2026-05-19-5ab6f922/artifacts/test-results/nonexistent.log"],
            "redactions": [],
        }) + "\n",
        encoding="utf-8",
    )

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "command_artifact_missing_fails" in rules


def test_kg_generated_regeneration_missing_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_future_kg_closeout_run(
        product,
        [{
            "schema_version": 1,
            "timestamp": "2026-07-05T12:00:00Z",
            "cwd": "{NEBULA_PRODUCT_ROOT}",
            "command": "python3 scripts/kg/validate.py --regenerate-symbols --check-symbols",
            "exit_code": 0,
            "artifacts": [],
            "redactions": [],
        }],
    )

    result = run_validator(product, "--feature", "F0001", "--stage", "closeout", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "kg_generated_regeneration_missing_fails" in rules


def test_kg_generated_regeneration_command_passes(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_future_kg_closeout_run(
        product,
        [{
            "schema_version": 1,
            "timestamp": "2026-07-05T12:00:00Z",
            "cwd": "{NEBULA_PRODUCT_ROOT}",
            "command": (
                "python3 scripts/kg/validate.py --regenerate-symbols --check-symbols "
                "--regenerate-decisions --check-decisions --write-coverage-report"
            ),
            "exit_code": 0,
            "artifacts": [],
            "redactions": [],
        }],
    )

    result = run_validator(product, "--feature", "F0001", "--stage", "closeout", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "kg_generated_regeneration_missing_fails" not in rules


def command_artifact_result(tmp_path: Path, artifact: str, *, existing_rel: str | None = None):
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(product, "F0001-new", "F0001")
    if existing_rel:
        target = product / existing_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("ok\n", encoding="utf-8")
    (run_folder / "commands.log").write_text(
        json.dumps({
            "schema_version": 1,
            "timestamp": "2026-05-19T12:00:00Z",
            "cwd": "{NEBULA_PRODUCT_ROOT}",
            "command": "pnpm test",
            "exit_code": 0,
            "artifacts": [artifact],
            "redactions": [],
        }) + "\n",
        encoding="utf-8",
    )
    return run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")


def command_artifact_rel() -> str:
    return f"planning-mds/operations/evidence/runs/{RUN_ID}/artifacts/test-results/output.log"


def test_repo_relative_existing_command_artifact_passes(tmp_path: Path) -> None:
    artifact = command_artifact_rel()
    result = command_artifact_result(tmp_path, artifact, existing_rel=artifact)
    assert result.returncode == 0, result.stdout + result.stderr
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "artifact_missing_fails" not in rules


def test_repo_relative_missing_command_artifact_fails(tmp_path: Path) -> None:
    artifact = command_artifact_rel()
    result = command_artifact_result(tmp_path, artifact)
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "artifact_missing_fails" in rules
    assert "commands_log_artifact_missing_fails" in rules
    assert "command_artifact_missing_fails" in rules


def test_current_product_root_absolute_command_artifact_warns(tmp_path: Path) -> None:
    artifact = command_artifact_rel()
    product = tmp_path / "product"
    absolute_artifact = str(product / artifact)
    result = command_artifact_result(tmp_path, absolute_artifact, existing_rel=artifact)
    assert result.returncode == 0, result.stdout + result.stderr
    warnings = {entry["rule_id"] for entry in json_result(result)["warnings"]}
    assert "absolute_artifact_under_product_root_warns" in warnings


@pytest.mark.parametrize("label", ["NEBULA_PRODUCT_ROOT", "PRODUCT_ROOT"])
def test_product_root_placeholder_command_artifact_warns(tmp_path: Path, label: str) -> None:
    artifact = command_artifact_rel()
    result = command_artifact_result(tmp_path, "{" + label + "}/" + artifact, existing_rel=artifact)
    assert result.returncode == 0, result.stdout + result.stderr
    warnings = {entry["rule_id"] for entry in json_result(result)["warnings"]}
    assert "placeholder_artifact_path_normalized_warns" in warnings


def test_historical_absolute_command_artifact_relocates_when_current_file_exists(tmp_path: Path) -> None:
    artifact = command_artifact_rel()
    legacy_artifact = f"/mnt/c/Users/gajap/sandbox/nebula-insurance-crm/{artifact}"
    result = command_artifact_result(tmp_path, legacy_artifact, existing_rel=artifact)
    assert result.returncode == 0, result.stdout + result.stderr
    warnings = {entry["rule_id"] for entry in json_result(result)["warnings"]}
    assert "legacy_absolute_artifact_relocated_warns" in warnings


def test_historical_absolute_command_artifact_missing_still_fails(tmp_path: Path) -> None:
    artifact = command_artifact_rel()
    legacy_artifact = f"/mnt/c/Users/gajap/sandbox/nebula-insurance-crm/{artifact}"
    result = command_artifact_result(tmp_path, legacy_artifact)
    payload = json_result(result)
    rules = {entry["rule_id"] for entry in payload["errors"]}
    warnings = {entry["rule_id"] for entry in payload["warnings"]}
    assert "artifact_missing_fails" in rules
    assert "legacy_absolute_artifact_relocated_warns" not in warnings


def test_scratch_command_artifact_fails(tmp_path: Path) -> None:
    result = command_artifact_result(tmp_path, "/tmp/nebula-artifact-output.log")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "scratch_artifact_fails" in rules


def test_unmappable_absolute_command_artifact_fails(tmp_path: Path) -> None:
    result = command_artifact_result(tmp_path, "/opt/external-artifact-output.log")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "unmappable_absolute_artifact_fails" in rules


def test_url_command_artifact_behavior_is_unchanged(tmp_path: Path) -> None:
    result = command_artifact_result(tmp_path, "https://example.invalid/artifacts/test-results/output.log")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json_result(result)["errors"] == []


# --------------------------------------------------------------------------- #
# §22 validator-defect downgrade
# --------------------------------------------------------------------------- #


def test_validator_defect_downgrade_demotes_error_to_warning(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        status="approved",
        latest=True,
        stage="closeout",
        manifest_updates={
            "status": "approved",
            "feature_state": "Archived",
            "feature_path_at_closeout": "planning-mds/features/archive/F0001-new",
            # Trigger manifest_changed_path_traversal_fails …
            "changed_paths": ["../leak", "planning-mds/features/F0001-new"],
            "waivers": {
                # … then waive it via validator_defect with the correct PM mirror.
                "validator_defect": {
                    "defect_description": "False positive on quoted path",
                    "affected_rule_ids": ["manifest_changed_path_traversal_fails"],
                    "approved_by": "PM",
                    "approved_on": "2026-05-19",
                    "follow_up_owner": "framework-team",
                    "follow_up_target_date": "2026-06-15",
                }
            },
        },
    )
    pm = run_folder / "pm-closeout.md"
    pm.write_text(
        ROLE_FILES["pm-closeout.md"]
        + "\n## Validator Defects\n\n- Accepted: manifest_changed_path_traversal_fails — defect: quoted path; target: 2026-06-15\n",
        encoding="utf-8",
    )

    result = run_validator(product, "--feature", "F0001", "--stage", "closeout", "--json")
    payload = json_result(result)
    error_rules = {entry["rule_id"] for entry in payload["errors"]}
    warning_rules = {entry["rule_id"] for entry in payload["warnings"]}
    assert "manifest_changed_path_traversal_fails" not in error_rules
    assert "validator_defect_waived_warns" in warning_rules


def test_validator_defect_downgrade_skipped_when_target_before_recorded(tmp_path: Path) -> None:
    """If the waiver is malformed (target_date < recorded_on), no downgrade
    happens — the original error remains."""
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        status="approved",
        latest=True,
        stage="closeout",
        manifest_updates={
            "status": "approved",
            "feature_state": "Archived",
            "feature_path_at_closeout": "planning-mds/features/archive/F0001-new",
            "recorded_on": "2026-05-19",
            "changed_paths": ["../leak", "planning-mds/features/F0001-new"],
            "waivers": {
                "validator_defect": {
                    "defect_description": "FP",
                    "affected_rule_ids": ["manifest_changed_path_traversal_fails"],
                    "approved_by": "PM",
                    "approved_on": "2026-05-19",
                    "follow_up_owner": "framework-team",
                    "follow_up_target_date": "2026-04-01",  # before recorded_on
                }
            },
        },
    )
    pm = run_folder / "pm-closeout.md"
    pm.write_text(
        ROLE_FILES["pm-closeout.md"]
        + "\n- Accepted: manifest_changed_path_traversal_fails — mitigation: see notes\n",
        encoding="utf-8",
    )

    result = run_validator(product, "--feature", "F0001", "--stage", "closeout", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    # Original error stays because the waiver is invalid.
    assert "manifest_changed_path_traversal_fails" in rules

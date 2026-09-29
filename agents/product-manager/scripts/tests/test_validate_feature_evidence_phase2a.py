"""Phase 2a tests for `validate-feature-evidence.py`.

Covers single-run validator checks landed in Phase 2a:
- Required artifact presence (§10) with stage-aware matrix (§17)
- Required-heading presence (§14)
- Manifest schema depth (§11) — paths, booleans, waivers, rerun_of
- gate-decisions row presence per stage (§17 matrix)
- commands.log JSONL + secret-pattern scanning (§13)
- §15 PM Acceptance Line Format parser
- effective_date_overridden_warns
- Two-approved supersession rule
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from test_validate_feature_evidence import (
    REPO_ROOT,
    RUN_ID,
    BASE_FILES,
    ROLE_FILES,
    json_result,
    run_validator,
    write_manifest_run,
    write_registry,
    write_artifacts,
)


def test_pm_acceptance_line_format_parser_passes() -> None:
    """Validates the parser via direct import — exercises all four identifier
    shapes and both separator/keyword variants per §15."""
    import importlib.util
    import sys

    path = REPO_ROOT / "agents" / "product-manager" / "scripts" / "validate-feature-evidence.py"
    spec = importlib.util.spec_from_file_location("vfe", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["vfe"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    content = """# PM Closeout

## Recommendation Acceptances

- Accepted: coverage — Waived because doc-only; 2026-05-19
- Accepted: manifest_changed_path_traversal_fails - validator defect; mitigation: 2026-06-15
- accepted: custom-product-waiver — extension key; 2026-05-19
- ACCEPTED: REC-042 — mitigation: see release notes
"""
    entries = module.parse_pm_acceptance_lines(content)
    identifiers = [entry.identifier for entry in entries]
    assert "coverage" in identifiers
    assert "manifest_changed_path_traversal_fails" in identifiers
    assert "custom-product-waiver" in identifiers
    assert "REC-042" in identifiers


def test_missing_g0_artifact_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(product, "F0001-new", "F0001")
    (run_folder / "g0-assembly-plan-validation.md").unlink()

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    assert result.returncode == 1
    payload = json_result(result)
    rules = {entry["rule_id"] for entry in payload["errors"]}
    assert "missing_g0_fails" in rules


def test_runtime_true_missing_preflight_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        stage="G1",
        manifest_updates={"runtime_bearing": True},
    )
    # Remove g1-runtime-preflight.md to provoke the rule.
    (product / "planning-mds" / "operations" / "evidence" / "runs" / RUN_ID / "g1-runtime-preflight.md").unlink()

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G1", "--json")
    assert result.returncode == 1
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "runtime_true_missing_preflight_fails" in rules


def test_missing_readme_heading_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(product, "F0001-new", "F0001")
    (run_folder / "README.md").write_text("# Run Summary\n", encoding="utf-8")

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    assert result.returncode == 1
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "missing_readme_heading_fails" in rules


def test_action_context_wrong_feature_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(product, "F0001-new", "F0001")
    (run_folder / "action-context.md").write_text(
        "# Action Context\n\n## Run Identity\n\nFeature: F9999\n\n## Inputs\n\n## Assumptions\n\n## Scope Boundaries\n\n## Lifecycle Stage\n",
        encoding="utf-8",
    )

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "action_context_wrong_feature_fails" in rules


def test_changed_path_traversal_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        manifest_updates={"changed_paths": ["../etc/passwd"]},
    )

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "manifest_changed_path_traversal_fails" in rules


def test_changed_path_absolute_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        manifest_updates={"changed_paths": ["/etc/passwd"]},
    )

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "manifest_changed_path_absolute_fails" in rules


def test_file_path_absolute_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        manifest_updates={"files": {"readme": "/etc/passwd"}},
    )

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "manifest_file_path_absolute_fails" in rules


def test_scm_diff_path_malformed_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        manifest_updates={"scm": {"base_ref": "main", "head_ref": "feature/F0001", "diff_artifact": "../leak.txt"}},
    )

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "manifest_scm_diff_path_malformed_fails" in rules


def test_empty_changed_paths_without_rerun_of_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        manifest_updates={"changed_paths": [], "rerun_of": None},
    )

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "manifest_empty_changed_paths_without_rerun_of_fails" in rules


def test_evidence_only_rerun_with_rerun_of_passes(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    # Seed a prior approved run so manifest_rerun_of_unknown_run_fails does not fire.
    prior_run_id = "2026-05-15-aaaa1111"
    write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        run_id=prior_run_id,
        status="approved",
    )
    write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        manifest_updates={
            "changed_paths": [],
            "rerun_of": prior_run_id,
            "scm": {"base_ref": "main", "head_ref": "feature/F0001", "diff_artifact": ""},
        },
    )

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    assert result.returncode == 0, result.stdout


def test_missing_runtime_boolean_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(product, "F0001-new", "F0001")
    manifest = json.loads((run_folder / "evidence-manifest.json").read_text(encoding="utf-8"))
    manifest.pop("runtime_bearing")
    (run_folder / "evidence-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "manifest_missing_runtime_boolean_fails" in rules


def test_unknown_waiver_key_without_pm_acceptance_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        manifest_updates={"waivers": {"custom_thing": {"reason": "x", "owner": "PM", "approved_on": "2026-05-19"}}},
    )

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "manifest_unknown_waiver_key_without_pm_acceptance_fails" in rules


def test_unknown_waiver_key_with_pm_acceptance_passes(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        stage="closeout",
        status="approved",
        latest=True,
        manifest_updates={
            "status": "approved",
            "feature_state": "Archived",
            "feature_path_at_closeout": "planning-mds/features/archive/F0001-new",
            "waivers": {"custom_thing": {"reason": "x", "owner": "PM", "approved_on": "2026-05-19"}},
        },
    )
    pm_closeout = run_folder / "pm-closeout.md"
    pm_closeout.write_text(
        ROLE_FILES["pm-closeout.md"] + "\n- Accepted: custom_thing — extension key approved 2026-05-19\n",
        encoding="utf-8",
    )

    result = run_validator(product, "--feature", "F0001", "--stage", "closeout", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "manifest_unknown_waiver_key_without_pm_acceptance_fails" not in rules


def test_gate_decisions_missing_stage_required_row_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(product, "F0001-new", "F0001", stage="G2")
    (run_folder / "gate-decisions.md").write_text(
        "# Gate Decisions\n\n| Gate | Decision | Decider | Timestamp | Rationale | Blocking | Follow-up |\n|---|---|---|---|---|---|---|\n| G0 | PASS | role | 2026-05-19 | ok | No | - |\n",
        encoding="utf-8",
    )
    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G2", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "gate_decisions_missing_stage_required_row_fails" in rules


def test_commands_log_malformed_json_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(product, "F0001-new", "F0001")
    (run_folder / "commands.log").write_text("{not json\n", encoding="utf-8")

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "commands_log_malformed_json_fails" in rules


def test_commands_log_missing_exit_code_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(product, "F0001-new", "F0001")
    (run_folder / "commands.log").write_text(
        json.dumps({"schema_version": 1, "timestamp": "2026-05-19T12:00:00Z", "cwd": "{NEBULA_PRODUCT_ROOT}", "command": "ok", "artifacts": [], "redactions": []}) + "\n",
        encoding="utf-8",
    )

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "commands_log_missing_exit_code_fails" in rules


def test_commands_log_empty_at_approved_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        stage="closeout",
        status="approved",
        latest=True,
        manifest_updates={
            "status": "approved",
            "feature_state": "Archived",
            "feature_path_at_closeout": "planning-mds/features/archive/F0001-new",
        },
    )
    (run_folder / "commands.log").write_text("", encoding="utf-8")

    result = run_validator(product, "--feature", "F0001", "--stage", "closeout", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "commands_log_empty_at_approved_fails" in rules


def test_commands_log_secret_pattern_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(product, "F0001-new", "F0001")
    (run_folder / "commands.log").write_text(
        json.dumps({
            "schema_version": 1,
            "timestamp": "2026-05-19T12:00:00Z",
            "cwd": "{NEBULA_PRODUCT_ROOT}",
            "command": "curl -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1MSJ9.abc123def456'",
            "exit_code": 0,
            "artifacts": [],
            "redactions": [],
        }) + "\n",
        encoding="utf-8",
    )

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "commands_log_secret_pattern_fails" in rules


def test_commands_log_secret_patterns_redacted_passes(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(product, "F0001-new", "F0001")
    (run_folder / "commands.log").write_text(
        json.dumps({
            "schema_version": 1,
            "timestamp": "2026-05-19T12:00:00Z",
            "cwd": "{NEBULA_PRODUCT_ROOT}",
            "command": "curl -H 'Authorization: Bearer ***REDACTED***' --token=$BEARER_TOKEN",
            "exit_code": 0,
            "artifacts": [],
            "redactions": ["Authorization"],
        }) + "\n",
        encoding="utf-8",
    )

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "commands_log_secret_pattern_fails" not in rules


def test_commands_log_absolute_cwd_warns(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(product, "F0001-new", "F0001")
    (run_folder / "commands.log").write_text(
        json.dumps({
            "schema_version": 1,
            "timestamp": "2026-05-19T12:00:00Z",
            "cwd": "/absolute/path",
            "command": "ok",
            "exit_code": 0,
            "artifacts": [],
            "redactions": [],
        }) + "\n",
        encoding="utf-8",
    )

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    warnings = {entry["rule_id"] for entry in json_result(result)["warnings"]}
    assert "commands_log_absolute_cwd_warns" in warnings


def test_commands_log_absolute_cwd_justified_passes(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(product, "F0001-new", "F0001")
    (run_folder / "commands.log").write_text(
        json.dumps({
            "schema_version": 1,
            "timestamp": "2026-05-19T12:00:00Z",
            "cwd": "/absolute/path",
            "command": "ok",
            "exit_code": 0,
            "artifacts": [],
            "redactions": [],
        }) + "\n",
        encoding="utf-8",
    )
    (run_folder / "artifact-trace.md").write_text(
        BASE_FILES["artifact-trace.md"]
        + "\n## Run Environment\n\n- Absolute cwd: /absolute/path — explained by sandboxed CI runner\n",
        encoding="utf-8",
    )

    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    warnings = {entry["rule_id"] for entry in json_result(result)["warnings"]}
    assert "commands_log_absolute_cwd_warns" not in warnings


def test_effective_date_overridden_warns(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product)
    result = run_validator(product, "--evidence-effective-date", "2026-05-20", "--json")
    assert result.returncode == 0
    warnings = {entry["rule_id"] for entry in json_result(result)["warnings"]}
    assert "effective_date_overridden_warns" in warnings


def test_two_approved_runs_without_supersession_fires(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        run_id="2026-05-19-aaaa1111",
        status="approved",
        stage="closeout",
        manifest_updates={
            "status": "approved",
            "feature_state": "Archived",
            "feature_path_at_closeout": "planning-mds/features/archive/F0001-new",
        },
    )
    write_manifest_run(
        product,
        "F0001-new",
        "F0001",
        run_id=RUN_ID,
        status="approved",
        latest=True,
        stage="closeout",
        manifest_updates={
            "status": "approved",
            "feature_state": "Archived",
            "feature_path_at_closeout": "planning-mds/features/archive/F0001-new",
        },
    )

    result = run_validator(product, "--feature", "F0001", "--stage", "closeout", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "two_approved_runs_without_supersession_fails" in rules


def test_manifest_final_approved_with_non_terminal_state_fires(tmp_path: Path) -> None:
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
            "feature_state": "Draft",
            "feature_path_at_closeout": "planning-mds/features/archive/F0001-new",
        },
    )

    result = run_validator(product, "--feature", "F0001", "--stage", "closeout", "--json")
    rules = {entry["rule_id"] for entry in json_result(result)["errors"]}
    assert "manifest_final_approved_with_non_terminal_state_fails" in rules


def test_complete_runtime_feature_passes_at_closeout(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | Runtime Feature | 2026-05-19 |  | `archive/F0001-runtime/` |")
    write_manifest_run(
        product,
        "F0001-runtime",
        "F0001",
        status="approved",
        latest=True,
        stage="closeout",
        manifest_updates={
            "runtime_bearing": True,
            "required_roles": ["Quality Engineer", "Code Reviewer", "DevOps"],
            "status": "approved",
            "feature_state": "Archived",
            "feature_path_at_closeout": "planning-mds/features/archive/F0001-runtime",
        },
    )

    result = run_validator(product, "--feature", "F0001", "--stage", "closeout", "--json")
    assert result.returncode == 0, result.stdout


def test_complete_security_sensitive_feature_passes_at_closeout(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | Sec Feature | 2026-05-19 |  | `archive/F0001-sec/` |")
    write_manifest_run(
        product,
        "F0001-sec",
        "F0001",
        status="approved",
        latest=True,
        stage="closeout",
        manifest_updates={
            "security_sensitive_scope": True,
            "required_roles": ["Quality Engineer", "Code Reviewer", "Security Reviewer"],
            "status": "approved",
            "feature_state": "Archived",
            "feature_path_at_closeout": "planning-mds/features/archive/F0001-sec",
        },
    )

    result = run_validator(product, "--feature", "F0001", "--stage", "closeout", "--json")
    assert result.returncode == 0, result.stdout

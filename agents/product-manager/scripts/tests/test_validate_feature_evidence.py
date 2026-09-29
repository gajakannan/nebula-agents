from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
VALIDATOR = REPO_ROOT / "agents" / "product-manager" / "scripts" / "validate-feature-evidence.py"
FIXTURE_ROOT = REPO_ROOT / "agents" / "product-manager" / "scripts" / "tests" / "fixtures" / "feature-evidence"
RUN_ID = "2026-05-19-5ab6f922"


def latest_run_path(product_root: Path, feature_slug: str) -> Path:
    return product_root / "planning-mds" / "operations" / "evidence" / "features" / feature_slug / "latest-run.json"


def run_validator(product_root: Path | None, *args: str) -> subprocess.CompletedProcess[str]:
    command = ["python3", str(VALIDATOR)]
    if product_root is not None:
        command.extend(["--product-root", str(product_root)])
    command.extend(args)
    return subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, check=False)


def json_result(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return json.loads(result.stdout)


def assert_rule(result: subprocess.CompletedProcess[str], rule_id: str, code: int) -> None:
    """For invocation `_fails` (exit 2), expect exactly one error.
    For content `_fails` (exit 1), the validator continues after each failure
    and may surface more errors — assert the named rule is present."""
    assert result.returncode == code, result.stdout + result.stderr
    payload = json_result(result)
    ids = [item["rule_id"] for item in payload["errors"]]
    if code == 2:
        assert ids == [rule_id], ids
    else:
        assert rule_id in ids, ids


def write_registry(product_root: Path, *, active: str = "", archived: str = "", retired: str = "") -> None:
    features = product_root / "planning-mds" / "features"
    features.mkdir(parents=True, exist_ok=True)
    (features / "REGISTRY.md").write_text(
        f"""# Feature Registry

## Active Features

| Feature ID | Name | Status | Phase | Folder |
|------------|------|--------|-------|--------|
{active}

## Planned (Reserved IDs)

| Feature ID | Name | Status | Phase | Folder |
|------------|------|--------|-------|--------|

## Archived Features

| Feature ID | Name | Archived Date | Evidence Reentry Date | Folder |
|------------|------|---------------|-----------------------|--------|
{archived}

## Retired Features

| Feature ID | Name | Terminal Status | Superseded By | Retired Date | Folder | Reason |
|------------|------|-----------------|---------------|--------------|--------|--------|
{retired}
""",
        encoding="utf-8",
    )


def write_status(feature_path: Path, closeout_date: str) -> None:
    feature_path.mkdir(parents=True, exist_ok=True)
    (feature_path / "STATUS.md").write_text(
        f"""# Status

**Overall Status:** Done

## Closeout Summary

| Field | Value |
|-------|-------|
| Closeout review date | {closeout_date} |
""",
        encoding="utf-8",
    )


BASE_FILES = {
    "README.md": "# Run Summary\n\n## Status\n\n## Evidence Index\n\n## Validation Summary\n\n## Open Follow-ups\n",
    "action-context.md": "# Action Context\n\n## Run Identity\n\nFeature: {feature_id}\nRun: {run_id}\n\n## Inputs\n\n## Assumptions\n\n## Scope Boundaries\n\n## Lifecycle Stage\n",
    "artifact-trace.md": "# Artifact Trace\n\n## Artifacts Read\n\n## Artifacts Created Or Updated\n\n## Generated Evidence\n\n## External Or Global Evidence References\n\n## Omissions And Waivers\n",
    "gate-decisions.md": "# Gate Decisions\n\n| Gate | Decision | Decider | Timestamp | Rationale | Blocking | Follow-up |\n|---|---|---|---|---|---|---|\n| G0 | PASS | Architect | 2026-05-19 | ok | No | - |\n",
    "commands.log": "",
    "lifecycle-gates.log": "# Lifecycle Gate Run\n\n## Command\n\nvalidate-trackers.py\n\n## Stage\n\nG8\n\n## Exit Code\n\n0\n\n## Result\n\ntracker-sync PASS\n\n## Output References\n\n## Skipped Gates\n",
    "g0-assembly-plan-validation.md": "# G0\n\nResult: PASS\n",
}

ROLE_FILES = {
    "g1-runtime-preflight.md": "# G1\n\nResult: PASS\n",
    "g2-self-review.md": "# G2 Self Review\n\n## Scope Review\n\n## Acceptance Criteria Review\n\n## Implementation Risks\n\n## Validation Evidence\n\nResult: PASS\n",
    "test-plan.md": "# Test Plan\n\nResult: PASS\n",
    "test-execution-report.md": "# Test Execution\n\nResult: PASS\n",
    "coverage-report.md": "# Coverage\n\nResult: PASS\n",
    "deployability-check.md": "# Deployability\n\nResult: PASS\n",
    "code-review-report.md": "# Code Review\n\nResult: APPROVED\n",
    "security-review-report.md": "# Security Review\n\nResult: PASS\n",
    "signoff-ledger.md": "# Signoff\n\n## Required Role Matrix\n\n## Current Signoff State\n\n## Recommendation Acceptances\n\n## Waivers And Omissions\n\nResult: PASS\n",
    "feature-action-execution.md": "# Feature Action Execution\n\n## Gate\n\n## Execution Timeline\n",
    "pm-closeout.md": "# PM Closeout\n\n## Final Story Status\n\n## Archive Decision\n\n## Deferred Follow-ups\n\n## Recommendation Acceptances\n\n## Tracker Updates\n\n## Validator Results\n\nResult: APPROVED\n",
}


def default_gate_results(stage: str, runtime_bearing: bool) -> dict[str, Any]:
    gates: dict[str, Any] = {
        "assembly_plan_validation": {"required": True, "result": "PASS", "artifact": "g0-assembly-plan-validation.md"},
    }
    if runtime_bearing:
        gates["runtime_preflight"] = {"required": True, "result": "PASS", "artifact": "g1-runtime-preflight.md"}
    if stage in {"G2", "G3", "G5", "G6", "G8", "closeout"}:
        gates["self_review"] = {"required": True, "result": "PASS", "artifact": "g2-self-review.md"}
        gates["deployability"] = {"required": True, "result": "PASS", "artifact": "deployability-check.md"}
    if stage in {"G5", "G6", "G8", "closeout"}:
        gates["signoff"] = {"required": True, "result": "PASS", "artifact": "signoff-ledger.md"}
    if stage in {"G8", "closeout"}:
        gates["pm_closeout"] = {"required": True, "result": "APPROVED", "artifact": "pm-closeout.md"}
        gates["tracker_sync"] = {"required": True, "result": "PASS", "artifact": "lifecycle-gates.log"}
    return gates


def default_role_results(stage: str, manifest: dict[str, Any]) -> dict[str, Any]:
    roles: dict[str, Any] = {}
    runtime_bearing = bool(manifest.get("runtime_bearing"))
    security = bool(manifest.get("security_sensitive_scope")) or "Security Reviewer" in manifest.get("required_roles", [])
    devops = bool(manifest.get("deployment_config_changed")) or "DevOps" in manifest.get("required_roles", [])
    if stage in {"G2", "G3", "G5", "G6", "G8", "closeout"}:
        roles["Quality Engineer"] = {
            "required": True,
            "result": "PASS",
            "required_artifacts": ["test-plan.md", "test-execution-report.md", "coverage-report.md"],
            "verdict_artifact": "test-execution-report.md",
        }
    if stage in {"G3", "G5", "G6", "G8", "closeout"}:
        roles["Code Reviewer"] = {
            "required": True,
            "result": "APPROVED",
            "required_artifacts": ["code-review-report.md"],
            "verdict_artifact": "code-review-report.md",
        }
        if security:
            roles["Security Reviewer"] = {
                "required": True,
                "result": "PASS",
                "required_artifacts": ["security-review-report.md"],
                "verdict_artifact": "security-review-report.md",
            }
    if devops and stage in {"G2", "G3", "G5", "G6", "G8", "closeout"}:
        artifacts = ["deployability-check.md"]
        if runtime_bearing:
            artifacts = ["g1-runtime-preflight.md", "deployability-check.md"]
        roles["DevOps"] = {
            "required": True,
            "result": "PASS",
            "required_artifacts": artifacts,
            "verdict_artifact": "deployability-check.md",
        }
    return roles


def write_status_md(feature_path: Path, feature_id: str, run_folder_rel: str, required_roles: list[str], stage: str = "closeout") -> None:
    """Write a STATUS.md with a Required Role Matrix + one current passing row per role for a single story."""
    feature_path.mkdir(parents=True, exist_ok=True)
    matrix = "\n".join(f"| {role} | Yes |" for role in required_roles)
    if stage in {"G5", "G6", "G8", "closeout"}:
        rows = "\n".join(
            f"| {feature_id}-S0001 | {role} | reviewer | PASS | {run_folder_rel}/test-execution-report.md | 2026-05-19 | - |"
            for role in required_roles
        )
    else:
        rows = ""
    (feature_path / "STATUS.md").write_text(
        f"""# Status

**Overall Status:** Done

## Required Role Matrix

| Role | Required |
|------|----------|
{matrix}

## Story Signoff Provenance

| Story | Role | Reviewer | Verdict | Evidence | Date | Notes |
|-------|------|----------|---------|----------|------|-------|
{rows}
""",
        encoding="utf-8",
    )


def write_manifest_run(
    product_root: Path,
    feature_slug: str,
    feature_id: str,
    run_id: str = RUN_ID,
    *,
    status: str = "in-progress",
    latest: bool = False,
    manifest_updates: dict[str, Any] | None = None,
    stage: str = "G0",
) -> Path:
    run_folder = product_root / "planning-mds" / "operations" / "evidence" / "runs" / run_id
    run_folder.mkdir(parents=True, exist_ok=True)
    feature_index_root = product_root / "planning-mds" / "operations" / "evidence" / "features" / feature_slug
    feature_index_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "feature_id": feature_id,
        "feature_slug": feature_slug.removeprefix(f"{feature_id}-"),
        "run_id": run_id,
        "status": status,
        "recorded_on": "2026-05-19",
        "contract_effective_date": "2026-05-19",
        "feature_path_at_run_start": f"planning-mds/features/{feature_slug}",
        "feature_path_at_closeout": None,
        "feature_state": "In Progress",
        "rerun_of": None,
        "changed_paths": [f"planning-mds/features/{feature_slug}"],
        "scm": {"base_ref": "main", "head_ref": f"feature/{feature_id}", "diff_artifact": "artifacts/diffs/changed-files.txt"},
        "runtime_bearing": False,
        "deployment_config_changed": False,
        "frontend_in_scope": False,
        "security_sensitive_scope": False,
        "required_roles": ["Quality Engineer", "Code Reviewer"],
        "gate_results": {},
        "files": {},
        "role_results": {},
        "omissions": [],
        "waivers": {},
        "global_evidence_refs": {},
    }
    if manifest_updates:
        manifest.update(manifest_updates)
    manifest.setdefault("gate_results", {})
    manifest.setdefault("role_results", {})
    if not manifest["gate_results"]:
        manifest["gate_results"] = default_gate_results(stage, bool(manifest.get("runtime_bearing")))
    if not manifest["role_results"]:
        manifest["role_results"] = default_role_results(stage, manifest)
    if bool(manifest.get("security_sensitive_scope")) and "Security Reviewer" not in manifest["required_roles"]:
        manifest["required_roles"] = manifest["required_roles"] + ["Security Reviewer"]
    if bool(manifest.get("deployment_config_changed")) and "DevOps" not in manifest["required_roles"]:
        manifest["required_roles"] = manifest["required_roles"] + ["DevOps"]
    (run_folder / "evidence-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_artifacts(run_folder, manifest, stage=stage)
    # Write the §11 scm.diff_artifact so cross-artifact checks pass when
    # changed_paths is populated. The diff artifact file path is run-folder relative.
    diff_artifact = manifest.get("scm", {}).get("diff_artifact") if isinstance(manifest.get("scm"), dict) else None
    if diff_artifact:
        diff_path = run_folder / diff_artifact
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        diff_path.write_text(
            "\n".join(str(p) for p in manifest.get("changed_paths", []) if isinstance(p, str)) + "\n",
            encoding="utf-8",
        )
    if stage in {"G5", "G6", "G8", "closeout"}:
        # Honor the registry's `Folder` column when the closeout path is archived.
        closeout = manifest.get("feature_path_at_closeout") or f"planning-mds/features/{feature_slug}"
        feature_path = product_root / closeout
        run_folder_rel = f"planning-mds/operations/evidence/runs/{run_id}"
        write_status_md(feature_path, feature_id, run_folder_rel, manifest["required_roles"], stage=stage)
        # Refresh signoff-ledger.md so it references the rows we just wrote — §21
        # validate_signoff_ledger_consistency would otherwise fire.
        ledger_rows = "\n".join(
            f"- {feature_id}-S0001 / {role}: PASS by reviewer on 2026-05-19"
            for role in manifest["required_roles"]
        )
        (run_folder / "signoff-ledger.md").write_text(
            f"# Signoff\n\n## Required Role Matrix\n\n## Current Signoff State\n\n{ledger_rows}\n\n## Recommendation Acceptances\n\n## Waivers And Omissions\n\nResult: PASS\n",
            encoding="utf-8",
        )
    if latest:
        latest_payload = {
            "schema_version": 1,
            "feature_id": feature_id,
            "run_id": run_id,
            "run_path": f"planning-mds/operations/evidence/runs/{run_id}",
            "manifest_path": f"planning-mds/operations/evidence/runs/{run_id}/evidence-manifest.json",
            "status": "approved",
            "approved_on": "2026-05-19",
        }
        (feature_index_root / "latest-run.json").write_text(json.dumps(latest_payload, indent=2), encoding="utf-8")
    return run_folder


def write_artifacts(run_folder: Path, manifest: dict[str, Any], stage: str = "G0") -> None:
    """Write the §10/§17 minimum artifact set for the requested stage."""
    feature_id = manifest["feature_id"]
    run_id = manifest["run_id"]
    for name, template in BASE_FILES.items():
        (run_folder / name).write_text(template.format(feature_id=feature_id, run_id=run_id), encoding="utf-8")

    if manifest.get("status") == "approved":
        log_line = json.dumps({
            "schema_version": 1,
            "timestamp": "2026-05-19T12:00:00-04:00",
            "cwd": "{NEBULA_PRODUCT_ROOT}",
            "command": "echo ok",
            "exit_code": 0,
            "artifacts": [],
            "redactions": [],
        })
        (run_folder / "commands.log").write_text(log_line + "\n", encoding="utf-8")

    gate_rows = ["G0"]
    if stage in {"G1", "G2", "G3", "G5", "G6", "G8", "closeout"}:
        gate_rows.append("G1")
    if stage in {"G2", "G3", "G5", "G6", "G8", "closeout"}:
        gate_rows.append("G2")
    if stage in {"G3", "G5", "G6", "G8", "closeout"}:
        gate_rows.append("G3")
    if stage in {"G5", "G6", "G8", "closeout"}:
        gate_rows.append("G4")
        gate_rows.append("G5")
    if stage in {"G6", "G8", "closeout"}:
        gate_rows.append("G6")
    if stage in {"G8", "closeout"}:
        gate_rows.append("G8")
    header = "# Gate Decisions\n\n| Gate | Decision | Decider | Timestamp | Rationale | Blocking | Follow-up |\n|---|---|---|---|---|---|---|\n"
    body = "".join(f"| {gate} | PASS | role | 2026-05-19 | ok | No | - |\n" for gate in gate_rows)
    (run_folder / "gate-decisions.md").write_text(header + body, encoding="utf-8")

    extra: list[str] = []
    if manifest.get("runtime_bearing"):
        extra.append("g1-runtime-preflight.md")
    if stage in {"G2", "G3", "G5", "G6", "G8", "closeout"}:
        extra += ["g2-self-review.md", "test-plan.md", "test-execution-report.md", "coverage-report.md", "deployability-check.md"]
    if stage in {"G3", "G5", "G6", "G8", "closeout"}:
        extra.append("code-review-report.md")
        if manifest.get("security_sensitive_scope") or "Security Reviewer" in manifest.get("required_roles", []):
            extra.append("security-review-report.md")
    if stage in {"G5", "G6", "G8", "closeout"}:
        extra.append("signoff-ledger.md")
    if stage in {"G6", "G8", "closeout"}:
        extra.append("feature-action-execution.md")
    if stage in {"G8", "closeout"}:
        extra.append("pm-closeout.md")
    for filename in extra:
        (run_folder / filename).write_text(ROLE_FILES[filename], encoding="utf-8")


def test_invocation_failures_emit_single_json_error(tmp_path: Path) -> None:
    product = tmp_path / "product"
    product.mkdir()
    write_registry(product)

    assert_rule(run_validator(product / "missing", "--json"), "cli_product_root_invalid_fails", 2)
    assert_rule(run_validator(product, "--run-id", "bad", "--json"), "cli_run_id_malformed_fails", 2)
    assert_rule(run_validator(product, "--json", "--json-out", str(tmp_path / "out.json")), "cli_json_flags_conflict_fails", 2)
    assert_rule(
        run_validator(product, "--evidence-effective-date", "2026-05-18", "--json"),
        "effective_date_override_earlier_than_default_fails",
        2,
    )
    assert_rule(run_validator(tmp_path / "no-registry", "--json"), "cli_product_root_invalid_fails", 2)


def test_registry_missing_is_invocation_failure(tmp_path: Path) -> None:
    product = tmp_path / "product"
    (product / "planning-mds" / "features").mkdir(parents=True)

    assert_rule(run_validator(product, "--json"), "registry_missing_fails", 2)


def test_secret_pattern_preconditions(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product)
    evidence = product / "planning-mds" / "operations" / "evidence"
    evidence.mkdir(parents=True)

    (evidence / "secret_patterns.json").write_text("{", encoding="utf-8")
    assert_rule(run_validator(product, "--json"), "secret_patterns_unloadable_fails", 2)

    (evidence / "secret_patterns.json").write_text(json.dumps({"bearer_token": {"type": "regex", "pattern": "x"}}), encoding="utf-8")
    assert_rule(run_validator(product, "--json"), "secret_patterns_conflict_fails", 2)

    (evidence / "secret_patterns.json").write_text(
        json.dumps({"custom_scanner": {"type": "multi_line_scanner", "secondary_match_classes": ["custom_scanner"]}}),
        encoding="utf-8",
    )
    assert_rule(run_validator(product, "--json"), "secret_patterns_invalid_secondary_class_fails", 2)


def test_path_class_extension_conflict(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product)
    evidence = product / "planning-mds" / "operations" / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "README.md").write_text(
        """# Evidence

## Path Class Extensions

| Path class (glob) | Forces |
|---|---|
| `engine/**` | `frontend_in_scope = true` |
""",
        encoding="utf-8",
    )

    assert_rule(run_validator(product, "--json"), "path_class_extension_conflict_fails", 2)


def test_registry_section_and_feature_lookup_failures(tmp_path: Path) -> None:
    product = tmp_path / "product"
    features = product / "planning-mds" / "features"
    features.mkdir(parents=True)
    (features / "REGISTRY.md").write_text("# Feature Registry\n\n## Active Features\n\n", encoding="utf-8")

    assert_rule(run_validator(product, "--json"), "registry_required_section_missing_fails", 1)

    write_registry(product)
    assert_rule(run_validator(product, "--feature", "F9999", "--json"), "feature_not_in_registry_fails", 2)


def test_eligibility_skip_counts_and_explicit_target_info(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(
        product,
        active="| F0001 | Draft Feature | Draft | MVP | `F0001-draft/` |",
        archived="| F0002 | Old Feature | 2026-05-18 |  | `archive/F0002-old/` |",
        retired=(
            "| F0003 | Abandoned Feature | Abandoned |  | 2026-05-20 |  | No longer needed |\n"
            "| F0004 | Superseded Feature | Superseded | F0005 | 2026-05-20 | `archive/F0004-old/` | Replaced |"
        ),
    )

    broad = run_validator(product, "--json")
    assert broad.returncode == 0, broad.stdout
    payload = json_result(broad)
    assert payload["features_skipped_pre_contract_archived"] == 1
    assert payload["features_skipped_retired_abandoned"] == 1
    assert payload["features_skipped_retired_superseded"] == 1
    assert payload["features_validated"] == 0

    retired = run_validator(product, "--feature", "F0003", "--json")
    assert retired.returncode == 0
    assert json_result(retired)["info"][0]["rule_id"] == "retired_feature_explicit_target_info"

    archived = run_validator(product, "--feature", "F0002", "--json")
    assert archived.returncode == 0
    assert json_result(archived)["info"][0]["rule_id"] == "pre_contract_archived_explicit_target_info"


def test_active_done_pre_contract_skip_warns(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, active="| F0001 | Done Feature | Done | MVP | `F0001-done/` |")
    write_status(product / "planning-mds" / "features" / "F0001-done", "2026-05-18")

    result = run_validator(product, "--json")

    assert result.returncode == 0
    payload = json_result(result)
    assert payload["features_skipped_active_done_pre_contract"] == 1
    assert payload["warnings"][0]["rule_id"] == "active_done_pre_contract_parseable_skip_warns"


def test_eligibility_missing_evidence_failures(tmp_path: Path) -> None:
    product = tmp_path / "product"

    write_registry(product, archived="| F0001 | Missing Date | TBD |  | `archive/F0001-missing-date/` |")
    assert_rule(run_validator(product, "--feature", "F0001", "--json"), "archived_missing_date_fails", 1)

    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    assert_rule(run_validator(product, "--feature", "F0001", "--json"), "post_contract_archived_missing_evidence_fails", 1)

    write_registry(product, active="| F0002 | Done Feature | Done | MVP | `F0002-done/` |")
    assert_rule(run_validator(product, "--feature", "F0002", "--json"), "active_done_post_contract_missing_evidence_fails", 1)


def test_stage_resolution_and_manifest_phase_one_rules(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    write_manifest_run(product, "F0001-new", "F0001")

    assert run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json").returncode == 0
    assert_rule(run_validator(product, "--feature", "F0001", "--stage", "G0", "--json"), "stage_without_run_id_before_g6_fails", 1)
    assert_rule(
        run_validator(product, "--feature", "F0001", "--run-id", "2026-05-19-aaaaaaaa", "--stage", "G0", "--json"),
        "run_folder_not_found_fails",
        1,
    )
    assert_rule(run_validator(product, "--feature", "F0001", "--stage", "G6", "--json"), "stage_g6_without_run_id_or_latest_run_fails", 1)


def test_g6_latest_resolution_and_mismatch_rules(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    write_manifest_run(product, "F0001-new", "F0001", status="approved", latest=True, stage="G6")

    assert run_validator(product, "--feature", "F0001", "--stage", "G6", "--json").returncode == 0
    assert_rule(
        run_validator(product, "--feature", "F0001", "--stage", "G6", "--run-id", "2026-05-19-aaaaaaaa", "--json"),
        "stage_g6_run_id_mismatch_with_latest_run_fails",
        1,
    )
    assert_rule(
        run_validator(product, "--feature", "F0001", "--stage", "G8", "--run-id", "2026-05-19-aaaaaaaa", "--json"),
        "stage_g8_run_id_mismatch_fails",
        1,
    )


def test_closeout_requires_latest_run(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    write_manifest_run(product, "F0001-new", "F0001")

    assert_rule(run_validator(product, "--feature", "F0001", "--stage", "closeout", "--json"), "missing_latest_run_fails", 1)


def test_manifest_parse_and_schema_errors(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(product, "F0001-new", "F0001")
    (run_folder / "evidence-manifest.json").write_text("{", encoding="utf-8")
    assert_rule(
        run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json"),
        "manifest_unparseable_fails",
        1,
    )

    write_manifest_run(product, "F0001-new", "F0001", manifest_updates={"run_id": "bad"})
    assert_rule(
        run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json"),
        "manifest_bad_run_id_fails",
        1,
    )

    write_manifest_run(product, "F0001-new", "F0001", manifest_updates={"feature_id": "F0002"})
    assert_rule(
        run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json"),
        "manifest_feature_id_mismatch_fails",
        1,
    )

    write_manifest_run(product, "F0001-new", "F0001", manifest_updates={"schema_version": 99})
    assert_rule(
        run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json"),
        "manifest_bad_schema_version_fails",
        1,
    )


def test_is_terminal_active_uses_exact_match(tmp_path: Path) -> None:
    """`Not Done` / `Incomplete` / `Doneness` must NOT classify as terminal active."""
    product = tmp_path / "product"
    write_registry(
        product,
        active=(
            "| F0001 | Rolled Back | Not Done | MVP | `F0001-rb/` |\n"
            "| F0002 | Mid Build | Incomplete | MVP | `F0002-mb/` |\n"
            "| F0003 | Marketing | Doneness | MVP | `F0003-mk/` |\n"
            "| F0004 | Real Done | Done | MVP | `F0004-rd/` |"
        ),
    )
    write_status(product / "planning-mds" / "features" / "F0004-rd", "2026-05-18")

    result = run_validator(product, "--json")
    payload = json_result(result)
    # F0001/F0002/F0003 must not appear as governed or as active-done skips.
    assert payload["features_skipped_active_done_pre_contract"] == 1, payload
    assert payload["features_validated"] == 0, payload
    # No spurious errors from non-terminal statuses.
    for finding in payload["errors"]:
        assert finding["feature"] not in {"F0001", "F0002", "F0003"}, finding


def test_g6_unparseable_latest_with_run_id_does_not_emit_mismatch(tmp_path: Path) -> None:
    """Regression: when latest-run.json is unparseable but --run-id is supplied at G6,
    the validator must emit latest_run_wrong_manifest_fails (unloadable) and stop —
    not let the run_folder code path subsequently overwrite or hide that signal."""
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(product, "F0001-new", "F0001", status="approved", latest=True)
    latest_run_path(product, "F0001-new").write_text("{", encoding="utf-8")

    result = run_validator(product, "--feature", "F0001", "--stage", "G6", "--run-id", RUN_ID, "--json")
    payload = json_result(result)
    rules = [item["rule_id"] for item in payload["errors"]]
    assert "latest_run_wrong_manifest_fails" in rules, payload
    assert "stage_g6_run_id_mismatch_with_latest_run_fails" not in rules, payload
    assert result.returncode == 1


def test_missing_manifest_and_latest_wrong_manifest(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(product, "F0001-new", "F0001", status="approved", latest=True)
    (run_folder / "evidence-manifest.json").unlink()
    assert_rule(
        run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json"),
        "missing_manifest_fails",
        1,
    )
    assert_rule(run_validator(product, "--feature", "F0001", "--stage", "closeout", "--json"), "latest_run_wrong_manifest_fails", 1)


def test_phase_one_fixture_map_closure() -> None:
    mapping = json.loads((FIXTURE_ROOT / "rule-fixture-map.json").read_text(encoding="utf-8"))
    indexed_fixtures = set(json.loads((FIXTURE_ROOT / "fixture-index.json").read_text(encoding="utf-8")))
    assert mapping
    for rule_id, entry in mapping.items():
        assert entry["owner_phase"] in {"Phase 1", "Phase 2a", "Phase 2b"}, rule_id
        assert entry["status"] in {"active", "pending"}, rule_id
        if entry["owner_phase"] in {"Phase 1", "Phase 2a"}:
            assert entry["status"] == "active", rule_id
            assert entry["positive_fixtures"], rule_id
            assert entry["negative_fixtures"], rule_id
            for fixture in entry["positive_fixtures"] + entry["negative_fixtures"]:
                assert (FIXTURE_ROOT / fixture).exists() or fixture in indexed_fixtures, fixture


# Authoritative §23 fixture inventory. The closure test below asserts that
# every name in this list is either a directory on disk under FIXTURE_ROOT or
# present in fixture-index.json. Update this list when §23 changes.
SECTION_23_REQUIRED_FIXTURES: list[str] = [
    # §23 required positive fixtures
    "complete_runtime_feature_passes",
    "complete_non_runtime_doc_feature_passes",
    "complete_security_sensitive_feature_passes",
    "complete_deployment_changed_feature_passes",
    "active_done_post_contract_with_evidence_passes",
    "post_contract_archived_with_evidence_passes",
    "reopened_historical_with_evidence_passes",
    "pre_contract_archived_skipped_passes",
    "active_done_pre_contract_parseable_skip_warns",
    "active_in_progress_ignored_passes",
    "retired_abandoned_skipped_passes",
    "retired_superseded_skipped_passes",
    "with_recommendations_accepted_passes",
    "stage_g0_allows_later_reports_pending_passes",
    "stage_g6_candidate_with_run_id_before_latest_run_passes",
    "stage_g6_uses_latest_run_when_run_id_omitted_passes",
    "stage_g6_candidate_null_closeout_path_passes",
    "stage_closeout_after_tracker_results_passes",
    "evidence_only_rerun_with_rerun_of_passes",
    "prior_run_marked_superseded_on_new_approval_passes",
    "validator_defect_waiver_with_followup_passes",
    "validator_defect_waived_warns",
    "commands_log_absolute_cwd_justified_passes",
    "commands_log_secret_patterns_redacted_passes",
    "kg_generated_regeneration_command_passes",
    "pm_acceptance_line_format_parser_passes",
    "path_class_union_match_passes",
    "path_class_case_sensitive_no_match_passes",
    "retired_feature_explicit_target_info",
    "pre_contract_archived_explicit_target_info",

    # §23 required negative fixtures
    "missing_manifest_fails", "missing_latest_run_fails", "manifest_bad_run_id_fails",
    "manifest_feature_id_mismatch_fails", "manifest_required_roles_mismatch_fails",
    "manifest_required_artifact_omitted_fails", "manifest_unparseable_fails",
    "manifest_unknown_waiver_key_without_pm_acceptance_fails",
    "manifest_changed_path_traversal_fails", "manifest_file_path_absolute_fails",
    "manifest_file_path_traversal_fails", "manifest_scm_diff_path_malformed_fails",
    "stage_g6_run_id_mismatch_with_latest_run_fails", "cli_json_flags_conflict_fails",
    "cli_run_id_malformed_fails", "cli_product_root_invalid_fails",
    "feature_not_in_registry_fails", "registry_missing_fails",
    "registry_required_section_missing_fails", "secret_patterns_invalid_secondary_class_fails",
    "run_folder_not_found_fails", "commands_log_empty_at_approved_fails",
    "gate_decisions_missing_stage_required_row_fails",
    "post_contract_archived_missing_evidence_fails", "archived_missing_date_fails",
    "active_done_post_contract_missing_evidence_fails",
    "active_done_pre_contract_malformed_date_requires_evidence_fails",
    "runtime_true_missing_preflight_fails", "deployment_changed_without_devops_fails",
    "security_true_without_security_role_fails", "scope_boolean_false_with_changed_paths_fails",
    "frontend_global_substituted_for_feature_report_fails", "missing_g0_fails", "missing_g2_fails",
    "missing_deployability_fails", "missing_test_plan_fails", "missing_test_execution_fails",
    "missing_coverage_report_fails", "coverage_waiver_missing_pm_acceptance_fails",
    "missing_code_review_fails", "security_required_missing_report_fails",
    "signoff_ledger_disagrees_fails", "status_stale_pass_followed_by_fail_fails",
    "status_evidence_outside_package_fails", "recommendation_no_pm_acceptance_fails",
    "commands_log_malformed_json_fails", "commands_log_secret_pattern_fails",
    "secret_patterns_unloadable_fails", "secret_patterns_conflict_fails",
    "latest_run_wrong_manifest_fails", "stage_without_run_id_before_g6_fails",
    "stage_g6_without_run_id_or_latest_run_fails", "stage_no_sorted_run_inference_fails",
    "stage_g8_requires_tracker_results_fails", "pm_role_required_missing_report_fails",
    "kg_generated_regeneration_missing_fails",
    "gate_decisions_missing_g6_fails", "gate_decisions_missing_g8_fails",
    "manifest_rerun_of_unknown_run_fails", "manifest_empty_changed_paths_without_rerun_of_fails",
    "stage_g8_run_id_mismatch_fails", "manifest_final_approved_with_non_terminal_state_fails",
    "two_approved_runs_without_supersession_fails", "validator_defect_waiver_missing_followup_fails",

    # §23 additional inventory
    "missing_readme_heading_fails", "action_context_wrong_feature_fails", "artifact_trace_missing_global_ref_fails",
    "gate_decisions_missing_g5_fails", "lifecycle_gates_missing_exit_code_fails",
    "manifest_bad_schema_version_fails", "manifest_bad_status_fails", "manifest_bad_recorded_on_fails",
    "manifest_bad_effective_date_fails", "manifest_bad_start_path_fails", "manifest_closeout_path_missing_fails",
    "manifest_slug_mismatch_fails", "manifest_missing_changed_paths_fails", "manifest_changed_path_absolute_fails",
    "manifest_scm_diff_missing_fails", "changed_paths_missing_diff_entry_fails",
    "manifest_missing_runtime_boolean_fails", "manifest_missing_deploy_boolean_fails",
    "manifest_missing_frontend_boolean_fails", "manifest_missing_security_boolean_fails",
    "manifest_missing_gate_results_fails", "manifest_file_path_missing_fails",
    "manifest_role_results_mismatch_fails", "manifest_waiver_without_report_fails",
    "manifest_global_ref_missing_fails", "manifest_retired_state_fails",
    "latest_run_bad_status_fails", "latest_run_absolute_path_fails",
    "commands_log_missing_exit_code_fails", "commands_log_artifact_missing_fails",
    "command_artifact_missing_fails",
    "missing_feature_action_execution_fails", "missing_pm_closeout_fails",
    "coverage_claim_without_artifact_fails", "test_results_reference_missing_fails",
    "security_scan_reference_missing_fails", "screenshot_reference_missing_fails",
    "required_artifact_omitted_fails", "runtime_preflight_omitted_when_runtime_true_fails",
    "security_report_omitted_when_required_fails", "omission_filesystem_mismatch_fails",
    "recommendation_ambiguous_fails", "recommendation_missing_severity_fails",
    "recommendation_missing_owner_fails", "blocking_language_with_pass_fails",
    "recommendation_acceptance_mismatch_fails", "coverage_waiver_mismatch_fails",
    "deferred_blocker_passes_fails",
    "status_missing_baseline_role_fails", "status_missing_forced_role_fails",
    "status_evidence_missing_file_fails", "status_recommendation_without_acceptance_fails",
    "status_story_missing_role_fails", "status_bad_date_fails", "status_missing_reviewer_fails",
    "signoff_ledger_stale_fails",
    "reopened_historical_missing_evidence_fails",
    "frontend_true_without_feature_test_notes_fails", "frontend_global_ref_missing_fails",
    "frontend_quality_bad_latest_run_fails", "frontend_ux_ref_missing_fails",
    "feature_identity_mismatch_fails", "run_identity_mismatch_fails", "closeout_path_mismatch_fails",
    "required_roles_mismatch_fails", "role_verdict_mismatch_fails", "gate_verdict_mismatch_fails",
    "changed_paths_mismatch_fails",
    "status_story_value_bad_format_fails", "status_story_value_unknown_story_fails",
    "effective_date_override_earlier_than_default_fails", "effective_date_overridden_warns",
    "commands_log_absolute_cwd_warns",
    "path_class_extension_conflict_fails",
]


def test_section_23_inventory_closure() -> None:
    """§23 closure pivoted on the inventory itself. Every fixture listed in
    SECTION_23_REQUIRED_FIXTURES (mirroring §23 positive + negative + additional
    inventory) must exist as a directory under FIXTURE_ROOT *or* be present in
    fixture-index.json. This catches drift where a §23 fixture name has neither
    a placeholder dir nor a registered virtual name."""
    indexed = set(json.loads((FIXTURE_ROOT / "fixture-index.json").read_text(encoding="utf-8")))
    missing = [
        name for name in SECTION_23_REQUIRED_FIXTURES
        if not (FIXTURE_ROOT / name).exists() and name not in indexed
    ]
    assert not missing, f"§23 fixtures missing from disk AND fixture-index.json: {sorted(missing)!r}"


def test_section_23_inventory_has_no_typos() -> None:
    """Sanity: every §23 fixture name follows the `_passes`/`_fails`/`_warns`/`_info`
    suffix rule (§22 rule identification). Catches typos in the inventory."""
    allowed_suffixes = ("_passes", "_fails", "_warns", "_info")
    bad = [name for name in SECTION_23_REQUIRED_FIXTURES if not name.endswith(allowed_suffixes)]
    assert not bad, f"Fixture names with non-canonical suffix: {bad!r}"

"""Tests for the QE→Security `security_scans` handoff rule.

When `security_sensitive_scope` is true and the run adopts a contract effective
on/after SECURITY_SCANS_EFFECTIVE_DATE (2026-05-25), every required scan class
(dependency, secrets, sast, dast) must either have run with a resolvable
artifact or carry a complete in-line waiver (reason, owner, approved_on).
Earlier runs are exempt so pre-existing evidence packages stay valid.
"""

from __future__ import annotations

from pathlib import Path

from test_validate_feature_evidence import (
    RUN_ID,
    json_result,
    run_validator,
    write_manifest_run,
    write_registry,
)

LATE_DATE = "2026-05-25"


def _error_ids(product: Path) -> set[str]:
    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G0", "--json")
    return {entry["rule_id"] for entry in json_result(result)["errors"]}


def _complete_scans(run_folder: Path) -> dict:
    """A passing block: one class ran with a real artifact, the rest waived."""
    (run_folder / "artifacts" / "security").mkdir(parents=True, exist_ok=True)
    (run_folder / "artifacts" / "security" / "dependency-scan.log").write_text("ok\n", encoding="utf-8")
    waiver = {"reason": "scanner unavailable in env", "owner": "DevOps", "approved_on": LATE_DATE}
    return {
        "dependency": {"ran": True, "result": "findings", "artifact": "artifacts/security/dependency-scan.log", "waiver": None},
        "secrets": {"ran": False, "result": "not_run", "artifact": None, "waiver": dict(waiver)},
        "sast": {"ran": False, "result": "not_run", "artifact": None, "waiver": dict(waiver)},
        "dast": {"ran": False, "result": "not_run", "artifact": None, "waiver": dict(waiver, owner="QE")},
    }


def test_security_scans_missing_fails(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    write_manifest_run(
        product, "F0001-new", "F0001",
        manifest_updates={"security_sensitive_scope": True, "contract_effective_date": LATE_DATE},
    )
    assert "security_scans_missing_fails" in _error_ids(product)


def test_security_scan_class_missing_fails(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(
        product, "F0001-new", "F0001",
        manifest_updates={"security_sensitive_scope": True, "contract_effective_date": LATE_DATE},
    )
    scans = _complete_scans(run_folder)
    del scans["dast"]
    write_manifest_run(
        product, "F0001-new", "F0001",
        manifest_updates={"security_sensitive_scope": True, "contract_effective_date": LATE_DATE, "security_scans": scans},
    )
    assert "security_scan_class_missing_fails" in _error_ids(product)


def test_security_scan_unbacked_fails(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(
        product, "F0001-new", "F0001",
        manifest_updates={"security_sensitive_scope": True, "contract_effective_date": LATE_DATE},
    )
    scans = _complete_scans(run_folder)
    # Asserts a scan ran but points at an artifact that does not exist.
    scans["sast"] = {"ran": True, "result": "clean", "artifact": "artifacts/security/sast-semgrep.sarif", "waiver": None}
    write_manifest_run(
        product, "F0001-new", "F0001",
        manifest_updates={"security_sensitive_scope": True, "contract_effective_date": LATE_DATE, "security_scans": scans},
    )
    assert "security_scan_unbacked_fails" in _error_ids(product)


def test_security_scan_unwaived_skip_fails(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(
        product, "F0001-new", "F0001",
        manifest_updates={"security_sensitive_scope": True, "contract_effective_date": LATE_DATE},
    )
    scans = _complete_scans(run_folder)
    # Did not run and waiver is incomplete (missing owner + approved_on).
    scans["secrets"] = {"ran": False, "result": "not_run", "artifact": None, "waiver": {"reason": "no time"}}
    write_manifest_run(
        product, "F0001-new", "F0001",
        manifest_updates={"security_sensitive_scope": True, "contract_effective_date": LATE_DATE, "security_scans": scans},
    )
    assert "security_scan_unwaived_skip_fails" in _error_ids(product)


def test_security_scans_complete_passes(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run_folder = write_manifest_run(
        product, "F0001-new", "F0001",
        manifest_updates={"security_sensitive_scope": True, "contract_effective_date": LATE_DATE},
    )
    scans = _complete_scans(run_folder)
    write_manifest_run(
        product, "F0001-new", "F0001",
        manifest_updates={"security_sensitive_scope": True, "contract_effective_date": LATE_DATE, "security_scans": scans},
    )
    ids = _error_ids(product)
    assert not {
        "security_scans_missing_fails",
        "security_scan_class_missing_fails",
        "security_scan_unbacked_fails",
        "security_scan_unwaived_skip_fails",
    } & ids


def test_pre_effective_date_run_is_exempt(tmp_path: Path) -> None:
    """A security-sensitive run on the old contract date carries no
    security_scans block and must not trip the new rule."""
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    write_manifest_run(
        product, "F0001-new", "F0001",
        manifest_updates={"security_sensitive_scope": True, "contract_effective_date": "2026-05-19"},
    )
    assert "security_scans_missing_fails" not in _error_ids(product)

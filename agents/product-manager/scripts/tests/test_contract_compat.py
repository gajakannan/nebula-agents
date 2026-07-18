"""Tests for version-aware dual-read convergence (F0007-S0007).

Covers dual-read parity across cutovers, seeded-disagreement detection, version
selection, and the contract_version field rules added to validate-feature-evidence.py.
"""

from __future__ import annotations

import shutil
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
PM_SCRIPTS = REPO_ROOT / "agents" / "product-manager" / "scripts"
sys.path.insert(0, str(PM_SCRIPTS))

import contract_compat as cc  # noqa: E402

REAL_SPEC_DIR = REPO_ROOT / "agents" / "actions" / "spec"


# ---- dual-read parity -------------------------------------------------------
def test_matrix_reports_zero_disagreement():
    report = cc.dual_read_matrix()
    assert report["ok"], report
    assert len(report["rows"]) == 10  # 5 cutovers x {explicit, legacy-date}
    assert all(not r["disagreements"] for r in report["rows"])


def test_inter_cutover_date_maps_by_legacy_and_agrees():
    r = cc.dual_read({"contract_effective_date": "2026-05-20"})
    assert r["ok"] and r["selected_version"] == "2026-05-19"
    assert r["selection_source"] == "legacy-date"


def test_explicit_version_selection():
    r = cc.dual_read({"contract_version": "2026-06-01", "contract_effective_date": "2026-06-01"})
    assert r["ok"] and r["selected_version"] == "2026-06-01" and r["selection_source"] == "explicit"


def test_unknown_version_in_dual_read():
    r = cc.dual_read({"contract_version": "2099-01-01"})
    assert not r["ok"] and r["rule"] == "manifest_unknown_version"


def test_seeded_disagreement_is_detected(tmp_path):
    spec_dir = tmp_path / "spec"
    shutil.copytree(REAL_SPEC_DIR, spec_dir)
    bundle_path = spec_dir / "history" / "2026-06-01.yaml"
    bundle = yaml.safe_load(bundle_path.read_text())
    bundle["shared"]["requirements"]["kg_reconciliation_required"] = False  # weaken vs the date matrix
    bundle_path.write_text(yaml.safe_dump(bundle, sort_keys=False))

    r = cc.dual_read({"contract_effective_date": "2026-06-01"}, spec_dir)
    assert not r["ok"]
    assert "kg_reconciliation_required" in r["disagreements"]
    assert r["disagreements"]["kg_reconciliation_required"] == {"legacy": True, "policy": False}


# ---- validate-feature-evidence.py version-field rules -----------------------
class FakeResult:
    def __init__(self):
        self.rules: list[str] = []

    def add_error(self, rule, message, **kwargs):
        self.rules.append(rule)


@pytest.fixture(scope="module")
def vfe():
    return cc._load_vfe()


def test_malformed_version_rejected(vfe):
    fr = FakeResult()
    vfe.validate_contract_version_field("not-a-version", "2026-07-11", fr, {})
    assert fr.rules == ["manifest_malformed_contract_version_fails"]


def test_version_date_conflict_rejected(vfe):
    fr = FakeResult()
    vfe.validate_contract_version_field("2026-06-01", "2026-05-25", fr, {})
    assert "manifest_version_date_conflict_fails" in fr.rules


def test_unknown_version_rejected(vfe):
    fr = FakeResult()
    vfe.validate_contract_version_field("2099-01-01", "2099-01-01", fr, {})
    assert "manifest_unknown_contract_version_fails" in fr.rules


def test_valid_consistent_version_accepted(vfe):
    fr = FakeResult()
    vfe.validate_contract_version_field("2026-07-11", "2026-07-11", fr, {})
    assert fr.rules == []


def test_legacy_manifest_without_version_is_untouched(vfe):
    # The hook only fires when contract_version is present; date-only manifests are legacy.
    fr = FakeResult()
    # A None version never reaches validate_contract_version_field, but if it did it must reject.
    vfe.validate_contract_version_field(None, "2026-07-11", fr, {})
    assert fr.rules == ["manifest_malformed_contract_version_fails"]

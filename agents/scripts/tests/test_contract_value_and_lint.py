"""Tests for contract-value.py and lint-vague-language.py (F0007-S0008)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "agents" / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cv = _load("contract_value", SCRIPTS_DIR / "contract-value.py")
lint = _load("lint_vague_language", SCRIPTS_DIR / "lint-vague-language.py")


# ---- contract-value ---------------------------------------------------------
def test_resolve_known_value():
    assert cv.resolve("coverage_min_pct") == 80


def test_unknown_key_has_no_fallback():
    with pytest.raises(cv.ContractValueError):
        cv.resolve("definitely_not_a_key")


def test_audit_clean_when_agent_map_matches_contract():
    report = cv.audit()
    assert report["ok"] and report["findings"] == []
    assert report["coverage_min_pct"] == 80


def test_audit_detects_drift(tmp_path):
    contract = tmp_path / "_contract.yaml"
    contract.write_text("shared:\n  coverage_min_pct: 90\n", encoding="utf-8")
    report = cv.audit(contract_path=contract)  # real agent-map (80) vs contract (90)
    assert not report["ok"]
    assert any(f["field"] == "unit_coverage_pct" for f in report["findings"])


# ---- lint-vague-language ----------------------------------------------------
def test_lint_flags_banned_words_with_suggestions():
    findings = lint.lint_text("This should be easy and fast.", lint.banned_words())
    terms = {f["term"].lower() for f in findings}
    assert {"should", "easy", "fast"} <= terms
    assert all(f["suggestion"] for f in findings)


def test_lint_respects_word_boundaries():
    findings = lint.lint_text("Tap his shoulder; simplistic is fine.", lint.banned_words())
    assert findings == []  # 'shoulder'/'simplistic' must not match 'should'/'simple'


def test_lint_exception_marker_skips_line():
    text = "We just note it. <!-- vague-ok -->\nThis should fail."
    findings = lint.lint_text(text, lint.banned_words())
    assert [f["line"] for f in findings] == [2]  # line 1 exempted


def test_lint_files_ok_when_clean(tmp_path):
    clean = tmp_path / "clean.md"
    clean.write_text("State the exact latency target and the specific control.\n", encoding="utf-8")
    assert lint.lint_files([clean])["ok"]


# ---- consumer migration (coverage script resolves from the shared contract) --
def test_coverage_script_min_from_contract(tmp_path):
    lcov = tmp_path / "lcov.info"
    lcov.write_text("LF:100\nLH:75\n", encoding="utf-8")  # 75% < 80 floor -> should fail
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "agents" / "quality-engineer" / "scripts" / "validate-test-coverage.py"),
         str(lcov), "--min-from-contract"],
        capture_output=True, text=True)
    assert proc.returncode == 1
    assert "min 80.00%" in proc.stdout

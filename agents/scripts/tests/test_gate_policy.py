"""Exhaustive table-driven tests for gate_policy.py (F0007-S0005)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "agents" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import gate_policy as gp  # noqa: E402


def d(code_c=0, code_h=0, sec_c=0, sec_h=0):
    return {"code": {"critical": code_c, "high": code_h},
            "security": {"critical": sec_c, "high": sec_h}}


@pytest.mark.parametrize("domains,status,approve,justify", [
    (d(code_c=1), "BLOCKED", False, False),
    (d(sec_c=3), "BLOCKED", False, False),
    (d(code_h=1), "WARNING", True, True),
    (d(sec_h=2), "WARNING", True, True),
    (d(), "ACCEPTABLE", True, False),
])
def test_standard_branches(domains, status, approve, justify):
    r = gp.evaluate("standard", domains)
    assert r["status"] == status
    assert r["approve_enabled"] is approve
    assert r["requires_justification"] is justify


@pytest.mark.parametrize("variant,domains,status", [
    ("plan", d(code_c=1), "NOT READY"),
    ("plan", d(code_h=1), "CONDITIONALLY READY"),
    ("plan", d(), "READY"),
    ("feature", d(sec_c=1), "NOT DONE"),
    ("feature", d(sec_h=1), "CONDITIONALLY DONE"),
    ("feature", d(), "TRULY DONE"),
])
def test_review_family_branches(variant, domains, status):
    assert gp.evaluate("review-family", domains, variant=variant)["status"] == status


def test_none_profile_always_passes():
    assert gp.evaluate("none", d(code_c=9, sec_c=9))["status"] == "PASS"


def test_critical_dominates_high():
    r = gp.evaluate("standard", d(code_c=1, code_h=5, sec_h=3))
    assert r["status"] == "BLOCKED"
    assert r["totals"] == {"critical": 1, "high": 8}


def test_negative_count_rejected():
    with pytest.raises(gp.SeverityError):
        gp.evaluate("standard", d(code_c=-1))


def test_boolean_count_rejected():
    with pytest.raises(gp.SeverityError):
        gp.evaluate("standard", {"code": {"critical": True, "high": 0}})


def test_unknown_profile_rejected():
    with pytest.raises(gp.SeverityError):
        gp.evaluate("bogus", d())


def test_cli_json_and_exit():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "gate_policy.py"), "--profile", "standard", "--code-high", "1"],
        capture_output=True, text=True)
    assert proc.returncode == 0
    import json
    assert json.loads(proc.stdout)["status"] == "WARNING"


def test_cli_negative_exit_2():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "gate_policy.py"), "--profile", "standard", "--code-critical", "-1"],
        capture_output=True, text=True)
    assert proc.returncode == 2

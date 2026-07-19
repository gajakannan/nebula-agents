"""Tests for render-prompts.py (F0007-S0006)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "agents" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rp = _load("render_prompts", SCRIPTS_DIR / "render-prompts.py")
REAL_SPEC_DIR = REPO_ROOT / "agents" / "actions" / "spec"

SHARED = {
    "run_id_format": "YYYY-MM-DD-[a-z0-9]{8}",
    "run_id_suffix": {"argv": ["python3", "-c", "import secrets; print(secrets.token_hex(4))"]},
    "run_id_forbidden": ["uuid4"],
    "base_run_files": ["README.md", "commands.log"],
    "artifacts_subdirs": ["coverage", "diffs"],
    "context_preamble": ["agents/ROUTER.md"],
    "coverage_min_pct": 80,
}


def mk_spec(scope="feature-completion", variants=None, notes=None):
    spec = {
        "action": "t", "action_doc": "agents/actions/t.md",
        "contract": {"name": "T Contract", "scope": scope, "version": "2026-07-11"},
        "run_id": {"scheme": "contract", "var": "RUN_ID"},
        "inputs": {"required": [{"name": "FEATURE_ID", "format": "F####"}]},
        "ownership": {},
        "gates": [{"id": "G0", "title": "t", "role": "architect",
                   "operations": [{"run": {"argv": ["python3", "x.py", "{FEATURE_ID}"], "cwd": "framework"}}]}],
        "stop_conditions": ["stop if x"],
    }
    if variants is not None:
        spec["variants"] = variants
    if notes is not None:
        spec["notes"] = notes
    return spec


# ---- unit: rendering + semantics --------------------------------------------
def test_renders_both_variants_with_header_and_package_ref():
    outputs = rp.render_action(mk_spec(), SHARED, "2026-07-11")
    assert set(outputs) == {"operator-friendly", "automation-safe"}
    for text in outputs.values():
        assert text.startswith("<!-- GENERATED")
        assert "do not edit" in text
        assert "policy_version: 2026-07-11" in text
        assert rp.PACKAGE_ROOT_REF in text


def test_render_is_byte_stable():
    a = rp.render_operator(mk_spec(), SHARED, "2026-07-11")
    b = rp.render_operator(mk_spec(), SHARED, "2026-07-11")
    assert a == b


def test_operator_only_action_renders_one_variant():
    outputs = rp.render_action(mk_spec(variants=["operator-friendly"]), SHARED, "2026-07-11")
    assert set(outputs) == {"operator-friendly"}


def test_unknown_scope_rejected():
    with pytest.raises(rp.RenderError) as exc:
        rp.render_action(mk_spec(scope="bogus"), SHARED, "2026-07-11")
    assert exc.value.code == "unknown_scope"


def test_unresolved_placeholder_rejected():
    with pytest.raises(rp.RenderError) as exc:
        rp.render_action(mk_spec(notes={"n": "see {BOGUS_VAR} here"}), SHARED, "2026-07-11")
    assert exc.value.code == "unresolved_placeholder"


def test_forbidden_run_id_scheme_rejected():
    bad_shared = dict(SHARED, run_id_suffix={"argv": ["python3", "-c", "import uuid; print(uuid.uuid4())"]})
    with pytest.raises(rp.RenderError) as exc:
        rp.render_action(mk_spec(), bad_shared, "2026-07-11")
    assert exc.value.code == "forbidden_run_id_scheme"


def test_missing_package_reference_rejected():
    with pytest.raises(rp.RenderError) as exc:
        rp._semantic_check("no package ref in this text", mk_spec(), SHARED)
    assert exc.value.code == "missing_package_reference"


# ---- integration: generate + drift ------------------------------------------
def test_generate_check_drift_and_extra(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "GENERATED_DIR", tmp_path)

    first = rp.generate(REAL_SPEC_DIR, "feature")
    assert first["ok"] and len(first["generated"]) == 2
    # byte-identical on regeneration
    before = (tmp_path / "feature-operator-friendly.md").read_bytes()
    rp.generate(REAL_SPEC_DIR, "feature")
    assert (tmp_path / "feature-operator-friendly.md").read_bytes() == before

    assert rp.check(REAL_SPEC_DIR, "feature")["ok"]

    # hand edit -> drift
    (tmp_path / "feature-operator-friendly.md").write_text("tampered", encoding="utf-8")
    drifted = rp.check(REAL_SPEC_DIR, "feature")
    assert not drifted["ok"] and drifted["drift"]

    # a missing variant file is caught
    rp.generate(REAL_SPEC_DIR, "feature")  # restore
    (tmp_path / "feature-automation-safe.md").unlink()
    missing = rp.check(REAL_SPEC_DIR, "feature")
    assert not missing["ok"] and missing["missing"]

    # a prefix-sharing file for a DIFFERENT action is not mistaken for an extra variant
    rp.generate(REAL_SPEC_DIR, "feature")
    (tmp_path / "feature-review-operator-friendly.md").write_text("x", encoding="utf-8")
    assert rp.check(REAL_SPEC_DIR, "feature")["ok"]


def test_committed_feature_pair_matches_policy():
    # The real committed generated pair must be in sync (this is the CI gate too).
    assert rp.check(REAL_SPEC_DIR, "feature")["ok"]


def test_cli_check_exit_zero():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "render-prompts.py"), "--check", "--action", "feature"],
        cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["ok"]

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


# ---- input constraints must survive compilation (F0007-S0006 review, SE-1) --- #
# A prompt that names an input without its declared `enum` / `required_when` tells
# the reader neither which values are legal nor when an optional input becomes
# required. `prompt_drift` cannot catch that class of loss: it compares committed
# output against freshly rendered output, and a constraint the renderer never emits
# is absent from both sides. These tests are the guard instead.
def test_declared_enum_and_required_when_are_rendered():
    spec = mk_spec()
    spec["inputs"] = {
        "required": [{"name": "FEATURE_ID", "format": "F####", "required_when": "PR_URL unset"}],
        "optional": [{"name": "MODE", "enum": ["clean", "drift-reconcile"], "default": "clean"},
                     {"name": "SLICE_ORDER", "required_when": "SLICE_ORDER_SOURCE=override"}],
    }
    out = rp.render_action(spec, SHARED, "2026-07-11")
    for variant, text in out.items():
        assert "clean" in text and "drift-reconcile" in text, variant
        assert "SLICE_ORDER_SOURCE=override" in text, variant
        assert "PR_URL unset" in text, variant


def test_constraints_use_brackets_not_braces():
    # `{IDENT}` is placeholder syntax; rendering a constraint with braces would trip
    # _semantic_check's unresolved-placeholder guard.
    spec = mk_spec()
    spec["inputs"] = {"required": [{"name": "FEATURE_ID", "format": "F####"}],
                      "optional": [{"name": "MODE", "enum": ["live", "dry-run"]}]}
    out = rp.render_action(spec, SHARED, "2026-07-11")  # must not raise
    assert "{live}" not in out["automation-safe"]


@pytest.mark.parametrize("spec_path", sorted(REAL_SPEC_DIR.glob("*.yaml")))
def test_every_declared_constraint_reaches_the_committed_prompts(spec_path):
    if spec_path.name == "_contract.yaml":
        pytest.skip("shared contract, not an action")
    import yaml
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    action = spec["action"]
    texts = {}
    for variant in rp.ALL_VARIANTS:
        path = rp._target(action, variant)
        if path.exists():
            texts[variant] = path.read_text(encoding="utf-8")
    assert texts, f"no committed prompt for {action}"
    inputs = spec.get("inputs") or {}
    for kind in ("required", "optional"):
        for item in inputs.get(kind) or []:
            for variant, text in texts.items():
                for value in item.get("enum", []):
                    assert str(value) in text, (
                        f"{action}-{variant}: enum value {value!r} for input "
                        f"{item['name']} is declared in the spec but absent from the prompt")
                if "required_when" in item:
                    assert str(item["required_when"]) in text, (
                        f"{action}-{variant}: required_when for input {item['name']} "
                        f"is declared in the spec but absent from the prompt")


# ---- session setup matches what init-run.py creates --------------------------
def _session_line(spec):
    text = rp.render_action(spec, SHARED, "2026-07-11")["operator-friendly"]
    return next(line for line in text.splitlines() if line.startswith("Session setup"))


def test_feature_bound_session_setup_initializes_manifest():
    line = _session_line(mk_spec())
    assert "initialize `evidence-manifest.json`" in line
    assert "init-run.py --action t --feature {FEATURE_ID}" in line


def test_base_run_session_setup_creates_no_manifest():
    spec = mk_spec(scope="base-run-only")
    spec["inputs"] = {"required": [{"name": "SCOPE"}], "optional": [{"name": "FEATURE_ID", "format": "F####"}]}
    line = _session_line(spec)
    assert "creates no `evidence-manifest.json`" in line
    assert "initialize `evidence-manifest.json`" not in line
    assert "init-run.py --action t [--feature {FEATURE_ID}]" in line


def test_integrate_scheme_session_setup_does_not_use_init_run():
    spec = mk_spec(scope="merge")
    spec["inputs"] = {"required": [{"name": "BRANCH"}]}
    spec["run_id"] = {"scheme": "integrate", "var": "RUN_ID"}
    spec["gates"][0]["operations"][0]["run"]["argv"] = ["python3", "x.py"]
    line = _session_line(spec)
    assert "not minted by `agents/scripts/init-run.py`" in line


def test_committed_validate_prompt_matches_its_contract():
    text = (REPO_ROOT / "agents" / "templates" / "prompts" / "evidence-contract"
            / "validate-operator-friendly.md").read_text()
    assert "initialize `evidence-manifest.json`" not in text
    assert "init-run.py --action validate [--feature {FEATURE_ID}]" in text


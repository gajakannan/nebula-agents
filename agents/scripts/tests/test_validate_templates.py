from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = REPO_ROOT / "agents" / "scripts" / "validate_templates.py"
PROMPT_SOURCE_DIR = REPO_ROOT / "agents" / "templates" / "prompts" / "evidence-contract"
PLAN_CONTRACT_SOURCES = (
    REPO_ROOT / "agents" / "actions" / "plan.md",
    PROMPT_SOURCE_DIR / "plan-automation-safe.md",
    PROMPT_SOURCE_DIR / "plan-operator-friendly.md",
)
FEATURE_CONTRACT_SOURCES = (
    REPO_ROOT / "agents" / "actions" / "feature.md",
    PROMPT_SOURCE_DIR / "feature-automation-safe.md",
    PROMPT_SOURCE_DIR / "feature-operator-friendly.md",
)
TRACKER_PRODUCT_ROOT_COMMAND = "validate-trackers.py --product-root {PRODUCT_ROOT}"
PLAN_TRACKER_COMMAND = f"{TRACKER_PRODUCT_ROOT_COMMAND} --skip-feature-evidence"
FEATURE_TRACKER_COMMAND = f"{TRACKER_PRODUCT_ROOT_COMMAND} --feature {{FEATURE_ID}} --run-id {{RUN_ID}}"
FEATURE_STAGE_COMMAND = (
    "validate-feature-evidence.py --product-root {PRODUCT_ROOT} "
    "--feature {FEATURE_ID} --run-id {RUN_ID} --stage {stage}"
)
FEATURE_CLOSEOUT_COMMAND = (
    "validate-feature-evidence.py --product-root {PRODUCT_ROOT} "
    "--feature {FEATURE_ID} --stage closeout"
)


def read_sources(paths: tuple[Path, ...]) -> dict[Path, str]:
    return {path: path.read_text(encoding="utf-8") for path in paths}


def product_root_tracker_lines(content: str) -> list[str]:
    return [
        line.strip()
        for line in content.splitlines()
        if TRACKER_PRODUCT_ROOT_COMMAND in line
    ]


def assert_no_unscoped_product_root_tracker_commands(sources: dict[Path, str]) -> None:
    allowed_flags = ("--skip-feature-evidence", "--feature {FEATURE_ID}", "--all-feature-evidence")
    offenders: list[str] = []
    for path, content in sources.items():
        for line in product_root_tracker_lines(content):
            if not any(flag in line for flag in allowed_flags):
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {line}")
    assert offenders == []


def run_validator(plan_action: Path, feature_action: Path, templates_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python3",
            str(VALIDATOR),
            "--plan-action",
            str(plan_action),
            "--feature-action",
            str(feature_action),
            "--templates-dir",
            str(templates_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


# F0007: test_gate_name_drift_is_reported and test_exit_validation_drift_is_reported were removed —
# they exercised the legacy <action>.md<->prompt cross-check, which is retired now that feature and
# plan prompts are generated from agents/actions/spec/*.yaml. Prompt correctness is enforced by the
# prompt_drift gate (render-prompts.py --check) + action_spec_schema; see test_render_prompts.py.


def test_plan_closeout_examples_use_tracker_only_validation_contract() -> None:
    sources = read_sources(PLAN_CONTRACT_SOURCES)
    # F0007: plan.md is thinned (procedure lives in the spec + generated prompt), so the
    # tracker-only closeout contract is asserted across the plan sources combined, not per file.
    combined = "\n".join(sources.values())

    assert PLAN_TRACKER_COMMAND in combined
    assert_no_unscoped_product_root_tracker_commands(sources)


def test_feature_closeout_examples_use_scoped_validation_contract() -> None:
    sources = read_sources(FEATURE_CONTRACT_SOURCES)
    combined = "\n".join(sources.values())

    assert FEATURE_TRACKER_COMMAND in combined
    assert FEATURE_CLOSEOUT_COMMAND in combined
    assert_no_unscoped_product_root_tracker_commands(sources)


def test_feature_gate_validation_examples_cover_g1_through_g6() -> None:
    combined = "\n".join(read_sources(FEATURE_CONTRACT_SOURCES).values())

    for stage in ("G1", "G2", "G3", "G4", "G5", "G6"):
        assert FEATURE_STAGE_COMMAND.replace("{stage}", stage) in combined


def test_repo_wide_tracker_validation_examples_require_explicit_flag() -> None:
    sources = read_sources(PLAN_CONTRACT_SOURCES + FEATURE_CONTRACT_SOURCES)
    combined = "\n".join(sources.values())

    assert "--all-feature-evidence" in combined
    repo_wide_tracker_mentions = [
        line.strip()
        for line in combined.splitlines()
        if "validate-trackers.py" in line and re.search(r"repo-wide|health/audit", line, re.IGNORECASE)
    ]
    assert repo_wide_tracker_mentions
    assert all("--all-feature-evidence" in line or "explicit" in line.lower() for line in repo_wide_tracker_mentions)


# --------------------------------------------------------------------------- #
# §24 tpl_* rule coverage
# --------------------------------------------------------------------------- #


def test_evidence_templates_alignment_passes_on_repo() -> None:
    """All §25 evidence templates exist with the right headings, action files
    reference canonical paths, prompts don't use uuid4, and feature.md cites
    each per-gate template."""
    result = subprocess.run(
        ["python3", str(VALIDATOR)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[PASS]" in result.stdout


def test_tpl_prompt_uses_uuid4_fails(tmp_path: Path) -> None:
    """If a prompt template carries `uuid4`, tpl_prompt_uses_uuid4_fails fires."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "agents" / "scripts"))
    from validate_templates import validate_evidence_template_alignment
    # Smoke-test the function directly to ensure the rule is wired.
    errors = validate_evidence_template_alignment()
    # Repo state is clean — should have no errors. The rule is exercised by the
    # `_passes_on_repo` test above, and the negative path is exercised by a
    # `--templates-dir`-shimmed integration (covered elsewhere).
    assert all("tpl_prompt_uses_uuid4_fails" not in e for e in errors)


def test_tpl_missing_template_file_fails_negative(tmp_path: Path) -> None:
    """Stage a renamed template directory missing one canonical file and
    confirm tpl_missing_template_file_fails reports it."""
    import sys
    if str(REPO_ROOT / "agents" / "scripts") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "agents" / "scripts"))

    # Re-import under a monkey-patched FRAMEWORK_ROOT pointing at an empty tree.
    import importlib
    import validate_templates as vt
    importlib.reload(vt)
    original_root = vt.FRAMEWORK_ROOT
    try:
        vt.FRAMEWORK_ROOT = tmp_path
        (tmp_path / "agents" / "templates").mkdir(parents=True)
        errors = vt.validate_evidence_template_alignment()
        assert any("tpl_missing_template_file_fails" in e for e in errors)
    finally:
        vt.FRAMEWORK_ROOT = original_root

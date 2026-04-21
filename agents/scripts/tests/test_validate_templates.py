from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = REPO_ROOT / "agents" / "scripts" / "validate_templates.py"


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


def test_gate_name_drift_is_reported(tmp_path: Path) -> None:
    plan_action = tmp_path / "plan.md"
    feature_action = tmp_path / "feature.md"
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    plan_action.write_text((REPO_ROOT / "agents/actions/plan.md").read_text(encoding="utf-8"), encoding="utf-8")
    feature_action.write_text((REPO_ROOT / "agents/actions/feature.md").read_text(encoding="utf-8"), encoding="utf-8")

    for name in (
        "plan-automation-safe.md",
        "plan-operator-friendly.md",
        "feature-automation-safe.md",
        "feature-operator-friendly.md",
    ):
        content = (REPO_ROOT / "agents/templates/prompts" / name).read_text(encoding="utf-8")
        if name == "plan-automation-safe.md":
            content = content.replace("G4 ONTOLOGY SYNC (B)", "G4 ONTOLOGY ALIGNMENT (B)", 1)
        (templates_dir / name).write_text(content, encoding="utf-8")

    result = run_validator(plan_action, feature_action, templates_dir)

    assert result.returncode != 0
    assert "missing gates" in result.stdout
    assert "G4 ONTOLOGY SYNC (B)" in result.stdout


def test_exit_validation_drift_is_reported(tmp_path: Path) -> None:
    plan_action = tmp_path / "plan.md"
    feature_action = tmp_path / "feature.md"
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    plan_action.write_text((REPO_ROOT / "agents/actions/plan.md").read_text(encoding="utf-8"), encoding="utf-8")
    feature_action.write_text((REPO_ROOT / "agents/actions/feature.md").read_text(encoding="utf-8"), encoding="utf-8")

    for name in (
        "plan-automation-safe.md",
        "plan-operator-friendly.md",
        "feature-automation-safe.md",
        "feature-operator-friendly.md",
    ):
        content = (REPO_ROOT / "agents/templates/prompts" / name).read_text(encoding="utf-8")
        if name == "feature-automation-safe.md":
            content = content.replace(
                "python3 agents/product-manager/scripts/validate-trackers.py",
                "python3 agents/product-manager/scripts/validate-trackerz.py",
                1,
            )
        (templates_dir / name).write_text(content, encoding="utf-8")

    result = run_validator(plan_action, feature_action, templates_dir)

    assert result.returncode != 0
    assert "missing exit-validation commands" in result.stdout
    assert "validate-trackers.py" in result.stdout

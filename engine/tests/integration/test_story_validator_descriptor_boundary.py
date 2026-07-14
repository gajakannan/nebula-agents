from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from nebula_agents.domain.enums import ValidatorKey
from nebula_agents.domain.errors import ErrorCode, NebulaError
from nebula_agents.infrastructure.process import SubprocessRunner
from nebula_agents.infrastructure.watcher import AllowlistedValidatorRunner


RUN_ID = "2026-07-14-b885d64c"
NOW = datetime(2026, 7, 14, 18, 0, tzinfo=UTC)


class Clock:
    def now(self) -> datetime:
        return NOW


VALID_STORY = """# Provider Session Story

**Story ID:** F0001-S0001
**Title:** Validate a stable story
**Feature:** F0001
**Priority:** P0
**Phase:** MVP

## User Story

**As a** local operator **I want** stable validation **So that** governance cannot be bypassed.

## Context & Background

The validator protects a governed local feature.

## Acceptance Criteria

- [ ] Given a denied or replaced story, when validation runs, then it is rejected.

## Data Requirements

No persistent data is introduced.

## Role-Based Visibility

Only an authorized local operator can publish a validator result.

## Non-Functional Expectations

Validation is bounded and fail closed.

## Dependencies

The governed feature directory must exist.

## Out of Scope

Remote validation is excluded.

## Questions & Assumptions

The owning UID is the local security boundary.

## Definition of Done

- [ ] Stable validation succeeds and unsafe replacement fails.
"""


def _workspace(tmp_path: Path, story_content: str) -> tuple[Path, Path, Path]:
    workspace = tmp_path / "workspace"
    feature = workspace / "planning-mds" / "features" / "F0001-feature"
    feature.mkdir(parents=True)
    story = feature / "F0001-S0001-stable-validation.md"
    story.write_text(story_content, encoding="utf-8")
    story.chmod(0o644)

    repository = Path(__file__).resolve().parents[3]
    validator = (
        workspace
        / "agents"
        / "product-manager"
        / "scripts"
        / "validate-stories.py"
    )
    validator.parent.mkdir(parents=True)
    shutil.copy2(
        repository / "agents" / "product-manager" / "scripts" / "validate-stories.py",
        validator,
    )
    helper = workspace / "agents" / "scripts" / "_product_root.py"
    helper.parent.mkdir(parents=True)
    shutil.copy2(repository / "agents" / "scripts" / "_product_root.py", helper)
    return workspace, feature, story


def _run(workspace: Path):
    return AllowlistedValidatorRunner(SubprocessRunner(), Clock()).run(
        ValidatorKey.STORIES,
        workspace_root=workspace,
        feature_id="F0001",
        run_id=RUN_ID,
        timeout_seconds=10,
    )


def test_production_runner_validates_stable_descriptor_bound_story(
    tmp_path: Path,
) -> None:
    workspace, _feature, _story = _workspace(tmp_path, VALID_STORY)

    result = _run(workspace)

    assert result.exit_code == 0
    assert "Story validation PASSED" in result.summary


def test_production_runner_rejects_preexisting_story_symlink(
    tmp_path: Path,
) -> None:
    workspace, _feature, story = _workspace(tmp_path, VALID_STORY)
    outside = tmp_path / "outside-valid-story.md"
    outside.write_text(VALID_STORY, encoding="utf-8")
    story.unlink()
    story.symlink_to(outside)

    with pytest.raises(NebulaError) as caught:
        _run(workspace)

    assert caught.value.code is ErrorCode.PATH_DENIED


def test_real_subprocess_rejects_story_replaced_after_parent_checks(
    tmp_path: Path,
) -> None:
    workspace, _feature, story = _workspace(tmp_path, "# invalid story\n")
    outside = tmp_path / "outside-valid-story.md"
    outside.write_text(VALID_STORY, encoding="utf-8")
    outside.chmod(0o644)

    class ReplacingRunner(SubprocessRunner):
        def run(self, argv, **kwargs):
            story.unlink()
            story.symlink_to(outside)
            return super().run(argv, **kwargs)

    result = AllowlistedValidatorRunner(ReplacingRunner(), Clock()).run(
        ValidatorKey.STORIES,
        workspace_root=workspace,
        feature_id="F0001",
        run_id=RUN_ID,
        timeout_seconds=10,
    )

    assert story.is_symlink()
    assert result.exit_code != 0
    assert "Descriptor-bound story validation failed" in result.summary


@pytest.mark.parametrize("unsafe_kind", ["mode", "fifo"])
def test_production_runner_rejects_unsafe_story_metadata(
    tmp_path: Path,
    unsafe_kind: str,
) -> None:
    workspace, feature, story = _workspace(tmp_path, VALID_STORY)
    if unsafe_kind == "mode":
        story.chmod(0o666)
    else:
        story.unlink()
        story = feature / "F0001-S0001-unsafe-fifo.md"
        story.parent.mkdir(parents=True, exist_ok=True)
        os.mkfifo(story, mode=0o600)

    result = _run(workspace)

    assert result.exit_code != 0
    assert "Descriptor-bound story validation failed" in result.summary


def test_public_validator_cli_still_accepts_normal_feature_path(
    tmp_path: Path,
) -> None:
    workspace, feature, _story = _workspace(tmp_path, VALID_STORY)
    validator = (
        Path(__file__).resolve().parents[3]
        / "agents"
        / "product-manager"
        / "scripts"
        / "validate-stories.py"
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(validator),
            "--product-root",
            str(workspace),
            str(feature),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Story validation PASSED" in completed.stdout

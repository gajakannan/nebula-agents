"""Acceptance criteria remain valid when a story's checklist is completed."""

from pathlib import Path
import subprocess
import sys

import pytest


VALIDATOR = Path(__file__).resolve().parents[1] / "validate-stories.py"


def validate_story(tmp_path: Path, criteria: str, *, status: str = "Done"):
    product = tmp_path / "product"
    feature = product / "planning-mds/features/F0001-customer-directory"
    feature.mkdir(parents=True)
    story = feature / "F0001-S0001-view-customers.md"
    story.write_text(
        f"""# View customers

**Story ID:** F0001-S0001
**Feature:** F0001 — Customer directory
**Title:** View customers
**Priority:** High
**Phase:** MVP
**Status:** {status}

## User Story

**As a** customer service clerk
**I want** to view the customer directory
**So that** I can answer customer questions.

## Context & Background

Clerks consult the directory during customer calls.

## Acceptance Criteria

{criteria}

## Data Requirements

Retain each customer's identifier and display name.

## Role-Based Visibility

Only authorized clerks may view customers; unauthorized requests are denied.

## Non-Functional Expectations

No customer data appears in unauthorized responses.

## Dependencies

None.

## Out of Scope

Changing customer records.

## Questions & Assumptions

None.

## Definition of Done

- [x] Acceptance observations are recorded.
""",
        encoding="utf-8",
    )
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--product-root", str(product), str(story)],
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize("marker", [" ", "x", "X"])
@pytest.mark.parametrize("indent", ["", "  "])
def test_nonempty_acceptance_checklists_validate_in_each_completion_state(
    tmp_path: Path, marker: str, indent: str
):
    result = validate_story(
        tmp_path, f"{indent}- [{marker}] Customer identifiers appear in ascending order."
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "has no criteria" not in result.stdout


def test_mixed_completed_and_incomplete_criteria_remain_valid(tmp_path: Path):
    result = validate_story(
        tmp_path,
        "- [x] The customer identifier is visible.\n"
        "- [ ] Unauthorized customer requests are denied.\n"
        "- [X] The customer name is visible.",
        status="In Progress",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_given_when_then_criteria_keep_the_existing_validation_path(tmp_path: Path):
    result = validate_story(
        tmp_path, "Given an authorized clerk, When the directory opens, Then customer names appear."
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "criteria",
    [
        "",
        "   ",
        "Customers appear in ascending identifier order.",
        "- [ ]",
        "- [x]   ",
        "- [X]\t",
        "- [z] Customers appear in ascending identifier order.",
        "- [xx] Customers appear in ascending identifier order.",
        "A description mentioning - [x] a checkbox is not a checklist item.",
    ],
)
def test_missing_or_noncriteria_content_still_fails(tmp_path: Path, criteria: str):
    result = validate_story(tmp_path, criteria)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (
        "Missing 'Acceptance Criteria' section" in result.stdout
        or "Acceptance criteria section exists but has no criteria" in result.stdout
    )

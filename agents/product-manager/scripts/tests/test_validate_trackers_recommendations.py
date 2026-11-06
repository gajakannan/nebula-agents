"""Tracker provenance accepts contract verdicts without bypassing deep evidence."""

from pathlib import Path

import pytest

from test_validate_trackers import RUN_ID, load_validator, run_main, write_tracker_product


def write_completed_trackers(
    product: Path,
    verdict: str = "PASS WITH RECOMMENDATIONS",
    *,
    terminal_state: str = "Done",
    reviewer: str = "security-reviewer",
    evidence: str | None = None,
    review_date: str = "2026-05-19",
    include_security_row: bool = True,
):
    write_tracker_product(product)
    features = product / "planning-mds/features"
    feature = features / "F0038-scoped"
    relative_feature = "F0038-scoped"
    if terminal_state == "Archived":
        archived = features / "archive"
        archived.mkdir()
        feature = feature.rename(archived / feature.name)
        relative_feature = "archive/F0038-scoped"
        registry = features / "REGISTRY.md"
        registry.write_text(
            registry.read_text().replace(
                "| F0038 | Scoped Evidence | In Progress | MVP | `F0038-scoped/` |\n", ""
            )
            + "| F0038 | Scoped Evidence | 2026-05-19 |  | `archive/F0038-scoped/` |\n"
        )
        roadmap = features / "ROADMAP.md"
        roadmap.write_text(
            roadmap.read_text().replace(
                "| [F0038 Scoped Evidence](./F0038-scoped/) | In Progress | Current |\n", ""
            )
            + "| [F0038 Scoped Evidence](./archive/F0038-scoped/) | Archived | Complete |\n"
        )
    else:
        for filename in ("REGISTRY.md", "ROADMAP.md"):
            path = features / filename
            path.write_text(path.read_text().replace("In Progress", "Done"))

    registry = features / "REGISTRY.md"
    registry.write_text(
        registry.read_text()
        + "\n## Retired Features\n\n"
        "| Feature ID | Name | Terminal Status | Superseded By | Retired Date | Folder | Reason |\n"
        "|---|---|---|---|---|---|---|\n"
    )
    story = feature / "F0038-S0001-view-customers.md"
    story.write_text("# View customers\n\n**Story ID:** F0038-S0001\n")
    (features / "STORY-INDEX.md").write_text(
        "# Story Index\n\n**Total Stories:** 1\n\n"
        f"- [F0038-S0001](./{relative_feature}/{story.name})\n"
    )
    run_relative = f"planning-mds/operations/evidence/runs/{RUN_ID}"
    run = product / run_relative
    run.mkdir(parents=True)
    for name in ("test-execution-report.md", "code-review-report.md", "security-review-report.md"):
        (run / name).write_text("# Synthetic review evidence\n")
    if evidence is None:
        evidence = f"{run_relative}/security-review-report.md"
    security_row = (
        f"| F0038-S0001 | Security Reviewer | {reviewer} | {verdict} | "
        f"{evidence} | {review_date} | - |\n"
        if include_security_row
        else ""
    )
    status = feature / "STATUS.md"
    status.write_text(
        f"""# Status

**Overall Status:** {terminal_state}

## Story Checklist

| Story | Status |
|---|---|
| F0038-S0001 | Done |

## Required Role Matrix

| Role | Required |
|---|---|
| Quality Engineer | Yes |
| Code Reviewer | Yes |
| Security Reviewer | Yes |

## Story Signoff Provenance

| Story | Role | Reviewer | Verdict | Evidence | Date | Notes |
|---|---|---|---|---|---|---|
| F0038-S0001 | Quality Engineer | quality-reviewer | PASS | {run_relative}/test-execution-report.md | 2026-05-19 | - |
| F0038-S0001 | Code Reviewer | code-reviewer | APPROVED | {run_relative}/code-review-report.md | 2026-05-19 | - |
{security_row}
"""
    )


def tracker_issues(product: Path):
    module = load_validator()
    validator = module.TrackerValidator(
        product / "planning-mds/features", product / "planning-mds/BLUEPRINT.md"
    )
    return validator.validate(), validator.issues


@pytest.mark.parametrize("terminal_state", ["Done", "Archived"])
@pytest.mark.parametrize(
    "verdict",
    ["PASS", "APPROVED", "PASS WITH RECOMMENDATIONS", "APPROVED WITH RECOMMENDATIONS"],
)
def test_completed_provenance_accepts_all_contract_passing_verdicts(
    tmp_path: Path, terminal_state: str, verdict: str
):
    product = tmp_path / "product"
    write_completed_trackers(product, verdict, terminal_state=terminal_state)
    exit_code, issues = tracker_issues(product)
    assert exit_code == 0, [issue.message for issue in issues]


@pytest.mark.parametrize("verdict", ["FAIL", "REQUEST CHANGES", "REJECTED", "", "NOT_REQUIRED"])
def test_required_role_still_rejects_nonpassing_verdicts(tmp_path: Path, verdict: str):
    product = tmp_path / "product"
    write_completed_trackers(product, verdict)
    exit_code, issues = tracker_issues(product)
    assert exit_code == 1
    assert any("Required role 'Security Reviewer' is missing" in issue.message for issue in issues)


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"reviewer": ""}, "missing reviewer"),
        ({"evidence": ""}, "missing evidence"),
        ({"review_date": ""}, "invalid date"),
        ({"review_date": "yesterday"}, "invalid date"),
        ({"evidence": "agents/security/SKILL.md"}, "references agents/ in evidence"),
    ],
)
def test_recommendation_verdict_still_requires_complete_provenance(
    tmp_path: Path, changes: dict[str, str], expected: str
):
    product = tmp_path / "product"
    write_completed_trackers(product, **changes)
    exit_code, issues = tracker_issues(product)
    assert exit_code == 1
    assert any(expected in issue.message for issue in issues)


def test_recommendation_support_does_not_replace_a_missing_required_role(tmp_path: Path):
    product = tmp_path / "product"
    write_completed_trackers(product, include_security_row=False)
    exit_code, issues = tracker_issues(product)
    assert exit_code == 1
    assert any("Required role 'Security Reviewer' is missing" in issue.message for issue in issues)


def test_recommendation_tracker_pass_still_runs_real_deep_evidence_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
):
    product = tmp_path / "product"
    write_completed_trackers(product)
    module = load_validator()
    # The complete local provenance has no evidence manifest. The actual child
    # validator must reject it; no mock replaces the feature-evidence invocation.
    assert run_main(module, monkeypatch, product, "--feature", "F0038", "--run-id", RUN_ID) == 1
    output = capfd.readouterr().out
    assert "errors: 0" in output
    assert "ERROR missing_manifest_fails:" in output

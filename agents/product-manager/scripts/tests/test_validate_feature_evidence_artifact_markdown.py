"""Real G2 reports can cite artifacts using normal Markdown punctuation."""
from pathlib import Path

import pytest

from test_validate_feature_evidence import (
    RUN_ID,
    json_result,
    run_validator,
    write_manifest_run,
    write_registry,
)


@pytest.mark.parametrize("reference", [
    "`artifacts/coverage/cov.json`.",
    "[Coverage JSON](artifacts/coverage/cov.json).",
    "[artifacts/coverage/cov.json](artifacts/coverage/cov.json).",
    "artifacts/coverage/cov.json,",
    "<artifacts/coverage/cov.json>;",
])
@pytest.mark.parametrize("exists", [True, False])
def test_markdown_reference_resolves_and_missing_artifact_still_fails(
    tmp_path: Path, reference: str, exists: bool
) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run = write_manifest_run(product, "F0001-new", "F0001", stage="G2")
    artifact = run / "artifacts/coverage/cov.json"
    if exists:
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text('{"coverage":90}\n')
    (run / "coverage-report.md").write_text("# Coverage\n\nResult: PASS\n\nRaw: " + reference + "\n")
    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G2", "--json")
    rules = {item["rule_id"] for item in json_result(result)["errors"]}
    assert ("coverage_claim_without_artifact_fails" in rules) is not exists
    if exists:
        assert "artifact_missing_fails" not in rules


def test_markdown_does_not_hide_traversal_reference(tmp_path: Path) -> None:
    product = tmp_path / "product"
    write_registry(product, archived="| F0001 | New Feature | 2026-05-19 |  | `archive/F0001-new/` |")
    run = write_manifest_run(product, "F0001-new", "F0001", stage="G2")
    (run / "coverage-report.md").write_text(
        "# Coverage\n\nResult: PASS\n\n[Escape](../../../../artifacts/coverage/outside.json).\n"
    )
    result = run_validator(product, "--feature", "F0001", "--run-id", RUN_ID, "--stage", "G2", "--json")
    assert result.returncode == 1
    rules = {item["rule_id"] for item in json_result(result)["errors"]}
    assert any("artifact" in rule for rule in rules)

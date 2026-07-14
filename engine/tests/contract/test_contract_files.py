from __future__ import annotations

import tomllib
from pathlib import Path


def test_public_cli_contract_documents_every_command_and_exit(repository_root: Path) -> None:
    contract = (
        repository_root / "planning-mds" / "architecture" / "f0001-cli-contract.md"
    ).read_text(encoding="utf-8")
    for command in (
        "doctor",
        "tui",
        "launch",
        "attach",
        "recover",
        "sessions",
        "status",
        "evidence",
        "validate",
    ):
        assert f"`{command}`" in contract
    for exit_code in (0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 130):
        assert f"| {exit_code} |" in contract


def test_pytest_metadata_matches_approved_compatible_branch_contract(
    repository_root: Path,
) -> None:
    document = tomllib.loads(
        (repository_root / "engine" / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert document["project"]["optional-dependencies"]["test"] == [
        "pytest>=9.0.3,<10",
        "pytest-cov>=5,<7",
    ]
    assert document["tool"]["coverage"]["run"]["branch"] is True


def test_six_approved_story_contracts_remain_present(repository_root: Path) -> None:
    feature_root = (
        repository_root
        / "planning-mds"
        / "features"
        / "F0001-tmux-native-agent-cockpit"
    )
    stories = sorted(feature_root.glob("F0001-S*.md"))
    assert [path.name[:11] for path in stories] == [
        "F0001-S0001",
        "F0001-S0002",
        "F0001-S0003",
        "F0001-S0004",
        "F0001-S0005",
        "F0001-S0006",
    ]

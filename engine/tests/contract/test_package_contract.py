"""Packaging contract: F0003 adds no required dependency (ADR-005, ADR-007).

ADR-007 chose a dependency-free stdio MCP implementation specifically so
`engine/pyproject.toml` would gain nothing required and the CLI would be unaffected when
no host is present. That is a claim about a file, and a file changes.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

#: The F0001 dependency set. F0003 must not extend it.
F0001_RUNTIME_DEPENDENCIES = {"jsonschema>=4.18,<5"}


@pytest.fixture(scope="module")
def pyproject(repository_root: Path) -> dict:
    return tomllib.loads((repository_root / "engine" / "pyproject.toml").read_text(encoding="utf-8"))


def test_f0003_adds_no_required_runtime_dependency(pyproject: dict) -> None:
    """The concrete form of ADR-005's "extends the package rather than adding a service".

    A new required dependency would also make ADR-007's SDK-unavailable edge case
    reachable again, which the decision exists to close.
    """
    assert set(pyproject["project"]["dependencies"]) == F0001_RUNTIME_DEPENDENCIES


def test_the_console_entry_point_is_unchanged(pyproject: dict) -> None:
    """`nebula-agents` is the published command; contract 1.1 extends it, never replaces it."""
    assert pyproject["project"]["scripts"] == {
        "nebula-agents": "nebula_agents.presentation.cli:main"
    }


def test_no_f0003_module_imports_a_third_party_package(repository_root: Path) -> None:
    """Every F0003 module must run on a clean install carrying only `jsonschema`.

    Import-level rather than install-level, because a clean-install check needs a network
    and a venv; this catches the same regression in-suite, on every run.
    """
    import ast
    import sys

    source = repository_root / "engine" / "src" / "nebula_agents"
    f0003_modules = [
        source / "domain" / "artifacts.py",
        source / "domain" / "summaries.py",
        source / "domain" / "capabilities.py",
        source / "domain" / "proposals.py",
        source / "domain" / "metrics.py",
        source / "application" / "evidence.py",
        source / "application" / "capabilities.py",
        source / "application" / "learning.py",
        source / "application" / "metrics.py",
        source / "application" / "commands.py",
        source / "infrastructure" / "artifact_index.py",
        source / "infrastructure" / "capability_probe.py",
        source / "infrastructure" / "summarizers.py",
        source / "infrastructure" / "proposal_store.py",
        source / "infrastructure" / "atomic.py",
    ]
    allowed = set(sys.stdlib_module_names) | {"nebula_agents", "jsonschema"}
    offenders = []
    for path in f0003_modules:
        assert path.exists(), f"{path} is missing"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            for name in names:
                if name.split(".")[0] not in allowed:
                    offenders.append(f"{path.name} -> {name}")
    assert offenders == [], "F0003 modules import third-party packages:\n" + "\n".join(offenders)

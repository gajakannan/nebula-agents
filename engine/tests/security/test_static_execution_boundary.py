from __future__ import annotations

import ast
from pathlib import Path

import pytest


FORBIDDEN_CALLS = {
    ("os", "system"),
    ("os", "popen"),
    ("subprocess", "getoutput"),
    ("subprocess", "getstatusoutput"),
}


def _python_sources(repository_root: Path) -> list[Path]:
    source_root = repository_root / "engine" / "src" / "nebula_agents"
    files = sorted(source_root.rglob("*.py"))
    assert files, "F0001 runtime source has not been created"
    return files


def _qualified_name(node: ast.AST) -> tuple[str, str] | None:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.value.id, node.attr
    return None


def test_runtime_never_uses_shell_true_or_shell_helpers(repository_root: Path) -> None:
    violations: list[str] = []
    for path in _python_sources(repository_root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            qualified = _qualified_name(node.func)
            if qualified in FORBIDDEN_CALLS:
                violations.append(f"{path.relative_to(repository_root)}:{node.lineno} {qualified}")
            for keyword in node.keywords:
                if (
                    keyword.arg == "shell"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                ):
                    violations.append(
                        f"{path.relative_to(repository_root)}:{node.lineno} shell=True"
                    )
    assert violations == []


@pytest.mark.parametrize(
    "module",
    [
        "domain/enums.py",
        "domain/models.py",
        "domain/errors.py",
        "domain/transitions.py",
        "domain/redaction.py",
        "application/authorization.py",
        "application/preflight.py",
        "application/runs.py",
        "application/gates.py",
        "application/transcripts.py",
        "application/queries.py",
        "infrastructure/process.py",
        "infrastructure/providers.py",
        "infrastructure/tmux.py",
        "infrastructure/filesystem_store.py",
        "presentation/cli.py",
        "presentation/session_entry.py",
    ],
)
def test_assembly_plan_runtime_modules_exist(repository_root: Path, module: str) -> None:
    path = repository_root / "engine" / "src" / "nebula_agents" / module
    assert path.is_file(), f"assembly-plan module is missing: {module}"


def test_common_application_layer_has_no_provider_specific_cli_flags(
    repository_root: Path,
) -> None:
    application_root = repository_root / "engine" / "src" / "nebula_agents" / "application"
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(application_root.rglob("*.py"))
    )
    forbidden = ("--dangerously-skip-permissions", "--full-auto", "--approval-policy")
    assert {flag for flag in forbidden if flag in source} == set()


def test_runtime_does_not_read_provider_credential_locations(repository_root: Path) -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in _python_sources(repository_root)
    ).lower()
    forbidden = (
        ".codex/auth.json",
        ".claude/credentials",
        "anthropic_api_key",
        "openai_api_key",
        ".netrc",
    )
    assert {value for value in forbidden if value in source} == set()


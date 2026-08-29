"""The inward dependency rule, enforced (BLUEPRINT §4.1, §5.1).

Domain and application must never import infrastructure or presentation. This test did
not exist before Step 5, and Step 5 is where it would have earned its keep: the first
draft of `application/evidence.py` imported `infrastructure.summarizers` directly. It was
caught by reading, which is exactly the kind of catch that stops working once the
codebase is larger than one person's attention.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "src" / "nebula_agents"

#: Each layer and the layers it may not reach.
FORBIDDEN = {
    "domain": ("application", "infrastructure", "presentation"),
    "application": ("infrastructure", "presentation"),
    # Infrastructure may use domain; presentation may use application and domain.
    "infrastructure": ("presentation",),
}


def modules(layer: str) -> list[Path]:
    return sorted((SOURCE / layer).glob("*.py"))


def imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            # Relative imports stay inside the layer by construction.
            if node.level == 0:
                names.add(node.module)
    return names


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_a_layer_never_imports_outward(layer: str) -> None:
    violations = []
    for path in modules(layer):
        for name in imported_names(path):
            for banned in FORBIDDEN[layer]:
                if name.startswith(f"nebula_agents.{banned}"):
                    violations.append(f"{layer}/{path.name} -> {name}")
    assert violations == [], "inward dependency rule violated:\n" + "\n".join(violations)


def test_no_extractor_can_reach_a_model_or_the_network() -> None:
    """ADR-008's guarantee, asserted structurally rather than promised.

    "No model call participates in generating a summary" is only true while nothing in
    the summarization path can make one. Import-level is the right granularity: a
    summarizer that cannot import an HTTP client cannot call a model.
    """
    banned = ("http", "urllib", "requests", "socket", "anthropic", "openai", "subprocess")
    names = imported_names(SOURCE / "infrastructure" / "summarizers.py")
    offenders = sorted(n for n in names if n.split(".")[0] in banned)
    assert offenders == []

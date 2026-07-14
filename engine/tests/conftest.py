from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest


ENGINE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ENGINE_ROOT.parent
SOURCE_ROOT = ENGINE_ROOT / "src"

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


@pytest.fixture(scope="session")
def repository_root() -> Path:
    return REPOSITORY_ROOT


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    (root / "planning-mds" / "features" / "F0001-test-feature").mkdir(
        parents=True
    )
    prompt_root = root / "agents" / "templates" / "prompts" / "evidence-contract"
    prompt_root.mkdir(parents=True)
    for action in ("plan", "feature", "build", "review", "validate"):
        (prompt_root / f"{action}-operator-friendly.md").write_text(
            f"# Safe {action} test prompt\n", encoding="utf-8"
        )
    return root


@pytest.fixture
def runtime_root(tmp_path: Path) -> Path:
    root = tmp_path / "runtime"
    root.mkdir(mode=0o700)
    return root


@pytest.fixture(scope="session")
def schema_root(repository_root: Path) -> Path:
    return repository_root / "planning-mds" / "schemas"


@pytest.fixture(scope="session")
def load_schema(schema_root: Path):
    def _load(name: str) -> dict[str, Any]:
        return json.loads((schema_root / name).read_text(encoding="utf-8"))

    return _load


@pytest.fixture(scope="session")
def fixed_now() -> datetime:
    return datetime(2026, 7, 13, 18, 0, tzinfo=UTC)


@pytest.fixture
def sanitized_environment(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    allowed = {
        "HOME": os.environ.get("HOME", "/tmp"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "TERM": os.environ.get("TERM", "xterm-256color"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
    }
    for name in tuple(os.environ):
        monkeypatch.delenv(name, raising=False)
    for name, value in allowed.items():
        monkeypatch.setenv(name, value)
    return allowed


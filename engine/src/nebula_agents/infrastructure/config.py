from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


SAFE_ENV_NAMES = (
    "PATH", "HOME", "SHELL", "USER", "LOGNAME", "TERM", "COLORTERM", "LANG", "LC_ALL", "LC_CTYPE",
    "TMPDIR", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "CODEX_HOME", "CLAUDE_CONFIG_DIR",
)


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    workspace_root: Path
    runtime_root: Path
    schema_root: Path
    feature_root: Path
    prompt_root: Path
    runs_root: Path
    watch_interval_seconds: float = 0.5
    debounce_seconds: float = 0.1
    lock_timeout_seconds: float = 5.0
    process_capture_limit: int = 65_536


def resolve_config(workspace_root: Path, runtime_override: Path | None = None) -> RuntimeConfig:
    workspace = workspace_root.expanduser().resolve()
    env_override = os.environ.get("NEBULA_AGENTS_RUNTIME_DIR")
    selected = runtime_override or (Path(env_override) if env_override else None) or workspace / ".nebula-agents" / "runtime"
    runtime = selected.expanduser().resolve()
    return RuntimeConfig(
        workspace_root=workspace,
        runtime_root=runtime,
        schema_root=workspace / "planning-mds" / "schemas",
        feature_root=workspace / "planning-mds" / "features",
        prompt_root=workspace / "agents" / "templates" / "prompts" / "evidence-contract",
        runs_root=runtime / "runs",
    )

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from nebula_agents.domain.enums import SourceRoot


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
    #: F0003's third approved root (ADR-006). The evidence tree is read for indexing;
    #: it is never written by the runtime, which is why it carries no owner-only mode
    #: requirement the way the runtime root does.
    evidence_root: Path
    watch_interval_seconds: float = 0.5
    debounce_seconds: float = 0.1
    lock_timeout_seconds: float = 5.0
    process_capture_limit: int = 65_536
    #: A capability report older than this triggers a re-probe (F0003-S0002).
    capability_report_max_age_seconds: float = 3600.0
    #: Summary size budget in markers, above which passing noise is truncated with a
    #: count. Failure markers are never dropped for size (ADR-008).
    summary_marker_limit: int = 200

    @property
    def approved_roots(self) -> dict[SourceRoot, Path]:
        """The three roots artifact identity is derived against (ADR-006).

        Returned as a mapping rather than three fields so callers cannot resolve a root
        F0003 has not approved, and so the longest-match rule always sees all three.
        """
        return {
            SourceRoot.WORKSPACE: self.workspace_root,
            SourceRoot.RUNTIME: self.runtime_root,
            SourceRoot.EVIDENCE: self.evidence_root,
        }


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
        evidence_root=workspace / "planning-mds" / "operations" / "evidence",
    )

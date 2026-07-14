from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Mapping

from nebula_agents.domain.enums import PromptAction, ProviderKey
from nebula_agents.domain.errors import ErrorCode, error
from nebula_agents.domain.models import PreflightCheck, PreflightResult, Probe, serialize_record

from .ports import Clock, ProviderAdapter, SchemaPort, TmuxPort


PROMPT_FILES: Mapping[PromptAction, str] = {
    PromptAction.PLAN: "plan-operator-friendly.md",
    PromptAction.FEATURE: "feature-operator-friendly.md",
    PromptAction.BUILD: "build-operator-friendly.md",
    PromptAction.REVIEW: "review-operator-friendly.md",
    PromptAction.VALIDATE: "validate-operator-friendly.md",
}
_PROMPT_DIRECTORY = ("agents", "templates", "prompts", "evidence-contract")
_PROMPT_LIMIT = 1_048_576


def contained(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def trusted_prompt_path(workspace: Path, action: PromptAction) -> Path | None:
    """Return the exact prompt leaf only when every ancestry component is trusted."""
    root = workspace.expanduser().resolve()
    current = root
    try:
        for component in _PROMPT_DIRECTORY:
            current = current / component
            if current.is_symlink() or not current.is_dir():
                return None
        prompt_root = current.resolve(strict=True)
        if not contained(root, prompt_root):
            return None
        requested = current / PROMPT_FILES[action]
        if requested.is_symlink() or not requested.is_file():
            return None
        resolved = requested.resolve(strict=True)
        if resolved.parent != prompt_root:
            return None
        return resolved
    except OSError:
        return None


def read_committed_prompt(
    workspace: Path,
    action: PromptAction,
    selected_path: str | None,
) -> tuple[Path, str]:
    """Read the fixed prompt via no-follow directory descriptors.

    The descriptor walk closes the preflight-to-launch symlink swap window and
    keeps the read bounded even if an untrusted process changes the leaf.
    """
    root = workspace.expanduser().resolve()
    expected = root.joinpath(*_PROMPT_DIRECTORY, PROMPT_FILES[action])
    if selected_path is None or Path(selected_path).expanduser() != expected:
        raise OSError("preflight prompt selection is not canonical")
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    current_fd = os.open(root, directory_flags)
    try:
        for component in _PROMPT_DIRECTORY:
            next_fd = os.open(component, directory_flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        prompt_fd = os.open(
            PROMPT_FILES[action],
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=current_fd,
        )
        try:
            before = os.fstat(prompt_fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size > _PROMPT_LIMIT:
                raise OSError("prompt contract is not a bounded regular file")
            payload = bytearray()
            while len(payload) <= _PROMPT_LIMIT:
                chunk = os.read(prompt_fd, min(64 * 1024, _PROMPT_LIMIT + 1 - len(payload)))
                if not chunk:
                    break
                payload.extend(chunk)
            after = os.fstat(prompt_fd)
            if (
                len(payload) > _PROMPT_LIMIT
                or before.st_dev != after.st_dev
                or before.st_ino != after.st_ino
                or before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
            ):
                raise OSError("prompt contract changed during its read")
            return expected, payload.decode("utf-8")
        finally:
            os.close(prompt_fd)
    finally:
        os.close(current_fd)


class PreflightService:
    def __init__(
        self,
        *,
        clock: Clock,
        tmux: TmuxPort,
        providers: Mapping[ProviderKey, ProviderAdapter],
        schema: SchemaPort,
    ) -> None:
        self._clock = clock
        self._tmux = tmux
        self._providers = dict(providers)
        self._schema = schema

    def run(
        self,
        workspace_root: Path,
        runtime_dir_override: Path | None = None,
        provider_hint: ProviderKey | None = None,
        prompt_action: PromptAction | None = None,
    ) -> PreflightResult:
        workspace = workspace_root.expanduser().resolve()
        runtime = (runtime_dir_override or workspace / ".nebula-agents" / "runtime").expanduser().resolve()
        checks: list[PreflightCheck] = []
        missing_paths: list[str] = []

        planning_root = workspace / "planning-mds"
        feature_root = planning_root / "features"
        prompt_root = workspace / "agents" / "templates" / "prompts" / "evidence-contract"
        prompt_root_ready = all(
            not workspace.joinpath(*_PROMPT_DIRECTORY[:index]).is_symlink()
            for index in range(1, len(_PROMPT_DIRECTORY) + 1)
        ) and prompt_root.is_dir()
        workspace_ready = feature_root.is_dir() and prompt_root_ready
        if not planning_root.is_dir():
            missing_paths.append(str(planning_root))
        if not feature_root.is_dir():
            missing_paths.append(str(feature_root))
        if not prompt_root.is_dir():
            missing_paths.append(str(prompt_root))
        checks.append(PreflightCheck("workspace_contract", "ready" if workspace_ready else "missing", "Governed feature and prompt roots are available." if workspace_ready else "Governed feature or prompt root is missing."))

        prompt_path: Path | None = None
        prompt_ready = True
        if prompt_action is not None:
            prompt_path = trusted_prompt_path(workspace, prompt_action)
            prompt_ready = prompt_path is not None
            if not prompt_ready:
                missing_paths.append(str(prompt_root / PROMPT_FILES[prompt_action]))
            checks.append(PreflightCheck("prompt_contract", "ready" if prompt_ready else "missing", "The requested committed prompt is available." if prompt_ready else "The requested committed prompt is missing."))

        runtime_status = "ready"
        runtime_message = "Runtime directory is owner-only."
        try:
            if runtime.exists():
                details = runtime.stat()
                if runtime.is_symlink() or not runtime.is_dir() or details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) & 0o077:
                    runtime_status = "denied"
                    runtime_message = "Runtime directory ownership or permissions are unsafe."
            else:
                parent = runtime.parent
                while not parent.exists() and parent != parent.parent:
                    parent = parent.parent
                details = parent.stat()
                sticky_shared = bool(stat.S_IMODE(details.st_mode) & stat.S_ISVTX)
                safely_creatable = (
                    parent.is_dir()
                    and os.access(parent, os.W_OK | os.X_OK)
                    and (details.st_uid == os.getuid() or sticky_shared)
                )
                if safely_creatable:
                    runtime_message = "Runtime directory will be initialized owner-only on the first authorized mutation."
                else:
                    runtime_status = "denied"
                    runtime_message = "Runtime directory cannot be initialized under its nearest existing parent."
        except OSError:
            runtime_status = "denied"
            runtime_message = "Runtime directory cannot be inspected safely."
        checks.append(PreflightCheck("runtime_directory", runtime_status, runtime_message))

        tmux_probe = self._tmux.probe()
        selected = (provider_hint,) if provider_hint is not None else tuple(self._providers)
        provider_probes = tuple(self._providers[key].probe(workspace) for key in selected if key in self._providers)
        if not provider_probes:
            provider_probes = (Probe((provider_hint or ProviderKey.CODEX).value, "missing", remediation_category="install_provider"),)

        statuses = {item.status for item in provider_probes}
        if runtime_status == "denied":
            overall = "denied"
        elif not workspace_ready or not prompt_ready or tmux_probe.status != "ready" or statuses & {"missing", "unsupported", "denied", "timeout", "error"}:
            overall = "blocked"
        elif "authentication_attention_needed" in statuses:
            overall = "authentication_attention_needed"
        else:
            overall = "ready"

        result = PreflightResult(
            schema_version="1.0",
            probed_at=self._clock.now(),
            workspace_root=str(workspace),
            runtime_dir=str(runtime),
            prompt_contract_path=str(prompt_path) if prompt_path else None,
            overall_status=overall,
            tmux=tmux_probe,
            providers=provider_probes,
            checks=tuple(checks),
            planning_docs_path=str(planning_root.resolve()) if planning_root.is_dir() else None,
            missing_paths=tuple(dict.fromkeys(missing_paths))[:16],
        )
        self._schema.validate("f0001-preflight-result.schema.json", serialize_record(result))
        return result

    def require_ready(
        self,
        workspace_root: Path,
        runtime_dir_override: Path | None,
        provider: ProviderKey,
        action: PromptAction,
    ) -> PreflightResult:
        result = self.run(workspace_root, runtime_dir_override, provider, action)
        if result.overall_status != "ready":
            raise error(ErrorCode.PREFLIGHT_BLOCKED, "Runtime preflight is not ready", "preflight", "Run doctor and resolve the reported checks.", status=result.overall_status)
        return result

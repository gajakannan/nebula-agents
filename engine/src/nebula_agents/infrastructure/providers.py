from __future__ import annotations

import shutil
from pathlib import Path

from nebula_agents.domain.enums import ProviderKey
from nebula_agents.domain.models import Probe

from .config import SAFE_ENV_NAMES
from .process import SubprocessRunner


class NativeCliAdapter:
    executable_name: str
    auth_argv: tuple[str, ...]

    def __init__(self, runner: SubprocessRunner) -> None:
        self._runner = runner

    def _executable(self) -> str | None:
        return shutil.which(self.executable_name)

    def probe(self, workspace_root: Path) -> Probe:
        executable = self._executable()
        if executable is None:
            return Probe(self.key.value, "missing", remediation_category="install_provider")
        version_result = self._runner.run((executable, "--version"), cwd=workspace_root, timeout_seconds=1.0, capture_limit=256, env_names=SAFE_ENV_NAMES)
        if version_result.timed_out:
            return Probe(self.key.value, "timeout", executable, remediation_category="provider_probe_timeout")
        if version_result.exit_code != 0:
            return Probe(self.key.value, "unsupported", executable, remediation_category="provider_version_failed")
        version = (version_result.stdout or version_result.stderr).strip()[:256] or None
        auth_result = self._runner.run((executable, *self.auth_argv), cwd=workspace_root, timeout_seconds=1.0, capture_limit=512, env_names=SAFE_ENV_NAMES)
        if auth_result.exit_code != 0:
            return Probe(self.key.value, "authentication_attention_needed", executable, version, "provider_login_status")
        return Probe(self.key.value, "ready", executable, version, None)

    def build_interactive_argv(self, workspace_root: Path, prompt_text: str) -> tuple[str, ...]:
        executable = self._executable()
        if executable is None:
            raise FileNotFoundError(self.executable_name)
        if "\x00" in prompt_text or len(prompt_text) > 65_536:
            raise ValueError("prompt content is invalid")
        return executable, prompt_text

    def classify_early_exit(self, exit_code: int, redacted_output: str) -> str:
        if exit_code == 0:
            return "exited"
        lowered = redacted_output.lower()
        if "login" in lowered or "auth" in lowered:
            return "authentication_attention_needed"
        return "provider_failed"


class CodexAdapter(NativeCliAdapter):
    executable_name = "codex"
    auth_argv = ("login", "status")

    @property
    def key(self) -> ProviderKey:
        return ProviderKey.CODEX


class ClaudeAdapter(NativeCliAdapter):
    executable_name = "claude"
    auth_argv = ("auth", "status")

    @property
    def key(self) -> ProviderKey:
        return ProviderKey.CLAUDE

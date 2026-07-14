from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from nebula_agents.domain.errors import ErrorCode, error
from nebula_agents.domain.models import Probe

from .config import SAFE_ENV_NAMES
from .process import SubprocessRunner


_SESSION = re.compile(r"^nebula-F\d{4}-[0-9a-f]{8}$")


class TmuxAdapter:
    def __init__(self, runner: SubprocessRunner) -> None:
        self._runner = runner

    def _binary(self) -> str | None:
        return shutil.which("tmux")

    def probe(self) -> Probe:
        binary = self._binary()
        if binary is None:
            return Probe("tmux", "missing", remediation_category="install_tmux")
        result = self._runner.run((binary, "-V"), cwd=Path.cwd(), timeout_seconds=1.0, capture_limit=256, env_names=SAFE_ENV_NAMES)
        if result.timed_out:
            return Probe("tmux", "timeout", binary, remediation_category="tmux_probe_timeout")
        if result.exit_code != 0:
            return Probe("tmux", "error", binary, remediation_category="tmux_probe_failed")
        return Probe("tmux", "ready", binary, result.stdout.strip()[:256] or None, None)

    def _require(self) -> str:
        binary = self._binary()
        if binary is None:
            raise error(ErrorCode.PREFLIGHT_BLOCKED, "tmux is not installed", "preflight", "Install tmux and rerun doctor.")
        return binary

    @staticmethod
    def _session(name: str) -> str:
        if not _SESSION.fullmatch(name):
            raise ValueError("invalid tmux session name")
        return name

    def has_session(self, session_name: str) -> bool:
        binary = self._require()
        result = self._runner.run((binary, "has-session", "-t", self._session(session_name)), cwd=Path.cwd(), timeout_seconds=1.0, capture_limit=256, env_names=SAFE_ENV_NAMES)
        if result.timed_out or result.exit_code not in (0, 1):
            raise error(
                ErrorCode.COMMAND_FAILED,
                "tmux session liveness could not be established",
                "command-failed",
                "Inspect tmux availability before retrying session compensation.",
            )
        return result.exit_code == 0

    def create_session(self, session_name: str, descriptor_path: Path) -> None:
        binary = self._require()
        descriptor = descriptor_path.resolve()
        # tmux's shell-command is the sole intentional shell seam. Every dynamic value
        # is a validated descriptor path and quoted as one argument.
        entry_argv = ("nebula-agents", "session-entry", "--descriptor", str(descriptor))
        if descriptor.parent.parent.name == "runs":
            runtime_root = descriptor.parent.parent.parent
            entry_argv = ("env", f"NEBULA_AGENTS_RUNTIME_DIR={runtime_root}", *entry_argv)
        command = shlex.join(entry_argv)
        result = self._runner.run((binary, "new-session", "-d", "-s", self._session(session_name), command), cwd=descriptor.parent, timeout_seconds=5.0, capture_limit=1024, env_names=SAFE_ENV_NAMES)
        if result.exit_code != 0:
            raise error(ErrorCode.COMMAND_FAILED, "tmux could not create the session", "command-failed", "Inspect tmux availability and retry.")

    def kill_session(self, session_name: str) -> None:
        binary = self._require()
        result = self._runner.run(
            (binary, "kill-session", "-t", self._session(session_name)),
            cwd=Path.cwd(),
            timeout_seconds=2.0,
            capture_limit=256,
            env_names=SAFE_ENV_NAMES,
        )
        # A concurrently exited session already satisfies compensation.
        if result.exit_code != 0 and self.has_session(session_name):
            raise error(ErrorCode.COMMAND_FAILED, "tmux session compensation failed", "command-failed", "Inspect the sanitized run timeline and terminate the recorded session.")

    def attach(self, session_name: str) -> int:
        binary = self._require()
        environment = {name: os.environ[name] for name in SAFE_ENV_NAMES if name in os.environ}
        return subprocess.call((binary, "attach-session", "-t", self._session(session_name)), env=environment, shell=False)

    def configure_pipe(self, session_name: str, filter_argv: Sequence[str] | None) -> None:
        binary = self._require()
        if filter_argv is None:
            argv = (binary, "pipe-pane", "-t", self._session(session_name))
        else:
            argv = (binary, "pipe-pane", "-o", "-t", self._session(session_name), shlex.join(tuple(filter_argv)))
        result = self._runner.run(argv, cwd=Path.cwd(), timeout_seconds=2.0, capture_limit=512, env_names=SAFE_ENV_NAMES)
        if result.exit_code != 0:
            raise error(ErrorCode.COMMAND_FAILED, "tmux transcript pipe could not be configured", "command-failed", "Keep the session available and retry transcript capture.")

    def pipe_active(self, session_name: str) -> bool:
        binary = self._require()
        result = self._runner.run(
            (binary, "display-message", "-p", "-t", self._session(session_name), "#{pane_pipe}"),
            cwd=Path.cwd(),
            timeout_seconds=1.0,
            capture_limit=64,
            env_names=SAFE_ENV_NAMES,
        )
        value = result.stdout.strip()
        if result.timed_out or result.exit_code != 0 or value not in ("0", "1"):
            raise error(
                ErrorCode.COMMAND_FAILED,
                "tmux transcript pipe liveness could not be established",
                "command-failed",
                "Keep transcript state active and inspect the tmux session.",
            )
        return value == "1"

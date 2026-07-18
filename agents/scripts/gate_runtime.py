#!/usr/bin/env python3
"""Shared shell-free typed-operation runtime (F0007-S0004).

One execution path for both the lifecycle runner and (later) the action gate
driver. Commands are argv arrays passed directly to ``subprocess`` — there is no
``shell=True`` and no string is ever handed to a shell. ``execute_argv`` is the
low-level shell-free exec (process-group isolation + timeout kill so no child is
orphaned; a ``capture`` toggle so callers that want console streaming, like the
lifecycle runner, keep it). ``run_operation`` layers typed-operation semantics
(placeholder expansion, cwd label mapping, declared-mutation enforcement,
timeout) and appends normalized telemetry through ``append-command-log.py`` — the
single command-log normalization path.

No spec content reaches a shell interpreter.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shlex
import signal
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
FRAMEWORK_ROOT = SCRIPT_DIR.parents[1]
FRAMEWORK_TELEMETRY_LABEL = "nebula-agents"
PRODUCT_TELEMETRY_LABEL = "{PRODUCT_ROOT}"
PLACEHOLDER_RE = re.compile(r"\{([^{}]+)\}")

sys.path.insert(0, str(SCRIPT_DIR))
import validate_action_specs as vas  # noqa: E402  (mutation-class allowlist)


def _load_hyphenated(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_acl = None


def _append_command_log():
    global _acl
    if _acl is None:
        _acl = _load_hyphenated("append_command_log", "append-command-log.py")
    return _acl


class GateRuntimeError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ExecResult:
    argv: list[str]
    cwd: str
    exit_code: int
    timed_out: bool
    signal: int | None
    started_at: str
    ended_at: str
    stdout: str | None = None
    stderr: str | None = None


def _kill_process_group(proc: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        else:  # pragma: no cover - non-posix fallback
            proc.kill()
    except (ProcessLookupError, PermissionError):
        pass


def execute_argv(argv: list[str], *, cwd: Path, timeout: float | None = None,
                 capture: bool = True) -> ExecResult:
    """Run *argv* shell-free in *cwd*. Never invokes a shell.

    On timeout the whole process group is killed so no grandchild is orphaned.
    With ``capture=False`` stdout/stderr are inherited (console streaming).
    """
    if not argv:
        raise GateRuntimeError("empty_argv", "argv must be non-empty")
    popen_kwargs: dict[str, Any] = {"cwd": str(cwd)}
    if capture:
        popen_kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if os.name == "posix":
        popen_kwargs["start_new_session"] = True  # isolate the child's process group

    started = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        proc = subprocess.Popen(argv, **popen_kwargs)  # shell=False (default)
    except FileNotFoundError as exc:
        raise GateRuntimeError("executable_not_found", f"executable not found: {argv[0]!r} ({exc})")
    except OSError as exc:
        raise GateRuntimeError("exec_failed", f"could not launch {argv[0]!r}: {exc}")

    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process_group(proc)
        stdout, stderr = proc.communicate()
        timed_out = True
    ended = datetime.now().astimezone().isoformat(timespec="seconds")

    rc = proc.returncode
    sig = -rc if rc is not None and rc < 0 else None
    return ExecResult(argv=argv, cwd=str(cwd), exit_code=rc, timed_out=timed_out,
                      signal=sig, started_at=started, ended_at=ended,
                      stdout=stdout, stderr=stderr)


def _expand(token: str, variables: dict[str, Any] | None) -> str:
    if variables is None:
        return token  # exec-and-log passes literal argv; no expansion

    def repl(match: re.Match) -> str:
        name = match.group(1)
        if name not in variables:
            raise GateRuntimeError("unresolved_placeholder",
                                   f"unresolved placeholder {{{name}}} in {token!r}")
        return str(variables[name])

    return PLACEHOLDER_RE.sub(repl, token)


def _resolve_cwd(label: str, product_root: Path) -> tuple[Path, str]:
    """Map a spec cwd label to a real directory + a telemetry label.

    Only ``framework`` and ``product`` (optionally with a contained subpath) are
    allowed; a caller cannot authorize a path escape by supplying another string.
    """
    base, _, sub = label.partition("/")
    if base == "framework":
        root, tel = FRAMEWORK_ROOT, FRAMEWORK_TELEMETRY_LABEL
    elif base == "product":
        root, tel = product_root, PRODUCT_TELEMETRY_LABEL
    else:
        raise GateRuntimeError("unknown_cwd_label",
                               f"cwd label must be 'framework' or 'product', got {label!r}")
    if not sub:
        return root, tel
    if ".." in Path(sub).parts or Path(sub).is_absolute():
        raise GateRuntimeError("cwd_escapes_root", f"cwd subpath escapes root: {label!r}")
    resolved = (root / sub).resolve()
    if root not in resolved.parents and resolved != root:
        raise GateRuntimeError("cwd_escapes_root", f"cwd subpath escapes root: {label!r}")
    return resolved, f"{tel}/{sub}"


def run_operation(op: dict[str, Any], *, product_root: Path, variables: dict[str, Any] | None = None,
                  run_folder: Path | None = None, log_path: Path | None = None,
                  extra_artifacts: list[str] | None = None,
                  redactions: list[str] | None = None) -> dict[str, Any]:
    """Execute one typed ``run`` operation shell-free and append telemetry.

    Rejects undeclared mutation classes and unknown cwd labels with named errors;
    logs exit status + durable artifacts through append-command-log.py.
    """
    if "run" not in op or not isinstance(op["run"], dict):
        raise GateRuntimeError("not_a_run_op", "run_operation only executes typed 'run' operations")
    body = op["run"]

    for cls in body.get("mutates", []) or []:
        if cls not in vas.ALLOWED_MUTATION_CLASSES:
            raise GateRuntimeError("undeclared_mutation_class",
                                   f"mutation class {cls!r} is not in the allowlist")

    argv = [_expand(str(tok), variables) for tok in body.get("argv", [])]
    cwd_path, cwd_label = _resolve_cwd(str(body.get("cwd", "")), product_root)
    timeout = body.get("timeout_seconds")

    result = execute_argv(argv, cwd=cwd_path, timeout=timeout, capture=True)

    artifacts = list(extra_artifacts or [])
    if run_folder is not None:
        for name in body.get("expected_artifacts", []) or []:
            candidate = run_folder / name
            if candidate.exists():
                artifacts.append(str(candidate))

    log_written = False
    if log_path is not None:
        acl = _append_command_log()
        try:
            normalized_artifacts = [acl.normalize_artifact(a, product_root) for a in artifacts]
            entry = acl.build_entry(
                cwd=cwd_label,
                command=shlex.join(argv),  # readable representation for the log only; never executed
                exit_code=result.exit_code,
                artifacts=normalized_artifacts,
                redactions=[r for r in (redactions or []) if r],
            )
            acl.append_entry(log_path, entry)
            log_written = True
        except acl.CommandLogError as exc:
            raise GateRuntimeError("log_write_failed", f"telemetry normalization failed: {exc}")

    return {
        "op_id": body.get("id"),
        "argv": argv,
        "cwd": cwd_label,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "signal": result.signal,
        "started_at": result.started_at,
        "ended_at": result.ended_at,
        "artifacts": artifacts,
        "log_written": log_written,
        "ok": result.exit_code == 0 and not result.timed_out,
    }

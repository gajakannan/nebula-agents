"""Owner-only tmux entry boundary for native provider execution.

Tmux necessarily accepts a command string.  The only supported command string
enters here with a descriptor path; every variable value remains structured JSON
and becomes a direct ``execvpe`` argv element only after revalidation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn
from uuid import UUID

_RUN_ID = re.compile(r"^\d{4}-\d{2}-\d{2}-[0-9a-f]{8}$")
_ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]{0,79}$")
_MAX_DESCRIPTOR_BYTES = 1_048_576
_REQUIRED_FIELDS = {
    "schema_version",
    "run_id",
    "provider_key",
    "executable_path",
    "argv",
    "cwd",
    "inherited_env_names",
    "owner_uid",
    "correlation_id",
    "created_at",
}

# Values remain provider-owned, but names crossing this boundary are fixed.
ALLOWED_ENV_NAMES = frozenset(
    {
        "CLAUDE_CONFIG_DIR",
        "CODEX_HOME",
        "COLORTERM",
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LOGNAME",
        "NO_COLOR",
        "PATH",
        "SHELL",
        "TERM",
        "TMPDIR",
        "USER",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
    }
)


class SessionEntryError(RuntimeError):
    pass


def load_validated_descriptor(path: Path) -> dict[str, Any]:
    """Load and validate a launch descriptor without following a final symlink."""

    requested = path.expanduser()
    if not requested.is_absolute():
        raise SessionEntryError("Descriptor path must be absolute.")
    try:
        if requested.is_symlink():
            raise SessionEntryError("Descriptor cannot be a symbolic link.")
        resolved = requested.resolve(strict=True)
    except OSError as error:
        raise SessionEntryError("Descriptor is not available.") from error

    runtime_root = _runtime_root_for(resolved)
    if not resolved.is_relative_to(runtime_root) or resolved == runtime_root:
        raise SessionEntryError("Descriptor is outside the runtime root.")
    _validate_private_directory(runtime_root)
    current = runtime_root
    for component in resolved.parent.relative_to(runtime_root).parts:
        current = current / component
        _validate_private_directory(current)

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor_fd = os.open(resolved, flags)
    except OSError as error:
        raise SessionEntryError("Descriptor cannot be opened safely.") from error
    try:
        metadata = os.fstat(descriptor_fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise SessionEntryError("Descriptor must be a regular file.")
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise SessionEntryError("Descriptor permissions must be 0600.")
        if metadata.st_uid != os.getuid():
            raise SessionEntryError("Descriptor owner does not match the current user.")
        if metadata.st_size <= 0 or metadata.st_size > _MAX_DESCRIPTOR_BYTES:
            raise SessionEntryError("Descriptor size is invalid.")
        payload = os.read(descriptor_fd, _MAX_DESCRIPTOR_BYTES + 1)
    finally:
        os.close(descriptor_fd)

    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SessionEntryError("Descriptor is not valid UTF-8 JSON.") from error
    _validate_document(document, resolved)
    return document


def execute_descriptor(path: Path) -> NoReturn:
    descriptor = load_validated_descriptor(path)
    executable = descriptor["executable_path"]
    argv = tuple(descriptor["argv"])
    cwd = descriptor["cwd"]
    environment = {
        name: os.environ[name]
        for name in descriptor["inherited_env_names"]
        if name in os.environ
    }
    os.chdir(cwd)
    # Validation is the helper acknowledgement.  Minimize the lifetime of argv.
    try:
        path.unlink()
    except OSError as error:
        raise SessionEntryError("Validated descriptor could not be retired.") from error
    os.execvpe(executable, argv, environment)
    raise AssertionError("os.execvpe returned unexpectedly")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nebula-agents session-entry", add_help=False)
    parser.add_argument("--descriptor", required=True)
    try:
        namespace = parser.parse_args(list(argv) if argv is not None else None)
        execute_descriptor(Path(namespace.descriptor))
    except SystemExit as error:
        return int(error.code)
    except SessionEntryError:
        print("session-entry: launch descriptor validation failed", file=sys.stderr)
        return 9
    except OSError:
        print("session-entry: provider execution failed", file=sys.stderr)
        return 8
    return 8


def _runtime_root_for(descriptor_path: Path) -> Path:
    override = os.environ.get("NEBULA_AGENTS_RUNTIME_DIR")
    if override:
        candidate = Path(override).expanduser()
        if not candidate.is_absolute():
            raise SessionEntryError("Runtime override must be absolute.")
        try:
            return candidate.resolve(strict=True)
        except OSError as error:
            raise SessionEntryError("Runtime override is not available.") from error
    for candidate in descriptor_path.parents:
        if candidate.name == "runtime" and candidate.parent.name == ".nebula-agents":
            return candidate
    raise SessionEntryError("Descriptor is not under a Nebula runtime root.")


def _validate_private_directory(path: Path) -> None:
    try:
        metadata = path.stat()
    except OSError as error:
        raise SessionEntryError("Runtime directory is not available.") from error
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
        raise SessionEntryError("Runtime directory ownership is invalid.")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise SessionEntryError("Runtime directory is accessible by another user.")


def _validate_document(document: object, descriptor_path: Path) -> None:
    if not isinstance(document, Mapping) or set(document) != _REQUIRED_FIELDS:
        raise SessionEntryError("Descriptor fields do not match the contract.")
    if document["schema_version"] != "1.0":
        raise SessionEntryError("Descriptor schema version is unsupported.")
    run_id = document["run_id"]
    if not isinstance(run_id, str) or _RUN_ID.fullmatch(run_id) is None:
        raise SessionEntryError("Descriptor run ID is invalid.")
    if descriptor_path.parent.name != run_id:
        raise SessionEntryError("Descriptor is not contained by its run directory.")
    provider_key = document["provider_key"]
    if not isinstance(provider_key, str) or provider_key not in {"codex", "claude"}:
        raise SessionEntryError("Descriptor provider is invalid.")
    owner_uid = document["owner_uid"]
    if not isinstance(owner_uid, int) or isinstance(owner_uid, bool) or owner_uid != os.getuid():
        raise SessionEntryError("Descriptor subject is invalid.")

    executable_text = document["executable_path"]
    if not isinstance(executable_text, str) or not executable_text:
        raise SessionEntryError("Descriptor executable is invalid.")
    executable = Path(executable_text)
    if not executable.is_absolute():
        raise SessionEntryError("Descriptor executable must be absolute.")
    try:
        canonical_executable = executable.resolve(strict=True)
    except OSError as error:
        raise SessionEntryError("Descriptor executable is not available.") from error
    if str(canonical_executable) != executable_text or not canonical_executable.is_file() or not os.access(canonical_executable, os.X_OK):
        raise SessionEntryError("Descriptor executable is not canonical and executable.")

    arguments = document["argv"]
    if (
        not isinstance(arguments, list)
        or not 1 <= len(arguments) <= 128
        or any(not isinstance(argument, str) or len(argument) > 65_536 or "\0" in argument for argument in arguments)
        or arguments[0] != executable_text
    ):
        raise SessionEntryError("Descriptor argv is invalid.")

    cwd_text = document["cwd"]
    if not isinstance(cwd_text, str) or not cwd_text:
        raise SessionEntryError("Descriptor working directory is invalid.")
    cwd = Path(cwd_text)
    if not cwd.is_absolute():
        raise SessionEntryError("Descriptor working directory must be absolute.")
    try:
        canonical_cwd = cwd.resolve(strict=True)
    except OSError as error:
        raise SessionEntryError("Descriptor working directory is not available.") from error
    if str(canonical_cwd) != cwd_text or not canonical_cwd.is_dir():
        raise SessionEntryError("Descriptor working directory is not canonical.")

    names = document["inherited_env_names"]
    if (
        not isinstance(names, list)
        or len(names) > 32
        or any(not isinstance(name, str) or _ENV_NAME.fullmatch(name) is None or name not in ALLOWED_ENV_NAMES for name in names)
        or len(names) != len(set(names))
    ):
        raise SessionEntryError("Descriptor environment allowlist is invalid.")
    correlation_id = document["correlation_id"]
    created_at_text = document["created_at"]
    if not isinstance(correlation_id, str) or not isinstance(created_at_text, str):
        raise SessionEntryError("Descriptor metadata is invalid.")
    try:
        UUID(correlation_id)
        created_at = datetime.fromisoformat(created_at_text.replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise SessionEntryError("Descriptor metadata is invalid.") from error
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise SessionEntryError("Descriptor timestamp must include a UTC offset.")

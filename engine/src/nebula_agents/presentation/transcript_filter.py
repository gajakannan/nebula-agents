"""Redact tmux pipe bytes before their first durable transcript write."""

from __future__ import annotations

import argparse
import os
import re
import stat
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import BinaryIO

from .session_entry import SessionEntryError, _runtime_root_for, _validate_private_directory

_RUN_ID = re.compile(r"^\d{4}-\d{2}-\d{2}-[0-9a-f]{8}$")
_CHUNK_BYTES = 4096


class TranscriptFilterError(RuntimeError):
    def __init__(self, message: str, *, exit_code: int = 9) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def filter_stream(run_id: str, output_path: Path, source: BinaryIO) -> None:
    if _RUN_ID.fullmatch(run_id) is None:
        raise TranscriptFilterError("Run ID is invalid.", exit_code=2)
    path = _validated_output_path(run_id, output_path)
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        output_fd = os.open(path, flags, 0o600)
    except OSError as error:
        raise TranscriptFilterError("Transcript output cannot be opened safely.") from error
    try:
        metadata = os.fstat(output_fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o600:
            raise TranscriptFilterError("Transcript output ownership or permissions are invalid.")
        redactor = _streaming_redactor()
        while True:
            chunk = source.read(_CHUNK_BYTES)
            if not chunk:
                break
            if not isinstance(chunk, bytes):
                raise TranscriptFilterError("Transcript source must provide bytes.", exit_code=8)
            _write_redacted(output_fd, redactor.feed(chunk))
        _write_redacted(output_fd, redactor.finalize())
        os.fsync(output_fd)
    except TranscriptFilterError:
        raise
    except Exception as error:
        raise TranscriptFilterError("Transcript redaction failed.", exit_code=8) from error
    finally:
        os.close(output_fd)


def main(argv: Sequence[str] | None = None, *, source: BinaryIO | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nebula-agents transcript-filter", add_help=False)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--path", required=True)
    try:
        namespace = parser.parse_args(list(argv) if argv is not None else None)
        stream = source if source is not None else sys.stdin.buffer
        filter_stream(namespace.run_id, Path(namespace.path), stream)
        return 0
    except SystemExit as error:
        return int(error.code)
    except (TranscriptFilterError, SessionEntryError) as error:
        print("transcript-filter: capture failed safely", file=sys.stderr)
        return getattr(error, "exit_code", 9)


def _validated_output_path(run_id: str, requested: Path) -> Path:
    requested = requested.expanduser()
    if not requested.is_absolute() or requested.name in {"", ".", ".."}:
        raise TranscriptFilterError("Transcript path must be absolute.", exit_code=2)
    if requested.exists() and requested.is_symlink():
        raise TranscriptFilterError("Transcript path cannot be a symbolic link.")
    try:
        parent = requested.parent.resolve(strict=True)
    except OSError as error:
        raise TranscriptFilterError("Transcript directory is not available.") from error
    path = parent / requested.name
    runtime_root = _runtime_root_for(path)
    if not path.is_relative_to(runtime_root):
        raise TranscriptFilterError("Transcript path is outside its run directory.")
    relative_parts = path.relative_to(runtime_root).parts
    if len(relative_parts) >= 2 and relative_parts[0] == run_id:
        run_root = runtime_root / run_id
    elif len(relative_parts) >= 3 and relative_parts[0] == "runs" and relative_parts[1] == run_id:
        run_root = runtime_root / "runs" / run_id
    else:
        raise TranscriptFilterError("Transcript path is outside its run directory.")
    _validate_private_directory(runtime_root)
    current = runtime_root
    for component in run_root.relative_to(runtime_root).parts:
        current = current / component
        _validate_private_directory(current)
    current = run_root
    for component in parent.relative_to(run_root).parts:
        current = current / component
        _validate_private_directory(current)
    return path


def _streaming_redactor() -> object:
    try:
        from nebula_agents.domain.redaction import StreamingRedactor
    except (ImportError, AttributeError) as error:
        raise TranscriptFilterError("Streaming redactor is unavailable.", exit_code=8) from error
    return StreamingRedactor()


def _write_redacted(file_descriptor: int, payload: object) -> None:
    if not isinstance(payload, bytes):
        raise TranscriptFilterError("Streaming redactor returned invalid output.", exit_code=8)
    remaining = memoryview(payload)
    while remaining:
        written = os.write(file_descriptor, remaining)
        if written <= 0:
            raise TranscriptFilterError("Transcript output write did not progress.")
        remaining = remaining[written:]

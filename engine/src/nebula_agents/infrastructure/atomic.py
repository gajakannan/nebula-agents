"""Owner-only locking and atomic writes, shared by every local store (ADR-002).

F0001 established this discipline for `run.json`: a per-directory advisory lock, a
same-directory temporary file, `fsync` before publish, atomic replace, and mode `0600`
inside `0700`. F0003 adds two more stores that need exactly the same guarantees.

These primitives are extracted rather than copied. A second hand-written copy of a
locking and fsync routine is how the two drift — one gets a fix the other never sees,
and the divergence is invisible until a crash exposes it.
"""

from __future__ import annotations

import fcntl
import json
import os
import stat
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from nebula_agents.domain.errors import ErrorCode, error

FILE_MODE = 0o600
DIRECTORY_MODE = 0o700


def json_bytes(document: object, *, pretty: bool) -> bytes:
    """Deterministic JSON. Sorted keys are what make snapshots comparable."""
    if pretty:
        return (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return (json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def assert_owner_only_directory(directory: Path) -> None:
    """Refuse to operate inside a directory anyone else can reach.

    Checked with `lstat` and an explicit symlink test, because a symlinked state
    directory would otherwise pass a naive mode check while pointing anywhere.
    """
    try:
        details = directory.lstat()
    except OSError as exc:
        raise error(
            ErrorCode.STATE_CORRUPT, "State directory is unavailable", "state-io",
            "Restore the owner-only state directory.",
        ) from exc
    if (
        directory.is_symlink()
        or not stat.S_ISDIR(details.st_mode)
        or details.st_uid != os.getuid()
        or stat.S_IMODE(details.st_mode) != DIRECTORY_MODE
    ):
        raise error(
            ErrorCode.STATE_CORRUPT,
            "State directory ownership or permissions are unsafe", "state-io",
            "Restore the owner-only state directory mode to 0700.",
        )


@contextmanager
def owner_only_lock(directory: Path, timeout_seconds: float, lock_name: str = ".lock") -> Iterator[None]:
    """Exclusive advisory lock on an owner-only directory.

    `lock_name` lets a second store in the same directory take its own lock rather than
    contend with the run lock — the artifact index is a projection and must never block
    a launch.
    """
    assert_owner_only_directory(directory)
    lock_path = directory / lock_name
    fd: int | None = None
    try:
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), FILE_MODE)
        details = os.fstat(fd)
        if not stat.S_ISREG(details.st_mode) or details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) != FILE_MODE:
            raise PermissionError("unsafe state lock")
    except OSError as exc:
        if fd is not None:
            os.close(fd)
        raise error(
            ErrorCode.STATE_CORRUPT, "State lock is unsafe", "state-io",
            "Restore the owner-only state lock.",
        ) from exc
    deadline = time.monotonic() + timeout_seconds
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise error(
                        ErrorCode.STATE_LOCK_TIMEOUT, "State lock timed out", "timeout",
                        "Wait for the active operation and retry.",
                    )
                time.sleep(0.05)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def write_owner_only(path: Path, data: bytes) -> None:
    """Write and fsync a mode-0600 file, refusing to follow a symlink."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), FILE_MODE)
    try:
        remaining = memoryview(data)
        while remaining:
            written = os.write(fd, remaining)
            if written <= 0:
                raise OSError("state write did not progress")
            remaining = remaining[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(path, FILE_MODE)


def publish_atomic(directory: Path, pending: Path, target: Path, backup: Path | None = None) -> None:
    """Replace `target` with `pending`, keeping a backup, then fsync the directory.

    The directory fsync is the step that is easy to omit and expensive to miss: without
    it the rename itself can be lost on power failure, leaving a published temp file and
    no target.
    """
    if backup is not None and target.exists():
        os.replace(target, backup)
        os.chmod(backup, FILE_MODE)
    os.replace(pending, target)
    os.chmod(target, FILE_MODE)
    dir_fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def preserve_corrupt(path: Path, marker: str) -> Path | None:
    """Move an unreadable state file aside instead of deleting it.

    A corrupt index is still evidence of what happened. Losing it costs the only record
    of the failure.
    """
    if not path.exists() or path.is_symlink():
        return None
    preserved = path.with_name(f"{path.name}.corrupt-{marker}")
    try:
        os.replace(path, preserved)
        os.chmod(preserved, FILE_MODE)
        return preserved
    except OSError:
        return None

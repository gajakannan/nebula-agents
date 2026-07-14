from __future__ import annotations

import json
import os
import stat
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from nebula_agents.domain.enums import RedactionStatus, TranscriptStatus
from nebula_agents.domain.errors import ErrorCode, error
from nebula_agents.domain.models import RunRecord, TranscriptState
from nebula_agents.domain.redaction import StreamingRedactor

from .tmux import TmuxAdapter


_STATUS_NAME = "transcript-status.json"
_STATUS_LIMIT = 16 * 1024
_STATUS_VALUES = frozenset({"active", "stopping", "completed", "failed"})
_FAILURE_REASONS = frozenset({
    "capture-process-not-running",
    "capture-status-unreadable",
    "filter-process-failed",
    "filter-output-failed",
    "filter-status-write-failed",
})


def _private_directory(path: Path) -> Path:
    if path.is_symlink():
        raise PermissionError("unsafe transcript directory")
    resolved = path.resolve(strict=True)
    details = resolved.stat()
    if not resolved.is_dir() or details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) != 0o700:
        raise PermissionError("unsafe transcript directory")
    return resolved


def _status_document(run_directory: Path) -> tuple[dict[str, object] | None, bool]:
    path = run_directory / _STATUS_NAME
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return None, False
    except OSError:
        return None, True
    try:
        details = os.fstat(fd)
        if (
            not stat.S_ISREG(details.st_mode)
            or details.st_uid != os.getuid()
            or stat.S_IMODE(details.st_mode) != 0o600
            or details.st_size > _STATUS_LIMIT
        ):
            return None, True
        payload = bytearray()
        while len(payload) <= _STATUS_LIMIT:
            chunk = os.read(fd, min(4096, _STATUS_LIMIT + 1 - len(payload)))
            if not chunk:
                break
            payload.extend(chunk)
        if len(payload) > _STATUS_LIMIT:
            return None, True
        document = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, True
    finally:
        os.close(fd)
    if not isinstance(document, dict):
        return None, True
    status_value = document.get("status")
    redaction_value = document.get("redaction_status")
    findings = document.get("findings")
    failure_reason = document.get("failure_reason")
    if (
        set(document) not in (
            {"schema_version", "status", "redaction_status", "findings", "updated_at"},
            {"schema_version", "status", "redaction_status", "findings", "failure_reason", "updated_at"},
        )
        or document.get("schema_version") != "1.0"
        or status_value not in _STATUS_VALUES
        or redaction_value not in {item.value for item in RedactionStatus}
        or not isinstance(findings, int)
        or isinstance(findings, bool)
        or not 0 <= findings <= 1_000_000
        or not isinstance(document.get("updated_at"), str)
        or len(str(document["updated_at"])) > 64
        or failure_reason not in (None, *_FAILURE_REASONS)
        or (status_value == "failed" and failure_reason is None and "failure_reason" in document)
    ):
        return None, True
    return document, True


def write_capture_status(
    run_directory: Path,
    *,
    status_value: str,
    redaction_status: RedactionStatus,
    findings: int,
    failure_reason: str | None = None,
) -> None:
    """Atomically persist a bounded status that never contains transcript data."""
    directory = _private_directory(run_directory)
    if status_value not in _STATUS_VALUES or findings < 0 or failure_reason not in (None, *_FAILURE_REASONS):
        raise ValueError("invalid transcript status")
    document = {
        "schema_version": "1.0",
        "status": status_value,
        "redaction_status": redaction_status.value,
        "findings": min(findings, 1_000_000),
        "failure_reason": failure_reason,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    payload = (json.dumps(document, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    temporary = directory / f".{_STATUS_NAME}.{os.getpid()}.{uuid4().hex}.tmp"
    fd = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        remaining = memoryview(payload)
        while remaining:
            written = os.write(fd, remaining)
            if written <= 0:
                raise OSError("transcript status write did not progress")
            remaining = remaining[written:]
        os.fsync(fd)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    finally:
        os.close(fd)
    try:
        os.replace(temporary, directory / _STATUS_NAME)
        directory_fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def redact_stream(source: BinaryIO, output_path: Path) -> tuple[RedactionStatus, int]:
    redactor = StreamingRedactor()
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(output_path, flags, 0o600)
    try:
        details = os.fstat(fd)
        if not stat.S_ISREG(details.st_mode) or details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) != 0o600:
            raise PermissionError("unsafe transcript file")
        while True:
            chunk = source.read(4096)
            if not chunk:
                break
            if not isinstance(chunk, bytes):
                raise TypeError("transcript source must provide bytes")
            payload = redactor.feed(chunk)
            _write_all(fd, payload)
        _write_all(fd, redactor.finalize())
        os.fsync(fd)
    finally:
        os.close(fd)
    return (RedactionStatus.REDACTED if redactor.findings else RedactionStatus.PASSED), redactor.findings


def _write_all(fd: int, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        written = os.write(fd, remaining)
        if written <= 0:
            raise OSError("transcript write did not progress")
        remaining = remaining[written:]


class TmuxTranscriptAdapter:
    def __init__(self, tmux: TmuxAdapter) -> None:
        self._tmux = tmux

    @staticmethod
    def _contained(run: RunRecord, output_path: Path) -> Path:
        run_dir = Path(run.audit_log_path).resolve().parent
        candidate = output_path.expanduser()
        if candidate.exists() and candidate.is_symlink():
            raise error(ErrorCode.PATH_DENIED, "Transcript path cannot be a symlink", "state-io", "Use the run's owner-only transcript path.")
        resolved_parent = candidate.parent.resolve()
        resolved = resolved_parent / candidate.name
        if resolved.parent != run_dir or resolved.name != "transcript.redacted.log":
            raise error(ErrorCode.PATH_DENIED, "Transcript path escapes the run directory", "state-io", "Use the run's owner-only transcript path.")
        return resolved

    def configure(self, *, run: RunRecord, output_path: Path) -> None:
        path = self._contained(run, output_path)
        if path.exists():
            details = path.stat()
            if not path.is_file() or details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) != 0o600:
                raise error(ErrorCode.PATH_DENIED, "Existing transcript is not owner-only", "state-io", "Repair or remove the unsafe transcript file.")
        else:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            os.close(fd)
        run_directory = Path(run.audit_log_path).resolve().parent
        write_capture_status(
            run_directory,
            status_value="active",
            redaction_status=RedactionStatus.NOT_RUN,
            findings=0,
        )
        filter_argv = (
            sys.executable,
            "-m",
            "nebula_agents.infrastructure.transcript_filter_entry",
            "--run-id",
            run.run_id,
            "--path",
            str(path),
        )
        if run_directory.parent.name == "runs":
            runtime_root = run_directory.parent.parent
            filter_argv = ("env", f"NEBULA_AGENTS_RUNTIME_DIR={runtime_root}", *filter_argv)
        try:
            self._tmux.configure_pipe(run.tmux_session, filter_argv)
        except Exception:
            try:
                write_capture_status(
                    run_directory,
                    status_value="failed",
                    redaction_status=RedactionStatus.FAILED,
                    findings=0,
                    failure_reason="filter-process-failed",
                )
            except Exception:
                pass
            raise

    def disable(self, *, run: RunRecord) -> None:
        run_directory = Path(run.audit_log_path).resolve().parent
        document, _ = _status_document(run_directory)
        was_failed = document is not None and document.get("status") == "failed"
        if not was_failed:
            write_capture_status(
                run_directory,
                status_value="stopping",
                redaction_status=RedactionStatus.NOT_RUN,
                findings=int(document.get("findings", 0)) if document else 0,
            )
        try:
            self._tmux.configure_pipe(run.tmux_session, None)
        except Exception:
            if not was_failed:
                try:
                    write_capture_status(
                        run_directory,
                        status_value="active",
                        redaction_status=RedactionStatus.NOT_RUN,
                        findings=int(document.get("findings", 0)) if document else 0,
                    )
                except Exception:
                    pass
            raise
        # Let the filter finalize its buffered redactor tail before returning.
        # If it cannot publish a terminal sidecar, capture_status will fail
        # closed using the pane pipe liveness probe.
        for attempt in range(21):
            terminal, _ = _status_document(run_directory)
            if terminal is not None and terminal.get("status") in ("completed", "failed"):
                break
            if attempt < 20:
                time.sleep(0.025)

    def is_active(self, *, run: RunRecord) -> bool:
        """Return authoritative tmux pane-pipe liveness for compensation."""
        return self._tmux.pipe_active(run.tmux_session)

    def terminate_session(self, *, run: RunRecord) -> None:
        self._tmux.kill_session(run.tmux_session)

    def session_present(self, *, run: RunRecord) -> bool:
        return self._tmux.has_session(run.tmux_session)

    def capture_status(self, *, run: RunRecord) -> TranscriptState | None:
        if run.transcript.status is not TranscriptStatus.ACTIVE or run.transcript.path is None:
            return None
        path = self._contained(run, Path(run.transcript.path))
        run_directory = path.parent
        document, exists = _status_document(run_directory)
        if document is None:
            if not exists:
                pipe_active = self._tmux.pipe_active(run.tmux_session)
                if pipe_active:
                    return None
                return TranscriptState(
                    TranscriptStatus.FAILED,
                    RedactionStatus.FAILED,
                    str(path),
                    None,
                    run.transcript.redaction_findings,
                    "capture-process-not-running",
                )
            return TranscriptState(TranscriptStatus.FAILED, RedactionStatus.FAILED, str(path), None, run.transcript.redaction_findings, "capture-status-unreadable")
        findings = max(run.transcript.redaction_findings, int(document["findings"]))
        if document["status"] == "failed":
            return TranscriptState(
                TranscriptStatus.FAILED,
                RedactionStatus.FAILED,
                str(path),
                None,
                findings,
                str(document.get("failure_reason") or "filter-process-failed"),
            )
        if document["status"] == "completed":
            redaction = RedactionStatus(str(document["redaction_status"]))
            if redaction not in (RedactionStatus.PASSED, RedactionStatus.REDACTED):
                return TranscriptState(TranscriptStatus.FAILED, RedactionStatus.FAILED, str(path), None, findings, "capture-status-unreadable")
            return TranscriptState(TranscriptStatus.COMPLETED, redaction, str(path), None, findings)
        pipe_active = self._tmux.pipe_active(run.tmux_session)
        if not pipe_active:
            return TranscriptState(
                TranscriptStatus.FAILED,
                RedactionStatus.FAILED,
                str(path),
                None,
                findings,
                "capture-process-not-running",
            )
        return None

    def filter_stream(self, source: BinaryIO, output_path: Path) -> tuple[RedactionStatus, int]:
        return redact_stream(source, output_path)

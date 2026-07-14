"""Private tmux transcript worker with fail-closed status reporting."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import BinaryIO

from nebula_agents.domain.enums import RedactionStatus

from .transcript import _status_document, redact_stream, write_capture_status


_RUN_ID = re.compile(r"^\d{4}-\d{2}-\d{2}-[0-9a-f]{8}$")


def _capture_target(run_id: str, requested: Path) -> tuple[Path, Path]:
    if _RUN_ID.fullmatch(run_id) is None or not requested.is_absolute() or requested.name != "transcript.redacted.log":
        raise ValueError("invalid transcript target")
    if requested.is_symlink():
        raise PermissionError("unsafe transcript target")
    run_directory = requested.parent.resolve(strict=True)
    if run_directory.name != run_id:
        raise PermissionError("unsafe transcript target")
    runtime_value = os.environ.get("NEBULA_AGENTS_RUNTIME_DIR")
    if runtime_value:
        runtime_root = Path(runtime_value).expanduser().resolve(strict=True)
        if run_directory != runtime_root / "runs" / run_id:
            raise PermissionError("unsafe transcript target")
    details = run_directory.stat()
    if details.st_uid != os.getuid() or (details.st_mode & 0o777) != 0o700:
        raise PermissionError("unsafe transcript directory")
    return run_directory, run_directory / requested.name


def run_filter(run_id: str, requested: Path, source: BinaryIO) -> int:
    run_directory, output_path = _capture_target(run_id, requested)
    try:
        redaction, findings = redact_stream(source, output_path)
        document, _ = _status_document(run_directory)
        if document is not None and document.get("status") == "stopping":
            write_capture_status(
                run_directory,
                status_value="completed",
                redaction_status=redaction,
                findings=findings,
            )
            return 0
        write_capture_status(
            run_directory,
            status_value="failed",
            redaction_status=RedactionStatus.FAILED,
            findings=findings,
            failure_reason="capture-process-not-running",
        )
        return 9
    except BaseException:
        try:
            write_capture_status(
                run_directory,
                status_value="failed",
                redaction_status=RedactionStatus.FAILED,
                findings=0,
                failure_reason="filter-output-failed",
            )
        except BaseException:
            pass
        return 8


def main(argv: Sequence[str] | None = None, *, source: BinaryIO | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nebula transcript filter", add_help=False)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--path", required=True)
    try:
        namespace = parser.parse_args(list(argv) if argv is not None else None)
        return run_filter(
            namespace.run_id,
            Path(namespace.path),
            source if source is not None else sys.stdin.buffer,
        )
    except (SystemExit, ValueError, OSError):
        print("transcript capture failed safely", file=sys.stderr)
        return 9


if __name__ == "__main__":
    raise SystemExit(main())

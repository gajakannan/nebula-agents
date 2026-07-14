from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

from nebula_agents.presentation.transcript_filter import (
    TranscriptFilterError,
    filter_stream,
)


RUN_ID = "2026-07-13-deadbeef"


def _runtime_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    run_root = runtime / RUN_ID
    run_root.mkdir(mode=0o700)
    monkeypatch.setenv("NEBULA_AGENTS_RUNTIME_DIR", str(runtime.resolve()))
    return runtime, run_root


def test_filter_writes_only_redacted_bytes_with_owner_only_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, run_root = _runtime_tree(tmp_path, monkeypatch)
    output = run_root / "transcript.redacted.log"
    sentinel = b"Bearer " + b"test-only-token-0123456789abcdef"
    source = io.BytesIO(b"before " + sentinel + b" after\n")

    filter_stream(RUN_ID, output, source)

    persisted = output.read_bytes()
    assert sentinel not in persisted
    assert b"[REDACTED]" in persisted
    assert output.stat().st_mode & 0o777 == 0o600


def test_filter_redacts_secret_crossing_actual_4096_byte_read_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, run_root = _runtime_tree(tmp_path, monkeypatch)
    output = run_root / "transcript.redacted.log"
    sentinel = b"Bearer " + b"test-only-token-0123456789abcdef"
    payload = b"x" * 4095 + sentinel + b"\n" + b"y" * 9000

    filter_stream(RUN_ID, output, io.BytesIO(payload))

    assert sentinel not in output.read_bytes()


def test_filter_rejects_output_outside_exact_run_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, _ = _runtime_tree(tmp_path, monkeypatch)
    other = runtime / "2026-07-13-feedface"
    other.mkdir(mode=0o700)
    with pytest.raises(TranscriptFilterError, match="outside"):
        filter_stream(RUN_ID, other / "transcript.log", io.BytesIO(b"safe"))


def test_filter_rejects_symlink_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, run_root = _runtime_tree(tmp_path, monkeypatch)
    target = run_root / "target.log"
    target.write_bytes(b"")
    target.chmod(0o600)
    symlink = run_root / "transcript.log"
    symlink.symlink_to(target)
    with pytest.raises(TranscriptFilterError, match="symbolic link"):
        filter_stream(RUN_ID, symlink, io.BytesIO(b"safe"))


def test_filter_rejects_preexisting_non_private_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, run_root = _runtime_tree(tmp_path, monkeypatch)
    output = run_root / "transcript.log"
    output.write_bytes(b"")
    output.chmod(0o644)
    with pytest.raises(TranscriptFilterError, match="permissions"):
        filter_stream(RUN_ID, output, io.BytesIO(b"safe"))


def test_filter_does_not_persist_any_bytes_when_source_type_is_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, run_root = _runtime_tree(tmp_path, monkeypatch)
    output = run_root / "transcript.log"

    class TextSource:
        def read(self, _size: int) -> str:
            return "untrusted text"

    with pytest.raises(TranscriptFilterError, match="must provide bytes"):
        filter_stream(RUN_ID, output, TextSource())  # type: ignore[arg-type]
    assert output.read_bytes() == b""


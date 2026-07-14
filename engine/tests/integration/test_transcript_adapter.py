from __future__ import annotations

import io
import os
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from nebula_agents.domain.enums import (
    GateStatus,
    PromptAction,
    ProviderKey,
    RedactionStatus,
    Role,
    RunStatus,
    TranscriptStatus,
)
from nebula_agents.domain.errors import ErrorCode, NebulaError
from nebula_agents.domain.models import (
    Actor,
    GateSnapshot,
    RunRecord,
    TranscriptState,
)
from nebula_agents.infrastructure.transcript import TmuxTranscriptAdapter
from nebula_agents.infrastructure.transcript import write_capture_status
from nebula_agents.infrastructure import transcript_filter_entry
from nebula_agents.infrastructure.transcript_filter_entry import run_filter


NOW = datetime(2026, 7, 13, 18, 0, tzinfo=UTC)
RUN_ID = "2026-07-13-deadbeef"


class Tmux:
    def __init__(self, pipe_error: Exception | None = None) -> None:
        self.calls: list[tuple[str, object]] = []
        self.active = False
        self.pipe_error = pipe_error
        self.present = True

    def configure_pipe(self, session_name, filter_argv):
        self.calls.append((session_name, filter_argv))
        self.active = filter_argv is not None

    def pipe_active(self, session_name: str) -> bool:
        assert session_name == "nebula-F0001-deadbeef"
        if self.pipe_error is not None:
            raise self.pipe_error
        return self.active

    def kill_session(self, session_name: str) -> None:
        assert session_name == "nebula-F0001-deadbeef"
        self.present = False
        self.active = False

    def has_session(self, session_name: str) -> bool:
        assert session_name == "nebula-F0001-deadbeef"
        return self.present


def _run(run_root: Path) -> RunRecord:
    return RunRecord(
        "1.0",
        1,
        RUN_ID,
        "F0001",
        None,
        ProviderKey.CODEX,
        "nebula-F0001-deadbeef",
        str(run_root.parent),
        str(run_root.parent / "prompt.md"),
        PromptAction.FEATURE,
        RunStatus.ACTIVE,
        Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR),
        None,
        GateSnapshot("G1", GateStatus.PENDING, False, (), None),
        None,
        (),
        TranscriptState(TranscriptStatus.DISABLED, RedactionStatus.NOT_RUN, None, None, 0),
        str(run_root / "events.jsonl"),
        2,
        NOW,
        NOW,
        NOW,
    )


def test_configure_creates_private_exact_path_and_registers_filter(tmp_path: Path) -> None:
    run_root = tmp_path / RUN_ID
    run_root.mkdir(mode=0o700)
    tmux = Tmux()
    adapter = TmuxTranscriptAdapter(tmux)  # type: ignore[arg-type]
    output = run_root / "transcript.redacted.log"
    adapter.configure(run=_run(run_root), output_path=output)
    assert adapter.is_active(run=_run(run_root)) is True
    assert output.is_file()
    assert output.stat().st_mode & 0o777 == 0o600
    session, argv = tmux.calls[0]
    assert session == "nebula-F0001-deadbeef"
    assert argv == (
        sys.executable,
        "-m",
        "nebula_agents.infrastructure.transcript_filter_entry",
        "--run-id",
        RUN_ID,
        "--path",
        str(output),
    )
    adapter.configure(run=_run(run_root), output_path=output)
    assert len(tmux.calls) == 2


@pytest.mark.parametrize("name", ["other.log", "../transcript.redacted.log"])
def test_configure_rejects_noncanonical_output_path(tmp_path: Path, name: str) -> None:
    run_root = tmp_path / RUN_ID
    run_root.mkdir(mode=0o700)
    adapter = TmuxTranscriptAdapter(Tmux())  # type: ignore[arg-type]
    with pytest.raises(NebulaError) as caught:
        adapter.configure(run=_run(run_root), output_path=run_root / name)
    assert caught.value.code is ErrorCode.PATH_DENIED


def test_configure_rejects_symlink_and_unsafe_existing_file(tmp_path: Path) -> None:
    run_root = tmp_path / RUN_ID
    run_root.mkdir(mode=0o700)
    adapter = TmuxTranscriptAdapter(Tmux())  # type: ignore[arg-type]
    target = run_root / "target.log"
    target.write_bytes(b"")
    target.chmod(0o600)
    output = run_root / "transcript.redacted.log"
    output.symlink_to(target)
    with pytest.raises(NebulaError):
        adapter.configure(run=_run(run_root), output_path=output)
    output.unlink()
    output.write_bytes(b"")
    output.chmod(0o644)
    with pytest.raises(NebulaError):
        adapter.configure(run=_run(run_root), output_path=output)


def test_disable_removes_pipe_from_exact_session(tmp_path: Path) -> None:
    run_root = tmp_path / RUN_ID
    run_root.mkdir(mode=0o700)
    tmux = Tmux()
    adapter = TmuxTranscriptAdapter(tmux)  # type: ignore[arg-type]
    adapter.disable(run=_run(run_root))
    assert tmux.calls == [("nebula-F0001-deadbeef", None)]
    assert adapter.is_active(run=_run(run_root)) is False


def test_capture_status_propagates_pipe_probe_failure(tmp_path: Path) -> None:
    run_root = tmp_path / RUN_ID
    run_root.mkdir(mode=0o700)
    output = run_root / "transcript.redacted.log"
    output.write_bytes(b"")
    output.chmod(0o600)
    active = replace(
        _run(run_root),
        transcript=TranscriptState(
            TranscriptStatus.ACTIVE,
            RedactionStatus.NOT_RUN,
            str(output),
            None,
            0,
        ),
    )
    adapter = TmuxTranscriptAdapter(Tmux(RuntimeError("probe unavailable")))  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="probe unavailable"):
        adapter.capture_status(run=active)


def test_transcript_adapter_terminates_and_verifies_owning_session(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / RUN_ID
    run_root.mkdir(mode=0o700)
    tmux = Tmux()
    adapter = TmuxTranscriptAdapter(tmux)  # type: ignore[arg-type]
    run = _run(run_root)

    assert adapter.session_present(run=run) is True
    adapter.terminate_session(run=run)
    assert adapter.session_present(run=run) is False


def test_filter_stream_redacts_before_private_append_and_reports_findings(
    tmp_path: Path,
) -> None:
    output = tmp_path / "transcript.log"
    sentinel = b"Bearer " + b"test-only-token-0123456789abcdef"
    adapter = TmuxTranscriptAdapter(Tmux())  # type: ignore[arg-type]
    status, findings = adapter.filter_stream(
        io.BytesIO(b"before " + sentinel + b" after"), output
    )
    assert status is RedactionStatus.REDACTED
    assert findings == 1
    assert sentinel not in output.read_bytes()
    assert output.stat().st_mode & 0o777 == 0o600
    status, findings = adapter.filter_stream(io.BytesIO(b" ordinary"), output)
    assert status is RedactionStatus.PASSED
    assert findings == 0
    assert b"ordinary" in output.read_bytes()


def test_filter_stream_rejects_text_source_and_unsafe_output_mode(tmp_path: Path) -> None:
    adapter = TmuxTranscriptAdapter(Tmux())  # type: ignore[arg-type]

    class TextSource:
        def read(self, _size):
            return "text"

    with pytest.raises(TypeError, match="bytes"):
        adapter.filter_stream(TextSource(), tmp_path / "new.log")  # type: ignore[arg-type]
    output = tmp_path / "unsafe.log"
    output.write_bytes(b"")
    output.chmod(0o644)
    with pytest.raises(PermissionError, match="unsafe"):
        adapter.filter_stream(io.BytesIO(b"safe"), output)


def test_private_worker_failure_is_durable_for_lifecycle_reconciliation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "runtime"
    run_root = runtime / "runs" / RUN_ID
    run_root.mkdir(mode=0o700, parents=True)
    runtime.chmod(0o700)
    (runtime / "runs").chmod(0o700)
    monkeypatch.setenv("NEBULA_AGENTS_RUNTIME_DIR", str(runtime.resolve()))
    run = _run(run_root)
    adapter = TmuxTranscriptAdapter(Tmux())  # type: ignore[arg-type]
    output = run_root / "transcript.redacted.log"
    adapter.configure(run=run, output_path=output)

    class FailingSource:
        def read(self, _size: int) -> bytes:
            raise OSError("simulated pipe failure")

    assert run_filter(RUN_ID, output, FailingSource()) == 8  # type: ignore[arg-type]
    observed = adapter.capture_status(
        run=replace(
            run,
            transcript=TranscriptState(
                TranscriptStatus.ACTIVE,
                RedactionStatus.NOT_RUN,
                str(output),
                None,
                0,
            ),
        )
    )
    assert observed is not None
    assert observed.status is TranscriptStatus.FAILED
    assert observed.redaction_status is RedactionStatus.FAILED


@pytest.mark.parametrize(
    ("status_value", "redaction", "failure_reason", "expected_status"),
    [
        ("completed", RedactionStatus.REDACTED, None, TranscriptStatus.COMPLETED),
        (
            "failed",
            RedactionStatus.FAILED,
            "filter-output-failed",
            TranscriptStatus.FAILED,
        ),
    ],
)
def test_restart_recovers_completed_and_failed_worker_sidecars(
    tmp_path: Path,
    status_value: str,
    redaction: RedactionStatus,
    failure_reason: str | None,
    expected_status: TranscriptStatus,
) -> None:
    run_root = tmp_path / RUN_ID
    run_root.mkdir(mode=0o700)
    output = run_root / "transcript.redacted.log"
    output.write_bytes(b"safe [REDACTED]")
    output.chmod(0o600)
    write_capture_status(
        run_root,
        status_value=status_value,
        redaction_status=redaction,
        findings=3,
        failure_reason=failure_reason,
    )
    active = replace(
        _run(run_root),
        transcript=TranscriptState(
            TranscriptStatus.ACTIVE,
            RedactionStatus.NOT_RUN,
            str(output),
            None,
            1,
        ),
    )

    observed = TmuxTranscriptAdapter(Tmux()).capture_status(run=active)  # type: ignore[arg-type]

    assert observed is not None
    assert observed.status is expected_status
    assert observed.redaction_status is redaction
    assert observed.redaction_findings == 3
    assert observed.failure_reason == failure_reason


def test_worker_and_sidecar_write_failure_is_recovered_from_stale_pipe_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "runtime"
    run_root = runtime / "runs" / RUN_ID
    run_root.mkdir(mode=0o700, parents=True)
    runtime.chmod(0o700)
    (runtime / "runs").chmod(0o700)
    monkeypatch.setenv("NEBULA_AGENTS_RUNTIME_DIR", str(runtime.resolve()))
    tmux = Tmux()
    adapter = TmuxTranscriptAdapter(tmux)  # type: ignore[arg-type]
    run = _run(run_root)
    output = run_root / "transcript.redacted.log"
    adapter.configure(run=run, output_path=output)
    active = replace(
        run,
        transcript=TranscriptState(
            TranscriptStatus.ACTIVE,
            RedactionStatus.NOT_RUN,
            str(output),
            None,
            0,
        ),
    )
    monkeypatch.setattr(
        transcript_filter_entry,
        "redact_stream",
        lambda *_args: (_ for _ in ()).throw(OSError("worker output failed")),
    )
    monkeypatch.setattr(
        transcript_filter_entry,
        "write_capture_status",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError("sidecar write failed")
        ),
    )

    assert run_filter(RUN_ID, output, io.BytesIO(b"input")) == 8
    tmux.active = False
    observed = TmuxTranscriptAdapter(tmux).capture_status(run=active)  # type: ignore[arg-type]

    assert observed is not None
    assert observed.status is TranscriptStatus.FAILED
    assert observed.redaction_status is RedactionStatus.FAILED
    assert observed.failure_reason == "capture-process-not-running"

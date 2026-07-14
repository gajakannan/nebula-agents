from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest

from nebula_agents.presentation import session_entry, transcript_filter
from nebula_agents.presentation.session_entry import SessionEntryError, execute_descriptor, load_validated_descriptor
from nebula_agents.presentation.transcript_filter import TranscriptFilterError, filter_stream


RUN_ID = "2026-07-13-deadbeef"


def _descriptor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, dict[str, object]]:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700, parents=True)
    run_root = runtime / RUN_ID
    run_root.mkdir(mode=0o700)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    executable = tmp_path / "provider"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)
    document: dict[str, object] = {
        "schema_version": "1.0",
        "run_id": RUN_ID,
        "provider_key": "codex",
        "executable_path": str(executable.resolve()),
        "argv": [str(executable.resolve()), "safe prompt"],
        "cwd": str(workspace.resolve()),
        "inherited_env_names": ["HOME", "PATH"],
        "owner_uid": os.getuid(),
        "correlation_id": "6fddeba4-7f25-4bf1-a298-70c095235f4f",
        "created_at": "2026-07-13T18:00:00Z",
    }
    path = run_root / "launch-descriptor.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    path.chmod(0o600)
    monkeypatch.setenv("NEBULA_AGENTS_RUNTIME_DIR", str(runtime.resolve()))
    return path, document


def _rewrite(path: Path, document: dict[str, object]) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")
    path.chmod(0o600)


def _runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, nested: bool = False) -> tuple[Path, Path]:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    if nested:
        runs = runtime / "runs"
        runs.mkdir(mode=0o700)
        run_root = runs / RUN_ID
    else:
        run_root = runtime / RUN_ID
    run_root.mkdir(mode=0o700)
    monkeypatch.setenv("NEBULA_AGENTS_RUNTIME_DIR", str(runtime.resolve()))
    return runtime, run_root


def test_descriptor_rejects_relative_outside_invalid_json_and_open_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _ = _descriptor(tmp_path, monkeypatch)
    with pytest.raises(SessionEntryError, match="absolute"):
        load_validated_descriptor(Path("descriptor.json"))

    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    outside.chmod(0o600)
    with pytest.raises(SessionEntryError, match="outside"):
        load_validated_descriptor(outside.resolve())

    path.write_bytes(b"\xffnot-json")
    path.chmod(0o600)
    with pytest.raises(SessionEntryError, match="UTF-8 JSON"):
        load_validated_descriptor(path)

    path, _ = _descriptor(tmp_path / "second", monkeypatch)
    monkeypatch.setattr(os, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError()))
    with pytest.raises(SessionEntryError, match="opened safely"):
        load_validated_descriptor(path)


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"run_id": "2026-07-13-feedface"}, "run directory"),
        ({"executable_path": "provider"}, "must be absolute"),
        ({"executable_path": "/definitely/missing/provider"}, "not available"),
        ({"argv": []}, "argv"),
        ({"argv": ["/bin/sh", "bad\x00argument"]}, "argv"),
        ({"cwd": "workspace"}, "working directory must be absolute"),
        ({"cwd": "/definitely/missing/workspace"}, "working directory is not available"),
        ({"inherited_env_names": ["PATH", "PATH"]}, "environment allowlist"),
        ({"correlation_id": 7}, "metadata"),
    ],
)
def test_descriptor_rejects_remaining_structural_boundary_cases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    update: dict[str, object],
    message: str,
) -> None:
    path, document = _descriptor(tmp_path, monkeypatch)
    document.update(update)
    _rewrite(path, document)
    with pytest.raises(SessionEntryError, match=message):
        load_validated_descriptor(path)


def test_descriptor_size_owner_directory_and_retirement_failures_are_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _ = _descriptor(tmp_path, monkeypatch)
    path.write_bytes(b"")
    path.chmod(0o600)
    with pytest.raises(SessionEntryError, match="size"):
        load_validated_descriptor(path)

    path, _ = _descriptor(tmp_path / "retire", monkeypatch)
    monkeypatch.setattr(Path, "unlink", lambda _self: (_ for _ in ()).throw(PermissionError()))
    with pytest.raises(SessionEntryError, match="retired"):
        execute_descriptor(path)


def test_runtime_root_fallback_and_override_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEBULA_AGENTS_RUNTIME_DIR", raising=False)
    runtime = tmp_path / ".nebula-agents" / "runtime"
    descriptor = runtime / RUN_ID / "descriptor.json"
    assert session_entry._runtime_root_for(descriptor) == runtime
    with pytest.raises(SessionEntryError, match="not under"):
        session_entry._runtime_root_for(tmp_path / "descriptor.json")

    monkeypatch.setenv("NEBULA_AGENTS_RUNTIME_DIR", "relative")
    with pytest.raises(SessionEntryError, match="absolute"):
        session_entry._runtime_root_for(descriptor)
    monkeypatch.setenv("NEBULA_AGENTS_RUNTIME_DIR", str(tmp_path / "missing"))
    with pytest.raises(SessionEntryError, match="not available"):
        session_entry._runtime_root_for(descriptor)


def test_session_entry_main_maps_parse_execution_and_fallthrough(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert session_entry.main([]) == 2
    monkeypatch.setattr(session_entry, "execute_descriptor", lambda _path: (_ for _ in ()).throw(OSError()))
    assert session_entry.main(["--descriptor", "/safe/path"]) == 8
    assert "provider execution failed" in capsys.readouterr().err
    monkeypatch.setattr(session_entry, "execute_descriptor", lambda _path: None)
    assert session_entry.main(["--descriptor", "/safe/path"]) == 8


def test_transcript_accepts_nested_run_layout_and_main_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, run_root = _runtime(tmp_path, monkeypatch, nested=True)
    output = run_root / "logs" / "transcript.log"
    output.parent.mkdir(mode=0o700)
    filter_stream(RUN_ID, output, io.BytesIO(b"safe output"))
    assert output.read_bytes() == b"safe output"
    assert transcript_filter.main(["--run-id", RUN_ID, "--path", str(output)], source=io.BytesIO(b" more")) == 0
    assert output.read_bytes() == b"safe output more"


def test_transcript_rejects_invalid_id_relative_missing_directory_and_open_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, run_root = _runtime(tmp_path, monkeypatch)
    with pytest.raises(TranscriptFilterError, match="Run ID") as invalid:
        filter_stream("bad", run_root / "transcript.log", io.BytesIO())
    assert invalid.value.exit_code == 2
    with pytest.raises(TranscriptFilterError, match="absolute"):
        filter_stream(RUN_ID, Path("transcript.log"), io.BytesIO())
    with pytest.raises(TranscriptFilterError, match="directory"):
        filter_stream(RUN_ID, run_root / "missing" / "transcript.log", io.BytesIO())

    output = run_root / "transcript.log"
    monkeypatch.setattr(os, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError()))
    with pytest.raises(TranscriptFilterError, match="opened safely"):
        filter_stream(RUN_ID, output, io.BytesIO())


def test_transcript_wraps_source_redactor_and_write_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, run_root = _runtime(tmp_path, monkeypatch)

    class BadSource:
        def read(self, _size: int) -> bytes:
            raise RuntimeError("device failed")

    with pytest.raises(TranscriptFilterError, match="redaction failed") as source_failure:
        filter_stream(RUN_ID, run_root / "source.log", BadSource())  # type: ignore[arg-type]
    assert source_failure.value.exit_code == 8

    class BadRedactor:
        def feed(self, _chunk: bytes) -> str:
            return "not bytes"

        def finalize(self) -> bytes:
            return b""

    original_redactor = transcript_filter._streaming_redactor
    monkeypatch.setattr(transcript_filter, "_streaming_redactor", lambda: BadRedactor())
    with pytest.raises(TranscriptFilterError, match="invalid output"):
        filter_stream(RUN_ID, run_root / "redactor.log", io.BytesIO(b"input"))

    monkeypatch.setattr(transcript_filter, "_streaming_redactor", original_redactor)
    monkeypatch.setattr(os, "write", lambda _fd, _payload: 0)
    with pytest.raises(TranscriptFilterError, match="did not progress"):
        filter_stream(RUN_ID, run_root / "write.log", io.BytesIO(b"input"))


def test_transcript_main_maps_parse_and_safe_boundary_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert transcript_filter.main([], source=io.BytesIO()) == 2
    monkeypatch.setattr(
        transcript_filter,
        "filter_stream",
        lambda *_args: (_ for _ in ()).throw(TranscriptFilterError("blocked", exit_code=8)),
    )
    assert transcript_filter.main(["--run-id", RUN_ID, "--path", "/safe"], source=io.BytesIO()) == 8
    assert "capture failed safely" in capsys.readouterr().err
    monkeypatch.setattr(
        transcript_filter,
        "filter_stream",
        lambda *_args: (_ for _ in ()).throw(SessionEntryError("blocked")),
    )
    assert transcript_filter.main(["--run-id", RUN_ID, "--path", "/safe"], source=io.BytesIO()) == 9

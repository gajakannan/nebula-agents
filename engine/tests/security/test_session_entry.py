from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from nebula_agents.presentation import session_entry
from nebula_agents.presentation.session_entry import (
    SessionEntryError,
    execute_descriptor,
    load_validated_descriptor,
    main,
)


def _descriptor_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, Path, dict[str, object]]:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    run_root = runtime / "2026-07-13-deadbeef"
    run_root.mkdir(mode=0o700)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    executable = tmp_path / "fake-provider"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)
    descriptor = run_root / "launch-descriptor.json"
    document: dict[str, object] = {
        "schema_version": "1.0",
        "run_id": "2026-07-13-deadbeef",
        "provider_key": "codex",
        "executable_path": str(executable.resolve()),
        "argv": [str(executable.resolve()), "prompt $(touch /tmp/not-created); && 'quoted'"],
        "cwd": str(workspace.resolve()),
        "inherited_env_names": ["HOME", "PATH", "TERM"],
        "owner_uid": os.getuid(),
        "correlation_id": "6fddeba4-7f25-4bf1-a298-70c095235f4f",
        "created_at": "2026-07-13T18:00:00Z",
    }
    descriptor.write_text(json.dumps(document), encoding="utf-8")
    descriptor.chmod(0o600)
    monkeypatch.setenv("NEBULA_AGENTS_RUNTIME_DIR", str(runtime.resolve()))
    return runtime, descriptor, workspace, document


def _rewrite(path: Path, document: dict[str, object]) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")
    path.chmod(0o600)


def test_load_validated_descriptor_accepts_private_contained_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, descriptor, _, document = _descriptor_tree(tmp_path, monkeypatch)
    assert load_validated_descriptor(descriptor) == document


def test_execute_descriptor_passes_metacharacters_as_single_argv_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, descriptor, workspace, document = _descriptor_tree(tmp_path, monkeypatch)
    seen: dict[str, object] = {}

    def fake_chdir(path: str) -> None:
        seen["cwd"] = path

    def fake_execvpe(executable: str, argv: tuple[str, ...], environment: dict[str, str]):
        seen["executable"] = executable
        seen["argv"] = argv
        seen["environment"] = environment
        return None

    monkeypatch.setattr(os, "chdir", fake_chdir)
    monkeypatch.setattr(os, "execvpe", fake_execvpe)
    monkeypatch.setenv("UNAPPROVED_SECRET_NAME", "must-not-cross-boundary")

    with pytest.raises(AssertionError, match="returned unexpectedly"):
        execute_descriptor(descriptor)

    assert seen["cwd"] == str(workspace.resolve())
    assert seen["executable"] == document["executable_path"]
    assert seen["argv"] == tuple(document["argv"])
    assert seen["argv"][1] == "prompt $(touch /tmp/not-created); && 'quoted'"
    assert "UNAPPROVED_SECRET_NAME" not in seen["environment"]
    assert not descriptor.exists(), "validated descriptors must be retired before exec"


def test_descriptor_rejects_group_readable_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, descriptor, _, _ = _descriptor_tree(tmp_path, monkeypatch)
    descriptor.chmod(0o640)
    with pytest.raises(SessionEntryError, match="0600"):
        load_validated_descriptor(descriptor)


def test_descriptor_rejects_nonregular_leaf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, descriptor, _, _ = _descriptor_tree(tmp_path, monkeypatch)
    descriptor.unlink()
    descriptor.mkdir(mode=0o700)

    with pytest.raises(SessionEntryError, match="regular file"):
        load_validated_descriptor(descriptor)


def test_descriptor_rejects_foreign_owner_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, descriptor, _, _ = _descriptor_tree(tmp_path, monkeypatch)
    original_fstat = os.fstat

    def foreign_fstat(file_descriptor: int):
        metadata = original_fstat(file_descriptor)
        return SimpleNamespace(
            st_mode=metadata.st_mode,
            st_uid=metadata.st_uid + 1,
            st_size=metadata.st_size,
        )

    monkeypatch.setattr(session_entry.os, "fstat", foreign_fstat)

    with pytest.raises(SessionEntryError, match="owner"):
        load_validated_descriptor(descriptor)


def test_descriptor_rejects_unavailable_or_foreign_runtime_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, descriptor, _, _ = _descriptor_tree(tmp_path, monkeypatch)
    original_stat = Path.stat

    def unavailable(path: Path, *args, **kwargs):
        if path == runtime.resolve():
            raise OSError("simulated runtime loss")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", unavailable)
    with pytest.raises(SessionEntryError, match="not available"):
        load_validated_descriptor(descriptor)

    monkeypatch.setattr(Path, "stat", original_stat)
    owner_uid = os.getuid()
    monkeypatch.setattr(session_entry.os, "getuid", lambda: owner_uid + 1)
    with pytest.raises(SessionEntryError, match="ownership"):
        load_validated_descriptor(descriptor)


def test_descriptor_rejects_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, descriptor, _, _ = _descriptor_tree(tmp_path, monkeypatch)
    symlink = descriptor.with_name("descriptor-link.json")
    symlink.symlink_to(descriptor)
    with pytest.raises(SessionEntryError, match="symbolic link"):
        load_validated_descriptor(symlink)


def test_descriptor_rejects_world_accessible_runtime_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, descriptor, _, _ = _descriptor_tree(tmp_path, monkeypatch)
    runtime.chmod(0o755)
    with pytest.raises(SessionEntryError, match="another user"):
        load_validated_descriptor(descriptor)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider_key", "bash"),
        ("schema_version", "2.0"),
        ("run_id", "../../escape"),
        ("owner_uid", -1),
        ("inherited_env_names", ["PATH", "OPENAI_API_KEY"]),
        ("correlation_id", "not-a-uuid"),
        ("created_at", "not-a-time"),
        ("created_at", "2026-07-13T18:00:00"),
        ("executable_path", ""),
        ("cwd", ""),
        ("argv", []),
        ("inherited_env_names", ["PATH", "PATH"]),
    ],
)
def test_descriptor_rejects_invalid_or_unapproved_contract_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    _, descriptor, _, document = _descriptor_tree(tmp_path, monkeypatch)
    document[field] = value
    _rewrite(descriptor, document)
    with pytest.raises(SessionEntryError):
        load_validated_descriptor(descriptor)


def test_descriptor_rejects_executable_argv_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, descriptor, _, document = _descriptor_tree(tmp_path, monkeypatch)
    document["argv"] = ["/bin/echo", "unexpected"]
    _rewrite(descriptor, document)
    with pytest.raises(SessionEntryError, match="argv"):
        load_validated_descriptor(descriptor)


def test_descriptor_rejects_additive_fields_and_nonexecutable_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, descriptor, _, document = _descriptor_tree(tmp_path, monkeypatch)
    document["unexpected"] = True
    _rewrite(descriptor, document)
    with pytest.raises(SessionEntryError, match="fields"):
        load_validated_descriptor(descriptor)

    document.pop("unexpected")
    Path(str(document["executable_path"])).chmod(0o600)
    _rewrite(descriptor, document)
    with pytest.raises(SessionEntryError, match="canonical and executable"):
        load_validated_descriptor(descriptor)


def test_descriptor_rejects_noncanonical_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, descriptor, workspace, document = _descriptor_tree(tmp_path, monkeypatch)
    workspace_link = tmp_path / "workspace-link"
    workspace_link.symlink_to(workspace, target_is_directory=True)
    document["cwd"] = str(workspace_link)
    _rewrite(descriptor, document)

    with pytest.raises(SessionEntryError, match="canonical"):
        load_validated_descriptor(descriptor)


def test_runtime_override_must_be_absolute_and_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, descriptor, _, _ = _descriptor_tree(tmp_path, monkeypatch)
    monkeypatch.setenv("NEBULA_AGENTS_RUNTIME_DIR", "relative/runtime")
    with pytest.raises(SessionEntryError, match="absolute"):
        load_validated_descriptor(descriptor)

    monkeypatch.setenv(
        "NEBULA_AGENTS_RUNTIME_DIR", str(tmp_path / "missing-runtime")
    )
    with pytest.raises(SessionEntryError, match="not available"):
        load_validated_descriptor(descriptor)


def test_session_entry_redacts_validation_details_from_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    descriptor = tmp_path / "not-private-secret-bearing-name.json"
    exit_code = main(["--descriptor", str(descriptor)])
    captured = capsys.readouterr()
    assert exit_code == 9
    assert str(descriptor) not in captured.err
    assert "validation failed" in captured.err

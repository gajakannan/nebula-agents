from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from nebula_agents.domain.enums import Role, RunStatus
from nebula_agents.domain.models import Actor
from nebula_agents.presentation import cli, session_entry, transcript_filter, tui
from nebula_agents.presentation.interop import IntegrationError


RUN_ID = "2026-07-13-deadbeef"
ACTOR = Actor(1000, "operator", Role.LOCAL_OPERATOR)


def test_help_uses_nonterminating_parser_exit_contract(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--help"]) == 0
    assert "Launch and govern native provider sessions" in capsys.readouterr().out

    parser = cli.ContractParser(prog="test")
    with pytest.raises(cli.ParserExit) as raised:
        parser.exit(3, "explicit failure\n")
    assert raised.value.status == 3
    assert "explicit failure" in capsys.readouterr().err


def test_hidden_helpers_delegate_without_exposing_them_in_parser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(session_entry, "main", lambda arguments: 41 if arguments == ["--descriptor", "safe"] else 1)
    monkeypatch.setattr(transcript_filter, "main", lambda arguments: 42 if arguments == ["--run-id", RUN_ID] else 1)
    assert cli.main(["session-entry", "--descriptor", "safe"]) == 41
    assert cli.main(["transcript-filter", "--run-id", RUN_ID]) == 42


def test_interrupt_and_broken_pipe_map_to_shell_safe_exit_codes(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli,
        "_build_application",
        lambda _root: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    assert cli.main(["status", "--run-id", RUN_ID, "--format", "json"]) == 130
    assert json.loads(capfd.readouterr().err)["error"]["code"] == "INTERRUPTED"

    monkeypatch.setattr(
        cli,
        "_build_application",
        lambda _root: (_ for _ in ()).throw(BrokenPipeError()),
    )
    assert cli.main(["status", "--run-id", RUN_ID]) == 0
    assert capfd.readouterr().err == ""


def test_table_debug_mode_emits_trace_only_when_explicitly_enabled(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli,
        "_build_application",
        lambda _root: (_ for _ in ()).throw(RuntimeError("debug-only")),
    )
    monkeypatch.setenv("NEBULA_AGENTS_DEBUG_TRACEBACK", "1")
    assert cli.main(["status", "--run-id", RUN_ID]) == 8
    captured = capfd.readouterr()
    assert "[ERROR] INTERNAL_ERROR" in captured.err
    assert "Traceback" in captured.err


def test_doctor_dispatch_passes_typed_hints_runtime_override_and_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path, capfd: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, Any] = {}

    def run(**kwargs: Any) -> dict[str, str]:
        seen.update(kwargs)
        return {"overall_status": "Ready"}

    monkeypatch.setenv("NEBULA_AGENTS_RUNTIME_DIR", str(tmp_path))
    namespace = argparse.Namespace(command="doctor", provider="codex", action="feature")
    assert cli._dispatch(SimpleNamespace(preflight=SimpleNamespace(run=run)), namespace, "json") == 0
    assert seen["provider_hint"].value == "codex"
    assert seen["prompt_action"].value == "feature"
    assert seen["runtime_dir_override"] == tmp_path
    assert json.loads(capfd.readouterr().out)["data"]["overall_status"] == "Ready"

    namespace = argparse.Namespace(command="doctor", provider=None, action=None)
    application = SimpleNamespace(preflight=SimpleNamespace(run=lambda **_kwargs: "unknown"))
    assert cli._dispatch(application, namespace, "table") == 3
    assert "unknown" in capfd.readouterr().out


def test_dispatch_tui_and_invalid_story_or_unknown_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = SimpleNamespace(current_actor=lambda: ACTOR)
    monkeypatch.setattr(tui, "run_tui", lambda app, run_id: 12 if app is application and run_id == RUN_ID else 1)
    assert cli._dispatch(application, argparse.Namespace(command="tui", run_id=RUN_ID), "table") == 12

    invalid_launch = argparse.Namespace(
        command="launch",
        feature="F0001",
        story="F0002-S0001",
        provider="codex",
        action="feature",
        run_id=None,
        label=None,
        transcript=False,
    )
    with pytest.raises(cli.UsageFault, match="belong"):
        cli._dispatch(application, invalid_launch, "table")
    with pytest.raises(IntegrationError, match="No dispatcher"):
        cli._dispatch(application, argparse.Namespace(command="unknown"), "table")


@pytest.mark.parametrize(
    ("function", "value", "message"),
    [
        (cli._feature_id, "f0001", "F####"),
        (cli._story_id, "F0001-1", "F####-S####"),
        (cli._run_id, "bad", "YYYY-MM-DD"),
        (cli._run_id, "2026-02-30-deadbeef", "calendar date"),
        (cli._label, "\x00", "visible text"),
        (cli._label, "x" * 81, "80 Unicode"),
        (cli._run_status, "running", "status must be"),
    ],
)
def test_argument_value_guards(function, value: str, message: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match=message):
        function(value)


def test_cli_helpers_cover_format_command_exit_and_validator_shapes() -> None:
    assert cli._feature_id("F0001") == "F0001"
    assert cli._story_id("F0001-S0001") == "F0001-S0001"
    assert cli._run_id(RUN_ID) == RUN_ID
    assert cli._label("  useful label  ") == "useful label"
    assert cli._run_status("active") == RunStatus.ACTIVE.value
    assert cli._requested_format(["status", "--format=json"]) == "json"
    assert cli._requested_format(["status", "--format", "json"]) == "json"
    assert cli._requested_format(["status"]) == "table"
    assert cli._command_name(["--format", "status"]) == "status"
    assert cli._command_name(["--help"]) == ""

    explicit = SimpleNamespace(exit_code=17, category="conflict")
    assert cli._error_exit(explicit) == 17
    assert cli._error_exit(SimpleNamespace(category="state_io")) == 9
    assert cli._error_exit(SimpleNamespace(category="unmapped")) == 8
    assert cli._validator_exit("invalid") == 0
    assert cli._validator_exit({"latest_validator": {"exit_code": 7}}) == 7
    assert cli._validator_exit({"exit_code": 126}) == 126
    assert cli._validator_exit({"exit_code": "bad"}) == 0

    success_stream = io.StringIO()
    cli._emit_success("status", {"status": "Active"}, "table", stream=success_stream)
    assert "[OK] Active" in success_stream.getvalue()
    error_stream = io.StringIO()
    cli._emit_error({"error": {"code": "BAD", "message": "failed"}}, "table", stream=error_stream)
    assert "[ERROR] BAD" in error_stream.getvalue()


def test_product_root_precedence_is_explicit_then_environment_then_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    working = tmp_path / "working"
    configured = tmp_path / "configured"
    explicit = tmp_path / "explicit"
    for path in (working, configured, explicit):
        path.mkdir()
    monkeypatch.chdir(working)
    monkeypatch.setenv("NEBULA_AGENTS_PRODUCT_ROOT", str(configured))

    assert cli._resolve_product_root() == configured.resolve()
    assert cli._resolve_product_root(explicit) == explicit.resolve()

    monkeypatch.delenv("NEBULA_AGENTS_PRODUCT_ROOT")
    assert cli._resolve_product_root() == working.resolve()


def test_nonrepository_cwd_doctor_uses_configured_product_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    non_repository = tmp_path / "elsewhere"
    product_root = tmp_path / "product"
    non_repository.mkdir()
    product_root.mkdir()
    seen: dict[str, object] = {}

    def doctor(**kwargs: object) -> dict[str, object]:
        seen.update(kwargs)
        return {
            "overall_status": "ready",
            "workspace_root": str(product_root.resolve()),
            "providers": [],
            "checks": [],
        }

    application = SimpleNamespace(
        preflight=SimpleNamespace(run=doctor),
        current_actor=lambda: ACTOR,
    )
    monkeypatch.chdir(non_repository)
    monkeypatch.setenv("NEBULA_AGENTS_PRODUCT_ROOT", str(product_root))
    built: list[Path] = []

    def build(root: Path) -> object:
        built.append(root)
        return application

    monkeypatch.setattr(cli, "_build_application", build)

    assert cli.main(["doctor", "--format", "json"]) == 0
    document = json.loads(capfd.readouterr().out)
    assert seen["workspace_root"] == product_root.resolve()
    assert document["data"]["workspace_root"] == str(product_root.resolve())
    assert built == [product_root.resolve()]


def test_explicit_product_root_flows_into_tui_composition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    product_root = tmp_path / "explicit-product"
    product_root.mkdir()
    application = SimpleNamespace(current_actor=lambda: ACTOR)
    built: list[Path] = []

    def build(root: Path) -> object:
        built.append(root)
        return application

    monkeypatch.setattr(cli, "_build_application", build)
    monkeypatch.setattr(tui, "run_tui", lambda app, run_id: 0)

    assert cli.main(["tui"], product_root=product_root) == 0
    assert built == [product_root.resolve()]


@pytest.mark.parametrize(
    "arguments",
    [
        ["status", "--run-id", RUN_ID, "--format", "json"],
        [
            "launch",
            "--feature",
            "F0001",
            "--provider",
            "codex",
            "--action",
            "feature",
            "--run-id",
            RUN_ID,
            "--format",
            "json",
        ],
    ],
)
def test_nonrepository_cwd_status_and_launch_use_environment_product_root(
    arguments: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    product_root = tmp_path / "product"
    elsewhere = tmp_path / "installed-entrypoint-cwd"
    product_root.mkdir()
    elsewhere.mkdir()
    built: list[Path] = []
    status = {
        "run_id": RUN_ID,
        "status": "Active",
        "artifacts": [],
    }
    application = SimpleNamespace(
        current_actor=lambda: ACTOR,
        runs=SimpleNamespace(launch=lambda **_kwargs: status),
        queries=SimpleNamespace(status=lambda **_kwargs: status),
    )

    def build(root: Path) -> object:
        built.append(root)
        return application

    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv("NEBULA_AGENTS_PRODUCT_ROOT", str(product_root))
    monkeypatch.setattr(cli, "_build_application", build)

    assert cli.main(arguments) == 0
    document = json.loads(capfd.readouterr().out)
    assert document["data"]["run_id"] == RUN_ID
    assert built == [product_root.resolve()]

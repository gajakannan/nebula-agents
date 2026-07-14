from __future__ import annotations

import runpy
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from nebula_agents.application.gates import GateService
from nebula_agents.application.preflight import PreflightService
from nebula_agents.application.queries import QueryService
from nebula_agents.application.runs import RunService
from nebula_agents.application.transcripts import TranscriptService
from nebula_agents.bootstrap import Application, SystemClock, build_application
from nebula_agents.domain.enums import PromptAction, ProviderKey, Role
from nebula_agents.domain.models import LaunchRequest


def _workspace(tmp_path: Path, schema_root: Path) -> Path:
    workspace = tmp_path / "workspace"
    target = workspace / "planning-mds" / "schemas"
    target.mkdir(parents=True)
    for schema in schema_root.glob("f0001-*.json"):
        shutil.copy2(schema, target / schema.name)
    (workspace / "planning-mds" / "features").mkdir()
    (workspace / "agents" / "templates" / "prompts" / "evidence-contract").mkdir(
        parents=True
    )
    return workspace


def test_build_application_and_read_composition_do_not_create_runtime_or_policy(
    tmp_path: Path, schema_root: Path
) -> None:
    workspace = _workspace(tmp_path, schema_root)
    runtime = tmp_path / "runtime"
    application = build_application(workspace, runtime)
    assert isinstance(application, Application)
    assert isinstance(application.preflight, PreflightService)
    assert isinstance(application.runs, RunService)
    assert isinstance(application.gates, GateService)
    assert isinstance(application.transcripts, TranscriptService)
    assert isinstance(application.queries, QueryService)
    assert application.current_actor().role is Role.LOCAL_OPERATOR
    assert application.queries.sessions() == ()
    assert not runtime.exists()
    assert not (runtime / "policy.json").exists()


def test_first_authorized_launch_initializes_owner_only_runtime_state(
    tmp_path: Path, schema_root: Path
) -> None:
    workspace = _workspace(tmp_path, schema_root)
    (workspace / "planning-mds" / "features" / "F0001-test").mkdir()
    prompt = (
        workspace
        / "agents"
        / "templates"
        / "prompts"
        / "evidence-contract"
        / "feature-operator-friendly.md"
    )
    prompt.write_text("FEATURE_ID={F####}\n", encoding="utf-8")
    runtime = tmp_path / "runtime"
    application = build_application(workspace, runtime)
    actor = application.current_actor()

    class Provider:
        def build_interactive_argv(self, workspace_root, prompt_text):
            assert workspace_root == workspace.resolve()
            assert "FEATURE_ID=F0001" in prompt_text
            return (str(Path(sys.executable).resolve()), "-c", "pass")

    class Tmux:
        def __init__(self) -> None:
            self.presence = [False, True]

        def has_session(self, _name: str) -> bool:
            return self.presence.pop(0) if len(self.presence) > 1 else self.presence[0]

        def create_session(self, _name: str, descriptor: Path) -> None:
            assert descriptor.stat().st_mode & 0o777 == 0o600

    application.runs._preflight = SimpleNamespace(
        require_ready=lambda *_args: SimpleNamespace(
            prompt_contract_path=str(prompt)
        )
    )
    application.runs._providers = {ProviderKey.CODEX: Provider()}
    application.runs._tmux = Tmux()

    assert not runtime.exists()
    result = application.runs.launch(
        LaunchRequest(
            "F0001",
            None,
            ProviderKey.CODEX,
            PromptAction.FEATURE,
            "2026-07-13-deadbeef",
        ),
        actor,
    )

    assert result.run_id == "2026-07-13-deadbeef"
    assert runtime.stat().st_mode & 0o777 == 0o700
    assert (runtime / "runs").stat().st_mode & 0o777 == 0o700
    run_root = runtime / "runs" / result.run_id
    assert run_root.stat().st_mode & 0o777 == 0o700
    assert (run_root / "run.json").stat().st_mode & 0o777 == 0o600
    assert (runtime / "policy.json").stat().st_mode & 0o777 == 0o600


def test_module_entrypoint_returns_cli_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("nebula_agents.presentation.cli.main", lambda: 17)
    with pytest.raises(SystemExit) as caught:
        runpy.run_module("nebula_agents.__main__", run_name="__main__")
    assert caught.value.code == 17


def test_system_clock_returns_timezone_aware_utc() -> None:
    value = SystemClock().now()
    assert value.tzinfo is not None
    assert value.utcoffset().total_seconds() == 0

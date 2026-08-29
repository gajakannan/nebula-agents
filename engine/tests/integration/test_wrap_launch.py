"""F0003-S0001 — wrapped launch, guarded.

`wrap` supersedes nothing: F0001's `launch` is called unchanged. The property that
matters is that the guard runs BEFORE it, so a blocked launch persists no session and
creates no run.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from nebula_agents.bootstrap import build_application
from nebula_agents.domain.enums import ProviderKey, PromptAction
from nebula_agents.domain.errors import ErrorCode, NebulaError
from nebula_agents.domain.models import LaunchRequest


@pytest.fixture
def workspace(tmp_path: Path, schema_root: Path) -> Path:
    root = tmp_path / "workspace"
    target = root / "planning-mds" / "schemas"
    target.mkdir(parents=True)
    for schema in schema_root.glob("f000*-*.json"):
        shutil.copy2(schema, target / schema.name)
    (root / "planning-mds" / "features" / "F0001-test").mkdir(parents=True)
    (root / "planning-mds" / "operations" / "evidence").mkdir(parents=True)
    prompts = root / "agents" / "templates" / "prompts" / "evidence-contract"
    prompts.mkdir(parents=True)
    (prompts / "feature-operator-friendly.md").write_text("FEATURE_ID={F####}\n", encoding="utf-8")
    return root


class Tmux:
    def __init__(self) -> None:
        self.presence = [False, True]
        self.created: list[str] = []

    def probe(self):
        return SimpleNamespace(status="ready")

    def has_session(self, _name: str) -> bool:
        return self.presence.pop(0) if len(self.presence) > 1 else self.presence[0]

    def create_session(self, name: str, _descriptor: Path) -> None:
        self.created.append(name)


def application(workspace: Path, runtime: Path, *, provider_status: str = "ready"):
    app = build_application(workspace, runtime)
    tmux = Tmux()

    class Provider:
        def probe(self, _root):
            return SimpleNamespace(status=provider_status, executable_path="/usr/bin/codex", version="cli 1.0")

        def build_interactive_argv(self, _root, _prompt):
            return (str(Path(sys.executable).resolve()), "-c", "pass")

    prompt = workspace / "agents" / "templates" / "prompts" / "evidence-contract" / "feature-operator-friendly.md"
    app.runs._preflight = SimpleNamespace(
        require_ready=lambda *a: SimpleNamespace(prompt_contract_path=str(prompt))
    )
    app.runs._providers = {ProviderKey.CODEX: Provider()}
    app.runs._tmux = tmux
    app.capabilities._prober._providers = {ProviderKey.CODEX: Provider()}
    app.capabilities._prober._tmux = tmux
    return app, tmux


def request() -> LaunchRequest:
    return LaunchRequest("F0001", None, ProviderKey.CODEX, PromptAction.FEATURE, None, None, False)


def test_wrap_probes_guards_and_then_launches(workspace: Path, tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    app, tmux = application(workspace, runtime)
    actor = app.current_actor()

    record = app.commands.wrap(request(), actor)

    assert record.run_id
    assert len(tmux.created) == 1
    assert (runtime / "capabilities" / "codex.json").exists()
    assert app.queries.status(record.run_id, actor).run_id == record.run_id


def test_a_blocked_wrap_creates_no_run_and_starts_no_session(workspace: Path, tmp_path: Path) -> None:
    """The guard runs before `launch`, which is the whole reason `wrap` exists.

    If the order were reversed the run would exist, the session would be live, and the
    block would be a report about something that already happened.
    """
    runtime = tmp_path / "runtime"
    app, tmux = application(workspace, runtime, provider_status="missing")
    actor = app.current_actor()

    with pytest.raises(NebulaError) as caught:
        app.commands.wrap(request(), actor)

    assert caught.value.code is ErrorCode.CAPABILITY_BLOCKED
    assert caught.value.exit_code == 3
    assert tmux.created == []
    assert app.queries.sessions(actor=actor) == ()


def test_a_blocked_wrap_still_persists_the_capability_report(workspace: Path, tmp_path: Path) -> None:
    """The durable record of the block. See finding S4-F1 in the run's gate-decisions."""
    runtime = tmp_path / "runtime"
    app, _ = application(workspace, runtime, provider_status="missing")
    with pytest.raises(NebulaError):
        app.commands.wrap(request(), app.current_actor())

    document = json.loads((runtime / "capabilities" / "codex.json").read_text(encoding="utf-8"))
    assert document["launch_decision"] == "blocked"
    assert document["blocked_reason"]


def test_wrap_calls_f0001_launch_unchanged(workspace: Path, tmp_path: Path) -> None:
    """`wrap` adds a guard ahead of `launch`; it does not reimplement it."""
    app, _ = application(workspace, tmp_path / "runtime")
    actor = app.current_actor()
    seen = []
    original = app.runs.launch
    app.commands.runs.launch = lambda req, act: (seen.append((req, act)), original(req, act))[1]

    app.commands.wrap(request(), actor)

    assert len(seen) == 1
    assert seen[0][0] == request()

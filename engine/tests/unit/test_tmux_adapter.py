from __future__ import annotations

from pathlib import Path

import pytest

from nebula_agents.domain.errors import ErrorCode, NebulaError
from nebula_agents.domain.models import ProcessResult
from nebula_agents.infrastructure.tmux import TmuxAdapter


SESSION = "nebula-F0001-deadbeef"


class Runner:
    def __init__(self, *results: ProcessResult) -> None:
        self.results = list(results)
        self.calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

    def run(self, argv, **kwargs):
        self.calls.append((tuple(argv), kwargs))
        return self.results.pop(0)


def _result(exit_code=0, stdout="", *, timed_out=False):
    return ProcessResult("tmux", exit_code, stdout, "", 1, timed_out=timed_out)


@pytest.mark.parametrize(
    ("result", "status"),
    [
        (_result(stdout="tmux 3.6\n"), "ready"),
        (_result(124, timed_out=True), "timeout"),
        (_result(1), "error"),
    ],
)
def test_tmux_probe_classifies_bounded_command_result(
    monkeypatch: pytest.MonkeyPatch, result: ProcessResult, status: str
) -> None:
    monkeypatch.setattr("nebula_agents.infrastructure.tmux.shutil.which", lambda _name: "/usr/bin/tmux")
    runner = Runner(result)
    probe = TmuxAdapter(runner).probe()
    assert probe.status == status
    assert runner.calls[0][0] == ("/usr/bin/tmux", "-V")
    if status == "ready":
        assert probe.version == "tmux 3.6"


def test_tmux_probe_and_required_commands_report_missing_binary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("nebula_agents.infrastructure.tmux.shutil.which", lambda _name: None)
    adapter = TmuxAdapter(Runner())
    assert adapter.probe().status == "missing"
    with pytest.raises(NebulaError) as caught:
        adapter.has_session(SESSION)
    assert caught.value.code is ErrorCode.PREFLIGHT_BLOCKED


def test_has_session_uses_exact_validated_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("nebula_agents.infrastructure.tmux.shutil.which", lambda _name: "/usr/bin/tmux")
    runner = Runner(_result(0), _result(1))
    adapter = TmuxAdapter(runner)
    assert adapter.has_session(SESSION) is True
    assert adapter.has_session(SESSION) is False
    assert runner.calls[0][0] == ("/usr/bin/tmux", "has-session", "-t", SESSION)
    with pytest.raises(ValueError, match="session"):
        adapter.has_session("bad; tmux kill-server")


@pytest.mark.parametrize("result", [_result(124, timed_out=True), _result(2)])
def test_has_session_rejects_unavailable_probe(
    monkeypatch: pytest.MonkeyPatch,
    result: ProcessResult,
) -> None:
    monkeypatch.setattr(
        "nebula_agents.infrastructure.tmux.shutil.which",
        lambda _name: "/usr/bin/tmux",
    )

    with pytest.raises(NebulaError) as caught:
        TmuxAdapter(Runner(result)).has_session(SESSION)

    assert caught.value.code is ErrorCode.COMMAND_FAILED


def test_create_session_quotes_descriptor_as_one_shell_command_value(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("nebula_agents.infrastructure.tmux.shutil.which", lambda _name: "/usr/bin/tmux")
    runner = Runner(_result())
    descriptor = tmp_path / "run with spaces" / "launch;descriptor.json"
    descriptor.parent.mkdir()
    adapter = TmuxAdapter(runner)
    adapter.create_session(SESSION, descriptor)
    argv, kwargs = runner.calls[0]
    assert argv[:6] == ("/usr/bin/tmux", "new-session", "-d", "-s", SESSION, argv[5])
    assert argv[5].startswith("nebula-agents session-entry --descriptor ")
    assert "'" in argv[5]
    assert kwargs["cwd"] == descriptor.parent.resolve()


def test_create_and_pipe_failures_map_to_stable_command_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("nebula_agents.infrastructure.tmux.shutil.which", lambda _name: "/usr/bin/tmux")
    adapter = TmuxAdapter(Runner(_result(1)))
    with pytest.raises(NebulaError) as created:
        adapter.create_session(SESSION, tmp_path / "descriptor.json")
    assert created.value.code is ErrorCode.COMMAND_FAILED
    adapter = TmuxAdapter(Runner(_result(1)))
    with pytest.raises(NebulaError) as piped:
        adapter.configure_pipe(SESSION, ("nebula-agents", "transcript-filter"))
    assert piped.value.code is ErrorCode.COMMAND_FAILED


def test_configure_pipe_enables_and_disables_exact_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("nebula_agents.infrastructure.tmux.shutil.which", lambda _name: "/usr/bin/tmux")
    runner = Runner(_result(), _result())
    adapter = TmuxAdapter(runner)
    adapter.configure_pipe(SESSION, ("nebula-agents", "transcript-filter", "--path", "/tmp/a b"))
    adapter.configure_pipe(SESSION, None)
    enabled = runner.calls[0][0]
    disabled = runner.calls[1][0]
    assert enabled[:5] == ("/usr/bin/tmux", "pipe-pane", "-o", "-t", SESSION)
    assert "'/tmp/a b'" in enabled[5]
    assert disabled == ("/usr/bin/tmux", "pipe-pane", "-t", SESSION)


@pytest.mark.parametrize(("stdout", "expected"), [("1\n", True), ("0\n", False)])
def test_pipe_active_accepts_only_exact_tmux_boolean_output(
    monkeypatch: pytest.MonkeyPatch,
    stdout: str,
    expected: bool,
) -> None:
    monkeypatch.setattr(
        "nebula_agents.infrastructure.tmux.shutil.which",
        lambda _name: "/usr/bin/tmux",
    )
    assert TmuxAdapter(Runner(_result(stdout=stdout))).pipe_active(SESSION) is expected


@pytest.mark.parametrize(
    "result",
    [
        _result(124, timed_out=True),
        _result(1),
        _result(0, stdout="unknown\n"),
    ],
    ids=("timeout", "nonzero", "malformed"),
)
def test_pipe_active_rejects_unavailable_or_malformed_probe(
    monkeypatch: pytest.MonkeyPatch,
    result: ProcessResult,
) -> None:
    monkeypatch.setattr(
        "nebula_agents.infrastructure.tmux.shutil.which",
        lambda _name: "/usr/bin/tmux",
    )

    with pytest.raises(NebulaError) as caught:
        TmuxAdapter(Runner(result)).pipe_active(SESSION)

    assert caught.value.code is ErrorCode.COMMAND_FAILED
    assert caught.value.message == (
        "tmux transcript pipe liveness could not be established"
    )


def test_attach_delegates_terminal_with_filtered_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("nebula_agents.infrastructure.tmux.shutil.which", lambda _name: "/usr/bin/tmux")
    monkeypatch.setenv("PATH", "/safe/bin")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-cross")
    seen: dict[str, object] = {}

    def fake_call(argv, **kwargs):
        seen["argv"] = tuple(argv)
        seen["kwargs"] = kwargs
        return 17

    monkeypatch.setattr("nebula_agents.infrastructure.tmux.subprocess.call", fake_call)
    assert TmuxAdapter(Runner()).attach(SESSION) == 17
    assert seen["argv"] == ("/usr/bin/tmux", "attach-session", "-t", SESSION)
    environment = seen["kwargs"]["env"]
    assert environment["PATH"] == "/safe/bin"
    assert "OPENAI_API_KEY" not in environment
    assert seen["kwargs"]["shell"] is False

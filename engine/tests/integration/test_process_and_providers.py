from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from nebula_agents.domain.enums import ProviderKey
from nebula_agents.domain.models import ProcessResult
from nebula_agents.infrastructure.process import SubprocessRunner
from nebula_agents.infrastructure.providers import ClaudeAdapter, CodexAdapter


FAKE_PROVIDER = Path(__file__).resolve().parents[1] / "fixtures" / "fake_provider.py"


def test_subprocess_runner_preserves_metacharacters_as_one_argument(tmp_path: Path) -> None:
    argv_log = tmp_path / "argv.json"
    prompt = "$(touch /tmp/not-created); && 'quoted' | cat"
    result = SubprocessRunner().run(
        (
            sys.executable,
            str(FAKE_PROVIDER),
            "--mode",
            "exit",
            "--argv-log",
            str(argv_log),
            prompt,
        ),
        cwd=tmp_path,
        timeout_seconds=2,
        capture_limit=4096,
    )
    assert result.exit_code == 0
    recorded = json.loads(argv_log.read_text(encoding="utf-8"))
    assert recorded[-1] == prompt
    assert not Path("/tmp/not-created").exists()


def test_subprocess_runner_passes_only_allowlisted_environment_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEBULA_TEST_ALLOWED", "allowed-value")
    monkeypatch.setenv("NEBULA_TEST_DENIED", "denied-value")
    code = "import json,os; print(json.dumps(dict(os.environ),sort_keys=True))"
    result = SubprocessRunner().run(
        (sys.executable, "-c", code),
        cwd=tmp_path,
        timeout_seconds=2,
        capture_limit=4096,
        env_names=("NEBULA_TEST_ALLOWED",),
    )
    environment = json.loads(result.stdout)
    assert environment == {"NEBULA_TEST_ALLOWED": "allowed-value", "LC_CTYPE": "C.UTF-8"} or environment == {"NEBULA_TEST_ALLOWED": "allowed-value"}
    assert "denied-value" not in result.stdout


def test_subprocess_runner_redacts_output_and_strips_terminal_controls(tmp_path: Path) -> None:
    sentinel = "Bearer " + "test-only-token-0123456789abcdef"
    payload = ("\x1b[31m" + sentinel + "\x1b[0m\x00").encode()
    emitter = f"import sys; sys.stdout.buffer.write({payload!r})"
    result = SubprocessRunner().run(
        (sys.executable, "-c", emitter),
        cwd=tmp_path,
        timeout_seconds=2,
        capture_limit=4096,
    )
    assert result.exit_code == 0
    assert sentinel not in result.stdout
    assert "[REDACTED]" in result.stdout
    assert "\x1b" not in result.stdout
    assert "\x00" not in result.stdout


def test_oversized_private_material_is_replaced_before_bounding(tmp_path: Path) -> None:
    header = "-----BEGIN TEST " + "PRIVATE KEY-----\n"
    output = header + "test-only-private-material" * 100 + "\n-----END TEST " + "PRIVATE KEY-----"
    result = SubprocessRunner().run(
        (sys.executable, str(FAKE_PROVIDER), "--mode", "emit", "--output", output),
        cwd=tmp_path,
        timeout_seconds=2,
        capture_limit=128,
    )
    # The complete sensitive block is represented by one marker, so the safe
    # output itself fits the bound and is not semantically truncated.
    assert result.truncated is False
    assert "PRIVATE KEY" not in result.stdout
    assert "test-only-private-material" not in result.stdout


def test_subprocess_runner_returns_bounded_timeout_result(tmp_path: Path) -> None:
    result = SubprocessRunner().run(
        (sys.executable, str(FAKE_PROVIDER), "--mode", "wait"),
        cwd=tmp_path,
        timeout_seconds=0.05,
        capture_limit=4096,
    )
    assert result.timed_out is True
    assert result.exit_code == 124
    assert result.duration_ms < 2000


@pytest.mark.parametrize("argv", [(), ("",), (sys.executable, "bad\x00value")])
def test_subprocess_runner_rejects_empty_or_nul_argv(argv: tuple[str, ...], tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="argv"):
        SubprocessRunner().run(
            argv, cwd=tmp_path, timeout_seconds=1, capture_limit=100
        )


class RecordingRunner:
    def __init__(self, results: list[ProcessResult]) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv, **_kwargs):
        self.calls.append(tuple(argv))
        return self.results.pop(0)


def _result(exit_code=0, stdout="ok", *, timed_out=False):
    return ProcessResult("provider", exit_code, stdout, "", 1, timed_out=timed_out)


@pytest.mark.parametrize(
    ("adapter_type", "key", "auth_tail"),
    [
        (CodexAdapter, ProviderKey.CODEX, ("login", "status")),
        (ClaudeAdapter, ProviderKey.CLAUDE, ("auth", "status")),
    ],
)
def test_provider_probe_keeps_version_and_auth_flags_inside_adapter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    adapter_type,
    key: ProviderKey,
    auth_tail: tuple[str, ...],
) -> None:
    runner = RecordingRunner([_result(stdout="provider 1.0"), _result()])
    monkeypatch.setattr("nebula_agents.infrastructure.providers.shutil.which", lambda _name: "/usr/bin/provider")
    adapter = adapter_type(runner)
    probe = adapter.probe(tmp_path)
    assert probe.key == key.value
    assert probe.status == "ready"
    assert runner.calls == [
        ("/usr/bin/provider", "--version"),
        ("/usr/bin/provider", *auth_tail),
    ]


def test_provider_probe_reports_auth_attention_without_login_attempt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = RecordingRunner([_result(stdout="codex 1.0"), _result(exit_code=1, stdout="login required")])
    monkeypatch.setattr("nebula_agents.infrastructure.providers.shutil.which", lambda _name: "/usr/bin/codex")
    probe = CodexAdapter(runner).probe(tmp_path)
    assert probe.status == "authentication_attention_needed"
    assert runner.calls[-1] == ("/usr/bin/codex", "login", "status")


def test_provider_probe_classifies_missing_timeout_and_unsupported_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("nebula_agents.infrastructure.providers.shutil.which", lambda _name: None)
    missing = CodexAdapter(RecordingRunner([])).probe(tmp_path)
    assert missing.status == "missing"
    assert missing.remediation_category == "install_provider"

    monkeypatch.setattr("nebula_agents.infrastructure.providers.shutil.which", lambda _name: "/usr/bin/codex")
    timeout = CodexAdapter(
        RecordingRunner([_result(exit_code=124, timed_out=True)])
    ).probe(tmp_path)
    assert timeout.status == "timeout"
    unsupported = CodexAdapter(RecordingRunner([_result(exit_code=2)])).probe(tmp_path)
    assert unsupported.status == "unsupported"


def test_provider_argv_preserves_prompt_as_one_value(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("nebula_agents.infrastructure.providers.shutil.which", lambda _name: "/usr/bin/codex")
    prompt = "feature $(touch /tmp/not-created); && echo no"
    argv = CodexAdapter(RecordingRunner([])).build_interactive_argv(tmp_path, prompt)
    assert argv == ("/usr/bin/codex", prompt)


def test_provider_argv_rejects_missing_executable_nul_and_oversized_prompt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("nebula_agents.infrastructure.providers.shutil.which", lambda _name: None)
    with pytest.raises(FileNotFoundError):
        CodexAdapter(RecordingRunner([])).build_interactive_argv(tmp_path, "prompt")
    monkeypatch.setattr("nebula_agents.infrastructure.providers.shutil.which", lambda _name: "/usr/bin/codex")
    adapter = CodexAdapter(RecordingRunner([]))
    with pytest.raises(ValueError, match="prompt"):
        adapter.build_interactive_argv(tmp_path, "bad\x00prompt")
    with pytest.raises(ValueError, match="prompt"):
        adapter.build_interactive_argv(tmp_path, "x" * 65_537)


@pytest.mark.parametrize(
    ("exit_code", "output", "classification"),
    [
        (0, "", "exited"),
        (1, "Login required", "authentication_attention_needed"),
        (1, "auth expired", "authentication_attention_needed"),
        (2, "provider crashed", "provider_failed"),
    ],
)
def test_provider_early_exit_classification(exit_code, output, classification) -> None:
    assert CodexAdapter(RecordingRunner([])).classify_early_exit(exit_code, output) == classification

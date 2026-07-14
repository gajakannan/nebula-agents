from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from nebula_agents.domain.enums import Role
from nebula_agents.domain.errors import ErrorCode, NebulaError
from nebula_agents.domain.models import Actor
from nebula_agents.presentation import cli


ACTOR = Actor(1000, "operator", Role.LOCAL_OPERATOR)


class Calls:
    def __init__(self) -> None:
        self.values: list[tuple[str, dict[str, object]]] = []

    def record(self, name: str, result: object):
        def method(**kwargs):
            self.values.append((name, kwargs))
            if isinstance(result, Exception):
                raise result
            return result

        return method


def _application(calls: Calls, *, result: object = None):
    run = result or {
        "run_id": "2026-07-13-deadbeef",
        "status": "Active",
        "latest_validator": None,
        "artifacts": [],
    }
    return SimpleNamespace(
        preflight=SimpleNamespace(
            run=calls.record(
                "doctor",
                {
                    "overall_status": "ready",
                    "tmux": {"key": "tmux", "status": "ready"},
                    "providers": [{"key": "codex", "status": "ready"}],
                    "checks": [],
                },
            )
        ),
        runs=SimpleNamespace(
            launch=calls.record("launch", run),
            attach=calls.record("attach", 0),
            recover=calls.record("recover", run),
        ),
        queries=SimpleNamespace(
            sessions=calls.record("sessions", (run,)),
            status=calls.record("status", run),
            evidence=calls.record("evidence", tuple(run.get("artifacts", []))),
        ),
        gates=SimpleNamespace(
            run_validator=calls.record(
                "validate",
                {**run, "latest_validator": {"exit_code": 0, "validator_key": "stories"}},
            )
        ),
        current_actor=lambda: ACTOR,
    )


def test_status_json_uses_success_envelope_and_stdout_only(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    calls = Calls()
    monkeypatch.setattr(cli, "_build_application", lambda _root: _application(calls))
    exit_code = cli.main(["status", "--run-id", "2026-07-13-deadbeef", "--format", "json"])
    captured = capfd.readouterr()
    document = json.loads(captured.out)
    assert exit_code == 0
    assert captured.err == ""
    assert document["contract_version"] == "1.0"
    assert document["command"] == "status"
    assert document["data"]["run_id"] == "2026-07-13-deadbeef"
    assert [name for name, _ in calls.values] == ["status"]


@pytest.mark.parametrize("command", ["sessions", "status", "evidence"])
def test_read_only_commands_never_call_launch_attach_or_gate_mutations(
    command: str,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    calls = Calls()
    monkeypatch.setattr(cli, "_build_application", lambda _root: _application(calls))
    argv = [command, "--format", "json"]
    if command != "sessions":
        argv[1:1] = ["--run-id", "2026-07-13-deadbeef"]
    assert cli.main(argv) == 0
    capfd.readouterr()
    assert [name for name, _ in calls.values] == [command]


def test_sessions_forces_one_hundred_record_service_bound(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    calls = Calls()
    monkeypatch.setattr(cli, "_build_application", lambda _root: _application(calls))
    assert cli.main(["sessions", "--format", "json"]) == 0
    capfd.readouterr()
    assert calls.values[0][1]["limit"] == 100


def test_sessions_surfaces_safe_corrupt_snapshot_recovery_projection(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    calls = Calls()
    application = _application(calls)
    application.queries.recovery_candidates = calls.record(
        "recovery_candidates",
        (
            {
                "run_id": "2026-07-13-feedface",
                "recoverable_revision": 9,
                "recovery_available": True,
                "can_recover": True,
                "last_gate": {"gate_id": "G3", "status": "Held"},
                "last_audit_event": {
                    "sequence": 12,
                    "event_type": "TranscriptCompleted",
                },
                "transcript_path": None,
                "recovery_command": (
                    "nebula-agents recover --run-id 2026-07-13-feedface "
                    "--expected-revision 9"
                ),
            },
        ),
    )
    monkeypatch.setattr(cli, "_build_application", lambda _root: application)

    assert cli.main(["sessions", "--format", "json"]) == 0
    document = json.loads(capfd.readouterr().out)

    recovery = document["data"][0]
    assert recovery["run_id"] == "2026-07-13-feedface"
    assert recovery["status"] == "Corrupt"
    assert recovery["revision"] == 9
    assert recovery["recovery_command"].endswith("--expected-revision 9")
    assert [name for name, _ in calls.values] == [
        "sessions",
        "recovery_candidates",
    ]


def test_validate_preserves_nonzero_validator_exit_and_never_decides_gate(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    calls = Calls()
    application = _application(calls)
    application.gates.run_validator = calls.record(
        "validate",
        {"run_id": "2026-07-13-deadbeef", "latest_validator": {"exit_code": 17}},
    )
    application.queries.status = calls.record(
        "status",
        {
            "run_id": "2026-07-13-deadbeef",
            "status": "Active",
            "latest_validator": {"exit_code": 17, "validator_key": "stories"},
            "artifacts": [],
            "can_attach": False,
            "can_recover": False,
            "recovery_available": False,
            "can_decide_gate": False,
            "can_configure_transcript": False,
        },
    )
    monkeypatch.setattr(cli, "_build_application", lambda _root: application)
    exit_code = cli.main(
        [
            "validate",
            "--run-id",
            "2026-07-13-deadbeef",
            "--validator",
            "stories",
            "--format",
            "json",
        ]
    )
    document = json.loads(capfd.readouterr().out)
    assert exit_code == 17
    assert document["data"]["latest_validator"]["exit_code"] == 17
    assert [name for name, _ in calls.values] == ["validate", "status"]


def test_doctor_blocked_returns_three_with_valid_json(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    calls = Calls()
    application = _application(calls)
    application.preflight.run = calls.record(
        "doctor", {"overall_status": "authentication_attention_needed", "providers": []}
    )
    monkeypatch.setattr(cli, "_build_application", lambda _root: application)
    assert cli.main(["doctor", "--provider", "codex", "--format", "json"]) == 3
    document = json.loads(capfd.readouterr().out)
    assert document["data"]["overall_status"] == "authentication_attention_needed"


def test_usage_error_is_stable_json_and_does_not_build_application(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli, "_build_application", lambda _root: pytest.fail("must not compose")
    )
    exit_code = cli.main(["status", "--run-id", "not-a-run", "--format", "json"])
    captured = capfd.readouterr()
    document = json.loads(captured.err)
    assert exit_code == 2
    assert captured.out == ""
    assert document["error"]["code"] == "USAGE_ERROR"
    assert document["error"]["category"] == "usage"


def test_nebula_error_maps_to_documented_exit_without_secret_details(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    calls = Calls()
    failure = NebulaError(
        ErrorCode.FORBIDDEN,
        "Operation denied",
        "forbidden",
        "Use the owning OS account.",
    )
    application = _application(calls)
    application.queries.status = calls.record("status", failure)
    monkeypatch.setattr(cli, "_build_application", lambda _root: application)
    assert cli.main(["status", "--run-id", "2026-07-13-deadbeef", "--format", "json"]) == 5
    document = json.loads(capfd.readouterr().err)
    assert document["error"]["code"] == "FORBIDDEN"


def test_unexpected_error_never_exposes_message_or_traceback_in_json(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    calls = Calls()
    application = _application(calls)
    sensitive = "internal test-only credential material"
    application.queries.status = calls.record("status", RuntimeError(sensitive))
    monkeypatch.setattr(cli, "_build_application", lambda _root: application)
    monkeypatch.setenv("NEBULA_AGENTS_DEBUG_TRACEBACK", "1")
    assert cli.main(["status", "--run-id", "2026-07-13-deadbeef", "--format", "json"]) == 8
    captured = capfd.readouterr()
    document = json.loads(captured.err)
    assert document["error"]["code"] == "INTERNAL_ERROR"
    assert sensitive not in captured.err
    assert "Traceback" not in captured.err


def test_attach_reuses_existing_service_and_never_calls_launch(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    calls = Calls()
    monkeypatch.setattr(cli, "_build_application", lambda _root: _application(calls))
    assert cli.main(["attach", "--run-id", "2026-07-13-deadbeef"]) == 0
    capfd.readouterr()
    assert [name for name, _ in calls.values] == ["attach"]


def test_recover_passes_explicit_revision_and_never_launches_or_attaches(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    calls = Calls()
    monkeypatch.setattr(cli, "_build_application", lambda _root: _application(calls))

    assert (
        cli.main(
            [
                "recover",
                "--run-id",
                "2026-07-13-deadbeef",
                "--expected-revision",
                "4",
                "--format",
                "json",
            ]
        )
        == 0
    )
    document = json.loads(capfd.readouterr().out)

    assert document["command"] == "recover"
    assert [name for name, _ in calls.values] == ["recover"]
    assert calls.values[0][1]["expected_revision"] == 4


def test_launch_human_guidance_and_json_non_regression_do_not_start_twice(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    run_id = "2026-07-13-deadbeef"
    calls = Calls()
    monkeypatch.setattr(cli, "_build_application", lambda _root: _application(calls))
    arguments = [
        "launch",
        "--feature",
        "F0001",
        "--provider",
        "codex",
        "--action",
        "feature",
        "--run-id",
        run_id,
    ]

    assert cli.main(arguments) == 0
    human = capfd.readouterr()
    assert f"nebula-agents tui --run-id {run_id}" in human.out
    assert f"nebula-agents attach --run-id {run_id}" in human.out
    assert [name for name, _ in calls.values] == ["launch", "status"]

    calls.values.clear()
    assert cli.main([*arguments, "--format", "json"]) == 0
    machine = capfd.readouterr()
    document = json.loads(machine.out)
    assert document["data"]["run_id"] == run_id
    assert "Next steps" not in machine.out
    assert "nebula-agents attach" not in machine.out
    assert [name for name, _ in calls.values] == ["launch", "status"]


def test_internal_subcommands_are_hidden_from_public_help() -> None:
    help_text = cli.build_parser().format_help()
    assert "session-entry" not in help_text
    assert "transcript-filter" not in help_text

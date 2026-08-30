"""The full F0003 operator lifecycle, through the CLI (Step 8).

Every layer of this chain has its own tests and they all pass. Twice now, a defect has
lived in the *seam* between two correct layers and only surfaced when the whole chain ran:
`infer_kind` classifying `validator.txt` as `status`, so a real validator failure could
never reach a learning proposal.

That is what this file is for. It exercises the operator's actual path — the CLI, not the
services — because that is the only place the seams are all present at once.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from nebula_agents.presentation import cli

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "summaries"


@pytest.fixture
def workspace(tmp_path: Path, schema_root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ws = tmp_path / "workspace"
    (ws / "planning-mds" / "schemas").mkdir(parents=True)
    for schema in schema_root.glob("f000*-*.json"):
        shutil.copy2(schema, ws / "planning-mds" / "schemas" / schema.name)
    (ws / "planning-mds" / "features" / "F0001-test").mkdir(parents=True)
    evidence = ws / "planning-mds" / "operations" / "evidence"
    evidence.mkdir(parents=True)
    prompts = ws / "agents" / "templates" / "prompts" / "evidence-contract"
    prompts.mkdir(parents=True)
    (prompts / "feature-operator-friendly.md").write_text("FEATURE_ID={F####}\n", encoding="utf-8")
    monkeypatch.setenv("NEBULA_AGENTS_RUNTIME_DIR", str(tmp_path / "runtime"))
    return ws


def run_cli(argv: list[str], workspace: Path, capfd) -> tuple[int, dict]:
    code = cli.main(argv + ["--format", "json"], product_root=workspace)
    captured = capfd.readouterr()
    payload = captured.out or captured.err
    return code, json.loads(payload) if payload.strip() else {}


@pytest.fixture
def launched(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    """Patch the provider and tmux seams once, at the composition root."""
    original = cli._build_application

    def build(root):
        app = original(root)

        class Provider:
            def probe(self, _r):
                return SimpleNamespace(status="ready", executable_path="/usr/bin/codex",
                                       version="codex-cli 1.0")
            def build_interactive_argv(self, _r, _p):
                return (str(Path(sys.executable).resolve()), "-c", "pass")

        class Tmux:
            def __init__(self): self.presence = [False, True]
            def probe(self): return SimpleNamespace(status="ready")
            def has_session(self, _n):
                return self.presence.pop(0) if len(self.presence) > 1 else self.presence[0]
            def create_session(self, _n, _d): return None

        prompts = workspace / "agents" / "templates" / "prompts" / "evidence-contract"
        app.runs._preflight = SimpleNamespace(
            require_ready=lambda *a: SimpleNamespace(
                prompt_contract_path=str(prompts / "feature-operator-friendly.md"))
        )
        from nebula_agents.domain.enums import ProviderKey
        app.runs._providers = {ProviderKey.CODEX: Provider()}
        app.runs._tmux = Tmux()
        app.capabilities._prober._providers = {ProviderKey.CODEX: Provider()}
        app.capabilities._prober._tmux = Tmux()
        return app

    monkeypatch.setattr(cli, "_build_application", build)
    return workspace


def test_the_whole_operator_lifecycle_runs_through_the_cli(launched, capfd, tmp_path: Path) -> None:
    """providers doctor -> wrap -> index -> summarize -> metrics -> learn review -> decide."""
    workspace = launched

    code, doctor = run_cli(["providers", "doctor", "--provider", "codex"], workspace, capfd)
    assert code == 0
    assert doctor["data"][0]["launch_decision"] == "allowed"

    code, wrapped = run_cli(
        ["wrap", "codex", "--feature", "F0001", "--action", "feature"], workspace, capfd
    )
    assert code == 0
    run_id = wrapped["data"]["run_id"]

    evidence = workspace / "planning-mds" / "operations" / "evidence"
    shutil.copy2(FIXTURES / "validator-output.txt", evidence / "validator.txt")
    shutil.copy2(FIXTURES / "command-log.jsonl", evidence / "commands.log")

    code, indexed = run_cli(
        ["evidence", "index", "--run-id", run_id,
         "--path", str(evidence / "validator.txt"),
         "--path", str(evidence / "commands.log")],
        workspace, capfd,
    )
    assert code == 0 and len(indexed["data"]) == 2
    # The seam that bit before: a file named `validator.txt` must be validator output,
    # not `status`, or its failures never reach a proposal.
    kinds = {item["artifact_kind"] for item in indexed["data"]}
    assert kinds == {"validator-output", "command-log"}

    code, listed = run_cli(["evidence", "list", "--run-id", run_id], workspace, capfd)
    assert code == 0 and len(listed["data"]) == 2

    code, summarized = run_cli(["evidence", "summarize", "--run-id", run_id], workspace, capfd)
    assert code == 0
    assert all(item["summary_status"] in {"Pass", "Partial"} for item in summarized["data"])
    assert all(item["failure_markers"] for item in summarized["data"])

    artifact_id = listed["data"][0]["artifact_id"]
    code, shown = run_cli(["evidence", "show", artifact_id], workspace, capfd)
    assert code == 0 and shown["data"]["artifact_id"] == artifact_id
    assert shown["data"]["summary_path"]

    code, metrics = run_cli(["metrics", "--run-id", run_id], workspace, capfd)
    assert code == 0
    names = {m["metric_name"] for m in metrics["data"]["metrics"]}
    assert len(names) == 9
    counted = next(m for m in metrics["data"]["metrics"] if m["metric_name"] == "artifact_count")
    assert counted["metric_value"] == 2

    code, drafted = run_cli(["learn", "review", "--run-id", run_id], workspace, capfd)
    assert code == 0
    assert len(drafted["data"]) == 2, "both failing kinds should produce a proposal"
    proposal = drafted["data"][0]

    code, proposals = run_cli(
        ["learn", "list", "--run-id", run_id, "--status", "Draft"], workspace, capfd
    )
    assert code == 0 and len(proposals["data"]) == 2

    code, detail = run_cli(
        ["learn", "show", proposal["proposal_id"], "--run-id", run_id], workspace, capfd
    )
    assert code == 0 and detail["data"]["source_artifact_ids"]

    # Deciding requires a per-target-class grant in the committed policy. Without it the
    # operator who owns the run is denied -- which is the point.
    code, denied = run_cli(
        ["learn", "decide", proposal["proposal_id"], "--run-id", run_id,
         "--decision", "reject", "--reason", "documented behaviour is correct"],
        workspace, capfd,
    )
    assert code == 5 and denied["error"]["code"] == "FORBIDDEN"

    key = {"planning-mds/architecture/SOLUTION-PATTERNS.md": "can_decide_architecture",
           "planning-mds/features/REGISTRY.md": "can_decide_planning"}[proposal["target_document"]]
    policy = tmp_path / "runtime" / "policy.json"
    document = json.loads(policy.read_text(encoding="utf-8"))
    document["proposal_grants"] = {key: True}
    policy.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    os.chmod(policy, 0o600)

    code, decided = run_cli(
        ["learn", "decide", proposal["proposal_id"], "--run-id", run_id,
         "--decision", "reject", "--reason", "documented behaviour is correct"],
        workspace, capfd,
    )
    assert code == 0 and decided["data"]["proposal_status"] == "Rejected"

    # Sticky rejection closes the loop: the same evidence is not re-raised.
    code, again = run_cli(["learn", "review", "--run-id", run_id], workspace, capfd)
    assert code == 0
    assert proposal["proposal_id"] not in {p["proposal_id"] for p in again["data"]}


def test_a_blocked_provider_stops_the_lifecycle_at_wrap(workspace: Path, capfd,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    """Exit 3, no run, no session — the guard's whole purpose, through the CLI."""
    original = cli._build_application

    def build(root):
        app = original(root)

        class Missing:
            def probe(self, _r):
                return SimpleNamespace(status="missing", executable_path=None, version=None)

        class Tmux:
            def probe(self): return SimpleNamespace(status="ready")
            def has_session(self, _n): return False

        from nebula_agents.domain.enums import ProviderKey
        app.capabilities._prober._providers = {ProviderKey.CODEX: Missing()}
        app.capabilities._prober._tmux = Tmux()
        return app

    monkeypatch.setattr(cli, "_build_application", build)
    code, document = run_cli(
        ["wrap", "codex", "--feature", "F0001", "--action", "feature"], workspace, capfd
    )
    assert code == 3
    assert document["error"]["code"] == "CAPABILITY_BLOCKED"

    code, sessions = run_cli(["sessions"], workspace, capfd)
    assert code == 0 and sessions["data"] == []


def test_every_f0003_command_appears_in_help() -> None:
    """The added commands are a contract; `--help` is where an operator finds them.

    Rendered directly rather than through `parse_args(["--help"])`, because
    `ContractParser.exit` raises `ParserExit` rather than `SystemExit` -- catching the
    wrong one would make this pass for the wrong reason.
    """
    rendered = cli.build_parser().format_help()
    for command in ("wrap", "providers", "evidence", "metrics", "learn"):
        assert command in rendered, f"{command} missing from --help"

    # F0001's commands must still be listed: contract 1.1 removes nothing.
    for command in ("doctor", "launch", "attach", "recover", "sessions", "status",
                    "evidence", "validate", "tui"):
        assert command in rendered

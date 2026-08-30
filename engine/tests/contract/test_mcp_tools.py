"""F0003-S0003 — the read-only MCP surface (ADR-007).

Checkpoint E. The guarantee under test is *structural*: the adapter is constructed with a
query-only facade, so no mutating service is reachable from it. That is asserted by
inspecting what the server actually holds, not by trusting the constructor signature.
"""

from __future__ import annotations

import ast
import io
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

from nebula_agents.application.commands import CommandService
from nebula_agents.application.evidence import EvidenceService
from nebula_agents.application.learning import LearningService
from nebula_agents.application.queries import QueryService
from nebula_agents.application.runs import RunService
from nebula_agents.bootstrap import build_application
from nebula_agents.domain.enums import ProviderKey, PromptAction
from nebula_agents.domain.models import LaunchRequest
from nebula_agents.presentation import mcp_server
from nebula_agents.presentation.mcp_server import (
    PAGE_SIZE,
    TOOL_NAMES,
    TOOLS,
    McpServer,
    handle_message,
    serve,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "summaries"
NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def served(tmp_path: Path, schema_root: Path):
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

    app = build_application(ws, tmp_path / "runtime")
    actor = app.current_actor()

    class Provider:
        def build_interactive_argv(self, _r, _p):
            return (str(Path(sys.executable).resolve()), "-c", "pass")

    class Tmux:
        def __init__(self): self.presence = [False, True]
        def has_session(self, _n):
            return self.presence.pop(0) if len(self.presence) > 1 else self.presence[0]
        def create_session(self, _n, _d): return None

    app.runs._preflight = SimpleNamespace(
        require_ready=lambda *a: SimpleNamespace(
            prompt_contract_path=str(prompts / "feature-operator-friendly.md"))
    )
    app.runs._providers = {ProviderKey.CODEX: Provider()}
    app.runs._tmux = Tmux()
    record = app.runs.launch(
        LaunchRequest("F0001", None, ProviderKey.CODEX, PromptAction.FEATURE, None, None, False), actor
    )
    shutil.copy2(FIXTURES / "command-log.jsonl", evidence / "commands.log")
    app.evidence.index_artifacts(record.run_id, [evidence / "commands.log"], actor)
    app.evidence.summarize(record.run_id, actor)

    server = McpServer(app.queries, SimpleNamespace(now=lambda: NOW))
    return SimpleNamespace(app=app, server=server, run_id=record.run_id,
                           evidence=evidence, actor=actor, schema_root=schema_root)


@pytest.fixture(scope="module")
def response_schema(schema_root: Path):
    document = json.loads(
        (schema_root / "f0003-mcp-response.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(document)
    return Draft202012Validator(document)


# --------------------------------------------------------------------------- #
# The read-only guarantee, structurally
# --------------------------------------------------------------------------- #
def test_the_server_holds_no_mutating_service(served) -> None:
    """ADR-007's guarantee. Inspect what it actually holds, not the signature."""
    mutating = (RunService, EvidenceService, LearningService, CommandService)
    held = [getattr(served.server, name) for name in vars(served.server)]
    assert not [obj for obj in held if isinstance(obj, mutating)]
    assert isinstance(served.server._queries, QueryService)


def test_the_module_never_imports_a_mutating_service() -> None:
    """A mutating tool would need this import, which makes it a visible edit.

    Import-level rather than instance-level: a handler could otherwise construct one
    itself and the instance check above would still pass.
    """
    source = Path(mcp_server.__file__).read_text(encoding="utf-8")
    banned = {"commands", "evidence", "learning", "runs", "gates", "transcripts"}
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module and "application" in node.module:
            imported.add(node.module.rsplit(".", 1)[-1])
    assert imported - {"queries"} <= set(), f"mcp_server imports mutating modules: {imported}"


def test_no_handler_name_reads_as_a_mutation() -> None:
    handlers = {name for name in vars(McpServer) if name.startswith("_") and not name.startswith("__")}
    for verb in ("write", "create", "index", "summarize", "draft", "decide", "launch"):
        assert not any(verb in name for name in handlers), f"handler suggests mutation: {verb}"


# --------------------------------------------------------------------------- #
# Tool names are a public contract
# --------------------------------------------------------------------------- #
def test_exactly_the_six_contract_tools_are_exposed() -> None:
    """Renaming one breaks host configuration, so the set is pinned literally."""
    assert set(TOOLS) == set(TOOL_NAMES) == {
        "nebula_session_list", "nebula_session_status", "nebula_gate_status",
        "nebula_validator_status", "nebula_evidence_list", "nebula_evidence_show",
    }


def test_tools_list_returns_every_tool_with_an_input_schema() -> None:
    response = handle_message(None, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = response["result"]["tools"]
    assert len(tools) == 6
    for tool in tools:
        assert tool["description"] and tool["inputSchema"]["type"] == "object"
        assert tool["inputSchema"]["additionalProperties"] is False


# --------------------------------------------------------------------------- #
# Responses conform to the committed schema
# --------------------------------------------------------------------------- #
def test_every_successful_response_validates(served, response_schema) -> None:
    calls = {
        "nebula_session_list": {},
        "nebula_session_status": {"run_id": served.run_id},
        "nebula_gate_status": {"run_id": served.run_id},
        "nebula_validator_status": {"run_id": served.run_id},
        "nebula_evidence_list": {"run_id": served.run_id},
    }
    for name, arguments in calls.items():
        payload = served.server.call(name, arguments)
        assert "error" not in payload, f"{name} failed: {payload.get('error')}"
        response_schema.validate(payload)
        assert payload["contract_version"] == "1.1"


def test_error_responses_validate_and_carry_no_stack_trace(served, response_schema) -> None:
    payload = served.server.call("nebula_session_status", {"run_id": "2026-01-01-deadbeef"})
    response_schema.validate(payload)
    assert payload["error"]["code"] == "NOT_FOUND"
    rendered = json.dumps(payload)
    assert "Traceback" not in rendered and "File \"" not in rendered


def test_an_unknown_tool_is_a_protocol_error_not_a_tool_response(served) -> None:
    """The committed schema pins `tool_name` to the six-name enum.

    An envelope naming an unknown tool could not be schema-conformant, and that is the
    schema being right: an unknown tool is not a tool *result*, it is a protocol error.
    Keeping it in the envelope would have forced either a non-conformant response or a
    dishonest `tool_name`.
    """
    with pytest.raises(mcp_server.UnknownTool):
        served.server.call("nebula_launch_everything", {})

    responses = drive(served.server, [
        json.dumps({"jsonrpc": "2.0", "id": 8, "method": "tools/call",
                    "params": {"name": "nebula_launch_everything", "arguments": {}}})
    ])
    assert responses[0]["error"]["code"] == -32601
    assert "nebula_launch_everything" in responses[0]["error"]["message"]


def test_a_missing_required_argument_is_invalid_input(served, response_schema) -> None:
    payload = served.server.call("nebula_session_status", {})
    response_schema.validate(payload)
    assert payload["error"]["code"] == "INVALID_INPUT"


# --------------------------------------------------------------------------- #
# evidence_show refuses unredacted content
# --------------------------------------------------------------------------- #
def test_evidence_show_returns_the_summary_and_retrieval_metadata(served) -> None:
    listed = served.server.call("nebula_evidence_list", {"run_id": served.run_id})
    artifact_id = listed["data"]["artifacts"][0]["artifact_id"]
    payload = served.server.call("nebula_evidence_show", {"artifact_id": artifact_id})
    assert payload["data"]["artifact_id"] == artifact_id
    assert payload["data"]["summary_path"]
    # Never raw bytes: the entry carries a path, not content.
    assert "content" not in payload["data"]


def test_evidence_show_refuses_content_when_redaction_is_not_pass(served, response_schema) -> None:
    """The rule that makes the tool safe to expose to a host at all."""
    unsummarized = served.evidence / "unsummarized.log"
    unsummarized.write_text("x\n", encoding="utf-8")
    entry = served.app.evidence.index_artifacts(
        served.run_id, [unsummarized], served.actor
    )[0]
    assert entry.redaction_status.value == "Pending"

    payload = served.server.call("nebula_evidence_show", {"artifact_id": entry.artifact_id})
    response_schema.validate(payload)
    assert payload["error"]["code"] == "REDACTION_FAILED"
    assert payload["error"]["category"] == "evidence_blocked"


# --------------------------------------------------------------------------- #
# Bounded responses
# --------------------------------------------------------------------------- #
def test_evidence_list_pages_rather_than_returning_everything(served) -> None:
    """No tool returns an unbounded log (runtime contract §2)."""
    paths = []
    for index in range(PAGE_SIZE + 5):
        path = served.evidence / f"artifact-{index:03d}.log"
        path.write_text(f"{index}\n", encoding="utf-8")
        paths.append(path)
    served.app.evidence.index_artifacts(served.run_id, paths, served.actor)

    first = served.server.call("nebula_evidence_list", {"run_id": served.run_id})
    assert len(first["data"]["artifacts"]) == PAGE_SIZE
    assert first["next_cursor"] is not None

    second = served.server.call(
        "nebula_evidence_list", {"run_id": served.run_id, "cursor": first["next_cursor"]}
    )
    assert 0 < len(second["data"]["artifacts"]) <= PAGE_SIZE
    ids = {a["artifact_id"] for a in first["data"]["artifacts"]}
    assert not ids & {a["artifact_id"] for a in second["data"]["artifacts"]}


def test_a_malformed_cursor_is_invalid_input(served, response_schema) -> None:
    payload = served.server.call(
        "nebula_evidence_list", {"run_id": served.run_id, "cursor": "not-a-cursor"}
    )
    response_schema.validate(payload)
    assert payload["error"]["code"] == "INVALID_INPUT"


# --------------------------------------------------------------------------- #
# The stdio loop
# --------------------------------------------------------------------------- #
def drive(server: McpServer, lines: list[str]) -> list[dict]:
    out = io.StringIO()
    serve(server, io.StringIO("\n".join(lines) + "\n"), out)
    return [json.loads(line) for line in out.getvalue().splitlines()]


def test_initialize_handshake_reports_tools_capability(served) -> None:
    responses = drive(served.server, [json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18"}}
    )])
    assert responses[0]["result"]["capabilities"] == {"tools": {}}
    assert responses[0]["result"]["serverInfo"]["name"] == "nebula-agents"


def test_a_malformed_line_is_skipped_without_killing_the_server(served) -> None:
    """Killing the server would take down the working tools along with the bad line."""
    responses = drive(served.server, [
        "{ not json",
        "",
        "[]",
        json.dumps({"jsonrpc": "2.0", "id": 9, "method": "ping"}),
    ])
    assert len(responses) == 1 and responses[0]["id"] == 9


def test_a_notification_produces_no_response(served) -> None:
    assert drive(served.server, [
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
    ]) == []


def test_an_unknown_method_returns_method_not_found(served) -> None:
    responses = drive(served.server, [
        json.dumps({"jsonrpc": "2.0", "id": 4, "method": "resources/list"})
    ])
    assert responses[0]["error"]["code"] == -32601


def test_a_tool_call_is_wrapped_with_an_is_error_flag(served) -> None:
    responses = drive(served.server, [
        json.dumps({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                    "params": {"name": "nebula_session_status",
                               "arguments": {"run_id": "2026-01-01-deadbeef"}}})
    ])
    assert responses[0]["result"]["isError"] is True
    body = json.loads(responses[0]["result"]["content"][0]["text"])
    assert body["error"]["code"] == "NOT_FOUND"

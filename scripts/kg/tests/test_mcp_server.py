from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
KG = REPO_ROOT / "scripts" / "kg"
sys.path.insert(0, str(KG))

import mcp_server  # noqa: E402
from kg_common import load_bundle  # noqa: E402

FEATURE = "F0007"


@pytest.fixture(scope="module")
def bundle() -> dict[str, object]:
    return load_bundle()


def _run_cli(script: str, *args: str) -> dict | list:
    """Run a KG CLI and return its parsed JSON stdout (telemetry redirected to a tmp file)."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl") as tf:
        proc = subprocess.run(
            [sys.executable, str(KG / script), *args, "--telemetry-file", tf.name],
            capture_output=True, text=True, cwd=str(KG),
        )
    assert proc.returncode == 0, f"{script} {args} failed: {proc.stderr}"
    return json.loads(proc.stdout)


# ---------- parity: MCP builder payload == CLI JSON (semantic / parsed-dict equality) ----------

@pytest.mark.parametrize("args,cli", [
    ({"target": FEATURE}, (FEATURE,)),
    ({"target": FEATURE, "fields": "ids"}, (FEATURE, "--fields", "ids")),
    ({"target": FEATURE, "tier": 1}, (FEATURE, "--tier", "1")),
])
def test_kg_context_parity(bundle, args, cli):
    assert mcp_server.build_context(args, bundle) == _run_cli("lookup.py", *cli)


@pytest.mark.parametrize("args,cli", [
    ({"ref": FEATURE}, (FEATURE,)),
    ({"ref": FEATURE, "compact": True}, (FEATURE, "--compact")),
])
def test_kg_blast_parity(bundle, args, cli):
    assert mcp_server.build_blast(args, bundle) == _run_cli("blast.py", *cli)


def _hint_matching_path(slice_: dict, bundle: dict) -> str | None:
    """Walk the feature slice for a file-path-shaped string that hint actually matches."""
    found: list[str] = []

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, str) and o.count("/") >= 2 and re.search(r"\.[A-Za-z0-9]+$", o):
            found.append(o)

    walk(slice_)
    return next((c for c in dict.fromkeys(found)
                 if mcp_server.build_hint({"path": c}, bundle).get("nodes")), None)


def test_kg_hint_parity(bundle):
    # use a real code path from the feature slice so the hint is non-empty (the CLI only
    # emits JSON when a path matches; the empty case is covered separately below).
    path = _hint_matching_path(mcp_server.build_context({"target": FEATURE}, bundle), bundle)
    if path is None:
        pytest.skip("no hint-matching code path in fixture")
    assert mcp_server.build_hint({"path": path}, bundle) == _run_cli("hint.py", path, "--json")


def test_kg_hint_empty_returns_payload(bundle):
    # Deliberate divergence: the CLI prints nothing on no-match; an MCP tool must return
    # structured data, so kg_hint returns a well-formed empty payload.
    h = mcp_server.build_hint({"path": "engine/src/Nonexistent/Nope.cs"}, bundle)
    assert h["path"] and h["nodes"] == [] and h["symbols"] == []


def test_include_projection_is_top_level_only(bundle):
    full = mcp_server.build_context({"target": FEATURE}, bundle)
    projected = mcp_server.build_context({"target": FEATURE, "include": ["target", "affects"]}, bundle)
    assert set(projected) <= {"target", "affects"}
    for k in projected:
        assert projected[k] == full[k]


def test_bad_args_raise_tool_error(bundle):
    with pytest.raises(mcp_server.McpToolError):
        mcp_server.build_context({}, bundle)                       # neither target nor file
    with pytest.raises(mcp_server.McpToolError):
        mcp_server.build_context({"target": FEATURE, "fields": "bogus"}, bundle)
    with pytest.raises(mcp_server.McpToolError):
        mcp_server.build_blast({"ref": "entity:does-not-exist"}, bundle)


# ---------- result-format contract: minified, semantically equal (not byte-equal) ----------

def test_result_is_minified(bundle):
    payload = mcp_server.build_context({"target": FEATURE, "fields": "ids"}, bundle)
    minified = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    assert "\n" not in minified and ", " not in minified
    # CLI keeps indent=2 (byte-different) but parses to the same dict
    cli_bytes = json.dumps(_run_cli("lookup.py", FEATURE, "--fields", "ids"), indent=2)
    assert minified != cli_bytes
    assert json.loads(minified) == json.loads(cli_bytes)


# ---------- kg_validate: read-only self-check ----------

@pytest.mark.parametrize("mode", ["check-orphans", "check-symbols", "check-coverage-gaps", "check-drift"])
def test_kg_validate_shape(bundle, mode):
    r = mcp_server.build_validate({"mode": mode}, bundle)
    assert r["mode"] == mode
    assert isinstance(r["ok"], bool)
    assert isinstance(r["errors"], list) and isinstance(r["warnings"], list)


def test_kg_validate_rejects_mutating_mode(bundle):
    for mode in ("regenerate-symbols", "write-coverage-report", "bogus"):
        with pytest.raises(mcp_server.McpToolError):
            mcp_server.build_validate({"mode": mode}, bundle)


def test_kg_validate_never_mutates(bundle):
    kg = REPO_ROOT / "planning-mds" / "knowledge-graph"
    snapshot = {p.name: p.stat().st_mtime for p in kg.glob("*.yaml")}
    for mode in ("check-symbols", "check-orphans", "check-coverage-gaps"):
        mcp_server.build_validate({"mode": mode}, bundle)
    assert {p.name: p.stat().st_mtime for p in kg.glob("*.yaml")} == snapshot


# ---------- kg_workstate: the writer + its safe-path boundary ----------

@pytest.mark.parametrize("bad", ["../evil", "a/b", "..", "foo/../bar", "/abs", "", "sess id", "x\\y", ".."])
def test_kg_workstate_rejects_unsafe_session(bad):
    with pytest.raises(mcp_server.McpToolError):
        mcp_server._safe_state_file(bad)


def test_kg_workstate_safe_path_under_workstate_dir():
    p = mcp_server._safe_state_file("good-session_1")
    assert p.parent == mcp_server._WORKSTATE_DIR
    assert p.name == "good-session_1.yaml"


def test_kg_workstate_init_decision_dump_roundtrip(bundle):
    import uuid
    sid = f"mcp-test-{uuid.uuid4().hex[:8]}"
    sf = mcp_server._safe_state_file(sid)
    try:
        init = mcp_server.build_workstate(
            {"action": "init", "session_id": sid, "role": "architect", "scope": FEATURE}, bundle)
        assert init["ok"] is True
        dec = mcp_server.build_workstate(
            {"action": "decision", "session_id": sid, "summary": "use temporal", "topic": "orchestration"}, bundle)
        assert dec["ok"] is True
        dump = mcp_server.build_workstate({"action": "dump", "session_id": sid}, bundle)
        assert dump["ok"] is True
        assert dump["state"]["session"]["role"] == "architect"
        digest = mcp_server.build_workstate({"action": "digest", "session_id": sid}, bundle)
        assert digest["ok"] is True
        assert digest["digest"]["session"]["role"] == "architect"
        assert "use temporal" in digest["digest"].get("decided", [])
    finally:
        if sf.exists():
            sf.unlink()


def test_kg_workstate_bad_action_and_missing_args(bundle):
    with pytest.raises(mcp_server.McpToolError):
        mcp_server.build_workstate({"action": "wipe", "session_id": "s"}, bundle)
    with pytest.raises(mcp_server.McpToolError):
        mcp_server.build_workstate({"action": "init", "session_id": "s"}, bundle)  # missing role


# ---------- over-stdio integration: initialize -> tools/list -> tools/call ----------

def _drive_server(requests: list[dict]) -> list[dict]:
    proc = subprocess.Popen(
        [sys.executable, str(KG / "mcp_server.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, cwd=str(KG),
    )
    payload = "".join(json.dumps(r) + "\n" for r in requests)
    out, _ = proc.communicate(payload, timeout=60)
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def test_stdio_protocol_roundtrip():
    responses = _drive_server([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},  # notification -> no response
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "kg_context", "arguments": {"target": FEATURE, "fields": "ids"}}},
    ])
    by_id = {r["id"]: r for r in responses}
    assert set(by_id) == {1, 2, 3}  # the notification produced no response

    assert by_id[1]["result"]["serverInfo"]["name"] == "kg"
    assert by_id[1]["result"]["protocolVersion"]
    assert {t["name"] for t in by_id[2]["result"]["tools"]} == {
        "kg_context", "kg_hint", "kg_blast", "kg_validate", "kg_workstate"}

    call = by_id[3]["result"]
    assert not call.get("isError")
    doc = json.loads(call["content"][0]["text"])  # minified JSON text content
    assert doc.get("target")


def test_stdio_tool_error_is_isError():
    responses = _drive_server([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "kg_context", "arguments": {"target": "F9999"}}},
    ])
    by_id = {r["id"]: r for r in responses}
    assert by_id[2]["result"]["isError"] is True

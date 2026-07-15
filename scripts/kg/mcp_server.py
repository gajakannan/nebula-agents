#!/usr/bin/env python3
"""KG retrieval MCP server (stdio, local, dependency-free).

Phase 1 of KG-MCP-PLAN: expose KG retrieval as MCP tools so any harness gets
identical, structured, token-light access — *without* changing retrieval semantics
or the YAML model. This is a thin function-call adapter over the existing CLI
builders (`lookup`, `hint`, `blast`) + `kg_common`; it does not re-implement
retrieval, and the CLIs remain the implementation + human/CI entry point.

Transport: stdio, newline-delimited JSON-RPC 2.0. No network surface, no auth.
Dependency: none — the MCP stdio surface (initialize / tools/list / tools/call /
ping) is small, so we implement it directly rather than pin the MCP SDK. This keeps
the product at its single `pyyaml` dependency (the LCD / least-infra decision); the
adapter is thin enough to swap onto the SDK later if a richer client needs it.

Tools (read-only this slice): kg_context (lookup), kg_hint (hint), kg_blast (blast).
kg_validate + kg_workstate land next. Results are MINIFIED JSON text — parity with
the CLIs is *semantic* (parsed-dict equality), never byte equality (the CLIs keep
indent=2; this layer minifies). Every call emits telemetry with source="mcp".
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import blast  # noqa: E402
import hint  # noqa: E402
import lookup  # noqa: E402
import validate  # noqa: E402
import workstate  # noqa: E402
import kg_common  # noqa: E402

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "kg", "version": "0.1.0"}

# Cache the bundle across calls in a session; invalidate on YAML mtime change so a
# mid-session KG edit is picked up without a stale read.
_BUNDLE: dict[str, Any] | None = None
_BUNDLE_MTIME: float | None = None
_KG_DIR = kg_common.REPO_ROOT / "planning-mds" / "knowledge-graph"


class McpToolError(Exception):
    """A tool-level error (bad args / unresolved ref) — surfaced as isError, not a crash."""


def _kg_mtime() -> float:
    try:
        return max((p.stat().st_mtime for p in _KG_DIR.glob("*.yaml")), default=0.0)
    except OSError:
        return 0.0


def _bundle() -> dict[str, Any]:
    global _BUNDLE, _BUNDLE_MTIME
    mtime = _kg_mtime()
    if _BUNDLE is None or mtime != _BUNDLE_MTIME:
        _BUNDLE = kg_common.load_bundle()
        _BUNDLE_MTIME = mtime
    return _BUNDLE


def _require_one(args: dict[str, Any], keys: tuple[str, ...]) -> str:
    present = [k for k in keys if args.get(k) not in (None, "")]
    if len(present) != 1:
        raise McpToolError(f"provide exactly one of: {', '.join(keys)}")
    return present[0]


def _project(payload: Any, include: Any) -> Any:
    """Top-level field projection (the contract's `include`; distinct from `fields`)."""
    if not include:
        return payload
    if not isinstance(include, list) or not all(isinstance(x, str) for x in include):
        raise McpToolError("`include` must be a list of top-level field names")
    if isinstance(payload, dict):
        return {k: payload[k] for k in include if k in payload}
    return payload


# ---------- pure payload builders (no telemetry side effects; used by parity tests) ----------

def build_context(args: dict[str, Any], bundle: dict[str, Any]) -> Any:
    """kg_context — feature/story slice or reverse file lookup (wraps lookup.py)."""
    mode = _require_one(args, ("target", "file"))
    if mode == "file":
        payload = lookup.lookup_by_file(str(args["file"]), bundle)
    else:
        tier = args.get("tier", 4)
        if tier not in (1, 2, 3, 4):
            raise McpToolError("`tier` must be one of 1, 2, 3, 4")
        fields = args.get("fields", "full")
        if fields not in ("ids", "summaries", "full"):
            raise McpToolError("`fields` must be one of: ids, summaries, full")
        try:
            payload = lookup.lookup_by_target(
                str(args["target"]), bundle,
                tier=tier, fields=fields, allow_missing=bool(args.get("allow_missing", False)),
            )
        except SystemExit as exc:  # unknown target -> tool error, not a crash
            raise McpToolError(str(exc)) from exc
    return _project(payload, args.get("include"))


def build_hint(args: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    """kg_hint — pre-search routing; mirrors `hint.py --json` (wraps hint.py)."""
    mode = _require_one(args, ("path", "symbol"))
    if mode == "symbol":
        _text, matches = hint.hint_symbol(str(args["symbol"]), bundle)
        return {
            "symbol": str(args["symbol"]),
            "matches": [
                {"id": s["id"], "name": s.get("name"), "node": s.get("node"),
                 "file": s.get("file"), "line": s.get("line"),
                 "container": s.get("container"), "kind": s.get("kind")}
                for s in matches
            ],
        }
    normalized = hint.normalize_repo_path(str(args["path"]))
    empty = {"path": normalized, "nodes": [], "features": [], "stories": [],
             "policy_rules": [], "symbols": []}
    if normalized.count("/") < 2:
        return empty
    matches = hint.match_path(normalized, bundle)
    if not matches:
        return empty
    node_ids = [m["id"] for m in matches]
    features, stories = kg_common.related_mapping_entries(node_ids, bundle["mappings"])
    payload = {
        "path": normalized,
        "nodes": node_ids,
        "features": [f["id"] for f in features],
        "stories": [s["id"] for s in stories],
        "policy_rules": hint.find_policy_rules_for_nodes(node_ids, bundle),
        "symbols": [
            {"id": s["id"], "name": s.get("name"), "kind": s.get("kind"),
             "container": s.get("container"), "line": s.get("line")}
            for s in kg_common.match_symbols_for_path(normalized, bundle)
        ],
    }
    hotspots = {nid: info for nid in node_ids
                for info in (hint._hotspots_by_node().get(nid),) if info}
    if hotspots:
        payload["hotspots"] = hotspots
    return payload


def build_blast(args: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    """kg_blast — impact radius before editing shared semantics (wraps blast.py)."""
    compact = bool(args.get("compact", False))
    symbol = args.get("symbol")
    if symbol:
        matches = blast.match_symbol_by_name(str(symbol), bundle, node_id=args.get("node"))
        if not matches:
            raise McpToolError(f"no symbols named: {symbol}")
        report = blast.build_symbol_blast(matches, bundle, {"symbol_name": str(symbol), "node": args.get("node")})
        return report["summary"] if compact else report

    ref = args.get("ref")
    if not ref:
        raise McpToolError("provide `ref` (node/feature/story/symbol id) or `symbol`")
    ref = str(ref)

    if ref.startswith("symbol:"):
        sym = blast.get_symbol_by_id(ref, bundle)
        if sym is None:
            raise McpToolError(f"unknown symbol id: {ref}")
        report = blast.build_symbol_blast([sym], bundle, {"symbol_id": ref})
        return report["summary"] if compact else report

    if args.get("is_file"):
        starting_ids = blast.node_ids_for_file(ref, bundle)
        if not starting_ids:
            raise McpToolError(f"no KG bindings found for: {ref}")
        query = {"file": blast.repo_relative(ref)}
    else:
        normalized = blast.normalize_target_id(ref)
        node = bundle["all_nodes"].get(normalized)
        if node is None:
            raise McpToolError(f"unknown node: {ref}")
        if node.get("_kind") in ("feature", "story"):
            starting_ids = blast.canonical_refs_from_mapping(node) or {normalized}
            query = {"feature_or_story": normalized, "affected_canonical_nodes": sorted(starting_ids)}
        else:
            starting_ids = {normalized}
            query = {"node": normalized}

    report = blast.build_blast_report(starting_ids, bundle, query)
    return report["summary"] if compact else report


def build_validate(args: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    """kg_validate — read-only self-check (wraps validate.py's read-only checks).

    Calls the same check functions main() uses, scoped to the requested mode. NEVER
    mutates: no coverage-report write, no symbol/decision regeneration.
    """
    mode = args.get("mode")
    report = validate.ValidationReport()
    summary: Any = None
    if mode == "check-drift":
        validate.validate_casbin_drift(report, bundle)
        memory_dir = args.get("memory_dir")
        if memory_dir:
            validate.validate_external_memory_drift(report, Path(str(memory_dir)))
    elif mode == "check-symbols":
        summary = validate.validate_symbol_index(report, bundle, required=True)
    elif mode == "check-orphans":
        summary = validate.validate_orphans(
            report, bundle, exempt_kinds=validate.DEFAULT_ORPHAN_EXEMPT_KINDS, as_errors=False)
    elif mode == "check-coverage-gaps":
        summary = validate.validate_coverage_gaps(
            report, excludes=validate.DEFAULT_COVERAGE_GAP_EXCLUDES, as_errors=False)
    else:
        raise McpToolError("`mode` must be one of: check-drift, check-symbols, check-orphans, check-coverage-gaps")
    payload = {"mode": mode, "ok": not report.errors,
               "errors": report.errors, "warnings": report.warnings}
    if summary is not None:
        payload["summary"] = summary
    return payload


# kg_workstate write boundary: only ever under {PRODUCT_ROOT}/.kg-state/workstate/.
_WORKSTATE_DIR = (kg_common.REPO_ROOT / ".kg-state" / "workstate").resolve()
_KG_GRAPH_DIR = (kg_common.REPO_ROOT / "planning-mds" / "knowledge-graph").resolve()
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _safe_state_file(session_id: Any) -> Path:
    """Derive a canonical state-file path from a session id, rejecting any escape.

    The MCP boundary is narrower than the CLI's --state-file: arbitrary paths are not
    accepted. Traversal, separators, and any path under the KG dir are rejected.
    """
    if not isinstance(session_id, str) or not session_id:
        raise McpToolError("`session_id` is required")
    if ".." in session_id or not _SESSION_ID_RE.fullmatch(session_id):
        raise McpToolError("`session_id` must match [A-Za-z0-9._-]+ (no path separators or '..')")
    path = (_WORKSTATE_DIR / f"{session_id}.yaml").resolve()
    if path.parent != _WORKSTATE_DIR:
        raise McpToolError("resolved state path escapes the workstate directory")
    if path == _KG_GRAPH_DIR or _KG_GRAPH_DIR in path.parents:
        raise McpToolError("refusing to write under the knowledge-graph directory")
    _WORKSTATE_DIR.mkdir(parents=True, exist_ok=True)
    return path


def _run_workstate(fn, ns: argparse.Namespace) -> tuple[str, int]:
    """Run a workstate cmd_* with stdout captured — its prints must never reach the
    JSON-RPC stdout channel."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(ns)
    return buf.getvalue(), rc


def build_workstate(args: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    """kg_workstate — session resilience; the ONE tool that writes (to a safe per-session
    state file under .kg-state/workstate/, never the KG). Wraps workstate.py cmd_*."""
    action = args.get("action")
    if action not in ("init", "decision", "escalate", "dump", "digest"):
        raise McpToolError("`action` must be one of: init, decision, escalate, dump, digest")
    state_file = _safe_state_file(args.get("session_id"))
    ns = argparse.Namespace(state_file=str(state_file), telemetry_file=None)
    result: dict[str, Any] = {"action": action, "session_id": args["session_id"],
                              "state_file": str(state_file)}

    if action == "dump":
        ns.compact = bool(args.get("compact", False))
        ns.current_view = bool(args.get("current_view", False))
        ns.json = True
        out, rc = _run_workstate(workstate.cmd_dump, ns)
        result["ok"] = rc == 0
        result["state"] = json.loads(out) if out.strip() else {}
        return result

    if action == "digest":
        ns.json = True
        out, rc = _run_workstate(workstate.cmd_digest, ns)
        result["ok"] = rc == 0
        result["digest"] = json.loads(out) if out.strip() else {}
        return result

    if action == "init":
        if not args.get("role"):
            raise McpToolError("`role` is required for action=init")
        ns.role = str(args["role"])
        ns.scope = args.get("scope")
        ns.run_id = args.get("run_id")
        ns.mode = args.get("mode")
        ns.force = bool(args.get("force", False))
        _out, rc = _run_workstate(workstate.cmd_init, ns)
    elif action == "decision":
        if not args.get("summary"):
            raise McpToolError("`summary` is required for action=decision")
        ns.summary = str(args["summary"])
        ns.files = args.get("files")
        ns.rationale = args.get("rationale")
        ns.topic = args.get("topic")
        ns.supersedes = args.get("supersedes")
        _out, rc = _run_workstate(workstate.cmd_decision, ns)
    else:  # escalate
        if not args.get("reason"):
            raise McpToolError("`reason` is required for action=escalate")
        ns.reason = str(args["reason"])
        ns.nodes = args.get("nodes")
        ns.opened_raw = args.get("opened_raw")
        _out, rc = _run_workstate(workstate.cmd_escalate, ns)

    result["ok"] = rc == 0
    if state_file.exists():  # echo the resulting state so the caller sees the update
        result["state"] = workstate.ensure_state_shape(workstate.load_state(state_file))
    return result


# ---------- tool registry ----------

TOOLS: dict[str, dict[str, Any]] = {
    "kg_context": {
        "builder": build_context,
        "description": "Feature/story KG slice (or reverse file lookup). Returns target, "
                       "affects, governed_by, uses_schema, uses_api_contract, depends_on, "
                       "validated_by, code_paths, source_precedence. Call before reading raw artifacts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Feature/story id, e.g. F0007 or F0007-S0003"},
                "file": {"type": "string", "description": "Repo-relative file for reverse lookup"},
                "tier": {"type": "integer", "enum": [1, 2, 3, 4], "description": "Depth (default 4)"},
                "fields": {"type": "string", "enum": ["ids", "summaries", "full"],
                           "description": "Node-summary verbosity within the tier (default full)"},
                "include": {"type": "array", "items": {"type": "string"},
                            "description": "Project to these top-level fields only"},
                "allow_missing": {"type": "boolean", "description": "Return an unmapped payload instead of erroring"},
            },
        },
    },
    "kg_hint": {
        "builder": build_hint,
        "description": "Pre-search routing — call BEFORE any code search. Returns matched nodes, "
                       "features, stories, Casbin policy rules, top symbols, and risk hotspots.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Repo-relative file or directory path"},
                "symbol": {"type": "string", "description": "Symbol source-name to route by"},
            },
        },
    },
    "kg_blast": {
        "builder": build_blast,
        "description": "Impact radius before editing shared semantics. Returns impacted features, "
                       "stories, code bindings, Casbin rules, and resolved files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Node id, feature/story id, or symbol: id"},
                "is_file": {"type": "boolean", "description": "Treat `ref` as a repo file path"},
                "symbol": {"type": "string", "description": "Symbol name (walks symbol call edges)"},
                "node": {"type": "string", "description": "Scope a --symbol blast to one canonical node id"},
                "compact": {"type": "boolean", "description": "Summary only, omit resolved file lists"},
            },
        },
    },
    "kg_validate": {
        "builder": build_validate,
        "description": "Read-only KG self-check mid-task (no Bash). Returns {ok, errors, warnings, "
                       "summary?}. Never mutates — no coverage-report/symbol/decision regeneration.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mode": {"type": "string",
                         "enum": ["check-drift", "check-symbols", "check-orphans", "check-coverage-gaps"],
                         "description": "Which read-only check to run"},
                "memory_dir": {"type": "string",
                               "description": "External-memory dir for check-drift (optional)"},
            },
            "required": ["mode"],
        },
    },
    "kg_workstate": {
        "builder": build_workstate,
        "description": "Session resilience — the one writing tool. Writes ONLY to a safe per-session "
                       "state file under .kg-state/workstate/ (never the KG). init/decision/escalate/dump.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["init", "decision", "escalate", "dump", "digest"]},
                "session_id": {"type": "string", "description": "Safe session id ([A-Za-z0-9._-]+)"},
                "role": {"type": "string", "description": "init: agent role"},
                "scope": {"type": "string", "description": "init: feature/story id"},
                "run_id": {"type": "string", "description": "init: correlation id"},
                "mode": {"type": "string", "description": "init: execution mode"},
                "force": {"type": "boolean", "description": "init: overwrite existing state"},
                "summary": {"type": "string", "description": "decision: one-line summary"},
                "files": {"type": "array", "items": {"type": "string"}, "description": "decision: affected files"},
                "rationale": {"type": "string", "description": "decision: brief rationale"},
                "topic": {"type": "string", "description": "decision: supersession topic slug"},
                "supersedes": {"type": "array", "items": {"type": "integer"},
                               "description": "decision: prior decision_ids replaced"},
                "reason": {"type": "string", "description": "escalate: reason"},
                "nodes": {"type": "array", "items": {"type": "string"}, "description": "escalate: triggering node ids"},
                "opened_raw": {"type": "array", "items": {"type": "string"},
                               "description": "escalate: raw artifact paths opened"},
                "compact": {"type": "boolean", "description": "dump: compact form"},
                "current_view": {"type": "boolean", "description": "dump: superseded-filtered projection"},
            },
            "required": ["action", "session_id"],
        },
    },
}


def _summary_for_telemetry(name: str, payload: Any) -> dict[str, Any]:
    return {"tool": name, "tokens_estimated": kg_common.estimate_tokens(payload)}


def call_tool(name: str, args: dict[str, Any], *, run_id: str | None = None) -> Any:
    spec = TOOLS.get(name)
    if spec is None:
        raise McpToolError(f"unknown tool: {name}")
    payload = spec["builder"](args, _bundle())
    # Telemetry carries source="mcp" via NEBULA_SOURCE (set in env at startup); eval.py
    # then separates MCP retrievals from CLI ones. Never let telemetry crash a call.
    try:
        kg_common.emit_telemetry(None, run_id, name, _summary_for_telemetry(name, payload))
    except Exception:
        pass
    return payload


# ---------- JSON-RPC over stdio ----------

def _result(mid: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def handle_message(msg: dict[str, Any]) -> dict[str, Any] | None:
    method = msg.get("method")
    if method is None:  # a response or malformed — nothing to do
        return None
    mid = msg.get("id")
    params = msg.get("params") or {}

    if method == "initialize":
        return _result(mid, {
            "protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return _result(mid, {})
    if method == "tools/list":
        tools = [{"name": n, "description": s["description"], "inputSchema": s["inputSchema"]}
                 for n, s in TOOLS.items()]
        return _result(mid, {"tools": tools})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            payload = call_tool(str(name), args)
        except McpToolError as exc:
            return _result(mid, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
        except Exception as exc:  # defensive — surface, don't kill the server
            return _result(mid, {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}],
                                 "isError": True})
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))  # minified
        return _result(mid, {"content": [{"type": "text", "text": text}]})

    if mid is None:  # unknown notification — ignore
        return None
    return _error(mid, -32601, f"Method not found: {method}")


def serve(stdin: Any = None, stdout: Any = None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    os.environ.setdefault("NEBULA_SOURCE", "mcp")
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue  # can't form a response without an id
        response = handle_message(msg)
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(serve())

"""Read-only MCP surface over stdio (F0003-S0003, ADR-007).

Six tools, JSON in, JSON out, no third-party dependency — mirroring the in-repo
precedent `scripts/kg/mcp_server.py`. `engine/pyproject.toml` gains nothing required, so
the CLI is unaffected when no host is present and S0003's "MCP SDK unavailable" edge case
is unreachable rather than handled.

**Read-only is structural, at two levels.** The server is constructed with a *query-only*
facade: the services that mutate are not reachable from here, so read-only is a
consequence of what was wired in rather than a check inside each handler. Every tool call
*also* evaluates the default-deny authorization contract with action `ReadState`. Both
mechanisms are kept deliberately — a policy misconfiguration alone must not widen the
surface, and a wiring mistake alone must not either.

Adding a mutating tool therefore requires changing the facade this adapter is constructed
with: a visible architectural edit, not a new handler.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable

from nebula_agents.application.queries import QueryService
from nebula_agents.domain.errors import ErrorCode, NebulaError

CONTRACT_VERSION = "1.1"
PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "nebula-agents", "version": CONTRACT_VERSION}

#: Page size for list tools. Responses are bounded: no tool returns an unbounded
#: transcript or log (runtime contract §2).
PAGE_SIZE = 50

#: NebulaError codes mapped to the committed `f0003-mcp-response` error vocabulary.
#: Anything unmapped becomes INVALID_INPUT rather than leaking an internal code.
_ERROR_CODES = {
    ErrorCode.RUN_NOT_FOUND: ("NOT_FOUND", "not_found"),
    ErrorCode.ARTIFACT_NOT_FOUND: ("NOT_FOUND", "not_found"),
    ErrorCode.PROPOSAL_NOT_FOUND: ("NOT_FOUND", "not_found"),
    ErrorCode.FORBIDDEN: ("FORBIDDEN", "authorization"),
    ErrorCode.PATH_DENIED: ("FORBIDDEN", "authorization"),
    ErrorCode.REDACTION_FAILED: ("REDACTION_FAILED", "evidence_blocked"),
    ErrorCode.STATE_IO: ("RUNTIME_UNREADABLE", "permission"),
    ErrorCode.STATE_CORRUPT: ("RUNTIME_UNREADABLE", "permission"),
    ErrorCode.PREFLIGHT_BLOCKED: ("WORKSPACE_NOT_CONFIGURED", "setup_required"),
    ErrorCode.USAGE_ERROR: ("INVALID_INPUT", "usage"),
}

#: Tool names are a PUBLIC CONTRACT. Renaming one breaks host configuration.
TOOL_NAMES = (
    "nebula_session_list",
    "nebula_session_status",
    "nebula_gate_status",
    "nebula_validator_status",
    "nebula_evidence_list",
    "nebula_evidence_show",
)

_RUN_ID = {"type": "string", "description": "Run identifier, YYYY-MM-DD-8hex."}

TOOLS: dict[str, dict[str, Any]] = {
    "nebula_session_list": {
        "description": "List active and recent runs with sanitized status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "additionalProperties": False,
        },
    },
    "nebula_session_status": {
        "description": "Provider, action, feature, gate, validator, and evidence summary for one run.",
        "inputSchema": {
            "type": "object", "properties": {"run_id": _RUN_ID},
            "required": ["run_id"], "additionalProperties": False,
        },
    },
    "nebula_gate_status": {
        "description": "Current gate state and decision records for one run.",
        "inputSchema": {
            "type": "object", "properties": {"run_id": _RUN_ID},
            "required": ["run_id"], "additionalProperties": False,
        },
    },
    "nebula_validator_status": {
        "description": "Latest validator results for one run.",
        "inputSchema": {
            "type": "object", "properties": {"run_id": _RUN_ID},
            "required": ["run_id"], "additionalProperties": False,
        },
    },
    "nebula_evidence_list": {
        "description": "Indexed artifacts with kind, summary, freshness, and retrieval availability.",
        "inputSchema": {
            "type": "object",
            "properties": {"run_id": _RUN_ID, "kind": {"type": "string"},
                           "cursor": {"type": "string"}},
            "required": ["run_id"], "additionalProperties": False,
        },
    },
    "nebula_evidence_show": {
        "description": "Redacted summary and retrieval metadata for one artifact. Never raw bytes.",
        "inputSchema": {
            "type": "object", "properties": {"artifact_id": {"type": "string"}},
            "required": ["artifact_id"], "additionalProperties": False,
        },
    },
}


class UnknownTool(LookupError):
    """A tool name outside the committed six. Surfaces as JSON-RPC -32601."""

    def __init__(self, tool_name: str) -> None:
        super().__init__(tool_name)
        self.tool_name = tool_name


class McpServer:
    """Constructed with the query facade ONLY (ADR-007).

    `queries` is typed `QueryService` rather than left loose so that handing this a
    command facade is a type error as well as an architectural one.
    """

    def __init__(self, queries: QueryService, clock) -> None:
        self._queries = queries
        self._clock = clock
        self._handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "nebula_session_list": self._session_list,
            "nebula_session_status": self._session_status,
            "nebula_gate_status": self._gate_status,
            "nebula_validator_status": self._validator_status,
            "nebula_evidence_list": self._evidence_list,
            "nebula_evidence_show": self._evidence_show,
        }
        assert set(self._handlers) == set(TOOL_NAMES)

    # ---------------------------------------------------------------- #
    # Envelope
    # ---------------------------------------------------------------- #
    def _envelope(self, tool_name: str, data: Any, next_cursor: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "contract_version": CONTRACT_VERSION,
            "tool_name": tool_name,
            "generated_at": _utc(self._clock.now()),
            "data": data,
        }
        if next_cursor is not None:
            body["next_cursor"] = next_cursor
        return body

    def _failure(self, tool_name: str, error: NebulaError) -> dict[str, Any]:
        """Structured, with no stack trace and no path outside an approved root."""
        code, category = _ERROR_CODES.get(error.code, ("INVALID_INPUT", "usage"))
        return {
            "contract_version": CONTRACT_VERSION,
            "tool_name": tool_name,
            "generated_at": _utc(self._clock.now()),
            "error": {
                "code": code,
                "message": error.message,
                "category": category,
                "remediation": error.remediation,
                "details": [],
            },
        }

    def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke one tool. Raises `UnknownTool` rather than returning an envelope.

        The committed `f0003-mcp-response` schema pins `tool_name` to the six-name enum,
        so an envelope naming an unknown tool could not be schema-conformant. That is the
        schema being right: an unknown tool is not a tool *result*, it is a protocol
        error, and it belongs at the JSON-RPC layer as `-32601`. Keeping it here would
        have forced either a non-conformant response or a dishonest `tool_name`.
        """
        handler = self._handlers.get(tool_name)
        if handler is None:
            raise UnknownTool(tool_name)
        try:
            return handler(arguments or {})
        except NebulaError as error:
            return self._failure(tool_name, error)

    # ---------------------------------------------------------------- #
    # Tools — every one of these reaches only the query facade
    # ---------------------------------------------------------------- #
    def _session_list(self, arguments: dict[str, Any]) -> dict[str, Any]:
        limit = min(int(arguments.get("limit", PAGE_SIZE)), 100)
        projections = self._queries.sessions(limit=limit)
        return self._envelope("nebula_session_list", {"sessions": [_plain(p) for p in projections]})

    def _session_status(self, arguments: dict[str, Any]) -> dict[str, Any]:
        run_id = _require(arguments, "run_id")
        return self._envelope("nebula_session_status", _plain(self._queries.status(run_id)))

    def _gate_status(self, arguments: dict[str, Any]) -> dict[str, Any]:
        run_id = _require(arguments, "run_id")
        projection = _plain(self._queries.status(run_id))
        return self._envelope("nebula_gate_status", {"run_id": run_id, "gate": projection.get("gate")})

    def _validator_status(self, arguments: dict[str, Any]) -> dict[str, Any]:
        run_id = _require(arguments, "run_id")
        projection = _plain(self._queries.status(run_id))
        return self._envelope(
            "nebula_validator_status",
            {"run_id": run_id, "latest_validator": projection.get("latest_validator")},
        )

    def _evidence_list(self, arguments: dict[str, Any]) -> dict[str, Any]:
        run_id = _require(arguments, "run_id")
        entries = self._queries.artifacts(run_id, kind=arguments.get("kind"))
        start = _cursor_offset(arguments.get("cursor"))
        page = entries[start : start + PAGE_SIZE]
        remaining = len(entries) > start + PAGE_SIZE
        return self._envelope(
            "nebula_evidence_list",
            {"run_id": run_id, "artifacts": [_plain(e) for e in page]},
            next_cursor=str(start + PAGE_SIZE) if remaining else None,
        )

    def _evidence_show(self, arguments: dict[str, Any]) -> dict[str, Any]:
        artifact_id = _require(arguments, "artifact_id")
        entry = self._queries.artifact(artifact_id)
        # Refuse content whenever redaction is not Pass, returning a structured
        # redaction-failure error rather than a partial body (runtime contract §2).
        if entry.redaction_status.value != "Pass":
            raise NebulaError(
                ErrorCode.REDACTION_FAILED,
                "The artifact summary is withheld because redaction did not complete.",
                "gate-blocked",
                "Re-run evidence summarize after resolving the redaction failure.",
            )
        return self._envelope("nebula_evidence_show", _plain(entry))


def _require(arguments: dict[str, Any], name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value:
        raise NebulaError(
            ErrorCode.USAGE_ERROR, f"{name} is required.", "usage",
            f"Pass {name} as a string.",
        )
    return value


def _cursor_offset(cursor: Any) -> int:
    if cursor is None:
        return 0
    try:
        offset = int(cursor)
    except (TypeError, ValueError):
        raise NebulaError(
            ErrorCode.USAGE_ERROR, "cursor is not a valid page marker.", "usage",
            "Pass the next_cursor value from the previous response.",
        ) from None
    return max(offset, 0)


def _utc(value) -> str:
    from nebula_agents.domain.models import serialize_record

    return serialize_record({"v": value})["v"]


def _plain(value: Any) -> Any:
    from nebula_agents.presentation.formatters import to_data

    return to_data(value)


# --------------------------------------------------------------------------- #
# JSON-RPC over stdio
# --------------------------------------------------------------------------- #
def _result(message_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def _rpc_error(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


def handle_message(server: McpServer, message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    if method is None:
        return None
    message_id = message.get("id")
    params = message.get("params") or {}

    if method == "initialize":
        return _result(message_id, {
            "protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return _result(message_id, {})
    if method == "tools/list":
        return _result(message_id, {"tools": [
            {"name": name, "description": spec["description"], "inputSchema": spec["inputSchema"]}
            for name, spec in TOOLS.items()
        ]})
    if method == "tools/call":
        try:
            payload = server.call(str(params.get("name")), params.get("arguments") or {})
        except UnknownTool as unknown:
            return _rpc_error(message_id, -32601, f"Unknown tool: {unknown.tool_name}")
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return _result(message_id, {
            "content": [{"type": "text", "text": text}],
            "isError": "error" in payload,
        })
    if message_id is None:
        return None
    return _rpc_error(message_id, -32601, f"Method not found: {method}")


def serve(server: McpServer, stdin: Any = None, stdout: Any = None) -> int:
    """Read line-delimited JSON-RPC until the host closes stdin.

    The process exits with its host; nothing is supervised (BLUEPRINT §5.6). A malformed
    line is skipped rather than fatal — a response cannot be formed without an id, and
    killing the server would take down the working tools with it.
    """
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(message, dict):
            continue
        response = handle_message(server, message)
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()
    return 0

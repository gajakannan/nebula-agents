# ADR-007: Dependency-Free Stdio MCP Server With a Read-Only Tool Set

## Status

- [ ] Proposed
- [x] Accepted
- [ ] Superseded
- [ ] Rejected

**Accepted:** 2026-08-29T11:15:45-04:00 by explicit operator approval.

## Context

F0003-S0003 adds six MCP tools — `nebula_session_list`, `nebula_session_status`,
`nebula_gate_status`, `nebula_validator_status`, `nebula_evidence_list`,
`nebula_evidence_show` — so a reviewer in an MCP-capable host can inspect runtime state
without attaching to a terminal. The story is explicit that the surface is read-only and
that "MCP tools inspect runtime state and evidence summaries" rather than becoming a
second orchestration path.

Two things must be settled: how the server is implemented, and how "read-only" is
enforced rather than merely intended.

There is direct precedent in this repository. `scripts/kg/mcp_server.py` already exposes
five knowledge-graph tools over stdio without taking the official MCP SDK as a
dependency, on a deliberate least-infrastructure argument recorded in the KG-MCP plan.

## Decision Drivers

- The story's own edge case: "MCP SDK is unavailable; command reports install guidance
  and CLI status remains available" — the CLI must not depend on the MCP path.
- Read-only must be structurally true, not a code-review promise.
- The framework is tool-agnostic; no host may become a required dependency.
- Existing in-repo precedent is either followed or departed from with a recorded reason.

## Decision

**Implementation.** `nebula-agents mcp serve` implements the MCP stdio protocol directly,
with no third-party dependency, mirroring `scripts/kg/mcp_server.py`. The surface is
small — six tools, JSON in, JSON out — and the protocol subset needed is correspondingly
small. `engine/pyproject.toml` gains no new required dependency, so the CLI is unaffected
when no host is present, and the story's SDK-unavailable edge case becomes unreachable
rather than handled.

**Read-only enforcement.** The guarantee is structural, at two levels:

1. The MCP presentation adapter is constructed with a *query-only* application facade.
   The services that mutate — launch, validator execution, gate decision, transcript
   configuration, artifact indexing, summary generation, proposal generation — are not
   reachable through it. Read-only is a consequence of what was wired in, not a check
   inside each handler.
2. Every tool call still evaluates the default-deny authorization contract with action
   `ReadState`. A tool that somehow attempted a mutating action would be denied.

Adding a mutating MCP tool therefore requires changing the facade the adapter is
constructed with — a visible architectural edit, not a new handler.

**Response shape.** Every response carries `contract_version` and conforms to a committed
schema. Payloads are bounded: list tools page, `nebula_evidence_show` returns the redacted
summary plus retrieval metadata and never raw artifact bytes. Errors are structured
(`error_code`, user-safe message, remediation) and carry no stack traces or paths outside
approved roots.

## Options Considered

1. **Dependency-free stdio + query-only facade:** Selected.
2. **Official MCP SDK:** Rejected for now. It would add a required dependency to a package
   whose primary surface is a CLI, and the protocol subset in use is small. Revisit if the
   tool surface grows or the protocol advances faster than a hand-rolled implementation
   can track; the adapter boundary makes that swap local.
3. **Read-only enforced by per-handler assertions:** Rejected. Correct only while every
   future handler remembers; the facade approach cannot be forgotten.
4. **Read-only enforced only by authorization policy:** Rejected as the sole mechanism. A
   policy misconfiguration would silently widen the surface; defense in depth keeps both.
5. **Reuse `scripts/kg/mcp_server.py` process:** Rejected — see ADR-005. Planning-time
   graph data and runtime state have different lifetimes and redaction rules.
6. **HTTP/SSE transport:** Rejected. A port contradicts the local trust boundary
   (ADR-005).

## Pros / Cons

**Dependency-free stdio**
- Pro: no dependency added; CLI unaffected by MCP concerns.
- Pro: matches existing in-repo precedent, so operators see one pattern.
- Pro: the host owns process lifetime; nothing to supervise.
- Con: protocol changes must be tracked by hand.
- Con: hand-rolled framing needs its own conformance tests.

**Query-only facade**
- Pro: the guarantee survives careless future edits.
- Con: requires the application layer to expose a genuine read/write split, which is
  additional structure F0001 did not need.

## Consequences

- The application layer must split query services from command services; this split is a
  Phase B interface commitment, not an implementation detail.
- Conformance tests must cover framing, unknown-method, malformed-input, and
  bounded-output behavior, since no SDK supplies them.
- Adding any mutating tool is an ADR-level change.
- Tool names are a public contract; renaming one breaks host configurations.
- F0002 may reuse the adapter by supplying its own query facade.

## Security & Compliance Notes

- Tools run as the spawning host's OS user; no privilege boundary is crossed and none is
  invented.
- `nebula_evidence_show` refuses content when `redaction_status` is not `Pass`, reporting
  redaction failure instead (S0003 edge case).
- Unreadable runtime directories yield a structured permission error without stack traces.
- Responses are bounded so a host cannot be flooded by a large transcript.

## References

- [ADR-005: control-plane packaging](./ADR-005-f0003-control-plane-packaging.md)
- [ADR-006: artifact identity](./ADR-006-f0003-artifact-identity-and-index.md)
- [Solution patterns](../SOLUTION-PATTERNS.md)
- [F0003 runtime contract](../f0003-runtime-contract.md)

## Follow-up Actions

- [ ] At feature G0, pin the MCP protocol revision targeted and its conformance fixtures.
- [ ] Record the query/command service split in the module map.
- [x] Accepted through the Phase B operator approval gate.

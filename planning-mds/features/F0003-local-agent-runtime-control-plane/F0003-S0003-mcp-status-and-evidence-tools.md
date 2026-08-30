# F0003-S0003 - MCP Status and Evidence Tools

## Story Header

**Story ID:** F0003-S0003
**Feature:** F0003 - Local Agent Runtime Control Plane
**Title:** MCP status and evidence tools
**Priority:** High
**Phase:** Platform Hardening

## User Story

**As a** reviewer using an AI coding tool
**I want** read-only MCP tools for Nebula session, gate, validator, and evidence status
**So that** I can inspect runtime state without attaching to the terminal or manually opening artifact paths.

## Context & Background

The framework is tool-agnostic, but MCP-compatible hosts can benefit from a narrow status surface. The first MCP tools should be read-only and should expose existing runtime state rather than becoming another orchestration path.

## Acceptance Criteria

**Happy Path:**
- **Given** the local runtime registry contains at least one run
- **When** an MCP host calls `nebula_session_list`
- **Then** the tool returns active and recent run IDs with sanitized status
- **When** the host calls `nebula_session_status` with a run ID
- **Then** the tool returns provider, action, feature, gate status, validator status, evidence summary, and attach guidance when allowed
- **When** the host calls `nebula_evidence_list`
- **Then** the tool returns artifact IDs, kinds, summaries, freshness, and retrieval availability
- **When** the host calls `nebula_evidence_show` with an artifact ID
- **Then** the tool returns the redacted summary and local retrieval metadata, not raw secret-bearing content

**Alternative Flows / Edge Cases:**
- MCP SDK is unavailable; command reports install guidance and CLI status remains available.
- Unknown run ID returns a structured not-found error.
- Artifact exists but fails redaction validation; tool refuses content and reports redaction failure.
- Runtime directory is unreadable; tool returns a permission error without stack traces.
- MCP server is invoked outside a workspace; tool returns setup guidance.

## Interaction Contract

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| MCP `nebula_session_list` | Query sessions | No editable state | None | Reads runtime registry and live reconciliation | Reviewer, Local Operator |
| MCP `nebula_session_status` | Query one run | No editable state | None | Reads persisted status and artifact index | Reviewer, Local Operator |
| MCP `nebula_gate_status` | Query gate state | No editable state | None | Reads gate decision records | Reviewer, Local Operator |
| MCP `nebula_validator_status` | Query validators | No editable state | None | Reads latest validator artifacts | Reviewer, Local Operator |
| MCP `nebula_evidence_list` | Query artifacts | No editable state | None | Reads artifact index | Reviewer, Local Operator |
| MCP `nebula_evidence_show` | Query redacted artifact summary | No editable state | None | Reads summary and retrieval metadata | Reviewer, Local Operator |

Required checks for mutation stories:
- [ ] All F0003 MCP tools are read-only.
- [ ] Tool responses are bounded and machine-readable.
- [ ] Errors are structured and do not leak credentials or stack traces.
- [ ] Tests cover success, not found, unreadable runtime, missing MCP SDK, and redaction failure.

## Data Requirements

**Required Fields:**
- `tool_name`: MCP tool identifier.
- `run_id`: Run being inspected.
- `gate_status`: Current gate state when available.
- `validator_status`: Latest validator state.
- `artifact_id`: Evidence artifact identifier.
- `summary_text`: Redacted summary text.
- `retrieval_available`: Boolean.

**Optional Fields:**
- `attach_guidance`: Local attach command or explanation when unavailable.
- `freshness_status`: Fresh, stale, missing, or unknown.
- `error_code`: Structured error code for failures.

**Validation Rules:**
- MCP tool names must be stable and documented.
- Raw artifacts are not returned unless a future explicitly approved tool allows it.
- Response payloads must include schema version.
- Unknown run or artifact IDs return structured errors.

## Role-Based Visibility

**Roles that can use MCP status tools:**
- Reviewer - Can inspect status and redacted evidence.
- Local Operator - Can inspect all status visible to local user.
- Architect - Can inspect schema and contract compatibility.

**Data Visibility:**
- InternalOnly content: Local retrieval paths when policy allows.
- ExternalVisible content: Redacted summaries, status, and freshness markers.

## Non-Functional Expectations

- Performance: Common MCP status calls complete within 1 second.
- Reliability: Tool responses are deterministic for fixture-backed runtime registries.
- Security: MCP tools default to read-only behavior and strict redaction.

## Dependencies

**Depends On:**
- F0003-S0001 runtime status command.
- F0003-S0004 artifact index.

**Related Stories:**
- F0003-S0005 summaries provide the content exposed by evidence tools.

## Business Rules

1. Read-only first: MCP tools inspect runtime state and evidence summaries.
2. Bounded output: Tools must avoid returning unbounded transcripts or logs.
3. Artifact traceability: Every evidence response must preserve artifact ID and retrieval metadata.

## Out of Scope

- MCP mutation tools for gate approval.
- Remote MCP service hosting.
- Raw transcript streaming through MCP.

## UI/UX Notes

- Command surfaces involved: `mcp serve` plus host-side MCP configuration; `status` covers the same state from the CLI.
- Key interactions: Query session list, inspect status, inspect evidence summary.

## Questions & Assumptions

**Open Questions:**
- [x] **Resolved 2026-08-29 — documented manual host configuration.** There is no
  `mcp install` subcommand. Writing a host's configuration file would put Nebula inside a
  trust boundary it does not own: that file governs which processes the host spawns, it
  often sits alongside credentials for other servers, and its format is the vendor's to
  change. An installer would have to locate it by guesswork, merge without clobbering
  unrelated entries, and track each host's schema. See
  [`docs/mcp-host-configuration.md`](../../../docs/mcp-host-configuration.md).

**Assumptions (to be validated):**
- Read-only MCP inspection is enough for the first runtime integration.

## Definition of Done

- [ ] Acceptance criteria met
- [ ] Edge cases handled
- [ ] Permissions enforced through local runtime read policies
- [ ] Audit/timeline logged as N/A for read-only calls, with optional access metrics only
- [ ] Tests cover MCP tool contracts and errors
- [ ] Documentation updated
- [ ] Story filename matches `Story ID` prefix
- [ ] Story index regenerated or updated

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

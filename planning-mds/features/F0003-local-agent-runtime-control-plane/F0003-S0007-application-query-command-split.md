# F0003-S0007 - Application Query/Command Service Split

## Story Header

**Story ID:** F0003-S0007
**Feature:** F0003 - Local Agent Runtime Control Plane
**Title:** Application query/command service split
**Priority:** Critical
**Phase:** Platform Hardening

## User Story

**As a** platform maintainer
**I want** the application layer split into query services and command services behind separate facades
**So that** the read-only guarantee of the MCP surface is structural rather than a promise each future handler has to remember.

## Context & Background

ADR-007 makes the MCP surface read-only by constructing its adapter with a query-only application facade, so no mutating service is reachable through it. BLUEPRINT §5.1 records that split as a Phase B interface commitment rather than an implementation detail.

That split does not exist yet. F0001 shipped a single application layer where reads and mutations sit side by side, and it carries 514 passing tests. So the split is a refactor of shipped, covered code — which is exactly why it needs its own story rather than being discovered partway through S0003. Plan-review run `2026-08-19-ec0a97ce` raised this as finding H3: architecturally mandatory, owned by nobody.

This story does the restructuring and nothing else. It adds no behavior, no command, and no tool.

## Acceptance Criteria

**Happy Path:**
- **Given** F0001's application layer with reads and mutations in one surface
- **When** the split is applied
- **Then** every application service is reachable through exactly one of two facades: a query facade or a command facade
- **Then** the query facade exposes no operation that writes to the filesystem, appends a runtime event, or changes gate, run, transcript, artifact, or proposal state
- **Then** the command facade exposes the mutating operations, and every one of them continues to evaluate authorization exactly as before
- **Then** the audit/timeline stream is byte-identical for an identical operation sequence: every mutating operation appends the same runtime event type and payload shape as before the split, and query-facade operations append no audit event at all
- **Then** the existing 514 engine tests pass unchanged, with no test rewritten to accommodate the new structure
- **Then** a test asserts the query facade's surface is mutation-free by construction, so adding a mutating method to it fails the build

**Alternative Flows / Edge Cases:**
- An operation both reads and writes (validator execution records its result): it belongs to the command facade, and the query facade exposes only its persisted result.
- A read that lazily initializes state (first-run directory creation) must move that initialization to the command path or drop it; a query must not create.
- Reconciliation reads live tmux state before reporting: reconciliation that persists a corrected status is a command; a probe that only reports is a query.
- A caller needing both facades receives both explicitly; neither facade may reach the other.
- Coverage falls below the configured threshold after the move: the split is incomplete, not the threshold wrong.

## Interaction Contract

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| Query facade | Read run, gate, validator, evidence, metric state | No editable state | None by construction | Reads persisted records only | All roles permitted to read |
| Command facade | Launch, validate, decide gate, configure transcript, index, summarize, draft, decide | Per operation | Writes records and appends runtime events | Existing F0001 persistence contract, unchanged | Per-operation authorization, unchanged |

Required checks for mutation stories:
- [ ] No query-facade operation writes to disk or appends a runtime event.
- [ ] Every command-facade operation evaluates authorization as it did before the split.
- [ ] The existing engine test suite passes without modification.
- [ ] Tests cover facade separation, the read-then-write operations, and the lazy-initialization edge case.

## Data Requirements

**Required Fields:**
- No new persisted fields. This story changes structure, not data.

**Validation Rules:**
- The query facade's public surface contains no operation whose implementation reaches a write path.
- Authorization action mapping is unchanged for every existing operation.
- No record schema changes.

## Role-Based Visibility

**Roles that depend on this split:**
- Platform Maintainer - Owns the refactor and its regression boundary.
- Architect - Approves the facade boundary as the interface commitment ADR-007 relies on.
- Security Reviewer - Confirms the read-only guarantee holds structurally, not by convention.

**Data Visibility:**
- InternalOnly content: module layout and facade composition.
- ExternalVisible content: none; this story adds no user-visible surface.

## Non-Functional Expectations

- Performance: no measurable regression in `sessions`, `status`, or `evidence list` latency.
- Reliability: behavior is unchanged; the 514 existing engine tests are the regression boundary.
- Security: the read-only guarantee moves from convention to construction, so a future mutating MCP tool requires an architectural edit rather than a handler edit.
- Authorization: unchanged for every existing operation. This story adds no action and grants nothing new.
- Audit/timeline: every mutating operation appends the same runtime event, with the same event type and payload shape, as it did before the split. The audit stream is part of the regression boundary — a diff of events emitted by an identical operation sequence across the refactor must be empty. Query-facade operations append no event, which is the same as today: reads never did.

## Dependencies

**Depends On:**
- F0001 application layer as shipped.

**Related Stories:**
- F0003-S0003 - The MCP adapter is constructed with the query facade this story creates; S0003 cannot deliver its structural read-only guarantee until this lands.

## Business Rules

1. Structure over convention: read-only must be enforced by what is reachable, not by what a handler remembers to avoid.
2. No behavior change: this story is complete only if it is invisible to every existing test.
3. Separation of grant: a caller receiving the query facade cannot escalate to mutation through it.

## Out of Scope

- New commands, tools, or MCP surfaces.
- Changes to authorization actions or policy.
- Record or schema changes.
- Performance optimization beyond avoiding regression.

## UI/UX Notes

- Command surfaces involved: none. This story has no operator-visible surface.

## Questions & Assumptions

**Open Questions:**
- [ ] Should the facades be separate modules or one module exposing two protocols?

**Assumptions (to be validated):**
- F0001's existing application operations partition cleanly into read and write, with validator execution the only read-then-write case.

## Definition of Done

- [ ] Acceptance criteria met
- [ ] Edge cases handled
- [ ] Permissions enforced unchanged through the command facade
- [ ] Audit/timeline logging unchanged for every mutating operation
- [ ] Tests cover facade separation and prove the query facade is mutation-free
- [ ] Documentation updated
- [ ] Story filename matches `Story ID` prefix
- [ ] Story index regenerated or updated

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

# F0007-S0008 - Shared Policy Consumers and Prose Thinning

## Story Header

**Story ID:** F0007-S0008
**Feature:** F0007 - Spec-Driven Orchestration and Prompt Compilation
**Title:** Shared policy consumers and prose thinning
**Priority:** High
**Phase:** Framework Hardening

## User Story

**As a** role agent and prompt consumer
**I want** policy literals resolved from shared configuration and deterministic procedure removed from prose
**So that** my context is spent on judgment while scripts and validators retain one enforceable answer.

## Context & Background

After generated prompts and validator parity are accepted, this slice consolidates coverage and other
fixed literals, adds vague-language linting, extracts the shared retrieval guard, and thins actions and
skills. It preserves judgment criteria, examples, rationale, classification, and role responsibilities.

## Acceptance Criteria

**Happy Path:**
- **Given** accepted generated prompts and validator parity
- **When** policy consumers and prose surfaces are migrated
- **Then** `coverage_min_pct` resolves from the shared contract in action operations, coverage scripts,
  and `agent-map.yaml`, with no private policy-owned numeric defaults
- **Then** affected action/skill files reference scripts/rule IDs while retaining identified judgment content
- **Then** the fixed procedural content of the feature prompt pair and targeted skills falls at least 40%

**Edge Cases / Rejected Inputs:**
- A private threshold literal in an owned consumer fails the inverse regression audit.
- A removed review criterion, rationale, teaching example, or role responsibility fails the semantic checklist.
- `lint-vague-language.py` reports exact lines and allows documented exceptions; it never rewrites content silently.
- A symbolic consumer that cannot resolve a shared value is rejected rather than using a hidden fallback.

## Data Requirements

- Shared values and symbolic references, including `coverage_min_pct`.
- Prose disposition inventory: move, retain, generate, or delete with rationale.
- Before/after line and fixed-procedure measurements.
- Vague-language finding: path, line, term, suggested correction, exception reference.

## Role-Based Visibility

- Role owners approve removal/retention in their skill.
- Maintainers update shared policy; consumers read symbolic values.
- The linter reports findings but is not authorized to mutate planning or architecture documents.
- Code Reviewer verifies no hidden fallback or duplicated policy remains.

## Non-Functional Expectations

- Symbol resolution is deterministic and adds negligible command startup overhead.
- Skills remain under the regression line limit.
- Extracted shared guidance uses stable links and remains available to all affected roles.
- Prose-thinning audit is reproducible and attached to story evidence.

## Dependencies

**Depends On:** F0007-S0006 and F0007-S0007.

**Related Stories:** S0009 validates the thin surfaces in a real pilot.

## Business Rules

1. Fixed policy belongs in spec/config; judgment belongs in prose.
2. No policy consumer substitutes an undocumented fallback.
3. Free-text examples containing numbers are allowed only when not normative policy.

## Out of Scope

- Rewriting editorial voice guidance in `blog` or `document`.
- Changing the coverage minimum itself.

## Questions & Assumptions

**Open Questions:**
- [ ] Decide whether `agent-map.yaml` uses a symbolic field or a generated resolved value plus drift check.

**Assumptions:**
- Rule IDs and shared document links provide enough local context after paraphrased validator sections are removed.

## Definition of Done

- [ ] Shared policy consumer path implemented and private defaults removed.
- [ ] Retrieval guard extracted and all role links validated.
- [ ] Vague-language linter implemented with exception support.
- [ ] Action/skill disposition inventory completed and approved by role owners.
- [ ] Context reduction target measured without judgment loss.
- [ ] Inverse literal and skill regression gates pass.

## Review Provenance

Story-level signoff is recorded in the parent `STATUS.md`.

# F0004-S0001 - Strategy Playbook Artifact and Entry Schema

## Story Header

**Story ID:** F0004-S0001
**Feature:** F0004 - Reflective Learning Loop and Strategy Playbook
**Title:** Strategy playbook artifact and entry schema
**Priority:** Critical
**Phase:** Context Engineering

## User Story

**As a** framework maintainer
**I want** a validated Strategy Playbook artifact with a strict per-entry schema and a framework-vs-product scope split
**So that** every learned strategy has a stable shape, provenance, and home before any action is allowed to write one.

## Context & Background

The loop needs a destination before it needs a writer. This story defines the `LEARNINGS.md` artifact, its per-entry schema, the scope split, and the `validate-learnings.py` checker. It deliberately keeps the playbook separate from `SKILL.md`: the skill stays the static role contract; the playbook holds mutable, curated strategy. No reflection or curation behavior is in scope here — only the artifact and its validator.

## Acceptance Criteria

**Happy Path:**
- **Given** the playbook schema is defined
- **When** a maintainer adds a well-formed entry to `agents/<role>/LEARNINGS.md`
- **Then** the entry carries `strategy_id`, `scope`, `role`, `trigger`, `strategy`, `provenance`, `status`, `supersedes`, `used_count`, and `success_count`
- **Then** `validate-learnings.py` exits 0 and reports the entry as valid

**Alternative Flows / Edge Cases:**
- Duplicate `strategy_id` within a file -> validator reports a conflict and exits non-zero (rejected).
- `product`-scope entry placed in an `agents/**` file -> validator reports a scope violation (forbidden) and exits non-zero.
- Missing required field (e.g., empty `trigger` on an `active` entry) -> validator error.
- Illegal `status` or `scope` value -> validator error with the allowed set.
- `supersedes` points to a non-existent `strategy_id` -> validator error.

## Data Requirements

**Required Fields:**
- `strategy_id`: `LRN-<role>-<NNNN>`, unique per file, never reused.
- `scope`: `framework` or `product`.
- `role`: Owning role slug or `cross`.
- `trigger`: Selection condition (task/phase/keywords).
- `strategy`: Imperative, generalizable lesson text.
- `provenance`: Originating run-id(s), action, gate outcome.
- `status`: `candidate` | `active` | `superseded` | `retired`.
- `supersedes`: Prior `strategy_id` or `none`.
- `used_count`, `success_count`: Non-negative integers.

**Optional Fields:**
- `created`, `last_used`: ISO dates.
- `tags`: Free-form selection hints.

**Validation Rules:**
- IDs unique within a file; retired IDs are not reissued.
- `framework`-scope files contain only `framework` entries; `product`-scope only `product`.
- `active` entries require non-empty `trigger`, `strategy`, and at least one provenance run-id.

## Role-Based Visibility

**Roles that can author or validate the artifact:**
- Local Operator - Can edit playbook files locally and run the validator.
- Architect - Approves the schema and scope policy.
- Role Agents - Read-only consumers; never edit the artifact.

**Data Visibility:**
- InternalOnly content: provenance run-ids and local evidence paths.
- ExternalVisible content: strategy text and trigger (must remain domain-neutral in framework scope).

## Non-Functional Expectations

- Performance: `validate-learnings.py` completes in under 2s for a 200-entry playbook.
- Security: validator never emits credential-bearing provenance; authorization to edit framework-scope files follows the same boundary as other `agents/**` changes.
- Reliability: validation is deterministic and platform-independent (utf-8 safe), matching existing framework validators.

## Dependencies

**Depends On:**
- None (foundational story for F0004).

**Related Stories:**
- F0004-S0006 - Genericness gate consumes this schema for framework-scope entries.
- F0004-S0004 - Curation lifecycle mutates entries defined here.

## Business Rules

1. Playbook is not a skill: `LEARNINGS.md` never replaces or edits `SKILL.md`.
2. Scope is physical: framework strategies live in `agents/**`; product strategies live under `{NEBULA_PRODUCT_ROOT}/planning-mds/learnings/`.
3. Stable identity: a `strategy_id` is permanent and is retired, never reused.

## Out of Scope

- Reflection, curation, selection, or counter mutation behavior (later stories).
- Genericness enforcement wiring (F0004-S0006).
- Any change to `SKILL.md` files or `agent-map.yaml`.

## UI/UX Notes

- No UI. Artifact is a markdown file; the validator is a CLI script consistent with existing framework validators.

## Questions & Assumptions

**Open Questions:**
- [ ] Should each entry's metadata be a fenced block or a compact table for best prompt-render compression during selection?

**Assumptions (to be validated):**
- A single `LEARNINGS.md` per role is sufficient; no per-action sharding needed at expected sizes.

## Definition of Done

- [ ] Acceptance criteria met
- [ ] Edge cases handled (duplicate id, scope violation, missing field, bad status, dangling supersedes)
- [ ] `validate-learnings.py` implemented with non-zero exit on any error
- [ ] Permissions/authorization for editing framework-scope files documented
- [ ] Schema documented in the feature assembly plan and GETTING-STARTED
- [ ] Tests cover valid entry, duplicate id, scope violation, illegal status, dangling supersedes
- [ ] Story filename matches `Story ID` prefix
- [ ] Story index regenerated or updated

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

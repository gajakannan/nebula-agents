# F0007-S0001 - Versioned Action Policy and Schema

## Story Header

**Story ID:** F0007-S0001
**Feature:** F0007 - Spec-Driven Orchestration and Prompt Compilation
**Title:** Versioned action policy and schema
**Priority:** Critical
**Phase:** Framework Hardening

## User Story

**As a** framework maintainer
**I want** action policy represented by a validated active specification and immutable historical bundles
**So that** deterministic rules have one declaration while evidence created under earlier contracts keeps its original meaning.

## Context & Background

This foundational slice defines policy identity, active and historical layout, action/spec shapes,
typed operations, placeholder rules, and manifest-version resolution. It does not switch any live
prompt or validator to the new source.

## Acceptance Criteria

**Happy Path:**
- **Given** valid `_contract.yaml`, action specs, and resolved historical bundles
- **When** `validate_action_specs.py` runs
- **Then** it exits 0 and reports versions, actions, gates, and shared values in deterministic order
- **Then** a new manifest resolver returns the exact bundle named by `contract_version`
- **Then** publishing or selecting a policy version emits an audit/timeline record naming the version
  and selection source

**Edge Cases / Rejected Inputs:**
- A string-form executable command, unknown placeholder, duplicate gate/checkpoint ID, undeclared
  mutation, or missing checkpoint pre/postcondition is rejected with a path-specific error.
- Duplicate or non-monotonic policy versions are rejected.
- An unknown manifest version is rejected; a legacy manifest maps to the newest eligible bundle by
  effective date and is never modified.
- Path placeholders resolving outside the framework/product roots are forbidden.

## Data Requirements

- Active contract: version, shared values, historical bundle directory.
- Historical bundle: version, effective date, fully resolved shared policy and action matrices.
- Action: identity, scope, inputs, ownership, gates, stop conditions, judgment/notes.
- Operation: argv, cwd, timeout, expected artifacts, mutation classes.
- Manifest lookup result: selected version, selection source (`explicit` or `legacy-date`), diagnostics.

## Role-Based Visibility

- Maintainer and Architect may author/review active policy.
- Validators and generators read active and historical bundles.
- Published historical bundles are read-only; no role is authorized to edit one in place.
- Product agents receive resolved policy output but cannot write framework policy.

## Non-Functional Expectations

- Deterministic validation output for identical files.
- Policy load and validation completes in under 250 ms on repository fixtures.
- YAML is loaded safely; schema processing performs no code execution.
- Version selection and validation results are suitable for audit evidence.

## Dependencies

**Depends On:** None.

**Related Stories:** S0002 consumes the schema for independent conformance; all later stories consume
the policy loader.

## Business Rules

1. Published history is immutable and fully resolved.
2. New runs carry both version and effective date.
3. Executable policy is typed data, never shell text.
4. Free-text judgment fields are presented but never executed.

## Out of Scope

- Prompt generation, gate execution, validator cutover, and prose deletion.
- Editing existing archived evidence manifests.

## Questions & Assumptions

**Open Questions:**
- [ ] Choose full multi-action bundles or per-action snapshots plus an immutable index.

**Assumptions:**
- Date-form version identifiers remain adequate until a same-day compatibility break is needed; the
  schema permits an explicit revision suffix if required.

## Definition of Done

- [ ] Active and historical layout documented and implemented.
- [ ] JSON Schema and semantic validator implemented.
- [ ] Legacy-date and explicit-version selection tested.
- [ ] Invalid operation, placeholder, version, and path cases tested.
- [ ] No current prompt or validator source removed.
- [ ] Validation report records an auditable version decision.
- [ ] Story index and parent status remain synchronized.

## Review Provenance

Story-level signoff is recorded in the parent `STATUS.md`.

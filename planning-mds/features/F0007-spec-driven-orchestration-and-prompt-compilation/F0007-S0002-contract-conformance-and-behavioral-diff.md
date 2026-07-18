# F0007-S0002 - Contract Conformance and Behavioral Diff

## Story Header

**Story ID:** F0007-S0002
**Feature:** F0007 - Spec-Driven Orchestration and Prompt Compilation
**Title:** Contract conformance and behavioral diff
**Priority:** Critical
**Phase:** Framework Hardening

## User Story

**As a** contract reviewer
**I want** policy meaning checked independently and changes summarized behaviorally
**So that** generated surfaces cannot all agree on a weakened or accidental contract change.

## Context & Background

Schema validity and generated drift only prove internal consistency. This slice adds historical golden
fixtures, non-generated semantic invariants, and a deterministic contract diff that classifies policy
changes before any consumer switches sources.

## Acceptance Criteria

**Happy Path:**
- **Given** baseline evidence fixtures for every current effective-date cutover
- **When** contract conformance runs against unchanged policy
- **Then** every fixture retains its recorded verdict and independent invariant checks pass
- **Then** `--contract-diff BASE..HEAD` reports gate, artifact, operation, threshold, stop-condition,
  and compatibility changes in stable order
- **Then** any approved expected-verdict update carries an audit/timeline entry with the new policy
  version, reviewer, rationale, and affected fixtures

**Edge Cases / Rejected Inputs:**
- Removing a required G7 artifact causes an independent conformance failure even if generated output
  matches the edited spec.
- Changing a historical fixture's expected verdict without a new version and review note is rejected.
- Reordering YAML without changing behavior produces an empty behavioral diff.
- A compatibility-breaking change mislabeled non-breaking is rejected by policy rules.

## Data Requirements

- Golden fixture index: fixture ID, policy version/date, action/stage, expected exit/verdict, rule IDs.
- Independent invariants: canonical scope, forbidden run-ID schemes, gate/artifact relations,
  historical immutability, monotonic dates, typed execution.
- Behavioral diff record: base/head, additions, removals, changes, compatibility class.

## Role-Based Visibility

- QE authors expected historical outcomes; PM and Architect approve intentional changes.
- Code Reviewer reads the behavioral diff and blocks unexplained weakening.
- Generators and validators cannot rewrite fixture expectations.
- Updating expected verdicts requires the same authorization as publishing a new policy version.

## Non-Functional Expectations

- Diff output is byte-stable and suitable for CI artifacts.
- Fixture failures identify policy path, fixture, old result, and new result.
- Conformance is read-only and leaves an audit report without mutating policy or evidence.

## Dependencies

**Depends On:** F0007-S0001.

**Related Stories:** S0006 retains prompt invariants; S0007 uses the historical matrix for dual-read.

## Business Rules

1. Generated equality is not proof of correctness.
2. Historical expectations are independently authored.
3. Every compatibility-impacting change creates a new policy version.

## Out of Scope

- Running gates or generating prompts.
- Deciding product-specific evidence waivers.

## Questions & Assumptions

**Open Questions:**
- [x] Decide whether the behavioral diff is Markdown, JSON, or both; CI requires a machine-readable form.
  **Resolved:** both — `validate_action_specs.py --contract-diff` emits JSON by default (the
  machine-readable CI form); `--format md` renders a human-review table.

**Assumptions:**
- Existing validator tests can seed most historical fixtures without copying entire product repositories.

## Definition of Done

- [x] Fixture index covers every existing effective-date cutover. (`conformance-baseline.yaml`,
  5 cutovers 2026-05-19..2026-07-11 with expected verdict, requirements, artifacts, model hash)
- [x] Independent invariants fail on seeded weakening examples. (`contract-conformance.py`;
  `test_contract_conformance.py` — removing G7 artifact fails while the spec stays schema-valid)
- [x] Behavioral diff distinguishes semantic changes from YAML reorder.
  (`validate_action_specs.py --contract-diff`; `test_contract_diff.py` reorder → identical)
- [x] Compatibility classification and authorization rules documented. (diff `compatibility_class`
  + `behavioral_change_without_version_bump` / history-immutability rules; baseline audit-log
  authorization in `conformance-baseline.yaml`)
- [x] CI-ready machine-readable output implemented. (`--contract-diff` JSON default; `--json` conformance)
- [x] Audit report contains no secret-bearing fixture content. (findings expose rule/path/message only;
  test asserts the shape; conformance is read-only)

## Review Provenance

Story-level signoff is recorded in the parent `STATUS.md`.

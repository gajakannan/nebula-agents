# F0007-S0005 - Gate Driver, Durable Checkpoints, and Severity Policy

## Story Header

**Story ID:** F0007-S0005
**Feature:** F0007 - Spec-Driven Orchestration and Prompt Compilation
**Title:** Gate driver, durable checkpoints, and severity policy
**Priority:** Critical
**Phase:** Framework Hardening

## User Story

**As a** governed feature operator
**I want** action gates sequenced by a durable driver with explicit manual attestations and central severity arithmetic
**So that** the most consequential ordering and approval decisions cannot be skipped or inconsistently calculated.

## Context & Background

`run-gate.py` resolves an action stage and delegates typed operations to the shared runtime. Manual
steps pause a durable journal. `gate_policy.py` calculates allowed outcomes after agents classify
findings; it does not classify findings itself.

## Acceptance Criteria

**Happy Path:**
- **Given** an initialized run and valid stage
- **When** `run-gate.py` executes the stage
- **Then** operations run in declared order, stop on first failure, and update command, lifecycle,
  and gate-state audit records atomically
- **Then** a manual checkpoint resumes only after an authorized evidence attestation is verified and hashed
- **Then** `gate_policy.py` returns the expected status/options for every existing severity branch

**Edge Cases / Rejected Inputs:**
- `--from` across an unattested checkpoint is rejected.
- Missing/changed checkpoint output, wrong run/stage, stale journal version, or concurrent resume is rejected.
- Re-running a completed idempotent stage reports completion; a non-idempotent replay requires explicit authorization.
- Critical/high count contradictions or negative values are rejected by severity policy.

## Data Requirements

- Gate state: run, action, version, stage, completed operations, pending checkpoint, attestations.
- Attestation: checkpoint ID, actor/role, timestamp, evidence paths, hashes, note.
- Severity input: profile and per-domain critical/high counts.
- Severity output: status, allowed options, approval enabled, justification requirement.

## Role-Based Visibility

- Only the checkpoint role or operator-authorized delegate may attest a manual step.
- Agents classify findings; the policy script only performs arithmetic.
- Evidence reviewers read the journal and hashes; unauthorized users cannot rewrite completed entries.

## Non-Functional Expectations

- Journal writes use a per-run lock and atomic replacement.
- Crash recovery resumes from the last committed operation without duplicating side effects.
- Structured verdict includes failed step and log references.
- Severity tables are exhaustive and table-tested.

## Dependencies

**Depends On:** F0007-S0003 and F0007-S0004.

**Related Stories:** S0006 renders driver instructions; S0007 validates driver-emitted evidence.

## Business Rules

1. Manual checkpoint evidence is mandatory, not advisory.
2. Pass/fail of invoked validators comes from their exit codes.
3. Procedure integrity belongs to the driver; evidence acceptance belongs to validators.

## Out of Scope

- Human review classification and product-specific remediation.
- Prompt compilation or deletion of existing severity prose.

## Questions & Assumptions

**Open Questions:**
- [x] Define the authorization representation for delegated checkpoint actors in local-only runs.
  **Resolved:** an attestation records `actor` + `role` (free-form, operator-supplied) alongside the
  hashed evidence and timestamp; local-only runs trust the operator identity and the per-run lock
  rather than cryptographic signing (per the story assumption). The role names the authorized
  checkpoint owner; delegation is expressed by recording the delegate as `actor` with the owning
  `role`. Content signing is deferred (not required initially).

**Assumptions:**
- File hashes plus durable paths are sufficient checkpoint evidence; content signing is not required initially.

## Definition of Done

- [x] Driver dry-run/list/run/resume interfaces implemented. (`run-gate.py` — `--list`, `--dry-run`,
  run a stage, `--from`, `--attest-checkpoint`, `--force`)
- [x] Checkpoint skip, tamper, concurrent resume, crash recovery, and replay tests pass.
  (`test_run_gate.py` — `--from` past an unattested checkpoint rejected; tampered/missing evidence
  rejected; per-run lock → concurrent conflict; resume does not re-run completed ops; `--force` replay)
- [x] All existing severity branches reproduced by table-driven tests. (`gate_policy.py`;
  `test_gate_policy.py` — standard + review-family (plan/feature) + none, negatives/booleans rejected)
- [x] Journal and logs provide complete audit/timeline records. (atomic `gate-state.json` journal with
  hashed attestations; `lifecycle-gates.log` blocks; `commands.log` via the shared runtime)
- [x] Driver/validator responsibility boundary documented. (module docstring + this story: the driver
  owns procedure integrity; pass/fail is each validator's own exit code)

## Review Provenance

Story-level signoff is recorded in the parent `STATUS.md`.

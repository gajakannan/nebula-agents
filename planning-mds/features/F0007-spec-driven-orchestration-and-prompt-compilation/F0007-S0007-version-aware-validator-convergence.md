# F0007-S0007 - Version-Aware Validator Convergence

## Story Header

**Story ID:** F0007-S0007
**Feature:** F0007 - Spec-Driven Orchestration and Prompt Compilation
**Title:** Version-aware validator convergence
**Priority:** Critical
**Phase:** Framework Hardening

## User Story

**As a** maintainer of evidence compatibility
**I want** validators to load the policy version that created each run and prove parity before removing private matrices
**So that** specification convergence does not change historical or current acceptance behavior.

## Context & Background

The evidence validator currently owns several date-sensitive rules and private stage/artifact maps.
This slice introduces version selection and dual-read comparison. Existing constants remain active
until the complete current/historical matrix reports zero disagreement.

## Acceptance Criteria

**Happy Path:**
- **Given** current and historical evidence fixtures
- **When** the validator runs in dual-read mode
- **Then** it records the selected policy version, evaluates both legacy and policy-derived matrices,
  and reports zero disagreement with unchanged rule IDs and exit codes
- **Then** new manifests require `contract_version`, while legacy manifests continue through date mapping
- **Then** removal of a private matrix requires an audit/timeline decision citing the zero-disagreement report

**Edge Cases / Rejected Inputs:**
- Unknown version, unsupported legacy date, malformed version field, or version/date contradiction is rejected with a named rule.
- Any legacy/policy disagreement blocks removal of private constants and emits a machine-readable diff.
- An active-policy update cannot change a historical fixture verdict.
- Unauthorized mutation of an evidence manifest during compatibility resolution is forbidden.

## Data Requirements

- Manifest adds `contract_version` for newly initialized runs.
- Validation result includes selected version, selection source, dual-read state, and disagreements.
- Historical test matrix covers stages G0-G8/closeout and conditional artifacts/roles at policy cutovers.

## Role-Based Visibility

- Validators read policy/evidence only.
- QE owns parity expectations; Architect approves compatibility mapping; PM approves contract release.
- No role may silence a disagreement by removing a historical fixture without an authorized policy decision.

## Non-Functional Expectations

- Historical fixture validation remains deterministic.
- Dual-read overhead stays below 20% of validator runtime on the fixture suite.
- Machine-readable output remains backward compatible or carries an explicit schema revision.
- Compatibility resolution leaves an audit trail and does not alter evidence.

## Dependencies

**Depends On:** F0007-S0001, F0007-S0002, and F0007-S0005.

**Related Stories:** S0008 removes duplicated prose/constants after parity; S0009 pilots closeout.

## Business Rules

1. Rule IDs remain stable unless a separately reviewed contract version introduces a new rule.
2. Private constants are removed only after zero-disagreement evidence.
3. Version/date conflicts fail closed.

## Out of Scope

- Rewriting old evidence packages.
- Broad validator cleanup unrelated to policy source convergence.

## Questions & Assumptions

**Open Questions:**
- [x] Decide how many releases dual-read remains available as a diagnostic after private constants are removed.
  **Resolved:** keep the dual-read diagnostic (`contract_compat.py`) for at least the next **two**
  published contract versions after removal, then re-evaluate. It is read-only and cheap, and it gives
  a fallback comparison during the first releases where policy-derived matrices are authoritative.

**Assumptions:**
- Existing validator fixtures can be extended to cover all policy cutovers without external product state.

## Definition of Done

- [x] Manifest template and consumer contract document version behavior.
  (`evidence-manifest-template.json` adds `contract_version`; `CONSUMER-CONTRACT.md` documents
  explicit-version + legacy-date resolution and the fail-closed rules)
- [x] Version selection and contradiction rules implemented. (`validate-feature-evidence.py`
  `validate_contract_version_field`: malformed / version-date-conflict / unknown-version, new-field
  guarded so legacy manifests are unaffected; `contract_compat.py` explicit/legacy selection)
- [x] Dual-read matrix is green across stages and historical cutovers.
  (`contract_compat.py --matrix` — zero disagreement across all 5 cutovers × {explicit, legacy-date})
- [x] Disagreement negative tests block constant removal. (`test_contract_compat.py` — a weakened
  bundle produces a machine-readable disagreement)
- [~] Private matrices removed only after recorded parity approval. **Intentionally deferred:** S0007
  keeps the private date constants active and proves parity; the actual removal happens in S0008 after
  a recorded zero-disagreement decision (this DoD item is the guard — it is honored by not removing yet).
- [x] Historical evidence is never modified by validation. (dual-read is read-only; the validator
  change is additive; no evidence or policy is mutated)

## Review Provenance

Story-level signoff is recorded in the parent `STATUS.md`.

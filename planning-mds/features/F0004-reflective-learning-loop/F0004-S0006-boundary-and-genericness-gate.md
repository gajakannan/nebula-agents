# F0004-S0006 - Boundary, Genericness, and Lifecycle-Gate Enforcement

## Story Header

**Story ID:** F0004-S0006
**Feature:** F0004 - Reflective Learning Loop and Strategy Playbook
**Title:** Boundary, genericness, and lifecycle-gate enforcement
**Priority:** High
**Phase:** Context Engineering

## User Story

**As a** framework maintainer
**I want** a lifecycle gate that enforces genericness and scope boundaries on every playbook change
**So that** the learning loop can never smuggle domain-specific lessons into generic agents or place strategy in the wrong scope.

## Context & Background

An adaptive loop is only safe inside this framework if it cannot erode the boundary contract. This story adds a `learnings_governance` gate to `lifecycle-stage.yaml` that runs `validate-learnings.py` and applies `validate-genericness.py` to framework-scope strategy text, plus a scope-placement check. The gate runs in the framework-bootstrap, planning, implementation, and release-readiness stages alongside the existing `boundary_genericness`, `skill_regression`, and `agent_map_schema` gates, so a domain term in a framework strategy fails CI exactly like a domain term anywhere else in `agents/**`.

## Acceptance Criteria

**Happy Path:**
- **Given** the `learnings_governance` gate is wired into `lifecycle-stage.yaml`
- **When** the gate runs against a clean playbook whose entries each sit in their declared scope
- **Then** it validates schema, scope placement, and genericness for framework-scope entries and exits 0

**Alternative Flows / Edge Cases:**
- A framework-scope entry contains a denylisted domain term -> genericness check fails, gate exits non-zero (rejected), naming the entry and term.
- A product-scope entry is found in an `agents/**` file -> scope-placement check fails (forbidden) and exits non-zero.
- A framework strategy references a product path or `{NEBULA_PRODUCT_ROOT}` literal -> flagged as a boundary violation.
- `validate-learnings.py` itself fails (bad schema) -> the governance gate fails without running downstream checks.
- A product playbook absent in a framework-only run -> gate skips product-scope checks cleanly (not an error).

## Data Requirements

**Required Fields:**
- `gate_id`: `learnings_governance`.
- `checked_files`: Playbook files evaluated.
- `genericness_result`, `scope_result`, `schema_result`: Per-check pass/fail.
- `violations`: Entry id + reason for each failure.

**Optional Fields:**
- `glossary_override`: Optional path for additional denylist terms (consistent with `validate-genericness.py`).

**Validation Rules:**
- Genericness is applied only to `framework`-scope text; product scope is exempt from the denylist but still schema-checked.
- The gate is non-advisory: a violation fails the run, matching existing framework gates.
- No credentials or product-domain terms may appear in any framework-scope entry.

## Role-Based Visibility

**Roles that rely on the gate:**
- Local Operator - Sees gate results during `reflect` apply and in CI.
- Architect - Owns the gate policy and approves any threshold changes.
- Security Reviewer - Reviews that provenance redaction and scope isolation hold.

**Data Visibility:**
- InternalOnly content: raw violation paths and matched terms.
- ExternalVisible content: pass/fail summary and remediation guidance.

## Non-Functional Expectations

- Performance: the gate completes within the existing framework-gate time envelope (seconds), reusing current validators.
- Security: the gate is the authorization boundary preventing domain leakage; it must fail closed (any error blocks).
- Reliability: deterministic and platform-independent, consistent with `run-lifecycle-gates.py` behavior.

## Dependencies

**Depends On:**
- F0004-S0001 - Schema and scope definitions.
- F0004-S0003 - The approval gate calls these checks before applying framework-scope operations.

**Related Stories:**
- F0004-S0004 - Curation must not produce entries that would fail this gate.

## Business Rules

1. Same denylist, no exceptions: framework strategies obey the existing genericness contract.
2. Fail closed: any governance error blocks the run; the gate is not advisory.
3. Scope isolation: framework files never hold product strategy and vice versa.

## Out of Scope

- Reflection, curation, and selection mechanics (other stories).
- Changing the existing `boundary_genericness` gate behavior for non-playbook files.
- Product-side lifecycle gates under `{NEBULA_PRODUCT_ROOT}` (product-owned).

## UI/UX Notes

- No UI. Results surface in the curation gate summary and CI gate output, like other framework gates.

## Questions & Assumptions

**Open Questions:**
- [ ] Should product-scope entries get an optional, separate advisory lint without blocking, for consistency hints?

**Assumptions (to be validated):**
- The embedded denylist in `validate-genericness.py` is the right authority for framework-scope strategy text without a new term source.

## Definition of Done

- [ ] Acceptance criteria met
- [ ] Edge cases handled (denylisted term, misplaced scope, product-path reference, schema failure, absent product playbook)
- [ ] `learnings_governance` gate added to all relevant stages in `lifecycle-stage.yaml`
- [ ] Gate composes `validate-learnings.py`, genericness, and scope-placement checks and fails closed
- [ ] Authorization/boundary semantics documented; provenance redaction verified
- [ ] Tests cover clean pass, denylist fail, scope-violation fail, schema fail, and product-absent skip
- [ ] Story filename matches `Story ID` prefix
- [ ] Story index regenerated or updated

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

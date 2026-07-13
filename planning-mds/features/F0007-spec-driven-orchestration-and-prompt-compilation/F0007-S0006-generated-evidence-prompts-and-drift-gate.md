# F0007-S0006 - Generated Evidence Prompts and Drift Gate

## Story Header

**Story ID:** F0007-S0006
**Feature:** F0007 - Spec-Driven Orchestration and Prompt Compilation
**Title:** Generated evidence prompts and drift gate
**Priority:** High
**Phase:** Framework Hardening

## User Story

**As a** framework maintainer
**I want** operator-friendly and automation-safe prompts compiled from the same action policy
**So that** prompt variants stay aligned and fixed procedure avoids manual paraphrase maintenance.

## Context & Background

This slice creates `render-prompts.py`, renderer templates, generated headers, committed output, and
CI drift enforcement. The feature action is the pilot because it carries the most gates and irregular
notes; remaining actions follow after its semantic review.

## Acceptance Criteria

**Happy Path:**
- **Given** valid action policy and renderer templates
- **When** prompts are generated twice
- **Then** both variants are byte-identical between runs, carry generated headers, and encode the
  same scope, operations, artifacts, stop conditions, and rationale
- **Then** `render-prompts.py --check` exits 0 only when committed output matches regenerated output

**Edge Cases / Rejected Inputs:**
- Missing template branches, unknown action scope, unresolved placeholder, or manual edit to generated
  output is rejected.
- A prompt that omits an independently required package reference or includes a forbidden run-ID
  scheme fails semantic validation even if drift is clean.
- Operator-only actions generate only their declared variants; undeclared extra files are rejected.

## Data Requirements

- Renderer input: active action spec, shared/common policy, variant template, judgment notes.
- Generated metadata: source paths, policy version, renderer version, do-not-edit marker.
- Snapshot matrix: action, scope, declared variants, expected sections and independent invariants.

## Role-Based Visibility

- Maintainers edit specs/templates, never generated files directly.
- PM and affected role owners approve semantic equivalence.
- DevOps owns CI drift integration; generated output remains readable to consumers without tooling.
- Unauthorized direct generated-file edits are overwritten and fail audit checks.

## Non-Functional Expectations

- Full regeneration completes in under 10 seconds.
- Stable ordering and whitespace yield reproducible output across supported environments.
- Renderer never evaluates template data as code or shell content.
- CI publishes a concise drift diff for review.

## Dependencies

**Depends On:** F0007-S0001, F0007-S0002, and F0007-S0005.

**Related Stories:** S0008 thins action/skill prose after generation; S0009 activates the full set.

## Business Rules

1. Generated prompts are committed and marked do-not-edit.
2. Drift checks prove reproducibility, not policy correctness.
3. Judgment notes remain human-readable and non-executable.

## Out of Scope

- Switching validators to policy data.
- Removing independent `validate_templates.py` invariants.

## Questions & Assumptions

**Open Questions:**
- [ ] Select Jinja2 or a stdlib renderer based on feature-pair prototype complexity and dependency cost.

**Assumptions:**
- Two renderer templates are clearer than one template with pervasive variant conditionals.

## Definition of Done

- [ ] Feature prompt pair generated and manually accepted for semantic equivalence.
- [ ] Remaining declared variants generated with snapshot coverage.
- [ ] Drift check and independent semantic checks wired to CI.
- [ ] Direct-edit and missing-branch negative tests pass.
- [ ] Generated-file resolution workflow documented for contributors.
- [ ] Semantic review decision appears in audit evidence.

## Review Provenance

Story-level signoff is recorded in the parent `STATUS.md`.

# F0007-S0009 - Governed Rollout and Compatibility Pilot

## Story Header

**Story ID:** F0007-S0009
**Feature:** F0007 - Spec-Driven Orchestration and Prompt Compilation
**Title:** Governed rollout and compatibility pilot
**Priority:** High
**Phase:** Framework Hardening

## User Story

**As a** framework release maintainer
**I want** the spec-driven path piloted, lifecycle-gated, documented, and reversible
**So that** the framework can adopt compiled prompts and scripted procedure without stranding in-flight work or weakening evidence guarantees.

## Context & Background

This final slice wires schema, conformance, and prompt drift into lifecycle/CI; updates contributor
and consumer documentation; runs one newly initialized governed feature end-to-end; and records a
rollback rehearsal. Existing in-flight runs remain on the contract and procedure selected at creation.

## Acceptance Criteria

**Happy Path:**
- **Given** S0001-S0008 are accepted and a new pilot feature is initialized
- **When** the pilot runs through closeout
- **Then** gate operations use `run-gate.py`, other commands use `exec-and-log.py`, checkpoints are
  attested, telemetry is complete, and closeout validation exits 0
- **Then** lifecycle CI blocks schema, conformance, historical, prompt drift, and consumer-literal failures
- **Then** rollback to the previous active policy is rehearsed without editing historical manifests

**Edge Cases / Rejected Inputs:**
- An in-flight run cannot opt into a new contract version between gates.
- A pilot checkpoint failure, prompt drift, validator disagreement, or incomplete command log blocks rollout.
- Removing the old path before parity/pilot approval is unauthorized and rejected.
- Rollback by editing `contract_version` in existing evidence is forbidden.

## Data Requirements

- Pilot identity, policy version, gate results, checkpoint attestations, command/lifecycle logs.
- Lifecycle gate results for schema, conformance, drift, historical matrix, skill/literal regression.
- Rollout decision: approve, hold, or rollback with owner/date/evidence.
- Compatibility and rollback report with changed docs and known residual risks.

## Role-Based Visibility

- Maintainer authorizes pilot activation and final rollout.
- PM owns pilot planning/closeout; Architect approves compatibility; QE verifies results.
- DevOps owns CI enforcement and rollback mechanics; Security reviews execution evidence.
- In-flight product teams may read rollout guidance but cannot change their run's version.

## Non-Functional Expectations

- Lifecycle gates finish within the existing CI budget plus documented prompt/fixture overhead.
- Rollback is configuration/generated-output based and preserves immutable history.
- Release notes identify consumer-visible manifest and execution changes.
- Pilot evidence is durable, redacted, and sufficient for independent review.

## Dependencies

**Depends On:** F0007-S0001 through F0007-S0008.

**Related Stories:** None; this is the feature closeout slice.

## Business Rules

1. No mixed procedure or version inside one run.
2. Rollout requires all phase gates and required role signoffs.
3. Old compatibility support is removed only under a later explicit contract decision.

## Out of Scope

- Converting existing in-flight runs.
- Automatic rollout to downstream product repositories without their own adoption decision.

## Questions & Assumptions

**Open Questions:**
- [x] Select the pilot feature and product root after confirming no active run will overlap migration.
  **Resolved (rehearsal):** the S0009 rehearsal uses a scaffolded fixture product root (the `driver`
  spec) so it overlaps no live run. Selecting the LIVE pilot feature + real product root is left to the
  maintainer at promotion time, after confirming no active run for that feature (the per-feature lock
  and concurrent-run check enforce this at `init-run.py`).

**Assumptions:**
- One representative feature-completion pilot plus the historical fixture suite is sufficient for initial framework adoption.

## Definition of Done

- [x] Lifecycle and CI gates enforced with documented remediation. (`lifecycle-stage.yaml` gates
  `action_spec_schema`, `contract_conformance`, `prompt_drift`; remediation in `rollout-report.md`)
- [x] Consumer contract, contributor guide, action docs, and changelog updated. (`CONSUMER-CONTRACT.md`
  version resolution; `CHANGELOG.md` F0007 entry; `rollout-report.md`. Action-doc *thinning* is the
  S0008 human-gated item, tracked there.)
- [~] Pilot reaches closeout with complete audit/timeline evidence. **Rehearsal** reaches closeout with
  complete telemetry (`test_pilot_end_to_end.py` — commands.log/lifecycle-gates.log/gate-state journal +
  hashed attestation). The **live** product-feature pilot closeout is human-gated and deferred.
- [ ] Independent feature review passes with all required roles represented. **Deferred:** requires real
  Architect/QE/Code-Reviewer/DevOps/Security reviewers — not self-certifiable.
- [x] Rollback rehearsal succeeds without historical mutation. (`test_rollback_preserves_immutable_history`
  + documented procedure in `rollout-report.md`)
- [x] Rollout decision and residual risks recorded in parent status. (`rollout-report.md` §4–§5; STATUS
  overall = rollout HOLD)

**Increment note:** S0009 adopts the CI/lifecycle gates, rehearses the governed run and rollback
end-to-end against a fixture product root, and records the rollout HOLD decision. The live governed
product pilot and the independent all-role feature review remain human-gated.

## Review Provenance

Story-level signoff is recorded in the parent `STATUS.md`.

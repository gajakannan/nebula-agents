# F0003-S0006 - Runtime Metrics and Failure-Learning Review

## Story Header

**Story ID:** F0003-S0006
**Feature:** F0003 - Local Agent Runtime Control Plane
**Title:** Runtime metrics and failure-learning review
**Priority:** Medium
**Phase:** Platform Hardening

## User Story

**As a** framework maintainer
**I want** runtime metrics and human-reviewed learning proposals from failed runs
**So that** recurring stalls, validator failures, evidence gaps, and process mistakes become visible improvements without automatic instruction drift.

## Context & Background

Once runtime status, evidence, and summaries exist, Nebula can compute useful local metrics and identify repeated failure patterns. The important boundary is human control: failed-run analysis may propose process corrections, but it must not rewrite agent instructions or framework contracts automatically.

## Acceptance Criteria

**Happy Path:**
- **Given** a run has status, gate, validator, artifact, and summary records
- **When** the operator runs `nebula-agents metrics --run <run_id>`
- **Then** the output includes run duration, gate wait time, validator pass/fail counts, latest failing validator, transcript health, evidence freshness, artifact counts, and blocked launch counts when relevant
- **When** the operator runs `nebula-agents learn review --run <run_id>`
- **Then** the command generates learning proposals only from failed or incomplete run evidence
- **Then** each proposal includes source artifact IDs, proposed target document, proposed change summary, confidence, and review status
- **Then** proposals require accept, edit, reject, or archive before any document change is made
- **Then** proposal generation and review decisions write audit timeline entries with proposal ID, reviewer role, decision, source artifact IDs, and timestamp

**Alternative Flows / Edge Cases:**
- Run has no failures; learning review reports no proposal generated.
- Evidence is stale or missing; proposal generation is blocked until evidence status is resolved.
- Proposed target document is outside approved paths; proposal is blocked.
- Multiple failures map to the same proposal; proposal groups evidence IDs.
- User rejects a proposal; rejection reason is recorded and proposal is not regenerated unless source evidence changes.

## Interaction Contract

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| CLI `metrics` | Inspect run metrics | No editable state | None | Reads runtime records and summaries | Local Operator, Reviewer |
| CLI `metrics --run <run_id>` | Inspect runtime health | No editable state | None | Recomputed from runtime records and the artifact index | Local Operator, Reviewer |
| CLI `learn review` | Generate proposals | Run ID and optional scope | Writes proposal artifacts in draft state | Learning review shows proposals after restart | Local Operator, Architect |
| CLI `learn decide <proposal-id>` | Accept, edit, reject, archive | Decision, reason, optional patch plan | Appends a decision record and sets `proposal_status`; never opens the target document | Decisions are append-only and linked to evidence IDs | Authorized by `DecideProposal` against the target document: Architect for architecture/process, Security Reviewer for security guidance, PM for planning process |

Required checks for mutation stories:
- [ ] Metrics are derived from runtime records, not free-form prose.
- [ ] Learning proposals link to source artifacts.
- [ ] Proposal targets are restricted to approved framework or product instruction paths.
- [ ] Document mutation requires explicit review acceptance outside proposal generation.
- [ ] Tests cover no-failure runs, failed validators, stale evidence, rejected proposals, and blocked target paths.

## Data Requirements

**Required Fields:**
- `run_id`: Run being measured.
- `metric_name`: Runtime metric key.
- `metric_value`: Numeric or categorical metric value.
- `metric_generated_at`: Timestamp.
- `proposal_id`: Learning proposal identifier.
- `source_artifact_ids`: Evidence supporting the proposal.
- `target_document`: Proposed destination document.
- `proposal_summary`: Short proposed correction.
- `proposal_status`: Draft, Accepted, Edited, Rejected, or Archived.

**Optional Fields:**
- `confidence`: Low, Medium, or High.
- `reviewer`: Person or role that reviewed the proposal.
- `decision_reason`: Reason for accepted or rejected decision.
- `patch_plan`: Approved change plan, not automatically applied by proposal generation.

**Validation Rules:**
- Metrics must be recomputable from runtime state and artifact index.
- Proposals require at least one source artifact ID.
- Proposal targets must be allowlisted.
- Rejected proposals remain rejected until source evidence changes.

## Role-Based Visibility

**Roles that can inspect metrics or proposals:**
- Local Operator - Can inspect metrics and generate draft proposals.
- Reviewer - Can inspect metrics.
- Architect - Can approve architecture or process-targeted proposals.
- Security Reviewer - Must approve proposals targeting security guidance.
- Product Manager - Can approve planning-process proposals.

**Data Visibility:**
- InternalOnly content: Local metrics snapshots and source artifact paths.
- ExternalVisible content: Redacted metric summaries and reviewed proposal summaries.

## Non-Functional Expectations

- Performance: Metrics computation completes within 2 seconds for normal runs.
- Reliability: Metrics are deterministic for the same runtime fixture.
- Security: Learning proposals cannot write files without explicit review workflow.
- Authorization: Proposal review decisions require the reviewer role authorized for the proposed target document.

## Dependencies

**Depends On:**
- F0003-S0004 artifact index.
- F0003-S0005 summaries.

**Related Stories:**
- F0003-S0001 command surface provides metrics and learning commands.

## Business Rules

1. Evidence-backed learning: Every proposal must cite source artifacts.
2. Human approval: Proposal generation never changes instruction files by itself.
3. Repeatable metrics: Runtime metrics must be derived from structured records.

## Out of Scope

- Automatic patch application.
- Hosted analytics.
- Cross-project telemetry upload.
- Model fine-tuning or external analytics pipelines.

## UI/UX Notes

- Command surfaces involved: `metrics`, `learn review`, `learn list`, `learn show`, `learn decide`.
- Key interactions: Inspect metrics, generate proposals, accept/edit/reject/archive proposals.

## Questions & Assumptions

**Open Questions:**
- [ ] Which documents should be in the initial proposal target allowlist?

**Assumptions (to be validated):**
- Failed validators and missing evidence will provide enough signal for first learning proposals.

## Definition of Done

- [ ] Acceptance criteria met
- [ ] Edge cases handled
- [ ] Permissions enforced through proposal target allowlist and review workflow
- [ ] Audit/timeline logged for proposal generation and decisions
- [ ] Tests cover metrics and proposal lifecycle
- [ ] Documentation updated
- [ ] Story filename matches `Story ID` prefix
- [ ] Story index regenerated or updated

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

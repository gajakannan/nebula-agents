# F0001-S0004 - Gate and Validator Dashboard

## Story Header

**Story ID:** F0001-S0004
**Feature:** F0001 - Tmux-Native Agent Cockpit
**Title:** Gate and validator dashboard
**Priority:** High
**Phase:** MVP

## User Story

**As a** product owner reviewing an agent run
**I want** the TUI to show the current gate, required evidence, and validator results before the next stage is allowed
**So that** one-step-at-a-time delivery remains enforceable while the agent stays in an interactive terminal session.

## Context & Background

The evidence-contract prompts include gated stages and user approval moments. The tmux cockpit must make those gates visible without flattening them into a single prompt. This story adds a dashboard that shows the current gate state, evidence readiness, and validation results, then records explicit operator decisions.

## Acceptance Criteria

**Happy Path:**
- **Given** a run registry has an active run and watched evidence artifacts
- **When** the operator opens the gate dashboard
- **Then** the TUI shows current gate, previous gate decision, required evidence files, latest validator result, and next allowed action
- **When** the operator runs story or tracker validation
- **Then** the command output summary, exit code, timestamp, and evidence path are recorded
- **When** the operator approves or holds a gate
- **Then** the decision, reviewer label, reason, and timestamp are appended to the run audit timeline

**Alternative Flows / Edge Cases:**
- Missing required evidence marks the gate as blocked and disables approval.
- Validator exit code nonzero marks the gate as blocked and shows the failing command.
- Unknown gate state is treated as blocked until the operator reconciles the run registry.
- Approval by an unauthorized local role is denied when role restrictions are configured.
- Re-running validation replaces the latest summary while preserving earlier audit entries.

## Interaction Contract

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| Gate Dashboard | Run validator | Validator choice | Writes validator result summary and audit entry | Latest validator row survives TUI restart | Local Operator or Reviewer |
| Gate Dashboard | Approve or hold gate | Decision, reviewer label, reason | Appends gate decision and updates gate state | Gate decision appears after reload and in evidence path | Local Operator; approval disabled when evidence or validation is blocked |

Required checks for mutation stories:
- [x] Render-only behavior cannot satisfy the story.
- [x] Gate decision validates evidence state, validator state, reviewer label, and reason when holding.
- [x] A successful gate decision has audit/timeline evidence.
- [x] Tests prove blocked gates cannot be approved and approved gates survive reload.

## Data Requirements

**Required Fields:**
- `gate_id`: Current lifecycle gate.
- `gate_status`: Pending, Blocked, Approved, Held, or Unknown.
- `required_evidence`: List of artifact paths required for the gate.
- `validator_command`: Command run for the latest validation.
- `validator_exit_code`: Exit code for the latest validation.
- `decision`: Approve or Hold.
- `decision_reason`: Required for Hold; optional for Approve.
- `reviewer_label`: Local reviewer/operator label.

**Optional Fields:**
- `recommendations`: Non-blocking notes from validation or review.
- `next_action_hint`: Suggested next operator action.

**Validation Rules:**
- Gate approval is rejected when required evidence is missing.
- Gate approval is rejected when the latest required validator failed.
- Decision records are append-only and include ISO timestamps.

## Role-Based Visibility

**Roles that can approve or hold gates:**
- Local Operator - Can approve or hold gates for their run.
- Reviewer - Can run validators and hold gates; approval depends on configured local role policy.

**Data Visibility:**
- InternalOnly content: Local evidence paths, validator command details, reviewer label.
- ExternalVisible content: Gate verdict, validation status, and sanitized decision summary.

## Non-Functional Expectations

- Performance: Gate dashboard refreshes within 1 second after watcher updates.
- Security: Authorization checks must prevent configured read-only reviewer roles from approving gates.
- Reliability: Validator execution timeout and cancellation are represented as blocked states with audit entries.

## Dependencies

**Depends On:**
- F0001-S0003 - Gate dashboard reads registry and evidence watcher state.

**Related Stories:**
- F0001-S0006 - Read-only commands expose validator status outside the TUI.
- F0002-S0003 - Future typed gate broker builds on these decision semantics.

## Business Rules

1. Blocked means blocked: The TUI cannot show a next-stage action as available when required evidence or validation is missing.
2. Human approval is explicit: Gate approval must be tied to a local user action and audit entry.
3. Validation is evidence: Validator command, exit code, and output summary are part of the run evidence.

## Out of Scope

- Automatic promotion across gates.
- Remote reviewer identity.
- Pull request status checks.
- Provider SDK approval mediation.

## UI/UX Notes

- Screens involved: Gate dashboard, validator output panel, hold reason prompt.
- Key interactions: Run validation, inspect blocked reason, approve, hold, open evidence path.

## Questions & Assumptions

**Open Questions:**
- [ ] Should gate approval require a freeform reviewer label in local-only mode, or infer the OS username?

**Assumptions (to be validated):**
- The evidence-contract artifacts expose enough gate state for the dashboard to map current stage and required evidence.
- Local role configuration is sufficient for MVP authorization semantics.

## Definition of Done

- [x] Acceptance criteria met
- [x] Edge cases handled
- [x] Permissions enforced for approve and hold actions
- [x] Audit/timeline logged for validator runs, approvals, holds, blocked attempts, and cancellations
- [x] Tests cover missing evidence, failed validator, approve, hold, unauthorized approval, timeout, and reload
- [x] Documentation updated
- [x] Story filename matches `Story ID` prefix
- [x] Story index regenerated or updated

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

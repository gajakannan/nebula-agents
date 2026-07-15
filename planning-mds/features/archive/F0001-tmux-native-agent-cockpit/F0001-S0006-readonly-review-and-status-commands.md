# F0001-S0006 - Read-Only Review and Status Commands

> Delivery status: Done; archived with F0001 on 2026-07-15.

## Story Header

**Story ID:** F0001-S0006
**Feature:** F0001 - Tmux-Native Agent Cockpit
**Title:** Read-only review and status commands
**Priority:** Medium
**Phase:** MVP

## User Story

**As a** reviewer
**I want** read-only terminal commands for session status, evidence, validation, and attach guidance
**So that** I can inspect an agent run without accidentally changing the native session or gate decision state.

## Context & Background

Not every user should operate the live run. Reviewers need a compact way to inspect current state, run validation checks, and understand recovery options without opening the full TUI or mutating gate state. These commands also make CI-like local verification easier during feature closeout.

## Acceptance Criteria

**Happy Path:**
- **Given** one or more run registry records exist
- **When** the reviewer runs `sessions`, `status`, `evidence`, or `doctor`
- **Then** the command prints sanitized read-only state and exits with status `0`
- **When** the reviewer runs a validation command
- **Then** the command prints the validator command, exit code, and summary without approving or holding a gate
- **Then** read-only commands do not launch providers, send provider input, approve gates, or edit prompt content

**Alternative Flows / Edge Cases:**
- Missing run ID is rejected with available run IDs listed.
- Stale tmux session reference is reported as exited or unknown after verification.
- Validation command failure returns the validator exit code and marks the review result blocked.
- Unauthorized local role is denied for attach guidance when role policy disables reviewer attach.
- Missing evidence path is reported as unavailable with the expected path.

## Interaction Contract

N/A - read-only command story except validation result recording when explicitly requested.

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| CLI `sessions/status/evidence/doctor` | Inspect state | No editable state | No mutation | Output matches current registry after reload | Reviewer and Local Operator |
| CLI `validate` | Run validator | Validator choice | Writes optional validation result audit entry, never a gate decision | Latest validation summary appears in status output | Reviewer and Local Operator; approval remains unavailable |

Required checks for mutation stories:
- [x] Render-only behavior satisfies read-only commands; validation result recording is the only allowed mutation.
- [x] Validation command arguments are constrained to known validators.
- [x] Validation result recording has an audit/timeline entry.
- [x] Tests prove read-only commands do not create sessions or gate decisions.

## Data Requirements

**Required Fields:**
- `run_id`: Run to inspect.
- `status`: Current run status.
- `provider_key`: Provider for the run.
- `tmux_session`: Session identity or stale reference.
- `gate_state`: Current gate state.
- `evidence_root`: Evidence path.
- `validator_summary`: Latest validator result when present.

**Optional Fields:**
- `attach_command`: Sanitized attach guidance.
- `transcript_path`: Redacted transcript path.
- `available_run_ids`: Run IDs printed when lookup fails.

**Validation Rules:**
- Read-only commands must not call provider CLIs except explicit diagnostic probes.
- Attach command output is suppressed when policy denies reviewer attach.
- Validation command names must come from a configured allowlist.

## Role-Based Visibility

**Roles that can inspect status:**
- Reviewer - Can inspect sanitized status and run validators.
- Local Operator - Can inspect all local status.

**Data Visibility:**
- InternalOnly content: Full local paths and attach guidance.
- ExternalVisible content: Sanitized summaries, validator status, and evidence availability.

## Non-Functional Expectations

- Performance: Status commands complete within 1 second for normal local registry sizes.
- Security: Authorization policy controls attach guidance and local path detail.
- Reliability: Commands have stable exit code semantics documented for scripting.

## Dependencies

**Depends On:**
- F0001-S0001 - Doctor command uses preflight checks.
- F0001-S0003 - Status and evidence commands read registry state.
- F0001-S0004 - Validation summaries align with gate dashboard semantics.

**Related Stories:**
- F0001-S0005 - Recovery data appears in read-only status.

## Business Rules

1. Read-only means no provider process creation and no gate decision mutation.
2. Validator execution is allowed because it creates review evidence, not product state.
3. Command output should be script-friendly and human-readable, with a future option for JSON output.

## Out of Scope

- Full-screen TUI rendering.
- Remote API access.
- Gate approval or hold actions.
- Provider prompt submission.

## UI/UX Notes

- Screens involved: CLI output only for MVP; TUI may reuse formatting later.
- Key interactions: List sessions, inspect status, run validation, view evidence path.

## Questions & Assumptions

**Open Questions:**
- [ ] Should JSON output be included in MVP or deferred until the managed orchestration feature?

**Assumptions (to be validated):**
- Reviewers have local repository access when running these commands.
- Read-only status is enough for early closeout reviews before richer dashboards exist.

## Definition of Done

- [x] Acceptance criteria met
- [x] Edge cases handled
- [x] Permissions enforced for attach guidance and validation allowlist
- [x] Audit/timeline logged for validation runs only; pure read-only commands are N/A
- [x] Tests cover status, sessions, evidence, doctor, validation failure, denied attach guidance, stale tmux session, and missing run
- [x] Documentation updated
- [x] Story filename matches `Story ID` prefix
- [x] Story index regenerated or updated

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

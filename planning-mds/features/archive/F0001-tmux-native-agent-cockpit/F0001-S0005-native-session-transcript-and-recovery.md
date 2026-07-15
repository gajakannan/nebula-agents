# F0001-S0005 - Native Session Transcript and Recovery

> Delivery status: Done; archived with F0001 on 2026-07-15.

## Story Header

**Story ID:** F0001-S0005
**Feature:** F0001 - Tmux-Native Agent Cockpit
**Title:** Native session transcript and recovery
**Priority:** High
**Phase:** MVP

## User Story

**As a** product build operator
**I want** redacted transcripts and recovery commands for native tmux sessions
**So that** interrupted agent runs can be understood, resumed, or reviewed without losing the engineering context already built in the terminal.

## Context & Background

Long-running agent work can be interrupted by terminal disconnects, machine sleep, provider crashes, or user context switches. The cockpit must provide enough recovery information to reattach or review what happened, while treating transcript content as sensitive by default.

## Acceptance Criteria

**Happy Path:**
- **Given** an active tmux-backed provider session
- **When** transcript capture is enabled for the run
- **Then** the cockpit stores a redacted transcript path in the run registry
- **Then** terminal output is captured in an append-only transcript artifact
- **Then** attach and recovery commands are displayed in the session detail view
- **When** the TUI process restarts
- **Then** the operator can reload the run registry and attach to the existing tmux session or open the transcript summary

**Alternative Flows / Edge Cases:**
- If tmux session exists but transcript capture failed, attach remains available and transcript status is marked blocked with the failure reason.
- If capture may still be active, pipe inactivity must be positively proved or durable status must remain `Active`; if neither safety result can be established, the owning tmux session is terminated and verified absent before the error returns.
- If tmux session no longer exists, recovery shows last transcript path, last known gate, and last audit event.
- Secret patterns detected in transcript output are redacted before evidence display.
- Transcript file permission denied is reported and does not disable attach.
- Oversized transcript files are summarized with a bounded preview and a link to the artifact path.

## Interaction Contract

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| Session Detail | Enable or view transcript | Transcript capture toggle when available | Updates run registry and writes transcript artifact | Restart shows transcript path and redaction status | Local Operator; Reviewer read-only unless granted capture toggle |
| Recovery Command | Attach or inspect transcript | No direct edit | Appends recovery audit entry | Run registry shows recovery attempt after reload | Local Operator and Reviewer |

Required checks for mutation stories:
- [x] Render-only behavior cannot satisfy the story.
- [x] Transcript capture validates output path and redaction settings.
- [x] Transcript enablement and recovery attempts have audit/timeline entries.
- [x] Tests prove transcript and attach recovery still work after TUI restart.

## Data Requirements

**Required Fields:**
- `transcript_path`: Redacted transcript artifact path.
- `capture_status`: Disabled, Active, Failed, or Completed.
- `redaction_status`: NotRun, Passed, Redacted, or Failed.
- `last_seen_at`: Last timestamp observed from tmux or transcript capture.
- `recovery_command`: Sanitized attach command.

**Optional Fields:**
- `transcript_preview`: Bounded sanitized preview.
- `redaction_findings`: Count and categories of redactions.
- `last_gate_id`: Last known lifecycle gate.

**Validation Rules:**
- Transcript path must stay inside approved runtime or evidence directories.
- Redaction must run before transcript content is rendered in review surfaces.
- Recovery command must not include secrets or raw provider auth arguments.

## Role-Based Visibility

**Roles that can recover sessions:**
- Local Operator - Can attach and manage transcript capture.
- Reviewer - Can attach or inspect transcript only when granted local terminal access.

**Data Visibility:**
- InternalOnly content: Raw transcript artifact path and full terminal output.
- ExternalVisible content: Redacted transcript summary and sanitized recovery command.

## Non-Functional Expectations

- Performance: Transcript preview renders from bounded content and does not load unbounded files into memory.
- Security: Authorization is local; transcript rendering always uses redacted output.
- Reliability: Recovery status distinguishes active tmux session, exited session, missing transcript, and unreadable transcript.

## Dependencies

**Depends On:**
- F0001-S0002 - Tmux session identity is required.
- F0001-S0003 - Run registry stores transcript and recovery metadata.

**Related Stories:**
- F0001-S0006 - Status commands expose recovery data.
- F0002-S0002 - Future managed sessions need equivalent context continuity.

## Business Rules

1. Preserve context: Recovery must favor reattaching to the native session when it still exists, except when terminating it is the only verified way to prevent capture continuing behind an untruthful durable state.
2. Redact before review: Transcript content shown outside the native terminal must pass redaction first.
3. Recovery is auditable: Attach attempts and transcript recovery events are recorded.

## Out of Scope

- Cloud transcript storage.
- Sharing transcripts with remote reviewers.
- Automatic provider prompt replay.
- Editing transcript content.

## UI/UX Notes

- Screens involved: Session detail, recovery panel, transcript preview.
- Key interactions: Attach, copy recovery command, view transcript preview, inspect redaction status.

## Questions & Assumptions

**Open Questions:**
- [ ] Should transcript capture default on for all runs, or ask during first launch because of sensitivity?

**Assumptions (to be validated):**
- tmux capture or pipe-pane behavior is reliable enough for MVP transcript collection.
- Redaction can use the existing secret pattern conventions in the product-manager scripts.

## Definition of Done

- [x] Acceptance criteria met
- [x] Edge cases handled
- [x] Permissions enforced through local access and path validation
- [x] Audit/timeline logged for transcript enablement, failure, redaction, attach, and recovery actions
- [x] Tests cover active recovery, exited session, redaction, denied transcript path, oversized transcript, and restart
- [x] Documentation updated
- [x] Story filename matches `Story ID` prefix
- [x] Story index regenerated or updated

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

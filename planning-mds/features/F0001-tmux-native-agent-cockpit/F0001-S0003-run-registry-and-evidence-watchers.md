# F0001-S0003 - Run Registry and Evidence Watchers

## Story Header

**Story ID:** F0001-S0003
**Feature:** F0001 - Tmux-Native Agent Cockpit
**Title:** Run registry and evidence watchers
**Priority:** High
**Phase:** MVP

## User Story

**As a** delivery lead
**I want** each active terminal session tied to a run registry and evidence paths
**So that** approvals, validation output, and recovery commands point at the same work package.

## Context & Background

The native terminal session is valuable, but it is not enough by itself. Nebula must maintain local structured state around the session so the cockpit can show what feature is being worked, which gate is active, where evidence is being written, and what command should be used to recover or validate the run.

## Acceptance Criteria

**Happy Path:**
- **Given** a tmux-backed provider session has launched
- **When** the run registry is written
- **Then** the registry stores run identity, provider, tmux session, feature/story focus, prompt action, workspace root, evidence root, gate state, transcript path, and timestamps
- **Then** evidence watchers detect changes to known artifacts such as lifecycle gate logs, gate decisions, commands logs, validation reports, and story/status files
- **Then** the TUI receives an update event when a watched artifact changes
- **Then** each registry change appends an audit event with timestamp, action, and sanitized details

**Alternative Flows / Edge Cases:**
- Missing evidence directory is reported as pending until the provider creates it or the operator initializes it.
- Deleted or moved evidence files are marked unavailable instead of crashing the watcher.
- Invalid JSON/YAML/Markdown metadata is rejected with the file path and parse error category.
- A run whose tmux session no longer exists is marked `DetachedOrExited` after verification.
- File permission denied is reported with a nonzero validation state and no retry loop that floods the terminal.

## Interaction Contract

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| Launch flow | Start provider run | Feature/story/action selected during launch | Creates or updates run registry and starts watchers | Restarting the TUI reloads the run and watcher status from disk | Local Operator; blocked if registry path is not writable |
| Session Detail | Inspect evidence state | No direct edit in this story | Watcher updates artifact status and audit timeline | Changed evidence files appear after reload or watcher restart | Local Operator and Reviewer |

Required checks for mutation stories:
- [x] Render-only behavior cannot satisfy the story.
- [x] Registry writes validate schema and path boundaries.
- [x] A successful registry mutation has an audit event.
- [x] Tests prove registry state survives process reload and changed evidence is observed.

## Data Requirements

**Required Fields:**
- `run_id`: Stable run identifier.
- `provider_key`: Provider used by the native session.
- `tmux_session`: Tmux identity.
- `feature_id`: Feature under work.
- `workspace_root`: Product root.
- `evidence_root`: Root directory for run evidence.
- `gate_state`: Current gate identifier and status.
- `artifacts`: List of watched artifact paths and statuses.
- `audit_events`: Append-only local event list.

**Optional Fields:**
- `story_id`: Focus story for the run.
- `last_validator_result`: Latest validation command summary.
- `transcript_path`: Current redacted transcript path.

**Validation Rules:**
- Registry paths must stay under the workspace root or configured runtime directory.
- Watcher events must store relative evidence paths where possible.
- Malformed artifact metadata must not overwrite the last valid registry state.

## Role-Based Visibility

**Roles that can inspect registry state:**
- Local Operator - Full local view.
- Reviewer - Read-only local view.

**Data Visibility:**
- InternalOnly content: Local paths, tmux session names, raw validation command summaries.
- ExternalVisible content: Sanitized evidence manifest and gate status.

## Non-Functional Expectations

- Performance: Watcher updates appear in the TUI within 1 second of filesystem notification or next poll.
- Security: Registry redacts secrets and stores only command templates or sanitized arguments.
- Reliability: Corrupt registry recovery preserves the original corrupt file and starts from the last valid snapshot when available.

## Dependencies

**Depends On:**
- F0001-S0002 - Run registry starts after tmux launch.

**Related Stories:**
- F0001-S0004 - Gate dashboard reads registry and evidence watcher state.
- F0001-S0005 - Transcript path is part of run metadata.

## Business Rules

1. Registry is local source of truth: The TUI should not infer run state only from screen text.
2. Evidence paths are explicit: Every gate and validator panel links to known files instead of relying on memory of terminal output.
3. Append-only audit: Registry-changing actions add audit entries rather than overwriting history silently.

## Out of Scope

- Remote database storage.
- Multi-user synchronization.
- Permanent analytics.
- Cloud evidence upload.

## UI/UX Notes

- Screens involved: Session detail, evidence panel, validator panel.
- Key interactions: Inspect artifact freshness, open evidence path, see watcher errors.

## Questions & Assumptions

**Open Questions:**
- [ ] Should runtime registry files be JSON for machine use, Markdown for operator readability, or both?

**Assumptions (to be validated):**
- Local filesystem watchers are available, with polling fallback for environments that lack native notifications.
- Evidence-contract prompt outputs can be mapped to a stable set of artifact paths.

## Definition of Done

- [x] Acceptance criteria met
- [x] Edge cases handled
- [x] Permissions enforced through runtime path validation
- [x] Audit/timeline logged for registry creation, update, artifact change, parse error, and session disappearance
- [x] Tests cover schema validation, reload, watcher change, deleted file, denied file, and corrupt registry recovery
- [x] Documentation updated
- [x] Story filename matches `Story ID` prefix
- [x] Story index regenerated or updated

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

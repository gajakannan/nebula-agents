# F0001-S0002 - Tmux Session Launch and Attach

> Delivery status: Done; archived with F0001 on 2026-07-15.

## Story Header

**Story ID:** F0001-S0002
**Feature:** F0001 - Tmux-Native Agent Cockpit
**Title:** Tmux session launch and attach
**Priority:** Critical
**Phase:** MVP

## User Story

**As a** product build operator
**I want** to launch Codex or Claude Code inside a named tmux session from the cockpit
**So that** I can keep native interactive approval prompts, subscription auth, and scrollback while the planning workflow tracks the run.

## Context & Background

The operator values the native provider terminal because it supports interactive feedback, approval prompts, and continuity across complex build stages. This story establishes tmux as the execution boundary: Nebula starts the provider inside tmux, records the session name, and lets the user attach to the native UI instead of replacing it.

## Acceptance Criteria

**Happy Path:**
- **Given** preflight reports tmux ready and a selected provider ready
- **When** the operator launches a new run for F0001 or a selected story
- **Then** Nebula creates a unique tmux session name using the feature ID and run ID
- **Then** the selected native provider CLI starts inside that tmux session with the chosen evidence-contract prompt
- **Then** the user can attach to the session and see the provider's native terminal UI
- **Then** the run registry records a launch event with provider, run ID, feature/story focus, tmux session name, command template, timestamp, and audit timeline entry

**Alternative Flows / Edge Cases:**
- Duplicate requested run ID is rejected before tmux launch.
- Provider CLI exits during launch; the session is marked failed and the attach action is disabled until the operator chooses a recovery action.
- Existing tmux session name collision is rejected with the colliding session listed.
- If the provider prompts for login, the prompt remains inside the native tmux session; Nebula does not intercept credentials.
- Attach to an existing active run must not launch a second provider process.

## Interaction Contract

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| TUI Session List | Select provider, feature/story, action, then launch | Provider, feature, story, prompt action, optional run label | Creates tmux session and run registry record | `sessions` command shows active run and `tmux has-session` finds the named session | Local Operator; launch blocked when preflight has errors |
| CLI `nebula-agents attach --run-id` | Attach to active run | No editable state | No new session; attaches to existing tmux session | Session registry `attached_at` audit entry is appended | Local Operator or Reviewer with shell access |

Required checks for mutation stories:
- [x] Render-only behavior cannot satisfy the story.
- [x] The launch path validates provider, feature/story ID, prompt action, and tmux session uniqueness.
- [x] A successful launch has an audit event in the run registry.
- [x] Tests prove attach reuses the existing tmux session after process reload.

## Data Requirements

**Required Fields:**
- `run_id`: Unique local run identifier.
- `feature_id`: Feature ID such as F0001.
- `story_id`: Optional story ID.
- `provider_key`: `codex` or `claude`.
- `tmux_session`: Generated tmux session name.
- `launch_command`: Redacted command template used for launch.
- `status`: Launching, Active, Failed, Exited, or Unknown.
- `created_at`: ISO timestamp.

**Optional Fields:**
- `run_label`: Human-readable label.
- `prompt_action`: Evidence-contract action such as plan, feature, review, validate, or build.

**Validation Rules:**
- `feature_id` and `story_id` must match known planning docs when supplied.
- `tmux_session` must be shell-safe and deterministic enough for recovery.
- `launch_command` must redact secrets and avoid persisting environment values.

## Role-Based Visibility

**Roles that can launch or attach:**
- Local Operator - Can launch and attach from their authenticated shell.
- Reviewer - Can attach when they have terminal access to the same machine/session.

**Data Visibility:**
- InternalOnly content: Launch command template, local paths, tmux session name, transcript path.
- ExternalVisible content: Sanitized status summary and evidence references.

## Non-Functional Expectations

- Performance: Launch feedback appears within 2 seconds after tmux command return.
- Security: Provider authentication remains inside the native CLI; Nebula must not collect credentials.
- Reliability: Session creation is atomic from the user's view: failed launches do not appear as active runs.

## Dependencies

**Depends On:**
- F0001-S0001 - Preflight must identify a usable provider and tmux environment.

**Related Stories:**
- F0001-S0003 - Registry expands launch state into evidence tracking.
- F0001-S0005 - Transcript and recovery use the tmux session identity.

## Business Rules

1. Native UI preservation: The provider's interactive terminal remains the source of truth for provider prompts.
2. No hidden approval: Nebula must not answer provider or lifecycle approval prompts without a user action.
3. Single process per run: Attaching to an active run never starts another provider process.

## Out of Scope

- Remote tmux hosts.
- Multi-pane collaborative editing.
- Automatic login or subscription management.
- Provider SDK execution.

## UI/UX Notes

- Screens involved: Session list, launch form, attach action, failed launch state.
- Key interactions: Select provider, select feature/story, launch, attach, recover.

## Questions & Assumptions

**Open Questions:**
- [ ] Should session names include provider key, feature ID, and timestamp, or use a shorter generated alias with metadata stored only in the registry?

**Assumptions (to be validated):**
- tmux is available in the same shell environment as the provider CLI.
- The terminal UI can attach without corrupting the native provider rendering.

## Definition of Done

- [x] Acceptance criteria met
- [x] Edge cases handled
- [x] Permissions enforced through local shell access and launch guards
- [x] Audit/timeline logged for launch, attach, failure, and exit events
- [x] Tests cover launch success, duplicate run, tmux collision, failed provider process, and attach reuse
- [x] Documentation updated
- [x] Story filename matches `Story ID` prefix
- [x] Story index regenerated or updated

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

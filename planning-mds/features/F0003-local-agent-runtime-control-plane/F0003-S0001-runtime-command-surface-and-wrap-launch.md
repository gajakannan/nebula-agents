# F0003-S0001 - Runtime Command Surface and Wrap Launch

## Story Header

**Story ID:** F0003-S0001
**Feature:** F0003 - Local Agent Runtime Control Plane
**Title:** Runtime command surface and wrap launch
**Priority:** Critical
**Phase:** Platform Hardening

## User Story

**As a** product build operator
**I want** a single local command surface for preflight, wrapped launch, session list, status, validators, evidence, and attach guidance
**So that** I can operate native agent sessions through Nebula without manually stitching together terminal commands and evidence paths.

## Context & Background

F0001 defines the tmux-native cockpit, but operators still need a concrete command entry point that performs preflight, starts the native provider, records run metadata, and keeps recovery commands discoverable. This story defines the runtime command surface that other F0003 stories can extend.

## Acceptance Criteria

**Happy Path:**
- **Given** the operator has a valid workspace and supported provider CLI
- **When** the operator runs `nebula-agents wrap <provider> --action <action> --feature <feature-id>`
- **Then** the command runs preflight, creates a unique `run_id`, records provider, workspace, action, feature, runtime directory, and session reference
- **Then** the command starts or delegates to the native session launcher without storing provider credentials
- **Then** `nebula-agents sessions` lists the run
- **Then** `nebula-agents status --run <run_id>` returns human-readable and machine-readable status
- **Then** `nebula-agents attach --run <run_id>` prints the exact attach command or opens the local attach flow
- **Then** launch and reconciliation audit timeline entries are written with run ID, command, result, and timestamp

**Alternative Flows / Edge Cases:**
- Missing required provider capability blocks launch and points to capability report details.
- Existing run ID collision is rejected and a new ID is generated.
- Runtime directory cannot be created; command exits nonzero and names the blocked path.
- Session launch succeeds but metadata write fails; command reports failed launch bookkeeping and provides manual recovery guidance.
- Status command detects a stale session reference and marks the run `stale` with reconciliation guidance.

## Interaction Contract

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| CLI `doctor` | Run local preflight | No editable state | Writes latest diagnostic report when runtime dir exists | Latest report is visible through `status` | Local Operator, Reviewer |
| CLI `wrap` | Launch native session | Provider, action, feature, optional story | Creates run metadata and session reference | `sessions` and `status` show the run after restart | Local Operator only |
| CLI `sessions` | List runs | No editable state | None | Reads persisted run registry and live session probe | Local Operator, Reviewer |
| CLI `status` | Inspect one run | No editable state | May reconcile stale runtime status | Status JSON includes reconciliation timestamp | Local Operator, Reviewer |
| CLI `attach` | Reattach or print attach command | No editable state | None unless attach audit is enabled | Attach guidance remains available after restart | Local Operator |

Required checks for mutation stories:
- [ ] Wrapped launch creates append-only run metadata.
- [ ] Status output includes a machine-readable JSON mode.
- [ ] Launch never persists provider credential bodies.
- [ ] Tests cover success, blocked capability, stale session, metadata write failure, and denied runtime directory.

## Data Requirements

**Required Fields:**
- `run_id`: Unique local run identifier.
- `provider_key`: Supported provider identifier.
- `action`: Framework action selected for the run.
- `feature_id`: Feature associated with the run.
- `workspace_root`: Absolute workspace path.
- `runtime_dir`: Absolute runtime state path.
- `session_ref`: tmux session name or future managed session identifier.
- `runtime_status`: Created, launching, running, stale, completed, failed, or abandoned.

**Optional Fields:**
- `story_id`: Focus story when provided.
- `prompt_contract_path`: Prompt template used to launch the run.
- `attach_command`: Local attach command when available.

**Validation Rules:**
- `run_id` must be unique within the runtime registry.
- `workspace_root` and `runtime_dir` must be absolute paths.
- `provider_key` must exist in the provider capability registry.
- `action` must match a known action in `agents/agent-map.yaml`.

## Role-Based Visibility

**Roles that can use the command surface:**
- Local Operator - Can run all commands.
- Reviewer - Can use read-only preflight, sessions, and status commands.
- Architect - Can inspect command contracts and status JSON.

**Data Visibility:**
- InternalOnly content: Local paths, session references, provider command paths.
- ExternalVisible content: Sanitized run state and validation status.

## Non-Functional Expectations

- Performance: `sessions` and `status` complete within 1 second for normal local registries.
- Reliability: Status reconciles persisted metadata with actual local session state before reporting.
- Security: Commands redact secret-like values before writing logs or status artifacts.
- Authorization: Launch commands require local operator permissions; read-only commands require filesystem access to the runtime directory.

## Dependencies

**Depends On:**
- F0001 session launch and attach behavior, or a compatible local launcher stub.

**Related Stories:**
- F0003-S0002 - Launch guards use provider capabilities before `wrap`.
- F0003-S0004 - Evidence store links artifacts to `run_id`.

## Business Rules

1. Native-first: Wrapped launch must preserve native provider interactivity.
2. Read-only default: Inspect commands must not mutate gates except for explicit reconciliation metadata.
3. Recoverability: Every launched run must expose attach or recovery guidance.

## Out of Scope

- Hosted execution.
- Provider account login.
- Automatic lifecycle gate approval.
- Managed SDK orchestration.

## UI/UX Notes

- Command surfaces involved: `doctor`, `wrap`, `sessions`, `status`, `attach`. F0003 is CLI-only; a terminal-UI presentation of these belongs to F0008.
- Key interactions: Run preflight, launch, list, inspect, attach.

## Questions & Assumptions

**Open Questions:**
- [ ] Should the first command entry point live under `agents/runtime/` or a root-level package wrapper?

**Assumptions (to be validated):**
- A local CLI surface is sufficient for the MCP implementation to consume, and for any later terminal-UI surface F0008 may add.

## Definition of Done

- [ ] Acceptance criteria met
- [ ] Edge cases handled
- [ ] Permissions enforced through local shell and filesystem boundaries
- [ ] Audit/timeline logged for launch and reconciliation events
- [ ] Tests cover command behavior and JSON output
- [ ] Documentation updated
- [ ] Story filename matches `Story ID` prefix
- [ ] Story index regenerated or updated

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

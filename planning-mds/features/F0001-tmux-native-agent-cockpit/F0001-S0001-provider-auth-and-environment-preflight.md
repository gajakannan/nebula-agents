# F0001-S0001 - Provider Auth and Environment Preflight

## Story Header

**Story ID:** F0001-S0001
**Feature:** F0001 - Tmux-Native Agent Cockpit
**Title:** Provider auth and environment preflight
**Priority:** Critical
**Phase:** MVP

## User Story

**As a** product build operator
**I want** a preflight check that reports terminal agent readiness before a run starts
**So that** I can know whether Codex or Claude Code can be launched through the subscription-authenticated CLI without switching away from the user's existing login.

## Context & Background

The first risk in the terminal UI is not rendering a list of sessions; it is launching the same native tools the operator already trusts. The preflight command must report whether the local shell can run tmux and provider CLIs, whether the workspace has planning assets, and whether the chosen provider appears ready without reading or storing secrets.

## Acceptance Criteria

**Happy Path:**
- **Given** the operator has `tmux` and at least one supported provider CLI on `PATH`
- **When** the operator runs the preflight command
- **Then** the output lists tmux readiness, provider CLI path, provider version when available, workspace root, planning docs path, evidence-contract prompt path, and runtime directory
- **Then** the command exits with status `0`
- **Then** no provider token, auth cache value, credential file body, or API key is printed or persisted

**Alternative Flows / Edge Cases:**
- Missing `tmux` is rejected with a nonzero exit and an install/remediation message.
- Missing provider CLI is rejected unless another supported provider is explicitly selected and ready.
- A workspace without `planning-mds/features` is rejected with the missing path listed.
- A provider command that returns an auth/login-required message is reported as `authentication attention needed`; the command must not attempt to login on the user's behalf.
- Permission denied while creating the runtime directory returns a nonzero exit and names the denied path.

## Interaction Contract

N/A - read-only diagnostic story. The command may create an empty runtime directory only when needed to test write access; it must not create provider sessions.

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| CLI `nebula-agents doctor` | Run preflight | No editable state | Runtime directory may be initialized after confirmation-free local check | Re-running shows the same runtime directory and latest probe results | Local operator only; no remote authorization surface |

## Data Requirements

**Required Fields:**
- `workspace_root`: Absolute path used for planning docs and future evidence.
- `runtime_dir`: Local path used for session registry and transient state.
- `tmux_path`: Resolved executable path or missing status.
- `provider_key`: Supported provider identifier.
- `provider_cli_path`: Resolved executable path or missing status.
- `provider_version`: Reported version string when available.
- `readiness_status`: Ready, missing, authentication attention needed, unsupported, or denied.

**Optional Fields:**
- `provider_hint`: User-selected provider override.
- `prompt_contract_path`: Evidence-contract prompt path selected for the intended action.

**Validation Rules:**
- Paths must be absolute in machine-readable output.
- Secret-like values must be redacted before display and never written to runtime state.
- Unsupported provider keys are rejected before probing the shell.

## Role-Based Visibility

**Roles that can run preflight:**
- Local Operator - Can run diagnostics in their own shell.
- Reviewer - Can run diagnostics when they have local repository access.

**Data Visibility:**
- InternalOnly content: Full local filesystem paths and provider readiness details.
- ExternalVisible content: Sanitized readiness summary with no username, token, account, or credential data.

## Non-Functional Expectations

- Performance: Preflight completes within 3 seconds when provider CLIs return normally.
- Security: Authorization is local-shell based; no provider auth material is read beyond command exit/output probes.
- Reliability: Each failed probe reports the exact check that failed and the remediation category.

## Dependencies

**Depends On:**
- None.

**Related Stories:**
- F0001-S0002 - Launch uses preflight results before starting a tmux session.
- F0001-S0006 - Read-only review commands reuse preflight output.

## Business Rules

1. Subscription-first boundary: F0001 must prefer already-authenticated local provider CLIs over API-key SDK paths.
2. Secret boundary: A readiness check may detect that auth attention is needed, but it must not inspect or persist credential bodies.
3. Provider neutrality: The preflight result schema must support both Codex and Claude Code without provider-specific fields leaking into common status views.

## Out of Scope

- Performing provider login.
- Validating billing, subscription tier, or remote account permissions.
- Launching tmux sessions.
- Running product-build prompts.

## UI/UX Notes

- Screens involved: Preflight panel, session launch guard.
- Key interactions: Run diagnostics, view pass/fail rows, open remediation text.

## Questions & Assumptions

**Open Questions:**
- [ ] Should provider readiness use only version/help commands, or should it optionally run a dry-run auth probe when the provider supports one?

**Assumptions (to be validated):**
- Provider CLIs expose enough non-secret output to distinguish missing CLI from login-required state.
- The operator launches Nebula Agents from the same shell context used for provider CLI auth.

## Definition of Done

- [x] Acceptance criteria met
- [x] Edge cases handled
- [x] Permissions enforced through local filesystem and shell access boundaries
- [x] Audit/timeline logged as N/A - diagnostic only, with runtime-dir initialization recorded when it occurs
- [x] Tests cover ready, missing tmux, missing provider, auth attention, unsupported provider, and denied runtime directory
- [x] Documentation updated
- [x] Story filename matches `Story ID` prefix
- [x] Story index regenerated or updated

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

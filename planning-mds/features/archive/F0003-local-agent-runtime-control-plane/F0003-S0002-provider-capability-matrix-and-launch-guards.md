# F0003-S0002 - Provider Capability Matrix and Launch Guards

## Story Header

**Story ID:** F0003-S0002
**Feature:** F0003 - Local Agent Runtime Control Plane
**Title:** Provider capability matrix and launch guards
**Priority:** Critical
**Phase:** Platform Hardening

## User Story

**As a** platform maintainer
**I want** provider capability reports and launch guards for local agent CLIs
**So that** Nebula can block unsafe launches, explain degraded modes, and preserve fallback behavior before a run starts.

## Context & Background

The runtime control plane should not assume every provider CLI exposes the same launch, stream, auth, transcript, and approval behavior. A capability matrix gives the command surface a structured readiness contract and gives future managed orchestration a stable handoff point.

## Acceptance Criteria

**Happy Path:**
- **Given** a supported provider key
- **When** the operator runs a provider probe
- **Then** Nebula records CLI path, version when available, launch support, attach support, transcript support, status probe support, approval visibility, and fallback availability
- **Then** each capability is marked `required`, `optional`, `unsupported`, or `fallback`
- **Then** each probe result is marked `pass`, `fail`, `timeout`, or `skipped`
- **Then** wrapped launch is allowed only when required capabilities pass or have an explicit fallback

**Alternative Flows / Edge Cases:**
- Provider CLI is missing; launch is blocked with remediation guidance.
- Provider probe times out; launch is blocked unless the capability is optional.
- Provider version command returns secret-like text; output is redacted before persistence.
- Provider supports launch but no transcript capture; launch is allowed only when Nebula transcript capture is available.
- Capability report is stale; launch warns or re-runs probes based on max-age policy.

## Interaction Contract

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| CLI `providers doctor` | Probe one or more providers | Provider selection | Writes capability report | `wrap` reads latest report and freshness timestamp | Local Operator, Reviewer |
| CLI `providers doctor --format table` | Inspect readiness | No editable state | None | Reads persisted reports | Local Operator, Reviewer, Architect |
| CLI `wrap` | Attempt launch | Provider and mode | Blocks or allows launch based on report | Blocked launch writes sanitized audit entry | Local Operator only |

Required checks for mutation stories:
- [ ] Capability report schema validates before launch consumes it.
- [ ] Required capability failure blocks launch.
- [ ] Fallback policy is explicit for unsupported required capabilities.
- [ ] Tests cover pass, fail, timeout, stale report, and fallback launch paths.

## Data Requirements

**Required Fields:**
- `provider_key`: Provider identifier.
- `provider_mode`: tmux-native, managed-exec, managed-sdk, or unavailable.
- `capability_name`: Capability under probe.
- `capability_requirement`: Required, Optional, Unsupported, or Fallback.
- `probe_result`: Pass, Fail, Timeout, or Skipped.
- `report_generated_at`: Timestamp for freshness checks.
- `fallback_available`: Boolean.

**Optional Fields:**
- `provider_cli_path`: Resolved executable path.
- `provider_version`: Redacted version string.
- `failure_reason`: Sanitized failure reason.
- `probe_artifact_id`: Evidence artifact ID for detailed output.

**Validation Rules:**
- Launch cannot proceed with failed required capabilities.
- Stale reports must be re-run or explicitly accepted based on policy.
- Capability reports must not contain provider credential bodies.
- Unknown provider keys are rejected before shell probes run.

## Role-Based Visibility

**Roles that can inspect capability reports:**
- Local Operator - Can run probes and launch.
- Reviewer - Can run probes and inspect blocked launch evidence.
- Architect - Can approve capability schema changes.
- Security Reviewer - Can inspect redaction and auth-boundary behavior.

**Data Visibility:**
- InternalOnly content: Local executable paths and detailed probe output.
- ExternalVisible content: Sanitized readiness matrix and blocked launch reason.

## Non-Functional Expectations

- Performance: Provider probes complete within configured timeout per provider.
- Reliability: Probe results are deterministic enough to support automated tests with fixtures.
- Security: Secret redaction applies before report persistence.
- Authorization: Probe and launch-guard commands require local filesystem permissions for the runtime directory and must not elevate provider access.

## Dependencies

**Depends On:**
- F0003-S0001 command surface.

**Related Stories:**
- F0002-S0001 provider adapter contract will consume capability categories after F0003 stabilizes them.

## Business Rules

1. Capability before launch: Runtime launch must consume a valid capability report.
2. Explicit degradation: Degraded or fallback behavior must be visible before the session starts.
3. No hidden credentials: Probes may observe command status but must not persist auth material.

## Out of Scope

- Provider account setup.
- Hosted credential checks.
- Full managed-provider adapter implementation.

## UI/UX Notes

- Command surfaces involved: `providers doctor` for the readiness matrix; `wrap` reports the blocked-launch reason and remediation inline.
- Key interactions: Run probe, inspect missing capabilities, follow fallback guidance.

## Questions & Assumptions

**Open Questions:**
- [ ] What default max-age should provider capability reports use before launch requires a fresh probe?

**Assumptions (to be validated):**
- Provider CLI version or help commands are enough for baseline readiness checks.

## Definition of Done

- [ ] Acceptance criteria met
- [ ] Edge cases handled
- [ ] Permissions enforced for probe execution and launch blocking
- [ ] Audit/timeline logged for probe and blocked launch events
- [ ] Tests cover report schema and launch guards
- [ ] Documentation updated
- [ ] Story filename matches `Story ID` prefix
- [ ] Story index regenerated or updated

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

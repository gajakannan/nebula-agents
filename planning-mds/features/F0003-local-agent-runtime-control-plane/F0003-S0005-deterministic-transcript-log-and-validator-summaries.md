# F0003-S0005 - Deterministic Transcript, Log, and Validator Summaries

## Story Header

**Story ID:** F0003-S0005
**Feature:** F0003 - Local Agent Runtime Control Plane
**Title:** Deterministic transcript, log, and validator summaries
**Priority:** High
**Phase:** Platform Hardening

## User Story

**As a** reviewer
**I want** deterministic summaries of transcripts, command logs, validator output, and evidence manifests
**So that** I can scan run history quickly while still tracing every summary back to full local evidence.

## Context & Background

Raw terminal transcripts and validator logs are often too long for fast review. The runtime should produce deterministic summaries that preserve the facts reviewers need: commands, exit codes, errors, gates, decisions, artifact paths, missing evidence, and open questions. These summaries must not change provider prompts during F0001.

## Acceptance Criteria

**Happy Path:**
- **Given** an indexed artifact exists
- **When** the summarizer processes it
- **Then** the summary includes artifact ID, artifact kind, source path, redaction status, key events, failures, warnings, exit codes, gate decisions, evidence paths, and open questions when present
- **Then** transcript summaries preserve user prompts, approval moments, tool-call attention points, and recovery markers in redacted form
- **Then** validator summaries preserve command, exit code, pass/fail status, failed rule names, and remediation hints
- **Then** command-log summaries preserve command order, duration when available, exit code, and failed commands

**Alternative Flows / Edge Cases:**
- Artifact is binary or unsupported; summary records unsupported kind and retrieval metadata.
- Artifact has strong secret indicators; summary is blocked and redaction failure is recorded.
- Artifact is incomplete because a run was interrupted; summary records partial status and last observed marker.
- Validator output is very large; summary extracts failed sections and truncates passing noise with counts.
- Summary generation fails; artifact remains indexed with summary status `failed`.

## Interaction Contract

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| CLI `evidence summarize` | Summarize one artifact or run | Artifact ID or run ID | Writes summary artifact and updates index | `evidence show` reads latest summary | Local Operator, automation |
| CLI `evidence show <artifact-id>` | Inspect summary | No editable state | None | Reads summary artifact | Reviewer, Local Operator |
| MCP `nebula_evidence_show` | Query summary | No editable state | None | Reads same summary artifact | Reviewer, Local Operator |

Required checks for mutation stories:
- [ ] Summary output is deterministic for the same input fixture.
- [ ] Secret-like values are redacted or block summary exposure.
- [ ] Summary includes artifact ID and source evidence reference.
- [ ] Tests cover transcript, command log, validator output, manifest, unsupported artifact, and redaction failure.

## Data Requirements

**Required Fields:**
- `artifact_id`: Source artifact identifier.
- `summary_id`: Summary artifact identifier.
- `artifact_kind`: Source artifact kind.
- `summary_status`: Pass, Failed, Blocked, Unsupported, or Partial.
- `redaction_status`: Pass, Fail, Pending, or NotRequired.
- `key_events`: Ordered event list.
- `failure_markers`: Failed commands, rules, or gates.
- `source_reference`: Local artifact retrieval reference.

**Optional Fields:**
- `warning_markers`: Non-blocking warnings.
- `open_questions`: Questions extracted from run output.
- `truncation_count`: Count of omitted low-signal lines.
- `last_observed_marker`: Last marker for interrupted runs.

**Validation Rules:**
- Summary generation must not modify source artifacts.
- Summaries must be reproducible for fixture inputs.
- Failed redaction blocks summary exposure.
- Summary content must remain bounded by configured size limits.

## Role-Based Visibility

**Roles that can generate or inspect summaries:**
- Local Operator - Can generate summaries.
- Reviewer - Can inspect summaries.
- Quality Engineer - Can verify summary coverage against fixtures.
- Security Reviewer - Can verify redaction behavior.

**Data Visibility:**
- InternalOnly content: Source paths and raw source content.
- ExternalVisible content: Redacted summary text and artifact IDs.

## Non-Functional Expectations

- Performance: Common artifact summaries complete within 5 seconds for normal run artifacts.
- Reliability: Summarizers use deterministic parsing and extraction rules.
- Security: Redaction runs before summary exposure.
- Authorization: Summary generation requires local read permissions for source artifacts and write permissions for the approved summary directory.

## Dependencies

**Depends On:**
- F0003-S0004 artifact index.

**Related Stories:**
- F0003-S0003 exposes summaries through MCP.
- F0003-S0006 uses summaries for metrics and learning proposals.

## Business Rules

1. Summary is not source of truth: Full artifact remains authoritative.
2. Deterministic first: Initial summarizers use rules and parsers before any model-generated interpretation.
3. Preserve failures: Failed commands, failed validators, and gate holds must not be omitted.

## Out of Scope

- Prompt compression that changes provider context.
- Model-generated summaries as the default path.
- Summaries of arbitrary external files outside approved artifact directories.

## UI/UX Notes

- Command surfaces involved: `evidence summarize`, `evidence show`.
- Key interactions: Generate summary, inspect failed sections, open source artifact path.

## Questions & Assumptions

**Open Questions:**
- [ ] Should summary fixtures live under `agents/runtime/tests/fixtures` or the product-manager evidence validator fixtures?

**Assumptions (to be validated):**
- Deterministic summaries are enough for first review workflows.

## Definition of Done

- [ ] Acceptance criteria met
- [ ] Edge cases handled
- [ ] Permissions enforced through artifact path and redaction checks
- [ ] Audit/timeline logged for summary generation and blocked summaries
- [ ] Tests cover deterministic summaries and redaction behavior
- [ ] Documentation updated
- [ ] Story filename matches `Story ID` prefix
- [ ] Story index regenerated or updated

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

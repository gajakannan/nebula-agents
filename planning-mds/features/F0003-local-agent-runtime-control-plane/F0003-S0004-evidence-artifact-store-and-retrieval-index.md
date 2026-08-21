# F0003-S0004 - Evidence Artifact Store and Retrieval Index

## Story Header

**Story ID:** F0003-S0004
**Feature:** F0003 - Local Agent Runtime Control Plane
**Title:** Evidence artifact store and retrieval index
**Priority:** High
**Phase:** Platform Hardening

## User Story

**As a** code reviewer
**I want** every runtime evidence artifact to have a stable ID, summary, kind, path, and redaction status
**So that** I can trace dashboard and MCP summaries back to full local evidence without guessing filenames.

## Context & Background

Nebula already has a strong evidence contract, but the runtime needs a concrete artifact index that ties transcripts, command logs, validator output, manifests, metrics, and learning proposals to the run that produced them. This story establishes the store and retrieval contract.

## Acceptance Criteria

**Happy Path:**
- **Given** a run has generated transcript, command-log, validator, manifest, or status artifacts
- **When** the runtime indexes artifacts
- **Then** each artifact receives a stable `artifact_id`, `run_id`, `artifact_kind`, `created_at`, `source_path`, `summary_path`, `redaction_status`, and `retrieval_policy`
- **Then** `nebula-agents evidence list --run <run_id>` returns all indexed artifacts
- **Then** `nebula-agents evidence show <artifact_id>` returns the redacted summary and retrieval metadata
- **Then** full retrieval paths remain local and bounded to approved directories
- **Then** artifact indexing audit timeline entries record artifact ID, run ID, policy result, and timestamp

**Alternative Flows / Edge Cases:**
- Artifact path points outside approved directories; indexing fails and records a policy violation.
- Artifact disappears after indexing; retrieval reports missing artifact and marks freshness stale.
- Redaction validation fails; artifact summary is withheld until fixed.
- Duplicate artifact content is indexed twice; IDs remain unique while content hash links duplicates.
- Artifact is too large for direct summary; index records summary status as pending or failed.

## Interaction Contract

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| CLI `evidence index` | Index new artifacts | Artifact path or run scope | Writes artifact index records | `evidence list` shows records after restart | Local Operator, automation |
| CLI `evidence list` | List artifacts | No editable state | None | Reads artifact index | Local Operator, Reviewer |
| CLI `evidence show` | Show redacted summary | No editable state | None | Reads summary and retrieval metadata | Local Operator, Reviewer |
| MCP `nebula_evidence_list` | Query artifact summaries | No editable state | None | Reads same artifact index | Reviewer, Local Operator |

Required checks for mutation stories:
- [ ] Artifact index validates path boundaries.
- [ ] Redaction status gates summary exposure.
- [ ] Missing artifacts are reported without crashing.
- [ ] Tests cover valid artifact, outside path, missing artifact, duplicate content, and failed redaction.

## Data Requirements

**Required Fields:**
- `artifact_id`: Stable artifact identifier.
- `run_id`: Producing run.
- `artifact_kind`: Transcript, command-log, validator-output, manifest, status, metric, or learning-proposal.
- `source_path`: Local path to full artifact.
- `summary_path`: Local path to redacted summary.
- `created_at`: Artifact creation timestamp.
- `redaction_status`: Pass, Fail, Pending, or NotRequired.
- `retrieval_policy`: LocalOnly, SummaryOnly, Blocked, or Missing.

**Optional Fields:**
- `content_hash`: Hash for duplicate detection.
- `freshness_status`: Fresh, stale, missing, or unknown.
- `related_gate`: Gate associated with the artifact.
- `validator_name`: Validator associated with the artifact.

**Validation Rules:**
- Source and summary paths must be inside approved workspace, runtime, or evidence directories.
- Artifact IDs must be stable across reloads.
- Failed redaction blocks summary exposure through CLI and MCP.
- Retrieval metadata must include enough information to locate the full artifact locally.

## Role-Based Visibility

**Roles that can inspect artifacts:**
- Local Operator - Can index and inspect local artifacts.
- Reviewer - Can inspect summaries and permitted local retrieval metadata.
- Security Reviewer - Can inspect redaction failures and path policy violations.

**Data Visibility:**
- InternalOnly content: Full local paths and raw artifact content.
- ExternalVisible content: Redacted summaries and artifact IDs.

## Non-Functional Expectations

- Performance: Listing artifacts for a run completes within 1 second for normal run sizes.
- Reliability: Index writes are atomic or recoverable.
- Security: Path traversal and symlink escapes are rejected before indexing.
- Authorization: Artifact indexing requires local write permissions to the runtime index; artifact inspection requires local read permissions for the index and approved evidence paths.

## Dependencies

**Depends On:**
- F0003-S0001 run registry.

**Related Stories:**
- F0003-S0005 writes summary artifacts.
- F0003-S0003 exposes artifact summaries through MCP.

## Business Rules

1. Full artifact is authoritative: Summaries never replace source evidence.
2. Local boundary: Retrieval paths stay local and bounded.
3. Redaction before exposure: Failed redaction blocks summary display.

## Out of Scope

- Remote artifact storage.
- Long-term artifact archival.
- Raw artifact streaming through MCP.

## UI/UX Notes

- Command surfaces involved: `evidence index`, `evidence list`, `evidence show`.
- Key interactions: List artifacts, inspect summary, copy local retrieval path.

## Questions & Assumptions

**Open Questions:**
- [ ] Should artifact IDs include run prefixes for human scanning or remain opaque?

**Assumptions (to be validated):**
- Local filesystem storage is sufficient for the first runtime implementation.

## Definition of Done

- [ ] Acceptance criteria met
- [ ] Edge cases handled
- [ ] Permissions enforced for path boundaries and redaction status
- [ ] Audit/timeline logged for artifact indexing and policy violations
- [ ] Tests cover artifact index behavior and retrieval policies
- [ ] Documentation updated
- [ ] Story filename matches `Story ID` prefix
- [ ] Story index regenerated or updated

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

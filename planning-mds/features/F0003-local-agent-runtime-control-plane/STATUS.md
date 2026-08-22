# F0003 - Local Agent Runtime Control Plane - Status

**Overall Status:** Phase B architecture drafted; pending operator approval before the `feature` action
**Last Updated:** 2026-08-21

## Phase B Architecture (drafted 2026-08-19)

| Deliverable | State | Location |
|-------------|-------|----------|
| Technical architecture | Drafted | `planning-mds/BLUEPRINT.md` §5 |
| Runtime contract (CLI + MCP + records) | Drafted | `planning-mds/architecture/f0003-runtime-contract.md` |
| ADRs | 5 authored, all `Proposed` | `ADR-005` … `ADR-009` |
| Solution patterns | §12 added; §1 MCP prohibition narrowed | `planning-mds/architecture/SOLUTION-PATTERNS.md` |
| Data model | F0003 records added | `planning-mds/architecture/data-model.md` |
| JSON schemas | 6 authored and schema-valid | `planning-mds/schemas/f0003-*.schema.json` |
| Ontology bindings | Complete; `coverage_excluded` removed | `planning-mds/kg-source/features/F0003.yaml` + 13 node shards |

Exit validation is green: `validate-stories`, `generate-story-index`, `validate-trackers`,
`kg --write-coverage-report`, `kg --check-drift`, `kg --check-reproducible`, and
`validate_templates` all pass, as do the six framework lifecycle gates.

**The Phase B approval checkpoint is outstanding.** The five ADRs stay `Proposed` until the
operator approves; approval is recorded in BLUEPRINT §5.9 and flips them to `Accepted`.

## Plan-Review Findings

### Re-run `2026-08-20-45b7ccd8` — verdict CONDITIONALLY READY (`requires_justification: true`)

First recorded readiness verdict for F0003; all five gates PR0-PR4 executed.

| ID | Severity | Finding | State |
|----|----------|---------|-------|
| N1 | High | PRD contradicted its own CLI-only decision at lines 38, 56, 97, 141 | **Resolved 2026-08-21** — all four reconciled; line 56's acceptance criterion now names `metrics --run <id>` |
| N2 | High | `security/f0001-authorization-model.md` omitted F0003's three actions | **Resolved 2026-08-21** — *F0003 Action Extensions* section added with the role matrix and the target-document rule for `DecideProposal` |
| N3 | Low | STATUS *Runtime Progress* had no item for S0007 | **Resolved 2026-08-21** |
| M1 | Medium | S0003 MCP install vs manual host configuration | Open (deferred by owner) |
| L1 | Low | S0001 open question unreconciled against ADR-005 | Open (deferred by owner) |

With N1 and N2 resolved, a further re-run should compute READY on severity alone. The
recorded verdict remains CONDITIONALLY READY until a gate produces a new one.

### Superseded run `2026-08-19-ec0a97ce` — verdict NOT READY

| ID | Severity | Finding | State |
|----|----------|---------|-------|
| C1 | Critical | Artifact-identity base directory ambiguous across S0004's three approved roots | **Resolved 2026-08-21** — ADR-006 revised to root-scoped identity with a `root_key` discriminator and longest-match root selection; propagated to 3 schemas, the runtime contract, data-model, and BLUEPRINT §5.2 |
| C2 | Critical | Operator surfaces undefined — five PRD screens and the proposal-decision surface | **Resolved 2026-08-21** — operator chose **CLI-only**. PRD screen table replaced by a command-surface table; `learn decide` defined as the proposal-decision command; terminal UI deferred to F0008 |
| H1 | High | No authorization action for proposal decisions; `RunValidator` overloaded | **Resolved 2026-08-21** — added `IndexEvidence`, `DraftProposal`, `DecideProposal`; `RunValidator` returned to its F0001 meaning (the `validate` command alone) |
| H2 | High | `RuntimeMetricSnapshot` declared as a record with no schema | **Resolved 2026-08-21** — `f0003-metric-snapshot.schema.json` added with a closed metric-name set and a `derived_from` block pinning the revisions a snapshot was computed against |
| H3 | High | Query/command split is an unscoped refactor of F0001 code that no story owns | **Resolved 2026-08-21** — F0003-S0007 authored to own it, with the 514 existing engine tests and the audit stream as its regression boundary |
| H4 | High | `coverage-report.yaml` committed stale in PR #64 | **Resolved** — regenerated |
| M1 | Medium | S0003 open question (MCP install vs manual host config) unanswered | Open |
| M2 | Medium | ADR-006 deferred digest length to G0 while the schema pinned 12 hex | **Resolved 2026-08-21** — 12 fixed in the ADR; the contradictory follow-up removed |
| L1 | Low | S0001 open question answered by ADR-005 but not reconciled in the story | Open |

No critical or high findings remain. M1 and L1 are open, both non-blocking under the
`review-family` profile (critical = 0 + high = 0 → READY on severity alone). Re-run
`plan-review` before the Phase B approval so the verdict rests on gate evidence rather
than on this table: the PR4 readiness gate has never executed, since the original run
halted at PR2 on H4.

## Story Checklist

| Story | Title | Status |
|-------|-------|--------|
| F0003-S0001 | Runtime command surface and wrap launch | [ ] Not Started |
| F0003-S0002 | Provider capability matrix and launch guards | [ ] Not Started |
| F0003-S0003 | MCP status and evidence tools | [ ] Not Started |
| F0003-S0004 | Evidence artifact store and retrieval index | [ ] Not Started |
| F0003-S0005 | Deterministic transcript, log, and validator summaries | [ ] Not Started |
| F0003-S0006 | Runtime metrics and failure-learning review | [ ] Not Started |
| F0003-S0007 | Application query/command service split | [ ] Not Started (prerequisite for S0003) |

## Runtime Progress

- [ ] Local command surface implemented
- [ ] Wrapped launch records run metadata
- [ ] Session status reconciles against real local session state
- [ ] Provider capability reports and launch guards implemented
- [ ] MCP read-only status tools implemented
- [ ] Evidence artifact store and retrieval index implemented
- [ ] Deterministic summarizers implemented
- [ ] Metrics command implemented (CLI-only; no dashboard — see PRD *UX / Surfaces*)
- [ ] Failure-learning proposal review flow implemented
- [ ] Application query/command service split implemented (S0007; prerequisite for the MCP surface)

## Cross-Cutting

- [x] Story validator passes
- [x] Tracker validator passes
- [ ] Security review of redaction and retrieval boundaries completed
- [~] Architecture review of runtime contract drafted; operator approval outstanding
- [ ] Tests cover command surface, MCP tools, artifact retrieval, summaries, metrics, and proposal workflow

## Required Signoff Roles (Set in Planning)

| Role | Required | Why Required | Set By | Date |
|------|----------|--------------|--------|------|
| Quality Engineer | Yes | Validates command behavior, status contracts, artifact retrieval, summaries, and metrics. | Architect | 2026-06-24 |
| Code Reviewer | Yes | Reviews runtime command implementation, tool contracts, and persistence boundaries. | Architect | 2026-06-24 |
| Security Reviewer | Yes | Reviews redaction, local path constraints, MCP read-only boundaries, and proposal safety. | Architect | 2026-06-24 |
| DevOps | No | Local-only runtime layer unless a later feature adds hosted operation. | Architect | 2026-06-24 |
| Architect | Yes | Required for runtime contract and F0002 handoff approval. | Architect | 2026-06-24 |

## Story Signoff Provenance

Complete this before moving `Overall Status` to `Done` or `Archived`.

| Story | Role | Reviewer | Verdict | Evidence | Date | Notes |
|-------|------|----------|---------|----------|------|-------|
| F0003-S0001 | Quality Engineer | TBD | TBD | TBD | TBD | Pending implementation |
| F0003-S0001 | Code Reviewer | TBD | TBD | TBD | TBD | Pending implementation |
| F0003-S0001 | Security Reviewer | TBD | TBD | TBD | TBD | Pending implementation |
| F0003-S0001 | Architect | TBD | TBD | TBD | TBD | Pending implementation |

## Deferred Non-Blocking Follow-ups

| Follow-up | Why deferred | Tracking link | Owner |
|-----------|--------------|---------------|-------|

## Closeout Summary

| Field | Value |
|-------|-------|
| Implementation completed | TBD |
| Closeout review date | TBD |
| Total stories | 7 |
| Stories completed | 0 / 7 |
| Test count (unit + integration) | TBD |
| Defects found during review | TBD |
| Defects fixed before closeout | TBD |
| Residual risks | TBD |

## Tracker Sync Checklist

- [x] `planning-mds/features/REGISTRY.md` status/path aligned
- [x] `planning-mds/features/ROADMAP.md` section aligned
- [x] `planning-mds/features/STORY-INDEX.md` regenerated or updated
- [x] `planning-mds/BLUEPRINT.md` feature/story status links aligned (F0003 was absent from the Feature Plan before 2026-08-19; added with all stories, now seven)
- [ ] Every required signoff role has story-level `PASS` entries with reviewer, date, and evidence

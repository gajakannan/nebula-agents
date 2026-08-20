# F0003 - Local Agent Runtime Control Plane - Status

**Overall Status:** Phase B architecture drafted; pending operator approval before the `feature` action
**Last Updated:** 2026-08-19

## Phase B Architecture (drafted 2026-08-19)

| Deliverable | State | Location |
|-------------|-------|----------|
| Technical architecture | Drafted | `planning-mds/BLUEPRINT.md` §5 |
| Runtime contract (CLI + MCP + records) | Drafted | `planning-mds/architecture/f0003-runtime-contract.md` |
| ADRs | 5 authored, all `Proposed` | `ADR-005` … `ADR-009` |
| Solution patterns | §12 added; §1 MCP prohibition narrowed | `planning-mds/architecture/SOLUTION-PATTERNS.md` |
| Data model | F0003 records added | `planning-mds/architecture/data-model.md` |
| JSON schemas | 5 authored and schema-valid | `planning-mds/schemas/f0003-*.schema.json` |
| Ontology bindings | Complete; `coverage_excluded` removed | `planning-mds/kg-source/features/F0003.yaml` + 12 node shards |

Exit validation is green: `validate-stories`, `generate-story-index`, `validate-trackers`,
`kg --write-coverage-report`, `kg --check-drift`, `kg --check-reproducible`, and
`validate_templates` all pass, as do the six framework lifecycle gates.

**The Phase B approval checkpoint is outstanding.** The five ADRs stay `Proposed` until the
operator approves; approval is recorded in BLUEPRINT §5.9 and flips them to `Accepted`.

## Story Checklist

| Story | Title | Status |
|-------|-------|--------|
| F0003-S0001 | Runtime command surface and wrap launch | [ ] Not Started |
| F0003-S0002 | Provider capability matrix and launch guards | [ ] Not Started |
| F0003-S0003 | MCP status and evidence tools | [ ] Not Started |
| F0003-S0004 | Evidence artifact store and retrieval index | [ ] Not Started |
| F0003-S0005 | Deterministic transcript, log, and validator summaries | [ ] Not Started |
| F0003-S0006 | Runtime metrics and failure-learning review | [ ] Not Started |

## Runtime Progress

- [ ] Local command surface implemented
- [ ] Wrapped launch records run metadata
- [ ] Session status reconciles against real local session state
- [ ] Provider capability reports and launch guards implemented
- [ ] MCP read-only status tools implemented
- [ ] Evidence artifact store and retrieval index implemented
- [ ] Deterministic summarizers implemented
- [ ] Metrics dashboard or status view implemented
- [ ] Failure-learning proposal review flow implemented

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
| Total stories | 6 |
| Stories completed | 0 / 6 |
| Test count (unit + integration) | TBD |
| Defects found during review | TBD |
| Defects fixed before closeout | TBD |
| Residual risks | TBD |

## Tracker Sync Checklist

- [x] `planning-mds/features/REGISTRY.md` status/path aligned
- [x] `planning-mds/features/ROADMAP.md` section aligned
- [x] `planning-mds/features/STORY-INDEX.md` regenerated or updated
- [x] `planning-mds/BLUEPRINT.md` feature/story status links aligned (F0003 was absent from the Feature Plan before 2026-08-19; added with all six stories)
- [ ] Every required signoff role has story-level `PASS` entries with reviewer, date, and evidence

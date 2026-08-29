# F0003 - Local Agent Runtime Control Plane - Status

**Overall Status:** In Progress — `feature` action run `2026-08-29-16075bda`, **G0-G1 PASS**; Step 1 (S0007) implemented, Checkpoint A met
**Last Updated:** 2026-08-29

## Phase B Architecture (drafted 2026-08-19)

| Deliverable | State | Location |
|-------------|-------|----------|
| Technical architecture | Drafted | `planning-mds/BLUEPRINT.md` §5 |
| Runtime contract (CLI + MCP + records) | Drafted | `planning-mds/architecture/f0003-runtime-contract.md` |
| ADRs | 5 authored, all `Accepted` | `ADR-005` … `ADR-009` |
| Solution patterns | §12 added; §1 MCP prohibition narrowed | `planning-mds/architecture/SOLUTION-PATTERNS.md` |
| Data model | F0003 records added | `planning-mds/architecture/data-model.md` |
| JSON schemas | 6 authored and schema-valid | `planning-mds/schemas/f0003-*.schema.json` |
| Ontology bindings | Complete; `coverage_excluded` removed | `planning-mds/kg-source/features/F0003.yaml` + 13 node shards |

Exit validation is green: `validate-stories`, `generate-story-index`, `validate-trackers`,
`kg --write-coverage-report`, `kg --check-drift`, `kg --check-reproducible`, and
`validate_templates` all pass, as do the six framework lifecycle gates.

**The Phase B approval checkpoint is closed.** The operator approved at
`2026-08-29T11:15:45-04:00` against plan-review run `2026-08-22-5ed12b9c` (verdict READY,
`requires_justification: false`). The five ADRs are `Accepted` and the approval is recorded
in BLUEPRINT §5.9.

## Feature Action — run `2026-08-29-16075bda`

| Gate | Role | State | Evidence |
|------|------|-------|----------|
| G0 Architect assembly plan | Architect | **PASS** 2026-08-29 | `g0-assembly-plan-validation.md` |
| G1 Runtime preflight | DevOps | **PASS** 2026-08-29 | `g1-runtime-preflight.md` |
| G2 Self-review + QE + deployability | QE, DevOps | Not started | — |
| G3 Code + security review | Code Reviewer, Security | Not started | — |
| G4 Approval | Operator | Not started | — |
| G5 Signoff | PM | Not started | — |
| G6 Candidate evidence | PM | Not started | — |
| G7 KG reconciliation | Architect | Not started | — |
| G8 Closeout | PM | Not started | — |

The assembly plan is
[`feature-assembly-plan.md`](./feature-assembly-plan.md) — 8 build steps, all 7 stories
covered. **Step 1 (S0007, the query/command facade split) lands first and alone**, because
the MCP adapter cannot be constructed with a query-only facade that does not yet exist, and
because the 514 existing engine tests are that step's regression boundary.

This run is also F0007-S0009's live governed pilot; F0007 cannot reach closeout without it.

### Step 1 — S0007 query/command facade split · Checkpoint A met

| Criterion | Result |
|-----------|--------|
| 514 existing engine tests pass **unmodified** | PASS — 522 total (514 + 8 new guards) |
| Audit stream byte-identical across the split | PASS — pre/post captured from `main` vs this tree and diffed; see `artifacts/facade-split/` |
| Query-facade operations append **zero** runtime events | PASS — the stream is exactly the two launch events |
| Adding a mutating method to the query facade fails the build | PASS — proven by injecting each failure and observing the guard fire |
| Executing the whole query surface leaves the runtime tree untouched | PASS — asserted against an **absent** runtime root, which must stay absent |
| Neither facade reaches the other | PASS |

`CommandService` holds `runs`, `gates`, `transcripts`. `QueryService` is the read facade
and declares `QUERY_SURFACE`. `PreflightService` sits on the read side because it only
inspects — the runtime directory is created by the first authorized mutation, not by
probing for it.

`Application` declares `queries`, `commands`, `preflight`, `identity`; `runs`, `gates`, and
`transcripts` are properties delegating to `commands`. That delegation is what lets the
514 existing tests pass without one of them being rewritten — see *Deviations* below.

## Plan-Review Findings

### Re-run `2026-08-20-45b7ccd8` — verdict CONDITIONALLY READY (`requires_justification: true`)

First recorded readiness verdict for F0003; all five gates PR0-PR4 executed.

| ID | Severity | Finding | State |
|----|----------|---------|-------|
| N1 | High | PRD contradicted its own CLI-only decision at lines 38, 56, 97, 141 | **Resolved 2026-08-21** — all four reconciled; line 56's acceptance criterion now names `metrics --run <id>` |
| N2 | High | `security/f0001-authorization-model.md` omitted F0003's three actions | **Resolved 2026-08-21** — *F0003 Action Extensions* section added with the role matrix and the target-document rule for `DecideProposal` |
| N3 | Low | STATUS *Runtime Progress* had no item for S0007 | **Resolved 2026-08-21** |
| N4 | Medium | `F0003-S0004` line 15 and `F0003-S0001` line 130 still described a dashboard/TUI surface | **Resolved 2026-08-23** — reworded to the command surface; swept on the generic terms `dashboard`/`TUI`/`GUI` rather than the five screen names, which is what let this survive three runs |
| M1 | Medium | S0003 MCP install vs manual host configuration | Open (deferred by owner) |
| L1 | Low | S0001 open question unreconciled against ADR-005 | Open (deferred by owner) |

Superseded by run `2026-08-22-5ed12b9c`, which computed **READY** (critical = 0, high = 0,
`requires_justification: false`) and is the verdict the Phase B approval was recorded
against.

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

No critical or high findings remain. M1 and L1 stay open by owner decision, both
non-blocking under the `review-family` profile. The PR4 readiness gate — which never
executed in this run, because it halted at PR2 on H4 — ran to completion in
`2026-08-22-5ed12b9c`, so the recorded verdict rests on gate evidence rather than on this
table.

## Story Checklist

| Story | Title | Status |
|-------|-------|--------|
| F0003-S0001 | Runtime command surface and wrap launch | [ ] Not Started |
| F0003-S0002 | Provider capability matrix and launch guards | [ ] Not Started |
| F0003-S0003 | MCP status and evidence tools | [ ] Not Started |
| F0003-S0004 | Evidence artifact store and retrieval index | [ ] Not Started |
| F0003-S0005 | Deterministic transcript, log, and validator summaries | [ ] Not Started |
| F0003-S0006 | Runtime metrics and failure-learning review | [ ] Not Started |
| F0003-S0007 | Application query/command service split | [x] **Implemented** 2026-08-29 (Step 1; prerequisite for S0003) |

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
- [x] Application query/command service split implemented (S0007; prerequisite for the MCP surface)

## Cross-Cutting

- [x] Story validator passes
- [x] Tracker validator passes
- [ ] Security review of redaction and retrieval boundaries completed
- [x] Architecture review of runtime contract complete; operator approved 2026-08-29 (BLUEPRINT §5.9)
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

## Deviations From the Assembly Plan

| Plan said | Built | Why |
|-----------|-------|-----|
| `Application` exposes exactly two facades plus `identity` | `Application` also declares `preflight`, and exposes `runs`/`gates`/`transcripts` as delegating properties | The two statements were in tension. `test_bootstrap.py` asserts `isinstance(application.runs, RunService)` and several tests monkeypatch `application.queries.status`, `application.gates.run_validator`, and `application.preflight.run`. The literal two-field shape would have required rewriting those tests, which S0007 forbids. The properties return **the same objects** `commands` holds, so there is one owner per service and no second path; the guarantee ADR-007 needs — that the MCP adapter receives only the read facade — is unaffected. |

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

# Plan Review Report — F0003 Local Agent Runtime Control Plane (re-run)

- **Run:** `2026-08-20-45b7ccd8` · supersedes `2026-08-19-ec0a97ce`
- **PLAN_SCOPE:** `feature` · **TARGET:** `F0003`
- **Contract:** Feature Evidence Contract, scope `read-only-audit`, version `2026-07-11`
- **Diff range:** `f7b7f5c..bfc4718` (Phase B package plus remediation from #66 and #68)

## Decision

**CONDITIONALLY READY.**

`review-family` arithmetic: critical = 0, high = 2 → CONDITIONALLY READY. Fix before
`feature.md` G0, or capture explicit risk acceptance with an owner and target date.

Both criticals from the prior run are genuinely resolved, not relocated. The identity rule
is now defined for every approved root, and the operator surface is decided and complete
enough to build against. Neither high finding blocks an implementer from starting; both
are internal inconsistencies that will mislead a reader who happens to open the wrong
section first.

Notably, **both new findings were introduced by the remediation itself** — each is a case
where a fix changed one section while the claim it changed also appeared elsewhere. That
is the specific failure mode this re-run was scoped to look for.

## Findings By Severity

| ID | Severity | Finding | Owner |
|----|----------|---------|-------|
| N1 | High | The PRD contradicts its own CLI-only decision in four places outside the revised section | PM |
| N2 | High | The security-owned authorization model does not carry F0003's three new actions | Architect + Security |
| N3 | Low | STATUS *Runtime Progress* has no checklist item for S0007 | PM |
| M1 | Medium | S0003's open question (MCP install vs manual host configuration) still unanswered | PM |
| L1 | Low | S0001's open question answered by ADR-005 but the story is still unreconciled | PM |

M1 and L1 carry over unresolved from the prior run by the owner's choice, and are restated
rather than re-argued.

## Prior-Finding Verification

Each prior finding was re-checked against artifacts rather than accepted from the
remediation's own description.

| Prior | Claim | Verified |
|-------|-------|----------|
| C1 | Root-scoped identity with `root_key` and longest-match selection | **Resolved.** ADR-006 defines selection over all three approved roots with a documented tiebreak; the rule now has a value for artifacts outside the run directory, which was the defect. Propagated to all three id patterns and the new `source_root` field |
| C2 | CLI-only; `learn decide` defined | **Resolved**, with N1 attached. The command exists with inputs, authorization, and semantics; "the review surface" no longer appears anywhere |
| H1 | Three actions added; `RunValidator` narrowed | **Resolved**, with N2 attached. BLUEPRINT §5.4 and the contract agree |
| H2 | Metric snapshot schema | **Resolved.** Schema exists and is valid; the closed `metric_name` enum covers every metric S0006's acceptance criteria name |
| H3 | S0007 owns the query/command split | **Resolved.** Story exists, passes validation, declares the 514 engine tests and the audit stream as its regression boundary, and is registered in the shard, trackers, and index |
| H4 | Coverage report regenerated | **Resolved.** Plain `validate.py` exits clean — see Validation Evidence |
| M2 | Digest length fixed at 12 | **Resolved.** The contradictory G0 follow-up is gone |

No prior finding was found to have been relocated rather than fixed.

## Product Readiness

*Owner: Product Manager*

**Strong, with one internal contradiction.** Seven stories now pass `validate-stories.py`
with no issues, including the newly added S0007. Acceptance criteria remain concrete and
fixture-ready.

**N1 (high).** The CLI-only decision is stated unambiguously in the PRD's *UX / Surfaces*
section, in BLUEPRINT §5.1 and §5.8, and in the runtime contract §1. But four statements
elsewhere in the same PRD still describe a graphical surface:

| Line | Text |
|------|------|
| 38 | *In Scope* — "Runtime metrics **dashboard** for run duration, gate wait time…" |
| 56 | *Acceptance Criteria Overview* — "Runtime metrics are visible in a local **dashboard** or status view" |
| 97 | *Runtime Flow Diagram* — "CLI or **TUI**" |
| 141 | "while CLI, **TUI**, and MCP surfaces read the same structured state" |

Line 56 is the sharpest, because an acceptance criterion is what a QE writes tests from: as
written, F0003 is not done until metrics appear in a dashboard the feature has decided not
to build. Line 38 has the same problem for scope.

A careful reader resolves this — the *UX / Surfaces* section is dated and explicit, and
BLUEPRINT §5.8 records the decision — which is why this is high rather than critical. But a
requirements document that contradicts itself on a scope boundary will mislead somebody,
and the cost of fixing it is four lines.

**N3 (low).** STATUS *Runtime Progress* lists nine implementation checkboxes covering
S0001–S0006 but none for S0007's query/command split, so a reader tracking progress
against that list would not see the refactor at all.

## Architecture Readiness

*Owner: Architect*

**Materially improved.** ADR-006's revision is the substantive fix: root selection is now
defined by longest-match across the three approved roots with an explicit tiebreak, which
holds under any nesting and under a relocated `NEBULA_AGENTS_RUNTIME_DIR`. The rejected
alternatives are recorded with reasons, including two — workspace-relative always, and
absolute-path digests — that are attractive and wrong for reasons worth having written
down. The `source_root` field makes an index entry self-describing.

The action split is likewise sound. `RunValidator` returning to its F0001 meaning removes a
genuine semantic overload, and separating `DraftProposal` from `DecideProposal` prevents an
automated caller from approving its own proposals — a real escalation path, closed by
construction rather than by policy.

The metric schema's `derived_from` block deserves note: S0006 requires metrics to be
"recomputable from runtime state and artifact index", and pinning the revisions a snapshot
was computed against turns that from an assertion into something a reader can check.

**N2 (high).** `planning-mds/security/f0001-authorization-model.md` line 17 enumerates the
authoritative action set — `Probe`, `Launch`, `Attach`, `ReadState`, `RunValidator`,
`DecideGate`, `ConfigureTranscript` — and its per-role allow/deny matrix at lines 26–30
covers those actions only. F0003's three new actions appear in BLUEPRINT §5.4 and the
runtime contract, but not here.

This matters more than a normal doc-sync gap because of who reads it. F0003 lists Security
Reviewer as a **required** signoff role, specifically for "MCP read-only boundaries and
proposal safety". The document that reviewer opens to check the authorization surface does
not mention `DecideProposal`, the action guarding the one operation in F0003 that can
change framework instructions. A signoff given against that document would be given
against an incomplete picture.

The fix is small — extend the action list and the role matrix, and state that
`DecideProposal` is evaluated against the target document rather than the run. But it
should precede the security signoff, not follow it.

## Buildability Challenge

*Owner: Code Reviewer*

**Buildable.** The gap that made the prior run's H3 a real risk is closed: S0007 owns the
query/command split, and its acceptance criteria are unusually well-suited to a refactor —
the existing 514 engine tests pass unmodified, the audit stream is byte-identical for an
identical operation sequence, and a test asserts the query facade is mutation-free by
construction so a future mutating method fails the build rather than silently widening the
MCP surface.

`learn decide` is specified to the level an implementer needs: inputs, the enumerated
decision values, which of them require `--reason`, append-only semantics, the authorization
action, and an explicit statement that it never opens the target document.

The six schemas are valid against Draft 2020-12 and their constraints match the prose. The
new `artifact_id` pattern accepts exactly the three root keys and rejects both the old
format and an unknown key.

**No new buildability findings.** Two prior non-findings are restated so they are not
re-raised: the absence of `feature-assembly-plan.md` is correct (the `feature` action
authors it at G0, and the spec forbids treating it as a plan deliverable), and story
sequencing is a G0 concern — S0007's prerequisite relationship to S0003 is declared in both
stories, which is the appropriate level for Phase B.

The five ADRs standing at `Proposed` remains the expected state for a package whose
approval checkpoint is deliberately open.

## Validation Evidence

All five PR2 validators executed through `run-gate.py` and completed. See `commands.log`
and `lifecycle-gates.log`.

| Validator | Result |
|-----------|--------|
| `validate-stories.py` (F0003) | PASS — 7 stories, no issues |
| `validate-trackers.py` | PASS — 0 errors, 0 warnings |
| `scripts/kg/validate.py` | **PASS** — H4 resolved; the stale coverage report that halted the prior run at PR2 is gone |
| `scripts/kg/validate.py --check-drift` | PASS |
| `validate_templates.py` | PASS |

PR2 completed this time, so the readiness gate rests on executed validator evidence rather
than on inspection alone.

Supporting checks recorded in `commands.log`:

- Six `f0003-*.schema.json` valid against Draft 2020-12; the `artifact_id` pattern
  exercised for `ws`, `rt`, `ev` plus old-format and unknown-key rejection; a sample metric
  snapshot validated against its schema.
- Six lifecycle gates pass; `--check-reproducible` OK.
- `run-gate.py` resolved `feature_slug` from the run manifest without `--feature-slug`,
  confirming the prior run's low-severity driver defect is fixed.

## Artifact Trace

Read-only. Artifacts read:

| Artifact | Role in the review |
|----------|--------------------|
| `F0003-.../PRD.md` | Scope, acceptance criteria, surfaces — evidence for N1 (lines 38, 56, 97, 141) |
| `F0003-.../F0003-S0001..S0007*.md` | Acceptance criteria, interaction contracts, open questions |
| `BLUEPRINT.md` §5 | Boundaries, data model, workflow, authorization, NFRs |
| `architecture/f0003-runtime-contract.md` | Commands, MCP tools, records, exit codes, schemas |
| `architecture/decisions/ADR-005..009*.md` | Decisions, options, revision history |
| `architecture/SOLUTION-PATTERNS.md` §1, §12 | Pattern compliance |
| `architecture/data-model.md` | Record table, identity rule, persistence layout |
| `security/f0001-authorization-model.md` | Action set and role matrix — evidence for N2 (lines 17, 26–30) |
| `schemas/f0003-*.schema.json` (6) | Shape conformance and Draft 2020-12 validity |
| `kg-source/features/F0003.yaml` + node shards | Traceability bindings |
| Prior run `2026-08-19-ec0a97ce` | Finding set being verified, not inherited |

## Routing

| Finding | Routes to | Suggested resolution |
|---------|-----------|----------------------|
| N1 | `plan.md` Phase A — PM | Revise PRD lines 38, 56, 97, 141 to match the CLI-only decision |
| N2 | `plan.md` Phase B — Architect + Security | Add the three actions and their role matrix to `f0001-authorization-model.md` before the security signoff |
| N3 | `plan.md` Phase A — PM | Add a Runtime Progress item for the query/command split |
| M1 | `plan.md` Phase B — PM | Answer the MCP host-configuration question |
| L1 | `plan.md` Phase A — PM | Close S0001's open question against ADR-005 |

None of these require re-opening an ADR or changing a decision. All five are text
reconciliation against decisions already made.

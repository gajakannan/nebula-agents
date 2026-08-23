# Plan Review Report — F0003 Local Agent Runtime Control Plane (third run)

- **Run:** `2026-08-22-5ed12b9c` · supersedes `2026-08-20-45b7ccd8`
- **PLAN_SCOPE:** `feature` · **TARGET:** `F0003`
- **Contract:** Feature Evidence Contract, scope `read-only-audit`, version `2026-07-11`
- **Diff range:** `fb78c2d..169eaef` (N1/N2/N3 remediation, PR #70)

## Decision

**READY.**

`review-family` arithmetic: critical = 0, high = 0 → READY. Computed by `gate_policy.py`,
not asserted here.

Both high findings from the previous run are resolved. F0003's planning package is
complete enough for a competent implementation agent to begin `feature.md` G0 without
inventing product rules, architecture decisions, contracts, workflow states, authorization
rules, or acceptance criteria.

One new medium finding (N4) and two carried-over items (M1, L1) remain. None blocks entry
to G0 under the severity profile, and all three are text-level.

## Findings By Severity

| ID | Severity | Finding | Owner |
|----|----------|---------|-------|
| N4 | Medium | Two story files still describe a dashboard/TUI surface, contradicting the CLI-only decision | PM |
| M1 | Medium | S0003's open question (MCP install vs manual host configuration) unanswered | PM |
| L1 | Low | S0001's open question answered by ADR-005 but the story is unreconciled | PM |

## Prior-Finding Verification

| Prior | Verified |
|-------|----------|
| N1 | **Resolved in the PRD.** All four flagged lines now match the CLI-only decision; the acceptance criterion at former line 56 names `nebula-agents metrics --run <run_id>` in table and JSON form, so a QE writing tests from it can no longer conclude a dashboard is required. The flow-diagram box alignment survived the edit. **Partially incomplete outside the PRD — see N4.** |
| N2 | **Resolved.** `security/f0001-authorization-model.md` now carries all three actions in its action set and a dedicated *F0003 Action Extensions* section. Cross-checked against BLUEPRINT §5.4 and the runtime contract: `IndexEvidence`, `DraftProposal`, and `DecideProposal` appear in all three with consistent semantics, and the target-class role mapping (Security Reviewer / Architect / Product Manager) is identical in the security doc, BLUEPRINT §5.4, and ADR-009. `RunValidator` is narrowed to the `validate` command in every location that mentions it. |
| N3 | **Resolved.** STATUS *Runtime Progress* now carries an S0007 item, marked as a prerequisite for the MCP surface. |

## Product Readiness

*Owner: Product Manager*

**Ready.** Seven stories pass `validate-stories.py` with no issues. The PRD is now
internally consistent on its scope boundary: *In Scope*, the acceptance criteria, the flow
diagram, and the closing prose all describe a command surface, and *UX / Surfaces* records
the decision with its date and rationale.

**N4 (medium).** The CLI-only reconciliation stopped at the PRD. Two story files still
describe the surface the feature decided not to build:

| File | Line | Text |
|------|------|------|
| `F0003-S0004` | 15 | *User Story* — "**So that** I can trace **dashboard** and MCP summaries back to full local evidence…" |
| `F0003-S0001` | 130 | *Assumptions* — "A local CLI surface is sufficient for the first **TUI** and MCP implementations to consume." |

S0004's is the more visible of the two: it sits in the User Story, the first substantive
line of the file, and states the story's purpose in terms of a surface that does not exist
in F0003. S0001's is an assumption rather than a requirement, and is arguably defensible —
a future F0008 TUI *would* consume this CLI — but as written it reads as an F0003
expectation.

Neither is an acceptance criterion, which is what separates this from N1: no test will be
written demanding a dashboard, and no scope statement promises one. That is why this is
medium rather than high. But it is the **third consecutive run** in which a
CLI-only reconciliation was applied to one document while the same claim survived in
another, and the fix is two lines.

The pattern is worth naming for the owner: the earlier sweeps searched for the five
specific screen *names* (Runtime Home, Capability Matrix, and so on), which were indeed
eliminated. The generic words "dashboard" and "TUI" were not part of that search, so they
persisted in files the named-screen sweep declared clean.

**M1 (medium), L1 (low).** Both carried over, deferred by the owner rather than missed.
Restated, not re-argued. M1 is a genuine open design question (`nebula-agents mcp install`
versus documented manual host configuration) and will need an answer before S0003 is built,
though not before G0 begins.

## Architecture Readiness

*Owner: Architect*

**Ready. No findings.**

The authorization model is now complete and consistent across its three homes. The security
document's *F0003 Action Extensions* section does the thing that was actually missing: it
states plainly that `DecideProposal`'s resource is the target document rather than the run,
and draws the consequence that owning a run does not confer the right to decide its
proposals. That is the sentence a Security Reviewer needs and could not previously find.

Two further points in that section are well-judged. Recording *why* `DraftProposal` and
`DecideProposal` are separate — a single capability would let an automated caller approve
its own proposals — preserves the reasoning against a future simplification that would
quietly reopen an escalation path. And the four added required tests are checkable rather
than aspirational, particularly the one asserting MCP calls cannot reach any of the three
actions through the query-only facade, which ties the authorization model to ADR-007's
structural guarantee.

Choosing to extend the existing document rather than rename it was correct: the BLUEPRINT
§4.7 reference stays valid, and the scope note at the top prevents a reader from concluding
the file is F0001-only.

The six schemas, five ADRs, runtime contract, data model, and SOLUTION-PATTERNS §12 are
unchanged since the previous run's verification and were re-read only where PR #70 touched
adjacent claims.

## Buildability Challenge

*Owner: Code Reviewer*

**Ready. No findings.**

Nothing in PR #70 changed a contract, schema, command surface, or story acceptance
criterion. The buildability assessment from `2026-08-20-45b7ccd8` therefore stands: the
CLI and MCP surfaces are specified to implementable detail, S0007 owns the query/command
refactor with the 514 existing engine tests and the audit stream as its regression
boundary, and `learn decide` is specified down to which decision values require `--reason`.

N4 does not affect buildability. An implementer reading S0004's User Story would build the
artifact index exactly as specified; the word "dashboard" in a *So that* clause changes no
acceptance criterion, no interaction contract, and no data requirement.

Restating two non-findings so they are not re-raised: the absence of
`feature-assembly-plan.md` is correct — the `feature` action authors it at G0 — and story
sequencing is a G0 concern. The five ADRs standing at `Proposed` remains the expected state
for a package whose approval checkpoint is deliberately open.

## Validation Evidence

All five PR2 validators executed through `run-gate.py` and completed.

| Validator | Result |
|-----------|--------|
| `validate-stories.py` (F0003) | PASS — 7 stories, no issues |
| `validate-trackers.py` | PASS — 0 errors, 0 warnings |
| `scripts/kg/validate.py` | PASS |
| `scripts/kg/validate.py --check-drift` | PASS |
| `validate_templates.py` | PASS |

Supporting checks recorded in `commands.log`:

- Six lifecycle gates pass; `--check-reproducible` OK.
- Repo-wide search for surface language across every F0003 artifact and the runtime
  contract — the evidence for N4, and for N1 being otherwise complete.
- Cross-document consistency check of the three new actions across the security model,
  BLUEPRINT §5.4, and the runtime contract.

## Artifact Trace

Read-only; writes confined to this run folder.

| Artifact | Used for |
|----------|----------|
| `F0003-.../PRD.md` | N1 verification — all four lines |
| `F0003-.../F0003-S0001..S0007*.md` | N4 evidence (S0004 line 15, S0001 line 130); M1, L1 |
| `security/f0001-authorization-model.md` | N2 verification — action set, role matrix, target-document rule |
| `BLUEPRINT.md` §4.4, §5.1, §5.4, §5.8 | Cross-document action consistency |
| `architecture/f0003-runtime-contract.md` | Command authorization column; `RunValidator` narrowing |
| `architecture/decisions/ADR-009*.md` | Target-class role mapping consistency |
| `F0003-.../STATUS.md` | N3 verification; finding history |
| Prior runs `2026-08-19-ec0a97ce`, `2026-08-20-45b7ccd8` | Finding history — read, not inherited |

## Routing

| Finding | Routes to | Suggested resolution |
|---------|-----------|----------------------|
| N4 | `plan.md` Phase A — PM | Reword S0004 line 15 and S0001 line 130 to the command surface. Two lines |
| M1 | `plan.md` Phase B — PM | Answer before S0003 is built; not required before G0 |
| L1 | `plan.md` Phase A — PM | Close S0001's open question against ADR-005 |

## Note for the Approver

This verdict clears the severity gate, but READY is a statement about the *planning
package*, not an approval. The Phase B approval checkpoint remains the operator's, and the
five ADRs remain `Proposed` until it is recorded.

N4 is genuinely optional before G0. Fixing it costs two lines; accepting it costs a reader
of S0004 briefly believing F0003 ships a dashboard. Either is defensible, and unlike the
previous run's `requires_justification: true`, no formal risk acceptance is required at
this severity.

# F0003 - Local Agent Runtime Control Plane - Status

**Overall Status:** In Progress — `feature` action run `2026-08-29-16075bda`, **G0-G7 PASS**; all 8 steps, all 7 stories, all signoffs, KG bound. **G8 (PM closeout) is the only gate left**
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
| G2 Self-review + QE + deployability | QE, DevOps | **PASS WITH RECOMMENDATIONS** 2026-08-29 | `g2-self-review.md`, `test-plan.md`, `test-execution-report.md`, `coverage-report.md`, `deployability-check.md` |
| G3 Code + security review | Code Reviewer, Security | **PASS WITH RECOMMENDATIONS** 2026-08-29 · severity ACCEPTABLE | `code-review-report.md`, `security-review-report.md` |
| G4 Approval | Operator | **APPROVED** 2026-08-29 | `gate-decisions.md` |
| G5 Signoff | PM | **PASS** 2026-08-30 | `signoff-ledger.md` |
| G6 Candidate evidence | QE | **PASS** 2026-08-30 | `feature-action-execution.md` |
| G7 KG reconciliation | Architect | **PASS** 2026-08-30 | `kg-reconciliation.md` |
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

### Step 2 — domain records, artifact identity, containment · Checkpoint B met

| Criterion | Result |
|-----------|--------|
| `artifact_id` stable across re-index, restart, and a **moved runtime root** | PASS |
| Longest-match root selection correct under all three nesting configurations | PASS — including a runtime root moved outside the workspace |
| Tie-break `runtime > evidence > workspace` exercised with colliding roots | PASS |
| A path outside all approved roots records a policy violation, does not crash | PASS — `PATH_DENIED`, exit 5 |
| Duplicate content yields distinct IDs linked by `content_hash` | PASS |
| A digest collision raises exit 6 and never overwrites | PASS |
| Records validate against the six committed JSON schemas | PASS — proven strict in both directions |
| Artifact IDs byte-identical across 3.11 / 3.12 / 3.14 | PASS |

New domain modules: `artifacts`, `summaries`, `capabilities`, `proposals`, `metrics`.
`enums` gains the F0003 vocabularies and the three authorization actions; `errors` gains
seven codes, all mapping to **existing** exit classes — contract `1.1` adds no new class.

Three invariants are enforced by construction rather than checked at call sites:
`redaction_status = Fail` forces `retrieval_policy = Blocked`; a summary that would drop
a failure marker for size becomes `Partial`, never `Pass`; and a proposal decision whose
reviewer role does not own the target document is refused where the decision is appended.

`ArtifactRedactionStatus` is deliberately **separate** from F0001's `RedactionStatus`
rather than merged — merging would change an F0001 record shape, which contract `1.1`
forbids. The bridge `artifact_redaction_of` is total, asserted by test, so a future F0001
member added without a mapping fails rather than silently defaulting to `Pass`.

### Step 3 — artifact index store and retrieval · S0004 substantially done

`FilesystemArtifactIndex` writes one atomic JSON document per run at
`{runtime_root}/runs/{run_id}/artifacts.json` — per-run lock, monotonic revision,
same-directory temp file, fsync, atomic replace, mode `0600`. It takes **its own** lock
rather than the run lock: the index is a projection and must never block a launch.

The ADR-002 primitives are **extracted** into `infrastructure/atomic.py` and shared with
`FilesystemRunRepository` rather than copied. A second hand-written locking and fsync
routine is how two copies drift — one gets a fix the other never sees. The 514 F0001 tests
verified the refactor changed no behavior.

CLI: `evidence index|list|show` are added as **optional subcommands** of the existing
`evidence` parser, so F0001's `evidence --run-id X` is untouched. `--run-id` moved off
`required=True` there, and the bare form's usage error moved into `main` — before the
application is built, matching how argparse behaved when it enforced it.

**Two findings, both recorded in the run's `gate-decisions.md`:**

| ID | Severity | Finding |
|----|----------|---------|
| S3-F1 | High | Contract `1.1` could not be "no F0001 schema changes": BLUEPRINT §5.3 requires indexing to append runtime events, and `event_type` is a closed enum. Resolved by extending the enum and correcting runtime-contract §9. **Architect confirmation needed at G3** |
| S3-F2 | Low | A G1 row claimed the six F0003 schemas load with "no registry change". The registry allowlisted `f0001-` only; the probe read a refusal as a validation. Corrected in the G1 artifact and replaced by a real test |

### Step 4 — provider capability matrix and the `wrap` guard · S0002 done

Six capabilities per provider, each with a **declared** requirement level rather than one
decided per probe. Two of those levels carry reasoning worth keeping:
`approval_visibility` is `required`, because preserving interactive approval prompts is
the reason F0003 stays tmux-native at all — a provider that cannot surface them fails the
premise rather than degrading quietly; `transcript` is `optional`, because Nebula captures
transcripts itself (ADR-004).

`wrap` is preflight + capability guard + F0001's `launch`, unchanged, in that order. The
ordering is the point and is asserted by test: a blocked launch creates no run and starts
no session. A stale report triggers a **re-probe**, not a warning — a guard deciding from
a report of unknown age is a guard in name only.

Probe output is redacted before persistence, tested against three secret shapes.

| ID | Severity | Finding |
|----|----------|---------|
| S4-F1 | Medium | A blocked launch has no run to append a runtime event to, because the guard deliberately runs before any run exists. The persisted capability report is the durable sanitized record. **Architect confirmation needed at G3** |

### Step 5 — deterministic summarizers · Checkpoint C met

| Criterion | Result |
|-----------|--------|
| Byte-identical across repeated calls | PASS |
| Byte-identical across **separate processes** | PASS — fresh interpreter, so nothing depends on hash seed or iteration order |
| Byte-identical across **3.11 / 3.12 / 3.14** | PASS — identical corpus digest `26bc7bec…` on all three |
| A truncation that would drop a failure marker yields `Partial`, not `Pass` | PASS |
| No model call reachable from any extractor | PASS — asserted at import level, structurally |
| `redaction_status = Fail` blocks summary exposure | PASS |

The fixture corpus in `engine/tests/fixtures/summaries/` was authored **before** the
extractors, and immediately earned it: the validator rule-name pattern used a greedy
`\S+` that swallowed the delimiting colon, so every failed rule was reported as
`out_of_scope_present:`. Rules written after their fixtures would have matched the bug.

Extraction runs on **bytes, before decoding** — a lossy decode first could split a
credential into halves no byte pattern matches, and the summary would carry the pieces.

**A layering guard was added, and Step 5 is why.** The first draft of
`application/evidence.py` imported `infrastructure.summarizers` directly, violating the
inward dependency rule BLUEPRINT §4.1/§5.1 states. No test enforced it. Extraction now
reaches the application layer through a `SummaryExtractor` port, and
`tests/contract/test_layering.py` fails the build on any outward import — verified by
reintroducing the violation and watching it name the exact file.

### Step 6 — metrics and learning proposals · Checkpoint D met

| Criterion | Result |
|-----------|--------|
| Metrics recompute identically from the pinned `derived_from` revisions | PASS |
| A clean run generates no proposal and exits 0 | PASS |
| A rejected proposal is not regenerated while source `content_hash` is unchanged | PASS — and *is* regenerated once the evidence changes |
| The run owner, lacking the target-document role, is denied `DecideProposal` | PASS — exit 5 |
| `learn decide --decision accept` does not open the target document | PASS — asserted the target path is never created |

Every metric in the closed set is emitted; one that does not apply carries a null value
with `applicable: false` rather than being omitted or zeroed. Omission and zero are both
misreadings — "no gate wait recorded" is not "waited zero seconds". `evidence_freshness`
reports the **worst** entry rather than an average, because an index 90% fresh and 10%
missing is not "mostly fresh": the missing artifacts are exactly the ones a reviewer will
fail to open.

Drafting and deciding are separate operations with separate authorization, which is what
closes the escalation path ADR-009 names: one capability covering both would let an
automated caller approve its own proposals.

**One behavioural fix found by the end-to-end smoke, not by a unit test.** `infer_kind`
classified a file named `validator.txt` as `status`, which has no failure rules — so a
real validator failure could never reach a learning proposal. Name hints now take
precedence over the extension.

### Step 8 — test and evidence closure

**709 tests**, 0 failures, green on 3.11 / 3.12 / 3.14. Line coverage **92.22%**
(minimum 85%), branch **82.64%**. 192 of those tests are F0003's.

`artifacts/test-coverage/acceptance-criteria-map.md` maps every story's acceptance
criteria to the test that closes it and **states its gaps** rather than implying
completeness — chiefly that S0003 is entirely unimplemented and untested.

Two checks were added that did not exist: a **packaging contract** test, because ADR-005
and ADR-007 both rest on "no new required dependency" and that is a claim about a file
that changes (verified separately against a genuinely clean install); and a **full
operator lifecycle** test through the CLI, because every layer had passing tests when
`infer_kind` misfiled `validator.txt` — the defect lived in the seam between two correct
layers, and only the whole chain exposes that class.

### Step 7 — read-only MCP surface · Checkpoint E met · M1 and L1 resolved

**M1 resolved: documented manual host configuration.** No `mcp install` subcommand —
writing a host's configuration file would put Nebula inside a trust boundary it does not
own. `docs/mcp-host-configuration.md` carries the configuration, and its troubleshooting
command was executed verbatim to confirm it works as printed. **L1 resolved in the same
pass** — ADR-005 already answered it and the built code is the evidence.

Read-only is structural, asserted at instance *and* import level: the module cannot import
a mutating application service, so a mutating tool cannot be added without a visible
architectural edit.

**S7-F1 (low):** `f0003-mcp-response` pins `tool_name` to the six-name enum, so an error
envelope naming an *unknown* tool cannot be conformant — which my first implementation
returned. The schema was right: an unknown tool is a protocol error (`-32601`), not a tool
result. Found by validating against the committed schema in test; reading would not have
caught it.

ADR-007's premise is demonstrated, not asserted: a clean install carrying only
`jsonschema` serves all six tools with no MCP SDK present.

### G2 — self-review, QE, deployability · PASS WITH RECOMMENDATIONS

730 tests green on 3.11/3.12/3.14; line 92.25%, branch 82.71%. `security_sensitive_scope`
flipped **false → true** and the four scan classes ran: dependency **clean** (6-package
runtime closure, 0 vulnerabilities), secrets **clean** (7 candidates, all triaged in the
artifact — synthetic redaction fixtures, their echoes in pytest parametrize IDs, and the
manifest's own digests), SAST **0 high / 0 medium / 17 low**, DAST **waived** (no port
exists; Architect-owned).

**One SAST low was mine and was real:** an `assert` guarded the MCP handler map against
the published tool contract, and `python -O` strips asserts — the invariant would have
vanished in an optimised run. Replaced with an unconditional check, verified under `-O`.

**S9-F1 (medium), found and fixed at this gate.** Outside a configured workspace every MCP
tool returned *success with an empty result* — indistinguishable from a real run with no
evidence, so a reviewer would read "this run has nothing" rather than "I am in the wrong
tree". `docs/mcp-host-configuration.md` already documented `WORKSPACE_NOT_CONFIGURED` for
this case: the documentation was right and the code was not. Found by **running** the
documented troubleshooting steps rather than reading them.

**S9-F2 (low), recorded not fixed:** `doctor` outside a workspace reports `SCHEMA_INVALID`
exit 9. Pre-existing F0001; reclassifying it is a contract change owned elsewhere.

**S9-F3 (low), framework:** `feature.yaml` declares `g2-deployability-check.md`; the
validator requires `deployability-check.md`. The names disagree.

### G3 — code and security review · PASS WITH RECOMMENDATIONS

`gate_policy.py --profile standard` computes **ACCEPTABLE** (critical 0, high 0,
`requires_justification: false`) — computed, not asserted.

**SEC-1 (high) was raised and fixed inside this cycle.** `learn decide` took `--role` from
the command line, and the check compared the *declared* role to the one the target
document requires — never asking whether the actor held it. Demonstrated: a
`LocalOperator` who owned the run passed `--role architect` and accepted an architecture
proposal. That defeats the security model's central claim about this action and reopens
ADR-009's escalation path from the other side.

Fixed: the role is derived from the target and verified against a new `proposal_grants`
block in the `0600` policy file; `--role` is **removed**, because a role the caller can
name is a role the caller can claim. Deny by default, and a grant for one target class
does not carry to another.

**CR-1 (medium)** is an architecture question, not a code fix: the artifact index and its
audit event commit in separate transactions, so a failure between them advances the
projection without the event BLUEPRINT §5.3 requires. Repairable — the index is a
projection and re-indexing is idempotent — and loud rather than silent.

### G4 — approval · APPROVED 2026-08-29

Severity **ACCEPTABLE**; no mitigation token required, because no high finding remains
open. All four carried decisions confirmed by the operator:

| ID | Confirmed |
|----|-----------|
| S3-F1 | The `event_type` enum extension is the one F0001 schema change `1.1` makes |
| SEC-1 | `proposal_grants` is the second additive F0001 schema change; no smaller fix exists |
| S4-F1 | The persisted capability report is the durable record for a blocked launch |
| CR-1 | Projection commits and audit events need **not** be atomic — repairable divergence is the accepted pattern, provided the projection is rebuildable and the failure is loud |

CR-1's confirmation is a **standing decision** for future F0003 stores, not a one-off.

### G5 — signoff · PASS 2026-08-30

All four Required=Yes roles signed by `gajakannan`, each with a verdict, ISO date, and an
evidence path: 28 story × role rows across seven stories. Eight recommendations
dispositioned; none blocking, and both high-severity items resolved before the gate.

A single individual holds all four roles. Recorded plainly in the ledger's *Independence
Note*, with the two things that partially offset it: the security review found and fixed a
**high** finding in the implementer's own code, and every structural guard was verified by
injecting the failure it exists to catch.

**S11-F1 (medium) — a correction to my own G0 reasoning.** `parse_status_required_roles`
reads a section named exactly `Required Role Matrix`. This STATUS.md called it *"Required
Signoff Roles (Set in Planning)"*, so the parser found nothing and `status_required` was
**empty for the whole run**. That makes the G0 claim that "the Security Reviewer
requirement comes independently from STATUS.md" **wrong** — the role became required only
when `security_sensitive_scope` was set true at G2. The outcome was unaffected; the
reasoning was not. Section renamed to match F0001 and the parser.

### G6 — candidate evidence · PASS 2026-08-30

G0–G5 evidence present and passing; `omissions[]` empty; the one waiver (DAST) complete.

The diff artifact was **regenerated from the run base** rather than the working tree — it
had been showing 9 files where the run actually touched 95, so a boolean cross-check would
have run against a tenth of the scope. Only `engine/**` matches a §7 path class;
`security_sensitive_scope` is true by judgment rather than glob, which is the conservative
direction.

### G7 — knowledge-graph reconciliation · PASS 2026-08-30

Six F0003 capabilities had **no** code bindings. `node_bindings` 7 → 13, authored as
shards and compiled — never hand-edited. Symbol index **1608 → 2034**; 426 symbols became
reachable because the capabilities now have bindings to resolve through. Orphan nodes: 0.

CODE paths only, so the G8 archive move cannot break them. `cli.py` was left with its
original F0001 owner rather than claimed twice: the compiler warns on binding overlap, and
it is right — an overlap makes "which capability owns this file" ambiguous exactly when
retrieval needs an answer.

**`coverage-report.yaml` is deliberately stale.** Regenerating it is forbidden at G7 and
belongs to G8, after the archive move relocates evidence paths. Verified safe: CI runs only
`--check-reproducible`, which exits 0.

Two framework findings recorded: **S12-F1** (`validate.py` prints `[PASS]` and exits 1) and
**S12-F2** (the Architect SKILL says "confirm exit 0" while the action spec forbids the only
command that would produce it).

### Remaining

**G8 — PM closeout only.** Status to Done, archive move, tracker sync, `latest-run.json`,
`pm-closeout.md`, and the deferred `--write-coverage-report`.

## Plan-Review Findings

### Re-run `2026-08-20-45b7ccd8` — verdict CONDITIONALLY READY (`requires_justification: true`)

First recorded readiness verdict for F0003; all five gates PR0-PR4 executed.

| ID | Severity | Finding | State |
|----|----------|---------|-------|
| N1 | High | PRD contradicted its own CLI-only decision at lines 38, 56, 97, 141 | **Resolved 2026-08-21** — all four reconciled; line 56's acceptance criterion now names `metrics --run <id>` |
| N2 | High | `security/f0001-authorization-model.md` omitted F0003's three actions | **Resolved 2026-08-21** — *F0003 Action Extensions* section added with the role matrix and the target-document rule for `DecideProposal` |
| N3 | Low | STATUS *Runtime Progress* had no item for S0007 | **Resolved 2026-08-21** |
| N4 | Medium | `F0003-S0004` line 15 and `F0003-S0001` line 130 still described a dashboard/TUI surface | **Resolved 2026-08-23** — reworded to the command surface; swept on the generic terms `dashboard`/`TUI`/`GUI` rather than the five screen names, which is what let this survive three runs |
| M1 | Medium | S0003 MCP install vs manual host configuration | **Resolved 2026-08-29** — documented manual host configuration; no `mcp install`. See `docs/mcp-host-configuration.md` |
| L1 | Low | S0001 open question unreconciled against ADR-005 | **Resolved 2026-08-29** — reconciled in the story; the built code is the evidence |

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
| M1 | Medium | S0003 open question (MCP install vs manual host config) unanswered | **Resolved 2026-08-29** |
| M2 | Medium | ADR-006 deferred digest length to G0 while the schema pinned 12 hex | **Resolved 2026-08-21** — 12 fixed in the ADR; the contradictory follow-up removed |
| L1 | Low | S0001 open question answered by ADR-005 but not reconciled in the story | **Resolved 2026-08-29** |

No critical or high findings remain. M1 and L1 stay open by owner decision, both
non-blocking under the `review-family` profile. The PR4 readiness gate — which never
executed in this run, because it halted at PR2 on H4 — ran to completion in
`2026-08-22-5ed12b9c`, so the recorded verdict rests on gate evidence rather than on this
table.

## Story Checklist

| Story | Title | Status |
|-------|-------|--------|
| F0003-S0001 | Runtime command surface and wrap launch | [x] **Implemented** 2026-08-29 (Steps 4+6) |
| F0003-S0002 | Provider capability matrix and launch guards | [x] **Implemented** 2026-08-29 (Step 4) |
| F0003-S0003 | MCP status and evidence tools | [x] **Implemented** 2026-08-29 (Step 7) |
| F0003-S0004 | Evidence artifact store and retrieval index | [x] **Implemented** 2026-08-29 (Steps 3+5) |
| F0003-S0005 | Deterministic transcript, log, and validator summaries | [x] **Implemented** 2026-08-29 (Step 5) |
| F0003-S0006 | Runtime metrics and failure-learning review | [x] **Implemented** 2026-08-29 (Step 6) |
| F0003-S0007 | Application query/command service split | [x] **Implemented** 2026-08-29 (Step 1; prerequisite for S0003) |

## Runtime Progress

- [x] Local command surface implemented
- [x] Wrapped launch records run metadata
- [x] Session status reconciles against real local session state
- [x] Provider capability reports and launch guards implemented
- [x] MCP read-only status tools implemented
- [x] Evidence artifact store and retrieval index implemented
- [x] Deterministic summarizers implemented
- [x] Metrics command implemented (CLI-only; no dashboard — see PRD *UX / Surfaces*)
- [x] Failure-learning proposal review flow implemented
- [x] Application query/command service split implemented (S0007; prerequisite for the MCP surface)

## Cross-Cutting

- [x] Story validator passes
- [x] Tracker validator passes
- [x] Security review complete (G3) — one HIGH finding raised and fixed within the cycle; severity ACCEPTABLE
- [x] Architecture review of runtime contract complete; operator approved 2026-08-29 (BLUEPRINT §5.9)
- [x] Tests cover command surface, MCP tools, artifact retrieval, summaries, metrics, and proposal workflow — 730 tests, 92.25% line

## Required Role Matrix

| Role | Required | Why Required | Set By | Date |
|------|----------|--------------|--------|------|
| Quality Engineer | Yes | Validates command behavior, status contracts, artifact retrieval, summaries, and metrics. | Architect | 2026-06-24 |
| Code Reviewer | Yes | Reviews runtime command implementation, tool contracts, and persistence boundaries. | Architect | 2026-06-24 |
| Security Reviewer | Yes | Reviews redaction, local path constraints, MCP read-only boundaries, and proposal safety. | Architect | 2026-06-24 |
| DevOps | No | Local-only runtime layer unless a later feature adds hosted operation. | Architect | 2026-06-24 |
| Architect | Yes | Required for runtime contract and F0002 handoff approval. | Architect | 2026-06-24 |

## Story Signoff Provenance

All four required story-level signoffs are complete for every story. A single
individual holds all four roles in this single-operator deployment; see the
*Independence Note* in `signoff-ledger.md`.

| Story | Role | Reviewer | Verdict | Evidence | Date | Notes |
|-------|------|----------|---------|----------|------|-------|
| F0003-S0001 | Quality Engineer | gajakannan | PASS | test-execution-report.md | 2026-08-30 | Guarded `wrap` launch, command surface, and run registration validated. |
| F0003-S0001 | Code Reviewer | gajakannan | PASS | code-review-report.md | 2026-08-30 | Guard-before-launch ordering and F0001 `launch` reuse approved. |
| F0003-S0001 | Security Reviewer | gajakannan | PASS | security-review-report.md | 2026-08-30 | No credential body persisted; blocked launch starts no session. |
| F0003-S0001 | Architect | gajakannan | PASS | g0-assembly-plan-validation.md | 2026-08-30 | Command surface matches the approved runtime contract 1.1. |
| F0003-S0002 | Quality Engineer | gajakannan | PASS | test-execution-report.md | 2026-08-30 | Capability matrix across four requirement levels and four probe results validated. |
| F0003-S0002 | Code Reviewer | gajakannan | PASS | code-review-report.md | 2026-08-30 | Declared requirement levels and the single guard rule approved. |
| F0003-S0002 | Security Reviewer | gajakannan | PASS | security-review-report.md | 2026-08-30 | Probe output redacted before persistence; timeout blocks as failure does. |
| F0003-S0002 | Architect | gajakannan | PASS | g0-assembly-plan-validation.md | 2026-08-30 | `approval_visibility` required is consistent with the tmux-native premise (ADR-001). |
| F0003-S0003 | Quality Engineer | gajakannan | PASS | test-execution-report.md | 2026-08-30 | Six MCP tools, paging, and error envelopes validated against the committed schema. |
| F0003-S0003 | Code Reviewer | gajakannan | PASS | code-review-report.md | 2026-08-30 | Read-only enforced structurally at instance and import level. |
| F0003-S0003 | Security Reviewer | gajakannan | PASS | security-review-report.md | 2026-08-30 | No mutating service reachable; `evidence_show` refuses unredacted content. |
| F0003-S0003 | Architect | gajakannan | PASS | g0-assembly-plan-validation.md | 2026-08-30 | Dependency-free stdio surface matches ADR-007; M1 resolved as manual host configuration. |
| F0003-S0004 | Quality Engineer | gajakannan | PASS | test-execution-report.md | 2026-08-30 | Identity, longest-match root selection, containment, and collision behaviour validated. |
| F0003-S0004 | Code Reviewer | gajakannan | PASS | code-review-report.md | 2026-08-30 | Atomic index with its own lock; re-index idempotent and the recovery path. |
| F0003-S0004 | Security Reviewer | gajakannan | PASS | security-review-report.md | 2026-08-30 | Symlink resolved before containment; owner-only modes verified. |
| F0003-S0004 | Architect | gajakannan | PASS | g0-assembly-plan-validation.md | 2026-08-30 | Root-scoped identity matches ADR-006 including the fixed 12-hex digest. |
| F0003-S0005 | Quality Engineer | gajakannan | PASS | test-execution-report.md | 2026-08-30 | Determinism proven across repeated calls, processes, and three interpreters. |
| F0003-S0005 | Code Reviewer | gajakannan | PASS | code-review-report.md | 2026-08-30 | Rule sets keep failure markers; truncation yields Partial, never Pass. |
| F0003-S0005 | Security Reviewer | gajakannan | PASS | security-review-report.md | 2026-08-30 | Redaction runs on bytes before decoding; no model call reachable. |
| F0003-S0005 | Architect | gajakannan | PASS | g0-assembly-plan-validation.md | 2026-08-30 | Rule-based extraction matches ADR-008; `rule_set_version` stamped. |
| F0003-S0006 | Quality Engineer | gajakannan | PASS | test-execution-report.md | 2026-08-30 | Metric closure, `derived_from` pinning, and proposal lifecycle validated. |
| F0003-S0006 | Code Reviewer | gajakannan | PASS | code-review-report.md | 2026-08-30 | Drafting and deciding separated; append-only decisions. |
| F0003-S0006 | Security Reviewer | gajakannan | PASS | security-review-report.md | 2026-08-30 | DecideProposal authority derived from the target and verified against policy (SEC-1). |
| F0003-S0006 | Architect | gajakannan | PASS | g0-assembly-plan-validation.md | 2026-08-30 | Inert proposals and allowlisted targets match ADR-009. |
| F0003-S0007 | Quality Engineer | gajakannan | PASS | test-execution-report.md | 2026-08-30 | 514 F0001 tests pass unmodified; audit stream byte-identical. |
| F0003-S0007 | Code Reviewer | gajakannan | PASS | code-review-report.md | 2026-08-30 | Facades partition the services; delegation, not duplication. |
| F0003-S0007 | Security Reviewer | gajakannan | PASS | security-review-report.md | 2026-08-30 | Query facade holds no mutating service; reads append no events. |
| F0003-S0007 | Architect | gajakannan | PASS | g0-assembly-plan-validation.md | 2026-08-30 | Split is the Phase B interface commitment ADR-007 depends on. |

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
- [x] Every required signoff role has story-level `PASS` entries with reviewer, date, and evidence

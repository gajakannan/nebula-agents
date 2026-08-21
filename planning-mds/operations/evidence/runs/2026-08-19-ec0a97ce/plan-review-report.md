# Plan Review Report — F0003 Local Agent Runtime Control Plane

- **Run:** `2026-08-19-ec0a97ce`
- **PLAN_SCOPE:** `feature` · **TARGET:** `F0003`
- **Contract:** Feature Evidence Contract, scope `read-only-audit`, version `2026-07-11`
- **Diff range:** `228be9b..f7b7f5c` (Phase B architecture, PR #64)

## Decision

**NOT READY.**

Two critical findings block entry to `feature.md` G0. Both are cases where a competent
implementation agent would have to *invent* a contract rather than read one: the base
directory that artifact identity is computed against, and the operator surface for the
five screens the PRD requires plus proposal decisions.

The severity arithmetic is the `review-family` profile: critical > 0 → **NOT READY**.

This verdict is about completeness of the planning package, not about the quality of the
decisions in it. The five ADRs are internally coherent and their options analysis is
sound; three of them (ADR-007, ADR-008, ADR-009) are build-ready as written. The gaps are
concentrated in ADR-006's identity rule and in surface coverage that no artifact owns.

Fixes route back to `plan.md` (Phase B rework). This reviewer repairs nothing.

## Findings By Severity

| ID | Severity | Finding | Owner |
|----|----------|---------|-------|
| C1 | Critical | Artifact-identity base directory is ambiguous — ADR-006 says "relative to the run root", S0004 admits three approved roots | Architect |
| C2 | Critical | Operator surfaces are undefined: the PRD requires five screens and S0006 requires a proposal-decision surface; the architecture covers only CLI and MCP | Architect + PM |
| H1 | High | No authorization action for proposal decisions; `RunValidator` is overloaded for indexing, summarizing, and drafting | Architect |
| H2 | High | `RuntimeMetricSnapshot` is a declared record with no schema, while the other four have one | Architect |
| H3 | High | The query/command application split ADR-007 depends on is an unscoped refactor of F0001 code that no story owns | Code Reviewer |
| H4 | High | `coverage-report.yaml` was committed stale in PR #64 — a derived artifact that no longer matches its sources | Architect |
| M1 | Medium | S0003's open question (MCP install vs manual host configuration) is unanswered by Phase B | PM |
| M2 | Medium | ADR-006 defers digest length to G0, but the committed schema already pins 12 hex | Architect |
| L1 | Low | S0001's open question is answered by ADR-005 but the story was never reconciled | PM |

## Product Readiness

*Owner: Product Manager*

**Strong.** All six stories pass `validate-stories.py` with no issues. Each carries a
well-formed user story, happy path, edge cases, an interaction contract, data
requirements with validation rules, role-based visibility, NFRs, dependencies, business
rules, and a definition of done. Acceptance criteria are concrete and testable — S0002's
capability states and S0005's per-kind preservation rules are specific enough to write
fixtures against directly.

**C2 (critical).** The PRD's *UX / Screens* section names five screens — Runtime Home,
Capability Matrix, Evidence Browser, Metrics View, Learning Review — and stories S0001,
S0005, and S0006 reference them in their Interaction Contracts and UI/UX Notes. The Phase
B architecture is silent on all five: `f0003-runtime-contract.md` contains zero
occurrences of "TUI", and BLUEPRINT's only two TUI mentions are in §4 (F0001), not §5
(F0003, which begins at line 153). The architecture defines a CLI surface and an MCP
surface and stops.

This is build-critical because S0006's acceptance criteria require that "proposals require
accept, edit, reject, or archive before any document change is made", and its interaction
contract assigns those actions to a *Learning Review* surface. The runtime contract §1
explicitly pushes them away from `learn review` — "Proposal *decisions* (accept, edit,
reject, archive) are recorded through the review surface, not through `learn review`" —
but the phrase "the review surface" appears nowhere else in the architecture. There is no
command, no MCP tool, and no screen definition. An implementer cannot satisfy S0006
without inventing that surface.

Note the ownership question this raises: F0008 (Agent Cockpit Landing Shell) is the
feature that owns operator-facing shell surfaces, and it is `Later` with no stories. Phase
B needs to state explicitly whether F0003's screens are F0003 scope, deferred to F0008, or
CLI-only for now with the PRD's screen table revised accordingly. Any of the three is a
defensible answer; leaving it unstated is not.

**M1 (medium).** S0003 asks whether MCP setup ships as `nebula-agents mcp install` or as
documented manual host configuration. ADR-005 and ADR-007 define `nebula-agents mcp serve`
but say nothing about host configuration. The question is still open.

**L1 (low).** S0001 asks whether the command entry point lives under `agents/runtime/` or
a root-level wrapper. ADR-005 answers it — extend `engine/` — but the story still carries
the question unresolved. Cosmetic, but story open questions should close when Phase B
decides them.

## Architecture Readiness

*Owner: Architect*

**Sound where it is complete.** The five ADRs follow the established format, each with
real options analysis rather than post-hoc justification. ADR-007's structural read-only
argument (a query-only facade rather than per-handler checks) and ADR-008's rejection of
model-generated summaries on determinism-plus-correctness grounds are both well reasoned
and directly traceable to story acceptance criteria. ADR-009's sticky-rejection mechanism
is a genuine answer to the overfit risk the PRD names. SOLUTION-PATTERNS §12 correctly
narrows the §1 MCP prohibition rather than silently contradicting it.

**C1 (critical).** ADR-006 line 36 states identity derives from "the artifact's canonical
path relative to the run root". S0004 line 73 requires that "Source and summary paths must
be inside approved workspace, runtime, **or evidence** directories". The workspace and
evidence roots are not inside the run root. For any artifact outside the run directory —
which includes evidence-package artifacts, the exact case S0004's `manifest` and
`validator-output` kinds describe — the ADR's rule has no defined value.

This is build-critical rather than editorial because the base directory *is* the ID.
Choosing workspace-relative instead of runtime-relative produces different digests for the
same artifact, and the ID is the join key that S0003, S0005, and S0006 all depend on.
Two implementers could each follow the ADR faithfully and produce incompatible indexes.

Phase B must state the base root per approved root — for example, path relative to
whichever approved root contains it, with the root recorded as a discriminator in the
entry so the digest is unambiguous.

**H1 (high).** BLUEPRINT §5.4 asserts F0003 "adds no new actions" and maps its commands
onto F0001's `Probe`, `Launch`, `ReadState`, and `RunValidator`. Two problems. First,
`RunValidator` was defined for executing allowlisted validators; the runtime contract
reuses it for `evidence index`, `evidence summarize`, and `learn review`, which are not
validator executions. Second, proposal *decisions* have no action at all — §5.4 says
authorization "follows the target document", which describes the policy input but names
no verb to authorize. The authorization model is incomplete for the operations F0003 adds.

**H2 (high).** `RuntimeMetricSnapshot` is declared as a record in BLUEPRINT §5.2, the
runtime contract §6, and data-model's F0003 table, but the contract §8 lists five schemas
and none covers metrics. The other four records each have one. Either metrics needs a
schema or the docs need to state why a derived record is exempt — the current state reads
as an oversight, and an implementer has no shape to target.

**M2 (medium).** ADR-006's follow-up says "At feature G0, fix the digest length after
estimating artifact counts per run", but `f0003-artifact-index.schema.json` already pins
`[0-9a-f]{12}` in both the `artifact_id` pattern and the ADR body. The decision is
effectively made and the follow-up is stale, or the schema is premature. They contradict.

## Buildability Challenge

*Owner: Code Reviewer*

**Mostly buildable.** The CLI surface, exit-code mapping, error shape, capability guard,
and per-kind summary preservation rules are specific enough to implement without
invention. The schemas are valid JSON Schema (verified against Draft 2020-12) and their
constraints match the prose. Story-to-ADR traceability is complete in the ontology
bindings.

**H3 (high).** ADR-007's read-only guarantee rests on constructing the MCP adapter with a
query-only facade, and BLUEPRINT §5.1 elevates this to "a Phase B interface commitment,
not an implementation detail". But that split does not exist in F0001's application layer
today — it is a refactor of shipped code. No F0003 story mentions it: grepping the six
stories for "query-only", "query facade", or "command service" returns nothing.

So the work is architecturally mandatory but unowned. An implementation agent starting
S0003 would discover mid-story that it must first restructure F0001's application layer,
with no acceptance criteria, no test expectations, and no regression boundary for the
514 existing engine tests. Either a story owns the split, or ADR-007 must state that the
facade is introduced within S0003 and scope its blast radius.

**Non-findings, recorded so they are not re-raised.** The absence of
`feature-assembly-plan.md` is correct — the `feature` action authors it at G0, and the
spec forbids treating it as a plan deliverable. Story sequencing is likewise a G0 concern.
The five ADRs standing at `Proposed` is the expected state for a package whose approval
checkpoint is deliberately open; it is not a finding.

## Validation Evidence

PR2 validators executed through `run-gate.py`. Results in `commands.log` and
`lifecycle-gates.log`.

| Validator | Result |
|-----------|--------|
| `validate-stories.py` (F0003) | PASS — 6 stories, no issues |
| `validate-trackers.py` | PASS — 0 errors, 0 warnings |
| `scripts/kg/validate.py` | **FAIL** — `coverage-report.yaml is stale` (see H4) |
| `scripts/kg/validate.py --check-drift` | Not reached — PR2 halts at first failure |
| `validate_templates.py` | Not reached |

**PR2 did not complete.** The spec's stop conditions include "A validator failure prevents
evidence-backed readiness", so this run halts at PR2 rather than forcing through. This is
the correct outcome, not an obstacle: the failure is a genuine defect in the package under
review (H4), and routing it back to the owner is exactly what a read-only reviewer should
do. The verdict is unaffected either way — the two critical findings come from PR1
artifact inspection and stand independently of PR2.

The three validators that did run are green, which is worth stating plainly — the findings
above are gaps the validators are not designed to catch. Tooling confirms the package is
well-formed and internally consistent; it cannot confirm that the package is complete
enough to build from. That judgment is what this review adds.

Supporting checks run during PR1, recorded in `commands.log`:

- Five `f0003-*.schema.json` validated against JSON Schema Draft 2020-12 — all valid.
- Six lifecycle gates pass; KG reproducibility (`--check-reproducible`) OK.
- `--check-drift` passes when run directly; it was simply not reached inside PR2.

### H4 — `coverage-report.yaml` was committed stale in the F0003 package

*Severity: High. Owner: Architect (`plan.md` Phase B). This is an F0003 finding.*

Plain `scripts/kg/validate.py` fails on the current tree:

```
Errors:
- coverage-report.yaml is stale (run python3 scripts/kg/validate.py --write-coverage-report)
```

Cause, traced to the source: the staleness check compares **only** `source_hash` values
(`validate.py` around line 1281 — the code comments that `last_modified` is deliberately
excluded because mtime differs between local and CI). Two entries drifted, both keyed to
`entity:learning-proposal`, whose `source_paths` include
`ADR-009-f0003-review-gated-learning-proposals.md`.

That ADR was edited *after* Phase B G5 ran `--write-coverage-report` — a vague-language
wording fix — and both the edit and the already-written report were committed together in
`f7b7f5c` (PR #64). `git log` confirms both files last changed in that same commit. The
package therefore shipped with a derived artifact that does not match its sources.

Impact is contained but real: CI does not catch it (the workflow runs
`--check-reproducible`, which passes) and none of the six lifecycle gates run plain
`validate.py`. It does block `plan-review` PR2, which is how it surfaced.

Remedy is `--write-coverage-report` and a re-commit, owned by `plan.md` Phase B. This
reviewer does not perform it — that is the read-only boundary working as intended.

**Correction to an earlier draft of this report.** An earlier revision recorded this as
"F1", a *framework* defect: the claim was that `coverage-report.yaml` embeds git-churn
values so it goes stale after any merge, making PR2 unsatisfiable for a read-only
reviewer. That was wrong on both counts. The freshness check ignores churn-derived fields
entirely, and the staleness here was caused by an out-of-order edit in the package under
review, not by merge activity. There is no circularity: the remedy is owned by `plan.md`,
the reviewer correctly refuses to apply it, and routing the fix back to the owner is the
designed behavior. The system worked; the package was wrong.

### Framework observation (low)

`run-gate.py` interpolated `{FEATURE_PATH}` as
`planning-mds/features/F0003-None` on the first PR2 invocation, because `--feature-slug`
was not supplied. `build_variables()` (line 171) f-strings `args.feature_slug` directly
into the path with no fallback and no validation, so an omitted slug yields a path
containing the literal string `None`, and the validator then fails against a nonexistent
directory — a misleading validator failure rather than a usage error.

The value was already available: `init-run.py` had recorded
`feature_slug: local-agent-runtime-control-plane` in `evidence-manifest.json` inside the
very run folder the driver resolves. Small fix, in either direction: read the slug from
the manifest, or fail closed on an unresolved placeholder. Routes to the F0007 maintainer.

### Second framework observation

`run-gate.py` interpolated `{FEATURE_PATH}` as
`planning-mds/features/F0003-None` on the first PR2 invocation, because `--feature-slug`
was not supplied — even though `init-run.py` had already resolved and recorded
`feature_slug: local-agent-runtime-control-plane` in the run manifest minutes earlier. The
driver did not fail on the unresolved value; it built a path containing the literal string
`None` and ran the validator against it, producing a misleading validator failure rather
than a usage error. Low severity, but it costs a debugging cycle and the fix is small:
resolve the slug from the manifest, or fail closed on an unresolved placeholder.

## Artifact Trace

Artifacts read (none written outside this run folder):

| Artifact | Role in the review |
|----------|--------------------|
| `features/F0003-.../PRD.md` | Screens, scope, risks, data requirements |
| `features/F0003-.../F0003-S0001..S0006*.md` | Acceptance criteria, interaction contracts, open questions |
| `BLUEPRINT.md` §5 | Boundaries, data model, workflow, authorization, NFRs |
| `architecture/f0003-runtime-contract.md` | CLI, MCP, records, exit codes, schemas |
| `architecture/decisions/ADR-005..009*.md` | Decisions, options, consequences |
| `architecture/SOLUTION-PATTERNS.md` §1, §12 | Pattern compliance |
| `architecture/data-model.md` | F0003 record table and persistence layout |
| `schemas/f0003-*.schema.json` | Shape conformance against prose |
| `kg-source/features/F0003.yaml` + 12 node shards | Traceability bindings |

## Routing

| Finding | Routes to | Suggested resolution |
|---------|-----------|----------------------|
| C1 | `plan.md` Phase B — Architect | State the identity base per approved root and record the root as a discriminator |
| C2 | `plan.md` Phase B — Architect + PM | Decide F0003 vs F0008 vs CLI-only for the five screens and the proposal-decision surface; revise the PRD screen table to match |
| H1 | `plan.md` Phase B — Architect | Add an action verb for proposal decisions; justify or narrow `RunValidator` reuse |
| H2 | `plan.md` Phase B — Architect | Add a metrics schema or record why a derived record is exempt |
| H3 | `plan.md` Phase A/B — PM + Architect | Give the query/command split an owning story, or scope it inside S0003 |
| M1 | `plan.md` Phase B — PM | Answer the MCP host-configuration question |
| M2 | `plan.md` Phase B — Architect | Reconcile ADR-006's follow-up with the committed schema |
| L1 | `plan.md` Phase A — PM | Close S0001's open question against ADR-005 |
| H4 | `plan.md` Phase B — Architect | Re-run `--write-coverage-report` and commit; the report shipped stale in PR #64 |
| (obs) | F0007 maintainer | `run-gate.py` builds `F0003-None` paths when `--feature-slug` is omitted instead of resolving from the manifest or failing closed |

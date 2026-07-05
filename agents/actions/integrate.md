# Action: integrate

## User Intent

Merge one contributor branch into the integration branch with zero hand-editing
of knowledge-graph or tracker files: sources merge semantically, generated
projections regenerate unconditionally, validation gates the merge, every run
leaves auditable evidence, and the maintainer keeps two explicit human gates
around the whole thing.

## Agent Flow

```
Gate I0 (review-verdict) → Integrator → Gate I6 (human test validation) → maintainer push
```

Serial by construction: one integration run at a time, maintainer-invoked.
The integrator never pushes; the maintainer pushes only after recording a
passing gate I6.

## Prerequisites

- `{PRODUCT_ROOT}/scripts/kg/merge3.py` and `tracker_merge.py` present (F0006 S0001/S0002)
- The source branch/PR is fetchable; the integration branch is designated
  (see Branch Strategy below)
- A `feature-review` verdict for the source branch's feature, or the
  maintainer's explicit waiver with rationale

## Inputs

| Input | Required | Notes |
|-------|----------|-------|
| `SOURCE` | yes | Contributor branch or PR number |
| `INTEGRATION_BRANCH` | yes | Never `main`. Current train: the maintainer-designated branch; steady state: integrator-created `integrate/<date>-train` |
| `REVIEW_VERDICT_REF` or `WAIVER` + rationale | yes (one of) | Gate I0 input; a waiver covers this run only |
| `RUN_ID` | auto | `integrate-YYYYMMDD-HHMMSS` (UTC), per the runbook convention |

## Branch Strategy (maintainer decision, 2026-07-05)

Integration lands **only on the integration branch**; `main` receives exactly
one promotion merge from that branch after the train completes, pushed by the
maintainer. For the first train this branch is `chore/merge-PRs` (the de facto
mainline — stale `main` is not a valid merge base). In steady state the
integrator creates a dedicated integration branch per train and the same
promotion rule applies.

## Procedure (gates I0–I6)

Work in a dedicated git worktree of the integration branch; never operate on
the maintainer's working checkout.

**I0 — Gate 1: feature-review verdict.** Verify `REVIEW_VERDICT_REF` (a
passing done-review) or record the maintainer's waiver + rationale in the run
inputs. Missing both → halt; the evidence run records the missing gate.
Nothing is merged.

**I1 — Branch verification (bounce check).** On the *source branch's own*
content: regenerate the generated projections from its sources and compare to
its committed copies; scan for code-overlap with the integration branch.
Committed ≠ regenerated → **bounce to the contributor** with the exact
commands to run; the evidence run records the bounce; the run ends. The
integrator does not fix contributor branches.

**I2 — Merge.**
1. `git merge --no-commit <source>` in the worktree (code merges via git;
   code conflicts halt here for maintainer/contributor as ordinary git work).
2. For each curated KG file with changes on both sides since the merge base:
   `python3 {PRODUCT_ROOT}/scripts/kg/merge3.py <file> --base <merge-base> --ours <integration-branch> --theirs <source> --json <run>/artifacts/merge3-<name>.json`
3. Same CLI for `REGISTRY.md` and `ROADMAP.md`.
4. Any typed conflict → halt: conflict report (text + JSON) names the owning
   role per record kind (architect: nodes/bindings; PM: features/trackers;
   co-sign: exclusions). Nothing is committed. After the owner resolves on the
   contributor branch (or a fixup branch), the maintainer re-invokes; the
   re-run is a new run.

**I3 — Unconditional regeneration.** Even when git reported a clean merge of
generated files — *especially* then:
```
python3 {PRODUCT_ROOT}/scripts/kg/validate.py --regenerate-symbols --check-symbols --regenerate-decisions --check-decisions
python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report
python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/
```

**I4 — Full validation.** All must exit 0:
```
python3 {PRODUCT_ROOT}/scripts/kg/validate.py
python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift
python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --skip-feature-evidence
```
Story-index regeneration must be zero-diff on re-run. A failure after a clean
semantic merge → halt with `ConstraintViolation` routed to the owning role.

**I5 — Evidence + prepared merge.** Complete the integration evidence run
(template: `agents/templates/integration-evidence-template.md`), commit the
merge on the worktree branch, and record the prepared-merge SHA. Do not push.

**I6 — Gate 2: human test validation.** Stop. The maintainer exercises the
feature on the prepared merge worktree and records pass/fail in the evidence
run. Pass → the maintainer pushes to the integration branch. Fail → treated as
a bounce: nothing pushed, routed, any later re-run is a new run.

## Hard Boundary (self-abort)

A run that modifies any source-authored file — feature docs, architecture,
schemas, API contracts, application code, Phase-B `kg-source/**` — must abort
and self-report the violation in the evidence run. Needing a source edit *is*
the definition of a semantic collision; route it.

## Outputs

- Integration evidence run at
  `{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}/`
  (base-run files + `integration-report.json` + merge3/tracker JSON reports)
- On success: a prepared merge commit on the integration-branch worktree,
  awaiting gate I6 + maintainer push
- On bounce/halt: the bounce or conflict report, addressed to contributor or
  owning role; nothing merged

## Validation

- All I4 validators exit 0 on the merged result
- Evidence run complete per the template (including both gate records)
- Re-running the semantic merges on the same inputs is byte-identical

## Example Usage

```
Run the integrate action: SOURCE=PR #47, INTEGRATION_BRANCH=chore/merge-PRs,
REVIEW_VERDICT_REF=<feature-review run for F0021>.
```

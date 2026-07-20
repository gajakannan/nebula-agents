# Action: integrate

## User Intent

Merge one contributor branch into the integration branch with zero hand-editing
of knowledge-graph or tracker files: sources merge semantically, generated
projections regenerate unconditionally, validation gates the merge, every run
leaves auditable evidence, and the maintainer keeps two explicit human gates
around the whole thing.

## Agent Flow

```
Gate I0 (review-verdict) → Integrator (I1–I5) → Gate I6 (human test validation) → maintainer push
```

Serial by construction: one integration run at a time, maintainer-invoked.
The integrator never pushes; the maintainer pushes only after recording a
passing gate I6.

---

## Contract (generated — the spec is the source of truth)

The fixed procedure for this action — the `I0`–`I6` gates (with the two maintainer checkpoints), inputs
(`SOURCE`/`PR_URL`, `INTEGRATION_BRANCH`, `REVIEW_VERDICT_REF`/`WAIVER`, `MODE`), ownership, forbidden
actions, stop conditions, and conflict resolution, plus the concrete per-gate commands — is declared once in
[`agents/actions/spec/integrate.yaml`](spec/integrate.yaml) and compiled into the operator prompt at
`agents/templates/prompts/evidence-contract/integrate-operator-friendly.md` (integrate has only the
operator-friendly variant). Regenerate with `python3 agents/scripts/render-prompts.py`; the `prompt_drift`
lifecycle gate fails if the committed prompt drifts from the spec.
**Edit the spec, not this doc or the generated prompt.**

integrate is **worktree- and maintainer-driven**, not `run-gate`-driven: the gates carry their commands as
judgment and run inside a dedicated worktree (`git worktree add <tmp> {INTEGRATION_BRANCH}`), never the
operator's checkout. `run-gate.py --action integrate --list` shows the I0–I6 runbook and pauses at the I0/I6
maintainer checkpoints. The run id uses the `integrate` scheme (`integrate-YYYYMMDD-HHMMSS`, UTC — not the
contract date/token id) and the evidence run is a `merge`-scope base run package.

### Gate flow (commands in the generated prompt)

- **I0 — feature-review verdict (maintainer):** verify a passing `REVIEW_VERDICT_REF` or record the maintainer's `WAIVER` + rationale; missing both → halt, nothing merged.
- **I1 — branch verification (bounce check):** regenerate `{SOURCE}`'s projections from its own sources and compare to its committed copies; committed ≠ regenerated → **bounce** to the contributor (the integrator never fixes their branch).
- **I2 — merge:** `git merge --no-commit` (code conflicts halt as ordinary git work), then `merge3.py` per both-sides-changed curated KG file and `REGISTRY.md`/`ROADMAP.md`; any typed conflict → halt, routed to the owning role.
- **I3 — unconditional regeneration:** regenerate symbols/decisions/coverage and the story index from source even when git reported a clean merge of generated files.
- **I4 — full validation:** `validate.py`, `--check-drift`, and `validate-trackers.py --skip-feature-evidence` all exit 0; story-index re-run is zero-diff.
- **I5 — evidence + prepared merge:** complete `integration-report.json`, commit the merge on the worktree branch, record the SHA — do not push.
- **I6 — human test validation (maintainer):** STOP; the maintainer exercises the feature on the prepared worktree, records pass/fail; pass → maintainer pushes; fail → bounce.

---

## Prerequisites

- `{PRODUCT_ROOT}/scripts/kg/merge3.py` and `tracker_merge.py` present (F0006 S0001/S0002)
- The source branch/PR is fetchable; the integration branch is designated (see Branch Strategy below)
- A `feature-review` verdict for the source branch's feature, or the maintainer's explicit waiver with rationale

## Branch Strategy (maintainer decision, 2026-07-05)

Integration lands **only on the integration branch**; `main` receives exactly
one promotion merge from that branch after the train completes, pushed by the
maintainer. For the first train this branch is `chore/merge-PRs` (the de facto
mainline — stale `main` is not a valid merge base). In steady state the
integrator creates a dedicated `integrate/<date>-train` branch per train and the
same promotion rule applies.

> **First post-train integration:** run it with **no blanket waiver** — supply a
> real `REVIEW_VERDICT_REF` (or deliberately omit both to exercise the I0 halt).
> The Phase-A train ran under a train-wide waiver, so I0's missing-verdict halt
> has never fired live; the next run exercises and records it (maintainer decision
> 2026-07-06 — see F0006 `STATUS.md` Deferred Non-Blocking Follow-ups).

## Hard Boundary (self-abort)

A run that modifies any source-authored file — feature docs, architecture,
schemas, API contracts, application code, Phase-B `kg-source/**` — must abort
and self-report the violation in the evidence run. Needing a source edit *is*
the definition of a semantic collision; route it to the owner.

## Outputs

- Integration evidence run at `{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}/`
  (base-run files + `integration-report.json` + merge3/tracker JSON reports)
- On success: a prepared merge commit on the integration-branch worktree, awaiting gate I6 + maintainer push
- On bounce/halt: the bounce or conflict report, addressed to the contributor or owning role; nothing merged

## Related Actions

- **Before:** [feature-review action](./feature-review.md) — supplies the I0 `REVIEW_VERDICT_REF`
- **Related:** [review action](./review.md) — per-change code/security review

## Example Usage

```
Run the integrate action: SOURCE=PR #47, INTEGRATION_BRANCH=chore/merge-PRs,
REVIEW_VERDICT_REF=<feature-review run for F0021>.
```

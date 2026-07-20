# Action: Build

## User Intent

Close and archive a set of planned features in one orchestrated run — each feature produced and validated under the Feature Evidence Contract — with build-level scope locking, aggregate lifecycle validation, a holistic approval gate, and a build closeout.

`build` is feature-in-a-loop at the **orchestration layer**: it does not re-derive the feature gates. It delegates each feature's implementation and closeout to the [feature action](./feature.md) and wraps those runs with cross-feature sequencing and a build-level base run package. Use the [feature action](./feature.md) for a single incremental slice; use `build` to close/archive several features together.

## Agent Flow

```
Product Manager / build orchestrator
  ↓  B0    Build scope lock (order BUILD_SCOPE by dependency)
  ↓  B1    Per-feature evidence package production  ─▶ delegates to feature action G0–G6 (per FEATURE_ID)
  ↓  B2    Per-feature G6 candidate validation
  ↓  B3    Lifecycle validators (tracker, story-index, KG drift, templates)
  ↓  B4    Per-feature G8 PM closeout             ─▶ delegates to feature action G8 (per FEATURE_ID)
  ↓  B4.5  Build-level approval gate (user reviews aggregated closeouts)
  ↓  B5    Build closeout + exit validation sweep
Build Complete
```

**Flow Type:** PM-orchestrated multi-feature closeout. The per-feature role work (backend, frontend, AI, QE, DevOps, code/security review, per-feature approval/signoff) belongs to the [feature action](./feature.md); `build` sequences those runs across `BUILD_SCOPE` and owns only the build-level base run package and cross-feature ordering.

---

## Contract (generated — the spec is the source of truth)

The fixed procedure for this action — the `B0`–`B5` gates (plus `B4.5`), artifacts, ordering,
typed commands, ownership, forbidden actions, stop conditions, and conflict resolution — is
declared once in [`agents/actions/spec/build.yaml`](spec/build.yaml) and compiled into the
operator/automation prompt pair at
`agents/templates/prompts/evidence-contract/build-operator-friendly.md` and
`build-automation-safe.md`. Regenerate with `python3 agents/scripts/render-prompts.py`; the
`prompt_drift` lifecycle gate fails if the committed prompts drift from the spec.
**Edit the spec, not this doc or the generated prompts.**

### Build gate flow

- **B0 Build scope lock** — confirm `BUILD_SCOPE`; record it in `action-context.md`; order features by
  dependency (a feature whose files another in-scope feature newly binds closes first; ties by
  `FEATURE_ID` ascending), recorded as the B0 row in `gate-decisions.md`.
- **B1 Per-feature evidence package production** — for each feature without an approved package, run the
  [feature action](./feature.md) through G0–G6 with a fresh `RUN_ID` (`rerun_of=null`); re-close and
  re-validate rules for features with an existing approved package follow the spec.
- **B2 Per-feature G6 candidate validation** — `validate-feature-evidence.py --stage G6` per feature; all
  in-progress runs must pass before any tracker sync at B3.
- **B3 Lifecycle validators** — `validate-trackers.py`, `generate-story-index.py`,
  `kg/validate.py --check-drift`, `validate_templates.py`; append each command + exit code to
  `lifecycle-gates.log`.
- **B4 Per-feature G8 PM closeout** — PM role switch; for each feature execute the feature G8 checklist
  (pm-closeout, finalize manifest, `patch-prior-manifest.py`, then `latest-run.json`, tracker + KG
  updates, archive move when Done/Completed).
- **B4.5 Build-level approval gate** — the user reviews the aggregated per-feature closeouts plus the B3
  lifecycle results; the decision is recorded as the B4.5 row in `gate-decisions.md`; refusal HALTs and
  restarts the affected features at B1.
- **B5 Build closeout + exit validation sweep** — build-level summary, then the ordered exit sweep
  (per-feature closeout validation, then tracker / story-index / KG symbols+decisions / coverage / drift /
  templates), all exit 0.

Ownership in brief (full map in the spec's `ownership:`): the **product-manager** owns per-feature
closeouts, manifest finalize/supersession, `latest-run.json`, and the tracker/archive updates; the
**build orchestrator** owns the `BUILD_RUN_FOLDER` base run files, cross-feature sequencing, and
`lifecycle-gates.log` aggregation. Per-feature role-report ownership inherits from the feature action.

Run the mechanics through the scripts (do not hand-transcribe them here):

- Build gate execution (ordered ops, durable checkpoints, telemetry) —
  `python3 agents/scripts/run-gate.py --action build --stage <B0..B5> ...` (`--list` prints the runbook)
- Per-feature production/closeout — the [feature action](./feature.md)'s own prompt pair +
  `run-gate.py --action feature ...` (which uses `init-run.py --action feature` for each feature's setup)
- Per-gate acceptance — `validate-feature-evidence.py --stage <Gn|closeout>` (invoked by `run-gate.py`)

The build run itself is a **base run** package at `BUILD_RUN_FOLDER` (not a feature package). A build with
an empty `BUILD_SCOPE` still produces that base run package; it produces no feature package and calls no
`validate-feature-evidence.py` (no feature scope), but tracker validation still runs as a sanity check.

---

## Runtime Execution Boundary

- The builder runtime orchestrates roles, gates, and artifact flow. Keep it stack-agnostic.
- Stack-specific compile/test/security execution must run in application runtime containers (or CI jobs built from those container definitions).
- Store executable evidence (test, lint, SAST, dependency scan outputs) under solution artifacts and use it in review gates.

## Canonical Evidence Package For Archived Features

When this build action archives a delivered feature at closeout, it produces the canonical feature evidence package defined by the Feature Evidence Contract in `CONSUMER-CONTRACT.md` at:

```text
{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}/
```

The per-feature pointer/index lives at `{PRODUCT_ROOT}/planning-mds/operations/evidence/features/{FEATURE_ID}-{FEATURE_SLUG}/latest-run.json`. For each `FEATURE_ID` in `BUILD_SCOPE`, `FEATURE_SLUG` and the per-feature `RUN_ID` are resolved by the build orchestrator per `evidence-contract/build-automation-safe.md`.

The package contents match those produced by [`agents/actions/feature.md`](./feature.md) (see its "Canonical Evidence Package" section). The same supersession-and-publish sequence applies at closeout (B4):

1. Invoke `agents/product-manager/scripts/patch-prior-manifest.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --new-run-id {RUN_ID}` to mark every prior approved manifest as `superseded`.
2. Only after step 1 succeeds, write the new `latest-run.json` for this feature.

If step 1 fails, do not proceed to step 2; surface the failure with the partial-closeout recovery guidance in `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md`. Build-action runs that do not archive a delivered feature use the base run evidence shape only.

### Context Reset Checkpoint (between features)

After a feature's evidence is persisted (its `latest-run.json` written) and **before
starting the next `FEATURE_ID` in `BUILD_SCOPE`, reset context.** Per-turn cost scales with
context size, so carrying a finished feature's full working context into the next feature
is a large cache write over a stale, bloated prefix (the dominant per-turn cost). The reset
is safe because the feature's state is durable in its evidence package, `STATUS.md`, and the KG.

- Harness-neutral: `/clear` (Claude Code), a fresh run (OpenAI), or a new operator session
  (manual). The next feature rehydrates from its feature folder + `workstate.py dump`/`digest`.
- Sequential fallback: a single-window run may skip the reset, but should expect rising
  per-turn cost across features (visible as cache-write spikes in `eval.py`).

---

## Prerequisites

Before running the build action:
- [ ] Plan action completed (requirements + architecture defined) for every feature in scope
- [ ] SOLUTION-PATTERNS.md exists and is up-to-date
- [ ] Tracker governance contract available (`{PRODUCT_ROOT}/planning-mds/features/TRACKER-GOVERNANCE.md`, seeded from `agents/templates/tracker-governance-template.md` when missing)
- [ ] User stories have clear acceptance criteria
- [ ] `python3 {PRODUCT_ROOT}/scripts/kg/validate.py` exits 0 at start
- [ ] User is available for the B4.5 build-level approval gate

---

## Related Actions

- **Before:** [plan action](./plan.md) — define what to build
- **Delegates to / alternative:** [feature action](./feature.md) — build/close a single feature; `build` invokes it per feature in scope
- **After:** [document action](./document.md) — generate documentation
- **Quality:** [test action](./test.md) — additional testing focus
- **Quality:** [review action](./review.md) — additional review focus

---

## Notes

- `build` closes/archives a **set** of features in one orchestrated run; use the [feature action](./feature.md) for a single incremental slice.
- Per-feature implementation, reviews, approval, and signoff are owned by the feature action — `build` does not re-derive them. It sequences those runs (B0/B1), validates them in aggregate (B2/B3), takes one holistic user approval (B4.5), and closes out (B4/B5).
- Critical issues block a feature's own approval inside its feature run; the build-level B4.5 gate is a holistic review of the aggregated per-feature closeouts and does not override any per-feature verdict.
- On B4.5 refusal, HALT and restart the affected features at B1 — do not proceed to B5.
- Reset context between features (see the Context Reset Checkpoint) to keep per-turn cost flat across `BUILD_SCOPE`.

# Feature Evidence README — F####-{slug} run {run-id}

> Template for `{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{run-id}/README.md`
> per §8 of the Feature Evidence Package Standardization contract.

## Run Summary

One paragraph describing what changed, who ran the action, and the lifecycle action (`feature` / `build` / `validate`).

## Status

Final state for this run: `draft` / `in-progress` / `approved` / `superseded` — must agree with `evidence-manifest.json` `status`.

## Evidence Index

- `evidence-manifest.json` — schema v1 (§11)
- `action-context.md` — Run Identity, Inputs, Assumptions, Scope Boundaries, Lifecycle Stage
- `artifact-trace.md` — read/written artifacts + Run Environment when needed
- `gate-decisions.md` — pass/fail/skip per gate row (§17 stage matrix)
- `commands.log` — JSON Lines per §13
- `lifecycle-gates.log` — lifecycle gate run summary
- Role and gate reports — list `g0-…`, `g1-…`, `g2-…`, `test-plan.md`, etc.

## Validation Summary

Each validator invocation (tracker, story-index, KG, template, feature-evidence) with exit code and rule IDs encountered. Mirror the `lifecycle-gates.log` contents and the manifest `gate_results`.

## Open Follow-ups

Deferred recommendations, validator defects, and operational follow-ups. Each item should reference an external ticket or `Recommendation Acceptances` line in `pm-closeout.md`.

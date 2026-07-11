# Knowledge-Graph Reconciliation — F####-{slug} run {run-id}

> Required at gate `G7` per §10. Authored by the **Architect** after signoff (`G5`) and candidate validation (`G6`), before PM closeout (`G8`). Reconciles the **semantic** knowledge-graph by **authoring shards** — `kg-source/bindings/**` (code bindings) and `kg-source/nodes/**` (canonical nodes, logical `F####/` doc refs only) — against the **as-built** source, then running `compile.py` to regenerate `code-index.yaml`/`canonical-nodes.yaml` (never hand-edit the generated projections). This keeps the compiled graph the next feature's architect reads at G0 correct. Architect-owned. Binds **code** paths only (stable across the archive move — logical refs resolve through the shard `path:`, so archiving needs no repoint); the path-sensitive `coverage-report.yaml` regeneration is a `G8` step, after the move.

## Scope

- Feature ID: F####
- Run ID: {run-id}
- Date: YYYY-MM-DD
- Reconciled by: Architect (feature-action)

## Binding Delta

Baseline = the `feature-assembly-plan.md` "Knowledge-Graph Binding Plan" declared at G0 (state "none declared" if the plan predates that section). List the bindings the implementation actually requires and how they differ from the G0 prediction (plan vs. as-built).

| Capability / node | code-index binding (glob) | G0-declared? | Action |
|-------------------|---------------------------|--------------|--------|
| capability:<id> | `experience/src/features/<dir>/**` | yes / no | added / updated / confirmed-existing-coverage |

Bind by **directory glob** where a cohesive folder is one capability — not file-by-file. Where an existing glob already covers a new file, record it as `confirmed-existing-coverage` (no edit), not a duplicate binding.

## Canonical Nodes

New `canonical-nodes.yaml` nodes or `WHY` rationale entries introduced by this feature — or an explicit **"none introduced; reuses existing semantics"**.

## Validator Results

| Check | Command | Result |
|-------|---------|--------|
| symbol regen + check | `validate.py --regenerate-symbols --check-symbols` | PASS (exit 0) |
| drift | `validate.py --check-drift` | PASS (exit 0) |

`coverage-report.yaml` was **not** regenerated at this gate (deferred to `G8`, after the archive move binds the relocated feature-doc paths).

## Handoff to Closeout

Confirm the semantic graph is green and ready for PM closeout to **verify** (not re-author). If a binding gap is found during closeout, it routes back here for a `G7` delta pass.

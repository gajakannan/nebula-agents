# F0006 - Getting Started

This feature has two homes:

- **Reference implementation** (code + data): a product repo's `scripts/kg/`,
  `planning-mds/kg-source/`, and `planning-mds/knowledge-graph/`. First target:
  `nebula-insurance-crm`.
- **Contract** (roles + docs): this repo, `nebula-agents` — the integrator persona,
  `agents/actions/integrate.md`, `agent-map.yaml`, and the KG/orchestration docs.

## Key files (product repo)

| File | Role |
|------|------|
| `scripts/kg/merge3.py` | Three-way semantic merge of KG records (Phase A entry point) |
| `scripts/kg/compile.py` | Deterministic shard→projection compiler (Phase B) |
| `scripts/kg/decompile.py` | One-time graph→shard exploder (migration only) |
| `scripts/kg/kg_common.py` | Canonical serializer + logical-ref resolver |
| `scripts/kg/validate.py` | Validation incl. `--check-reproducible` |
| `planning-mds/kg-source/**` | The only authored graph layer (Phase B) |
| `planning-mds/knowledge-graph/*` | Generated projections — never hand-edit |
| `.gitattributes` | Marks generated paths (`linguist-generated`, merge driver) |

## Key files (this repo)

| File | Role |
|------|------|
| `agents/integrator/SKILL.md` | Integrator persona: duties, hard boundary, routing |
| `agents/actions/integrate.md` | The integration run procedure |
| `agents/agent-map.yaml` | Integrator registration + shard ownership scopes |
| `agents/docs/KNOWLEDGE-GRAPH.md` | Source/generated classification and compile flow |

## Run a semantic merge (Phase A)

```bash
# from the product repo root, during a merge with conflicts on curated KG files
python3 scripts/kg/merge3.py \
  --base  <merge-base-ref> --ours <target-ref> --theirs <source-ref> \
  planning-mds/knowledge-graph/canonical-nodes.yaml
# → writes the merged file (canonical form) OR prints a typed conflict report; never both
```

## Per-PR integration gates (Phase A merge train)

> The Phase-A merge train is **complete** — all 7 contributor PRs were integrated and promoted to
> `main` on 2026-07-06 (see `STATUS.md`). The sequence below is the steady-state per-PR procedure the
> train established; it is what each future integration run follows.

Every PR passes the same sequence; the two human gates are deliberate pauses, recorded in the
integration evidence run:

1. **Gate 1 — feature review:** run the `feature-review` action against the contributor branch.
   The integrator requires a passing verdict, or a maintainer waiver recorded with rationale.
2. **Integrator run:** semantic merge (`merge3.py` + tracker rows), unconditional regeneration,
   full validation, evidence run, prepared merge commit. The integrator never pushes.
3. **Gate 2 — human test validation:** the maintainer exercises the feature on the prepared merge
   worktree and records pass/fail. A fail is routed like a bounce; nothing is pushed.
4. **Push:** the maintainer pushes the recorded-pass merge to the **integration branch**
   (`chore/merge-PRs` for this train) — never directly to `main`.
5. **Green integration branch:** validators re-run there before the next PR's integration starts.

`main` receives exactly one promotion merge from the integration branch after the whole train
completes. Steady state (after this train): the integrator creates a dedicated integration branch
per train instead of reusing a maintainer branch; the promotion rule stays the same.

## Run a compile and verify reproducibility (Phase B)

```bash
python3 scripts/kg/compile.py                       # shards → projections + derived indexes
python3 scripts/kg/validate.py --check-reproducible  # committed output == compile(source)
python3 scripts/kg/validate.py                       # graph integrity
```

Both validators must exit 0 on every branch; CI enforces the same.

## The two rules that must never be violated

1. **Never hand-edit a generated file.** If a projection looks wrong, fix the shard (or the
   compiler) and recompile.
2. **Never trust a textually clean git merge of a generated file.** Integration always recompiles,
   even when git reports no conflict — a line-level union of two projections is not the compile of
   the merged sources.

## Prove the payoff

- **Independent features:** two branches adding different feature shards merge with zero manual
  steps and a green validator run.
- **Archive move:** archiving a feature is one edit to its feature shard (`path:` + `status:`);
  recompile; graph and trackers stay green with no repoint anywhere (the F0005 acceptance).
- **Real collision:** two branches defining the same `capability:` id with different fields fails
  the integration with a `DivergentInsert` report naming the owning role — not YAML conflict markers.

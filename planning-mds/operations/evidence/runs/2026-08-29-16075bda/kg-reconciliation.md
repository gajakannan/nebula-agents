# Knowledge-Graph Reconciliation — F0003

**Run:** `2026-08-29-16075bda` · **Gate:** G7 · **Owner:** Architect
**Date:** 2026-08-30 · **Role switched:** read `agents/architect/SKILL.md`

## Gate

Bind the as-built source into the semantic graph so a future retrieval resolves an F0003
capability to the code that implements it. Authored as shards under
`planning-mds/kg-source/bindings/`, then compiled — `knowledge-graph/*.yaml` is generated
and is never hand-edited.

## Binding Delta

Six F0003 capabilities had **no** code bindings before this gate. `node_bindings` grows
from 7 to 13.

| Capability | Domain | Application | Infrastructure | Presentation | Tests |
|------------|--------|-------------|----------------|--------------|-------|
| `runtime-command-surface` | — | `commands.py` | — | — | 6 |
| `provider-capability-matrix` | `capabilities.py` | `capabilities.py` | `capability_probe.py` | — | 1 |
| `readonly-mcp-runtime-surface` | — | — | — | `mcp_server.py` | 1 |
| `evidence-artifact-index` | `artifacts.py` | `evidence.py` | `artifact_index.py`, `atomic.py` | — | 3 |
| `deterministic-evidence-summaries` | `summaries.py` | — | `summarizers.py` | — | 3 |
| `runtime-metrics-and-learning-review` | `metrics.py`, `proposals.py` | `metrics.py`, `learning.py` | `proposal_store.py` | — | 4 |

**CODE paths only.** Feature-doc paths move at the G8 archive transition; `engine/**` does
not, so every binding here stays resolvable afterwards. That is the reason the gate
restricts them, and it is why no `planning-mds/features/F0003-*` path appears above.

Verified after compiling: `lookup.py capability:readonly-mcp-runtime-surface` resolves to
`presentation/mcp_server.py` and its contract test. Orphan nodes: **0**.

## Canonical Nodes

**No canonical node was added, removed, or renamed.** All six capabilities, four entities,
and two workflows F0003 touches were declared in `kg-source/features/F0003.yaml` at Phase B
and verified at plan-review; this gate binds code to nodes that already existed rather than
inventing new ones. `--check-orphans` reports **0 orphan nodes**, confirming nothing was
left unbound.

ADR rationale for ADR-005 … ADR-009 was recorded against the governed nodes during Phase B,
so no rationale entries are added here either.

## A binding the compiler refused to let me have both ways

`presentation/cli.py` is the runtime command surface *and* the surface F0001 bound to
`capability:read-only-run-queries`. Claiming it for both produced:

```
warning: binding-overlap: path `engine/src/nebula_agents/presentation/cli.py` is claimed by
['capability:read-only-run-queries', 'capability:runtime-command-surface']
```

The warning is right: an overlap makes "which capability owns this file" ambiguous exactly
when retrieval needs an answer. `cli.py` genuinely serves both capabilities and the model
has no way to express a shared surface, so it **stays with its original owner** rather than
acquiring a second. `runtime-command-surface` is made findable through `commands.py` and
the six F0003 CLI tests instead.

Recorded rather than silently accepted, because the next person to extend `cli.py` will hit
the same choice.

## Findings

### S12-F1 (Medium) — `validate.py` prints `[PASS]` and exits 1

Adding bindings makes `coverage-report.yaml` stale, which `validate.py` reports as:

```
Errors:
- coverage-report.yaml is stale (run python3 scripts/kg/validate.py --write-coverage-report)

[PASS] knowledge-graph integrity checks passed.
```

It prints an `Errors:` block **and** `[PASS]`, then exits **1**. The three signals
disagree, and a reader taking any one of them alone reaches a different conclusion.

### S12-F2 (Low) — the SKILL and the action spec disagree at this gate

`agents/architect/SKILL.md` responsibility #14 says: *"After any of the above: run
`validate.py` and confirm exit 0."*

`agents/actions/spec/feature.yaml` G7 carries an explicit constraint:

> `forbid: --write-coverage-report` — *path-sensitive; deferred to G8 after the archive
> move relocates evidence paths.*

Regenerating the coverage report is the only thing that makes the exit code 0, and the
gate forbids it. Both instructions cannot be followed.

**Resolved in favour of the action spec.** It is specific to this gate, names the exact
flag, and gives a reason that is correct — the coverage report records evidence paths, and
G8's archive move relocates them, so a report written now would be regenerated
immediately. The SKILL's instruction is general guidance that did not anticipate this gate.

**Confirmed safe:** CI runs only `validate.py --check-reproducible`, which exits **0**.
Nothing is broken by leaving the report stale until G8, and `--check-reproducible` confirms
the committed generated files still equal `compile(source)`.

## Validator Results

| Check | Result |
|-------|--------|
| `compile.py` | Clean, no warnings after the overlap was resolved |
| `validate.py` | `[PASS]`, exit 1 solely on the deferred coverage report — see S12-F1 |
| `validate.py --check-drift` | PASS |
| `validate.py --check-reproducible` | **OK** — committed generated files equal `compile(source)` |
| `validate.py --check-orphans` | 0 orphan nodes |
| `--regenerate-symbols` / `--check-symbols` | exit 0 — symbol index **1608 → 2034** symbols, all on bound nodes |
| `--regenerate-decisions` / `--check-decisions` | exit 0 — 0 decision markers, 0 WHY |
| `--write-coverage-report` | **Not run.** Forbidden at G7; deferred to G8 |

All four generated-layer commands are recorded in `commands.log` through `exec-and-log.py`.
The symbol growth is the substantive result of this gate: 426 new symbols became reachable
because the six F0003 capabilities now have bindings to resolve through.

## Handoff to Closeout

G8 inherits three things from this gate:

1. **`coverage-report.yaml` is deliberately stale.** Regenerating it is forbidden here and
   is G8's job, *after* the archive move relocates evidence paths. Running it before the
   move would write paths that the move immediately invalidates.
2. **All bindings are CODE paths**, so the archive move does not break them. No binding
   points at `planning-mds/features/F0003-*`.
3. **Two framework findings**, S12-F1 and S12-F2, are recorded in `gate-decisions.md` and
   route to the framework owner rather than to F0003's closeout.

Nothing else is deferred. The manifest stays `in-progress`; `latest-run.json`, tracker
sync, and `pm-closeout.md` are G8's alone.

## Result

PASS

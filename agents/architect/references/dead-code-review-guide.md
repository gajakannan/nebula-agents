# Dead-Code Review Guide

The knowledge graph answers "what's covered" through canonical nodes, feature
mappings, code-index bindings, and the symbol layer. This guide covers the
inverse question: **what has drifted, or is dead?** Three complementary
checks close that loop:

- **Ontology orphans** — canonical nodes that nothing else references and that
  have no code-index binding. Surfaced by
  `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/validate.py --check-orphans`.
- **Code dead-code candidates** — bound symbols not reachable from any
  declared entry point. Surfaced by
  `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/dead-code.py`.
- **Code-index coverage gaps** — invocations from files outside
  `code-index.yaml` bindings that target bound symbols. The sidecar
  `planning-mds/knowledge-graph/unbound-but-referenced.yaml` is the
  substrate; surfaced by `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/validate.py
  --check-coverage-gaps` and the ad-hoc projection
  `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/coverage-gaps.py`.

The three checks attack the same underlying drift from different sides:
orphans see *unbound canonical nodes*, dead-code sees *unreached bound
symbols*, and coverage-gaps sees *unbound source files invoking bound
symbols*. A dead-code false positive driven by a missing `code-index.yaml`
binding usually appears in the coverage-gaps sidecar already.

All three are routing aids for release-readiness cleanup. Per
`solution-ontology.yaml.authority.precedence`, raw source files remain
authoritative — these reports nominate cleanup candidates; humans confirm
removal.

---

## When to run

| Cadence | Owner | Command |
|---|---|---|
| Release-readiness checkpoint | Architect | `validate.py --check-orphans` + `dead-code.py --safe-only` + `validate.py --check-coverage-gaps` |
| Feature close | Backend / frontend / ai engineer | `dead-code.py --node <touched-node>` to confirm no new orphans introduced; spot-check `coverage-gaps.py --by-target` if the feature adds new public surface |
| ADR creation | Architect | `validate.py --check-orphans` — confirm the new ADR has at least one rationale link, otherwise it ships as an orphan |
| Before deleting code | Anyone | `dead-code.py --min-confidence 0.85 --node <node>` to confirm the deletion candidate is unreached, **then** `coverage-gaps.py --by-target` to confirm no unbound caller would break |

Two release-readiness gates in `agents/templates/lifecycle-stage-template.yaml`
wire these into the lifecycle: `kg_orphan_check` runs the orphan + dead-code
sweep; `kg_coverage_gap_check` runs the unbound-source sweep. Both default
to warn so a first run doesn't drown reviewers; products opt into errors
with `--orphans-as-errors` / `--coverage-gaps-as-errors`.

---

## Ontology orphans

A canonical node is an orphan when **none** of the following hold:

1. A feature or story references it via any `REF_FIELDS` edge (`affects`,
   `governed_by`, `uses_schema`, `uses_api_contract`, `depends_on`,
   `restricted_to_role`, `enforced_by_policy`, `workflow_states`,
   `validated_by`, `supersedes`) or via the `feature` parent on a story.
2. Another canonical node references it via `related_nodes`, `allowed_roles`,
   `rationale.adr`, or workflow `transitions_to`.
3. A `code-index.yaml` binding exists with the node's id.

### Default exemptions

| Kind | Why exempt |
|---|---|
| `workflow_state` | Rolls up to its parent workflow; validator already checks state cohesion |
| `glossary_term` | Vocabulary anchor — value is being referenced from prose, not from edges |

Extend exemptions per product via `--orphan-exempt-kind <kind>` (repeatable).
Record any product-specific exemption in a product ADR so future architects
can see the reasoning.

### Severity

By default orphan findings are warnings; the validator still passes overall.
Promote them to errors with `--orphans-as-errors` when wiring a hard gate at
release readiness. The framework's
[lifecycle-stage-template.yaml](../../templates/lifecycle-stage-template.yaml)
ships `kg_orphan_check` as a release-readiness gate, not an
implementation-stage gate, so day-to-day development is not blocked.

### Resolution paths

For each orphan, pick one:

| Action | When |
|---|---|
| Add a feature mapping | Node represents real domain semantics that some feature uses, but the mapping has not been backfilled |
| Add a code-index binding | Node has implementation but `code-index.yaml` does not point to it yet |
| Remove the node from `canonical-nodes.yaml` | Node was added speculatively and no feature picked it up; remove and let the next feature reintroduce it if needed |
| Add a rationale link (ADRs only) | ADR exists but no canonical node cites it; the ADR is the orphan — add a `rationale:` entry on the node it actually governs |
| Record an exemption | The orphan is intentional (e.g., placeholder for a not-yet-built feature). Document why in a product ADR and add the kind to the gate's `--orphan-exempt-kind` list |

---

## Code dead-code candidates

`dead-code.py` walks the call graph in `symbol-index.yaml` starting from
**declared entry points**:

- **Bound entry-point nodes**: any symbol whose canonical node has `_kind` in
  `{endpoint, ui_route}` (override with `--entry-kind`).
- **Framework name suffixes**: `*Handler`, `*Listener`, `*Subscriber`,
  `*Consumer`, `*Plugin`, `*Adapter`, `*Middleware`, `*Filter`,
  `*Interceptor`. These are invoked by DI containers / pipelines / message
  buses; no caller appears in the symbol index.
- **Framework file patterns**: hosted services (`*HostedService.cs`,
  `*BackgroundService.cs`, `*Worker.cs`), endpoint registrations
  (`*Endpoints.cs`, `*Controller.cs`), bootstrappers (`Program.cs`,
  `Startup.cs`, `DependencyInjection.cs`), EF Core configurations
  (`*Configuration.cs`, `Configurations/`), DI extensions
  (`*Extensions.cs`, `*Module.cs`, `*Registration.cs`), seeders
  (`*SeedData.cs`, `*Seeder.cs`), migrations (`Migrations/`), and tests
  (`*Tests.cs`, `*.test.{t,j}sx?`, `*.spec.{t,j}sx?`, `test_*.py`,
  `*_test.py`, `tests/**`).

Reachability is BFS over the `callees` graph from those seeds.

### Confidence model

Each unreached symbol gets a confidence score in `[0, 1]`:

```
baseline                                              0.6   (unreached)
+0.2  no callers anywhere in the symbol index
+0.1  visibility is public
−0.2  visibility is private/internal/protected
−0.2  node has no feature-mapping refs (ontology orphan — already covered)
```

Score clamps to `[0, 1]`.

| Band | Score | Meaning |
|---|---|---|
| `weak` | 0.5–0.69 | Lower confidence — for C# usually a code-index-coverage gap (a calling file isn't bound), for TS/Python usually a cross-node call the same-node resolver missed. Inspect, do not remove without source-level confirmation |
| `default` | 0.7–0.84 | Plausible candidate. Default `--min-confidence`. Triage at feature close |
| `safe` | 0.85–1.0 | High-confidence candidate. `--safe-only` threshold. Default architect gate at release readiness |

The model biases toward false negatives (missing a dead symbol) rather than
false positives (proposing a removal that breaks code). When in doubt, the
score is lower.

### Skipped symbol kinds

`class`, `record`, `struct`, `interface`, `type`, `enum`, `delegate`,
`property`, and `constructor` are never flagged — they are declarations
rather than callable bodies. Method/function symbols on the same type carry
the real reachability signal.

### Known limitations

Call-edge resolution is per-language (see [symbol-index-guide.md](symbol-index-guide.md)
"Field reference"):

- **C#** — semantically resolved via Roslyn `SemanticModel`. Cross-node
  calls and interface dispatch are correctly tracked. The remaining
  blind spot is **code-index coverage**: a calling file that isn't
  bound in `code-index.yaml` is never parsed, so its invocations don't
  appear in the call graph. When a method looks dead, first verify
  every caller file is bound. The compilation/emission split
  (compilation-root files outside the bound set still contribute to
  semantic resolution and feed `unbound-but-referenced.yaml`) shrinks
  but does not eliminate this blind spot — file additions outside
  the compilation root remain invisible until added.
- **TypeScript** — semantically resolved via ts-morph
  `getExpression().getSymbol()` since the Phase A2 upgrade. Cross-node
  calls and class `implements`/`extends` heritage are tracked. Behaves
  like C# for triage purposes.
- **Python** — name-matched within the same canonical node only.
  Cross-node calls are invisible to the walk. The confidence dampers
  compensate by lowering the score when a symbol's node has
  feature-mapping refs that could carry an untracked cross-node flow,
  but some genuine false positives remain. The semantic-engine swap
  (Jedi or Pyright) is deferred until a product acquires enough Python
  surface to measure resolution accuracy meaningfully.

The triage rubric below explains how to recognize each class of false
positive.

---

## Triage rubric

For each candidate, ask in order:

1. **Is the symbol name a registration helper or framework callback the
   pattern list missed?** (e.g., `RegisterRoutes`, `OnModelCreating`,
   `BuildContainer`). If yes, extend `FRAMEWORK_ENTRY_NAME_SUFFIXES` or
   `FRAMEWORK_ENTRY_FILE_PATTERNS` in `scripts/kg/symbols.py` and re-run.
2. **Does the coverage-gaps sidecar know about this symbol?** Run
   `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/coverage-gaps.py --by-target` and
   look for the candidate symbol id in the output. If it appears, the
   sidecar already located one or more unbound caller files — bind
   them in `code-index.yaml` and regenerate. The sidecar is the
   automated form of the grep step below; it produces zero noise from
   matches inside string literals or comments.
3. **For C#/TS: is every file that could call this symbol bound in
   `code-index.yaml`?** Grep the codebase for the method name. If a
   caller file shows up but isn't in `code-index.yaml` and the sidecar
   missed it (most often: the file lives outside the configured
   compilation root, so the semantic resolver never saw the invocation),
   add the file to the appropriate canonical-node binding and
   regenerate. Grep remains the fallback when the sidecar's
   compilation-root walk doesn't reach the suspect path.
4. **For Python: does any file call this symbol from a different
   canonical node?** Same-node-resolution false positive. Either bind
   the calling file to the same canonical node, or record the symbol
   in a per-product ignore list referenced from a product ADR.
5. **Is the symbol genuinely unused?** Confirm `coverage-gaps.py
   --by-target` shows zero entries for it, then delete. Re-run
   `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/symbols.py` + `dead-code.py` to
   confirm the report shrinks.

---

## Examples (customers / orders)

| Finding | Action |
|---|---|
| `policy_rule:order-export` is an orphan: no feature `enforced_by_policy` references it, and no code-index binding exists | Remove the node — premature. The next feature that needs export policy can re-add it. |
| `adr:042` is an orphan: no canonical node lists it under `rationale.adr` | Add a `rationale:` entry on the node the ADR actually governs (e.g., `entity:order`). The ADR is the source of truth; the rationale link is what makes it discoverable. |
| `entity:order-attachment` is an orphan but a planned feature folder under `planning-mds/features/F0044-order-attachments/` exists | Add the feature to `feature-mappings.yaml.coverage.excluded_features` until the feature is implemented; the orphan disappears. |
| `dead-code.py` reports `CustomerService.GetByExternalIdAsync` at confidence 0.9; `coverage-gaps.py --by-target` shows it called from `OrderImportEndpoints.cs`, and that file is missing from `code-index.yaml` | Code-index coverage gap. Add `OrderImportEndpoints.cs` to the appropriate canonical-node binding (typically `entity:customer` or the endpoint's own node) and regenerate. The sidecar surfaced the missing binding without grep; the next run resolves the call. |
| `dead-code.py` reports a Python service method at confidence 0.9; grep shows it called from a different canonical node's file | Same-node-resolution limitation (Python extractor emits bare names; the semantic-engine swap is deferred). Either bind the caller into the same canonical node, or add a per-product ignore entry. |
| `dead-code.py` reports `LegacyOrderReceiptFormatter.Format` at confidence 0.9; both `coverage-gaps.py --by-target` and grep show zero references | Genuine dead code. Delete the file. Re-run `symbols.py`. |

---

## Telemetry

All four CLIs emit JSONL telemetry events via `kg_common.emit_telemetry`.
Key fields:

| Field | `validate.py --check-orphans` | `validate.py --check-coverage-gaps` | `dead-code.py` | `coverage-gaps.py` |
|---|---|---|---|---|
| `tool` | `validate` | `validate` | `dead-code` | `coverage-gaps` |
| `orphan_count` / `kept` / `candidates_count` | yes | `kept` (after exclusions) | yes | `after_filter` |
| `nodes_returned` / `nodes_count` | orphaned node ids | target nodes hit by unbound callers | nodes hosting candidates | target nodes hit |
| `confidence_band` | `high` if any orphans, else `low` | `high` if any kept findings | high/low by candidate count | high/low |
| `tokens_estimated` | yes | yes | yes | yes |

`eval.py` scores these against scenario fixtures the same way it scores
`lookup.py` and `hint.py`.

---

## Relationship to other gates

| Gate | Relationship |
|---|---|
| `symbol_index_sync` | Must pass before `kg_orphan_check` or `kg_coverage_gap_check` is meaningful — every downstream report assumes the symbol layer (and the sidecar regenerated alongside it) is in sync |
| `kg_coverage_gap_check` | Pairs with `kg_orphan_check` at release readiness. Coverage gaps usually explain a fraction of dead-code candidates; clearing them first shrinks the dead-code triage list |
| `inline_decisions_check` | Independent; a decision marker on an orphan node is its own signal that the node was intended to be reached |
| `boundary_genericness` | Independent; orphan detection is framework-generic and never names solution concepts |
| Risk scoring (`risk.py`) | Independent; a node with high `kg.risk` and an orphan child symbol is a stronger signal than either in isolation, but no automated rule combines them |

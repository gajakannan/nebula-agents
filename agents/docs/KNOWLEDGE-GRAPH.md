# Knowledge Graph

The framework-level reference for how the solution knowledge graph works,
what populates it, and how agents query it during planning and implementation.

This is the single source of truth for the KG model. Role SKILLs, action
docs, ROUTER, and AGENT-USE link here instead of restating it.

## Compiled projection (Phase B — F0006)

The knowledge graph is a **compiled database projection**, not a hand-maintained set of files.

- **Authored source — the only layer roles edit:** `planning-mds/kg-source/**` shards — one concept
  per small file, typed by directory, each directory owned by exactly one role
  (`nodes/` `bindings/` `policies/` `ontology/` → Architect; `features/` → PM; `exclusions/` → PM +
  Architect co-sign). See `kg-source/README.md` (in the product repo) for the schema, the per-kind ID
  grammar, and the REGISTRY/ROADMAP column↔field mapping.
- **Doc references are move-invariant:** a shard cites a feature doc **only** by its logical
  `F####/relative/path` form; the compiler resolves it through that feature shard's `path:`. Archiving a
  feature is **one `path:` edit + recompile** — no doc-ref repoint anywhere (this closes the F0005 gap;
  physical `planning-mds/features/…` paths in shards are rejected). Stable-root refs
  (`architecture/`, `api/`, `schemas/`, `security/`, `engine/`, `experience/`) pass through physical.
- **Generated projections — never hand-edit:** `scripts/kg/compile.py` deterministically emits the
  trio (`canonical-nodes.yaml`, `feature-mappings.yaml`, `code-index.yaml`), mirrors
  `solution-ontology.yaml`, and regenerates the REGISTRY/ROADMAP fenced table regions from the shards;
  `symbols.py`/`decisions.py`/`--write-coverage-report`/`generate-story-index.py` produce the remaining
  derived layers. The committed projection always equals `compile(source)` — CI enforces it
  (`validate.py --check-reproducible`; `.gitattributes` marks generated paths). **If a projection looks
  wrong, fix the shard (or the compiler) and recompile — never edit the generated file.**
- **`depends_on` and every tracker fact have a single home:** the feature shard. REGISTRY/ROADMAP feature
  tables are generated views of the feature shards (surrounding prose stays PM-authored).
- **Semantic merge, never text merge:** contributor branches merge shards by semantic ID via
  `merge3.py` (typed conflict taxonomy: divergent insert/update, delete-vs-update, orphan edge,
  uniqueness) — the **integrator** is the sole writer of generated files on the mainline and recompiles
  unconditionally (a textually clean git merge of a generated file is never trusted). See
  `ORCHESTRATION-CONTRACT.md`.

## Why It Exists

Every product built with this framework accumulates a large web of
features → architectural decisions → contracts → code. Without an index, an
agent assembling context for a feature must grep the repo, read whole
folders, and stitch the picture together from prose. That wastes tokens
and misses bindings the agent has no way to discover.

The knowledge graph is that index. It records, in stable typed nodes and
edges:

- which canonical entities, endpoints, schemas, workflows, capabilities,
  roles, and ADRs a feature touches,
- which source files implement each canonical node, and
- which symbols (methods, classes, calls, implements) live in those files.

Agents query the index through `lookup.py`, `hint.py`, and `blast.py`
instead of scanning the repo. The KG is a **retrieval aid only** — raw
artifacts (PRDs, ADRs, OpenAPI, schemas, source code) remain authoritative
on conflict.

## Mental Model

```
                  ┌──────────────────────────────────────────────────┐
                  │       solution-ontology.yaml  (vocabulary)       │
                  │  node_types · edge_types · id_patterns           │
                  │  Architect-curated · changes rarely              │
                  └──────────────────────────────────────────────────┘
                                       ▲ references node types from
                                       │
   ┌───────────────────────┐  ┌───────────────────────┐  ┌─────────────────────────┐
   │  feature-mappings     │  │  canonical-nodes      │  │  code-index             │
   │  feature → affects[]  │─▶│  entity · endpoint ·  │◀─│  node_id → paths{}      │
   │  feature → governed   │  │  capability · workflow│  │  (globs into            │
   │  feature → uses_schema│  │  · schema · role · …  │  │   engine/, experience/, │
   │  PM seeds in plan/A   │  │  Architect-curated    │  │   neuron/, etc.)        │
   │  Architect finalizes  │  │  on Phase B           │  │  Architect-curated      │
   │  in plan/B            │  │                       │  │  on Phase B + on new    │
   │                       │  │                       │  │  surfaces               │
   └───────────────────────┘  └───────────────────────┘  └─────────────────────────┘
              │                          │                          │
              │                          │           drives walk    │
              │                          │           ─────────────▶ ▼
              │                          │             ┌───────────────────────────┐
              │                          │             │  symbols.py               │
              │                          │             │  walks ONLY bound files   │
              │                          │             │  Python  → stdlib ast     │
              │                          │             │  C#      → Roslyn         │
              │                          │             │  TS/TSX  → ts-morph       │
              │                          │             └─────────────┬─────────────┘
              │                          │                           ▼
              │                          │             ┌───────────────────────────┐
              │                          │             │  symbol-index.yaml        │
              │                          │             │  methods, calls,          │
              │                          │             │  implements, line ranges  │
              │                          │             │  AUTO-GENERATED           │
              │                          │             │  via validate.py          │
              │                          │             │  --regenerate-symbols     │
              │                          │             └───────────────────────────┘
              ▼                          ▼                           ▼
          ┌────────────────────────────────────────────────────────────┐
          │                       QUERY LAYER                          │
          │  lookup.py F#### --tier 1     → feature slice (mappings +  │
          │                                  canonical + code_paths)   │
          │  hint.py <path>               → file → nodes/features/risk │
          │  blast.py <node|feature|file> → impact radius              │
          │  workstate.py escalate ...    → record context climb       │
          │                                                            │
          │  Joins happen at query time (kg_common.resolve_node).      │
          │  Raw yamls are NOT loaded into agent context directly.     │
          └─────────────────────────┬──────────────────────────────────┘
                                    ▼
                         ┌──────────────────────┐
                         │   agent / human      │
                         └──────────────────────┘

          ┌────────────────────────────────────────────────────────────┐
          │                  HEALTH / FRESHNESS                        │
          │  validate.py                  → ids resolve, paths exist   │
          │  validate.py --check-drift    → Casbin + memory-path drift │
          │  validate.py --check-orphans  → canonical nodes unreferenced
          │  validate.py --check-symbols  → symbols bind to real files │
          │  validate.py --write-coverage-report → refresh coverage    │
          │  decisions.py                 → harvest inline ADR markers │
          │  dead-code.py --safe-only     → symbol-level dead code     │
          │  cochange.py --coverage-gaps  → undeclared structural edges│
          │  pagerank.py / risk.py        → hub + risk surfacing       │
          └────────────────────────────────────────────────────────────┘
```

**Three rules to internalise:**

1. **Structure is hand-curated.** Architect writes the canonical nodes and
   their code-index glob patterns; PM seeds feature mappings during
   planning Phase A; Architect finalizes them in Phase B. Nothing scans
   the repo to invent these.
2. **Symbol layer is auto-extracted, but only inside curated paths.**
   `symbols.py` walks only the files declared in `code-index.yaml`. There
   are no broad repo scans. Coverage is exactly what the architect bound.
3. **Joins happen at query time.** Agents never load raw KG yamls into
   conversation context. They call `lookup.py`/`hint.py`/`blast.py`,
   which join the tables on demand and return a compact slice.

## File Inventory

All KG yaml files live at `{PRODUCT_ROOT}/planning-mds/knowledge-graph/`.
Scripts and AST extractors live at `{PRODUCT_ROOT}/scripts/kg/`.

| File | Owner | Source | What it holds |
|------|-------|--------|---------------|
| `solution-ontology.yaml` | Architect | hand | Vocabulary: node_types, edge_types, id_patterns, provenance/rationale schemas, retrieval contract |
| `canonical-nodes.yaml` | Architect | hand | Every shared canonical node (entity, workflow, capability, endpoint, schema, ADR, role, policy_rule, …) with rationale and notes |
| `feature-mappings.yaml` | PM seeds, Architect finalizes | hand | Per-feature/story edges into canonical layer (`affects`, `governed_by`, `uses_schema`, `depends_on`, `validated_by`, …) and excluded_features list |
| `code-index.yaml` | Architect | hand | `node_bindings`: canonical node id → glob list of repo-relative paths (backend/frontend/test buckets) |
| `symbol-index.yaml` | — | **auto** | Per-bound-file symbols (methods, classes, line ranges) with `calls` and `implements` edges resolved within the bound set |
| `coverage-report.yaml` | — | **auto** | Per-feature freshness, bound implementation surfaces, exclusion accounting, bus-factor flags |
| `decisions-index.yaml` | — | **auto** | Inline `// KG-DECISION:` markers harvested from source by `decisions.py` |
| `unbound-but-referenced.yaml` | — | **auto** | Invocations from unbound files into bound symbols (signal for missing bindings) |

Architect owns all canonical shared layers and code bindings. PM owns
feature/story/persona mappings and provenance. Implementation agents
**flag drift** when they discover it but do not silently redefine
canonical semantics — drift goes back to Architect or PM.

## How Symbol Extraction Works

`symbols.py` (`{PRODUCT_ROOT}/scripts/kg/symbols.py`) is the only writer of
`symbol-index.yaml`. It is the *only* part of the KG that touches real
source code. Its scope is bounded by `code-index.yaml.node_bindings` — it
does not scan the repo broadly.

For each file declared in a node binding:

| Language | Extractor | Implementation |
|----------|-----------|----------------|
| Python (`.py`) | stdlib `ast` | inline in `symbols.py` |
| C# (`.cs`) | Roslyn (`Microsoft.CodeAnalysis.CSharp`) | `scripts/kg/csharp-symbols/Program.cs` (subprocess) |
| TS/TSX (`.ts`, `.tsx`) | `ts-morph` (TS compiler API) | `scripts/kg/ts-symbols/extract.js` (subprocess) |

Each extractor emits, per symbol:

- `name`, `kind` (method/class/function/property)
- `line`, `end_line` (1-based span, consumed by `diff-impact.py`)
- `calls` — resolved `{name, container}` for invocations whose target the
  semantic model can determine; `{name, container: null}` for unresolved
  (external/framework) calls
- `implements` — interface members or base methods this symbol satisfies
  (lets `blast.py` follow polymorphic dispatch)

A per-file content-hash cache under `.kg-state/` ensures unchanged files
are not re-parsed.

Cross-file caller/callee edges are resolved each run by name-matching
within the same canonical node. The Roslyn and ts-morph extractors accept
`--compilation-root <dir>` to widen the parse scope (so external callers
resolve correctly) while still emitting symbols only for the bound set,
and `--sidecar <path>` to record invocations from unbound files that
target bound symbols — fed back into `unbound-but-referenced.yaml`.

This is what enables `lookup.py --implementers <interface-id>` and
`blast.py --file <path>` to return the right transitive set without
grepping.

## Querying the KG

Agents never read the yaml files directly. They go through the CLIs,
which all live at `{PRODUCT_ROOT}/scripts/kg/` and are agent-agnostic
(work from any terminal).

### `lookup.py` — feature/story/file scope materialization

| Form | What you get |
|------|--------------|
| `lookup.py F0007` | Full feature slice: target, affects, governed_by, uses_schema/api_contract, depends_on, validated_by, code_paths per canonical node, source_precedence |
| `lookup.py F0007-S0003` | Same shape, scoped to one story |
| `lookup.py F0007 --tier 1` | Minimal scope (target + direct refs only) |
| `lookup.py F0007 --tier 2/3/4` | Progressive expansion (one hop, two hops, full) |
| `lookup.py F0007 --fields ids` | Trim resolved-node summaries to ids only (`--fields ids\|summaries\|full`, default `full`) — verbosity *within* the selected tier, not field projection |
| `lookup.py F0007 --allow-missing` | Don't error on unmapped — useful for greenfield Phase A stubs |
| `lookup.py --file engine/src/Foo.cs` | Reverse lookup: file → canonical nodes → features/stories |
| `lookup.py --symbol <method-name>` | Symbols matching name with their containing node |
| `lookup.py --defines <proposed-name>` | Coverage check before introducing a new surface (catches duplicates) |
| `lookup.py --implementers <interface-symbol-id>` | All implementations of an interface member |
| `lookup.py --overrides <method-id>` | All overrides of a base method |
| `lookup.py --callers-only <symbol-id>` | Inbound call sites only |

### `hint.py` — compact pre-search routing

```
python3 {PRODUCT_ROOT}/scripts/kg/hint.py <repo-relative-path>
python3 {PRODUCT_ROOT}/scripts/kg/hint.py --json <repo-relative-path>
```

Emits a single short block: matched nodes, features, stories, Casbin
rules, top symbols, and risk flags for a file or directory. The
agent-agnostic entry point. Run this **before** any code search — it
replaces blind grep with ontology-routed exploration.

### `blast.py` — impact radius

| Form | What you get |
|------|--------------|
| `blast.py <node-id>` | Impacted features, stories, code bindings, Casbin rules, resolved files |
| `blast.py --file <path>` | Reverse-binds the file to nodes, then expands |
| `blast.py <feature-id>` | Walks the feature's canonical refs |
| `blast.py <node-id> --compact` | Counts only |

Run **before** editing shared semantics (entities, workflows, schemas) to
know what else moves with you.

### `workstate.py` — context resilience

| Form | Purpose |
|------|---------|
| `workstate.py --state-file <p> init --role <role> --scope <id> --run-id <uuid>` | Start session state |
| `workstate.py --state-file <p> decision "<summary>" --topic <slug>` | Record a decision (supports `--supersedes` for current-view filtering) |
| `workstate.py --state-file <p> escalate "<reason>" --nodes ... --opened-raw ...` | Record an explicit insufficient-context climb |
| `workstate.py --state-file <p> dump --compact` | Recover structured state after context compaction |
| `workstate.py --state-file <p> dump --current-view` | Decisions with superseded topics filtered out |
| `workstate.py --state-file <p> digest` | Terse work-narrative (done / decided / next) — cheaper to rehydrate on resume than a full `dump` |

### MCP server (same retrieval, structured transport)

For harnesses that speak MCP, the same retrieval is exposed as local stdio tools by
`{PRODUCT_ROOT}/scripts/kg/mcp_server.py` (committed `{PRODUCT_ROOT}/.mcp.json` launches
it). It is a thin adapter over the **same** CLI builders — identical semantics, minified
JSON payloads, telemetry tagged `source="mcp"`. The CLIs above remain the implementation
and the fallback for non-MCP harnesses.

| MCP tool | Wraps | Notes |
|----------|-------|-------|
| `kg_context` | `lookup.py` | feature/story slice or reverse file lookup; `fields=ids\|summaries\|full`, `tier 1-4`, `include` for top-level projection |
| `kg_hint` | `hint.py` | pre-search routing; returns a structured (possibly empty) payload |
| `kg_blast` | `blast.py` | impact radius; `compact` for summary only |
| `kg_validate` | `validate.py` (read-only modes) | `check-drift\|check-symbols\|check-orphans\|check-coverage-gaps` → `{ok, errors, warnings}`; never mutates |
| `kg_workstate` | `workstate.py` | the only writer; actions init/decision/escalate/dump/digest; writes **only** under `{PRODUCT_ROOT}/.kg-state/workstate/<session>.yaml` (traversal/KG-dir writes rejected) |

**Launch config — two cases:**

- Session launched **from `{PRODUCT_ROOT}`** → the committed `{PRODUCT_ROOT}/.mcp.json`:
  ```json
  { "mcpServers": { "kg": { "command": "python3", "args": ["scripts/kg/mcp_server.py"] } } }
  ```
- Session launched **from the `nebula-agents` framework cwd** → the relative path won't
  resolve, so point at the product copy via `NEBULA_PRODUCT_ROOT` (the same env the
  framework already uses to locate the product repo — see AGENT-USE.md §resolution):
  ```json
  { "mcpServers": { "kg": { "command": "python3",
      "args": ["${NEBULA_PRODUCT_ROOT}/scripts/kg/mcp_server.py"] } } }
  ```

The server self-locates the KG from its own file path, so no `PRODUCT_ROOT` env is needed
at runtime — only the launch path must resolve. MCP-capable harnesses should prefer the
`kg_*` tools; the CLIs above are the fallback for harnesses without MCP.

### Other CLIs

| Tool | Purpose |
|------|---------|
| `pagerank.py --top N [--type entity]` | Hub nodes by PageRank — surfaces high-attention entities |
| `risk.py` | Composite risk score per canonical node (high ≥ 7, critical ≥ 9 bands) |
| `cochange.py --top N [--coverage-gaps]` | Git co-change edges; `--coverage-gaps` finds unbound files that co-change with bound files |
| `dead-code.py --safe-only` | Symbol-level dead-code candidates |
| `decisions.py` | Harvest `// KG-DECISION:` markers into `decisions-index.yaml` |
| `diff-impact.py <range>` | Map a branch's diff to impacted canonical nodes — used to verify planned blast radius |
| `eval.py --since <ref>` | Score retrieval quality against historical telemetry |
| `telemetry_rotate.py <path>` | Rotate `.kg-state/telemetry.jsonl` |

## Lifecycle: Who Updates What, When

The KG only stays useful if updates happen in the same change that makes
them necessary. Each row below names the **trigger**, the **owner**, and
the **artifact**.

| Trigger | Owner | Update |
|---------|-------|--------|
| New feature planned (Phase A) | PM | Seed minimal `feature-mappings.yaml` entry: id, path, status, obvious dependencies/high-confidence `affects` |
| Architecture decided (Phase B) | Architect | Complete `affects`, `governed_by`, `uses_schema`, `depends_on`, `validated_by` in `feature-mappings.yaml` |
| New entity / endpoint / workflow / capability / schema / role / policy_rule | Architect | Add canonical node to `canonical-nodes.yaml` (with `notes` for non-obvious context) |
| New code surface (file/folder that implements a canonical node) | Architect | Add glob to `code-index.yaml` `node_bindings[node].paths` |
| New ADR landed | Architect | Add `rationale: [{adr, section, summary}]` to every canonical node the ADR governs; inline `// KG-DECISION:` markers as needed, then run `decisions.py` to harvest |
| Code edited in bound files | (auto) | Run `validate.py --regenerate-symbols` — Roslyn/ts-morph/ast re-walks only the bound set; cache makes it cheap |
| Code moved or file renamed | Architect | Update `code-index.yaml` globs; `validate.py` will flag stale paths until fixed |
| Casbin policy changed | Architect | Update or add `policy_rule` canonical nodes; `validate.py --check-drift` catches policy.csv ↔ KG mismatch |
| Feature folder archived | PM | Update `path:` in `feature-mappings.yaml` (e.g. `features/F0007-…` → `features/archive/F0007-…`) and `status:` to `archived-done` |
| Cross-feature dependency you're unsure about | PM | Use edge provenance: `{id: feature:F0008, provenance: inferred, confidence: 0.6}` — validator warns if confidence < 0.5 |
| Speculative or contested link | Architect | Mark `provenance: ambiguous` — validator always warns until reviewed |
| Plan gate (G4 Ontology Sync) | Architect | Run `validate.py --write-coverage-report` then `validate.py` (must exit 0) |
| Feature exit | Architect/QE | Re-run `validate.py --regenerate-symbols` then `validate.py --check-symbols --check-drift` |
| Release-readiness checkpoint | Architect | `validate.py --check-orphans` (decide remove/bind/exempt for each), `dead-code.py --safe-only`, `risk.py` (high/critical band review), `bus_factor_flag` review in `coverage-report.yaml` |
| Touching an interface/base method | Architect | `lookup.py --implementers <id>` (or `--overrides`) — the returned set is the change scope |
| Considering a new node/service/method name | Architect | `lookup.py --defines <name>` before introducing, to catch duplicate surfaces |
| Plan claims blast radius X | Architect | `diff-impact.py <feature-branch-range>` — surfaced nodes outside the stated scope mean widen the plan or narrow the change |

## Health Checks

All run from `{PRODUCT_ROOT}/scripts/kg/`. Use them defensively — they
catch drift before it propagates.

| Command | What it catches |
|---------|-----------------|
| `validate.py` | Broken IDs, references that don't resolve, glob patterns that match zero files, uncovered feature directories, stale `coverage-report.yaml` |
| `validate.py --write-coverage-report` | Refreshes `coverage-report.yaml` (always run before the bare `validate.py` if KG changed) |
| `validate.py --check-drift` | Casbin policy ↔ `policy_rule` node mismatch. Add `--memory-dir <path>` to also scan an external memory directory for stale repo-path references |
| `validate.py --check-symbols` | Each symbol-index entry resolves to a canonical node and a real file |
| `validate.py --regenerate-symbols` | Re-runs `symbols.py` before validating (Roslyn/ts-morph/ast); use after code edits in bound files |
| `validate.py --check-decisions` | Inline KG-DECISION markers resolve to real files, nodes, symbols, and ADRs |
| `validate.py --regenerate-decisions` | Re-runs `decisions.py` before validating |
| `validate.py --check-orphans` | Canonical nodes with no incoming refs and no code-index binding |
| `validate.py --orphans-as-errors` | Promotes orphan findings to errors. `--orphan-exempt-kind KIND` adds an exemption (repeatable) |
| `validate.py --check-coverage-gaps` | Invocations from files outside `code-index` that target bound symbols (reads `unbound-but-referenced.yaml`) |
| `validate.py --coverage-gaps-as-errors` | Promotes coverage-gap findings to errors. `--coverage-gap-exclude GLOB` adds an exemption |
| `validate.py --check-untested` | Public methods/functions with no caller in a test-classified file |
| `validate.py --untested-as-errors` | Promotes untested-surface findings to errors. `--untested-exempt-node NODE_ID` exempts a node |

## Failure Modes & Fallbacks

| Symptom | Cause | Response |
|---------|-------|----------|
| `lookup.py F####` returns empty / target only | Feature not yet in `feature-mappings.yaml` (greenfield or in the `excluded_features` list) | Fall back to file-centric reads. Backfill the mapping as part of the same change set. Do not invent edges. |
| `lookup.py` returns matches with `provenance: inferred, confidence < 0.5` or `provenance: ambiguous` for a node you're about to edit | Speculative link, not verified | **Halt the gate.** Run `workstate.py escalate "<reason>" --nodes ... --opened-raw ...`, open the raw artifacts, then proceed. Do not edit on weak matches. |
| `validate.py` reports unknown ref | Mapping points at a canonical id that doesn't exist | Either add the canonical node (if the semantics are real and shared) or remove/correct the ref |
| `validate.py` reports glob with no matches | Code moved/renamed; binding is stale | Update the glob in `code-index.yaml` to the new location |
| `--check-orphans` flags a canonical node | Node has no incoming refs and no code binding | Decide one of: (a) add a feature mapping or code binding that closes the gap, (b) remove the node if premature, (c) record an exemption in the gate config (rationale anchors, deferred features) |
| `--check-coverage-gaps` flags a file | An unbound file calls into bound symbols — likely a missing binding | Add the file's directory to the relevant `code-index` entry, or document why it's intentionally unbound |
| Symbol-index entry resolves to a missing file | Code deleted without updating bindings | Drop the binding glob; rerun `--regenerate-symbols` |
| Casbin drift (`--check-drift`) | `policy.csv` and `policy_rule` nodes diverged | Update whichever is wrong (raw artifacts win); add or remove `policy_rule` nodes to match |
| `pm-closeout.md` references a path that no longer exists | Memory-path drift | Run `validate.py --check-drift --memory-dir <memory-path>` to find and fix |

**Source precedence on conflict** (declared in `solution-ontology.yaml`):

1. Target feature folder and `feature-assembly-plan.md` for feature-local
   implementation intent.
2. `planning-mds/architecture/decisions/**` for architectural decisions.
3. `planning-mds/api/*.yaml` and `planning-mds/schemas/*.json` for
   interface and payload contracts.
4. `planning-mds/architecture/data-model.md` and
   `planning-mds/domain/glossary.md` for domain definitions.
5. `planning-mds/knowledge-graph/*.yaml` for compressed retrieval and
   routing.

If KG and raw disagree, raw wins. Fix the source first if it's wrong;
then fix the KG mapping in the same change set.

## Scope: What the KG Is Not

- **Not a runtime.** The application does not read these yamls at run
  time. Removing them does not change app behavior, only retrieval cost.
- **Not authoritative.** PRDs, ADRs, OpenAPI, JSON Schema, and source
  code are. The KG is a retrieval index over them.
- **Not a substitute for reading raw artifacts on conflict, drift, or
  verification.** It is a starting context, not a final answer.
- **Not auto-discovered.** Structural bindings are hand-curated by the
  Architect. The symbol layer is auto-extracted but only within those
  bindings — there are no broad repo scans anywhere in the KG.

## For Framework Maintainers

Adding a new node type:

1. Declare it in `solution-ontology.yaml` `node_types` (owner, description).
2. Add an `id_patterns` entry with examples.
3. If it participates in new edges, add `edge_types` rows (`from`, `to`,
   description).
4. Update any actions whose retrieval contract needs to load it.
5. Add a row to the File Inventory table above if the new type lands in a
   new yaml.

Adding a new language extractor:

1. Implement the extractor as a subprocess matching the contract in
   `csharp-symbols/Program.cs` (read JSON file list from stdin, write JSON
   symbol records to stdout). Each record needs `name`, `kind`, `line`,
   `end_line`, `calls`, `implements`.
2. Wire dispatch in `symbols.py` keyed by file extension.
3. Document the language in the **How Symbol Extraction Works** table
   above.
4. Ensure CI can install the toolchain (Roslyn = .NET SDK; ts-morph =
   Node + `pnpm install` in the extractor dir).

Adding a new validator mode:

1. Add the flag to `validate.py` with a `--help` string that names the
   exact check.
2. Add a row to **Health Checks** above with the *what it catches*
   description.
3. If the mode introduces a fail-by-default behavior, also add the
   `--<mode>-as-errors` variant so callers can opt into hard failure.
4. If the mode warrants a lifecycle trigger (e.g. release-readiness),
   add it to the **Lifecycle** table.

## Cross-References

- `agents/docs/CONTEXT-ENGINEERING.md` — the context-engineering strategy
  (select / compress / write / isolate) the KG query layer, tiering, and
  `workstate.py` serve. This doc is the *how the KG works*; that one is the
  *why it's shaped for context*.
- `agents/ROUTER.md` — task-to-reference routing; KG tools row points here.
- `agents/docs/AGENT-USE.md` — session setup and prompt patterns; defers
  KG mechanics to this doc.
- `agents/architect/SKILL.md` — Architect's KG responsibilities; the
  *what to do as Architect* lives there, the *how the KG works* lives
  here.
- `agents/product-manager/SKILL.md` — PM's KG responsibilities (mapping
  seeds, provenance annotations).
- `agents/actions/plan.md`, `agents/actions/feature.md` — action-level
  retrieval contracts, gates, and validation order.
- `{PRODUCT_ROOT}/planning-mds/knowledge-graph/` — the live KG data for a
  given product (yamls only; no docs).
- `{PRODUCT_ROOT}/scripts/kg/` — CLIs, AST extractors, and `kg_common.py`
  (`resolve_node` is where joins happen).

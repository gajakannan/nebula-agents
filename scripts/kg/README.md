# scripts/kg — Knowledge-Graph Toolchain

CLIs over `planning-mds/knowledge-graph/`. The framework-level reference for
the KG model is `nebula-agents/agents/docs/KNOWLEDGE-GRAPH.md`; this README
documents only what lives in this directory that isn't covered there yet.

## Semantic merge — `merge3.py` (F0006-S0001)

Three-way merge of one **curated** KG file by semantic record id, replacing
line-level git merges of KG YAML. Curated files: `canonical-nodes.yaml`,
`feature-mappings.yaml`, `code-index.yaml`.

```bash
# during an integration, from the repo root
python3 scripts/kg/merge3.py planning-mds/knowledge-graph/canonical-nodes.yaml \
  --base <merge-base-ref> --ours <target-ref> --theirs <source-ref> \
  [--dry-run] [--json report.json] [--full-validate]
```

Inputs are file paths or git refs. Exit codes: `0` clean merge (canonical
output written), `1` typed conflicts or constraint violation (nothing
written), `2` usage/input error.

**Merge semantics** (record = list element carrying `id`):

| Situation | Result |
|-----------|--------|
| Same content, different serialization | converges (canonicalize before compare) |
| Added/changed/deleted on one side only | kept |
| Added on both sides, identical | converges |
| Added on both sides, different | `DivergentInsert` |
| Deleted vs updated | `DeleteVsUpdate` |
| Changed differently — same scalar field | `DivergentUpdate` |
| Changed differently — different fields | field-level recursion, merges |
| Set-like list (default) changed on both sides | three-way set union, sorted |
| Ordered list (`states`, `transitions_to`, `rules`) reordered on both sides | `OrderedListConflict` |
| Merged result re-adds a duplicate id | `UniqueViolation` |
| Merge deletes a node something still references | `OrphanEdge` |
| `--full-validate`: validator fails on merged graph | `ConstraintViolation` (rolled back) |
| Similar names across different ids | `SemanticDuplicateWarning` (advisory) |

Every conflict names its **owning role** (`architect` for node/binding
kinds, `product-manager` for feature/story kinds, both for exclusions).
Output is all-or-nothing: one unresolved conflict blocks the whole file.
Object-form edge refs (`{id:, provenance:, confidence:}`) are references,
never record definitions.

Generated projections (`symbol-index.yaml`, `coverage-report.yaml`,
`unbound-but-referenced.yaml`, `decisions-index.yaml`) are **never merge
inputs** — regenerate them after merging the curated sources, and never
trust a textually clean git merge of them.

**ID-level diff** (used to prove the one-time canonicalization commit
changed nothing semantically, and handy before/after any KG edit):

```bash
python3 scripts/kg/merge3.py planning-mds/knowledge-graph/feature-mappings.yaml \
  --semantic-diff HEAD planning-mds/knowledge-graph/feature-mappings.yaml
```

## Tracker-table merge — `merge3.py` on markdown trackers (F0006-S0002)

The same CLI merges `REGISTRY.md` and `ROADMAP.md`: pass the tracker path as
the target and merge3 dispatches by file type. Feature tables are merged as
records keyed by feature ID (a row is a record, cells are fields, same
conflict taxonomy, every conflict routes to the **PM**). Row ordering is
never a conflict — it is recomputed per table:

| Table | Order rule |
|-------|-----------|
| REGISTRY Active / Planned / Legacy | feature-ID ascending |
| REGISTRY Retired / Archived | newest-first by date column, feature-ID-desc tiebreak |
| ROADMAP Now / Next / Later / Abandoned / Completed | manual (operator priority): a changed side's order is adopted; both-sides-added rows are woven in (ours first at equal anchors); real double reorders conflict |

Also handled: `**Next Available Feature Number:**` merges to the max
(monotonic counter); section membership is a field (a feature moved to two
different sections conflicts); table column changes conflict; prose merges
with an append-tolerant rule and conflicts to the PM otherwise; unknown
tracker files and unkeyable rows fail loudly (no silent text merge).
`STORY-INDEX.md` is generated — merge3 rejects it; regenerate with
`generate-story-index.py` after merging.

Per-table rules live in `TRACKER_CONFIGS` (`scripts/kg/tracker_merge.py`);
new tracker tables must be registered there before they can merge.

## Canonical serialization (`kg_common.py`)

`canonicalize_document` / `canonical_dump` / `canonical_equal`: one
deterministic serializer for the curated files — priority-then-alphabetical
mapping keys, record lists sorted by `id`, scalar lists de-duplicated and
sorted, `ORDERED_LIST_FIELDS` (`states`, `transitions_to`, `rules`) keep
authored order. Idempotent; byte-stable across machines. The curated trio
was canonicalized once (no-semantic-change commit) so formatting noise can
never reappear in merges. If you add an order-significant list field to the
KG schema, register it in `ORDERED_LIST_FIELDS` — unregistered structures
conflict rather than silently union.

Tests: `scripts/kg/tests/test_merge3.py`.

## Shard validation — `shard_validate.py` (F0006-S0004)

Validates the authored shard layer (`planning-mds/kg-source/**`) against the schema + ownership
contract in `planning-mds/kg-source/README.md`: directory↔kind agreement, ID grammar (reusing the
ontology's `id_patterns`), references are IDs only, doc refs are logical (`F####/…`) or stable-root,
one-concept-per-file (or an allowed per-kind bundle), and owner-resolvability.

```bash
python3 scripts/kg/shard_validate.py                 # all shards under kg-source/
python3 scripts/kg/shard_validate.py <file|dir> ...  # specific shards
```

Standalone and importable (the compiler calls it). Tests: `scripts/kg/tests/test_shard_validate.py`.

## Compile — `compile.py` (F0006-S0005)

Deterministic compiler: the only sanctioned producer of the projection trio
(`canonical-nodes.yaml`, `feature-mappings.yaml`, `code-index.yaml`) from `kg-source/` shards.
Validates shards, resolves logical `F####/…` doc refs through each feature shard's `path:` (absorbs
F0005), assembles + emits the trio through `kg_common.canonical_dump` (byte-identical anywhere),
mirrors `solution-ontology.yaml` verbatim into the generated tree, and runs compile-time analysis
(duplicate IDs = hard error; name-similarity + binding-glob overlap = advisory, blocking under
`--strict`). All-or-nothing: nothing is written unless the whole build succeeds.

```bash
python3 scripts/kg/compile.py                 # shards → projection trio (+ ontology mirror)
python3 scripts/kg/compile.py --check         # compile to memory, diff committed (reproducibility)
python3 scripts/kg/compile.py --strict        # analysis warnings become blocking
python3 scripts/kg/compile.py --generators \  # also drive decisions/coverage/story-index …
    --framework-root ../nebula-agents         # … then strip their generated_at timestamps
```

Feature shards carry the full tracker-projected field set; `compile.py` emits only the *technical*
subset into `feature-mappings.features` (presentation fields render to the trackers at S0007) and
expands each feature's `story_mappings:` block into `feature-mappings.stories`. Tests: `scripts/kg/tests/test_compile.py`.

## Decompile (migration-only) — `decompile.py` (F0006-S0006)

Migration utility that explodes a monolithic KG + REGISTRY/ROADMAP feature tables into
`planning-mds/kg-source/**` shards (rewriting physical feature-doc refs to logical `F####/…`), gated
by `compile(decompile(graph)) == graph` byte-identical. Nebula Agents adopted the shard baseline on
2026-07-15; `kg-source/` is now the authored truth and the `knowledge-graph/` trio + ontology are
generated. `decompile.py` is retired from the normal flow but kept for future migrations:

```bash
python3 scripts/kg/decompile.py --check   # dry-run: partition + round-trip, write nothing
python3 scripts/kg/decompile.py           # write kg-source/ shards (migration)
```

Tests: `scripts/kg/tests/test_decompile.py` (real-graph round-trip, idempotency, count-reconciliation,
anomaly gate).

## Tracker generation — `tracker_gen.py` (F0006-S0007)

Generates the **REGISTRY.md** and **ROADMAP.md** feature tables from `kg-source/features/**`, writing
only inside fenced regions (`<!-- generated:begin <file>:<table> -->` … `<!-- generated:end … -->`);
surrounding PM-authored prose is byte-untouched. REGISTRY placement/sort is derived
(`retired_date`/`superseded_by`→Retired, `archived_date`→Archived, `planned`→Planned, else Active;
Retired/Archived sort date-desc + ID-desc); ROADMAP order follows each feature's captured
`roadmap_order`. Closes the byte-identical tracker round trip (zero-diff regeneration on unchanged
shards). `compile.py` drives it on the real tree.

```bash
python3 scripts/kg/tracker_gen.py           # regenerate REGISTRY/ROADMAP fenced regions
python3 scripts/kg/tracker_gen.py --check   # zero-diff check (regions match shards)
```

The S0002 tracker-row merge (`tracker_merge.py`) is now **transition-only** — with tables generated,
merges recompute the fenced regions from shards rather than merging rows. BLUEPRINT.md §3.3 generation
is **deferred** (it's a bespoke prose list with stale duplicates, not a clean projection). Tests:
`scripts/kg/tests/test_tracker_gen.py`.

## Reproducibility + git policy — `reproducibility.py` (F0006-S0008)

`validate.py --check-reproducible` (delegates to `reproducibility.py`) is the single check CI and the
integrator use to prove the committed generated files are a pure function of source:

```bash
python3 scripts/kg/validate.py --check-reproducible   # compile-check + shard-validate + rules + .gitattributes
python3 scripts/kg/reproducibility.py --write-gitattributes  # regenerate .gitattributes from the manifest
```

It fails (naming the file + remediation) on a hand-edited/stale projection or tracker region, an
invalid shard, `.gitattributes` drift, an archived feature reachable by a non-archive path, a
suppression-ledger entry without a rationale, or a binding path that matches no file. A
`KG-Reproducibility-Override: <reason>` trailer on the head commit downgrades failures to logged
warnings (emergencies only).

**Manifest + git policy.** `generated_paths.yaml` is the one authoritative list of every generated
path with a `whole-file` / `fenced-region` granularity marker. `.gitattributes` is **generated from it**
(never hand-listed): whole-file paths get `linguist-generated` + `merge=ours`; the fenced-region
trackers (REGISTRY/ROADMAP) get neither (both are file-scoped and would hide/drop PM prose). The
`merge=ours` driver needs a one-time local `git config merge.ours.driver true`.

**CI.** `.github/workflows/kg-reproducibility.yml` runs `--check-reproducible` on every PR, then (full
scope) rebuilds the symbol/decision/coverage indexes and diffs. Committed `symbol-index`/
`decisions-index`/`unbound-but-referenced` carry no `generated_at` (stripped, S0005-D1) so the
regenerate-and-diff is deterministic. Tests: `scripts/kg/tests/test_reproducibility.py`.

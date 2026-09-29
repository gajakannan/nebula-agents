# Semantic Query Architecture

Design memo for the semantic-query work scoped in
`_private-plans/semantic-agent-tooling-prompt.md`. The prompt fixes the
architectural direction (per-language static extractors feeding a precomputed
symbol graph, no LSP) and the phasing. This memo closes the design questions
that block code from being written: data shapes, CLI surfaces, classification
conventions, and the gating order between phases.

Authority remains with raw source per
`solution-ontology.yaml.authority.precedence`. Everything below is a routing
aid. New behaviour is additive — existing `lookup.py`, `hint.py`, `blast.py`,
`dead-code.py`, and `validate.py` keep their current shapes and exit codes.

---

## 1. Compilation/emission split — sidecar schema

Each extractor (C#, TS, Python) takes a `--compilation-root` parameter that
widens the parse scope beyond `code-index.yaml` bindings. The extractor emits
`SymbolRecord` entries only for files in the bound-files list, and emits a
side report for every invocation that originates in a file *outside*
the bound-files list but targets a *bound* symbol.

Each extractor accepts a `--sidecar <path>` argument and writes the sidecar
as a JSON array to that path. The orchestrator passes a per-language temp
path, reads each file after the subprocess exits, then aggregates. This
keeps stdout (symbols payload) and stderr (logs) cleanly separated and
makes the sidecar independently testable. The per-extractor sidecar shape
is:

```json
[
  {
    "source_file": "engine/tests/Nebula.Tests/Integration/CustomerEndpointTests.cs",
    "source_line": 84,
    "target": {
      "name": "CancelAsync",
      "container": "CustomerService"
    }
  }
]
```

The orchestrator (`symbols.py`) aggregates sidecars across languages and
writes `planning-mds/knowledge-graph/unbound-but-referenced.yaml` in this
shape:

```yaml
version: 0
generated_at: '2026-05-17T00:00:00+00:00'
summary:
  total_invocations: 142
  by_language:
    csharp: 88
    typescript: 54
    python: 0
  source_files: 27
  bound_targets: 19
invocations:
  - source_file: engine/tests/Nebula.Tests/Integration/CustomerEndpointTests.cs
    source_line: 84
    language: csharp
    target_symbol: symbol:entity-customer:customer-service.cancel-async
    target_node: entity:customer
  - source_file: experience/tests/orders/cancel-flow.test.tsx
    source_line: 41
    language: typescript
    target_symbol: symbol:entity-order:order-service.cancel
    target_node: entity:order
```

Resolution rules:

- `target_symbol` resolves through the same global `(container, name)` lookup
  the orchestrator uses for caller/callee edges. If the target cannot be
  resolved to a stable id (e.g. ambiguous overloads), the entry falls back to
  `target_name` / `target_container` strings and `target_symbol` is omitted.
  Consumers must tolerate both shapes.
- `source_file` is repo-relative, always.
- `language` is the source-file's language. Cross-language calls (a TS test
  invoking a C# REST endpoint) are out of scope — those are HTTP boundaries,
  not symbol edges, and live in the endpoint canonical node, not here.

The unbound-but-referenced file is consumed by:

- `coverage-gaps` CLI (Phase B(c)) — thin projection.
- `validate.py --check-coverage-gaps` (Phase D) — gating with exemptions.

Both consumers read by `version:` and degrade gracefully if the file is
absent (warn, exit zero).

---

## 2. Line-range → symbol mapping for `diff-impact.py`

`symbol-index.yaml` stores `line:` (declaration start) only. Mapping a git
diff hunk to the enclosing symbol therefore needs a range. Two viable
approaches:

| Approach | Cost | Accuracy |
|---|---|---|
| A. Derive ranges in `diff-impact.py` by sorting symbols per file and treating each symbol's range as `[symbol.line, next_symbol.line)` with the last symbol running to EOF | Zero schema change. Cheap in-memory pass per file. | Coarse — nested classes overshoot; properties between two methods get attributed to the earlier method. |
| B. Extend extractors to emit `end_line`, persist on `SymbolRecord` and in `symbol-index.yaml` | One field per record. Symbol-index volume grows ~5%. Each extractor needs the equivalent of a syntax-node end-position read (cheap in all three). | Exact. |

**Decision: ship B.** `end_line` is cheap to extract (Roslyn `Span.End`,
ts-morph `getEndLineNumber()`, Python `ast.AST.end_lineno`), the schema impact
is one new field, and approach A is wrong in the common case of a property
declared between two methods. The orchestrator already strips fields with
`to_index_dict()`, so adding `end_line` to `SymbolRecord` and emitting it
on-disk is a two-line change.

Diff-to-symbol mapping rule: a changed hunk `[hunk_start, hunk_end]` in
`file` impacts every symbol whose `[line, end_line]` intersects the hunk.
Multiple symbols can match (overlapping class + nested method); all are
reported.

When `end_line` is missing (legacy entries during rollout), `diff-impact.py`
falls back to approach A so the tool still runs.

---

## 3. Symbol-id stability under rename

The current id scheme is
`symbol:<node-slug>:<container-or-file-stem>.<name>`. A pure method rename
(`CancelAsync` → `Cancel`) changes the id. That's a problem for
`diff-impact.py`, which needs to identify "this symbol was edited" across the
before/after of a rename.

**Decision: keep the current id scheme; resolve renames at query time, not in
the id.** A content-hash component would make ids opaque and break the
human-readability that the architect-facing tooling relies on.

`diff-impact.py` handles renames by:

1. Parsing the diff for rename markers (`git diff --find-renames` /
   `similarity index` headers).
2. Re-resolving any symbol whose declaration line lies inside a renamed
   range, using the new file path and the new name as parsed from the diff
   hunk.
3. Reporting both the pre-rename and post-rename ids in the blast set, so
   downstream consumers can match against either side of the rename.

This keeps the id scheme simple, makes rename handling local to one CLI, and
costs nothing for non-rename diffs.

Open caveat: pure method renames inside an unrenamed file are not detected
by `git diff --find-renames` (that flag operates on whole files). For
intra-file renames, `diff-impact.py` reports the *new* id and an
`unresolved_pre_rename: true` flag; reviewers handle the gap manually. The
frequency of this case will be measured from telemetry; if it dominates,
revisit with a stronger detector (line-anchor heuristic, AST diff).

---

## 4. `implements` persistence in `symbol-index.yaml`

The C# extractor emits `implements: [{name, container}, ...]`, the
orchestrator stores them on `SymbolRecord.implements`, and `to_index_dict()`
*strips* them before writing to `symbol-index.yaml`
(`scripts/kg/symbols.py:96`). `--implementers` and `--overrides` (Phase B(a))
need this data at query time.

**Decision: stop stripping `implements` on write.** Add it to the on-disk
schema as a peer of `callers` and `callees`. Each entry is the resolved
`symbol-id` of the satisfied member (not the raw `{name, container}` pair).

Implementation note (corrects an earlier draft of this memo):
`scripts/kg/symbols.py:577-584` currently resolves `impl.implements` inline
during the dispatch loop *and discards the resolved record* — only the
synthetic caller/callee edges land on the impl. Persistence therefore
requires three small changes, not one:

1. In the dispatch loop, replace `impl.implements` (currently a list of raw
   `{name, container}` dicts) with the list of resolved interface-member
   symbol ids encountered.
2. Stop the `d.pop("implements", None)` in `to_index_dict()`.
3. Sort/dedupe the persisted list for stable diffs.

Total delta is roughly 10 lines, all in `symbols.py`.

Updated `symbol-index.yaml` excerpt:

```yaml
- id: symbol:entity-customer:customer-service.cancel-async
  node: entity:customer
  kind: method
  name: CancelAsync
  file: backend/src/Customers/Services/CustomerService.cs
  line: 142
  end_line: 168
  signature: 'public async Task<Result> CancelAsync(...)'
  visibility: public
  language: csharp
  container: CustomerService
  callers: [...]
  callees: [...]
  implements:
    - symbol:entity-customer:i-customer-service.cancel-async
```

`--implementers <interface-symbol-id>` reverses this array: scan every
symbol, return those whose `implements` contains the requested id.
`--overrides <method-id>` is the same operation against a base class method.

TS gets parity once Phase A TS implements-edge extraction lands. Python
records will have `implements: []` until the semantic-engine swap (deferred).

---

## 5. Tests-bucket convention — already implicit, just formalize it

`code-index.yaml` node bindings already group files under purpose buckets
(`backend.domain`, `backend.application`, `backend.tests`, `frontend.feature`,
`frontend.pages`, `frontend.tests`). `kg_common.py:360-383` already records a
`bucket` field on every collected pattern, derived from the YAML key path:

```python
{"bucket": "backend.tests", "pattern": "engine/tests/.../CustomerTests.cs"}
```

**Decision: classify any file matched via a bucket whose last segment is
`tests` (case-insensitive) as a test file.** No `code-index.yaml` schema
change is required. The convention is already in the data — `symbols.py` just
needs to propagate it.

Mechanics:

1. `symbols.py` builds `file_to_node` today. Extend it to also build
   `file_to_buckets: dict[str, list[str]]` (a file can match multiple
   bindings).
2. A file is a test if **any** matched bucket ends with `.tests` or equals
   `tests` (case-insensitive). The ANY rule is deliberate: when a file
   participates in both a test bucket and a non-test bucket, treating it as
   a test errs on the safer side for `--check-untested` (a false-positive
   "this file is a test" merely excludes its symbols from
   needs-coverage reports; a false-negative would surface real test code
   as untested production code, which is noisy and wrong). Persist on
   `SymbolRecord` as `is_test: bool`.
3. `to_index_dict()` writes `is_test: true` only when true (keep the false
   case out of the on-disk file for size).

`--check-untested` (Phase D) and any future `untested` projection then have
an unambiguous classification without a new YAML field or a path-glob
heuristic in `symbols.py`.

Document this in `symbol-index-guide.md` under "How `code-index.yaml` and
`symbol-index.yaml` compose" — one paragraph naming the `.tests` suffix as
the classification rule.

---

## 6. New CLI surface — concrete shapes

### Extensions to `lookup.py`

The existing modes are mutually exclusive: positional `target`, `--file`,
`--symbol`. The new flags follow the same mutual-exclusion model — each
selects a distinct mode.

```
python3 scripts/kg/lookup.py --callers-only <symbol-id>
python3 scripts/kg/lookup.py --callees-only <symbol-id>
python3 scripts/kg/lookup.py --implementers <symbol-id>
python3 scripts/kg/lookup.py --overrides <symbol-id>
python3 scripts/kg/lookup.py --defines <name> [--node <node-id>]
```

All five accept the existing `--run-id`, `--telemetry-file`, and emit the
same JSON shape via `emit_lookup_telemetry`. Output payloads share the
existing `lookup.py --symbol` envelope (`{symbol, neighborhood, ...}`) but
populate only the requested slice. Example for `--callers-only`:

```json
{
  "query": {"kind": "callers-only", "symbol_id": "symbol:entity-customer:customer-service.cancel-async"},
  "callers": [
    "symbol:entity-customer:customer-endpoints.cancel",
    "symbol:entity-customer:customer-bulk-job.cancel-many"
  ],
  "telemetry": {"confidence_band": "high", "nodes_returned": 1, "symbols_returned": 2}
}
```

Empty results return `callers: []` with `confidence_band: "low"`. Unresolved
symbol ids exit non-zero with a clear stderr message — no silent empties.

### New CLI: `diff-impact.py`

```
python3 scripts/kg/diff-impact.py <git-range> [--depth N] [--format {json,yaml,text}]
```

- `<git-range>` is any string `git diff` accepts (`origin/main..HEAD`,
  `HEAD~5..HEAD`, a single commit sha).
- `--depth` defaults to 2 caller hops.
- Reads the diff via `git diff --name-only --find-renames` then per-file
  `git diff --unified=0` to extract changed line ranges.
- Maps changed ranges to symbols via the `line`/`end_line` rule from §2.
- Walks `callers` transitively up to `--depth`, collecting symbols and the
  canonical nodes they belong to.
- Output shape:

  ```json
  {
    "range": "origin/main..HEAD",
    "depth": 2,
    "changed_symbols": [{"id": "...", "node": "...", "rename": null}],
    "blast_symbols": [{"id": "...", "node": "...", "hops": 1}],
    "affected_nodes": ["entity:customer", "endpoint:cancel-customer"],
    "renames": [{"from_id": "...", "to_id": "...", "unresolved_pre_rename": false}],
    "telemetry": {"tokens_estimated": 1024, "confidence_band": "high"}
  }
  ```

- Emits one telemetry event per invocation via `kg_common.emit_telemetry`
  with `tool: "diff-impact"`.

### `coverage-gaps` (Phase B(c))

Thin projection over `unbound-but-referenced.yaml`. Two modes:

```
python3 scripts/kg/coverage-gaps.py            # default: by source file
python3 scripts/kg/coverage-gaps.py --by-target # group by bound symbol
```

Default exclusions baked in (test files where the test is the *source*
already, migration files, `scripts/`, `tools/`) so the first run doesn't
drown reviewers. Product-level exemptions live in the same per-product
ignore list `validate.py --check-coverage-gaps` reads (§Phase D).

---

## 7. Compilation-root defaults — product vs framework split

`--compilation-root` defaults live in **product** code, never in
`agents/**`. Concretely:

- C# extractor (`scripts/kg/csharp-symbols/Program.cs`): default
  `engine/src,engine/tests`. Matches `nebula-insurance-crm` layout but
  belongs to *that* product's pipeline.
- TS extractor (`scripts/kg/ts-symbols/extract.js`): default
  `experience/src,experience/tests`. Same scoping.
- Python extractor (inline in `symbols.py`): default **empty** (no
  compilation-root walk). Python is rarely a product's first-class language
  and the KG pipeline itself lives in `scripts/kg/` — walking it
  recursively from inside itself is awkward and adds noise. Products with
  first-class Python opt in by passing `--compilation-root`.

The new CLIs (`lookup.py` flag additions, `diff-impact.py`,
`coverage-gaps.py`) and the new validate.py flags MUST NOT bake the
product-specific path defaults. They read `compilation_roots` (if needed)
from `symbol-index.yaml.summary` — the index records what it was generated
from, and consumers read that.

`agents/architect/references/symbol-index-guide.md` will reference
`{NEBULA_PRODUCT_ROOT}/...` placeholders only. No `engine/` or `experience/` in
any framework-layer file.

---

## 8. Phase B(a) sub-ordering refinement

The prompt says Phase B(a) (lookup.py flag additions) ships before B(b)
(diff-impact.py) and B(c) (coverage-gaps). True, but B(a) itself has an
internal ordering:

| Flag | Gated on | Reason |
|---|---|---|
| `--callers-only`, `--callees-only` | Phase A C# (already passes) | Reads `callers`/`callees` which already exist in `symbol-index.yaml`. |
| `--defines` | Phase A C# | Reads `name` field across all symbols; existing data. |
| `--implementers`, `--overrides` | Phase A C# **and** Phase A TS implements-edge extraction | Reads the new `implements:` array. C#-only ships partial; full ships after TS. |

Ship the first three with Phase A(C#). Ship `--implementers` /
`--overrides` after Phase A(TS) so the answers aren't silently incomplete
on the experience tier.

---

## 9. Gate naming

The existing release-readiness gate is `kg_orphan_check`. The new gate
proposed in the prompt as `semantic_coverage_check` reads inconsistently
with the existing convention.

**Decision: name the new gate `kg_coverage_gap_check`.** Symmetric with
`kg_orphan_check`, parallels the underlying CLI flag
(`validate.py --check-coverage-gaps`), and groups visually with the other
`kg_*_check` gates that will follow as the symbol layer grows.

Apply the same convention to any future gate added through this initiative.

---

## 10. Refined rollout sequence

The prompt's deliverable order stands. The internal ordering inside each
phase, with the gaps above resolved:

1. **Memo (this file).** Reviewed and aligned before any code.
2. **Phase A — compilation/emission split.**
   - A1. C# extractor: `--compilation-root` flag, emission filter, sidecar,
     `end_line` field. Smallest delta; validates the contract.
   - A2. TS extractor: single multi-file `Project` (drop
     `skipFileDependencyResolution`), `getSymbol()`-based call resolution,
     `implements`/`extends` edges, sidecar, `end_line`.
   - A3. Python: plumbing-only (compilation-root walk, bound-file filter,
     sidecar, `end_line` via `ast.AST.end_lineno`). No semantic upgrade.
   - A4. `symbols.py` orchestrator: sidecar aggregation,
     `unbound-but-referenced.yaml` write, `is_test` propagation from buckets,
     stop stripping `implements`, persist `end_line`.
   - Validate by regenerating `symbol-index.yaml` and re-running
     `dead-code.py --safe-only`. Candidate list should stay at zero. The
     sidecar should contain at least one entry per binding that declares a
     `*.tests` bucket targeting a public method in that binding's
     non-test buckets — i.e. for any binding with both a service class
     and integration tests for it, the integration test → service call
     should appear in `unbound-but-referenced.yaml`. If no such entries
     appear, the compilation-root walk is broken.
3. **Phase B — query surface.**
   - B(a-i). `lookup.py --callers-only`, `--callees-only`, `--defines` —
     ship together; reuse existing pipeline.
   - B(a-ii). `lookup.py --implementers`, `--overrides` — ship after A2
     so TS results are complete.
   - B(b). `diff-impact.py`.
   - B(c). `coverage-gaps.py`.
4. **Phase C — agent SKILL wiring.** Surgical edits per SKILL; run
   `agents/scripts/run-skill-regression.py` between batches.
5. **Phase D — `validate.py --check-coverage-gaps`,
   `validate.py --check-untested`, `kg_coverage_gap_check` gate in
   `lifecycle-stage-template.yaml`. `--check-untested` is unblocked by the
   tests-bucket convention in §5 and can ship in the same wave.

---

## 11. Deferred — measurement triggers unchanged from prompt

The following remain deferred. Triggers below are what would surface them
back into scope; do not pre-decide.

- **`references` edge kind** (type-refs, attribute-access, instantiation).
  Trigger: a recurring agent need where caller/callee misses the connection
  (e.g. a refactor that breaks consumers via a constructor call). Measure
  edge-count delta on real `symbol-index.yaml` volume before committing.
- **`signature-search`**. Trigger: Phase C wiring surfaces evidence that
  duplicate-surface discovery is a recurring pain that `--defines` doesn't
  cover.
- **Python semantic-engine swap (Jedi or Pyright).** Trigger: a product
  acquires enough Python surface to measure resolution accuracy
  meaningfully. The swap is local to `PythonAstExtractor.extract()` — the
  sidecar contract and orchestrator interface from §1 are stable across
  the swap.

---

## 12. Constraints honored

- `solution-ontology.yaml.authority.precedence` — every new output is a
  routing aid; raw source remains authoritative.
- `BOUNDARY-POLICY.md` — examples in this memo use customer/order only.
- `CONSUMER-CONTRACT.md` — all new flags and CLIs degrade gracefully when
  upstream artifacts are absent.
- Backward compatibility — additive changes only: new flags on `lookup.py`,
  two new CLIs (`diff-impact.py`, `coverage-gaps.py`), two new fields on
  `symbol-index.yaml` (`end_line`, `implements`), one optional field
  (`is_test`). No existing flag, CLI, schema field, or exit code changes
  meaning.
- Cache correctness across compilation scope — `FileCacheEntry`
  (`symbols.py:384`) is keyed only on per-file sha256, but Roslyn's
  resolution of an invocation depends on *which other files are in the
  compilation*. A file added to or removed from the compilation root
  changes what `{container}` a bound file's `raw_calls` see, even though
  the bound file's hash is unchanged. The cache header gains a
  `compilation_roots_hash` (sorted, normalized root paths, sha256); on
  mismatch the orchestrator force-invalidates and full-re-parses. Cheap
  in steady state, correct on root changes.
- Telemetry — every new CLI invocation emits one JSONL event via
  `kg_common.emit_telemetry` with `tool`, `nodes_returned`,
  `symbols_returned`, `confidence_band`, `tokens_estimated`, and the
  `NEBULA_ACTION` correlation context.
- Tool-agnostic — nothing in `agents/**` names Claude Code, Cursor, or any
  orchestrator. New CLIs are plain Python invocations the same as
  `lookup.py`.

---

## 13. Rollout state (2026-05-18)

The rollout in §10 is complete. Commits below are on
`feat/knowledge-graph-optimization` in each repo.

| Phase | Deliverable | Status | Commits |
|---|---|---|---|
| A1+A2 | C# + TS compilation-root, sidecar, `end_line` | Shipped | `e8f3493` (nebula-insurance-crm) |
| A3 | Python plumbing, `is_test` propagation, orchestrator persist of `implements` | Shipped | `39f0f21` (nebula-insurance-crm) |
| B(a-i) | `lookup.py --callers-only`, `--callees-only`, `--defines` | Shipped | `8214b06` (nebula-insurance-crm) |
| B(b) | `diff-impact.py` | Shipped | `3393410` (nebula-insurance-crm) |
| B(c) | `coverage-gaps.py` | Shipped | `36f414f` (nebula-insurance-crm) |
| B(a-ii) | `lookup.py --implementers`, `--overrides` | Shipped | `9c03c96` (nebula-insurance-crm) |
| C | Architect / backend / frontend / ai-engineer / code-reviewer + `actions/review.md` / security / devops / product-manager / technical-writer SKILL wirings | Shipped | `ce51538` (nebula-agents) |
| C tag-on | `--implementers` / `--overrides` references in architect, backend, frontend, code-reviewer | Shipped | `980de52` (nebula-agents) |
| D (validator) | `validate.py --check-coverage-gaps` + `--check-untested` (with `*-as-errors` and exemption flags) | Shipped | `e74aef2` (nebula-insurance-crm) |
| D (gate + wiring + guide) | `kg_coverage_gap_check` gate in `lifecycle-stage-template.yaml`, quality-engineer SKILL §4 + `actions/test.md` Step 1, full refresh of `symbol-index-guide.md` | Shipped | `e8997a0` (nebula-agents) |
| D (guide refresh) | `dead-code-review-guide.md` extended to weave the sidecar / coverage-gaps as the automated form of the grep step; grep retained as fallback per §Phase D caution | Shipped | `89f0f64` (nebula-agents) |
| Deferred (item 1, partial) | `instantiates` + `type_refs` edges added to C# and TS extractors; orchestrator gains cross-node `by_top_level_type_name` index; attribute-access deferred on measurement | Shipped | this commit (both repos) |
| Deferred (item 2) | `signature-search` not implemented; measurement plan documented for `--defines` empty-rate signal over one feature cycle | Documented only | this commit |

Smoke-test reality on the product baseline at the time of shipping:

- Phase A regeneration produced 2332 symbols (2074 C#, 258 TS), 245 with
  populated `implements:`, and 7 entries in
  `unbound-but-referenced.yaml`.
- `validate.py --check-coverage-gaps` warns on 2 real findings after the
  baked-in test/migration/scripts/tools exclusions strip the 5
  test-as-source entries.
- `validate.py --check-untested` warns on 447 findings — the current
  test-coverage baseline. Gate is warn-only so this surfaces the gap
  without blocking release-readiness.
- `diff-impact.py` against a recent F0020 commit returned 348 changed
  symbols, 35 hop-1/2 callers, and 10 canonical nodes affected.

### Deferred — measurement triggers (updated 2026-05-19)

The following remain deferred. Triggers below are what would surface them
back into scope. Do not pre-decide; the work below is gated on signal,
not on a deadline.

- **`references` edge kind — attribute-access subset.** The instantiation
  and type-ref subsets shipped (commit on this branch; +2,118 edges, 0.5x
  the existing baseline, cross-node visible). Attribute-access was
  measured at ~25k edges on the same product (~5.7x baseline) and
  deferred. Trigger to revisit: agent demand for "which fields/properties
  reference this entity" that `lookup.py --symbol`, `--implementers`, and
  the new `instantiates` / `type_refs` arrays can't already satisfy.
- **`signature-search`.** Trigger: telemetry from `lookup.py` shows
  `query_kind="defines"` events with `empty_scope=true` accumulating
  over a feature cycle while agents proceed to find the symbol by other
  means. Operational measurement plan:

  | Metric | How to read | Action threshold |
  |---|---|---|
  | `--defines` empty-result rate | Filter `.kg-state/telemetry.jsonl` by `tool=lookup`, `payload.query_kind=defines`, `payload.empty_scope=true` over one full feature cycle | >30% empty rate → prototype the `name+arity` index variant as a flag on lookup.py |
  | Recovery path | When `--defines` returns empty, observe what the agent invoked next (typically `grep`, `Read`, or `hint.py --symbol`) | If `grep`/`Read` dominates the recovery path, signature-search is the real gap; if `hint.py` recovers, the issue is naming not signature |
  | Cost ceiling | Whichever variant we pick, the added telemetry event budget per query stays within the existing `tokens_estimated` envelope | Reject any variant that doubles per-query token cost |

  No design decision pre-committed. The three options remain on the
  table: regex over `signature` strings, a `name+container+arity`
  in-memory index, or LLM-aided semantic search. The cheapest variant
  (name+arity) is likely the first prototype if and when the threshold
  fires.
- **Python semantic-engine swap (Jedi or Pyright).** Trigger: a product
  acquires enough Python surface to measure resolution accuracy
  meaningfully. The swap is local to `PythonAstExtractor.extract()` —
  the sidecar contract and orchestrator interface from §1 stay stable
  across the swap, so this is purely a quality-of-edges upgrade.
- **`dead-code-review-guide.md` grep-step removal.** Trigger: the
  sidecar produces stable findings across several regenerations on the
  product and is shown to subsume the grep step. Measurement window is
  open — the current refresh weaves the sidecar in as an automated
  pre-step but does not remove grep, per the memo's caution about
  stripping a working fallback before its replacement is proven.

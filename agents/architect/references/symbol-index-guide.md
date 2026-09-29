# Symbol-Index Guide

`{NEBULA_PRODUCT_ROOT}/planning-mds/knowledge-graph/symbol-index.yaml` is the
symbol-level layer of the knowledge graph. It binds individual methods,
classes, functions, and properties to the canonical nodes already declared in
`code-index.yaml`, so retrieval can jump straight to a definition instead of
loading a whole file.

Symbol-index is **not** authoritative. Raw source files remain the source of
truth (per `solution-ontology.yaml.authority.precedence`). The symbol layer is
a retrieval aid that turns "open the file and read everything" into "look up
the symbol, get its callers/callees, edit narrowly."

---

## When to use it

- Before editing a bound method body — call
  `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/lookup.py --symbol <name>` to get the
  symbol record plus its caller/callee neighbourhood.
- When only one slice of that neighbourhood is needed, the narrow
  projections are cheaper than `--symbol`:
  - `lookup.py --callers-only <symbol-id>` — caller ids only, no siblings.
  - `lookup.py --callees-only <symbol-id>` — callee ids only.
  - `lookup.py --defines <name>` — every definition matching a bare name
    across the whole index (use during design before introducing a new
    surface; scope further with `--node <node-id>`).
  - `lookup.py --implementers <interface-symbol-id>` — every concrete
    type satisfying an interface member.
  - `lookup.py --overrides <method-id>` — every override of a base-class
    method (same scan as `--implementers`; different intent).
  - `lookup.py --untested <node-id>` — public/internal methods and
    functions on one canonical node with no caller in a classified tests
    bucket. Use for feature-close triage; use `validate.py --check-untested`
    for whole-repo gates.
- When triaging a regression — `blast.py --symbol <name>` or
  `blast.py symbol:<id>` walks one hop of call edges and reports the
  canonical nodes and files reached.
- When assessing the impact of a feature branch — `diff-impact.py
  <git-range> [--depth N]` maps the diff to symbols and walks callers
  transitively to enumerate the canonical nodes affected.
- When reviewing a diff that adds, renames, or removes a class, function,
  method, or property in a bound file — re-run `validate.py
  --regenerate-symbols --check-symbols` so the layer stays in sync.

### Narrow projection vs. full neighbourhood

`lookup.py --symbol` returns the symbol record plus full call neighbourhood,
sibling symbols on the same canonical node, and decisions touching the
symbol. Use it when the question is "what is around this symbol?". The
narrow projections (`--callers-only`, `--callees-only`, `--defines`,
`--implementers`, `--overrides`) skip the neighbourhood/sibling work and
return only the requested slice — cheaper context for agents that already
know what they're looking for.

---

## Schema

```yaml
version: 0
generated_at: '2026-05-10T00:00:00+00:00'
summary:
  total_symbols: 1234
  by_language:
    csharp: { files: 100, parsed: 100, cached: 0 }
    typescript: { files: 40, parsed: 40, cached: 0 }
    python: { files: 0, parsed: 0, cached: 0 }
  disambiguated_ids: 4
  compilation_roots_by_language:
    csharp: [backend/src, backend/tests]
    typescript: [frontend/src, frontend/tests]
    python: []
  compilation_roots_hash_by_language:
    csharp: <sha256>
    typescript: <sha256>
    python: <sha256>
  sidecar_authoritative_languages: [csharp, typescript]
symbols:
  - id: symbol:entity-customer:customer-service.cancel-async
    node: entity:customer
    kind: method
    name: CancelAsync
    file: backend/src/Customers/Services/CustomerService.cs
    line: 142
    signature: 'public async Task<Result> CancelAsync(Guid id, CancellationToken ct)'
    visibility: public
    language: csharp
    container: CustomerService
    callers:
      - symbol:entity-customer:customer-endpoints.cancel
    callees:
      - symbol:entity-customer:customer-repository.update-async
      - symbol:entity-customer:i-customer-repository.update-async

  - id: symbol:entity-order:order-form.submit
    node: entity:order
    kind: function
    name: submit
    file: frontend/src/features/orders/OrderForm.tsx
    line: 84
    signature: 'function submit(values: OrderValues): Promise<void>'
    visibility: local
    language: typescript
    container: null
    callers: []
    callees:
      - symbol:entity-order:order-form.validate
```

### Field reference

| Field | Type | Description |
|---|---|---|
| `id` | string | Stable symbol id: `symbol:<node-slug>:<container-or-file-stem-slug>.<name-slug>`. Collisions are disambiguated with `-2`, `-3`, … suffixes. |
| `node` | string | Canonical node id from `canonical-nodes.yaml` or `mapping_nodes`. |
| `kind` | enum | `class \| record \| struct \| interface \| enum \| delegate \| method \| function \| property \| constructor \| type` |
| `name` | string | Source-level identifier (e.g. `CancelAsync`, `submit`). |
| `container` | string \| null | Owning type for members (e.g. `CustomerService`); `null` for top-level declarations. |
| `file` | string | Repo-relative file path. |
| `line` | integer | 1-based line number of the declaration. |
| `signature` | string | First line of the declaration, attributes stripped. |
| `visibility` | enum | `public \| internal \| protected \| private` (C#); `export \| local \| public` (TS); `public \| private` (Python). |
| `language` | enum | `csharp \| typescript \| python` |
| `callers` | string[] | Symbol ids that invoke this symbol. Resolved semantically for C# and TypeScript (cross-node visible); name-matched within the same canonical node for Python. |
| `callees` | string[] | Symbol ids this symbol invokes. Same resolution model as `callers`. |
| `end_line` | integer | 1-based line number of the declaration's closing brace (or last AST node). Used by `diff-impact.py` to map changed line ranges to symbols. |
| `is_test` | bool | `true` when the symbol's file matches a `code-index.yaml` binding bucket ending in `.tests` (case-insensitive). Drives `validate.py --check-untested` and the `coverage-gaps` test-source exclusion. |
| `implements` | string[] | Symbol ids of interface members or base-class methods this symbol satisfies. Empty array stripped from on-disk form. C# and TS emit; Python is `[]` until the semantic-engine swap. |
| `instantiates` | string[] | Symbol ids of types this symbol constructs (`new T(...)` in C#/TS). Resolved cross-node when the target is a top-level type. Empty array stripped from on-disk form. C# and TS emit; Python is `[]`. |
| `type_refs` | string[] | Symbol ids of types referenced in the declaration's signature (parameters, return type, property type, generic arguments, type constraints). Built-in / `System.*` / library types skipped to keep the array focused on bound surface. Empty array stripped from on-disk form. C# and TS emit; Python is `[]`. |

Call-edge resolution is per-language:

- **C#** — the Roslyn extractor builds a single `Compilation` across every
  bound file, then resolves each `InvocationExpressionSyntax` via
  `SemanticModel.GetSymbolInfo`. Each call is emitted as `{name, container}`
  where `container` is the resolved declaring type. The orchestrator looks
  up the callee globally on `(container, name)`, so cross-node calls
  (endpoint → service, service → repository, controller → handler) resolve
  correctly. For every method that satisfies an interface member or
  overrides a base method, a synthetic edge is added from the interface
  member to the impl so reaching `IFoo.Bar` walks into every `Foo.Bar`,
  and the impl persists the interface-member id on its `implements:` array.
- **TypeScript** — the ts-morph extractor builds a single Project across
  every bound file, resolves each `CallExpression` via
  `getExpression().getSymbol()` to its declaring class/module, and emits
  call edges as `{name, container}` parallel to C#. Class declarations
  also emit `implements` and `extends` heritage so `--implementers` and
  `--overrides` queries are cross-node visible on the experience tier.
- **Python** — the stdlib-ast extractor emits bare invocation names. The
  orchestrator matches names against other symbols on the **same canonical
  node** as the caller. Cross-node calls are invisible to the walk;
  over-linking within a node is acceptable. The semantic-engine swap
  (Jedi or Pyright) is deferred until a product acquires enough Python
  surface to measure resolution accuracy meaningfully.

Over-linking and missed cross-node edges in Python (and any leftover gaps
in TS) are both acceptable — the layer is a routing aid, not a
static-analysis report. Raw source files remain authoritative per
`solution-ontology.yaml.authority.precedence`.

### Compilation scope vs. emission scope

Each extractor takes a `--compilation-root` flag (one or more directory
roots). The extractor walks each root for source files of the relevant
language, builds a single semantic compilation across all of them, and
emits `SymbolRecord` entries only for files in the bound-files list
derived from `code-index.yaml`. Calls from compilation-root files that
are *not* bound (tests outside their owning binding, helpers under
`scripts/`, etc.) still influence semantic resolution but do not
themselves produce symbols.

Invocations originating in unbound compilation-root files that target a
bound symbol are written to a side report:
`planning-mds/knowledge-graph/unbound-but-referenced.yaml`. This is the
substrate for `validate.py --check-coverage-gaps` and the
`coverage-gaps.py` projection — it surfaces real coverage gaps without
re-running grep.

### `implements:` and the satisfies/overrides queries

The on-disk record gains one field `implements: [<symbol-id>, ...]`
listing the interface members (and base-class virtuals) the symbol
satisfies. Querying:

- `lookup.py --implementers <interface-symbol-id>` reverses the array:
  scan every symbol, return those whose `implements` contains the
  requested id.
- `lookup.py --overrides <method-id>` runs the same scan against a
  base-class method id.

C# emits `implements` for both interface dispatch and base-class
override edges. TS emits via heritage clauses (`implements`, `extends`).
Python records carry `implements: []` until the semantic-engine swap
lands.

### `instantiates:` and `type_refs:`

Two additional edge arrays sit alongside `callers` / `callees` /
`implements` to answer questions that semantic call-resolution alone
cannot:

- `instantiates: [<type-symbol-id>, ...]` — types this symbol constructs
  via `new T(...)`. Reverse-scan to answer "who instantiates this class?"
  — the canonical refactor-impact question when a constructor signature
  changes.
- `type_refs: [<type-symbol-id>, ...]` — types named in this symbol's
  declared surface (parameters, return type, property type, generic
  arguments, type constraints). Reverse-scan to answer "which surfaces
  reference this type?" — useful for type rename or split refactors.

Edges resolve cross-node when the target is a top-level type (class,
record, struct, interface, enum, delegate, type alias). Built-in
primitives, framework anchors (C# `System.*`, TS lib.d.ts, node_modules
types), and self-edges are dropped. C# and TS emit; Python is `[]`
until the semantic-engine swap. Both arrays are stripped from on-disk
form when empty.

The measured edge-count delta on the product baseline was ~0.5x the
existing total (621 instantiates + 1,497 type_refs vs ~4,400 callers
+ callees + implements). Attribute-access edges were also measured
(~25k, 5x baseline by themselves) and explicitly deferred until an
agent need is shown — the cost dominates the marginal value.

There are no dedicated lookup.py reverse-scan flags yet
(`--instantiated-by`, `--type-referenced-by`). Forward direction is
already exposed via `lookup.py --symbol` (the record carries both
arrays). Reverse-scan flags will ship if telemetry shows agents asking
for them; until then, raw projection over `symbol-index.yaml` is the
escape hatch.

---

## Regeneration

```bash
# Full regeneration (uses .kg-state/symbols-cache.json for incremental parsing)
python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/symbols.py

# Force a full re-parse (ignore cache)
python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/symbols.py --force

# Restrict to a single canonical node
python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/symbols.py --node entity:customer

# Restrict to a single language
python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/symbols.py --language typescript

# Regenerate as part of validation (delegates to symbols.py)
python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/validate.py --regenerate-symbols --check-symbols
```

### Cadence

- After any design session that adds aggregate methods, service operations,
  endpoints, or React components on a bound canonical node.
- As part of the build action closeout (Step 6 KG validation).
- Before opening a code review on a feature branch.

---

## Supported languages

| Extension | Extractor | Where |
|---|---|---|
| `.py` | Python stdlib `ast` | inline in `scripts/kg/symbols.py` |
| `.ts`, `.tsx` | ts-morph (TypeScript compiler API) | `scripts/kg/ts-symbols/` (Node subprocess) |
| `.cs` | Roslyn (`Microsoft.CodeAnalysis.CSharp`) | `scripts/kg/csharp-symbols/` (.NET subprocess) |

The Node and .NET extractors must be installed before they will produce
symbols:

```bash
# Once per checkout (or after dependency changes)
(cd {NEBULA_PRODUCT_ROOT}/scripts/kg/ts-symbols && npm install)
(cd {NEBULA_PRODUCT_ROOT}/scripts/kg/csharp-symbols && dotnet build --configuration Release)
```

`symbols.py` detects missing extractors and skips those languages with a
warning to stderr — the rest of the pipeline still works.

Adding a new language is a matter of writing a new `BaseExtractor` subclass
in `symbols.py` (or a parallel subprocess tool) and mapping its file
extensions in `LANGUAGE_BY_EXT`.

---

## How `code-index.yaml` and `symbol-index.yaml` compose

| Layer | Granularity | Generated by | Authoritative? |
|---|---|---|---|
| `canonical-nodes.yaml` | Domain concept (entity, workflow, endpoint…) | hand-curated | No (raw docs win) |
| `code-index.yaml` | File / glob | hand-curated | No (raw source wins) |
| `symbol-index.yaml` | Method / class / function / property | `symbols.py` from `code-index.yaml` | No (raw source wins) |

`symbol-index.yaml` walks **only** files declared in `code-index.yaml`. The
product owns curation of `code-index.yaml`; the framework cannot inject new
file paths. To bring a new directory under symbol-layer coverage, add a
binding (or extend an existing one) in `code-index.yaml`, then regenerate.

---

## Telemetry

`symbols.py` and `lookup.py --symbol` emit JSONL telemetry events with the
same shape as the other KG tools (see `eval.py`). Key fields:

- `tool` — `symbols`, `lookup`, `hint`, or `blast`
- `nodes_returned` / `nodes_count` — canonical nodes touched
- `symbols_returned` / `symbols_count` — symbol ids in the response
- `confidence_band` — `high` (clean match) / `low` (empty) / `ambiguous`
  (collisions / disambiguated ids)
- `tokens_estimated` — best-effort estimate so cost is comparable across
  tools.

Use `eval.py` to score retrieval quality against scenario fixtures.

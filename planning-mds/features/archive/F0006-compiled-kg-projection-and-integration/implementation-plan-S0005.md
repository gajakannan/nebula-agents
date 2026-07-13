# F0006-S0005 — Implementation Plan (Deterministic KG Compiler with Logical Doc Refs)

> **Living tracker for the B2 build.** Companion to
> [`F0006-S0005-deterministic-kg-compiler.md`](./F0006-S0005-deterministic-kg-compiler.md).
> Builds on S0004 ([`implementation-plan-S0004.md`](./implementation-plan-S0004.md), done).
> Update §10 as work lands.

| Field | Value |
|-------|-------|
| Story | F0006-S0005 (PRD row **B2**) |
| Phase | B — Compiled projection |
| Status | **Done — signed off 2026-07-09** (Architect + Code Reviewer + QE PASS; 24 compile tests + 3 story-block cases green) |
| Created | 2026-07-09 |
| Branch (both repos) | `feat/F0006-phase-B-compiled-projection` |
| Signoff required | Architect + Code Reviewer + **Quality Engineer** (determinism/round-trip) |
| Touches `main` | **No** — feature branch only |
| Almost all work lands in | product repo `nebula-insurance-crm` (`scripts/kg/`) |

---

## 0. Scope — what S0005 delivers (and defers)

**Delivers:** `scripts/kg/compile.py` — a deterministic compiler that builds the **projection trio**
(`canonical-nodes.yaml`, `feature-mappings.yaml`, `code-index.yaml`) from `kg-source/` shards through
the S0001 canonical serializer, resolving logical `F####/…` doc refs; drives the existing downstream
generators; runs compile-time analysis (duplicate IDs, name-similarity, glob overlap); `--check` and
`--strict` modes; all-or-nothing writes.

**Defers:** populating real shards / the migration (S0006 — S0005 is proven on **fixture shard trees**
+ golden files, since the real `kg-source/` is empty until S0006); tracker-table rendering (S0007);
CI wiring (S0008); any change to `symbols.py`/`decisions.py` **internals** (explicitly out of scope —
see decision **D1**).

---

## 1. Reuse surface (most of the engine already exists)

| Need | Reuse (already in repo) |
|------|-------------------------|
| Canonical serialization | `kg_common.canonical_dump()` — the S0001 serializer (`_CanonicalDumper`, `sort_keys=False`, width 100), deterministic/cross-machine |
| Canonical ordering | `kg_common.canonicalize_document()` (priority-then-alpha keys, record lists sorted by `id`, scalar lists deduped/sorted except `ORDERED_LIST_FIELDS`) |
| Reproducibility diff | `kg_common.canonical_equal()` |
| Duplicate-ID detection | `merge3.check_input_duplicates()` |
| **Name/alias similarity** | `merge3.graph_checks()` already fingerprints `label/name/title` via `"".join(casefold isalnum)` and emits `SemanticDuplicateWarning` when >1 id shares a normalized name — **answers the S0005 open question by reuse** (see D2) |
| Shard load + validate | S0004 `shard_validate.validate_paths()` / `classify_directory()` / `KIND_ID_RE` |
| Section↔kind inverse | `kg_common.SECTION_TYPES` (shard dir → canonical-nodes section) |
| Trio basenames | `merge3.CURATED_BASENAMES = (canonical-nodes, feature-mappings, code-index)` |

New code is mostly the **shard→projection assembly** + the **logical-ref resolver** + the driver/CLI.

---

## 2. Compiler pipeline (`compile.py`)

1. **Load + validate shards** — read `kg-source/**`; run S0004 `shard_validate` first (fail fast, no writes).
2. **Resolve logical doc refs** — build `feature_id → path` from feature shards; rewrite every
   `F####/rel` `source_docs` entry to `<feature.path>/rel`, assert the file exists; stable-root refs
   pass through; unresolvable ref → loud error (shard, ref, resolution attempt).
3. **Assemble projections**
   - `nodes/<section>/*` + `policies/*` → `canonical-nodes.yaml` sections (via `SECTION_TYPES` inverse)
   - `bindings/*` → `code-index.yaml` `node_bindings`
   - `features/*` (technical subset: `status/path/affects/governed_by/uses_*/depends_on/supersedes`) → `feature-mappings.yaml` `features`; `exclusions/*` → `excluded_features`; **`stories` → see D3**
   - preserve the file-level scalars (`version`, `status`, `coverage_note`) — content, not timestamps
4. **Compile-time analysis** — duplicate IDs (hard error); name-similarity + binding-glob overlap
   (advisory on branches, blocking under `--strict`); suppressible only via the ledger (D-ledger).
5. **Emit** via `canonical_dump` — **all-or-nothing** (temp write + atomic rename, the merge3 pattern):
   nothing is written unless the whole build succeeds.
6. **Drive downstream generators** — `decisions.py`, `symbols.py`, `validate.py --write-coverage-report`,
   story-index (**D5**), and — after S0007 — tracker tables. Timestamp handling per **D1**.
7. **`--check`** — compile to a temp tree, diff against committed (byte-identity for the trio; **D1**
   governs the timestamped derived files). This is the primitive S0008's CI wraps.

---

## 3. Logical-ref resolver (absorbs F0005)

`resolve_doc_ref` does **not** exist yet (`kg_common` has `resolve_node`/`resolve_refs` for node IDs
only). New in this story, in `kg_common.py` (so `validate.py`/`lookup.py`/`eval.py` can share it):

- `F####/rel-path` → `<feature-shard path>/rel-path`, existence-checked.
- Stable-root (`architecture/`, `api/`, `schemas/`, `security/`, `engine/`, `experience/`) → passthrough, validated as-is.
- Malformed (`F####/` empty remainder, unknown feature, missing file) → loud error.
- **Acceptance:** flipping a feature shard's `path:` between live and archive changes **no** shard content and keeps compile green (the F0005 payoff).

---

## 4. Determinism approach

- Trio emitted only through `canonical_dump` → stable ordering, cross-machine byte-identical.
- No timestamps in the **trio** (verified: committed `canonical-nodes.yaml`/`code-index.yaml`/
  `feature-mappings.yaml` carry none).
- Double-compile byte-identity test + a cross-machine check (fixture tree).
- Emitted comments limited to generated-section banners; versions/counts derived from content only.

---

## 5. Decisions (resolved 2026-07-09)

> **Confirmed:** **D1** = driver-strips `generated_at`; **D2** = reuse merge3 normalized-name
> fingerprint (fuzzy deferred); **D3** = embed a `stories:` block in the feature shard (a minor S0004
> schema amendment done during this build). **D4/D5/D-ledger** = recommended defaults. Details below.

- **D1 — timestamps in driven generators (the crux).** `decisions.py` and `symbols.py` write
  `generated_at: <now>` and those files **are committed** (`decisions-index.yaml` currently
  `2026-07-06T04:57:16+00:00`; `symbol-index.yaml` likewise). The story requires "no committed
  timestamps / byte-identical derived outputs," but S0005 Out-of-Scope forbids changing those
  generators' internals. **Recommendation:** compile.py, as the *driver*, post-processes each driven
  output to drop/stabilize the top-level `generated_at` key (a driver-level normalization — the
  generator internals are untouched, staying in scope). Alternative: scope byte-identity to the trio +
  story-index and let S0008 check the timestamped files semantically (modulo `generated_at`). *I favor
  the driver-strip; confirm.*
- **D2 — alias/name similarity (the story's open question).** **Recommendation:** reuse
  `merge3.graph_checks`' deterministic normalized-name fingerprint (exact match on casefold-alphanumeric
  across `label/name/title`) as the advisory/strict signal now; defer fuzzy near-duplicate detection
  (e.g. the `document-generation` vs `outbound-document-generation` class) to a later opt-in, because a
  fuzzy threshold is a tuning/false-positive risk the story flagged as unresolved. Confirm, or ask for
  `difflib`-ratio fuzzy at a conservative threshold (e.g. 0.92).
- **D3 — where do `feature-mappings.stories` come from? (potential S0004 gap).** `feature-mappings.yaml`
  has a hand-authored `stories` list (164 entries, each with `affects`/`uses_*`). S0004 sharded
  *features* but deferred *stories* to "projected from story files." The compiler must still emit
  `feature-mappings.stories` byte-identically, and there is **no shard source for it today**. Options:
  (a) feature shards embed a `stories:` block (small S0004 schema addition); (b) per-story shards under
  `features/`; (c) derive from structured story-file frontmatter (story `.md` files don't carry it
  today). **Recommendation:** (a) — add a `stories:` list to the feature-shard schema and fold it in as
  a minor S0004 amendment. This is the one decision that may touch the S0004 contract, so I want your
  call before building. *(Could alternatively be pushed to S0006 as a migration concern — say which.)*
- **D4 — `solution-ontology.yaml` home during Phase B.** It's curated source, rehoming to
  `kg-source/ontology/`, but existing tools read `knowledge-graph/solution-ontology.yaml`.
  **Recommendation:** compile.py copies `kg-source/ontology/solution-ontology.yaml` →
  `knowledge-graph/solution-ontology.yaml` verbatim (a generated mirror) so tools keep working until the
  S0009 repoint. Confirm.
- **D5 — story-index generator is cross-repo.** `generate-story-index.py` lives in `nebula-agents`
  (run with `--product-root`), not in the product repo. **Recommendation:** compile.py drives it only
  when a framework path is supplied (env/flag); otherwise it's a no-op and story-index stays the
  framework's separate step. The trio + resolver remain the hard S0005 deliverable regardless.
- **D-ledger — suppression ledger home.** Alias/glob suppressions with rationale live in a source file.
  **Recommendation:** `kg-source/exclusions/suppressions.yaml` (PM+architect co-sign, already that dir's
  owners), validated by a small S0004-style rule. Confirm.

---

## 6. File inventory

**Product repo `nebula-insurance-crm`:**
- `scripts/kg/compile.py` — the compiler + generator driver + `--check`/`--strict` CLI
- `scripts/kg/kg_common.py` — **edit**: add `resolve_doc_ref` (+ shared helpers)
- `scripts/kg/tests/test_compile.py` — determinism, resolver matrix, analysis, `--check`, all-or-nothing
- `scripts/kg/tests/fixtures/kg-source/**` — extend S0004 fixtures into a compile-complete tree + golden projections
- `scripts/kg/README.md` — **edit**: document the compile flow (story DoD)
- possibly `kg-source/exclusions/suppressions.yaml` schema (D-ledger)

**Framework repo `nebula-agents`:** none required for S0005 (the `validate-feature-evidence.py`
matcher learning `compile.py` and doc reconciliation are **S0009**). STATUS/plan tracking only.

---

## 7. Test plan (QE-signed)

Double-compile byte-identical; cross-machine check; resolver matrix (live / archived / unmapped /
missing / malformed / stable-root passthrough); duplicate-ID hard error; name-similarity + glob-overlap
advisory→blocking under `--strict`; ledger suppression; `--check` detects a hand-edit; all-or-nothing
(inject a failure mid-build → nothing written); golden-file trio compare.

---

## 8. Risks

- **Determinism vs. driven generators** — the D1 timestamp issue is the main correctness risk; the
  driver-strip keeps it in scope.
- **Downstream generator determinism** — story assumes `decisions.py`/`symbols.py`/coverage are
  deterministic given identical inputs; verify (spot-checked for symbols in PR #47; confirm decisions +
  coverage during build; coverage-report.yaml timestamp status TBD).
- **D3 story-mapping gap** could widen scope if it forces an S0004 schema amendment.

---

## 9. Sequencing note

S0005 lands the compiler against **fixtures**; it does not migrate the real graph (that's S0006). The
real `kg-source/` is still empty, so `compile.py` on the real tree is a no-op until S0006 populates it —
which is why determinism/resolution are proven on fixtures + golden files here.

---

## 10. Progress checklist (maps to story DoD)

- [x] Decisions D1–D5 + D-ledger resolved with maintainer (2026-07-09)
- [x] S0004 amendment: add `stories:` block to feature-shard schema + validator + README (D3)
- [x] `resolve_doc_ref` in `kg_common.py` + resolver test matrix green
- [x] `compile.py` assembles the trio via `canonical_dump`; all-or-nothing
- [x] Compile-time analysis (duplicate/ name-similarity/ glob-overlap) + suppression ledger, strict/advisory modes
- [x] `--check` mode diffs committed projections correctly
- [x] Downstream generators driven; timestamp handling per D1
- [x] Determinism proven (double-compile + cross-machine) on the fixture tree + golden files
- [x] Unit + golden-file tests (`test_compile.py`)
- [x] `scripts/kg/README.md` compile-flow section
- [x] Story index updated (S0005 → Done); STATUS provenance (Architect + Code Reviewer + QE)

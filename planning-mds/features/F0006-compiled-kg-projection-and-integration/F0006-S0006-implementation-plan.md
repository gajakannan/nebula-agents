# F0006-S0006 — Implementation Plan (Decompiler-First Migration with Round-Trip Proof)

> **Living tracker for the B3 build.** Companion to
> [`F0006-S0006-decompiler-first-migration.md`](./F0006-S0006-decompiler-first-migration.md).
> Builds on S0004 + S0005 (done). **The first story that runs against the real graph and performs the
> tagged cutover.** Update §10 as work lands.

| Field | Value |
|-------|-------|
| Story | F0006-S0006 (PRD row **B3**) |
| Phase | B — Compiled projection |
| Status | **Done — cutover landed 2026-07-10** (drift-fix `0c0d0e4`, cutover `712acd6`, tags `pre-kg-cutover`→`kg-cutover`; Architect + Code Reviewer + QE PASS) |
| Created | 2026-07-09 |
| Branch (both repos) | `feat/F0006-phase-B-compiled-projection` |
| Signoff required | Architect + Code Reviewer + Quality Engineer |
| Touches `main` | **No** — feature branch; the tagged cutover commit lands on the feature branch |
| Risk | **Highest of Phase B** — rewrites the real graph. Mitigated by byte-identical round-trip proof + single-revert rollback |

---

## 0. Scope

**Delivers:** `scripts/kg/decompile.py` — a one-time, mechanical exploder that turns the current
monolithic graph **and the REGISTRY/ROADMAP feature tables** into `kg-source/**` shards, rewriting
physical feature-doc refs to logical `F####/…` form. The cutover gate is
`compile(decompile(graph)) == graph` **byte-identical** (for the KG trio; the tracker byte-identity
closes at S0007). Ends with the **tagged cutover commit** on `nebula-insurance-crm`: shards become the
authored truth, the monolith becomes generated output.

**Defers:** tracker *generation* / byte-identical tracker round trip (S0007); CI enforcement flips
(S0008); doc/contract reconciliation (S0009); adopting other product repos.

---

## 1. Reuse surface

| Need | Reuse |
|------|-------|
| Read REGISTRY/ROADMAP tables | `tracker_merge.parse_tracker(text, basename)` → `Section`/`Table(rows: key→{col:cell})` (S0002) |
| Shard output serialization | `kg_common.canonical_dump` |
| Round-trip check | `compile.py` (`compile_sources` + `render`/`check_projections`, S0005) |
| Validate emitted shards | `shard_validate.validate_paths` (S0004) |
| Ref rewrite (inverse resolver) | invert `kg_common.resolve_doc_ref` using the feature `path:` map |
| Column↔field mapping | `kg-source/README.md` §4.1 (S0004 contract) |

Net-new: the partitioner (monolith sections → shard files at the D2 granularity), the tracker→
presentation-field mapper, the ref-rewriter, anomaly detection, and the cutover driver.

---

## 2. The real reconciliation facts (verified 2026-07-09)

- **canonical-nodes**: 15 node sections / ~631 nodes → `nodes/<section>/**` + `policies/` (policy_rules).
  All kinds have a directory home (no orphan kind).
- **code-index**: 216 `node_bindings` → `bindings/**`.
- **source_docs**: **276** refs into `planning-mds/features/` (rewrite → logical `F####/…`); **649**
  stable-root (passthrough).
- **features**: **40 REGISTRY rows = 33 KG-mapped (`feature-mappings.features`) + 7 coverage-excluded**
  (`coverage.excluded_features`: F0025/26/29/31/37/39/40 — the planned/reserved set). Union reconciles
  exactly; no feature is in one and missing from the other.
- **stories**: 164 in `feature-mappings.stories` → grouped by `feature` into each feature shard's
  `stories:` block (S0005-D3).
- **status vocab (real)**: `feature-mappings.features` uses `architecture-complete`, `archived`,
  `archived-done`, `planned` — **exceeds S0004's enum** (see D-status).
- **feature-mappings metadata**: `version`, `status`, `coverage_note`, `rules` (list), and
  `coverage` (dict whose only key is `excluded_features`).

---

## 3. Migration pipeline (`decompile.py`)

1. **Preflight** — load the four curated files + REGISTRY/ROADMAP; assert validators green; build the
   `feature_id → path` map.
2. **Partition nodes** — each `canonical-nodes` section → `nodes/<section>/**` (or `policies/` for
   policy_rules) at the D2 granularity (one-file for capabilities/entities/workflows; per-kind bundle
   for the thin kinds). Rewrite `source_docs`/path refs into `planning-mds/features/…` to `F####/rel`.
3. **Partition bindings** — `code-index.node_bindings` → `bindings/**`.
4. **Partition features** — for each of the 40: emit a `features/F####.yaml` merging the **technical**
   fields (from `feature-mappings.features`, when mapped) + **presentation** fields parsed from
   REGISTRY/ROADMAP via the §4.1 mapping + the feature's `stories:` block (grouped from
   `feature-mappings.stories`). The 7 coverage-excluded get presentation only + the D-coverage-excluded
   marker.
5. **Ontology** — move `solution-ontology.yaml` → `kg-source/ontology/` content-identical.
6. **Meta** — capture each projection's non-record header (version/status/coverage_note/rules) into the
   D-header meta artifact.
7. **Validate + round-trip** — `shard_validate` all emitted shards; then
   `compile(decompile(graph))` and assert **byte-identical** to the pre-migration KG trio + ontology.
8. **Anomaly gate** — any unpartitionable content, orphan mapping, feature/tracker mismatch, or
   residual diff → **loud failure, nothing written** (fix drift at the source first, then re-run).

`--check` runs 1–8 and reports the intended partition + the round-trip diff **without writing shards**.

---

## 4. Decisions (resolved 2026-07-09)

> **Confirmed:** **D-cutover** = build + dry-run + migration report, then **pause for maintainer
> go/no-go** before the tagged cutover commit. **D-coverage-excluded** = feature shard +
> `coverage_excluded:{reason}` marker (compile routes to `coverage.excluded_features`). **D-header** =
> single `kg-source/projections-meta.yaml` (NON_SHARD; compile reads it). **D-status** = extend the
> feature `status` enum additively to the real vocab. **D-drift** = fix at source first, never in shards
> (drift list surfaced in the dry-run). Details below.

- **D-header — projection metadata home (byte-identity crux).** `compile` must re-emit
  `version/status/coverage_note/rules` (and rebuild `coverage`) exactly. These aren't records, so they
  need a source home. **Recommendation:** `kg-source/projections-meta.yaml` (a tooling meta file, added
  to `shard_validate.NON_SHARD_BASENAMES` like the suppression ledger); `compile` reads it into its
  `headers` param. Confirm.
- **D-coverage-excluded — model the 7 planned features.** They live in REGISTRY (presentation) **and**
  `coverage.excluded_features` ({id, path, reason}), but not in `features[]`. **Recommendation:** emit
  them as normal `features/F####.yaml` shards carrying presentation + a `coverage_excluded: {reason}`
  marker; `compile` routes any feature with that marker into `coverage.excluded_features` (id/path/
  reason) and omits it from `features[]`. This keeps one shard per feature and retires the separate
  `exclusions/` dir for now (kept in the schema for future non-feature exclusions). Confirm, or prefer
  separate `exclusions/` shards.
- **D-status — extend the S0004 status enum.** Shard `status` projects verbatim into
  `feature-mappings.features.status`, so it must allow the real values `architecture-complete`,
  `archived`, `archived-done`, `planned` (+ the planned-provisional case from REGISTRY).
  **Recommendation:** amend `feature.schema.json`'s `status` enum additively to the real vocab; REGISTRY
  display strings ("Superseded"/"Done and archived"/…) derive from `status` + `roadmap_section` at
  render (S0007), not stored. Confirm.
- **D-cutover-execution — when to run the tagged cutover.** **Recommendation:** build `decompile.py`,
  prove the round trip on the real graph via `--check`, produce the migration report, and **pause for
  your review of that report** before I create the tagged cutover commit. The cutover is one revertable
  commit, but it rewrites the authored surface — so it gets an explicit go/no-go from you at build time.
  Confirm this gating (vs. execute-through).
- **D-drift — pre-existing source drift.** Decompiling may surface real graph/tracker drift (e.g. the
  `glossary_term` record with a `capability:` id noted in S0004; the known `test_lookup_tier`
  source_docs discrepancy). **Recommendation:** fix each at the source (monolith/tracker) as its own
  reviewed commit **before** the cutover, never laundered into shards (story Business Rule 2). I'll
  surface the full drift list in the dry-run for your review. Confirm.

---

## 5. Round-trip proof + anomaly handling

- **Gate:** `compile(decompile(graph)) == graph` byte-identical for `canonical-nodes.yaml`,
  `feature-mappings.yaml`, `code-index.yaml`, `solution-ontology.yaml`. Any residual diff is a
  decompile/compile mapping bug fixed in the tool — never a hand-edit of shards.
- **Idempotency:** decompiling twice → identical shards.
- **Count reconciliation:** node/binding counts per section, 40 feature rows (33 + 7), 164 stories —
  all reconcile exactly (nothing dropped or invented).
- **Tracker fields:** each feature shard carries the presentation fields its REGISTRY table + ROADMAP
  section require; **the byte-identical tracker re-render is S0007's gate** — here the gate is
  *populated + schema-valid + count-reconciled*.

---

## 6. Cutover mechanics

One **tagged** migration commit on the feature branch: adds `kg-source/**` + `projections-meta.yaml`,
leaves the projections byte-identical (they now equal `compile(source)`), and flips authoring truth.
A pre-migration tag + the byte-identical proof make rollback a single `git revert`. After cutover,
`decompile.py` is retired from the normal flow (kept for adopting other repos).

---

## 7. File inventory

**Product repo `nebula-insurance-crm`:**
- `scripts/kg/decompile.py` — the exploder + `--check` + migration report
- `scripts/kg/compile.py` — **edit**: route `coverage_excluded` features to `coverage.excluded_features`; read `projections-meta.yaml` headers
- `scripts/kg/shard_validate.py` — **edit**: `NON_SHARD_BASENAMES += projections-meta.yaml`; `coverage_excluded` on feature schema
- `planning-mds/schemas/kg-source/feature.schema.json` — **edit** (D-status enum, D-coverage-excluded field)
- `planning-mds/kg-source/**` — **generated by the migration** (the real shards + meta)
- `scripts/kg/tests/test_decompile.py` — round-trip, idempotency, anomaly, count-reconciliation
- migration report (archived with feature evidence)

**Framework repo `nebula-agents`:** STATUS/plan tracking only (contract/doc reconciliation is S0009).

---

## 8. Test plan (QE-signed)

`compile(decompile(fixture))` byte-identical; idempotent re-decompile; `--check` dry-run writes
nothing; anomaly failures (kind with no home, orphan mapping, feature/tracker mismatch) write nothing
and list every instance; count reconciliation (nodes/bindings/40 features/164 stories); ref-rewrite
(feature-doc → logical, stable-root preserved); the real-graph round trip proven and recorded.

---

## 9. Risks

- **Byte-identity is unforgiving** — header/`coverage` reconstruction (D-header/D-coverage-excluded)
  and canonical ordering must match exactly. The `--check` dry-run de-risks before any write.
- **Tracker parsing** — REGISTRY/ROADMAP prose/format quirks; reuse `tracker_merge.parse_tracker` and
  fail loudly on unmapped columns.
- **Real drift** — fixed at source first (D-drift), which may add a few pre-cutover cleanup commits.
- **Scope creep into S0007** — presentation fields are *populated + validated* here, not re-rendered;
  hold that line.

---

## 10. Progress checklist

- [x] Decisions D-header / D-coverage-excluded / D-status / D-cutover / D-drift resolved (2026-07-09)
- [x] S0004 schema amendments (status enum, `coverage_excluded`, object-form refs, open technical fields, `stories`→`story_mappings`) + `compile` header/coverage/blacklist routing
- [x] `decompile.py`: node/binding/feature partition at D2 granularity; ref rewrite; ontology move; meta
- [x] Tracker → presentation-field mapper (REGISTRY + ROADMAP via §4.1)
- [x] `--check` dry-run + migration report; anomaly gate (nothing written on failure)
- [x] `test_decompile.py`: real-graph round-trip, idempotency, anomaly, count-reconciliation green (6 tests)
- [x] Dry-run on the **real** graph; drift list identified (**1 item: 6 mis-filed glossary/capability records**); round-trip **proven byte-identical** after the fix (hermetic)
- [x] Source-drift fix applied (6 records glossary_terms→capabilities, reviewed commit `0c0d0e4`); `decompile.py` wrote 182 real shards; tagged cutover commit `712acd6`; `compile.py --check` byte-identical
- [x] Migration report recorded; STATUS provenance (Architect + Code Reviewer + QE PASS); story index updated (S0006 → Done)

## Dry-run checkpoint (2026-07-10)

`decompile.py --check` on the real graph reconciles all counts (**631 nodes / 216 bindings / 40 features
[33 mapped + 7 coverage-excluded] / 164 stories**) and writes nothing. It surfaces **one** pre-existing
source-drift item:

- **6 records in the `glossary_terms` section carry `capability:` ids** (`capability:document-classification`,
  `-completeness-signal`, `-management`, `-retention`, `-templates`, `outbound-document-generation`).
  They are **referenced 84× as `capability:document-*`** across the trio → they are genuinely
  **capabilities mis-filed into the glossary_terms section** (renaming the ids would break 84 refs; the
  correct fix is to **move the 6 records to the `capabilities` section, ids unchanged**).

**Proven (hermetic, `test_decompile.py`):** after that single move,
`compile(decompile(graph)) == graph` is **byte-identical for all four files with 0 anomalies**.

Per **D-drift** + **D-cutover**, the source fix + tagged cutover await maintainer go/no-go.

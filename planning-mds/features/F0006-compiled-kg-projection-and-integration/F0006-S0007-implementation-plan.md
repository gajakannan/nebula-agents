# F0006-S0007 — Implementation Plan (Tracker Generation from Feature Shards)

> **Living tracker for the B4 build.** Companion to
> [`F0006-S0007-tracker-generation-from-shards.md`](./F0006-S0007-tracker-generation-from-shards.md).
> Builds on S0004–S0006 (done; `kg-source/` is authoring truth, 40 feature shards populated with
> presentation fields). Closes the tracker round trip S0006 set up. Update §11 as work lands.

| Field | Value |
|-------|-------|
| Story | F0006-S0007 (PRD row **B4**) |
| Phase | B — Compiled projection |
| Status | **Done — 2026-07-11** (REGISTRY/ROADMAP generated; zero-diff round trip; QE + Code Reviewer + PM PASS; BLUEPRINT deferred). Commit `a85a436` |
| Created | 2026-07-10 |
| Branch (both repos) | `feat/F0006-phase-B-compiled-projection` |
| Signoff required | Quality Engineer + Code Reviewer (+ **PM** signs the one-time canonicalization diff) |
| Touches `main` | **No** — feature branch |

---

## 0. Scope

**Delivers:** generation of the **REGISTRY.md**, **ROADMAP.md**, **and BLUEPRINT.md** feature lists
from the feature shards (as `STORY-INDEX.md` is already generated from story files). The generator owns
**fenced regions** (`<!-- generated:begin … -->` / `<!-- generated:end -->`); surrounding prose stays
PM-authored. Closes the byte-identical tracker round trip: `compile(decompile(trackers)) == trackers`
(modulo a one-time canonicalization pass, PM-reviewed). `compile.py` drives it so a branch and an
integration run render identically.

**Defers:** CI/`.gitattributes` region enforcement (S0008); the S0002 tracker-merge tool retires to a
**transition-only** role (doc note here, no code removal); `nebula-agents`' own trackers (S0009/never).

---

## 1. Reuse surface

| Need | Reuse |
|------|-------|
| Parse existing tables / prose / markers | `tracker_merge.parse_tracker` → `Section`/`Table(rows, columns)` (S0002) |
| Per-table sort rules | `tracker_merge.TRACKER_CONFIGS` (`id_asc`, `date_desc`+ID-desc tiebreak, `manual`) |
| Column↔field mapping | `kg-source/README.md` §4.1 (shared with S0006 decompile) |
| Feature facts | the 40 populated `kg-source/features/**` shards |
| Deterministic write / driver | `merge3._atomic_write`; `compile.py` driver + `--check` |

Net-new: the renderer (shard fields → canonical markdown rows), the status→table/display derivation,
the fenced-region writer (writes only between markers), and the `Next Available Feature Number` counter.

---

## 2. What S0006 left, and the gap S0007 closes

S0006 **populated** each feature shard's presentation fields from the trackers and reconciled counts,
but explicitly did **not** prove the tables re-render byte-identically. S0007 renders them and proves
zero-diff regeneration. Two realities discovered while grounding this plan:

- **ROADMAP feature-link targets:** 39 `…/README.md`, **1 `…/PRD.md`** (F0014) → the link is *almost*
  derivable from `id`+`name`+`path`, with one exception (see **D-link**).
- **REGISTRY table + display status are not a straight function of `status`:** e.g. F0010 has canonical
  `status: archived-done` but renders in the **Retired** table as **"Superseded"** (it carries
  `retired_date` + `superseded_by`). Placement/display derive from a *combination* of fields (see
  **D-registry-derivation**), and may need one stored display field.

Like S0006's KG-trio work, expect an **iterate-to-byte-identity** loop; the one-time canonicalization
pass (**D-canon**) is the sanctioned escape valve for hand-authoring quirks.

---

## 3. Generator design

- **Fenced regions:** one region per table, e.g. `<!-- generated:begin registry:active -->` …
  `<!-- generated:end registry:active -->`. The generator writes **only** between markers; prose
  outside is byte-untouched. Missing/duplicated/moved markers → loud failure.
- **Render:** for each REGISTRY status table and each ROADMAP section, select the feature shards that
  belong (derivation §5), sort by the table's rule (`TRACKER_CONFIGS`), and emit rows with **stable
  column widths + cell escaping** so re-runs are zero-diff.
- **Counter:** `Next Available Feature Number` = `max(existing F####) + 1`.
- **Completeness:** every feature shard appears in exactly one REGISTRY status table **and** one ROADMAP
  section; a shard with no `roadmap_section` (or unplaceable in REGISTRY) → loud failure.
- **Driver:** `compile.py` invokes the generator after the trio (behind the same all-or-nothing).

---

## 4. Column↔field derivation (from §4.1 + this story's rules)

- **Folder** cell = ``path`` minus `planning-mds/features/`, plus trailing `/`, backtick-wrapped
  (`` `archive/F0010-…/` ``).
- **ROADMAP Feature** cell = `[F#### — name](./<folder>/README.md)` (link target per **D-link**).
- **REGISTRY table placement** (per **D-registry-derivation**): has `retired_date`/`superseded_by` →
  Retired; else has `archived_date` → Archived; else `status ∈ {planned, planned-provisional}` →
  Planned; else → Active.
- **Display status:** Retired → "Superseded" (Terminal Status); Planned → "Planned"/"Planned
  (provisional)"; Active → the `status` display; Archived table has no status column.
- **ROADMAP section** = the shard's explicit `roadmap_section`.
- Retired/Archived dates, `reason`, `completion_state`, `rationale` render verbatim from their fields.

---

## 5. Decisions (resolved 2026-07-10)

> **Confirmed:** **D-canon** = accept the one-time PM-reviewed canonicalization (tables change
> cosmetically once, then zero-diff). **D-registry-derivation** = rule-first (§4), add a stored field
> only if the rules can't reproduce a committed row. **D-blueprint** = **INCLUDE** BLUEPRINT.md's
> feature-plan list in S0007 (fenced region + generated from shards, its own canonicalization diff).
> **D-link / D-markers** = recommended defaults. Details below.

- **D-canon — one-time canonicalization (the crux).** The committed REGISTRY/ROADMAP were hand-authored;
  the generator defines a *canonical* table render. The first generation normalizes the committed tables
  to that render — a **one-time, PM-reviewed diff** (whitespace/cell format/link normalization). The
  story sanctions this ("modulo the documented canonicalization pass"). **Recommendation:** accept it;
  the committed REGISTRY.md/ROADMAP.md **will change cosmetically once** at S0007, then regeneration is
  zero-diff. Confirm (this is the parallel of S1's KG canonicalization).
- **D-link — ROADMAP link target.** 39 `README.md`, 1 `PRD.md` (F0014). **Recommendation:** render
  `./<folder>/README.md` uniformly and normalize F0014's link to README.md **iff** its README exists
  (verify at build; if not, store the target as a shard field). Confirm normalize-vs-preserve.
- **D-registry-derivation — table placement + display status.** **Recommendation:** the rule set in §4;
  if it can't reproduce every committed row's placement/label, add one `registry_status`/`terminal_status`
  field to the feature shard (a small additive schema + a shard patch), rather than over-inferring.
  Confirm the rule-first approach.
- **D-markers — fenced-region convention.** **Recommendation:** `<!-- generated:begin <file>:<table> -->`
  per table region, added once to REGISTRY.md/ROADMAP.md; the S0008 manifest marks these two files
  `fenced-region` granularity (already specified). Confirm the marker style.
- **D-blueprint — BLUEPRINT.md feature-plan list. DECIDED: INCLUDE.** BLUEPRINT.md's feature-plan list
  gets the same treatment in S0007 — fenced region(s) + generated from the feature shards, with its own
  one-time canonicalization diff (PM-reviewed). Its list shape differs from the REGISTRY/ROADMAP tables,
  so the generator gets a BLUEPRINT-specific renderer + column↔field mapping (inspect the real list at
  build; likely id/name/phase/status/section). Same fenced-region + zero-diff-regeneration gate.

---

## 6. Round-trip proof + zero-diff regeneration

1. Add fenced markers (one-time) + run the generator → canonical tables (the **D-canon** diff; PM signs).
2. Commit the normalized trackers.
3. **Gate:** re-running the generator on unchanged shards is **zero-diff** (`git diff` empty). This is
   `compile(decompile(trackers)) == trackers` closed on the canonicalized tables.
4. Count reconciliation: 40 features across REGISTRY tables (33 mapped + 7 planned) and ROADMAP sections,
   each feature in exactly one of each.

---

## 7. File inventory

**Product repo `nebula-insurance-crm`:**
- `scripts/kg/tracker_gen.py` — the fenced-region renderer (or a `tracker` module `compile.py` imports)
- `scripts/kg/compile.py` — **edit**: drive tracker generation in the downstream generator list
- `planning-mds/features/REGISTRY.md`, `ROADMAP.md` — **edit once**: add fenced markers + the canonicalized tables (D-canon; PM-reviewed)
- `planning-mds/BLUEPRINT.md` — **edit once**: fenced region(s) + generated feature-plan list (D-blueprint; PM-reviewed); BLUEPRINT-specific renderer + mapping
- `planning-mds/schemas/kg-source/feature.schema.json` — **edit** only if D-registry-derivation needs a stored display field
- `scripts/kg/tests/test_tracker_gen.py` — region-integrity, ordering, counter, zero-diff, count-reconciliation
- `scripts/kg/README.md` — **edit**: tracker-generation section; note S0002 tracker-merge is transition-only

**Framework repo `nebula-agents`:** STATUS/plan tracking; TRACKER-GOVERNANCE implications handed to S0009 (per story DoD).

---

## 8. Test plan (QE-signed)

Region-integrity (missing/duplicated marker → fail; prose outside untouched); deterministic ordering
per table (id_asc / date_desc+ID-desc / manual); `Next Available` counter; **zero-diff regeneration** on
unchanged shards; count reconciliation (every feature in exactly one REGISTRY table + one ROADMAP
section); the one-time canonicalization diff reviewed and, after commit, empty on re-run.

---

## 9. Risks

- **Markdown byte-identity** is the main risk (prose cells, escaping, link/format variance). Mitigated
  by D-canon (normalize once) + zero-diff-regeneration as the real gate.
- **Field sufficiency** — if S0006's populated fields can't reproduce a cell, augment the shard (small
  additive field + patch), don't hand-edit the table (that would break the round trip).
- **Scope drift into S0008** — region *enforcement* (CI) is S0008; S0007 only generates.

---

## 10. Sequencing note

S0007 runs against the **real** populated shards (post-S0006 cutover). The one-time canonicalization
touches the committed REGISTRY.md/ROADMAP.md prose files (fenced regions only) — a PM-reviewed diff on
the feature branch, revertable.

---

## 11. Progress checklist

- [x] Decisions D-canon / D-link / D-registry-derivation / D-markers / D-blueprint resolved (2026-07-10)
- [x] `tracker_gen.py`: fenced-region renderer; status→table/display derivation; counter; sort rules (REGISTRY/ROADMAP)
- [x] Fenced markers added to REGISTRY.md / ROADMAP.md (one-time)
- [x] First generation → canonical tables; **PM reviewed + signed the canonicalization diff** (markers + 3 ROADMAP rows)
- [x] `compile.py` drives tracker generation
- [x] Zero-diff regeneration proven on unchanged shards; count reconciliation
- [x] `test_tracker_gen.py` green (region-integrity, ordering, counter, zero-diff; REGISTRY/ROADMAP)
- [~] **BLUEPRINT.md §3.3 — DEFERRED** (D-blueprint 2026-07-11: bespoke prose + stale duplicates, not a clean projection); tracked in STATUS Deferred Non-Blocking Follow-ups
- [x] `scripts/kg/README.md` updated; S0002 noted transition-only; TRACKER-GOVERNANCE handed to S0009
- [x] STATUS provenance (QE + Code Reviewer; PM cutover signoff); story index updated

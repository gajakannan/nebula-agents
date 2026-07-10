# F0006-S0004 — Implementation Plan (`kg-source/` Shard Schema, Layout & Ownership)

> **Living tracker for the B1 build.** Companion to
> [`F0006-S0004-kg-source-shard-schema-and-ownership.md`](./F0006-S0004-kg-source-shard-schema-and-ownership.md).
> Update the checklist in §9 as work lands.

| Field | Value |
|-------|-------|
| Story | F0006-S0004 (PRD row **B1**) |
| Phase | B — Compiled projection |
| Status | **Planned — awaiting approval** (esp. decision **D2**) |
| Created | 2026-07-09 |
| Branch (both repos) | `feat/F0006-phase-B-compiled-projection` |
| Signoff required | Architect + Code Reviewer (**no QE** for S0004, per `STATUS.md`) |
| Touches `main` | **No** — feature branch only; main merges need explicit maintainer ask |

---

## 0. Scope — what S0004 delivers (and deliberately does *not*)

**Delivers:** the *input contract* for Phase B — the shard schema (per kind), the directory/ownership
taxonomy, the REGISTRY/ROADMAP column↔field mapping, and a **shard validator** with tests. Spec +
validation only.

**Explicitly defers (do not build here):**
- Compiler → S0005
- Populating real shards / the migration → S0006
- Tracker rendering → S0007
- CI / `.gitattributes` / `generated_paths.yaml` → S0008
- Removal of now-generated `knowledge-graph/*.yaml` write-scopes + doc reconciliation → S0009

S0004's `agent-map.yaml` change is **additive** — it adds the new `kg-source/**` write-scopes; it does
**not** remove the `knowledge-graph/*.yaml` scopes (the monolith stays authoritative until the B3
cutover; removing them now would misdescribe reality).

---

## 1. Headline finding — the "4 subdirs" assumption is false

PRD §3 sketches `nodes/{entities,capabilities,workflows,endpoints}/`. The **real**
`canonical-nodes.yaml` has **15 node sections / ~631 nodes**, and `solution-ontology.yaml` already
enumerates **19 `node_types` and 17 `id_patterns`** authoritatively. S0004's own "Assumptions (to be
validated)" line flagged this ("verify against the real `canonical-nodes.yaml` kind census"). Verified
2026-07-09 — it does **not** hold.

**Resolution:** the shard taxonomy is derived from the ontology / real census, not the 4-subdir
sketch. This is the single most important thing S0004 must get right — S0005/S0006 compile against it.

Live census (2026-07-09, `nebula-insurance-crm`):

```
canonical-nodes.yaml sections: adrs(34) api_contracts(2) capabilities(61) config_keys(11)
  endpoints(124) entities(54) events(25) evidence(5) glossary_terms(22) migrations(10)
  policy_rules(108) roles(10) schemas(147) ui_routes(12) workflows(6)
feature-mappings.yaml: features(33) stories(164) + excluded_features
code-index.yaml: node_bindings(216)
solution-ontology.yaml: node_types(19) id_patterns(17) edge_types(12) + embedded `ownership` matrix
```

---

## 2. Directory taxonomy (graph source → shard directory)

| Shard directory | Source today | ~Count | Owner (primary / co-sign) |
|---|---|---|---|
| `nodes/{adrs,api_contracts,capabilities,config_keys,endpoints,entities,events,evidence,glossary_terms,migrations,roles,schemas,ui_routes,workflows}/` | `canonical-nodes.yaml` sections | ~523 | Architect |
| `policies/` | `canonical-nodes.yaml` `policy_rules` + `authorization-*.yaml` | 108 | Architect / **+security** on `authorization-*` |
| `bindings/` | `code-index.yaml` `node_bindings` | 216 | Architect |
| `features/` | `feature-mappings.yaml` `features` **+** REGISTRY/ROADMAP presentation fields | 33 | Product Manager |
| `exclusions/` | `feature-mappings.yaml` `excluded_features` | — | **PM + architect** (symmetric co-sign) |
| `ontology/` | `solution-ontology.yaml` (whole-file rehome, not exploded) | 1 | Architect / **+PM** per its embedded matrix |

`stories` (164) stay projected from story files (STORY-INDEX is already generated) — **not** new shards.

---

## 3. Shard schemas (the JSON Schemas)

**Node shard** (`nodes/<kind>/<id-body>.yaml`): `id` (grammar per kind), `label`, `source_docs`
(logical refs only), `related_nodes` (IDs only) + kind-specific fields
(`route/method/resource/action/allowed_roles` for endpoints, `states` for workflows, `event_type` for
events, `key` for config_keys, `path`→stable-root for adrs/schemas, etc.). **`kind` is the `id:`
prefix and must agree with its directory** — no separate `kind:` field, so agreement is structurally
enforced.

**Feature shard** (`features/F####.yaml`) — the full tracker-projected field set:
`id`, `name`, `path`, `status`, `phase`, `roadmap_section` (Now/Next/Later/Abandoned/Completed —
required; every feature must be placed), `rationale` (Why-Now/Next/Later; required when in
Now/Next/Later), `validation_gate` (where applicable), `affects[]`, `depends_on[]`, `governed_by[]`,
`uses_api_contract[]`, `uses_schema[]`, `supersedes`/`superseded_by`, `retired_date`+`reason`,
`archived_date`, `completion_state`. Retirement/archive/supersession fields present **only when they
apply** (conditional-required).

**Column↔field mapping** (one contract shared by S0006 decompile *and* S0007 generate):

| Tracker table | Columns → shard fields |
|---|---|
| REGISTRY Active / Planned | ID←`id`, Name←`name`, Status←`status`, Phase←`phase`, Folder←`path` |
| REGISTRY Retired | +Terminal Status←`status`, Superseded By←`superseded_by`, Retired Date←`retired_date`, Reason←`reason` |
| REGISTRY Archived | ID←`id`, Name←`name`, Archived Date←`archived_date`, Folder←`path` |
| ROADMAP Now / Next / Later | Feature←link(`id`,`name`,`path`), Phase←`phase`, Why\*←`rationale` |
| ROADMAP Abandoned | Feature←link, Superseded By←`superseded_by`, Rationale←`reason` |
| ROADMAP Completed | Feature←link, Phase←`phase`, Completion State←`completion_state` |

REGISTRY table placement derives from `status`; ROADMAP section is the explicit `roadmap_section`
(a prioritization axis not derivable from status).

**Binding shard** (`bindings/`): `id` + `paths{backend/frontend/tests/...}` — code paths are
physical/stable, **not** logical refs. **Ontology / Exclusion**: schema declares home + curated-source
classification; content moves at S0006.

**ID grammar:** reuse the ontology's 17 `id_patterns` via `kg_common.type_regex_map()` — not
reinvented, so the grammar can't drift from the ontology.

---

## 4. Ownership map → `agent-map.yaml` (this repo, additive)

Add `kg-source/**` write-scopes: **architect** → `nodes/**`, `bindings/**`, `policies/**`,
`ontology/**`; **PM** → `features/**`. Encode co-sign as a secondary-approver annotation on the primary
scope (not a second write-scope): `exclusions/` (PM+architect), `ontology/` (+PM),
`policies/authorization-*` (+security). Leave the Phase-A `knowledge-graph/*.yaml` scopes and
integrator annotations untouched (S0009 removes/flips them post-cutover). Encode the same ownership map
in the product repo's `kg-source/README.md`; `KNOWLEDGE-GRAPH.md` doc encoding is S0009 (per S0004 DoD).

---

## 5. Validator — `scripts/kg/shard_validate.py` (standalone, importable)

Standalone module (keeps the ~1000-line `validate.py` clean; S0005's compiler imports it). Reuses
`kg_common` (`load_yaml`, `type_regex_map`, `iter_feature_dirs`) and `jsonschema` (confirmed
importable). Actionable errors naming file + field + rule + fix.

**Edge-case test list** (`tests/test_shard_validate.py`), one per acceptance criterion:

1. valid node/binding/feature trio passes
2. `kind` ≠ directory fails
3. physical `planning-mds/features/...` doc ref fails *with logical-form hint*
4. two top-level concepts in one file fails (unless dir allows a scoped bundle)
5. file in an unmapped directory fails
6. each kind's ID grammar (good + bad)
7. cross-shard ref carrying a path (not ID) fails
8. feature shard missing a required projected field fails (Now-section w/o `rationale`; retired w/o `retired_date`/`reason`)
9. unparseable YAML / missing `id` fails
10. binding glob syntactically invalid fails
11. owner-resolvability (every dir resolves to exactly one primary owner)

---

## 6. Exact file inventory

**Product repo `nebula-insurance-crm`:**
- `planning-mds/kg-source/README.md` — schema spec + layout + ownership map + column↔field mapping
- `planning-mds/schemas/kg-source/*.schema.json` — per-kind schemas (node kinds, feature, binding, policy, exclusion, ontology-ref)
- `scripts/kg/shard_validate.py` — validator
- `scripts/kg/tests/test_shard_validate.py` — tests
- `scripts/kg/tests/fixtures/kg-source/**` — fixture shards (valid + each failing case); **not** real populated shards (that's S0006)

**Framework repo `nebula-agents` (this repo):**
- `agents/agent-map.yaml` — additive `kg-source/**` scopes + co-sign annotations
- `planning-mds/features/F0006-.../STATUS.md` — S0004 → Done + Architect/Code-Reviewer provenance
- this plan doc — kept current

---

## 7. Decisions (flag if you disagree)

- **D1 — taxonomy:** expand `nodes/` to the real 14 node kinds + top-level `policies/bindings/features/exclusions/ontology/`. *(forced by §1)* — **decided**
- **D2 — file granularity:** one-concept-per-file for the collision-prone kinds (`capabilities`, `entities`, `workflows`) and **all features**; allow per-kind **bundle** files for thin high-count kinds (`endpoints`, `schemas`, `policy_rules`, `adrs`, `roles`, `config_keys`, `events`, `glossary_terms`, `migrations`, `api_contracts`, `ui_routes`, `evidence`). Bundles stay mergeable via `merge3`. **⇐ the one call most worth confirming; sets S0006 migration granularity.** — **PENDING CONFIRMATION**
- **D3 — validator home:** standalone `shard_validate.py`, not folded into `validate.py`. — **decided**
- **D4 — ID grammar:** reuse ontology `id_patterns` rather than a new list. — **decided**
- **D5 — closeout style:** record S0004 signoff in `STATUS.md` provenance (Architect + Code Reviewer) with the green validator test run as evidence — Phase-A delegated-signoff style, not a full `feature.md` evidence run. — **decided**

---

## 8. Boundaries / risks

- Data anomaly already visible: a `glossary_terms` record carries id `capability:document-classification` (wrong prefix). S0004's validator **flags** such cases; **fixing** them is S0006's "fix drift at the source first" rule — S0004 does not touch graph data.
- Nothing here touches `main` in either repo.
- `status` vocabulary reconciliation (feature-mappings `archived-done` vs REGISTRY `Superseded`/`Planned`/…) is captured as a projection rule in the mapping doc; actual normalization happens during S0006 decompile.

---

## 9. Progress checklist (maps to story DoD)

- [ ] D2 confirmed with maintainer (unblocks migration granularity)
- [ ] `kg-source/README.md` schema spec + layout + ownership map + column↔field mapping landed
- [ ] Per-kind JSON Schemas under `planning-mds/schemas/kg-source/` landed
- [ ] `shard_validate.py` implemented (reuses `kg_common` + `jsonschema`)
- [ ] `test_shard_validate.py` — all 11 edge cases green
- [ ] Fixture shards (valid + failing) under `tests/fixtures/kg-source/`
- [ ] Ownership map encoded in `agent-map.yaml` (additive) — verified against §2
- [ ] Single-home decision recorded for the full tracker-projected field set + column↔field mapping
- [ ] Story filename matches `Story ID` prefix (already true)
- [ ] Story index regenerated / updated
- [ ] `STATUS.md` — S0004 → Done; Architect + Code Reviewer provenance rows
- [ ] Architect signoff
- [ ] Code Reviewer signoff

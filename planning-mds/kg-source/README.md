# `kg-source/` — Authored Knowledge-Graph Source Shards

> **Status:** adopted in Nebula Agents during F0001 G7 remediation completed on 2026-07-15. These shards are
> authoritative; `scripts/kg/compile.py` produces `planning-mds/knowledge-graph/*.yaml` and the
> generated tracker regions.

`kg-source/` is the **only layer humans and role agents author**. A deterministic compiler
(`scripts/kg/compile.py`, S0005) projects it into the generated graph
(`planning-mds/knowledge-graph/*.yaml`) and the tracker tables. Two rules are absolute:

1. **Never hand-edit a generated file.** If a projection looks wrong, fix the shard (or the compiler)
   and recompile.
2. **Shards reference other concepts by ID only, and reference docs by *logical* ref only.** No shard
   ever embeds a path to another shard, and no shard embeds a physical `planning-mds/features/...`
   doc path (those move; use the logical `F####/rel-path` form — see §5).

---

## 1. Directory layout & ownership

Every shard lives under a directory typed by kind. Each directory has exactly one **primary owner
role** (the conflict-routing target); three directories additionally require **co-sign**.

| Directory | Holds | Compiles into | Primary owner | Co-sign |
|-----------|-------|---------------|---------------|---------|
| `nodes/adrs/` | `adr:` records | `canonical-nodes.yaml → adrs` | Architect | — |
| `nodes/api_contracts/` | `api:` records | `→ api_contracts` | Architect | — |
| `nodes/capabilities/` | `capability:` records | `→ capabilities` | Architect | — |
| `nodes/config_keys/` | `config_key:` records | `→ config_keys` | Architect | — |
| `nodes/endpoints/` | `endpoint:` records | `→ endpoints` | Architect | — |
| `nodes/entities/` | `entity:` records | `→ entities` | Architect | — |
| `nodes/events/` | `event:` records | `→ events` | Architect | — |
| `nodes/evidence/` | `evidence:` records | `→ evidence` | Architect | — |
| `nodes/glossary_terms/` | `glossary_term:` records | `→ glossary_terms` | Architect | — |
| `nodes/migrations/` | `migration:` records | `→ migrations` | Architect | — |
| `nodes/roles/` | `role:` records | `→ roles` | Architect | — |
| `nodes/schemas/` | `schema:` records | `→ schemas` | Architect | — |
| `nodes/ui_routes/` | `ui_route:` records | `→ ui_routes` | Architect | — |
| `nodes/workflows/` | `workflow:` records | `→ workflows` | Architect | — |
| `policies/` | `policy_rule:` records + `authorization-*.yaml` | `→ policy_rules` | Architect | **+ Security** on `authorization-*.yaml` |
| `bindings/` | node→code path bindings | `code-index.yaml → node_bindings` | Architect | — |
| `features/` | `feature:` records **+ tracker presentation fields** | `feature-mappings.yaml → features` + REGISTRY/ROADMAP tables | Product Manager | — |
| `exclusions/` | excluded-feature records | `feature-mappings.yaml → excluded_features` | Product Manager | **+ Architect** (symmetric) |
| `ontology/` | `solution-ontology.yaml` (whole-file rehome) | (curated source; consumed by all tools) | Architect | **+ PM** per its embedded ownership matrix |

Detailed `story:` mappings are authored inside their owning feature shard's `story_mappings`
block. `STORY-INDEX.md` is independently generated from story files, and `coverage-report.yaml`
stays a `validate.py --write-coverage-report` regeneration.

> This taxonomy is the **corrected** layout. PRD §3 sketched only `nodes/{entities,capabilities,`
> `workflows,endpoints}/`; the real `canonical-nodes.yaml` carries 15 node sections / ~631 nodes and
> `solution-ontology.yaml` enumerates 19 `node_types`. The four-subdir sketch was an illustration, not
> the census — see the S0004 implementation plan §1.

Ownership is also encoded as write-scopes in `agents/agent-map.yaml` (architect →
`nodes/`,`bindings/`,`policies/`,`ontology/`; PM → `features/`), with co-sign as a secondary-approver
annotation on the primary scope — **not** a second write-scope.

---

## 2. Shard files: one concept per file, or an allowed bundle

A shard file is either:

- **Single-concept** — a YAML mapping with a top-level `id:` (one record). Allowed in every directory.
- **Bundle** — a YAML mapping with exactly one top-level key equal to the directory's plural kind name
  mapping to a list of records (e.g. `endpoints:` → `[ {id: …}, … ]`). Allowed **only** in
  bundle-eligible directories.

A file that contains two or more top-level `id`-bearing concepts (and is not a valid single-key
bundle) fails validation ("one concept per file").

**Granularity policy (D2, confirmed 2026-07-09):**

| Mode | Directories |
|------|-------------|
| **One concept per file** (required) | `nodes/capabilities/`, `nodes/entities/`, `nodes/workflows/`, `features/` |
| **Bundle allowed** | all other `nodes/*`, `policies/`, `bindings/`, `exclusions/` |

Rationale: the collision-prone, prose-rich kinds (capabilities, entities, workflows) and every feature
get their own file so independent branches touch disjoint paths. Thin, high-count kinds may bundle;
bundles still merge cleanly through `merge3.py` (kept for shards in Phase B).

Filename convention: the ID's kebab body (already filesystem-safe by the ID grammar), e.g.
`capability:dashboard-home` → `nodes/capabilities/dashboard-home.yaml`; bundles use the plural kind
name, e.g. `nodes/endpoints/endpoints.yaml`.

---

## 3. Per-kind field profiles

`id` is required on every record. Referential fields (`related_nodes`, `affects`, `governed_by`,
`uses_schema`, `uses_api_contract`, `depends_on`, `allowed_roles`, `supersedes`/`superseded_by`) carry
**IDs only**. `source_docs` carry **logical or stable-root refs only** (§5). The machine-enforced
profile lives in `scripts/kg/shard_validate.py` (`KIND_PROFILES`) and is covered by tests; the
structural envelope lives in `planning-mds/schemas/kg-source/node.schema.json`.

| Kind | Required | Optional |
|------|----------|----------|
| `adr` | `id`, `label`, `path` | `related_nodes` |
| `api_contract` | `id`, `label`, `path` | `related_nodes` |
| `capability` | `id`, `label` | `source_docs`, `related_nodes`, `notes` |
| `config_key` | `id`, `label`, `key` | `related_nodes`, `source_docs`, `notes` |
| `endpoint` | `id`, `label`, `route`, `method` | `related_nodes`, `source_docs`, `resource` |
| `entity` | `id`, `label` | `source_docs`, `related_nodes`, `related_entities`, `notes` |
| `event` | `id`, `label`, `event_type` | `related_nodes`, `source_docs` |
| `evidence` | `id`, `label`, `path` | `related_nodes` |
| `glossary_term` | `id`, `label` | `related_nodes`, `source_docs` |
| `migration` | `id`, `label`, `path` | `related_nodes` |
| `role` | `id`, `label` | `notes`, `source_docs`, `related_nodes` |
| `schema` | `id`, `path` | `related_nodes` |
| `ui_route` | `id`, `label`, `route` | `related_nodes`, `source_docs` |
| `workflow` | `id`, `label` | `rationale`, `states`, `source_docs`, `related_nodes` |
| `policy_rule` | `id`, `label`, `resource`, `action`, `allowed_roles` | `related_nodes`, `source_docs` |
| `binding` | `id`, `paths` | — |
| `feature` | see §4 | see §4 |
| `exclusion` | `id`, `reason` | `excluded_by`, `notes` |

`path` on `adr`/`api_contract`/`migration`/`schema`/`evidence` is a **stable-root** ref (§5) — those
docs live in `architecture/`, `api/`, `schemas/`, `engine/` and don't move with features.

---

## 4. Feature shard — the single home for every tracker fact

`features/F####.yaml` is the sole authored home not only for `path`/`status`/`depends_on` but for
**every fact the REGISTRY and ROADMAP tables project**. A tracker cell that is not derivable from a
feature-shard field is a schema gap, not a table edit.

| Field | Required | Meaning |
|-------|----------|---------|
| `id` | yes | `feature:F####` |
| `name` | yes | display name |
| `path` | yes | feature folder (physical; the anchor logical refs resolve *through*) |
| `status` | yes | canonical status (see vocabulary below) |
| `phase` | no | delivery phase label where the registry view uses one |
| `roadmap_section` | yes | `Now` \| `Next` \| `Later` \| `Abandoned` \| `Completed` |
| `roadmap_order` | no | integer position within the ROADMAP section (captures the PM-authored order; consumed by the S0007 tracker generator) |
| `rationale` | when `roadmap_section ∈ {Now,Next,Later}` | the ROADMAP "Why Now/Next/Later" prose |
| `completion_state` | when `roadmap_section = Completed` | the ROADMAP "Completion State" prose |
| `validation_gate` | where applicable | entry/exit gate note |
| `registry_section` | no | explicit `Active` / `Retired` / `Planned` / `Archived` placement override |
| `affects` | no | node IDs |
| `depends_on` | no | feature/story/node IDs |
| `governed_by` | no | `adr:` IDs |
| `uses_api_contract` | no | `api:` IDs |
| `uses_schema` | no | `schema:` IDs |
| `supersedes` / `superseded_by` | when applicable | feature IDs |
| `retired_date` + `reason` | when `status = superseded/retired` | REGISTRY Retired row |
| `archived_date` | when archived | REGISTRY Archived row |
| `evidence_reentry_date` | when archived evidence was re-entered | REGISTRY Archived evidence date |
| `completed_date` | when completed | ROADMAP Completed date |
| `story_mappings` | no | detailed story mappings owned by this feature (`id`, `path`, `affects`, `uses_*`); compiled into `feature-mappings.yaml` top-level `stories` with `feature` set to this shard's id (added S0005-D3; named distinctly from any verbatim per-feature `stories` id-list feature-mappings itself carries) |

**Canonical `status` vocabulary** (lowercase-kebab; display strings are derived at render time):
`active`, `in-progress`, `planned`, `planned-provisional`, `superseded`, `done`, `archived-done`,
`retired`, `architecture-complete`, and `archived`. The tracker-display mapping (e.g. `archived-done` → REGISTRY "Archived" table + ROADMAP
"Completed") is documented in §4.1; **normalization of today's mixed vocabulary happens during the
S0006 decompile**, not here.

### 4.1 REGISTRY / ROADMAP column↔field mapping (shared by S0006 decompile & S0007 generate)

| Tracker table | Columns → shard fields |
|---------------|------------------------|
| REGISTRY · Active / Planned | ID←`id`, Name←`name`, Status←`status`, Phase←`phase`, Folder←`path` |
| REGISTRY · Retired | ID←`id`, Name←`name`, Terminal Status←`status`, Superseded By←`superseded_by`, Retired Date←`retired_date`, Folder←`path`, Reason←`reason` |
| REGISTRY · Archived | ID←`id`, Name←`name`, Archived Date←`archived_date`, Evidence Reentry Date←`evidence_reentry_date`, Folder←`path` |
| ROADMAP · Now | Feature←link(`id`,`name`,`path`), Status←`status`, Why Now←`rationale`, Validation Gate←`validation_gate` |
| ROADMAP · Next | Feature←link(`id`,`name`,`path`), Status←`status`, Why Next←`rationale`, Entry Criteria←`validation_gate` |
| ROADMAP · Later | Feature←link(`id`,`name`,`path`), Status←`status`, Notes←`rationale` |
| ROADMAP · Abandoned | Feature←link(`id`,`name`,`path`), Superseded By←`superseded_by`, Rationale←`rationale` |
| ROADMAP · Completed | Feature←link(`id`,`name`,`path`), Completed Date←`completed_date`, Evidence←`completion_state` |

REGISTRY table placement uses `registry_section` when present and otherwise derives from lifecycle
fields and `status`; ROADMAP section is the explicit `roadmap_section`
(a prioritization axis not derivable from status). This one mapping is the contract S0006's decompiler
populates *from* and S0007's generator renders *back to* — the byte-identical round trip proves they
agree.

---

## 5. Reference forms

- **Cross-concept references** (`related_nodes`, `affects`, `depends_on`, `allowed_roles`, …): the
  target's **canonical ID** only. Never a file path.
- **Logical feature-doc refs** (`source_docs` into a feature folder): `F####/relative/path.md` — the
  compiler resolves the `F####` prefix through that feature shard's `path:`, so archiving a feature
  (one `path:` edit) repoints every ref with zero shard changes. A physical
  `planning-mds/features/...` ref is rejected with the logical-form hint.
- **Stable-root refs** (`source_docs`/`path` outside `planning-mds/features/`): physical paths under
  `architecture/`, `api/`, `schemas/`, `security/`, `engine/`, `experience/` pass through as-is.

---

## 6. ID grammar

IDs follow `solution-ontology.yaml`'s `id_patterns` (the authoritative source). The validator reuses
`kg_common.type_regex_map()` and fills the kinds it does not yet cover, using the shared slug
`[a-z0-9]+(?:-[a-z0-9]+)*`:

| Kind | Grammar | Example |
|------|---------|---------|
| entity / capability / workflow / role / schema / ui_route / event / config_key / migration / glossary_term / policy_rule | `<kind>:<slug>` | `capability:dashboard-home` |
| endpoint | `endpoint:<slug>` | `endpoint:submission-transition` |
| api_contract | `api:<slug>` | `api:nebula-rest` |
| adr | `adr:<number-or-slug>` | `adr:014-search` |
| feature | `feature:F####` | `feature:F0006` |

No sequence numbers except REGISTRY-governed `F####`; no GUIDs for concepts.

---

## 7. Validate

```bash
python3 scripts/kg/shard_validate.py                 # validate every shard under kg-source/
python3 scripts/kg/shard_validate.py <file|dir> ...  # validate specific shards
python3 scripts/kg/compile.py --check                # prove projections and tracker regions are current
python3 scripts/kg/validate.py --check-reproducible  # prove source, output, and git policy agree
```

Exit 0 = all shards valid; exit 1 = one or more violations (each names the file, field, rule, and
fix). The compiler (S0005) imports the same checks so a branch and its integration run enforce one
contract. Every violation type is covered by `scripts/kg/tests/test_shard_validate.py`.

# F0006-S0004 - `kg-source/` Shard Schema, Layout, and Ownership

## Story Header

**Story ID:** F0006-S0004
**Feature:** F0006 - Compiled Knowledge-Graph Projection and Governed Integration
**Title:** `kg-source/` shard schema, layout, and ownership
**Priority:** Critical
**Phase:** Platform Hardening (Feature Phase B)

## User Story

**As a** contributor (human or role agent) adding a feature's graph facts
**I want** a documented shard layer — one concept per small file, typed by directory, each directory owned by exactly one role — with a validated schema
**So that** independent features touch disjoint files (naturally mergeable), every shard has an unambiguous owner for conflict routing, and the compiler has a stable input contract.

## Context & Background

This story is the specification half of Phase B: the shard schema and ownership map must be agreed
before the compiler (S0005) or the migration (S0006) is built against them. It also settles the
classification questions earlier drafts left open: `solution-ontology.yaml` is curated source and
rehomes to `kg-source/ontology/` (keeping its embedded architect/PM ownership matrix authoritative
for its sections); `decisions-index.yaml` is confirmed generated. It records the **single-home**
decision for feature facts: the feature shard is the sole authored home not only for `path`,
`status`, and `depends_on`, but for **every fact the REGISTRY and ROADMAP tables project** — display
`name`, `phase`, roadmap section, the `Why Now`/`Why Next` rationale and the validation/entry gate,
supersession, and retirement/archive dates. None of these presentation fields live in the current KG
files (`feature-mappings.yaml` carries only `status`/`path`/`affects`/`depends_on`/`supersedes`), so
the schema must define them here or S0007's tracker generator has nothing to render and S0006's
decompiler has no target to populate. The tracker **column↔field mapping** is part of this schema
contract — one definition consumed by *both* the S0006 decompiler (trackers → shard fields) and the
S0007 generator (shard fields → trackers), so the migration round trip is symmetric. ROADMAP's
dependency mentions and every other table cell become projections from the shard.

Layout (per PRD §3): `nodes/{entities,capabilities,workflows,endpoints}/`, `features/`,
`bindings/`, `policies/`, `exclusions/`, `ontology/`. Semantic-ID strategy per PRD §4 (no sequence
numbers except REGISTRY-governed `F####`; no GUIDs for concepts). Logical doc refs per PRD §5.

## Acceptance Criteria

**Happy Path:**
- **Given** the schema spec and a new capability with its binding and owning feature
- **When** a contributor authors three shards (node, binding, feature) following the spec
- **Then** each file passes shard validation (id, kind/directory agreement, owner resolvable,
  logical doc refs only, references well-formed) and the schema documents every field they needed.

**Alternative Flows / Edge Cases:**
- A shard whose `kind` disagrees with its directory fails validation.
- A shard with a physical `planning-mds/features/...` doc ref fails with the logical-form hint.
- A shard file containing two top-level concepts fails ("one concept per file") unless the
  directory's spec explicitly allows a scoped bundle (e.g. an endpoint group).
- Ownership map covers every directory; a file outside mapped directories fails.
- The spec defines ID grammar per kind (`capability:kebab-case`, `entity:kebab-case`,
  `endpoint:resource-action`, `adr:NNN`, `schema:name`, `feature:F####`).
- Cross-shard references (`affects`, `governed_by`, `uses_schema`) are declared by ID only —
  resolution is the compiler's job, so shards never embed paths to other shards.
- A feature shard missing a field its REGISTRY status table or ROADMAP section requires (e.g. a
  `now`-section feature with no `rationale`, or a retired feature with no `retired_date`/`reason`)
  fails validation — S0007's tracker projection must never have to invent a cell.

## Interaction Contract

N/A — specification + validation rules; no interactive surface.

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| Shard files under `planning-mds/kg-source/**` | Author/edit a shard | The shard | Validated by compiler/`validate.py` | Deterministic re-validation | Directory owner role only |

## Data Requirements

**Deliverables:**
- Schema spec document (product repo `planning-mds/kg-source/README.md` + JSON Schemas per kind
  under `planning-mds/schemas/kg-source/`).
- Feature-shard schema enumerating the **full tracker-projected field set** — `id`, `name`, `path`,
  `status`, `phase`, `roadmap_section`, `rationale` (Why Now/Why Next), `validation_gate`/entry
  criteria, `affects`, `depends_on`, `supersedes`/`superseded_by`, `retired_date`, `reason`,
  `archived_date` (retirement/archive fields present only when they apply) — plus the REGISTRY and
  ROADMAP **column↔field mapping**, so S0006 (decompile) and S0007 (generate) share one contract.
- Ownership map: directory → primary owner (+ co-sign), encoded both in docs and in
  `agents/agent-map.yaml` write scopes:
    - Primary architect: `nodes/`, `bindings/`, `policies/`, `ontology/`
    - Primary PM: `features/`
    - Co-sign: `exclusions/` (PM + architect), `ontology/` (+ PM per its embedded matrix),
      `policies/` (+ security where applicable)
  Co-sign is encoded as a secondary approver on the primary owner's scope, not a second write scope.

**Validation Rules:**
- Every shard: parseable YAML, required `id`, kind/directory agreement, single owner.
- Referential fields ID-only; doc refs logical-only; binding globs syntactically valid.

## Role-Based Visibility

**Roles that can author each shard directory (the ownership map this story defines):**
- Architect — `nodes/`, `bindings/`, `policies/`, `ontology/`.
- Product Manager — `features/`.
- Co-sign — `exclusions/` (PM + architect), `ontology/` (+ PM per its embedded matrix), `policies/`
  (+ security on `authorization-*.yaml`).
- Compiler / `validate.py` — read-only consumers that enforce owner-resolvability.

**Data Visibility:** N/A — source-shard schema for local planning docs; no auth surface and no
internal/external data exposure. Directory ownership is encoded as write scopes in
`agents/agent-map.yaml`, not as end-user ABAC.

## Dependencies

**Depends On:** F0006-S0003 (routing table consumes the ownership map; Phase A complete).
**Related Stories:** F0006-S0005 (compiler consumes this contract), F0006-S0006 (migration emits
shards in this shape and populates the presentation fields), F0006-S0007 (tracker generator renders
the presentation fields and column↔field mapping defined here), F0006-S0009 (agent-map/docs encode
the ownership).

## Business Rules

1. One concept (or one explicitly-allowed scoped bundle) per file.
2. Every directory has exactly one **primary owner role** (the conflict-routing target). Three
   directories additionally require **co-sign** on the relevant files/sections, which the
   compiler/validator records but does not auto-resolve:
   - `exclusions/` — PM + architect (symmetric: either-side change needs both).
   - `ontology/` — architect primary; PM co-sign on the sections its embedded ownership matrix
     assigns to PM.
   - `policies/` — architect primary; security co-sign where applicable (e.g. `authorization-*.yaml`).
3. Feature shards are the single home for **every fact the trackers project**: `path`, `status`,
   `depends_on`, `affects`, display `name`, `phase`, roadmap section, the `Why Now`/`Why Next`
   rationale, the validation/entry gate, supersession, and retirement/archive dates. A tracker
   table cell that is not derivable from a feature-shard field is a schema gap, not a table edit.
4. No shard may reference another shard by file path — IDs only.

## Out of Scope

- The compiler itself (S0005), populating the shards (S0006), tracker projection fields' rendering
  (S0007).

## Non-Functional Expectations

- Schema validation errors are actionable (name the file, field, rule, and fix).

## Questions & Assumptions

**Open Questions:**
- [x] Whether `policies/` needs security-role co-sign for authorization rules — **decided: yes**,
      security co-sign on `authorization-*.yaml` (per PRD §2 "security co-sign where applicable";
      encoded in the co-sign column of Business Rule 2).

**Assumptions (to be validated):**
- The current graph's node kinds map cleanly onto the four `nodes/` subdirectories (verify against
  the real `canonical-nodes.yaml` kind census during S0006).

## Definition of Done

- [x] Schema spec + JSON Schemas reviewed and landed (`kg-source/README.md`; `schemas/kg-source/{node,feature,binding,exclusion}.schema.json`)
- [x] Ownership map encoded in docs and `agent-map.yaml` (architect `nodes/bindings/policies/ontology`, PM `features/exclusions`, co-sign annotated; `validate_agent_map.py` green)
- [x] Shard validation implemented (`scripts/kg/shard_validate.py`, standalone) with tests for every edge case
      above (29 tests green)
- [x] Single-home decision recorded for the **full tracker-projected field set** (not just
      `depends_on`): schema enumerates `name`, `phase`, roadmap section, rationale, validation/entry
      gate, supersession, and retirement/archive dates, plus the REGISTRY/ROADMAP column↔field
      mapping (`kg-source/README.md` §4/§4.1; KNOWLEDGE-GRAPH.md encoding lands via S0009)
- [x] Story filename matches `Story ID` prefix
- [x] Story index regenerated or updated (S0004 → Done)

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

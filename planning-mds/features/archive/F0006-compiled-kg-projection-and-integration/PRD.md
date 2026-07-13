# F0006 - Compiled Knowledge-Graph Projection and Governed Integration PRD

## Feature Header

**Feature ID:** F0006
**Feature Name:** Compiled Knowledge-Graph Projection and Governed Integration
**Priority:** Critical
**Phase:** Platform Hardening
**Status:** Archived (recovery G8 closeout 2026-07-12)
**Supersedes:** F0005 (Move-Invariant Knowledge-Graph Feature-Doc References — absorbed as the compiler's reference format)

## Feature Statement

**As a** framework maintainer merging concurrent contributor feature branches
**I want** the knowledge graph and feature trackers to be deterministic projections compiled from
small per-concept source files, merged semantically (by record ID against the merge base) and
regenerated unconditionally at integration time by a dedicated integrator role
**So that** independent features merge with zero hand-editing of graph/tracker files, true semantic
collisions surface as typed domain errors routed to the owning role, and no textual YAML merge can
ever corrupt or silently stale the graph.

## Business Objective

- **Goal:** Stop asking git to merge compiled YAML; make N concurrent contributor branches
  integrable with effort proportional to *real semantic collisions*, not file churn.
- **Metric 1:** Hand-merged hunks in `planning-mds/knowledge-graph/*` and tracker files per
  contributor PR merged. Baseline: PR #47 required 7 conflicted files, ~600 conflicted lines, and a
  role-agent review to resolve. Target: 0 (independent features), or a typed conflict report
  (real collisions).
- **Metric 2:** Time-to-merge for a contributor PR whose code is clean. Baseline: days (manual
  review of KG conflicts). Target: one integrator run.
- **Metric 3:** Graph staleness escapes on the mainline (stale paths, duplicated nodes, stale
  counts). Baseline: known instances from F0038 closeout and PR #47 union-merge risk.
  Target: 0 — prevented structurally by unconditional regeneration + reproducibility CI.

## Problem Statement

- **Current State (evidence from `nebula-insurance-crm`):**
  - PR #47 (F0021): 7 merge conflicts, all tracker/KG (`REGISTRY.md`, `ROADMAP.md`,
    `canonical-nodes.yaml`, `feature-mappings.yaml`, `symbol-index.yaml`,
    `unbound-but-referenced.yaml`, `coverage-report.yaml`), zero code conflicts. Four more PRs
    (#48–#51) fork from the same point with the same shape; PR #51 stacks on #47. Two more
    (#53 F0022, #54 F0008) joined the queue on 2026-07-04 touching the identical KG/tracker file
    set — the queue grows while integration stays manual.
  - Contributor tooling **re-serialized** curated YAML (indent style, comments stripped, unicode
    escapes), so both sides of most hunks contain the *same nodes* — git union merge would
    duplicate nodes and break structure; textual conflict resolution is noise-vs-signal work.
  - Generated files (`symbol-index`, `coverage-report`, `unbound-but-referenced`,
    `decisions-index`, `STORY-INDEX.md`) get hand-merged or accepted from one side, which is always
    wrong: a *textually clean* git merge of two generated files is not the generation over merged
    sources (ordering, counts, cross-references go silently stale).
  - No role owns integration. The orchestration contract assigns per-feature ownership (PM = WHAT,
    architect = HOW) but nobody owns "reconcile with a mainline that moved" — F0038's closeout
    needed an off-book PM edit of architect-owned files, and PR #47's resolution had no sanctioned
    owner at all.
  - Physical feature-doc paths embedded in the graph go stale on the G8 archive move (the F0005
    problem, re-triggered by every merge from a branch cut before an archive).
- **Desired State:** Contributors author **source shards** (one concept per file) and code;
  everything global is compiled. Merges are semantic (record-level, three-way) with a typed
  conflict taxonomy. Generated outputs are committed on every branch, provably reproducible in CI,
  and regenerated unconditionally at merge time by the integrator role — the sole writer of
  generated files on the mainline.
- **Impact:** Multi-contributor development stops being gated on a maintainer hand-resolving YAML;
  ownership boundaries become honest (nobody needs off-book edits); the graph can never drift from
  its sources without CI catching it.

## Scope & Boundaries

**In Scope — Phase A (governed integration, pre-migration):**
- `scripts/kg/merge3.py`: three-way semantic merge of the *current monolithic* curated KG files
  (`canonical-nodes.yaml`, `feature-mappings.yaml`, `code-index.yaml`), keyed by semantic ID, with
  typed conflicts, per-field merge rules, canonical serialization, all-or-nothing output.
- Tracker-row merge: `REGISTRY.md` / `ROADMAP.md` feature tables merged as records keyed by
  feature ID (deterministic ordering rules), inside or alongside `merge3.py`.
- The **integrator role** in `nebula-agents` (persona, `agent-map.yaml` wiring, `integrate` action,
  integration evidence contract) and its operating procedure for maintainers.
- Draining the 7-PR queue in `nebula-insurance-crm` (#47–#51, #53, #54) as the integrator's first
  production runs; contributor PRs that arrive before the train completes join the same train.

**In Scope — Phase B (compiled projection):**
- `planning-mds/kg-source/` shard layer: schema, directory layout, per-directory role ownership.
- `scripts/kg/compile.py`: deterministic compiler emitting the graph projections, then driving the
  existing generators (`symbols.py`, `decisions.py`, coverage, story index).
- Logical feature-doc references (`F####/relative-path`) as the only doc-ref format in source
  shards — absorbs F0005 S0001–S0003.
- Decompiler-first migration: mechanically explode the current graph into shards; require a
  byte-identical compile round-trip before shards become truth.
- Tracker generation: `REGISTRY.md` and `ROADMAP.md` feature tables (and `STORY-INDEX.md`, already
  generated) become projections from feature shards.
- Git policy and CI: reproducibility check, hand-edit guard on generated files, `.gitattributes`
  (merge driver + `linguist-generated` for whole-file generated paths only).
- Framework-contract reconciliation: actions, prompts, KG docs, templates, ownership boundaries —
  absorbs F0005 S0004.

**Out of Scope:**
- Adopting OmniGraph (or any graph database/runtime): no Lance/object storage, no server, no vector
  search, no Cedar. Only its merge *semantics* are adapted. Revisit only if Nebula later needs
  live multi-agent graph writes or server-backed memory.
- GitHub merge queue / bot accounts — unavailable on a personal account; the integrator role
  replaces both. Plain GitHub Actions (PR-level checks) remain in scope.
- Rewriting evidence-run history (append-only; supersede with new runs, never edit).
- Code-merge tooling — code conflicts stay ordinary git work (they were zero in the observed PRs).
- Migrating product repos other than `nebula-insurance-crm` (each is an independent later
  application of the same steps).

## Acceptance Criteria Overview

Phase-A criteria (the first five below, plus unconditional merge-time regeneration) are **met** —
evidence in `STATUS.md` (merge-train exit and S0001–S0003 signoffs). Phase-B criteria remain open
until S0004–S0009 land.

- [x] `merge3.py` merges base/ours/theirs of the curated KG files by semantic ID; identical
      re-serialized content converges with **zero** conflicts; real divergence yields typed
      conflicts; output is canonically serialized or nothing (all-or-nothing).
- [x] REGISTRY/ROADMAP feature tables merge as keyed rows with deterministic ordering
      (archived tables newest-first, feature-ID-descending tiebreak).
- [x] The integrator role exists in `nebula-agents` (persona + `agent-map.yaml` + `integrate`
      action) and is the sole sanctioned writer of generated graph/tracker files on the mainline;
      it never authors source changes (never writes feature docs or `kg-source/` shards; the
      curated KG trio and tracker tables change only via mechanical merge3/tracker convergence);
      conflicts route to architect (nodes/bindings) or PM (features/trackers) per the taxonomy.
- [x] All open `nebula-insurance-crm` contributor PRs (7 at planning time: #47–#51, #53, #54) are
      merged through integrator runs, each leaving an integration evidence run and a green
      `validate.py`.
- [x] Every integration run is bracketed by two human gates, both recorded in the evidence run:
      a passing `feature-review` verdict (or maintainer waiver with rationale) verified before the
      run starts, and a maintainer test validation of the prepared merge worktree before push.
- [ ] `kg-source/` schema is documented with per-directory ownership mapped to existing roles;
      `solution-ontology.yaml` has an explicit home in the classification.
- [ ] `compile.py` is deterministic (stable ordering/formatting, no committed timestamps): same
      sources → byte-identical outputs, proven by double-compile in CI.
- [ ] Migration round-trip is proven: decompile current graph **and REGISTRY/ROADMAP feature
      tables** → shards → compile → byte-identical to the pre-migration graph (at B3) **and to the
      pre-migration trackers (at B4)**, modulo the documented canonicalization pass.
- [ ] Committed projections equal `compile(source)` on every PR (CI reproducibility check,
      blocking after Phase B cutover); hand-edits to generated files fail CI with an actionable
      message.
- [x] Merge-time regeneration is **unconditional** — the integrator recompiles even when git
      reports a clean merge of generated files.
- [ ] Feature-doc references in source shards are logical (`F####/rel-path`); archiving a feature
      is exactly one `path:` edit in its feature shard; no physical feature path survives in any
      source-authored graph field (F0005's acceptance, delivered via the compiler).
- [ ] Framework docs/templates/prompts describe exactly the shipped behavior — no off-book steps.

## Design & Mechanism

### 1. Core principle

Treat the knowledge graph like a **compiled database projection**, not hand-merged documentation.
Human/LLM-authored files are small, stable, and mergeable; global KG files and tracker tables are
deterministic outputs produced from those source facts plus current code.

### 2. Source vs generated classification (complete inventory)

**Authoritative source (authored by roles, merged semantically):**

| Artifact | Owner |
|----------|-------|
| `planning-mds/kg-source/nodes/**`, `bindings/**` | Architect |
| `planning-mds/kg-source/features/**` | Product Manager |
| `planning-mds/kg-source/policies/**` | Architect (security co-sign where applicable) |
| `planning-mds/kg-source/exclusions/**` | PM + Architect co-sign |
| `planning-mds/kg-source/ontology/**` (rehomed `solution-ontology.yaml`) | Architect (entity/glossary) + PM (per its embedded ownership matrix) |
| `planning-mds/features/**` (PRDs, stories, STATUS) | PM (+ architect sections) |
| `planning-mds/architecture/decisions/**`, `schemas/`, `api/`, `security/` | Architect / security |
| `engine/**`, `experience/**`, `neuron/**` | Implementers |

**Generated projections (compiled; committed on every branch; integrator-written on mainline):**

| Output | Produced by |
|--------|-------------|
| `planning-mds/knowledge-graph/canonical-nodes.yaml` | `compile.py` (Phase B) |
| `planning-mds/knowledge-graph/feature-mappings.yaml` | `compile.py` (Phase B) |
| `planning-mds/knowledge-graph/code-index.yaml` | `compile.py` (Phase B) |
| `planning-mds/knowledge-graph/symbol-index.yaml` | `scripts/kg/symbols.py` |
| `planning-mds/knowledge-graph/unbound-but-referenced.yaml` | `scripts/kg/symbols.py` |
| `planning-mds/knowledge-graph/coverage-report.yaml` | `validate.py --write-coverage-report` |
| `planning-mds/knowledge-graph/decisions-index.yaml` | `scripts/kg/decisions.py` |
| `planning-mds/features/STORY-INDEX.md` | `generate-story-index.py` |
| `planning-mds/features/REGISTRY.md` / `ROADMAP.md` **feature tables** | tracker generator (Phase B, S0007) |

Notes:
- `decisions-index.yaml` and `solution-ontology.yaml` were unclassified in every earlier draft of
  this design; they are classified above and must appear in all tooling file lists.
- REGISTRY/ROADMAP are *partially* generated: the feature tables are projections; surrounding
  prose (purpose, rules, notes) stays authored. The generator owns only the fenced table regions —
  so in `generated_paths.yaml` (S0008) they carry a `fenced-region` granularity marker (vs
  `whole-file` for every other output), which excludes them from the `.gitattributes` merge driver
  and scopes their reproducibility check to the fenced regions.
- During Phase A (pre-compiler), the curated trio (`canonical-nodes`, `feature-mappings`,
  `code-index`) is still source-authored — merged via `merge3.py`, not regenerated.

### 3. `kg-source/` layout and shard schema (Phase B)

```
planning-mds/kg-source/
  nodes/
    entities/service-case.yaml
    capabilities/claims-service-case-tracking.yaml
    workflows/claim-intake.yaml
    endpoints/service-cases.yaml
  features/
    F0024-claims-and-service-case-tracking.yaml
  bindings/
    claims-service-case-tracking.yaml
  policies/
    authorization-rules.yaml
  exclusions/
    feature-coverage-exclusions.yaml
  ontology/
    solution-ontology.yaml
```

One logical concept (or one tightly scoped bundle) per file — independent PRs touch disjoint files.

Example node shard:

```yaml
id: capability:claims-service-case-tracking
kind: capability
name: Claims and service case tracking
aliases:
  - service case tracking
source_docs:
  - F0024/README.md          # logical ref — resolved via the feature shard's path
governed_by:
  - adr:030
uses_schema:
  - schema:service-case
```

Example feature shard (the **single home** for every fact the REGISTRY/ROADMAP tables project — not
just path/status/dependencies but display name, phase, roadmap section, rationale, gates,
supersession, and dates; each tracker cell becomes a projection from here, so the `depends_on`
previously duplicated in ROADMAP is now one authored place):

```yaml
id: feature:F0024
name: Claims and service case tracking       # REGISTRY / ROADMAP display name
path: planning-mds/features/F0024-claims-and-service-case-tracking
status: in-progress          # → archived-done flips this AND the path, nothing else
phase: Brokerage Platform Expansion
roadmap_section: now         # now | next | later | completed | abandoned
rationale: >-                # ROADMAP "Why Now" / "Why Next" cell
  Claims handling is the next core workflow after policy issuance.
validation_gate: >-          # ROADMAP gate / entry-criteria cell
  Adjuster can open, triage, and resolve a service case end to end.
affects:
  - capability:claims-service-case-tracking
depends_on:
  - feature:F0021
# retirement/archive fields appear only when they apply:
#   superseded_by: feature:F0099    retired_date: 2026-07-04    reason: "…"
#   archived_date: 2026-08-01
```

Every presentation field above lives in the current REGISTRY/ROADMAP tables and in **no** KG file;
S0004 defines them, S0006's decompiler populates them from the tables at migration, and S0007's
generator renders them back — the round trip is what proves nothing was lost.

Example binding shard:

```yaml
id: capability:claims-service-case-tracking
paths:
  backend:
    - engine/src/Nebula.Api/Claims/**
  tests:
    - engine/tests/Nebula.Tests/Claims/**
```

Every shard must carry `id`, `kind` (or be typed by directory), and resolve to exactly one owner
role via its directory.

### 4. ID strategy

- Deterministic **semantic IDs** for domain concepts: `feature:F0024`,
  `capability:claims-service-case-tracking`, `entity:service-case`, `workflow:claim-intake`,
  `endpoint:service-cases-create`, `schema:service-case`, `adr:030`.
- **No sequence numbers** as primary IDs (they collide across parallel contributors) — the sole
  exception is the existing `F####` feature numbering, which REGISTRY governs centrally.
- **No random GUIDs** for semantic concepts (they hide duplicates). UUIDs only for append-only
  events: evidence runs, review events, approvals, telemetry.

### 5. Logical feature-doc references (absorbs F0005)

Source shards reference feature docs as `F####/relative-path` (`F0024/README.md`). The compiler
resolves the prefix through the feature shard's `path:`. Archiving a feature changes **one line**
(the feature shard's `path:`, plus `status:`); every doc ref stays valid with no repoint. The
compiler emits resolved-or-logical form into projections as consumers require; `validate.py`
fails loudly on unresolvable refs (unknown feature, unmapped, missing file). Stable-root refs
(`schemas/`, `architecture/`, `security/`, `api/`) remain physical, untouched. F0005's
dual-format resolver, migration, and enforcement stories are delivered inside S0005/S0006/S0008.

### 6. Deterministic compiler — `scripts/kg/compile.py` (Phase B)

1. Read `planning-mds/kg-source/**`.
2. Resolve logical feature refs; validate IDs and references; detect duplicate semantic IDs;
   detect alias/name near-duplicates above a configurable similarity threshold (advisory on PR,
   blocking at integration with recorded suppression + rationale); detect binding-glob overlaps
   across capabilities (a deterministic semantic-duplication signal).
3. Emit `canonical-nodes.yaml`, `feature-mappings.yaml`, `code-index.yaml` through **one canonical
   serializer** (stable key order, stable list order, stable indent/width, comments via generated
   section banners only).
4. Drive existing generators: `symbols.py`, `decisions.py`,
   `validate.py --write-coverage-report`, `generate-story-index.py`, tracker tables (S0007).

Determinism rules: identical sources → byte-identical outputs; no timestamps in committed outputs
(timestamps live in CI artifacts and evidence runs); double-compile in CI proves it.

### 7. Three-way semantic merge — `scripts/kg/merge3.py` (Phase A, kept in Phase B for shards)

Inputs: base (merge-base), ours, theirs versions of a KG YAML file (Phase A: the monolithic curated
trio; Phase B: any conflicting source shard). Internal model: records keyed by semantic ID.

Per-record rules:

| Situation | Result |
|-----------|--------|
| Added on one side | keep |
| Added on both sides, identical after canonicalization | converge (this alone dissolves the PR #47 re-serialization hunks) |
| Added on both sides, different fields | `DivergentInsert` conflict |
| Changed on one side | keep the change |
| Changed identically on both | converge |
| Changed differently | recurse to **field level** |
| Deleted on one side, unchanged on the other | delete |
| Deleted vs updated | `DeleteVsUpdate` conflict |

Per-field rules (inside a doubly-changed record):

| Field type | Rule |
|-----------|------|
| Scalar changed differently | `DivergentUpdate` conflict |
| List (default) | set union, deterministically sorted |
| List (order-significant, per-field registry e.g. workflow steps) | conflict unless one side unchanged |
| Mapping | recurse per key |

Graph-level checks on the merged result (before writing anything):

| Check | Conflict kind |
|-------|---------------|
| Binding/edge references a node the other side deleted | `OrphanEdge` |
| Duplicate ID or duplicate unique alias | `UniqueViolation` |
| Alias/name fingerprint overlap across different IDs | `SemanticDuplicateWarning` (advisory PR / blocking integration) |
| `validate.py` fails on the merged graph | `ConstraintViolation` |

Output: either the canonically serialized merged file(s) **or** a structured conflict report
(kind, record ID, field, both values, owning role) — never a partial write, never conflict markers.
Generated files are **never merge inputs**.

### 8. Git policy (user-decided; supersedes earlier drafts)

- **Generated projections are committed on every branch.** Branches stay self-contained: agents
  and humans read committed graph state without running tooling; PR diffs show the projected
  effect of shard changes.
- **Invariant instead of prohibition:** CI verifies `compile(source) == committed output` on every
  PR (the reproducibility check). Hand-edits to generated files fail this check with instructions
  (unless the commit is an integrator run or carries an explicit maintainer override).
- **Merge-time regeneration is unconditional.** A textually clean git merge of generated files is
  *more* dangerous than a conflicting one — git's line-union of two projections is not the compile
  of merged sources. The integrator always discards both sides and recompiles.
- `.gitattributes`: **whole-file** generated paths get `linguist-generated` (collapse PR diffs) and
  a merge driver (`merge=ours` or equivalent) so textual conflicts on them never block anyone — the
  recompile overwrites the result regardless. The two **partially-generated** trackers
  (`REGISTRY.md`/`ROADMAP.md`) are excluded from both `linguist-generated` and the merge driver:
  only their fenced table regions are recompiled, and their surrounding PM-authored prose remains a
  visible, ordinary text diff that routes to the PM (S0002/S0007).
- **Integration never targets `main` directly** (maintainer decision, 2026-07-05). Integrator
  merges land on a designated **integration branch**: for the Phase-A train, the existing
  `chore/merge-PRs` (the de facto mainline — `main` is stale and is not a valid merge base).
  `main` receives only the maintainer's single promotion merge after the train completes. In
  steady state the integrator **creates a dedicated integration branch per train** instead of
  reusing a maintainer branch; the same promotion rule applies.
- Never git-union KG YAML. Never edit old evidence runs (append-only; supersede with a new run).

### 9. Integrator role (replaces merge queue + bot account)

A dedicated agent in `nebula-agents`, run **serially by the maintainer** at merge time —
serialization comes from one maintainer running one agent at a time, which is what a merge queue
would otherwise provide. Sole writer of generated graph/tracker files on the mainline.

**Precondition (human gate 1):** the branch's feature carries a passing `feature-review` verdict
(done-review), or the maintainer records an explicit waiver with rationale in the run inputs. The
integrator verifies the verdict/waiver reference and halts without it — it never performs the
review itself.

**Integration target:** every run lands on the designated integration branch, never directly on
`main` (see git policy §8) — `chore/merge-PRs` for the Phase-A train; a dedicated
integrator-created branch per train in steady state. `main` only ever receives the maintainer's
promotion merge.

Duties, per integration run:
1. Determine merge base; merge code and source-authored files (git for code; `merge3.py` for KG
   sources and tracker rows).
2. Verify the branch's own reproducibility (committed projection == compile of branch sources);
   if it fails, **bounce to the contributor** — the integrator does not fix contributor branches.
3. Recompile projections and regenerate all derived indexes on the merged result, unconditionally.
4. Run full validation (`validate.py`, orphan checks, tracker validators, story index zero-diff).
5. Emit an **integration evidence run** (append-only, same evidence contract as feature runs):
   inputs (branch, base, PR), merge decisions, conflict report if any, validator outputs.
6. Prepare the merge commit for the maintainer's push. The integrator never pushes to the mainline
   itself.
7. **Pause for human test validation (human gate 2):** the run stops here. The maintainer
   exercises the feature on the prepared merge worktree and records the outcome in the evidence
   run; only a recorded pass gets pushed. A failed validation is handled like a bounce — routed to
   the contributor or owning role, with any later re-run a new run.

Hard boundary: the integrator **never edits source shards or feature docs**. Any integration that
would require a source change is by definition a semantic collision and routes to the owning role:
architect for `nodes/`, `bindings/`, `policies/`, `ontology/`; PM for `features/`, trackers;
co-sign for `exclusions/`. After the owner resolves on the contributor branch (or a fixup branch),
the integrator re-runs.

### 10. Contributor flow (Phase B steady state)

1. Contributor edits code, feature docs, schemas, ADRs — and **only scoped `kg-source/` shards**.
2. Local compile keeps the branch's committed projections coherent (agents on the branch read
   committed state).
3. Local `validate.py` proves internal consistency; CI reproducibility check proves the committed
   projections match the sources.
4. PR review sees small shard diffs plus collapsed generated diffs.
5. Feature-review verdict (or recorded waiver) on the branch, integrator run at merge time
   (above), then maintainer test validation on the prepared merge before push. Independent
   features merge with zero manual *merge* steps — the only human touch points are these two
   deliberate gates.

### 11. Validation rules (enforced by compiler + `validate.py` + CI)

- No duplicate semantic IDs; no unknown references.
- No physical `planning-mds/features/...` paths in source-authored doc-reference fields.
- No hand-edited generated file (reproducibility check).
- Every feature shard `path:` exists; every logical `F####/…` ref resolves to an existing file.
- Every binding glob matches ≥ 1 file unless explicitly allowed (with rationale).
- Every alias near-collision is reviewed or suppressed with recorded rationale.
- Every shard has `id`, kind (explicit or directory-typed), and exactly one owning role.
- Every generated output is reproducible from source (double-compile, byte-identical).
- Binding-glob overlap across capabilities reported as a semantic-duplication signal.
- Archived feature ⇒ no non-archive feature-doc path anywhere in projections.

## Sequencing & Migration Plan

Ordering constraint (hard): **Phase A first.** The migration rewrites exactly the files all seven
open contributor PRs touch; migrating first would invalidate every open PR.

| Step | Content | Exit proof |
|------|---------|-----------|
| A1 (S0001, S0002) | `merge3.py` + tracker-row merge on the current monolithic graph | Replays the PR #47 resolution: re-serialization hunks converge; the known real deltas (F0038 archive repoints, `excluded_features` regression, stale `status`) surface as typed conflicts/reports |
| A2 (S0003) | Integrator role, `integrate` action, evidence contract | Dry-run integration of PR #47 produces a complete evidence run |
| A3 (operational) | Drain the queue: #47 → #51 → #50/#48/#49 → #53/#54 | 7 merged PRs, 9 integration evidence runs (more runs than PRs — dry-runs, halts, and re-runs each leave an append-only run) — each merge recording a feature-review verdict/waiver and a maintainer test-validation pass — mainline green |
| B1 (S0004) | Shard schema + ownership spec; source/generated classification | Spec reviewed; every generated path classified (reproducibility enforcement deferred to B5) |
| B2 (S0005) | `compile.py` + logical refs (F0005 absorbed) | Deterministic double-compile; resolver test matrix green |
| B3 (S0006) | Decompiler: explode current graph **and REGISTRY/ROADMAP feature tables** → shards; round-trip proof | `compile(decompile(graph))` byte-identical; feature shards carry the tracker presentation fields (name/phase/section/rationale/gate/dates), schema-valid and count-reconciled; shards become truth; monolith becomes output |
| B4 (S0007) | Tracker generation (REGISTRY/ROADMAP tables) | `compile(decompile(trackers)) == trackers` byte-identical from the S0006-populated shards (closes the tracker round trip) |
| B5 (S0008) | Stand up reproducibility CI (warn-only shake-out → **blocking** post-cutover); hand-edit guard; `.gitattributes` | CI red on synthetic hand-edit; green on compliant PR |
| B6 (S0009) | Contract/docs/templates reconciliation | No doc describes an off-book step; F0005 gap closed in prose |

Rollback: Phase A tools are additive (no data change) — rollback is "stop using them." Phase B has
two tagged, individually-revertable rewrites: **B3** (graph + feature-table fields → shards; graph
round-trip proof) and **B4** (REGISTRY/ROADMAP feature tables → generated regions; tracker
round-trip proof). A pre-migration tag plus each step's byte-identical proof makes rollback of
either a single revert.

## Role-Based Ownership

| Role | Responsibility |
|------|----------------|
| Architect | Authors `nodes/`, `bindings/`, `policies/`, `ontology/` shards (G7); owns merge semantics for those kinds; resolves architect-routed conflicts |
| Product Manager | Authors `features/` shards (path/status/depends_on + tracker presentation fields: name/phase/section/rationale/gate/dates — the single home); owns tracker prose; resolves PM-routed conflicts; archive = one shard edit |
| **Integrator (new)** | Runs integration: semantic merge, unconditional recompile, validation, evidence; sole writer of generated files on mainline; never authors sources (mechanical merge3/tracker convergence only; never writes feature docs or `kg-source/` shards); verifies the feature-review gate before running and pauses for maintainer test validation before push |
| Maintainer (human) | Runs the integrator serially; owns both human gates (feature-review waivers, test validation of the prepared merge); pushes the prepared merge; owns overrides |
| Quality Engineer / Code Reviewer | Signoff on tools (merge determinism, round-trip, CI guards) |
| DevOps | CI reproducibility workflow, `.gitattributes`, branch protections |

## Framework Edit Inventory (`nebula-agents`)

| Surface | Change |
|---------|--------|
| `agents/integrator/SKILL.md` | **New** persona: duties 1–6, hard boundary, routing table, evidence contract |
| `agents/agent-map.yaml` | Register `integrator` (reads: everything; writes: `{PRODUCT_ROOT}/planning-mds/knowledge-graph/**` generated outputs, tracker table regions, integration evidence dir — mainline context only). Phase B: add `kg-source/` write scopes to architect (`nodes/`,`bindings/`,`policies/`,`ontology/`) and PM (`features/`); **remove every direct write scope to a now-generated file, symmetrically** — PM's `feature-mappings.yaml` **and** the architect's `canonical-nodes.yaml`/`feature-mappings.yaml`/`code-index.yaml` (all three become `compile.py` outputs); **relocate** the architect's `solution-ontology.yaml` scope to `kg-source/ontology/**` (rehome, not removal). `coverage-report.yaml` stays (a `--write-coverage-report` regeneration, not a hand-edit). Flip the integrator's Phase-A scope annotations — the curated trio ("via merge3 only") and REGISTRY/ROADMAP ("via tracker merge only") — to the Phase-B reality ("regenerated via `compile.py`"). After this, no `knowledge-graph/*.yaml` appears in any authoring role's write scope; only the integrator's generated-output scope (mainline) and the compiler (branches) produce them |
| `agents/actions/integrate.md` | **New** action: the integration run procedure, inputs, gates (feature-review precondition, human-test-validation pause), bounce rules |
| `agents/actions/README.md`, `agents/ROUTER.md` | Route/announce the new action |
| `agents/actions/feature.md` | G7: architect authors shards (logical refs only); G8: archive = feature-shard `path:`/`status:` edit + recompile — delete the off-book repoint narrative |
| `agents/actions/build.md`, `agents/actions/plan.md` | Phase B: the 2026-07-05 "Enforce generated KG regeneration" gate commands (`--regenerate-symbols`/`--regenerate-decisions`/`--write-coverage-report`) switch to the `compile.py`-driven flow; authored-file wording (canonical-nodes/code-index) reconciled to shards |
| `agents/templates/prompts/evidence-contract/feature-operator-friendly.md` | Same reconciliation (the "code paths only, stable across archive" claim becomes true) |
| `agents/templates/prompts/evidence-contract/feature-automation-safe.md`, `build-automation-safe.md`, `build-operator-friendly.md`, `plan-automation-safe.md`, `plan-operator-friendly.md` | Same reconciliation — these carry the same 2026-07-05 KG-regeneration enforcement lines and Phase-A authored-file instructions |
| `agents/product-manager/scripts/validate-feature-evidence.py` (+ its tests) | Phase B: the generated-KG regeneration command matchers must accept the `compile.py` flow (today they match only `validate.py --regenerate-*` / `symbols.py` / `decisions.py`); gate the change on a new `contract_effective_date`, as the 2026-07-05 rule did |
| `agents/templates/prompts/evidence-contract/integrate-operator-friendly.md` | **New** operator prompt for integration runs |
| `agents/docs/KNOWLEDGE-GRAPH.md` | Source/generated classification, shard schema, compile flow, logical refs, merge taxonomy |
| `agents/docs/ORCHESTRATION-CONTRACT.md` | Integrator role, mainline generated-file ownership, conflict routing |
| `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md` | Maintainer procedure: verify feature-review verdict (or record waiver), run integrator, review evidence, test-validate the prepared merge, record the outcome, push |
| `agents/templates/kg-reconciliation-template.md` | Shard-based reconciliation + logical-ref examples |
| `agents/templates/feature-assembly-plan-template.md` | KG step points at shards, not monoliths |
| `agents/templates/tracker-governance-template.md`, `feature-registry-template.md` | Mark generated table regions; sync rules reference the generator |
| `agents/templates/ci-gates-template.yml` | Reproducibility-check job template |
| **New template**: `integration-evidence-template.md` (or extend `evidence-manifest-template.json`) | Integration evidence run format |

## Product-Repo Edit Inventory (reference: `nebula-insurance-crm`)

| Surface | Change |
|---------|--------|
| `scripts/kg/merge3.py` | **New** (Phase A): three-way semantic merge + conflict report |
| `scripts/kg/kg_common.py` | Canonical serializer; logical-ref resolver (`resolve_doc_ref`) |
| `scripts/kg/compile.py` | **New** (Phase B): shard→projection compiler + generator driver |
| `scripts/kg/decompile.py` | **New** (Phase B, migration-only): graph **and REGISTRY/ROADMAP feature-table** → shards exploder (populates feature-shard presentation fields via the S0004 column↔field mapping) with `--check` dry-run |
| `scripts/kg/validate.py` | Reproducibility mode (`--check-reproducible`); logical-ref resolution at existence/coverage call sites; new rules (physical-path ban, alias-collision ledger, glob-overlap, archived⇒no-stale-path) |
| `scripts/kg/lookup.py`, `eval.py` | Resolve logical refs for display/aggregation (F0005 call sites) |
| `scripts/kg/decisions.py`, `symbols.py`, `generate-story-index.py` | Invoked by compiler/integrator; unchanged semantics, listed as generated-output producers |
| `planning-mds/kg-source/**` | **New** source layer (Phase B migration) |
| `planning-mds/knowledge-graph/*` | Becomes fully generated (Phase B); `solution-ontology.yaml` rehomed to `kg-source/ontology/` |
| `planning-mds/features/REGISTRY.md`, `ROADMAP.md` | Feature tables become generated regions (Phase B) |
| `scripts/kg/generated_paths.yaml` | **New** (Phase B, S0008): single authoritative list of every generated path, each with a `whole-file`/`fenced-region` granularity marker (content per §2); consumed by CI, `.gitattributes` generation, and the integrator |
| `.gitattributes` | `linguist-generated` + merge driver on `whole-file` generated paths only (generated from `generated_paths.yaml`, never hand-listed); the `fenced-region` trackers get neither because GitHub Linguist and merge drivers are file-scoped |
| `.github/workflows/` | Reproducibility check — stood up at B5 (S0008); warn-only shake-out, then blocking post-cutover |
| `CONTRIBUTING.md` / contributor docs | Shard-authoring flow; "never edit `knowledge-graph/*` by hand" |

## Risks & Assumptions

- **Risk:** Phase A merge tool mis-merges the very PRs it exists to unblock.
  **Mitigation:** A1 exit proof replays the already-hand-reviewed PR #47 resolution and must
  reproduce its known outcomes; the integrator's validator gate is a second net; evidence runs make
  every decision auditable.
- **Risk:** Canonical serialization pass rewrites the curated files once (a "big diff" commit).
  **Mitigation:** Do it as a dedicated no-semantic-change commit (verified by ID-level diff), before
  the train, so subsequent merges are noise-free.
- **Risk:** Order-significant list fields silently set-unioned.
  **Mitigation:** explicit per-field policy registry; unknown fields default to conflict, not union.
- **Risk:** Integrator becomes a bottleneck (serial by design).
  **Mitigation:** acceptable at current scale (single maintainer); the compiled-projection design
  keeps each run minutes-long; revisit queueing only if contributor volume demands it.
- **Risk:** Two features legitimately need the same new node ID concurrently (`DivergentInsert`).
  **Mitigation:** that is a *real* collision; the taxonomy routes it to the architect — this is the
  system working, not failing.
- **Risk:** Tracker generation (S0007) fights hand-edits during transition.
  **Mitigation:** generator owns only fenced table regions; cutover compares generated vs
  hand-maintained state and reconciles once.
- **Assumption:** `F####` central numbering via REGISTRY remains the one sanctioned sequence
  (contributors reserve IDs before branching).
- **Assumption:** Current archive convention (folder prefix moves, relative paths stable) holds —
  same assumption F0005 validated.
- **Assumption:** Python + PyYAML/ruamel available wherever integration runs (already true for the
  existing `scripts/kg/` toolchain).

## Dependencies

- Evidence-run contract and gate model (`agents/actions/feature.md`, evidence templates) — the
  integration evidence run reuses them.
- Product-repo KG toolchain: `scripts/kg/{validate,symbols,decisions,lookup,eval}.py`,
  `generate-story-index.py`, `kg_common.py`.
- A green reference graph as the migration baseline (`nebula-insurance-crm`, post-merge-train).
- REGISTRY feature-ID allocation discipline (central `F####` reservation).
- Supersedes **F0005**; its four stories map into S0005 (resolver), S0006 (migration),
  S0008 (enforcement), S0009 (contract reconciliation).

## Related Stories

- [F0006-S0001](./F0006-S0001-three-way-semantic-kg-merge.md) - Three-way semantic KG merge tool (`merge3.py`)
- [F0006-S0002](./F0006-S0002-tracker-table-three-way-merge.md) - Tracker-table three-way merge (REGISTRY/ROADMAP rows)
- [F0006-S0003](./F0006-S0003-integrator-role-and-integrate-action.md) - Integrator role and `integrate` action
- [F0006-S0004](./F0006-S0004-kg-source-shard-schema-and-ownership.md) - `kg-source/` shard schema, layout, and ownership
- [F0006-S0005](./F0006-S0005-deterministic-kg-compiler.md) - Deterministic KG compiler with logical doc refs
- [F0006-S0006](./F0006-S0006-decompiler-first-migration.md) - Decompiler-first migration with round-trip proof
- [F0006-S0007](./F0006-S0007-tracker-generation-from-shards.md) - Tracker generation from feature shards
- [F0006-S0008](./F0006-S0008-reproducibility-ci-and-git-policy.md) - Reproducibility CI, enforcement, and git policy
- [F0006-S0009](./F0006-S0009-framework-contract-reconciliation.md) - Framework contract, roles, and docs reconciliation

## Rollout & Enablement

- Phase A ships first and is exercised immediately: the 7-PR merge train in `nebula-insurance-crm`
  is the integrator's shakedown cruise. Pre-compiler, its "recompile" step means: regenerate the
  four derived files + `merge3.py` the curated trio + tracker rows. Every train car passes the two
  human gates: feature-review before its run, maintainer test validation before its push.
- Phase B lands behind the round-trip proof; the reproducibility check is stood up at B5 (S0008) —
  warn-only for a shake-out window, then blocking — with the integrator's per-run recompile + bounce
  (S0003) covering the pre-CI window.
- Other product repos adopt by applying B1–B5 with the same scripts; each adoption is tracked in
  that repo, not in this feature.
- The compiled-projection spec (this PRD §§1–11) is the durable contract; if contributor volume
  later outgrows the serial integrator, revisit dedicated infrastructure (including a re-evaluation
  of OmniGraph) as a separate feature.

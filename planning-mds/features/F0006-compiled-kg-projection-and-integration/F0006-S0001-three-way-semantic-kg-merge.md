# F0006-S0001 - Three-Way Semantic KG Merge Tool (`merge3.py`)

## Story Header

**Story ID:** F0006-S0001
**Feature:** F0006 - Compiled Knowledge-Graph Projection and Governed Integration
**Title:** Three-way semantic KG merge tool (`merge3.py`)
**Priority:** Critical
**Phase:** Platform Hardening (Feature Phase A)

## User Story

**As a** maintainer integrating a contributor branch whose fork point predates mainline KG changes
**I want** a tool that merges base/ours/theirs versions of the curated KG YAML by semantic record ID, with typed conflicts and canonical output
**So that** re-serialization noise converges to zero conflicts, independent additions merge automatically, and only real semantic collisions need a human role's decision — never line-level YAML conflict markers.

## Context & Background

PR #47 demonstrated the failure mode: contributor tooling re-dumped `canonical-nodes.yaml` and
`feature-mappings.yaml` (different list indent, comments stripped, `§` → `\xA7`), so git saw the
*same 548-node graph* as hundreds of conflicting lines. The PR side was a strict superset only
because it was the first merge from the shared fork point — the six PRs behind it (#48–#51, plus
#53/#54 which joined 2026-07-04) need genuine delta replay against a moved mainline.

The design adapts OmniGraph's three-way, row-level branch merge (typed conflict taxonomy, merge
checked against constraints, all-or-nothing publish) as a few hundred lines of Python over YAML
records. Crucially, this story targets the **current monolithic** files — it keys on semantic IDs,
not lines or files — so it unblocks the 7-PR merge train before any shard migration exists. In
Phase B the same tool merges individual source shards on the rare occasions they conflict.

Includes a prerequisite: a **canonical serializer** in `kg_common.py` (stable key order, list
order, indent) plus a one-time canonicalization commit of the curated files, verified semantically
unchanged by ID-level diff, so post-canonicalization merges are formatting-noise-free.

## Acceptance Criteria

**Happy Path (convergence):**
- **Given** base, ours, and theirs versions of `canonical-nodes.yaml` where theirs is a
  re-serialization of base plus new F0021 nodes, and ours is base plus F0038 changes
- **When** `merge3.py --base B --ours O --theirs T canonical-nodes.yaml` runs
- **Then** the output contains every node exactly once, F0021 and F0038 changes both present,
  serialized canonically, and the exit code is 0 with zero conflicts.

**Happy Path (typed conflict):**
- **Given** ours and theirs both modify the same scalar field of the same node to different values
- **When** the merge runs
- **Then** no output file is written, exit code is non-zero, and the conflict report names the
  record ID, field, both values, kind `DivergentUpdate`, and the owning role for the record's kind.

**Alternative Flows / Edge Cases:**
- Same record added on both sides with identical canonical content → converges silently.
- Same record added with different fields → `DivergentInsert`.
- Record deleted on one side, updated on the other → `DeleteVsUpdate`.
- List fields default to set-union with deterministic sort; fields in the ordered-list registry
  conflict instead unless one side is unchanged.
- Unknown/unregistered field types default to **conflict**, never silent union.
- Merged result re-validated before write: binding referencing a node the other side deleted →
  `OrphanEdge`; duplicate ID/unique alias → `UniqueViolation`; `validate.py` failure on the merged
  graph → `ConstraintViolation`. Any of these blocks the write (all-or-nothing).
- Alias/name similarity across *different* IDs → `SemanticDuplicateWarning` (non-blocking in this
  story; the integrator decides per S0003 policy).
- Generated files passed as input → hard error ("generated files are never merge inputs").
- Report available as human-readable text and structured JSON (for the integration evidence run).

## Interaction Contract

N/A — CLI tool; no interactive surface.

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| `scripts/kg/merge3.py` | Run with base/ours/theirs refs or files | Target KG file (only on full success) | Canonically merged file, or no write + conflict report | Re-run on same inputs yields byte-identical result | Maintainer / integrator / CI |

## Data Requirements

**Inputs:** three versions (git refs or file paths) of one curated KG file; the per-field policy
registry (ordered lists, unique fields); repo checkout for merged-result validation.
**Outputs:** merged canonical YAML (exclusive-or) a conflict report
`{kind, record_id, field?, ours, theirs, owning_role, message}` in text + JSON.

**Validation Rules:**
- Record identity = the file's semantic ID field (`id:` for nodes/features/bindings).
- Canonicalization is idempotent: `canonicalize(canonicalize(x)) == canonicalize(x)`.
- Exit codes distinguish clean-merge / conflicts / usage-error for scripting.
- No partial writes under any failure mode.

## Role-Based Visibility

**Roles that can run this tool / act on its output:**
- Maintainer / integrator — runs `merge3.py`; consumes the merged file or the typed conflict report.
- Architect — owns and resolves conflicts routed for node/binding/policy/ontology kinds.
- Product Manager — owns and resolves conflicts routed for feature/tracker kinds.
- CI — runs the tool non-interactively (exit codes drive the pipeline).

**Data Visibility:** N/A — local planning-doc tooling over committed KG YAML; no server-side auth
surface and no internal/external data exposure (matches the Security Reviewer "No" rationale in the
feature `STATUS.md`).

## Dependencies

**Depends On:** none (first story; operates on current monolithic graph).
**Related Stories:** F0006-S0002 (tracker rows use the same engine), F0006-S0003 (integrator calls
this tool), F0006-S0005 (canonical serializer shared with the compiler).

## Business Rules

1. Identical content in different formatting is **not** a conflict — canonicalize before compare.
2. All-or-nothing: a single unresolved conflict blocks the entire file's output.
3. Every conflict names its owning role (architect: node/binding/policy/ontology kinds; PM:
   feature kinds) — routing is data, not tribal knowledge.
4. The tool never resolves a real semantic conflict heuristically; it only converges provable
   equivalences and one-sided changes.

## Out of Scope

- Tracker markdown tables (S0002). Integration procedure and evidence (S0003).
- Source shards and compiler (Phase B). Code merges (plain git).

## Non-Functional Expectations

- Performance: full 548-node graph merge in seconds; no network I/O.
- Determinism: identical inputs → byte-identical output across runs and machines.

## Questions & Assumptions

**Open Questions:**
- [x] ruamel.yaml (comment-preserving) vs PyYAML + generated section banners for the canonical
      form. **Decided: PyYAML + generated banners** — comments in *generated* projections should
      themselves be generated, and Phase B makes the files fully generated anyway. Shipped
      `kg_common.py` uses `yaml` with no ruamel dependency.

**Assumptions (to be validated):**
- Every record in the curated trio has a unique `id` (PR #47 review observed this; the tool must
  verify and fail loudly if not).

## Definition of Done

- [x] Acceptance criteria met, including the PR #47 replay: re-serialization hunks converge; the
      known real deltas (F0038 archive repoints, `excluded_features` regression, stale `status`)
      surface as typed items
- [x] Canonical serializer landed in `kg_common.py`; one-time canonicalization commit made with
      ID-level-diff proof of semantic no-change
- [x] Unit tests: converge-identical, one-sided, field-recurse, ordered-list conflict,
      delete-vs-update, orphan-edge, unique-violation, all-or-nothing, idempotent canonicalization
- [x] JSON conflict report consumed successfully by a sample evidence-run manifest
- [x] Documentation in the product repo's `scripts/kg/` README
- [x] Story filename matches `Story ID` prefix
- [x] Story index regenerated or updated

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

# F0006-S0006 - Decompiler-First Migration with Round-Trip Proof

## Story Header

**Story ID:** F0006-S0006
**Feature:** F0006 - Compiled Knowledge-Graph Projection and Governed Integration
**Title:** Decompiler-first migration with round-trip proof
**Priority:** Critical
**Phase:** Platform Hardening (Feature Phase B)

## User Story

**As a** framework maintainer cutting the reference graph over to the shard model
**I want** a mechanical decompiler that explodes the current monolithic graph **and the REGISTRY/ROADMAP feature tables** into `kg-source/` shards, with proof that compiling those shards reproduces the pre-migration graph byte-identically
**So that** the migration cannot silently lose or alter graph semantics, requires no hand-transcription of ~550 nodes **or of every feature's tracker fields**, and is a single revert away from rollback.

## Context & Background

The safe migration direction is decompile-first (review amendment #2): rather than hand-authoring
shards and hoping they compile to something equivalent, `decompile.py` mechanically partitions the
existing (already canonicalized, post-merge-train) `canonical-nodes.yaml`,
`feature-mappings.yaml`, `code-index.yaml`, plus `solution-ontology.yaml` into per-concept shards —
rewriting physical feature-doc refs to logical `F####/...` form (absorbing F0005-S0002's migration)
— and the cutover gate is `compile(decompile(graph)) == graph`.

The decompiler also partitions the **REGISTRY.md and ROADMAP.md feature tables** into each feature
shard's presentation fields (`name`, `phase`, roadmap section, `Why Now`/`Why Next` rationale,
validation/entry gate, supersession, retirement/archive dates — the S0004 tracker-field set), using
the same column↔field mapping S0007's generator renders with. This is why the migration is
decompile-first for trackers too: those fields exist today only in the hand-maintained tables and in
no KG file, so hand-authoring them into ~40 feature shards would be exactly the error-prone
transcription this story exists to avoid. Ordering note: the graph round trip
(`compile(decompile(graph)) == graph`) is proven **here** (the compiler exists from S0005); the
**byte-identical tracker round trip closes at S0007** when the tracker generator lands. S0006
populates and schema-validates the presentation fields (completeness + count reconciliation);
S0007 proves they render back to the original tables.

Hard precondition: **the merge train is complete** (Phase A exit — 7 PRs as of 2026-07-05, plus
any that arrive before the train finishes). The migration rewrites exactly the files every open PR
touches; migrating with open contributor PRs invalidates them all.

## Acceptance Criteria

**Happy Path:**
- **Given** the post-train, canonicalized reference graph (validators green)
- **When** `decompile.py` runs, then `compile.py` runs on its output
- **Then** the compiled projections are byte-identical to the pre-migration files, every shard
  passes S0004 validation, `validate.py` stays green across the migration, and the reproducibility
  check (`validate.py --check-reproducible`) is green on the compiled result.

**Logical-ref migration:**
- **Given** a canonical node with physical refs into a live feature folder and an archived one
- **When** decompilation rewrites doc refs
- **Then** both become `F####/rel-path` form, resolving (per S0005) to the same physical files as
  before — including the F0038 archive paths that previously needed hand-repointing.

**Tracker-field migration:**
- **Given** the current REGISTRY.md / ROADMAP.md feature tables
- **When** `decompile.py` partitions them (using the S0004 column↔field mapping)
- **Then** every feature shard carries the presentation fields its REGISTRY status table and ROADMAP
  section require (`name`, `phase`, section, rationale, gate, supersession, dates), each shard passes
  S0004 completeness validation, and REGISTRY-row / ROADMAP-section counts reconcile exactly (nothing
  dropped, nothing invented). The byte-identical re-render is S0007's gate; here the gate is
  **populated + schema-valid + count-reconciled**.

**Alternative Flows / Edge Cases:**
- `--check` dry-run reports the intended shard partition and ref rewrites without writing.
- Idempotency: decompiling twice produces identical shards.
- Unpartitionable content (node kind with no directory home, orphan mapping entry, ref to a
  feature absent from mappings, a tracker row whose feature has no shard, or a feature with no
  tracker row/section) → loud failure listing every instance; nothing written. Resolve by fixing
  the source graph/tracker first (pre-existing drift is fixed at the source, not papered over in
  shards).
- Stable-root refs are not rewritten (byte-preserved through the round trip).
- `solution-ontology.yaml` moves to `kg-source/ontology/` content-identical (home change only).
- Cutover mechanics: one migration commit (tagged) containing shards + unchanged projections +
  the switch of authoring truth; rollback = revert that commit.

## Interaction Contract

N/A — migration CLI; no interactive surface.

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| `scripts/kg/decompile.py` | Run (`--check` first) | `planning-mds/kg-source/**` (new files only) | Shard tree, or dry-run report, or loud failure with no writes | Idempotent re-run; round-trip diff empty | Maintainer, once per repo; kept for future repo adoptions |

## Data Requirements

**Inputs:** the four curated/monolithic files; feature-mappings for ref rewriting; the
**REGISTRY.md + ROADMAP.md feature tables** for feature-shard presentation fields; the S0004 schema
and its tracker column↔field mapping.
**Outputs:** populated `kg-source/**` (feature shards carry both technical **and** presentation
fields); migration report (shard count per directory, refs rewritten, tracker fields mapped per
feature, anomalies).

**Validation Rules:**
- Round-trip byte-identity is the cutover gate **for the KG files here**; for REGISTRY/ROADMAP it is
  proven at S0007 (the generator) — S0006 gates on presentation-field completeness + count
  reconciliation.
- Every emitted shard passes S0004 validation (technical **and** presentation fields).
- Node/mapping/binding **and REGISTRY-row / ROADMAP-section** counts reconcile exactly (nothing
  dropped, nothing invented).

## Role-Based Visibility

**Roles that can run this migration tool:**
- Maintainer — runs `decompile.py` once per repo at cutover (and retains it for future repo adoptions).
- Architect / PM — review the emitted shards for their owned directories before cutover.
- No contributor/agent runs it in the normal flow (migration-only tool).

**Data Visibility:** N/A — one-time local migration over committed KG/tracker files; no auth surface
and no internal/external data exposure.

## Dependencies

**Depends On:** F0006-S0004 (shard contract), F0006-S0005 (compiler + `--check`), Phase A complete
(merge train landed — hard precondition).
**Related Stories:** F0006-S0007 (tracker generator closes the byte-identical tracker round trip
this story sets up; both share S0004's column↔field mapping), F0006-S0008 (reproducibility check
flips blocking after this lands).

## Business Rules

1. No shard is hand-authored during migration — including feature-shard presentation fields
   decompiled from the trackers; the decompiler is the only writer.
2. Pre-existing graph drift discovered during decompilation is fixed in the monolith first (as its
   own reviewed commit), then re-decompiled — the migration never launders errors into shards.
3. After cutover, the monolithic files are generated outputs; the decompiler is retired from the
   repo's normal flow (kept for adopting other repos).

## Out of Scope

- CI enforcement flips (S0008). Tracker generation (S0007). Other product repos (each adopts
  later with the same tool).

## Non-Functional Expectations

- Full decompile + compile + diff cycle in under a minute on the reference graph.

## Questions & Assumptions

**Open Questions:**
- [ ] Shard filename convention for nodes with long IDs (proposal: the ID's kebab body, which is
      already filesystem-safe by the S0004 ID grammar).

**Assumptions (to be validated):**
- Post-canonicalization (S0001), byte-identity through the round trip is achievable because both
  decompiler and compiler share the canonical serializer.

## Definition of Done

- [x] Acceptance criteria met; graph round-trip byte-identity proven on the real graph (`compile.py --check` green post-cutover) and recorded
- [x] Tracker decompile: REGISTRY/ROADMAP feature tables partitioned into feature-shard
      presentation fields (via `tracker_merge.parse_tracker` + §4.1 mapping); count-reconciliation
      (40 = 33 + 7); anomaly failure on tracker/shard mismatch (byte-identical tracker round trip closes at S0007)
- [x] Dry-run, idempotency, anomaly-failure, and count-reconciliation tests (`test_decompile.py`, 6)
- [x] Migration executed on `nebula-insurance-crm` (tagged cutover commit `712acd6`; tags `pre-kg-cutover`→`kg-cutover`; drift-fix `0c0d0e4`)
- [x] Migration report recorded (report in commit `712acd6` + STATUS; 182 shards)
- [x] Story filename matches `Story ID` prefix
- [x] Story index regenerated or updated (S0006 → Done)

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

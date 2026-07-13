# F0006-S0005 - Deterministic KG Compiler with Logical Doc Refs

## Story Header

**Story ID:** F0006-S0005
**Feature:** F0006 - Compiled Knowledge-Graph Projection and Governed Integration
**Title:** Deterministic KG compiler with logical doc refs
**Priority:** Critical
**Phase:** Platform Hardening (Feature Phase B)

## User Story

**As a** branch owner (contributor, role agent, or integrator)
**I want** `scripts/kg/compile.py` to deterministically build every graph projection from `kg-source/` shards — resolving logical `F####/...` doc refs through feature shards — and then drive the existing generators
**So that** the committed graph is always a pure function of the sources, identical sources produce byte-identical outputs anywhere, and archiving a feature is one shard edit with zero repoints.

## Context & Background

This is the engine of the compiled-projection model, and it absorbs F0005's resolver story
(F0005-S0001): logical doc refs become the *only* doc-ref form in shards, resolved at compile time
via each feature shard's `path:`. The compiler emits the projection trio
(`canonical-nodes.yaml`, `feature-mappings.yaml`, `code-index.yaml`) through the S0001 canonical
serializer, then drives the existing downstream generators (`symbols.py`, `decisions.py`,
`validate.py --write-coverage-report`, `generate-story-index.py`, and — after S0007 — the tracker
tables), so one command rebuilds the entire generated surface.

Compile-time analysis is where semantic-duplication detection lives: duplicate IDs (hard error),
alias/name similarity above threshold (advisory on PR, blocking at integration unless suppressed
with rationale — the suppression ledger is itself a source file), and binding-glob overlap across
capabilities (deterministic duplicate signal, per review amendment).

## Acceptance Criteria

**Happy Path:**
- **Given** a valid `kg-source/` tree
- **When** `compile.py` runs twice from a clean state
- **Then** both runs produce byte-identical projections and derived outputs, containing no
  timestamps, with stable ordering throughout.

**Logical-ref resolution (F0005 acceptance):**
- **Given** a node shard referencing `F0038/README.md` and F0038's feature shard `path:` pointing
  at the archive location
- **When** compilation resolves refs
- **Then** validation confirms the file exists at the archived path, and flipping the feature
  shard between live and archive paths changes **no** shard content and keeps compilation green.

**Alternative Flows / Edge Cases:**
- Unresolvable logical ref (unknown feature, missing file after resolution, malformed
  `F####/`-prefix with empty remainder) → loud compile error naming shard, ref, and resolution
  attempt; never skipped.
- Stable-root refs (`schemas/`, `architecture/`, `security/`, `api/`) pass through physical,
  validated as-is.
- Duplicate semantic ID across shards → hard error naming both files.
- Alias similarity above threshold → report entry; blocking only in `--strict` (integration) mode
  and absent a ledger suppression.
- Binding-glob overlap across different capabilities → report entry (same advisory/strict split).
- Unknown reference (ID mentioned, no shard) → hard error.
- Partial-failure behavior: compile writes nothing unless the whole build succeeds (all-or-nothing,
  same rule as merge3).
- `--check` mode: compile to memory/temp and diff against committed projections (the
  reproducibility primitive S0008's CI uses).

## Interaction Contract

N/A — CLI tool; no interactive surface.

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| `scripts/kg/compile.py` | Run (optionally `--check` / `--strict`) | Generated projections + derived outputs only | Full rebuild or no writes + error/report | Double-run byte-identical | Any branch owner; integrator in `--strict` |

## Data Requirements

**Inputs:** `kg-source/**`, repo file tree (for glob/doc existence), suppression ledger
(`kg-source/exclusions/` or `policies/`), downstream generator scripts.
**Outputs:** the projection trio; invocation of downstream generators; machine-readable analysis
report (duplicates, similarities, overlaps).

**Validation Rules:**
- Deterministic ordering: nodes by ID; lists sorted unless field is registered order-significant.
- No committed timestamps; versions/counts derived from content only.
- Emitted comments limited to generated section banners.

## Role-Based Visibility

**Roles that can run the compiler / act on its output:**
- Any branch owner (contributor, role agent) — runs `compile.py` to keep committed projections coherent.
- Integrator — runs it in `--strict` mode at merge (analysis severities become blocking).
- Architect / PM — own the shards it reads and resolve blocking analysis findings for their kinds.
- CI — runs `--check` non-interactively.

**Data Visibility:** N/A — local build tooling over committed shards/projections; no auth surface
and no internal/external data exposure.

## Dependencies

**Depends On:** F0006-S0004 (shard contract), F0006-S0001 (canonical serializer).
**Related Stories:** F0006-S0006 (round-trip uses `--check`), F0006-S0008 (CI wraps `--check`),
F0006-S0007 (tracker generation joins the driver), F0006-S0009 (the evidence-contract matchers in
`validate-feature-evidence.py` must learn the `compile.py` flow once it becomes the sanctioned
regeneration entry point — today they match only `validate.py --regenerate-*` command strings).

## Business Rules

1. The compiler is the only sanctioned producer of the projection trio after cutover.
2. Analysis severity is mode-dependent: advisory on contributor branches, blocking at integration
   (`--strict`), always suppressible only via the recorded ledger with rationale.
3. Existing generator semantics are reused, not reimplemented — `compile.py` orchestrates them.

## Out of Scope

- Populating shards from the current graph (S0006). CI wiring (S0008). Tracker-table rendering
  (S0007). Any change to `symbols.py`/`decisions.py` internals.

## Non-Functional Expectations

- Full compile of the reference graph (~550 nodes) in seconds.
- Error messages actionable: file, ID, rule, suggested fix.

## Questions & Assumptions

**Open Questions:**
- [ ] Alias-similarity algorithm and threshold (token-set ratio vs normalized edit distance);
      calibrate against the known real duplicate risk (`document-generation` vs
      `outbound-document-generation` class of cases).

**Assumptions (to be validated):**
- Downstream generators are already deterministic given identical inputs (spot-verified for
  `symbols.py` during PR #47 review; verify `decisions.py` + coverage in implementation).

## Definition of Done

- [x] Acceptance criteria met; determinism proven by double-compile **and** a path-independent (cross-machine proxy) compile — byte-identical
- [x] F0005 resolver test matrix green (live, archive-flip, unmapped, missing, malformed, stable-root
      passthrough, physical-path reject)
- [x] Analysis report + suppression ledger (`kg-source/exclusions/suppressions.yaml`, rationale-gated) implemented with strict/advisory modes
- [x] `--check` mode diffs committed projections correctly (fresh / drift / tamper)
- [x] Unit + golden-file tests (`test_compile.py`, 24); documented in `scripts/kg/README.md`
- [x] Story filename matches `Story ID` prefix
- [x] Story index regenerated or updated (S0005 → Done)

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

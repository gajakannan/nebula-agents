# F0006-S0002 - Tracker-Table Three-Way Merge (REGISTRY/ROADMAP Rows)

## Story Header

**Story ID:** F0006-S0002
**Feature:** F0006 - Compiled Knowledge-Graph Projection and Governed Integration
**Title:** Tracker-table three-way merge (REGISTRY/ROADMAP rows)
**Priority:** High
**Phase:** Platform Hardening (Feature Phase A)

## User Story

**As a** maintainer integrating contributor branches that each registered/advanced their own feature
**I want** REGISTRY.md and ROADMAP.md feature tables merged as records keyed by feature ID, with deterministic row ordering
**So that** two branches that each added their own feature row merge automatically in the published order, instead of producing markdown-table conflict hunks a human must interleave by hand.

## Context & Background

Two of PR #47's seven conflicts were `REGISTRY.md` and `ROADMAP.md` — pure table-row interleaving
(F0038's row vs F0021's row in the same archived-features tables). The PM-agent resolution rule was
already deterministic: union of rows, newest-first by archive date, feature-ID-descending tiebreak.
This story mechanizes that rule so the integrator never hand-edits trackers.

Markdown tables are treated as record sets: a table region is parsed to rows keyed by the feature
ID column; rows merge by the S0001 record engine (a row is a record; cells are scalar fields);
output re-renders with the table's deterministic sort. Surrounding prose (purpose, rules, notes
sections) merges as ordinary text — if prose conflicts, that conflicts normally and routes to the
PM. This is the Phase A stopgap; Phase B (S0007) replaces merged tables with *generated* tables,
at which point this story's machinery handles only the transition period and non-generated tables.

## Acceptance Criteria

**Happy Path:**
- **Given** base REGISTRY.md, ours adding an F0038 row, theirs adding an F0021 row (same table)
- **When** the tracker merge runs
- **Then** the output table contains both rows exactly once, ordered by the table's sort rule
  (archived: date desc, then feature-ID desc), other rows byte-identical, and exit code 0.

**Typed conflict:**
- **Given** ours and theirs set a *different status* in the same feature's row
- **When** the merge runs
- **Then** no output is written and the report names the feature ID, column, both values
  (`DivergentUpdate`, owning role: PM).

**Alternative Flows / Edge Cases:**
- ROADMAP section membership counts as a field: the same feature moved to different sections
  (`Now` vs `Next`) on the two sides → conflict, PM-routed.
- A feature row deleted (retired) on one side and edited on the other → `DeleteVsUpdate`.
- `Next Available Feature Number` merges to `max(ours, theirs)` (monotonic counter rule).
- STORY-INDEX.md is **not** merged — it is already generated (`generate-story-index.py`); the
  integrator regenerates it (S0003). This story must reject it as input.
- Tables whose key column can't be identified fail loudly (no silent text-merge fallback).
- Row ordering rules are per-table configuration, not hardcoded: active tables sort ID-ascending,
  archived tables newest-first with ID-desc tiebreak (the published PR #47 resolution rule).

## Interaction Contract

N/A — CLI tool; no interactive surface.

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| `scripts/kg/merge3.py` (tracker mode or subcommand) | Run with base/ours/theirs of a tracker file | Tracker file (only on full success) | Merged file with deterministically ordered tables, or conflict report | Re-run yields byte-identical output | Maintainer / integrator / CI |

## Data Requirements

**Inputs:** three versions of a tracker markdown file; per-table config (key column, sort rule,
monotonic fields).
**Outputs:** merged markdown, or the same typed conflict report format as S0001.

**Validation Rules:**
- A feature ID appears at most once per table after merge.
- Table structure (columns) must match across the three versions; column changes conflict.
- Row rendering is canonical (consistent cell padding/trim) so re-merges are stable.

## Role-Based Visibility

**Roles that can run this tool / act on its output:**
- Maintainer / integrator — runs the tracker merge; consumes the merged tracker or conflict report.
- Product Manager — owns every tracker conflict (REGISTRY/ROADMAP rows route to PM).
- CI — runs it non-interactively.

**Data Visibility:** N/A — local planning-doc tooling over committed tracker markdown; no auth
surface and no internal/external data exposure.

## Dependencies

**Depends On:** F0006-S0001 (record-merge engine, conflict report format).
**Related Stories:** F0006-S0003 (integrator invokes tracker merge), F0006-S0007 (supersedes table
merging with table generation for feature tables).

## Business Rules

1. Trackers are PM territory: every tracker conflict routes to the PM role.
2. Ordering is never a conflict — it is always recomputed from the sort rule.
3. The union must preserve mainline-published history: rows present on the mainline never
   disappear because a branch lacked them.

## Out of Scope

- Generating tables from shards (S0007). BLUEPRINT.md feature-plan list (low conflict rate;
  hand-merge until S0007 evaluates including it). Story files themselves.

## Non-Functional Expectations

- Deterministic output; sub-second on current tracker sizes.

## Questions & Assumptions

**Open Questions:**
- [x] Home: `merge3.py --tracker` mode vs a sibling `merge3_trackers.py`. **Decided: one CLI** —
      shipped as a `tracker_merge.py` module invoked through the `merge3.py` CLI with file-type
      detection and the shared S0001 conflict-report format (see `STATUS.md` reference-implementation
      progress).

**Assumptions (to be validated):**
- Tracker tables all carry the feature ID as the first column (true today in both repos).

## Definition of Done

- [x] Acceptance criteria met, including a replay of the PR #47 REGISTRY/ROADMAP resolution
      producing the same union the PM agent hand-approved (F0038 row above F0021)
- [x] Unit tests: independent-row union, same-row divergence, section-move conflict,
      delete-vs-update, counter max-merge, canonical rendering idempotence
- [x] STORY-INDEX rejection test
- [x] Documented alongside merge3 usage
- [x] Story filename matches `Story ID` prefix
- [x] Story index regenerated or updated

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

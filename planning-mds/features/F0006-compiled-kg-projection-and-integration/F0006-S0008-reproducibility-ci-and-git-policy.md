# F0006-S0008 - Reproducibility CI, Enforcement, and Git Policy

## Story Header

**Story ID:** F0006-S0008
**Feature:** F0006 - Compiled Knowledge-Graph Projection and Governed Integration
**Title:** Reproducibility CI, enforcement, and git policy
**Priority:** High
**Phase:** Platform Hardening (Feature Phase B)

## User Story

**As a** maintainer accepting contributor PRs
**I want** CI that proves every branch's committed projections equal `compile(source)`, rejects hand-edited generated files with actionable errors, and git attributes that keep generated-file churn out of review and out of manual conflict resolution
**So that** the committed-projection policy is an enforced invariant rather than a convention, and the integrator can trust any green branch's sources without auditing its generated files.

## Context & Background

This story enforces the git policy the user decided (superseding the earlier uncommitted-build-dir
draft): generated files **are** committed on every branch, and the safety comes from one invariant
— reproducibility — checked at PR time (GitHub Actions works on personal accounts; only merge
queues don't) and re-checked by the integrator at merge time (S0003's bounce rule and this CI are
the same check in two places).

It also delivers F0005-S0003's enforcement (no physical feature-doc paths in source-authored
fields) as compiler/validator rules wired into CI, plus the archive-consistency rule from the
PR #47 postmortem: archived feature ⇒ no non-archive feature path anywhere in projections.

## Acceptance Criteria

**Happy Path:**
- **Given** a PR whose shards compile to exactly its committed projections
- **When** the reproducibility workflow runs (`validate.py --check-reproducible`, wrapping
  S0005's `--check`)
- **Then** the check passes, whole-file generated-path diffs render collapsed
  (`linguist-generated`), and no reviewer sees projection churn by default while
  partially-generated tracker prose remains visible for review.

**Hand-edit rejection:**
- **Given** a PR that edits `canonical-nodes.yaml` directly (no shard change compiles to it)
- **When** CI runs
- **Then** the check fails naming the file and the exact remediation ("edit the shard / run
  compile.py; generated files are never hand-edited"), unless the commit carries the documented
  maintainer-override trailer (logged, for emergencies only).

**Alternative Flows / Edge Cases:**
- Stale derived output (shard changed, contributor forgot to recompile) → same failure, "run
  compile.py" remediation — this is the CI twin of the integrator's bounce.
- `.gitattributes` merge driver on **whole-file** generated paths prevents textual conflict-marker
  deadlocks during any local merge; the integrator's unconditional recompile overwrites the driver's
  result anyway (defense in depth — the driver is convenience, never correctness). The
  partially-generated trackers (`REGISTRY.md`/`ROADMAP.md`) are **excluded** from both the driver and
  `linguist-generated`: only their fenced regions are recompiled, so whole-file `merge=ours` would
  silently drop incoming PM-authored prose edits, and Linguist would collapse prose diffs because its
  attributes are file-scoped. That prose merges as ordinary text (S0002/S0007) and routes to the PM.
- Tracker fenced-region integrity: markers missing/moved/hand-edited inside → reproducibility fail.
- Rollout: this workflow is a B5 deliverable, landing *after* the S0006 cutover (B3). It runs
  **warn-only** for a shake-out window, then flips blocking (branch protection) — a one-line change.
  The pre-CI window (the Phase-A train and B1–B4) is covered by the integrator's per-run recompile +
  bounce (S0003), which is the same reproducibility check enforced at merge time.
- Phase A interim (retrospective for the reference repo): before the compiler exists, the same
  workflow shape can check the *derived* files only (regenerate symbols/decisions/coverage/story-index
  and diff). In `nebula-insurance-crm` the merge train completed (2026-07-06) before S0008 was built,
  so this interim check never ran there — the integrator's per-run unconditional regeneration + bounce
  rule (S0003) covered that window instead. The mode remains available for any repo that runs a
  Phase-A merge train before standing up its compiler.
- Enforcement rules in `validate.py`: physical feature-path ban in source fields; archived ⇒ no
  stale path in projections; alias-suppression ledger entries must carry rationale; every binding
  glob matches ≥ 1 file unless allowed.

## Interaction Contract

N/A — CI + git configuration; no interactive surface.

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| `.github/workflows/kg-reproducibility.yml` | Push / open PR | None (checks only) | Pass/fail with remediation text | Workflow logs per run | All PRs; blocking post-cutover |
| `.gitattributes` | Merge locally | Merge behavior of generated paths | Conflict-free generated files pending recompile | — | All clones |

## Data Requirements

**Deliverables:** a single shared generated-path manifest, `scripts/kg/generated_paths.yaml` (every
generated path with a **granularity** marker — `whole-file` for the projection/derived files,
`fenced-region` for the partially-generated trackers `REGISTRY.md`/`ROADMAP.md`; the PRD §2
"Generated projections" table is its authoritative content) — the one home the three consumers
below read from; workflow file (from a new `ci-gates-template.yml` job template in `nebula-agents`);
`.gitattributes` entries produced from the manifest (never hand-listed), applying `linguist-generated`
and the merge driver **only to `whole-file` paths** — `fenced-region` trackers are excluded from both
`linguist-generated` and the `merge=ours` driver because both are file-scoped controls that would hide
or drop PM-authored prose the recompile does not restore; validator rules; override-trailer convention
documented.

**Validation Rules:**
- The generated-path list has one authoritative home — `scripts/kg/generated_paths.yaml` — consumed
  by CI, `.gitattributes` generation, and the integrator; no second hand-maintained copy exists (a
  CI check fails if `.gitattributes` drifts from the manifest).
- Granularity is honored end-to-end: `whole-file` paths are compared byte-for-byte by
  `--check-reproducible`; `fenced-region` paths (`REGISTRY.md`/`ROADMAP.md`) are checked only inside
  their `generated:begin`/`generated:end` markers, get neither `linguist-generated` nor the
  `merge=ours` driver, and their surrounding PM-authored prose is never collapsed or clobbered.
- Override use is visible: CI annotates the run; the integrator records it in evidence.

## Role-Based Visibility

**Roles that can act on this surface:**
- DevOps — owns the reproducibility workflow, `.gitattributes` merge driver, and branch protection.
- Maintainer — may apply the documented override trailer (logged, emergencies only).
- Integrator — consumes the same `generated_paths.yaml` manifest and enforces the same check at merge.
- All contributors — the check runs on every PR (blocking post-cutover).

**Data Visibility:** N/A — CI + git configuration over a local repo / GitHub Actions on a personal
account; no application auth surface and no internal/external data exposure.

## Dependencies

**Depends On:** F0006-S0005 (`--check`), F0006-S0006 (cutover gates the blocking flip),
F0006-S0007 (region integrity).
**Related Stories:** F0006-S0003 (same invariant at merge time), F0006-S0009 (contributor docs).

## Business Rules

1. Reproducibility is the *only* rule about committed generated files — no path-based commit bans
   that would break integrator runs or overrides.
2. Warn-only for a shake-out window when the CI first lands (post-cutover), blocking thereafter;
   never blocking while open PRs predate the policy.
3. The merge driver is convenience; correctness comes solely from recompilation.

## Out of Scope

- The merge-time regeneration itself (S0003). Branch protection beyond this check. Product repos
  other than the reference.

## Non-Functional Expectations

- Workflow completes in low single-digit minutes (checkout + compile + diff).

## Questions & Assumptions

**Open Questions:**
- [ ] Merge-driver choice: `merge=ours` vs a custom "take either, recompile will fix" driver —
      decide with DevOps during implementation (drivers don't run on GitHub's server-side merges,
      which is fine: server-side merges of these PRs don't happen; the integrator merges locally).

**Assumptions (to be validated):**
- GitHub Actions minutes on the personal account suffice for per-PR compile checks (small repo,
  seconds of compute).

## Definition of Done

- [ ] Acceptance criteria met; red test (synthetic hand-edit) and green test recorded in CI
- [ ] `scripts/kg/generated_paths.yaml` manifest landed **with per-path granularity**
      (`whole-file`/`fenced-region`); `.gitattributes` generated from it (merge driver on
      `whole-file` paths only); CI and the integrator consume the same manifest (no second
      hand-maintained copy)
- [ ] Validator rules landed with tests (physical-path ban, archived-consistency, ledger
      rationale, glob-match)
- [ ] Warn-only shake-out → blocking flip executed once the CI lands (post-cutover)
- [ ] `ci-gates-template.yml` job template added in `nebula-agents`
- [ ] Story filename matches `Story ID` prefix
- [ ] Story index regenerated or updated

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

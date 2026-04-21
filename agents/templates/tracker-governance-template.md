---
template: tracker-governance
version: 1.1
applies_to: product-manager, architect, code-reviewer, quality-engineer
---

# Tracker Governance Contract

This document defines how planning trackers stay current and trustworthy.

## Why This Exists

- `REGISTRY.md`, `ROADMAP.md`, `STORY-INDEX.md`, `BLUEPRINT.md`, and per-feature `STATUS.md` are operational controls.
- Feature/story state transitions must update tracker state in the same change set.

## Authoritative Tracker Roles

- `{PRODUCT_ROOT}/planning-mds/features/REGISTRY.md`: authoritative feature inventory, status, and folder paths.
- `{PRODUCT_ROOT}/planning-mds/features/ROADMAP.md`: authoritative sequencing view (`Now / Next / Later / Completed`).
- `{PRODUCT_ROOT}/planning-mds/features/STORY-INDEX.md`: auto-generated story rollup from strict story filenames.
- `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/STATUS.md`: authoritative feature execution state and deferred follow-ups.
- `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`: baseline strategy snapshot; must not contradict tracker state.

## Ownership

- Product Manager: updates tracker docs during planning changes.
- Architect: validates tracker consistency at planning-to-build handoff. Owns the required signoff matrix at planning time — sets which roles are mandatory for each feature's completion.
- Implementers: update feature `STATUS.md` when story state changes.
- Code Reviewer: blocks approval when tracker drift is detected.
- Quality Engineer: validates acceptance criteria coverage and records test signoff evidence.
- Security Reviewer: records security signoff when included in required signoff roles.

## Signoff Governance (Mandatory)

- Every feature `STATUS.md` must include:
  - `Required Signoff Roles`
  - `Story Signoff Provenance`
- Minimum required roles for features marked `Done` or moved to archive:
  - `Quality Engineer`
  - `Code Reviewer`
- Architect adds additional required roles based on risk/scope:
  - `Security Reviewer` — for authn/authz, access control, identity/session, secrets, sensitive data boundaries, or policy changes
  - `DevOps` — for runtime/deployability or environment-contract changes
  - `Architect` — when architecture-sensitive exceptions or tradeoffs require explicit acceptance
- Every required role must have story-level provenance entries for every story in scope with:
  - pass verdict (`PASS` or `APPROVED`)
  - reviewer identity
  - review date
  - concrete evidence path(s)
- Product Manager must not close or archive a feature until all required signoffs pass.

## Provenance Boundary Rules (Mandatory)

- Signoff provenance is solution execution evidence and must live outside `agents/`.
- `agents/**` may define process/templates/checklists, but is never accepted as completion evidence.
- Provenance `Evidence` should point to project outputs such as:
  - `{PRODUCT_ROOT}/planning-mds/**` (reviews, test plans, security evidence, tracker updates)
  - implementation/test artifacts in `{PRODUCT_ROOT}/engine/**`, `{PRODUCT_ROOT}/experience/**`, `{PRODUCT_ROOT}/neuron/**`, `docs/**`, or CI outputs

## Lifecycle Rules

- Feature lifecycle states: `Draft` -> `In Progress` -> `Done` -> `Archived`.
- `Done` means implementation complete and signoff evidence captured in `STATUS.md`.
- `Done` may include a `Deferred Non-Blocking Follow-ups` section in `STATUS.md`; deferments must not change overall completion state.
- Archived features must:
  - live under `{PRODUCT_ROOT}/planning-mds/features/archive/`
  - be listed under `Archived Features` in `REGISTRY.md`
  - appear in `ROADMAP.md` under `Completed`, not `Now/Next/Later`.

## Orphaned Story Rule (Mandatory)

Before marking a feature `Done` or moving to `Archived`, the PM must verify that all non-completed stories are either:

1. **Explicitly deferred** in `STATUS.md` `Deferred Non-Blocking Follow-ups` with a tracking link to a new or existing feature, or
2. **Promoted** to a new feature ID in `REGISTRY.md` if the scope warrants standalone tracking.

No story file may be archived in a `Not Started` or `In Progress` state without a rehoming decision recorded in the closeout. This prevents future work from being silently buried in the archive.

## Story File Rules

- Story files must follow `F{NNNN}-S{NNNN}-{slug}.md`.
- Non-story documents in feature folders must not start with `F{NNNN}-S{NNNN}`.
- Story IDs in file content must match filename prefix.

## Mandatory Sync Triggers

Update trackers immediately when any of the following occurs:

1. A feature is created, renamed, moved, or archived.
2. A story is added, removed, renamed, or moved.
3. A feature/story status changes (including done/archive transitions).
4. Roadmap prioritization or sequencing changes.
5. Blueprint feature/story status text changes.

## Required Validation Commands

Run these before declaring planning or feature execution complete:

```bash
python3 agents/product-manager/scripts/validate-stories.py {PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/
python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/
python3 agents/product-manager/scripts/validate-trackers.py
```

## Definition of Fresh Trackers

All conditions must pass:

- [ ] Every `REGISTRY.md` folder path exists and points to the correct active/archive location.
- [ ] `ROADMAP.md` links resolve and align with current feature state.
- [ ] `STORY-INDEX.md` story count and links match current strict story files.
- [ ] `BLUEPRINT.md` linked feature/story paths resolve and match archive status.
- [ ] No non-story file is parsed as a story.
- [ ] For every feature in `Done` or `Archived`, required signoff roles have story-level passing provenance evidence for each story in `STATUS.md`.

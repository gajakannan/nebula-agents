# Tracker Governance

**Last Updated:** 2026-07-11

> **Compiled-projection note (F0006-S0009).** In a product repo that has adopted the compiled-projection
> model (reference: `nebula-insurance-crm`), the **REGISTRY.md and ROADMAP.md feature tables are
> generated** from `kg-source/features/**` by `scripts/kg/tracker_gen.py` — the generator owns the
> fenced `<!-- generated:begin … -->` regions; surrounding prose stays PM-authored. Never hand-edit a
> generated table region; edit the feature shard and recompile. **This repo (`nebula-agents`) has not
> yet adopted the shard model for its own planning graph** (it has no populated KG); its trackers below
> remain hand-authored. Adopting it here is a tracked follow-up.

## Authoritative Trackers

| Tracker | Purpose | Required Sync Trigger |
|---------|---------|-----------------------|
| `planning-mds/BLUEPRINT.md` | Top-level feature and story planning index. | Feature or story added, moved, retired, completed, or archived. |
| `planning-mds/features/REGISTRY.md` | Feature ID allocation, status, and folder paths. | Feature created, renamed, status changed, retired, or archived. |
| `planning-mds/features/ROADMAP.md` | Now / Next / Later delivery sequencing. | Feature priority or delivery order changes. |
| `planning-mds/features/STORY-INDEX.md` | Strict story-file rollup. | Story file added, renamed, moved, or removed. |
| `planning-mds/features/F####-*/STATUS.md` | Feature delivery state and signoff provenance. | Story status, required reviewer role, evidence, or closeout changes. |

## Lifecycle Rules

- A feature starts as `Planned` or `Draft`, moves to `In Progress` only when implementation starts, and moves to `Done` only after required story signoff provenance is recorded.
- `Archived` is a post-closeout state. Archived features move under `planning-mds/features/archive/`.
- Superseded features are archive-ready at supersession: the folder moves under `planning-mds/features/archive/` immediately (terminal state — nothing further accumulates), while the registry record stays in `Retired Features` (status `Superseded`, folder path `archive/F####-…/`), not `Archived Features`, because no scope was delivered under that ID. Stories left `Not Started` must carry a recorded rehoming decision (the story mapping to the superseding feature).
- Story IDs are never reused inside a feature.
- Feature IDs are never reused across active, planned, retired, or archived records.
- F0001 is the first executable terminal UI path. F0002 is a future-state platform path and must preserve a fallback to F0001 behavior until parity is proven.

## Required Signoff Roles

All completed features require:

| Role | Required By Default | Notes |
|------|---------------------|-------|
| Quality Engineer | Yes | Acceptance criteria and regression evidence. |
| Code Reviewer | Yes | Implementation quality, maintainability, and defect review. |
| Security Reviewer | Conditional | Required for auth, secrets, transcript, provider-token, or permission-boundary changes. |
| DevOps | Conditional | Required for CI, install, runtime, or environment-contract changes. |
| Architect | Conditional | Required for platform boundaries, orchestration model, or provider abstraction changes. |

## Evidence Boundary

- Evidence must reference solution artifacts under this repo, product planning docs, test reports, or operation evidence packages.
- Evidence must not cite `agents/**` guidance files as proof of delivered behavior.
- Terminal transcript evidence must redact secrets, tokens, account identifiers that are not needed for review, and provider auth cache details.

## Required Validation Commands

Use explicit product-root arguments when running validators from this repo:

```bash
python agents/product-manager/scripts/validate-stories.py --product-root /home/gajap/uSandbox/repos/nebula/nebula-agents planning-mds/features
python agents/product-manager/scripts/validate-trackers.py --product-root /home/gajap/uSandbox/repos/nebula/nebula-agents --skip-feature-evidence
```

## Orphaned Story Rule

A story file is orphaned when it exists under `planning-mds/features` but is missing from `STORY-INDEX.md`, `BLUEPRINT.md`, or the parent feature `STATUS.md`. Orphaned stories are blocking until either linked into the feature scope or retired with a written reason.

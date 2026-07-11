---
template: feature-registry
version: 1.1
applies_to: product-manager
---

# Feature Registry Template

Tracks all features by ID, name, and status. Place as `REGISTRY.md` at `{PRODUCT_ROOT}/planning-mds/features/REGISTRY.md`. In a compiled-projection repo (F0006), the feature **tables** are generated from `kg-source/features/**` into fenced `<!-- generated:begin … -->` regions by `scripts/kg/tracker_gen.py` — edit the feature shard, not the table; surrounding prose stays authored.

---

# Feature Registry

**Next Available Feature Number:** F{NNNN}

**Planning Views:**
- Roadmap sequencing (`Now / Next / Later`): `{PRODUCT_ROOT}/planning-mds/features/ROADMAP.md`
- Story rollup index: `{PRODUCT_ROOT}/planning-mds/features/STORY-INDEX.md`
- Governance contract: `{PRODUCT_ROOT}/planning-mds/features/TRACKER-GOVERNANCE.md`

## Active Features

| Feature ID | Name | Status | Phase | Folder |
|------------|------|--------|-------|--------|
| F0001 | [Feature name] | [Draft / In Progress / In Refinement / Architecture Complete / Complete] | [MVP / Phase 1 / Infrastructure / ...] | `F0001-{slug}/` |
| F0002 | [Feature name] | [Draft / In Progress / In Refinement / Architecture Complete / Complete] | [MVP / Phase 1 / Infrastructure / ...] | `F0002-{slug}/` |

## Retired Features

Replaces the legacy `Abandoned Features` section. Per §19, retired features are registry records that were not delivered as completed scope. Two terminal statuses: `Abandoned` (work stopped before delivery) and `Superseded` (replaced by another feature).

| Feature ID | Name | Terminal Status | Superseded By | Retired Date | Folder | Reason |
|------------|------|-----------------|---------------|--------------|--------|--------|
| [F{NNNN}] | [Feature name] | [Abandoned / Superseded] | [F{NNNN} or N/A] | [YYYY-MM-DD] | [`archive/F{NNNN}-{slug}/` or blank for never-reached-G0] | [Why retired] |

Rules per §19:

- `Terminal Status` is `Abandoned` or `Superseded` only.
- `Superseded By` is required when `Terminal Status = Superseded`; blank or `N/A` for `Abandoned`.
- `Folder` may be blank for abandoned features that never reached G0/assembly; superseded features should normally carry the archive folder.
- Retired Feature IDs are never reused.

## Planned (Reserved IDs)

Features with allocated IDs that are not yet in active development. Tracks future headroom.

| Feature ID | Name | Status | Phase | Folder |
|------------|------|--------|-------|--------|
| [F{NNNN}] | [Feature name] | [Planned / Architecture Complete / In Refinement] | [Phase] | `F{NNNN}-{slug}/` |

## Archived Features

| Feature ID | Name | Archived Date | Evidence Reentry Date | Folder |
|------------|------|---------------|-----------------------|--------|
| [F{NNNN}] | [Feature name] | [YYYY-MM-DD] | [optional YYYY-MM-DD if reopened post-contract] | `archive/F{NNNN}-{slug}/` |

Per §6, the optional `Evidence Reentry Date` column flags a pre-contract archived feature that has been reopened, materially changed, or re-closed on or after the contract effective date (`2026-05-19`). When present and `>= 2026-05-19`, the feature requires the canonical feature evidence package at the new closeout. Validators must not use filesystem timestamps or git history to infer reentry — the field is the authoritative signal.

## Numbering Rules

- Feature IDs use a 4-digit zero-padded format: `F0001`, `F0002`, ..., `F9999`
- Numbers are assigned sequentially — never reuse a retired number
- Story IDs within a feature follow `F{NNNN}-S{NNNN}` (e.g., `F0001-S0001`)
- Update **Next Available Feature Number** whenever a new feature is added

## Sync Rules

- Update REGISTRY whenever a feature is created, renamed, re-scoped, marked done, or archived.
- Keep folder paths exact and valid (`F{NNNN}-{slug}/` for active, `archive/F{NNNN}-{slug}/` for archived).
- Ensure `{PRODUCT_ROOT}/planning-mds/features/TRACKER-GOVERNANCE.md` exists (seed from `agents/templates/tracker-governance-template.md` when initializing a new repo).
- After registry edits, regenerate story index and run tracker validation.

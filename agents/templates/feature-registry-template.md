---
template: feature-registry
version: 1.1
applies_to: product-manager
---

# Feature Registry Template

Tracks all features by ID, name, and status. Place as `REGISTRY.md` at `{PRODUCT_ROOT}/planning-mds/features/REGISTRY.md`.

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

## Abandoned Features

Features that were superseded by a different approach before completion.

| Feature ID | Name | Superseded By | Abandoned Date | Folder |
|------------|------|---------------|----------------|--------|
| [F{NNNN}] | [Feature name] | [F{NNNN}] | [YYYY-MM-DD] | `archive/F{NNNN}-{slug}/` |

## Planned (Reserved IDs)

Features with allocated IDs that are not yet in active development. Tracks future headroom.

| Feature ID | Name | Status | Phase | Folder |
|------------|------|--------|-------|--------|
| [F{NNNN}] | [Feature name] | [Planned / Architecture Complete / In Refinement] | [Phase] | `F{NNNN}-{slug}/` |

## Archived Features

| Feature ID | Name | Archived Date | Folder |
|------------|------|---------------|--------|
| [F{NNNN}] | [Feature name] | [YYYY-MM-DD] | `archive/F{NNNN}-{slug}/` |

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

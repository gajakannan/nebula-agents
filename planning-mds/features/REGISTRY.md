# Feature Registry

**Next Available Feature Number:** F0009

**Planning Views:**
- Roadmap sequencing (`Now / Next / Later`): `{PRODUCT_ROOT}/planning-mds/features/ROADMAP.md`
- Story rollup index: `{PRODUCT_ROOT}/planning-mds/features/STORY-INDEX.md`
- Governance contract: `{PRODUCT_ROOT}/planning-mds/features/TRACKER-GOVERNANCE.md`

## Active Features

<!-- generated:begin registry:active -->
| Feature ID | Name | Status | Phase | Folder |
|------------|------|--------|-------|--------|
| F0007 | Spec-Driven Orchestration and Prompt Compilation | Planned | Framework Hardening | `F0007-spec-driven-orchestration-and-prompt-compilation/` |
<!-- generated:end registry:active -->

## Retired Features

Replaces the legacy `Abandoned Features` section. Retired features are registry records that were not delivered as completed scope. Two terminal statuses are allowed: `Abandoned` and `Superseded`.

<!-- generated:begin registry:retired -->
| Feature ID | Name | Terminal Status | Superseded By | Retired Date | Folder | Reason |
|------------|------|-----------------|---------------|--------------|--------|--------|
| F0005 | Move-Invariant Knowledge-Graph Feature-Doc References | Superseded | F0006 | 2026-07-04 | `archive/F0005-move-invariant-kg-doc-references/` | Fully absorbed by F0006's compiled-projection design: logical doc refs become the compiler's reference format (F0006-S0005), migration lands via the decompiler (F0006-S0006), enforcement via reproducibility CI (F0006-S0008), contract reconciliation via F0006-S0009. |
<!-- generated:end registry:retired -->

## Planned (Reserved IDs)

<!-- generated:begin registry:planned -->
| Feature ID | Name | Status | Phase | Folder |
|------------|------|--------|-------|--------|
| F0002 | Managed Agent Orchestration | Planned | Future Platform | `F0002-managed-agent-orchestration/` |
| F0003 | Local Agent Runtime Control Plane | Planned | Platform Hardening | `F0003-local-agent-runtime-control-plane/` |
| F0004 | Reflective Learning Loop and Strategy Playbook | Planned | Context Engineering | `F0004-reflective-learning-loop/` |
| F0008 | Agent Cockpit Landing Shell | Planned | Operator Experience | `F0008-agent-cockpit-landing-shell/` |
<!-- generated:end registry:planned -->

## Archived Features

<!-- generated:begin registry:archived -->
| Feature ID | Name | Archived Date | Evidence Reentry Date | Folder |
|------------|------|---------------|-----------------------|--------|
| F0001 | Tmux-Native Agent Cockpit | 2026-07-15 | 2026-07-15 | `archive/F0001-tmux-native-agent-cockpit/` |
| F0006 | Compiled Knowledge-Graph Projection and Governed Integration | 2026-07-12 | 2026-07-12 | `archive/F0006-compiled-kg-projection-and-integration/` |
<!-- generated:end registry:archived -->

## Numbering Rules

- Feature IDs use a 4-digit zero-padded format: `F0001`, `F0002`, ..., `F9999`.
- Numbers are assigned sequentially and are never reused.
- Story IDs within a feature follow `F{NNNN}-S{NNNN}`.
- Update **Next Available Feature Number** whenever a new feature is added.
- F0001 is reserved for the tmux-native first usable surface.
- F0002 is reserved for the future managed-orchestration state.

## Sync Rules

- Update this registry whenever a feature is created, renamed, re-scoped, marked done, retired, or archived.
- Keep folder paths exact and valid.
- After registry edits, update `ROADMAP.md`, regenerate or update `STORY-INDEX.md`, and run planning validation.

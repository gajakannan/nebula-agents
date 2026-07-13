# F0005 - Move-Invariant Knowledge-Graph Feature-Doc References

**Status:** Superseded by [F0006](../F0006-compiled-kg-projection-and-integration/README.md) (2026-07-04)
**Priority:** High
**Phase:** Platform Hardening

> **Superseded — no work happens under this feature.** The compiled-projection design (F0006)
> fully absorbs F0005: logical doc refs are the compiler's reference format. Story mapping:
> S0001 resolver → F0006-S0005, S0002 migration → F0006-S0006, S0003 enforcement → F0006-S0008,
> S0004 contract reconciliation → F0006-S0009. Per process, supersession makes a feature
> archive-ready: the folder was moved here (`features/archive/`) at supersession as the design
> record; its registry record lives in `REGISTRY.md` Retired Features (terminal status
> `Superseded`), not Archived Features, because no scope was delivered under this ID.

## Overview

Knowledge-graph nodes (`canonical-nodes.yaml`, `code-index.yaml`) embed **physical**
feature-doc paths such as `planning-mds/features/F0038-.../README.md`. When the Product
Manager archives a completed feature at gate `G8` (folder moves to
`planning-mds/features/archive/F0038-.../`), every one of those embedded paths goes stale —
and `validate.py` fails with `Missing path for <node>.source_docs`. The ownership contract
forbids the PM from editing those architect-owned files, and the architect (who may) runs at
`G7`, *before* the move. No role is cleanly positioned to repoint after the move.

F0005 removes the whole problem class by making feature-doc references **move-invariant**:
nodes reference docs by a logical `F####/relative-path` form, and the single physical location
lives only in `feature-mappings.yaml` (already PM-owned and already updated on the archive move,
per `agents/docs/KNOWLEDGE-GRAPH.md`). A small resolver joins the two at read time. After this
feature ships, archiving a feature is exactly one `path:` edit, and no KG binding can go stale.

This is the durable form of the fix that F0038's closeout had to improvise: its PM repointed
`canonical-nodes.yaml` by hand (`pm-closeout.md` line 60), contradicting the contract's
"PM does not author the semantic graph" rule. F0005 makes that hand-edit unnecessary and makes
the contract honest.

## Documents

| Document | Purpose |
|----------|---------|
| [PRD.md](./PRD.md) | Full requirements, design, migration, and framework-edit inventory |
| [STATUS.md](./STATUS.md) | Delivery checklist and signoff tracking |
| [GETTING-STARTED.md](./GETTING-STARTED.md) | Where the resolver lives and how to verify the graph |

## Stories

| ID | Title | Status |
|----|-------|--------|
| [F0005-S0001](./F0005-S0001-feature-doc-reference-resolver.md) | Feature-doc reference resolver (dual-format, fail-loud) | Not Started |
| [F0005-S0002](./F0005-S0002-migrate-feature-doc-refs-to-logical.md) | Migrate existing feature-doc references to logical form | Not Started |
| [F0005-S0003](./F0005-S0003-enforce-logical-only-feature-doc-refs.md) | Enforce logical-only feature-doc references | Not Started |
| [F0005-S0004](./F0005-S0004-reconcile-framework-contract-and-docs.md) | Reconcile framework contract, prompt, and KG docs | Not Started |

**Total Stories:** 4
**Completed:** 0 / 4

## Architecture Review

**Phase B status:** Not Started
**Execution Plan:** TBD

### Key Findings

- The framework contract already *assumes* this design: `agents/docs/KNOWLEDGE-GRAPH.md` line 294
  documents the archive step as "update `path:` in `feature-mappings.yaml`" and nothing else. The
  data schema is what never matched. F0005 aligns the data to the contract, not the reverse.
- The change is a **hybrid**, not a wholesale rewrite: only feature-folder refs (~220 in
  `canonical-nodes.yaml`, ~44 in `code-index.yaml`) become logical. Refs into stable roots
  (`schemas/`, `architecture/`, `security/`, `api/` — ~480 refs) stay physical, untouched.
- Consumer surface is exactly three product-repo scripts: `validate.py`, `lookup.py`, `eval.py`.
- This feature spans two repos: the **reference implementation** (resolver + migration) lands in a
  product repo's `scripts/kg/` (first: `nebula-insurance-crm`); the **contract** (feature action,
  operator prompt, KG docs) lands here in `nebula-agents`. It is registered here because it is
  fundamentally a framework-contract change.

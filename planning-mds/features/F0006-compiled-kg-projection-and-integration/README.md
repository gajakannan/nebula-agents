# F0006 - Compiled Knowledge-Graph Projection and Governed Integration

**Status:** Planned
**Priority:** Critical
**Phase:** Platform Hardening

## Overview

Multi-contributor feature branches conflict on exactly the files no human (or LLM) should ever
hand-merge: the knowledge-graph YAML and the feature trackers. The reference product repo
(`nebula-insurance-crm`) proved it — PR #47 (F0021) carried 7 merge conflicts, **all** of them
tracker/KG, zero code; six more contributor PRs (#48–#51, plus #53/#54 which joined 2026-07-04)
sit behind it touching the identical KG/tracker file set.
Worse, contributor tooling re-serialized the curated YAML, so git's textual merge saw the *same
nodes* as conflicting hunks, and a git union merge would silently duplicate nodes.

F0006 ends the problem class by treating the knowledge graph as a **compiled database projection**:

- Contributors author small, mergeable **source shards** (`planning-mds/kg-source/`), never the
  monolithic graph files.
- A deterministic **compiler** (`scripts/kg/compile.py`) emits the graph and tracker projections;
  generated outputs stay **committed on every branch** (self-contained branches, agents read
  committed state) with a CI invariant: committed output must equal `compile(source)`.
- A **three-way semantic merge tool** (`scripts/kg/merge3.py`) merges graph records by semantic ID
  against the merge base — with a typed conflict taxonomy — instead of asking git to merge YAML text.
- A new **integrator role** (agent) runs serially at merge time as the sole writer of generated
  files on the mainline: merge sources, recompile, validate, emit integration evidence, prepare the
  merge for the maintainer. It never edits source shards; semantic collisions route to the owning
  role (architect or PM). Two **human gates** bracket each run: a passing `feature-review` verdict
  (or recorded maintainer waiver) before it starts, and the maintainer's test validation of the
  prepared merge before push.

Sequencing is deliberate: the merge tool and integrator land **first** and drain the 7-PR queue on
the *current* monolithic graph (the merge keys on semantic IDs, so it does not need the shard
migration); only then does the source-shard migration rewrite the graph files. F0006 absorbs and
supersedes **F0005** (move-invariant logical doc refs become the compiler's reference format).

## Documents

| Document | Purpose |
|----------|---------|
| [PRD.md](./PRD.md) | Full requirements: classification, shard schema, compiler, merge semantics, integrator contract, git policy, migration, and the two-repo edit inventory |
| [STATUS.md](./STATUS.md) | Delivery checklist and signoff tracking |
| [GETTING-STARTED.md](./GETTING-STARTED.md) | Where the tools live, how to run a compile/merge, how to verify reproducibility |

## Stories

| ID | Title | Status |
|----|-------|--------|
| [F0006-S0001](./F0006-S0001-three-way-semantic-kg-merge.md) | Three-way semantic KG merge tool (`merge3.py`) | Done |
| [F0006-S0002](./F0006-S0002-tracker-table-three-way-merge.md) | Tracker-table three-way merge (REGISTRY/ROADMAP rows) | Done |
| [F0006-S0003](./F0006-S0003-integrator-role-and-integrate-action.md) | Integrator role and `integrate` action | Done |
| [F0006-S0004](./F0006-S0004-kg-source-shard-schema-and-ownership.md) | `kg-source/` shard schema, layout, and ownership | Not Started |
| [F0006-S0005](./F0006-S0005-deterministic-kg-compiler.md) | Deterministic KG compiler with logical doc refs | Not Started |
| [F0006-S0006](./F0006-S0006-decompiler-first-migration.md) | Decompiler-first migration with round-trip proof | Not Started |
| [F0006-S0007](./F0006-S0007-tracker-generation-from-shards.md) | Tracker generation from feature shards | Not Started |
| [F0006-S0008](./F0006-S0008-reproducibility-ci-and-git-policy.md) | Reproducibility CI, enforcement, and git policy | Not Started |
| [F0006-S0009](./F0006-S0009-framework-contract-reconciliation.md) | Framework contract, roles, and docs reconciliation | Not Started |

**Total Stories:** 9
**Completed:** 3 / 9 (Phase A complete — merge train executed and promoted 2026-07-06)

## Phasing

| Phase | Stories | Gate |
|-------|---------|------|
| **A — Governed integration (pre-migration)** | S0001, S0002, S0003 | The 7 open contributor PRs in `nebula-insurance-crm` (#47, #51, #50, #48, #49, #53, #54) merged via the integrator with green validators and integration evidence per merge, each bracketed by a feature-review verdict/waiver (gate 1) and maintainer test validation before push (gate 2) |
| **B — Compiled projection** | S0004–S0009 | `kg-source/` is the only authored layer; compile round-trip is byte-identical; CI reproducibility check blocking; contract docs match shipped behavior |

Phase A must complete before Phase B begins: the migration rewrites exactly the files every open
PR touches (amendment: land the merge train first). Contributor PRs that arrive before the train
completes join the same train.

All Phase-A integration lands on the `chore/merge-PRs` integration branch — never directly on
`main`, which receives only the single promotion merge after the train completes. In steady state
the integrator creates a dedicated integration branch per train; the promotion rule stays the same.

## Architecture Review

**Phase B status:** Not Started
**Execution Plan:** TBD

### Key Findings

- Merge semantics are adapted from OmniGraph's three-way, row-level branch merge (typed conflict
  taxonomy: divergent insert/update, delete-vs-update, orphan edge, uniqueness/constraint
  violations) **without** adopting its runtime — the essence is a few hundred lines of Python over
  YAML records keyed by semantic ID.
- The semantic merge works on **today's monolithic** `canonical-nodes.yaml`/`feature-mappings.yaml`
  because it keys on IDs, not lines or files. That is what allows Phase A to unblock the PR queue
  before any migration.
- Two artifacts were unclassified in every earlier draft and are classified here:
  `decisions-index.yaml` (**generated**, via `scripts/kg/decisions.py`) and
  `solution-ontology.yaml` (**curated source** — typed vocabulary with its own embedded ownership
  matrix; rehomed under `kg-source/` in Phase B).
- Trackers are part of the problem, not a side note: 2 of PR #47's 7 conflicts were
  REGISTRY.md/ROADMAP.md. Phase A merges their rows as keyed records; Phase B generates the feature
  tables outright.
- This feature spans two repos: the **reference implementation** (merge tool, compiler, migration,
  CI) lands in the product repo's `scripts/kg/` (first: `nebula-insurance-crm`); the **contract**
  (integrator role, `integrate` action, ownership boundaries, KG docs, templates) lands here in
  `nebula-agents`. Registered here because it is fundamentally a framework-contract change.

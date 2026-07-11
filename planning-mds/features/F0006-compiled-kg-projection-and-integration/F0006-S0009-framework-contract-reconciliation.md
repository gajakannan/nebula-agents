# F0006-S0009 - Framework Contract, Roles, and Docs Reconciliation

## Story Header

**Story ID:** F0006-S0009
**Feature:** F0006 - Compiled Knowledge-Graph Projection and Governed Integration
**Title:** Framework contract, roles, and docs reconciliation
**Priority:** High
**Phase:** Platform Hardening (Feature Phase B)

## User Story

**As a** framework operator or role agent following the written contract
**I want** every action, prompt, ownership boundary, template, and doc updated to describe the shipped compiled-projection and integrator behavior — with no remaining description of hand-maintained graph files or off-book repoints
**So that** a strict agent obeying the letter of the contract performs correctly at every gate, and the contract stops being aspirational in exactly the places F0038 and PR #47 proved it wrong.

## Context & Background

This absorbs F0005-S0004 and extends it to the full F0006 surface. The framework currently makes
claims that are false post-F0006 (or were false already): `feature.md` and the operator prompt say
the architect's G7 binding is "code paths only, stable across the archive move" (it wasn't); the
ownership rules make no one the writer of generated files on the mainline; no action describes
integration. Docs ship **last** (after S0003 for integrator surfaces, after S0004–S0008 for the
projection surfaces) so the contract never describes unshipped behavior — but the story is
specified now so every edit target is inventoried up front (PRD "Framework Edit Inventory").

## Acceptance Criteria

**Happy Path (contract audit):**
- **Given** the shipped Phase A + B behavior
- **When** each inventoried surface is reconciled and the audit rereads the full set
- **Then** no framework file instructs or implies: hand-editing a generated file, PM edits to
  architect-owned graph files, physical feature-doc refs in shards, trusting a clean merge of
  generated files, or any merge path that bypasses the integrator on graph/tracker files.

**Alternative Flows / Edge Cases:**
- `agents/agent-map.yaml`: integrator registered (S0003); architect is primary writer of
  `kg-source/{nodes,bindings,policies,ontology}/**`; PM writes `kg-source/features/**` and tracker
  prose. **Every direct write scope to a now-generated file is removed, symmetrically** — PM's
  `feature-mappings.yaml` **and** the architect's `canonical-nodes.yaml`, `feature-mappings.yaml`,
  and `code-index.yaml` (all three become `compile.py` outputs); the architect's
  `solution-ontology.yaml` scope is **relocated** to `kg-source/ontology/**` (rehome, not removal).
  `coverage-report.yaml` remains (a `--write-coverage-report` regeneration, not a hand-edit). The
  integrator's Phase-A scope annotations flip to Phase-B reality: the curated trio from "via merge3
  only" and REGISTRY/ROADMAP from "via tracker merge only" to "regenerated via `compile.py`".
  Co-sign encoded on the primary scopes per S0004's ownership map: `exclusions/` (PM + architect),
  `ontology/` (architect + PM per its embedded matrix), `policies/` (architect + security where
  applicable). After reconciliation no `knowledge-graph/*.yaml` remains in any authoring role's
  write scope (only the integrator's generated-output scope), so every "X owns Y" line traces to
  exactly one primary scope plus zero-or-more co-sign requirements (S0004 Business Rule 2) and the
  map matches S0004's ownership map exactly (Validation Rule below).
- `agents/actions/feature.md`: G7 = author/update shards + compile + validate; G8 archive = feature
  shard `path:`/`status:` edit + recompile; exit validation includes `--check-reproducible`.
- Prompts: `feature-operator-friendly.md` reconciled; `integrate-operator-friendly.md` exists
  (S0003) and is referenced by the runbook.
- The 2026-07-05 "Enforce generated KG regeneration" surfaces (commit `d18909b`): `build.md`,
  `plan.md`, and the feature/build/plan automation-safe + operator-friendly prompts carry Phase-A
  regeneration commands and authored-file instructions — all reconciled to the compile-driven
  flow. `validate-feature-evidence.py`'s generated-KG command matchers learn `compile.py` (gated
  on a new `contract_effective_date` so earlier evidence stays valid), with tests updated.
- Docs: `KNOWLEDGE-GRAPH.md` (classification, shard schema, compile flow, logical refs, merge
  taxonomy, `depends_on` single-home), `ORCHESTRATION-CONTRACT.md` (integrator role + sole-writer
  rule + routing), `MANUAL-ORCHESTRATION-RUNBOOK.md` (the integration procedure + both human gates
  already landed in S0003; this story adds only the Phase-B compile-flow steps to the maintainer
  procedure — it does not re-author the integration section).
- Templates: `kg-reconciliation`, `feature-assembly-plan`, `tracker-governance`,
  `feature-registry` (generated-region markers), `ci-gates` (S0008 job) — examples use shards and
  logical refs.
- `agents/actions/README.md` + `ROUTER.md` route `integrate`.
- This repo's own `TRACKER-GOVERNANCE.md` notes which product-repo trackers became generated and
  that `nebula-agents` itself has not adopted the shard model (until it does).
- Each edited surface cites the story/PRD section that made the old text wrong (review
  traceability).

## Interaction Contract

N/A — documentation and configuration; no interactive surface.

| Surface / Entry Point | User Action | Editable State | Save / Mutation Result | Reload / Persistence Evidence | Roles / Status Constraints |
|-----------------------|-------------|----------------|-------------------------|-------------------------------|----------------------------|
| Framework docs/templates/map | Role agents read at action time | The inventoried files | Contract text matches shipped behavior | Contract audit checklist in evidence | Architect-owned reconciliation, code-reviewer signoff |

## Data Requirements

**Inputs:** PRD Framework Edit Inventory (authoritative checklist); shipped behavior from
S0001–S0008.
**Outputs:** edited files + a completed audit checklist stored with feature evidence.

**Validation Rules:**
- Zero remaining references to: PM repoint of canonical-nodes/code-index, hand-merge of KG YAML,
  hand-maintained REGISTRY/ROADMAP feature tables (post-S0007), physical feature-doc refs in
  authoring guidance.
- `agent-map.yaml` write scopes match S0004's ownership map exactly.
- The one documented sub-file ownership split is `REGISTRY.md`/`ROADMAP.md`: PM owns the prose (via
  `features/**`), the integrator regenerates the fenced table regions — encoded by the
  `fenced-region` granularity marker in `generated_paths.yaml` (S0008), not by two conflicting
  whole-file scopes. Every other "X owns Y" statement still maps to exactly one whole-path scope.

## Role-Based Visibility

**Roles that read / own the reconciled contract:**
- All role agents (architect, PM, integrator, maintainer, implementers) — read the contract at
  action time; the reconciliation makes each gate's written instruction match shipped behavior.
- Architect — owns the reconciliation; Code Reviewer signs it off.
- `agent-map.yaml` write scopes encode every "X owns Y" statement (testable ownership).

**Data Visibility:** N/A — framework documentation and configuration; no auth surface and no
internal/external data exposure.

## Dependencies

**Depends On:** F0006-S0003 (integrator surfaces), F0006-S0004–S0008 (projection surfaces).
**Related Stories:** All — this is the closing story.

## Business Rules

1. The contract never describes unshipped behavior; docs land with or after their mechanism.
2. Ownership language is testable: every "X owns Y" statement corresponds to an `agent-map.yaml`
   scope or a validator rule.

## Out of Scope

- New behavior (all mechanisms land in S0001–S0008). Historical evidence runs (append-only).
  Retroactive edits to F0038/PR #47 records.

## Non-Functional Expectations

- Audit checklist is re-runnable (grep-able assertions where possible).

## Questions & Assumptions

**Open Questions:**
- [ ] Whether `nebula-agents` should adopt the shard model for its own planning graph in this
      story or a follow-up feature (proposal: follow-up; this repo has no populated KG yet).

**Assumptions (to be validated):**
- The PRD inventory is complete; the audit includes a sweep for uninventoried mentions
  (`grep -ri 'canonical-nodes\|feature-mappings\|code-index\|regenerate-symbols\|regenerate-decisions' agents/`).

## Definition of Done

- [x] Every PRD-inventoried surface edited (agent-map, feature.md, KNOWLEDGE-GRAPH/ORCHESTRATION-CONTRACT/RUNBOOK docs, feature prompts, templates, validate-feature-evidence.py); `audit-contract.py` **clean (zero violations)**
- [x] `agent-map.yaml` scopes verified against S0004 ownership map (no authoring role writes a generated projection; `validate_agent_map.py` green; ownership invariant asserted by the audit)
- [x] Sweep for uninventoried stale references clean (audit stale-phrase sweep over 13 authoring surfaces → 0)
- [x] F0005 gap formally closed in prose (`KNOWLEDGE-GRAPH.md` documents logical `F####/` refs as the only
      authoring form; archive = one shard `path:` edit + recompile; the off-book-repoint narrative is gone)
- [x] Story filename matches `Story ID` prefix
- [x] Story index regenerated or updated (S0009 → Done)
- [~] `validate-feature-evidence.py` learns `compile.py` gated on `contract_effective_date >= 2026-07-11` (+ 4 tests); nebula-agents self-adoption deferred (D-self-adoption, documented in TRACKER-GOVERNANCE)

## Review Provenance

Story-level signoff provenance is recorded in the parent feature `STATUS.md`.

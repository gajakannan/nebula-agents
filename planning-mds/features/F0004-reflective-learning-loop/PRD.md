# F0004 - Reflective Learning Loop and Strategy Playbook PRD

## Feature Header

**Feature ID:** F0004
**Feature Name:** Reflective Learning Loop and Strategy Playbook
**Priority:** High
**Phase:** Context Engineering
**Status:** Draft

## Feature Statement

**As a** framework maintainer running agent-driven builds
**I want** the framework to distill reusable strategies from completed-run evidence and load only the relevant ones back into future sessions
**So that** agents stop repeating mistakes the framework has already seen, without weakening determinism, role boundaries, or the genericness contract.

## Business Objective

- **Goal:** Close the framework's context-engineering loop with a governed `learn -> Write -> Select` sub-loop, so run outcomes improve future runs instead of being discarded after closeout.
- **Metric:** Across a fixed task set, repeated gate-rejection categories decline run-over-run while loaded prompt context stays inside the existing §13.3 input budget.
- **Baseline:** Role `SKILL.md` files are static, hand-authored, and version-bumped manually; the "Write" move externalizes session state and decisions (`workstate.py`, `KG-DECISION`, `STATUS.md`) but never produces generalizable strategy, and "Select" never loads strategy back. Retrospectives exist only as human-facing blogger output and leave agent working memory immediately.
- **Target:** A `reflect` action mines existing run evidence and proposes approval-gated edits to a scoped Strategy Playbook (`LEARNINGS.md`); the Select/Compress moves load task-matched, budget-bounded strategies into later sessions.

## Problem Statement

- **Current State:** The framework observes runs (telemetry via `eval.py`, evidence per `AGENT-OPS.md`, gate outcomes) but does not adapt from them. The same review-rejection reason, the same context-budget overrun, and the same dead-end approach can recur across sessions with nothing carrying the lesson forward.
- **Desired State:** Completed-run evidence is reflected into candidate strategies, curated under human approval into a mutable playbook, and selectively reloaded — a real learning loop layered onto the four context-engineering moves already named in `agents/docs/CONTEXT-ENGINEERING.md`.
- **Impact:** Agents get measurably more consistent on recurring work without fine-tuning, new dependencies, or loss of the framework's "plain markdown plus small Python validators" identity.

## Scope & Boundaries

**In Scope:**
- A scoped Strategy Playbook artifact (`LEARNINGS.md`) with a validated per-entry schema and a framework-vs-product scope split.
- A `reflector` role that performs deterministic, script-assisted analysis of existing run evidence and emits a candidate-strategy set.
- A `reflect` action that composes reflection, curation, and an operator approval gate; mutations land only as approved diffs.
- A curation lifecycle (`ADD` / `UPDATE` / `REMOVE` / `MERGE`) with usage and success counters, decay/retirement, and ID/topic supersession reusing existing `workstate.py --supersedes` semantics.
- Strategy selection and context load-back integrated with `ROUTER.md`, the cache tiers, and the input budget.
- A `learnings_governance` lifecycle gate enforcing genericness and scope boundaries on every playbook change.

**Out of Scope:**
- Any automatic, un-approved mutation of `SKILL.md` role contracts (the playbook is a separate artifact; SKILL.md stays the static contract).
- Embedding/vector-similarity dedup or any vector database dependency.
- Model fine-tuning, weight updates, or training-data collection.
- Cross-organization or hosted/shared playbooks; the playbook is local to a workspace.
- Replacing the blogger retrospective (human narrative) — that output remains, but is no longer the only place lessons live.
- Reflecting from raw source diffs without evidence; reflection consumes the existing evidence/telemetry contract, not ad-hoc repo scraping.

## Acceptance Criteria Overview

- [ ] A `LEARNINGS.md` entry schema exists and is enforced by `validate-learnings.py` (required fields, unique IDs, legal status/scope values).
- [ ] Framework-scope strategies live in `agents/<role>/LEARNINGS.md`; product-scope strategies live under `{NEBULA_PRODUCT_ROOT}/planning-mds/learnings/`; neither file may hold the other scope.
- [ ] The `reflector` role produces a candidate-strategy set from existing evidence without mutating the playbook.
- [ ] The `reflect` action presents proposed `ADD`/`UPDATE`/`REMOVE`/`MERGE` operations at an approval gate; only operator-approved operations are applied.
- [ ] Applied entries carry provenance (run-id + action + gate outcome) and maintained `used_count` / `success_count`.
- [ ] Selection returns only task-matched strategies and respects the §13.3 input budget; load-back lands in the stable cache tiers, not the per-turn tail.
- [ ] The `learnings_governance` gate fails when a framework-scope entry contains denylisted domain terms or when scope placement is violated.

## UX / Screens

This feature has no graphical UI. Its only human surface is the operator-facing **approval gate** during the `reflect` action, rendered in the terminal (TUI or CLI), consistent with how F0001/F0002 render gate decisions. ASCII layouts for that surface and for the loop architecture are provided below per the PM ASCII-layout requirement.

| Surface | Purpose | Key Actions |
|---------|---------|-------------|
| Reflect Summary | Show candidate strategies distilled from a run's evidence. | Inspect candidates, drill into provenance. |
| Curation Diff Gate | Show proposed `ADD`/`UPDATE`/`REMOVE`/`MERGE` operations as a reviewable diff. | Approve, hold, edit, or reject each operation. |
| Playbook Inspector | Show active strategies for a role/scope with counters. | Filter by role/scope, inspect decay/retire candidates. |

**Key Workflows:**
1. Reflect — operator runs `reflect` after a `build`/`feature`/`review` run; the reflector analyzes existing evidence and surfaces candidates.
2. Curate — proposed playbook operations are shown as a diff at an approval gate.
3. Approve — operator approves/holds/edits operations; approved ones are applied with provenance.
4. Select — a later session loads only task-matched strategies within budget before work begins.

## Architecture / How It Works (ASCII)

```text
 EXISTING ACTIONS (unchanged - already emit evidence + telemetry)
 plan  .  build  .  feature  .  review  .  test
        |
        |  (1) role agent runs; SKILL.md stays the STATIC contract
        v
 +-------------------------------+
 |  RUN EVIDENCE / TELEMETRY     |   already produced today
 |  - latest-run.json            |     AGENT-OPS evidence contract
 |  - eval.py telemetry          |     tokens, run-id, cache spikes
 |  - gate outcomes              |     review REJECT reasons
 |  - workstate.py digest        |     decisions / escalations / thrash
 +---------------+---------------+
                 |  (2) reflect action mines outcomes (incl. failures + path)
                 v
 +=========================================================================+
 |  NEW ACTION: reflect            (runs AFTER gates, never inside them)    |
 |-------------------------------------------------------------------------|
 |   [A] reflector role     deterministic, script-assisted trace analysis  |
 |                          -> "this REJECT class recurs across N runs"     |
 |                                   |                                       |
 |                                   v                                       |
 |   [B] curation step      ADD / UPDATE / REMOVE / MERGE proposed ops      |
 |                          used_count / success_count . decay stale        |
 |                          reuses workstate.py decision --supersedes        |
 |                                   |                                       |
 |                                   v                                       |
 |   [C] APPROVAL GATE      proposes a DIFF; operator approves/holds/edits  |
 |                          framework-scope ops must pass genericness        |
 +==================================+======================================+
                                    |  (3) approved strategy diff only
                                    v
 +-------------------------------------------------------------------------+
 |  STRATEGY PLAYBOOK  (LEARNINGS.md - mutable, scoped)                     |
 |   FRAMEWORK scope -> agents/<role>/LEARNINGS.md    (denylist-clean)      |
 |   PRODUCT  scope -> {NEBULA_PRODUCT_ROOT}/planning-mds/learnings/               |
 |   entry: { id . scope . role . trigger . strategy . provenance .        |
 |            status . supersedes . used_count . success_count }            |
 +----------------------------------+--------------------------------------+
                                    |  (4) Select + Compress (load back)
                                    |     ROUTER-style task gating
                                    |     -> stable cache tier, NOT a dump
                                    v
                        +---------------------------+
                        |  next session: role agent  |
                        |  prompt carries only the   |
                        |  task-matched strategies   |
                        +---------------------------+
                                    |
                                    +---> back to (1)
```

## Screen Layouts (ASCII)

### Curation Diff Gate - Terminal (wide)

```text
+----------------------------------------------------------------------+
| reflect  -  F0004 curation gate          run: 2f7c..  role: reviewer |
+----------------------------------------------------------------------+
| Proposed playbook operations (3)                                     |
|                                                                      |
|  [1] ADD     LRN-reviewer-0007  scope: framework                     |
|       trigger: PR touches auth + missing // WHY marker               |
|       strategy: require WHY marker evidence before approving auth    |
|                 changes; cite kg risk band in the review note        |
|       provenance: run 2f7c (review) gate=REJECT x4                   |
|       [a]pprove  [h]old  [e]dit  [r]eject                            |
|                                                                      |
|  [2] MERGE    LRN-reviewer-0004 <- LRN-reviewer-0006                 |
|       reason: near-duplicate trigger; counters accumulate            |
|       [a]pprove  [h]old  [e]dit  [r]eject                            |
|                                                                      |
|  [3] REMOVE   LRN-backend-0002   used_count=0 over 12 runs           |
|       reason: decayed - never selected since created 2026-05         |
|       [a]pprove  [h]old  [e]dit  [r]eject                            |
+----------------------------------------------------------------------+
| genericness: PASS   scope: PASS   budget delta: +0.4% input          |
| [A]pprove all   [H]old all   [w]rite approved   [q]uit (no change)   |
+----------------------------------------------------------------------+
```

### Reflect Summary - Terminal (narrow)

```text
+------------------------------+
| reflect summary  run 2f7c    |
| candidates: 3                |
|  + 1 add  . 1 merge  . 1 rm  |
| evidence: review REJECT x4   |
| budget delta: +0.4% input    |
| [enter] open curation gate   |
+------------------------------+
```

## Data Requirements

**Core Records:**
- `strategy_id`: Stable identifier `LRN-<role>-<NNNN>`.
- `scope`: `framework` or `product`.
- `role`: Owning role slug, or `cross` for multi-role strategies.
- `trigger`: The task/phase/keywords that make the strategy relevant for selection.
- `strategy`: The imperative, generalizable lesson text.
- `provenance`: Originating run-id(s), action, and gate outcome that justified the entry.
- `status`: `candidate`, `active`, `superseded`, or `retired`.
- `supersedes`: Prior `strategy_id` this entry replaces, or `none`.
- `used_count` / `success_count`: Selection and positive-outcome counters.
- `proposed_operation`: `ADD`, `UPDATE`, `REMOVE`, or `MERGE` (curation-time only).

**Validation Rules:**
- `strategy_id` is unique within a playbook file and never reused after retirement.
- `framework`-scope entries must pass `validate-genericness.py`; `product`-scope entries are forbidden in `agents/**`.
- Every `active` entry has non-empty `trigger`, `strategy`, and at least one `provenance` run-id.
- Counter and status changes are append-only in evidence and traceable to an approved curation operation.

## Role-Based Access

| Role | Access Level | Notes |
|------|--------------|-------|
| Local Operator | Run `reflect`, inspect candidates, approve/hold/edit/reject curation operations, write approved diffs | Same local-shell trust boundary as F0001. |
| Reviewer | Inspect playbook entries and curation evidence; recommend hold on framework-scope promotions | Cannot self-approve a promotion they authored. |
| Architect | Approve promotion of `framework`-scope strategies and changes to selection/budget thresholds | Required when a strategy changes a role's standing guidance. |
| Role Agents | Read-only consumers of selected strategies at session start | Never write the playbook directly; only `reflect` writes, behind the gate. |

## Success Criteria

- A `reflect` run on real evidence produces at least one correctly-scoped, genericness-clean candidate with valid provenance.
- Approved operations apply atomically and are rejected as a set if the governance gate fails.
- Selection demonstrably loads only task-matched strategies and keeps the loaded prefix within the input budget.
- Over a repeated task set, a tracked rejection category decreases while no genericness or scope regression is introduced.
- No path exists by which the loop mutates a `SKILL.md` or applies an operation the operator did not approve.

## Risks & Assumptions

- Risk: Playbook bloat inflates the cached prefix. Mitigation: counters + decay + budget delta shown at the gate; selection is task-matched, not whole-file.
- Risk: A learned strategy encodes a domain-specific lesson into a generic agent. Mitigation: genericness gate on framework scope; product lessons forced to `{NEBULA_PRODUCT_ROOT}`.
- Risk: Non-determinism from evolving guidance. Mitigation: human approval gate, provenance, and supersession audit — no silent mutation.
- Risk: Reflection overfits to a single noisy run. Mitigation: recurrence threshold across runs before a candidate is proposed for promotion.
- Assumption: Existing evidence/telemetry (`latest-run.json`, `eval.py`, gate outcomes) is sufficient input for useful reflection.
- Assumption: ID/topic supersession is adequate dedup without embeddings for the expected playbook size.

## Dependencies

- `agents/docs/CONTEXT-ENGINEERING.md` four-move model (Select/Compress/Write/Isolate) — this feature adds the missing learn sub-loop.
- `agents/docs/AGENT-OPS.md` evidence contract and `eval.py` telemetry — the reflection input surface.
- `workstate.py` decision/`--supersedes` semantics — reused for curation supersession.
- `agents/scripts/validate-genericness.py` and `lifecycle-stage.yaml` gate runner — reused for governance.
- `agents/ROUTER.md` task routing — extended for strategy selection.

## Related Stories

- [F0004-S0001](./F0004-S0001-strategy-playbook-artifact-and-schema.md) - Strategy playbook artifact and entry schema
- [F0004-S0002](./F0004-S0002-reflector-role-and-trace-analysis.md) - Reflector role and trace analysis
- [F0004-S0003](./F0004-S0003-reflect-action-and-approval-gate.md) - Reflect action and approval-gated curation
- [F0004-S0004](./F0004-S0004-curation-lifecycle-and-decay.md) - Curation lifecycle, counters, and supersession
- [F0004-S0005](./F0004-S0005-strategy-selection-and-load-back.md) - Strategy selection and context load-back
- [F0004-S0006](./F0004-S0006-boundary-and-genericness-gate.md) - Boundary, genericness, and lifecycle-gate enforcement

## Rollout & Enablement

- Ship behind an explicit, default-off enablement flag; the loop only runs when an operator invokes `reflect`.
- Begin with `candidate`-only output (no auto-promotion) until a maintainer accepts the first promotions by hand.
- Keep framework-scope promotion gated on Architect signoff until genericness behavior is proven on real runs.
- Selection load-back starts as opt-in per role and graduates to default only after budget-delta evidence shows it stays within §13.3.

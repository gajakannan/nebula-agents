# F0004 - Feature Assembly Plan (Architect, Phase B)

**Feature:** F0004 - Reflective Learning Loop and Strategy Playbook
**Author role:** Architect
**Status:** Drafted
**Last Updated:** 2026-06-23

> Framework feature. Deliverables are markdown contracts, Python validators/curator
> scripts, and gate wiring under `agents/**` and `lifecycle-stage.yaml` — not product
> application code. This plan adapts the standard per-feature execution plan to that
> reality: file tables, CLI/function signatures, logic flows, traceability, and
> integration checkpoints, but no C#/EF-Core layers.

## 1. Architectural Summary

F0004 layers a governed `learn -> Write -> Select` sub-loop onto the four
context-engineering moves already defined in `agents/docs/CONTEXT-ENGINEERING.md`.
It introduces one new artifact (`LEARNINGS.md`), one new role (`reflector`), one new
action (`reflect`), two new scripts (`playbook.py`, `validate-learnings.py`), and one
new lifecycle gate (`learnings_governance`). Everything else is reuse: evidence and
telemetry (`AGENT-OPS.md`, `eval.py`), supersession (`workstate.py --supersedes`),
genericness (`validate-genericness.py`), routing (`ROUTER.md`), and the gate runner
(`run-lifecycle-gates.py`).

The defining constraint is that an *adaptive* loop must live inside a *deterministic,
boundary-enforced* framework. Three design choices satisfy that: (a) every mutation is
an operator-approved diff; (b) strategy is physically scope-split and genericness-gated;
(c) dedup is ID/topic supersession, not embeddings — preserving the "markdown plus small
Python validators" identity with zero new runtime dependencies.

## 2. Component Boundary (C4 L3 — Component, ASCII companion)

```text
                         +-------------------------------------------+
                         |             reflect action                |
                         |          (agents/actions/reflect.md)      |
                         |                                           |
   evidence/telemetry -->|  reflector role  --candidates-->  curate  |
   (read-only)           |  (agents/reflector/SKILL.md)      step    |
                         |                                    |      |
                         |                          approval gate    |
                         +----------------------------+--------------+
                                                      | approved ops
                                                      v
   +----------------+    select/record-outcome   +--------------------------+
   | role agent     |<---------------------------|   playbook.py (curator)  |
   | (next session) |    task-matched slice      |   apply/select/counters  |
   +----------------+                            +------------+-------------+
                                                              | read/write (gated)
                                                              v
                              +-----------------------------------------------+
                              |  LEARNINGS.md  (scoped strategy playbook)     |
                              |  framework: agents/<role>/LEARNINGS.md        |
                              |  product:   {NEBULA_PRODUCT_ROOT}/planning-mds/      |
                              |             learnings/                        |
                              +-----------------------+-----------------------+
                                                      ^
                                                      | validates (fail-closed)
                       +------------------------------+------------------------------+
                       | validate-learnings.py  +  validate-genericness.py (fwk)     |
                       | wired as gate: learnings_governance (lifecycle-stage.yaml)  |
                       +-------------------------------------------------------------+
```

## 3. New and Modified Files

### 3.1 New files

| Path | Kind | Owner story | Purpose |
|------|------|-------------|---------|
| `agents/reflector/SKILL.md` | Role contract | S0002 | Reflector role: read-only trace analysis -> candidate set |
| `agents/reflector/references/` | References | S0002 | Generic analysis references (recurrence, pattern kinds) |
| `agents/actions/reflect.md` | Action flow | S0003 | Compose reflect -> curate -> approval gate |
| `agents/scripts/playbook.py` | Curator CLI | S0004/S0005 | reflect/curate/apply/select/record-outcome |
| `agents/scripts/validate-learnings.py` | Validator | S0001 | Schema, unique-id, scope, status checks |
| `agents/scripts/tests/test_playbook.py` | Tests | S0004/S0005 | Curator + selection unit tests |
| `agents/scripts/tests/test_validate_learnings.py` | Tests | S0001/S0006 | Schema + scope + genericness gate tests |
| `agents/templates/prompts/reflect-automation-safe.md` | Prompt template | S0003 | Automation-safe reflect prompt |
| `agents/templates/prompts/reflect-operator-friendly.md` | Prompt template | S0003 | Operator-friendly reflect prompt |
| `agents/templates/learnings-entry-template.md` | Template | S0001 | Canonical playbook entry shape |
| `agents/<role>/LEARNINGS.md` | Artifact (per role, seeded empty) | S0001 | Framework-scope strategy playbook |

### 3.2 Modified files

| Path | Change | Owner story |
|------|--------|-------------|
| `lifecycle-stage.yaml` | Add `learnings_governance` gate to all four stages + `gates:` block | S0006 |
| `agents/ROUTER.md` | Add strategy-selection routing entry | S0005 |
| `agents/agent-map.yaml` | Register `reflector` role + `reflect` action with model-tier/execution | S0002/S0003 |
| `agents/actions/README.md` | Catalogue `reflect` in the action index | S0003 |
| `agents/docs/CONTEXT-ENGINEERING.md` | Add the learn sub-loop under the Write/Select moves; remove the matching "Known gap" | S0005 |
| `{NEBULA_PRODUCT_ROOT}/.agentignore` (product-side, optional) | Keep `learnings/` warm (not cold-archived) | S0005 |

## 4. Script Signatures (`playbook.py`)

```text
playbook.py reflect        --run-id RUN_ID --role ROLE [--threshold N]
                           -> writes candidates file (no playbook mutation)

playbook.py curate         --from-candidates FILE
                           -> emits proposed ops (ADD|UPDATE|REMOVE|MERGE) for the gate

playbook.py apply          --approved FILE
                           -> atomically applies approved ops; writes provenance + audit

playbook.py select         --role ROLE --task "TEXT" [--budget-pct N]
                           -> returns task-matched active entries within budget (read-only)

playbook.py record-outcome --strategy-id ID --run-id RUN_ID --success BOOL
                           -> increments used_count/success_count append-only
```

```text
validate-learnings.py [paths...] [--scope framework|product] [--glossary FILE]
   exit 0  -> all entries valid, scoped, (framework) genericness-clean
   exit 1  -> schema / unique-id / scope / status / genericness violation (names entry)
```

## 5. Entry Schema (canonical)

```text
### LRN-<role>-<NNNN>
- scope: framework | product
- role: <role-slug> | cross
- status: candidate | active | superseded | retired
- trigger: <task/phase/keywords that make this relevant to selection>
- strategy: <imperative, generalizable lesson>
- provenance: <run-id(s)> | <action> | <gate outcome>
- supersedes: <LRN-id> | none
- used_count: <int>   success_count: <int>
- created: <ISO date>   last_used: <ISO date>
```

Rendered directly into prompts during selection (Compress: a slice, not the file).

## 6. Logic Flows

### 6.1 `apply` (gated mutation) — S0003/S0004

1. Load approved-ops file; assert every op `approval_state == approved`.
2. For framework-scope ops, run `validate-genericness.py` on the strategy text; on any
   hit, abort the whole set (fail closed).
3. Resolve `MERGE`: pick survivor, accumulate `used_count`/`success_count`, set the other
   `superseded` with `supersedes` linkage (mark, do not delete).
4. Apply `ADD`/`UPDATE`/`REMOVE` to the scoped file in a temp buffer.
5. Run `validate-learnings.py` on the buffer; on failure, roll back (no partial write).
6. Atomically replace the file; append an audit/timeline record (approver, ops, provenance).

### 6.2 `select` (read-only + counter) — S0005

1. Load `active` entries for `role` plus `cross`.
2. Score by `trigger` match against task (ROUTER-assisted) blended with `success_count`.
3. Greedily fill up to `budget-pct` of the input budget; record `dropped_ids`.
4. Place the slice in a stable cache tier (never the per-turn tail).
5. Call `record-outcome --success=false` provisionally on selection to bump `used_count`;
   the real success bit is set when the consuming run's gate resolves.

### 6.3 `learnings_governance` gate — S0006

1. `validate-learnings.py` on all playbook files (schema/scope/status). Fail closed.
2. `validate-genericness.py` on framework-scope strategy text only.
3. Scope-placement check: no product entry in `agents/**`; no framework entry referencing
   a product path or `{NEBULA_PRODUCT_ROOT}` literal.
4. Exit non-zero on any violation, naming entry + reason.

## 7. Mutation Traceability

| Story interaction (mutation verb) | Entry point | Command/step | Carrier | Authorization | Concurrency | Validation failure | Audit/timeline | Test |
|---|---|---|---|---|---|---|---|---|
| Approve curation op (S0003) | Curation diff gate | `playbook.py apply --approved` | `LEARNINGS.md` entry | Operator (product) / Architect (framework promotion); no self-approval | Atomic set apply; rollback on validate fail | Op blocked at gate; cannot approve until edited+revalidated | Approval record (approver, ops, provenance) | `test_validate_learnings`, action e2e |
| Apply curation (S0004) | `playbook.py apply` | temp buffer -> validate -> atomic swap | entry status/counters/supersedes | Gated apply path only | Last-writer rejected on conflict | Roll back; no partial playbook | apply/merge/retire records | `test_playbook` |
| Record outcome (S0004/S0005) | `playbook.py record-outcome` | counter increment | `used_count`/`success_count` | Runtime, tied to run-id | Append-only | Ignored+logged if entry retired | counter event w/ run-id | `test_playbook` |
| Select strategies (S0005) | `playbook.py select` | scored slice | counters only | Role read scope (own + cross) | Deterministic | Over-budget -> drop lowest-value, report | selection event w/ run-id | `test_playbook` |

If any link above cannot be satisfied during implementation, stop and raise a clarifying
question before kickoff (per Architect responsibility #10 mutation-traceability rule).

## 8. Architecture Decision Record

### ADR F0004-001 — Governed, scope-split, embedding-free learning loop

**Status:** Proposed

**Context.** The framework observes runs but never adapts from them; `SKILL.md` is static
and the Write move never distills reusable strategy. We want a learning loop without
breaking determinism, the framework/product boundary, or the "markdown + small validators"
identity.

**Decision.**
1. Strategy lives in a new `LEARNINGS.md` artifact, never in `SKILL.md`.
2. Every mutation is an operator-approved diff behind an approval gate; no silent writes.
3. Strategy is physically scope-split (framework vs product) and framework scope is
   genericness-gated via the existing denylist.
4. Dedup/replacement is ID/topic supersession reusing `workstate.py --supersedes`; no
   embeddings, no vector store.
5. Selection loads a task-matched slice into a stable cache tier within the §13.3 budget.

**Consequences.**
- (+) Adaptive behavior with zero new runtime dependencies and no boundary erosion.
- (+) Auditable, reversible, human-in-the-loop evolution of guidance.
- (-) Lower-recall dedup than embeddings at large scale; acceptable at expected sizes.
- (-) Requires operator effort per promotion until recurrence-threshold auto-promotion is
  trusted (deliberately deferred; candidate-only at launch).

**Alternatives considered.** Auto-mutating `SKILL.md` (rejected: breaks determinism and the
static-contract role); embedding-based curation (rejected: new dependency, against identity);
folding learning into the `review` action (rejected: review is product-scoped, instance-scoped,
and stateless — wrong subject, target, and lifetime for cross-session strategy).

## 9. Integration Checkpoints

| Checkpoint | Criterion (testable) | Owner story |
|------------|----------------------|-------------|
| C1 Schema | `validate-learnings.py` passes valid fixture; fails each of: dup id, scope violation, bad status, dangling supersedes | S0001 |
| C2 Reflector | Reflector emits >=1 provenance-bearing candidate from a REJECT-recurring run; 0 candidates on missing evidence | S0002 |
| C3 Gate apply | Approved `ADD` persists with provenance+counters; rejected ops leave no trace; apply is atomic | S0003 |
| C4 Curation | MERGE accumulates counters; decay proposes retire (not delete); scope-change rejected | S0004 |
| C5 Selection | Only `active` task-matched entries return; budget bound respected; no per-turn cache spike | S0005 |
| C6 Governance | `learnings_governance` fails on denylisted framework term and on misplaced scope; fails closed | S0006 |
| C7 Boundary | No `SKILL.md` modified by any step; `validate-genericness.py` + `skill_regression` + `agent_map_schema` still pass | all |

## 10. Sequencing and Handoffs

- **Build order:** S0001 -> S0002 -> S0003 -> S0004 -> S0005, with S0006 landing alongside
  S0003 (the gate must exist before the first framework-scope apply).
- **Backend/devops:** `playbook.py` and validators are pure-Python, reuse
  `agents/scripts/_product_root.py` and the existing test harness; gate wiring is a
  `lifecycle-stage.yaml` edit consumed by `run-lifecycle-gates.py`.
- **QA:** owns C1–C7; treats `agents/scripts/tests/` as the home for unit tests.
- **Security:** reviews evidence-read scope (honors `.agentignore`/cold-archive), the
  approval-write boundary, provenance redaction, and scope isolation.
- **Docs:** update `CONTEXT-ENGINEERING.md` to fold the loop in and retire the matching
  "Known gap"; catalogue the action in `actions/README.md`.

## 11. Framework vs Product Workstream Split

- **Framework (`agents/**`, `lifecycle-stage.yaml`):** role, action, scripts, gate, templates,
  framework-scope `LEARNINGS.md`. Subject to genericness.
- **Product (`{NEBULA_PRODUCT_ROOT}/planning-mds/learnings/`):** product-scope playbook content and
  any product-side `.agentignore` warm-listing. Domain terms allowed here only.
- Do not close a discovered framework gap by editing product docs or vice versa
  (Architect responsibility #12).

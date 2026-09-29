# F0004 - Reflective Learning Loop and Strategy Playbook - Getting Started

## Prerequisites

- [ ] At least one completed `build`, `feature`, or `review` run with evidence under `{NEBULA_PRODUCT_ROOT}/planning-mds/operations/evidence/` (the reflection input surface).
- [ ] `eval.py` telemetry available for the runs being reflected (token estimates and run-ids stamped per `AGENT-OPS.md`).
- [ ] `validate-genericness.py` and the `lifecycle-stage.yaml` gate runner working locally (existing framework gates).
- [ ] Decision on initial scope policy: which roles start with selection load-back enabled.

## Services to Run

F0004 is a framework capability, not a service. It runs as an action plus validators. Commands follow this shape:

```bash
# Distill candidate strategies from a completed run's evidence (no playbook mutation).
python3 agents/scripts/playbook.py reflect --run-id <RUN_ID> --role <role>

# Curate: present proposed ADD/UPDATE/REMOVE/MERGE operations at the approval gate.
python3 agents/scripts/playbook.py curate --from-candidates <CANDIDATES_FILE>

# Apply only operator-approved operations, writing provenance and counters.
python3 agents/scripts/playbook.py apply --approved <APPROVED_FILE>

# Select task-matched strategies for a session (read-only; respects input budget).
python3 agents/scripts/playbook.py select --role <role> --task "<task summary>"

# Validate the playbook artifact (schema, unique IDs, scope, status).
python3 agents/scripts/validate-learnings.py
```

The operator-facing path is the `reflect` action (`agents/actions/reflect.md`), which composes the steps above and renders the curation diff gate.

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `NEBULA_AGENTS_LEARNING_ENABLED` | Master switch; the loop only runs when set. | `false` |
| `NEBULA_AGENTS_LEARNING_AUTOPROMOTE` | Allow `candidate -> active` without a per-entry approval (still gated overall). | `false` |
| `NEBULA_AGENTS_LEARNING_SELECT_ROLES` | Comma-separated roles with selection load-back enabled. | `` (none) |
| `NEBULA_AGENTS_LEARNING_BUDGET_PCT` | Max share of input budget the loaded playbook slice may consume. | `5` |

## Seed Data

Use real completed-run evidence as input, not synthetic fixtures, so distilled strategies reflect genuine recurring outcomes. For tests, commit a small set of redacted evidence packages and a frozen `LEARNINGS.md` fixture per scope under the feature's test assets.

## How to Verify

1. Run `playbook.py reflect` against a run whose `review` gate produced a repeated REJECT category; confirm a matching candidate is surfaced with provenance.
2. Open the curation gate; confirm proposed operations render as a reviewable diff and nothing is written until you approve.
3. Approve one `ADD`; confirm the entry lands in the correct scoped file with `status: active`, counters initialized, and provenance recorded.
4. Run `validate-learnings.py` and the `learnings_governance` gate; confirm a deliberately domain-specific framework-scope entry fails genericness.
5. Run `playbook.py select` for a matching task; confirm only relevant strategies return and the budget delta stays within `NEBULA_AGENTS_LEARNING_BUDGET_PCT`.
6. Confirm no `SKILL.md` file was modified by any step.

## Key Files

| Layer | Path | Purpose |
|-------|------|---------|
| Planning | `planning-mds/features/F0004-reflective-learning-loop/PRD.md` | Requirements and loop architecture |
| Planning | `planning-mds/features/F0004-reflective-learning-loop/feature-assembly-plan.md` | Phase B execution plan + ADR |
| Framework (planned) | `agents/actions/reflect.md` | The reflect action flow |
| Framework (planned) | `agents/reflector/SKILL.md` | The reflector role contract |
| Framework (planned) | `agents/scripts/playbook.py` | Curator: reflect/curate/apply/select |
| Framework (planned) | `agents/scripts/validate-learnings.py` | Playbook schema and scope validator |
| Framework (planned) | `agents/<role>/LEARNINGS.md` | Framework-scope strategy playbook |
| Product (planned) | `{NEBULA_PRODUCT_ROOT}/planning-mds/learnings/` | Product-scope strategy playbook |
| Reused | `agents/docs/CONTEXT-ENGINEERING.md` | The four-move model this loop extends |
| Reused | `lifecycle-stage.yaml` | Where the `learnings_governance` gate is wired |

## Notes

- The playbook is never an autonomous writer: only the gated `apply` step mutates it, and only with operator-approved operations.
- Keep framework-scope strategies generic — they are subject to the same denylist as every other `agents/**` file.
- Selection is a retrieval aid, not the source of truth; on conflict, the role `SKILL.md` contract wins, consistent with the KG source-precedence rule.

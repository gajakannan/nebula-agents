# F0007 - Spec-Driven Orchestration and Prompt Compilation - Getting Started

## Current State

F0007 is planned. The commands below define the intended developer interface and become executable
as their owning stories land. Until S0009 completes, existing action prompts and validators remain
authoritative for live runs.

## Prerequisites

- Python 3 with `agents/scripts/requirements.txt` installed.
- A clean framework checkout for prompt drift comparisons.
- A disposable product-root fixture for initialization, locking, and evidence validation tests.
- Historical evidence fixtures covering the 2026-05-19, 2026-05-25, 2026-06-01, 2026-07-05,
  and 2026-07-11 policy cutovers.

## Planned Commands

```bash
python3 agents/scripts/validate_action_specs.py
python3 agents/scripts/validate_action_specs.py --contract-diff origin/main..HEAD
python3 agents/scripts/render-prompts.py --check
python3 agents/scripts/init-run.py --action feature --feature F0007 --product-root PATH
python3 agents/scripts/run-gate.py --action feature --stage G0 --product-root PATH --feature F0007 --run-id RUN_ID
python3 agents/scripts/exec-and-log.py --log RUN_FOLDER/commands.log --product-root PATH --cwd product -- command arg
```

## Development Sequence

1. Implement and validate S0001-S0002 before adding any runtime consumer.
2. Keep existing validator constants active while S0003-S0006 are developed.
3. Generate only the feature prompt pair first; inspect its semantic diff manually.
4. Enable dual-read validator mode in S0007 and resolve all disagreements.
5. Thin prose in S0008 after generation and validation are independently green.
6. Run the S0009 pilot only on a newly initialized run; never change contract versions mid-run.

## Verification

```bash
python3 agents/product-manager/scripts/validate-stories.py --product-root . --strict-warnings planning-mds/features/F0007-spec-driven-orchestration-and-prompt-compilation
python3 agents/product-manager/scripts/validate-trackers.py --product-root . --skip-feature-evidence
python3 agents/scripts/run-lifecycle-gates.py
```

The F0007-specific completion gate additionally requires:

- Historical fixture verdict matrix unchanged.
- Prompt generation byte-identical on two consecutive runs.
- No executable string command accepted by the schema.
- Concurrent run initialization yields exactly one successful creator.
- Unattested checkpoint resume is rejected.
- One end-to-end governed pilot passes closeout.

## Key Files

| Layer | Path | Purpose |
|-------|------|---------|
| Design | `agents/docs/PROSE-TO-SPEC-MIGRATION.md` | Accepted migration design |
| Policy | `agents/actions/spec/` | Active and historical action contracts |
| Runtime | `agents/scripts/gate_runtime.py` | Shared typed execution engine |
| Generation | `agents/scripts/render-prompts.py` | Prompt compiler and drift check |
| Validation | `agents/scripts/validate_action_specs.py` | Structural, semantic, and diff validation |
| Evidence | `agents/product-manager/scripts/validate-feature-evidence.py` | Version-aware evidence validation |

## Rollback

- Before S0009, disable new lifecycle gates and keep hand-written prompts/current constants active.
- After S0009, select the previous active policy version and regenerate prompts; do not edit a
  published historical bundle.
- Never roll back by changing `contract_version` in existing evidence manifests.

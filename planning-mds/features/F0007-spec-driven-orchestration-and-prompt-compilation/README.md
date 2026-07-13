# F0007 - Spec-Driven Orchestration and Prompt Compilation

**Status:** Planned
**Priority:** Critical
**Phase:** Framework Hardening

## Overview

Nebula Agents currently expresses the orchestration contract in action prose, evidence prompts,
role skills, validators, and prose-alignment checks. The same fixed rules are paraphrased across
many files, so policy changes consume prompt context and can drift without a structural diff.

F0007 makes a versioned action specification the policy source, scripts the deterministic
execution layer, generated prompts the presentation layer, and hand-written prose the judgment
layer. It preserves historical evidence semantics, uses typed shell-free operations, and keeps
independent conformance fixtures so a generated system cannot become consistently wrong.

The source design is
[`agents/docs/PROSE-TO-SPEC-MIGRATION.md`](../../../agents/docs/PROSE-TO-SPEC-MIGRATION.md).

## Delivery Shape

```text
versioned action policy
        |
        +--> generated evidence prompts + drift check
        +--> typed gate runtime + durable checkpoints
        +--> version-aware evidence validators
        +--> symbolic threshold/configuration consumers
        |
independent historical fixtures + semantic invariants
```

## Documents

| Document | Purpose |
|----------|---------|
| [PRD.md](./PRD.md) | Requirements, boundaries, compatibility model, and success measures |
| [feature-assembly-plan.md](./feature-assembly-plan.md) | Build order, file inventory, decisions, checkpoints, and traceability |
| [STATUS.md](./STATUS.md) | Story state, required roles, and signoff provenance |
| [GETTING-STARTED.md](./GETTING-STARTED.md) | Planned commands, prerequisites, and verification flow |

## Stories

| ID | Title | Status |
|----|-------|--------|
| [F0007-S0001](./F0007-S0001-versioned-action-policy-and-schema.md) | Versioned action policy and schema | Not Started |
| [F0007-S0002](./F0007-S0002-contract-conformance-and-behavioral-diff.md) | Contract conformance and behavioral diff | Not Started |
| [F0007-S0003](./F0007-S0003-run-initialization-and-product-scaffolding.md) | Run initialization and product scaffolding | Not Started |
| [F0007-S0004](./F0007-S0004-typed-command-runtime-and-telemetry.md) | Typed command runtime and complete telemetry | Not Started |
| [F0007-S0005](./F0007-S0005-gate-driver-checkpoints-and-severity-policy.md) | Gate driver, durable checkpoints, and severity policy | Not Started |
| [F0007-S0006](./F0007-S0006-generated-evidence-prompts-and-drift-gate.md) | Generated evidence prompts and drift gate | Not Started |
| [F0007-S0007](./F0007-S0007-version-aware-validator-convergence.md) | Version-aware validator convergence | Not Started |
| [F0007-S0008](./F0007-S0008-shared-policy-consumers-and-prose-thinning.md) | Shared policy consumers and prose thinning | Not Started |
| [F0007-S0009](./F0007-S0009-governed-rollout-and-compatibility-pilot.md) | Governed rollout and compatibility pilot | Not Started |

**Total Stories:** 9
**Completed:** 0 / 9

## Phasing

| Phase | Stories | Exit Gate |
|-------|---------|-----------|
| A - Policy foundation | S0001-S0002 | Versioned policy validates; historical fixtures retain their baseline verdicts; behavioral diff is reviewable |
| B - Deterministic runtime | S0003-S0005 | Run creation, typed execution, telemetry, severity arithmetic, and checkpoint resume pass concurrency and failure tests |
| C - Compilation and convergence | S0006-S0008 | Prompts reproduce accepted semantics; validators dual-read without disagreement; policy literals are consolidated |
| D - Rollout | S0009 | One governed feature run completes end-to-end without mixed prose/script procedure or historical regression |

## Architecture Review

**Phase B status:** Planned; see [feature-assembly-plan.md](./feature-assembly-plan.md).

### Key Decisions

- Policy is versioned data; scripts execute it; prose explains judgment and rationale.
- Historical policy bundles are immutable and fully resolved.
- Commands are argv arrays and are never interpreted by a shell.
- Drift checks prove reproducibility; independent fixtures and invariants prove meaning.
- `run-gate.py` owns gate procedure, while `exec-and-log.py` covers non-gate commands.
- The existing lifecycle runner and the action gate driver share one execution library.

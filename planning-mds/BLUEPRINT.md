# Nebula Agents Planning Blueprint

**Last Updated:** 2026-07-12

## Purpose

This blueprint is the top-level planning index for Nebula Agents. It links feature-level PRDs, implementation stories, and tracker status so product build work can move one step at a time with explicit validation before the next stage starts.

## Product Direction

Nebula Agents should become an operator cockpit for high-quality agentic delivery. The first usable surface preserves the native Codex and Claude Code terminal experience through tmux sessions. The future platform can add managed provider adapters only after the tmux path proves the gate, evidence, recovery, and approval model.

## Feature Plan

- [F0001 - Tmux-Native Agent Cockpit](features/F0001-tmux-native-agent-cockpit/README.md) - Planned / Now
  - [F0001-S0001 - Provider auth and environment preflight](features/F0001-tmux-native-agent-cockpit/F0001-S0001-provider-auth-and-environment-preflight.md) - Not Started
  - [F0001-S0002 - Tmux session launch and attach](features/F0001-tmux-native-agent-cockpit/F0001-S0002-tmux-session-launch-and-attach.md) - Not Started
  - [F0001-S0003 - Run registry and evidence watchers](features/F0001-tmux-native-agent-cockpit/F0001-S0003-run-registry-and-evidence-watchers.md) - Not Started
  - [F0001-S0004 - Gate and validator dashboard](features/F0001-tmux-native-agent-cockpit/F0001-S0004-gate-and-validator-dashboard.md) - Not Started
  - [F0001-S0005 - Native session transcript and recovery](features/F0001-tmux-native-agent-cockpit/F0001-S0005-native-session-transcript-and-recovery.md) - Not Started
  - [F0001-S0006 - Read-only review and status commands](features/F0001-tmux-native-agent-cockpit/F0001-S0006-readonly-review-and-status-commands.md) - Not Started

- [F0002 - Managed Agent Orchestration](features/F0002-managed-agent-orchestration/README.md) - Planned / Next
  - [F0002-S0001 - Provider adapter contract](features/F0002-managed-agent-orchestration/F0002-S0001-provider-adapter-contract.md) - Not Started
  - [F0002-S0002 - Managed session thread continuity](features/F0002-managed-agent-orchestration/F0002-S0002-managed-session-thread-continuity.md) - Not Started
  - [F0002-S0003 - Typed gate decision broker](features/F0002-managed-agent-orchestration/F0002-S0003-typed-gate-decision-broker.md) - Not Started
  - [F0002-S0004 - Streaming event and approval bridge](features/F0002-managed-agent-orchestration/F0002-S0004-streaming-event-and-approval-bridge.md) - Not Started
  - [F0002-S0005 - Migration from tmux to managed orchestration](features/F0002-managed-agent-orchestration/F0002-S0005-migration-from-tmux-to-managed-orchestration.md) - Not Started

- [F0004 - Reflective Learning Loop and Strategy Playbook](features/F0004-reflective-learning-loop/README.md) - Planned / Later
  - [F0004-S0001 - Strategy playbook artifact and entry schema](features/F0004-reflective-learning-loop/F0004-S0001-strategy-playbook-artifact-and-schema.md) - Not Started
  - [F0004-S0002 - Reflector role and trace analysis](features/F0004-reflective-learning-loop/F0004-S0002-reflector-role-and-trace-analysis.md) - Not Started
  - [F0004-S0003 - Reflect action and approval-gated curation](features/F0004-reflective-learning-loop/F0004-S0003-reflect-action-and-approval-gate.md) - Not Started
  - [F0004-S0004 - Curation lifecycle, counters, and supersession](features/F0004-reflective-learning-loop/F0004-S0004-curation-lifecycle-and-decay.md) - Not Started
  - [F0004-S0005 - Strategy selection and context load-back](features/F0004-reflective-learning-loop/F0004-S0005-strategy-selection-and-load-back.md) - Not Started
  - [F0004-S0006 - Boundary, genericness, and lifecycle-gate enforcement](features/F0004-reflective-learning-loop/F0004-S0006-boundary-and-genericness-gate.md) - Not Started

- [F0005 - Move-Invariant Knowledge-Graph Feature-Doc References](features/archive/F0005-move-invariant-kg-doc-references/README.md) - Superseded by F0006 (2026-07-04; folder archived at supersession; see `features/REGISTRY.md` Retired Features)

- [F0006 - Compiled Knowledge-Graph Projection and Governed Integration](features/archive/F0006-compiled-kg-projection-and-integration/README.md) - Archived (implementation and promotion complete 2026-07-11; recovery G8 closeout 2026-07-12)
  - [F0006-S0001 - Three-way semantic KG merge tool (`merge3.py`)](features/archive/F0006-compiled-kg-projection-and-integration/F0006-S0001-three-way-semantic-kg-merge.md) - Done
  - [F0006-S0002 - Tracker-table three-way merge (REGISTRY/ROADMAP rows)](features/archive/F0006-compiled-kg-projection-and-integration/F0006-S0002-tracker-table-three-way-merge.md) - Done
  - [F0006-S0003 - Integrator role and `integrate` action](features/archive/F0006-compiled-kg-projection-and-integration/F0006-S0003-integrator-role-and-integrate-action.md) - Done
  - [F0006-S0004 - `kg-source/` shard schema, layout, and ownership](features/archive/F0006-compiled-kg-projection-and-integration/F0006-S0004-kg-source-shard-schema-and-ownership.md) - Done
  - [F0006-S0005 - Deterministic KG compiler with logical doc refs](features/archive/F0006-compiled-kg-projection-and-integration/F0006-S0005-deterministic-kg-compiler.md) - Done
  - [F0006-S0006 - Decompiler-first migration with round-trip proof](features/archive/F0006-compiled-kg-projection-and-integration/F0006-S0006-decompiler-first-migration.md) - Done
  - [F0006-S0007 - Tracker generation from feature shards](features/archive/F0006-compiled-kg-projection-and-integration/F0006-S0007-tracker-generation-from-shards.md) - Done
  - [F0006-S0008 - Reproducibility CI, enforcement, and git policy](features/archive/F0006-compiled-kg-projection-and-integration/F0006-S0008-reproducibility-ci-and-git-policy.md) - Done
  - [F0006-S0009 - Framework contract, roles, and docs reconciliation](features/archive/F0006-compiled-kg-projection-and-integration/F0006-S0009-framework-contract-reconciliation.md) - Done

- [F0007 - Spec-Driven Orchestration and Prompt Compilation](features/F0007-spec-driven-orchestration-and-prompt-compilation/README.md) - Planned / Now
  - [F0007-S0001 - Versioned action policy and schema](features/F0007-spec-driven-orchestration-and-prompt-compilation/F0007-S0001-versioned-action-policy-and-schema.md) - Not Started
  - [F0007-S0002 - Contract conformance and behavioral diff](features/F0007-spec-driven-orchestration-and-prompt-compilation/F0007-S0002-contract-conformance-and-behavioral-diff.md) - Not Started
  - [F0007-S0003 - Run initialization and product scaffolding](features/F0007-spec-driven-orchestration-and-prompt-compilation/F0007-S0003-run-initialization-and-product-scaffolding.md) - Not Started
  - [F0007-S0004 - Typed command runtime and complete telemetry](features/F0007-spec-driven-orchestration-and-prompt-compilation/F0007-S0004-typed-command-runtime-and-telemetry.md) - Not Started
  - [F0007-S0005 - Gate driver, durable checkpoints, and severity policy](features/F0007-spec-driven-orchestration-and-prompt-compilation/F0007-S0005-gate-driver-checkpoints-and-severity-policy.md) - Not Started
  - [F0007-S0006 - Generated evidence prompts and drift gate](features/F0007-spec-driven-orchestration-and-prompt-compilation/F0007-S0006-generated-evidence-prompts-and-drift-gate.md) - Not Started
  - [F0007-S0007 - Version-aware validator convergence](features/F0007-spec-driven-orchestration-and-prompt-compilation/F0007-S0007-version-aware-validator-convergence.md) - Not Started
  - [F0007-S0008 - Shared policy consumers and prose thinning](features/F0007-spec-driven-orchestration-and-prompt-compilation/F0007-S0008-shared-policy-consumers-and-prose-thinning.md) - Not Started
  - [F0007-S0009 - Governed rollout and compatibility pilot](features/F0007-spec-driven-orchestration-and-prompt-compilation/F0007-S0009-governed-rollout-and-compatibility-pilot.md) - Not Started

## Validation Policy

- Product planning updates must keep `features/REGISTRY.md`, `features/ROADMAP.md`, `features/STORY-INDEX.md`, and this blueprint synchronized.
- Story files must use one story per file with IDs matching `F####-S####`.
- F0001 is the mandatory first delivery path. F0002 must not remove tmux fallback until feature closeout evidence proves parity for interactive prompts, user approvals, terminal visibility, transcript recovery, and validator gates.

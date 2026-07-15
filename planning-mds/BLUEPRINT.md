# Nebula Agents Planning Blueprint

**Last Updated:** 2026-07-15

## Purpose

This blueprint is the top-level planning index for Nebula Agents. It links feature-level PRDs, implementation stories, and tracker status so product build work can move one step at a time with explicit validation before the next stage starts.

## Product Direction

Nebula Agents should become an operator cockpit for high-quality agentic delivery. The first usable surface preserves the native Codex and Claude Code terminal experience through tmux sessions. The future platform can add managed provider adapters only after the tmux path proves the gate, evidence, recovery, and approval model.

## Feature Plan

- [F0001 - Tmux-Native Agent Cockpit](features/archive/F0001-tmux-native-agent-cockpit/README.md) - Archived / Completed (2026-07-15)
  - [F0001-S0001 - Provider auth and environment preflight](features/archive/F0001-tmux-native-agent-cockpit/F0001-S0001-provider-auth-and-environment-preflight.md) - Done
  - [F0001-S0002 - Tmux session launch and attach](features/archive/F0001-tmux-native-agent-cockpit/F0001-S0002-tmux-session-launch-and-attach.md) - Done
  - [F0001-S0003 - Run registry and evidence watchers](features/archive/F0001-tmux-native-agent-cockpit/F0001-S0003-run-registry-and-evidence-watchers.md) - Done
  - [F0001-S0004 - Gate and validator dashboard](features/archive/F0001-tmux-native-agent-cockpit/F0001-S0004-gate-and-validator-dashboard.md) - Done
  - [F0001-S0005 - Native session transcript and recovery](features/archive/F0001-tmux-native-agent-cockpit/F0001-S0005-native-session-transcript-and-recovery.md) - Done
  - [F0001-S0006 - Read-only review and status commands](features/archive/F0001-tmux-native-agent-cockpit/F0001-S0006-readonly-review-and-status-commands.md) - Done

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

## 4. F0001 Technical Architecture

### 4.1 Service Boundaries

F0001 is one local Python executable, not a daemon or hosted service. It uses four inward-facing layers:

| Boundary | Responsibility | Must Not Own |
|----------|----------------|--------------|
| Presentation | CLI commands and the terminal cockpit; maps input and renders sanitized views | Provider processes, filesystem persistence, or lifecycle rules |
| Application | Preflight, launch, attach, validation, gate-decision, transcript, recovery, and query use cases | Direct `tmux` calls or provider-specific command syntax |
| Domain | Run, gate, validator, transcript, and authorization invariants | Terminal rendering, subprocesses, or files |
| Infrastructure adapters | Tmux, Codex/Claude CLI, filesystem state, evidence polling, OS identity, clock, and process execution | Gate policy or run-state decisions |

F0001 owns the minimum local registry, native-session lifecycle, gate visibility, and redacted recovery surface. F0003 owns MCP tools, stable artifact IDs, deterministic summaries, metrics, and learning proposals. F0002 owns managed provider adapters and remote/SDK orchestration. Direct native CLI use remains a fallback.

### 4.2 Data Model

The `RunRecord` aggregate is stored as an atomic JSON snapshot with a monotonically increasing `revision`. It contains run identity, provider/tmux identity, feature/story focus, workspace and evidence roots, current session/gate/transcript state, the latest validator result, artifact observations, `created_at`, and `updated_at`. Each state-changing operation also appends a `RuntimeEvent` to a per-run JSONL audit stream with `sequence`, `occurred_at`, actor, event type, and sanitized payload.

`ProviderProbe`, `GateSnapshot`, `ValidatorResult`, `TranscriptState`, and `ArtifactObservation` are value records within the aggregate. `LocalPolicy` maps OS user/group attributes to local roles and action grants. F0001 has no database, soft delete, or cross-run transaction; writes use a per-run lock, revision check, same-directory temporary file, `fsync`, and atomic replace. JSON Schemas under `planning-mds/schemas/` are authoritative.

### 4.3 Workflow Rules

- Session transitions: `PreflightPending -> Launching -> Active -> Exited`; launch failures move to `Failed`; a missing tmux session moves `Active -> DetachedOrExited`; reconciliation may move `DetachedOrExited -> Active`. `Failed` and `Exited` are terminal for that run.
- Gate transitions: `Unknown -> Pending` only after reconciliation; `Pending <-> Blocked` follows required evidence and validator state; `Pending|Blocked -> Held` is explicit; `Held -> Pending` is explicit; only an authorized user may move an eligible `Pending -> Approved`. A gate decision is append-only.
- Transcript transitions: `Disabled -> Active -> Completed|Failed`; retry from `Failed -> Active` requires a new explicit action. Unredacted output is never written as fallback.
- Repeating a successful request is idempotent where safe. Duplicate run IDs and tmux names are conflicts; attaching never launches a second provider; approving an already approved gate returns the existing decision.
- Every mutation and every denied or blocked mutation appends a runtime event. Read-only queries do not create events; validator execution records its result because it changes review evidence.

### 4.4 Authorization Model

Authorization uses a default-deny subject/resource/action contract. Subject attributes are OS user ID, group IDs, configured role, and run ownership. Resource attributes are run ID, owner ID, session state, gate state, evidence readiness, and transcript state. Actions are `Probe`, `Launch`, `Attach`, `ReadState`, `RunValidator`, `DecideGate`, and `ConfigureTranscript`.

`LocalOperator` may mutate runs it owns. `Reviewer` may read state and run allowlisted validators; attach guidance, gate hold, or gate approval requires an explicit policy grant. Provider login is owned by the provider CLI. F0001 never reads credential bodies or copies provider authentication state. This keeps Casbin-compatible ABAC semantics without requiring a policy server for the local MVP.

### 4.5 API and CLI Contracts

F0001 exposes no HTTP API, so OpenAPI is not applicable. Its public contract is the versioned CLI and JSON output described in `planning-mds/architecture/f0001-cli-contract.md`. CREATE operations are `launch`, validator-result recording, gate decisions, and transcript enablement. READ operations are `doctor`, `sessions`, `status`, and `evidence`; `attach` delegates to the existing tmux session without creating a provider process.

All subprocess calls originate from validated argv records. Provider-specific flags live behind provider adapters. Errors use stable machine codes plus human remediation and stable exit-code classes. `--format json` output conforms to the shared schemas; terminal tables are projections of the same records.

The public machine-readable record contracts are `RunRecord` for status/READ projections, `RuntimeEvent` for append-only mutation evidence, and `LocalPolicy` for authorization configuration. They are filesystem/CLI contracts rather than HTTP resources.

### 4.6 Non-Functional Requirements

- **Performance:** `doctor` completes within 3 seconds when probes return normally; launch feedback appears within 2 seconds of tmux return; cached registry status returns within 250 ms for 100 local runs; evidence and gate changes appear within 1 second at the default 500 ms polling interval.
- **Security:** state files are owner-only (`0600`) and directories `0700`; subprocess input is argv-based except the isolated tmux helper seam; secrets are neither inspected nor persisted; transcript content is redacted before its first disk write; path containment uses resolved paths, not prefix strings.
- **Availability:** there is no remote availability SLO. A TUI crash must not terminate the tmux/provider session, and state recovery must succeed from the last valid snapshot plus append-only events.
- **Reliability:** snapshot writes are locked, revision-checked, and atomic; corrupt files are preserved for diagnosis; failed redaction disables transcript writes; unknown gate or session state fails closed.
- **Scalability:** MVP supports 100 retained local run snapshots, 20 watched active runs, and one provider process per run. Larger stores, remote coordination, and distributed execution are deferred to F0003/F0002.
- **Portability:** MVP supports POSIX environments with tmux and Python 3.11 or newer; Windows is supported through WSL when tmux and the provider CLI run inside the same distribution.
- **UI quality:** the TUI must support keyboard-only operation, resize without state loss, text labels in addition to color, and a narrow layout at 80x24. There is no web theme surface.
- **Caching:** the process may keep an in-memory read projection invalidated by registry/watcher events; it must re-probe tmux and re-check gate eligibility before mutations. No external cache is used.

### 4.7 Architecture Artifacts

- [Solution patterns](architecture/SOLUTION-PATTERNS.md)
- [Data model](architecture/data-model.md)
- [System context](architecture/c4-context.md) and [container view](architecture/c4-container.md)
- [CLI contract](architecture/f0001-cli-contract.md)
- [Workflow design](architecture/f0001-workflows.md)
- [Authorization model](security/f0001-authorization-model.md)
- [Architecture decisions](architecture/decisions/)

### 4.8 Architecture Boundary Decision

F0001 deliberately has no HTTP service, database, managed provider SDK, MCP surface, artifact index, metrics store, or learning loop. Those are not missing layers; they are explicit F0003/F0002 scope boundaries. The feature action creates the implementation-level `feature-assembly-plan.md` at G0 from this approved Phase B design.

### 4.9 Phase B Approval

The operator approved the F0001 architecture at `2026-07-13T21:39:29-04:00`. The four F0001 ADRs are Accepted, architecture validation is clean, and F0001 is ready to enter the `feature` action at G0.

The feature action started on 2026-07-13 as run `2026-07-13-1cfbc5a0`, completed remediation and review in run `2026-07-14-b885d64c`, and archived on 2026-07-15. Its completed G0 implementation plan is retained at [`features/archive/F0001-tmux-native-agent-cockpit/feature-assembly-plan.md`](features/archive/F0001-tmux-native-agent-cockpit/feature-assembly-plan.md); implementation remains bounded to one local Python package under `engine/`.

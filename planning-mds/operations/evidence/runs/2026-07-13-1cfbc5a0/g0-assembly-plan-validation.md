# G0 Assembly Plan Validation — F0001 run 2026-07-13-1cfbc5a0

## Run Identity

- Feature: F0001 — Tmux-Native Agent Cockpit
- Gate: G0
- Reviewer: Architect Agent
- Reviewed on: 2026-07-13
- Plan: `planning-mds/features/F0001-tmux-native-agent-cockpit/feature-assembly-plan.md`

## Scope Review

The plan covers all six stories through one local Python package. It includes preflight, provider/tmux execution, local persistence/watchers, gate/validator actions, transcript/recovery, CLI/TUI projections, tests, package smoke, security scans, evidence, and closeout handoffs. HTTP, database, MCP, managed provider SDK, remote collaboration, analytics, and retention remain excluded.

## Architecture Reconciliation

- Package and dependency direction match `SOLUTION-PATTERNS.md` and ADR-001.
- Atomic snapshot/event ordering, replay, lock, and failure-injection tests match ADR-002.
- Typed provider argv plus constant session-entry descriptor seam match ADR-003; the exact descriptor schema was added at G0.
- Opt-in, 8 KiB overlap, redact-before-write behavior and failure isolation match ADR-004.
- Local ABAC actions, reviewer defaults, path/mode requirements, and mutation rechecks match the authorization model.
- CLI commands, JSON contracts, exits, run/gate/transcript state machines, watcher intervals, and schema names match approved architecture.

## Dependency And Ownership Review

Domain/port signatures land before adapters and presentation. Backend owns runtime modules, Frontend owns terminal presentation inside the same package, QE owns executable evidence, Security owns the security verdict, Architect owns shared contracts and G7 reconciliation, and PM alone owns G8 closeout. No two roles are assigned conflicting ownership of the same canonical semantics.

## Mutation And Audit Review

Every mutating story path names its application method, carrier, authorization action, concurrency guard, stable failure class, event, and restart/integration proof. Pure `sessions`, `status`, `evidence`, and non-initializing `doctor` reads remain audit N/A. Attach and recovery cannot start a second provider.

## Integration And Test Review

The plan has feasible checkpoints after environment, durable native session, governed runtime, transcript, and presentation work. It requires real tmux with deterministic fake providers, persistence failure injection, exhaustive chunk-split redaction tests, contract fixtures, table/JSON parity, 80x24/resize behavior, clean-install smoke, and at least 85% line coverage with critical-guard branch targets.

## Knowledge-Graph Prediction

Six predicted F0001 capabilities and the `engine/src/nebula_agents/**/*.py` binding glob are named. The repository's missing KG/compiler contract is explicitly carried to G7; the plan forbids fabricated graph output and treats unresolved governance as a closeout blocker.

## Findings

No blocking plan finding. The runtime environment and installed provider flag behavior must be verified at G1 before implementation validation. The absence of a self-hosted KG is non-blocking at G0 but must be resolved or formally governed at G7 before G8.

## Result

PASS


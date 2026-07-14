# Action Context — F0001 run 2026-07-13-1cfbc5a0

## Run Identity

- Action: `feature`
- Feature: `F0001`
- Feature slug: `tmux-native-agent-cockpit`
- Run ID: `2026-07-13-1cfbc5a0`
- Product root: `nebula-agents`
- Branch: `feat/F0001-tmux-native-agent-cockpit`
- Started: `2026-07-13T21:43:15-04:00`
- Current owner: Architect Agent

## Inputs

- Explicit operator request to start the F0001 feature action.
- Phase A PRD and six story files under `planning-mds/features/F0001-tmux-native-agent-cockpit/`.
- Operator-approved Phase B architecture accepted at `2026-07-13T21:39:29-04:00`.
- `agents/actions/feature.md`, `CONSUMER-CONTRACT.md`, `agents/docs/AGENT-OPS.md`, and the feature-assembly/evidence templates.
- Installed local environment: Python 3.14.4, tmux 3.6, Codex CLI, and Claude CLI available on `PATH`.

## Assumptions

- Python 3.11 is the compatibility floor; the current Python 3.14 environment is used for the first local validation lane.
- Stdlib `curses` is the portable presentation baseline on POSIX/WSL.
- F0001 introduces no hosted deployment, network listener, database, managed provider SDK, MCP server, or new model behavior.
- The existing uncommitted Phase B artifacts belong to the same approved F0001 workstream and are included in this run's SCM scope.

## Scope Boundaries

In scope: one package under `engine/`, local CLI/TUI presentation, typed provider/tmux adapters, local ABAC, JSON/JSONL persistence, evidence watchers, validators/gates, opt-in redacted transcripts, tests, docs, and governed evidence.

Out of scope: F0002 managed-provider orchestration, F0003 MCP/index/metrics/summary surfaces, HTTP, remote multi-user operation, provider login, API-key SDKs, cloud upload, analytics, and retention automation.

The formal feature action intentionally bypasses `.agentignore` only for the exact evidence contract, current run folder, and the selected F0006 manifest pattern needed to understand validator conventions. No broad cold-archive retrieval was used for product discovery.

## Lifecycle Stage

Current stage: `G3 — BLOCKED / REQUEST CHANGES`.

The local CLI/TUI implementation is present. Installed-package preflight, 424-test acceptance, 90.03% line coverage, real-tmux/fake-provider lifecycle, self-review, deployability, and security review pass. Independent code review nevertheless reproduced six Critical, one High, and one Medium blocking findings, including incomplete doctor output, lifecycle/side-effect inconsistency, evidence-path bypasses, validator containment gaps, transcript crash inconsistency, unreachable corrupt-state recovery, an unmet branch-coverage contract, and dependency-plan drift. Per the feature-action stop rule, this run stops at G3 and does not open G4.

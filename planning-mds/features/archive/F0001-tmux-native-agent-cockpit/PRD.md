# F0001 - Tmux-Native Agent Cockpit PRD

## Feature Header

**Feature ID:** F0001
**Feature Name:** Tmux-Native Agent Cockpit
**Priority:** Critical
**Phase:** MVP
**Status:** Archived - accepted and delivered 2026-07-15

## Feature Statement

**As a** product build operator
**I want** a terminal UI that launches and monitors native Codex and Claude Code sessions through tmux
**So that** I can keep interactive engineering quality, subscription auth, gated approvals, and recovery visibility while Nebula Agents tracks the work.

## Business Objective

- **Goal:** Provide the first trustworthy terminal UI path for agentic product build runs.
- **Metric:** A user can start, attach to, validate, and recover a native agent session from the cockpit without switching to API-key orchestration.
- **Baseline:** Operators run Codex or Claude Code directly in a shell and manually track gates, prompts, evidence, and validator status.
- **Target:** Operators keep the native session while Nebula exposes run state, stage gates, validation commands, transcript recovery, and evidence paths.

## Problem Statement

- **Current State:** The evidence-contract prompts and previous product-build runs rely on rich interactive loops: user feedback, gated approvals, visible terminal output, and agent continuity across planning and implementation.
- **Desired State:** Nebula wraps that native loop in a terminal cockpit without splitting the work into stateless prompt chunks or losing provider-specific interactivity.
- **Impact:** A premature SDK-only implementation would likely degrade engineering judgment, approval handling, and subscription-auth reuse. A tmux-first cockpit reduces that risk while still creating a path to richer orchestration later.

## Scope & Boundaries

**In Scope:**
- Detect local readiness for `tmux`, `codex`, and `claude` CLIs.
- Launch native provider CLIs in named tmux sessions from the terminal UI.
- Reattach to active sessions without relaunching the provider.
- Record local run metadata: feature ID, run ID, provider, tmux session name, workspace, prompt/action, current gate, and evidence paths.
- Surface gate status, validator commands, and recent evidence artifacts.
- Capture redacted transcript logs for recovery and review.
- Provide read-only commands for session listing, status, validation, and attach.

**Out of Scope:**
- Replacing native CLIs with SDK-only orchestration.
- Rewriting the evidence-contract prompts into isolated stateless stages.
- Managing provider subscriptions or authentication flows directly.
- Multi-user remote collaboration.
- Cloud-hosted execution.
- Automatic approval of provider tool calls or lifecycle gates.

## Acceptance Criteria Overview

- [x] The cockpit can detect whether `tmux` and at least one supported provider CLI are available.
- [x] A user can launch a native Codex or Claude Code session inside a named tmux session.
- [x] Existing subscription-authenticated shells are reused by the launched provider CLI.
- [x] A user can detach and reattach while preserving the native provider UI and scrollback.
- [x] The cockpit records run metadata and exposes evidence paths for the active run.
- [x] Gate status and validation commands are visible before the next stage is approved.
- [x] Transcript capture is available with documented secret redaction behavior.

## UX / Screens

| Screen | Purpose | Key Actions |
|--------|---------|-------------|
| Session List | Show active and recent agent sessions. | Launch, attach, inspect status, run preflight. |
| Session Detail | Show one tmux-backed run and its gate/evidence state. | Attach, validate, view transcript path, inspect gate state. |
| Gate Review | Show current gate, required evidence, and approval status. | Approve, hold, rerun validators, record decision. |
| Validator Output | Show latest validation command results. | Rerun, open evidence path, copy command. |

**Key Workflows:**
1. Preflight - operator checks local provider and tmux readiness.
2. Launch - operator starts Codex or Claude Code in a tmux session with a feature/action prompt.
3. Monitor - cockpit watches evidence files and status markers while the native agent remains interactive.
4. Gate - operator reviews current stage output and approves or holds the next step.
5. Recover - operator reattaches to the tmux session or opens the transcript after interruption.

## Screen Layouts (ASCII)

### Session List - Desktop

```text
+------------------------------------------------------------------+
| Nebula Agents                         Provider: codex  tmux: ok  |
+------------------------------+-----------------------------------+
| Sessions                     | Details                           |
| > F0001/run-20260618-001     | Feature: F0001                    |
|   F0002/run-draft            | Story: F0001-S0002                |
|                              | Gate: G2 awaiting operator        |
| [N] New  [A] Attach [D] Doc  | Evidence: planning-mds/...        |
+------------------------------+-----------------------------------+
| Validators: stories PASS | trackers pending | transcript active  |
+------------------------------------------------------------------+
```

### Session Detail - Narrow

```text
+--------------------------------+
| F0001/run-20260618-001         |
| Provider: codex                |
| tmux: nebula-F0001-001         |
| Gate: G2 awaiting operator     |
+--------------------------------+
| [Attach] [Validate] [Evidence] |
| Transcript: active/redacted    |
+--------------------------------+
```

## Data Requirements

**Core Records:**
- `run_id`: Stable ID for the local execution run.
- `feature_id`: Feature under active work.
- `story_id`: Optional story focus for the run.
- `provider`: `codex`, `claude`, or future supported provider key.
- `tmux_session`: Native tmux session name.
- `workspace_root`: Absolute workspace path.
- `prompt_contract`: Evidence-contract prompt/action used to start the session.
- `gate_state`: Current lifecycle gate and decision state.
- `evidence_root`: Local evidence package path.
- `transcript_path`: Redacted transcript path.

**Validation Rules:**
- `run_id` must be unique for active sessions.
- `tmux_session` must be unique for active sessions.
- Provider auth checks must never persist tokens or auth cache contents.
- Transcript paths must stay inside the workspace evidence area or approved local runtime directory.

## Role-Based Access

| Role | Access Level | Notes |
|------|--------------|-------|
| Local Operator | Launch / attach / validate / approve gates | Uses the local shell identity and provider CLI auth. |
| Reviewer | Read session state / run validators / inspect evidence | Can use read-only commands unless explicitly granted launch rights. |

## Success Criteria

- A native provider session can be launched and reattached through tmux without reauthentication.
- Gate state and validation status are visible without reading raw log files manually.
- Interrupted sessions can be recovered through attach or transcript review.
- No secret-bearing provider auth data is written to run metadata or transcript artifacts.

## Risks & Assumptions

- Risk: tmux behavior differs by terminal emulator. Mitigation: keep preflight explicit and document supported behavior.
- Risk: transcript capture may record sensitive content. Mitigation: default redaction and clear evidence boundaries.
- Risk: provider CLIs change command flags. Mitigation: preflight captures versions and provider launch commands are configurable.
- Assumption: The user's shell is already authenticated for the provider CLI when subscription auth is desired.

## Dependencies

- Local `tmux`.
- Local `codex` and/or `claude` CLI.
- Existing evidence-contract prompts under `agents/templates/prompts/evidence-contract`.
- Story and tracker validators under `agents/product-manager/scripts`.

## Architecture Traceability

**Phase B design:** Approved at `2026-07-13T21:39:29-04:00`.

| Story | Architecture coverage |
|-------|-----------------------|
| F0001-S0001 | Provider adapter contract, non-secret readiness probes, preflight JSON Schema, and `doctor` exit semantics |
| F0001-S0002 | Tmux session lifecycle, validated launch descriptor, one-provider-per-run invariant, and attach reuse |
| F0001-S0003 | Atomic run snapshot, append-only runtime events, artifact observations, polling watcher, and recovery rules |
| F0001-S0004 | Gate state machine, validator allowlist, eligibility guard, local authorization actions, and immutable decisions |
| F0001-S0005 | Opt-in pipe capture, redact-before-write filter, bounded preview, transcript state machine, and recovery contract |
| F0001-S0006 | Versioned read-only CLI/JSON projections, stable exit codes, and mutation isolation for validator recording |

### Phase B Resolution of Story Questions

| Question | Resolution |
|----------|------------|
| Provider readiness probe depth | Default probes are executable discovery, version/help, and provider-supported non-secret login status. F0001 never starts a dry-run model request or performs login during preflight. |
| Tmux session naming | `nebula-F####-<run-suffix>`; provider and full metadata stay in the registry so the tmux name remains short and shell-safe. |
| Registry format | Atomic JSON snapshot for current state plus append-only JSONL for audit history. Markdown is a rendered view, not persistence. |
| Gate reviewer label | Capture OS user ID and resolved username; an optional display label may supplement but never replace the OS identity. |
| Transcript default | Disabled by default and enabled explicitly per run. Redaction happens before the first transcript write. |
| JSON CLI output | Included in MVP through `--format json`; human tables and the TUI are projections of the same versioned records. |

### Technical Boundaries

- The cockpit is a single local Python executable with Presentation, Application, Domain, and Infrastructure Adapter modules.
- The native provider TUI remains the source of truth inside tmux. Nebula observes state and invokes explicit operator actions; it does not parse the screen to infer approvals.
- F0003 owns MCP status tools, artifact IDs, deterministic summaries, metrics, and learning proposals. F0002 owns managed provider orchestration.
- There is no HTTP API or database in F0001. Public integration contracts are the CLI, JSON Schemas, runtime snapshot, append-only event stream, and evidence paths.

### Architecture Documents

- [`../../../architecture/SOLUTION-PATTERNS.md`](../../../architecture/SOLUTION-PATTERNS.md)
- [`../../../architecture/data-model.md`](../../../architecture/data-model.md)
- [`../../../architecture/f0001-workflows.md`](../../../architecture/f0001-workflows.md)
- [`../../../architecture/f0001-cli-contract.md`](../../../architecture/f0001-cli-contract.md)
- [`../../../security/f0001-authorization-model.md`](../../../security/f0001-authorization-model.md)
- [`../../../architecture/decisions/ADR-001-f0001-local-tmux-runtime.md`](../../../architecture/decisions/ADR-001-f0001-local-tmux-runtime.md)
- [`../../../architecture/decisions/ADR-002-f0001-runtime-persistence.md`](../../../architecture/decisions/ADR-002-f0001-runtime-persistence.md)
- [`../../../architecture/decisions/ADR-003-f0001-provider-execution-boundary.md`](../../../architecture/decisions/ADR-003-f0001-provider-execution-boundary.md)
- [`../../../architecture/decisions/ADR-004-f0001-transcript-redaction.md`](../../../architecture/decisions/ADR-004-f0001-transcript-redaction.md)

## Related Stories

- [F0001-S0001](./F0001-S0001-provider-auth-and-environment-preflight.md) - Provider auth and environment preflight
- [F0001-S0002](./F0001-S0002-tmux-session-launch-and-attach.md) - Tmux session launch and attach
- [F0001-S0003](./F0001-S0003-run-registry-and-evidence-watchers.md) - Run registry and evidence watchers
- [F0001-S0004](./F0001-S0004-gate-and-validator-dashboard.md) - Gate and validator dashboard
- [F0001-S0005](./F0001-S0005-native-session-transcript-and-recovery.md) - Native session transcript and recovery
- [F0001-S0006](./F0001-S0006-readonly-review-and-status-commands.md) - Read-only review and status commands

## Rollout & Enablement

- Deliver as an opt-in local CLI/TUI surface.
- Keep direct shell usage of Codex and Claude Code as a supported fallback.
- Require a documented recovery path before any F0002 managed-provider replacement work begins.

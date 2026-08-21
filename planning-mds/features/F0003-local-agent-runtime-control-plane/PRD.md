# F0003 - Local Agent Runtime Control Plane PRD

## Feature Header

**Feature ID:** F0003
**Feature Name:** Local Agent Runtime Control Plane
**Priority:** High
**Phase:** Platform Hardening
**Status:** Draft

## Feature Statement

**As a** product build operator
**I want** a local runtime control plane around native agent sessions
**So that** Nebula Agents can launch, inspect, summarize, retrieve evidence from, and learn from agent runs without losing the native interactive workflow.

## Business Objective

- **Goal:** Turn the planned cockpit into an executable local runtime layer with stable commands, status APIs, evidence retrieval, summarization, metrics, and reviewed learning proposals.
- **Metric:** A user can launch or inspect a local agent run, query current status through CLI or MCP, retrieve full evidence by stable ID, view concise summaries, and review proposed process corrections after failed runs.
- **Baseline:** The framework has strong role, action, gate, and evidence contracts, but most runtime behavior is still planned in feature documents.
- **Target:** Nebula Agents has a small, testable local runtime API that supports F0001 tmux-native operation and supplies concrete interfaces for F0002 managed orchestration.

## Problem Statement

- **Current State:** Agents can follow markdown contracts, but run state, evidence discovery, status inspection, transcript summarization, and feedback from failed runs remain manual or feature-level plans.
- **Desired State:** Nebula provides local commands and machine-readable surfaces that make session state, gates, evidence, summaries, and runtime health observable without replacing native provider CLIs.
- **Impact:** Operators get faster recovery and review loops, while future managed orchestration receives stable contracts instead of inferring behavior from terminal output alone.

## Scope & Boundaries

**In Scope:**
- Local command surface for launch, wrap, session list, status, attach guidance, validator execution, and evidence inspection.
- Provider capability report and launch guards for supported local agent CLIs.
- MCP-compatible read-only tools for session status, gate status, validator status, and evidence lookup.
- Local evidence artifact store with stable artifact IDs, redacted public summaries, and full local retrieval paths.
- Deterministic summarizers for transcripts, command logs, validator output, and evidence manifests.
- Runtime metrics dashboard for run duration, gate wait time, validator results, transcript health, and evidence freshness.
- Failure-learning proposal workflow that drafts process corrections for human review instead of writing them automatically.

**Out of Scope:**
- Hosted multi-user orchestration.
- Provider account management or credential storage.
- Automatic approval of lifecycle gates or provider tool calls.
- Model-output compression that changes what the native provider sees during F0001.
- Removing tmux-native fallback.
- Writing learned corrections directly into framework or product instructions without review.

## Acceptance Criteria Overview

- [ ] A `nebula-agents` local command surface exists for preflight, wrap launch, sessions, status, validators, evidence, and attach guidance.
- [ ] Provider capability reports determine whether launch is allowed, degraded, or blocked.
- [ ] MCP-compatible read-only tools expose session, gate, validator, and evidence status.
- [ ] Evidence artifacts receive stable IDs and can be summarized or retrieved locally without storing secrets.
- [ ] Deterministic summarizers preserve errors, failed commands, gate decisions, artifact paths, and open questions.
- [ ] Runtime metrics are visible in a local dashboard or status view.
- [ ] Failed-run learning produces reviewable proposals with provenance and never mutates instructions without approval.

## UX / Surfaces

**F0003 is CLI-only.** It ships no screens. Every capability below is delivered as a
command with `--format table|json`; the table form is the human surface. A terminal-UI
presentation of these same application services belongs to F0008 (Agent Cockpit Landing
Shell) and is explicitly out of scope here.

This is a deliberate narrowing, recorded 2026-08-21. An earlier revision of this PRD named
five screens — Runtime Home, Capability Matrix, Evidence Browser, Metrics View, Learning
Review — which the Phase B architecture never defined; plan-review run
`2026-08-19-ec0a97ce` raised that gap as finding C2. Rather than grow a second UI surface
inside a runtime feature, the screens are replaced by the commands that already carry
their behavior, and the shell that presents them is left to the feature that owns shells.

| Capability | Command surface | Key actions |
|------------|-----------------|-------------|
| Runtime health and sessions | `sessions`, `status --run <id>` | Inspect run state, gate status, attach guidance |
| Provider readiness | `providers doctor` | Probe, inspect remediation, see blocked-launch reason |
| Evidence browsing | `evidence list --run <id>`, `evidence show <artifact-id>` | List artifacts, read redacted summary, get retrieval metadata |
| Runtime metrics | `metrics --run <id>` | Run duration, gate wait, validator counts, transcript health, evidence freshness |
| Learning review | `learn review --run <id>`, `learn decide <proposal-id>` | Draft proposals from failed-run evidence; record accept / edit / reject / archive |

Machine consumers use `--format json` or the read-only MCP tools (S0003). Nothing in this
feature renders a persistent screen, owns a layout, or manages terminal focus.

## Key Workflows

1. Runtime preflight - operator verifies local dependencies and provider capability before launch.
2. Wrapped launch - operator starts a native session through a Nebula command that records run metadata and starts watchers.
3. Read-only inspection - operator or agent queries status through CLI or MCP without attaching to the terminal.
4. Evidence retrieval - reviewer follows stable artifact IDs from summaries to full local evidence.
5. Failure learning - failed run output is summarized into proposed process corrections for human review.

## Runtime Flow Diagram

```text
+------------------+        +-----------------------------+
| Local Operator   |        | AI Tool / Reviewer          |
| CLI or TUI       |        | MCP-compatible host         |
+--------+---------+        +--------------+--------------+
         |                                 |
         | nebula-agents doctor/wrap       | nebula_* status/evidence tools
         v                                 v
+---------------------------------------------------------+
|              Nebula Local Runtime Control Plane          |
|                                                         |
|  +------------------+     +--------------------------+  |
|  | Command Surface  |     | Read-Only MCP Surface    |  |
|  | doctor/wrap      |     | session/gate/validator   |  |
|  | sessions/status  |     | evidence status tools    |  |
|  | attach/evidence  |     +-------------+------------+  |
|  +--------+---------+                   |               |
|           |                             |               |
|           v                             v               |
|  +------------------+     +--------------------------+  |
|  | Provider Probe   |     | Runtime Registry         |  |
|  | Capability Matrix|---->| runs, sessions, gates,   |  |
|  | Launch Guards    |     | validators, metrics      |  |
|  +--------+---------+     +-------------+------------+  |
|           |                             |               |
|           v                             v               |
|  +------------------+     +--------------------------+  |
|  | Native Session   |---->| Evidence Artifact Index  |  |
|  | tmux + provider  |     | artifact IDs, paths,     |  |
|  | CLI remains live |     | redaction, retrieval     |  |
|  +--------+---------+     +-------------+------------+  |
|           |                             |               |
|           v                             v               |
|  +------------------+     +--------------------------+  |
|  | Transcript and   |---->| Deterministic Summaries  |  |
|  | Command Capture  |     | logs, validators, gates  |  |
|  +------------------+     +-------------+------------+  |
|                                         |               |
|                                         v               |
|                          +--------------------------+   |
|                          | Metrics and Learning     |   |
|                          | run health, failures,    |   |
|                          | review-only proposals    |   |
|                          +--------------------------+   |
+---------------------------------------------------------+
```

The runtime registry is the coordination point. Native sessions remain interactive, while CLI, TUI, and MCP surfaces read the same structured state and evidence indexes.

## Data Requirements

**Core Records:**
- `run_id`: Stable local run identifier.
- `provider_key`: Supported provider identifier.
- `provider_capabilities`: Capability report used for launch gating.
- `session_ref`: tmux session name or future managed session ID.
- `runtime_status`: Ready, running, blocked, degraded, completed, failed, or abandoned.
- `gate_status`: Current lifecycle gate and decision state.
- `validator_results`: Latest command, exit code, duration, artifact path, and summary.
- `artifact_id`: Stable ID for evidence, transcript, command log, or summary.
- `artifact_kind`: Transcript, command-log, validator-output, manifest, status, metric, or learning-proposal.
- `summary_text`: Redacted deterministic summary.
- `retrieval_path`: Local path to full artifact.
- `learning_proposal_status`: Draft, accepted, edited, rejected, or archived.

**Validation Rules:**
- Artifact IDs are unique within a run and stable across reloads.
- Retrieval paths stay inside approved workspace, runtime, or evidence directories.
- Summaries must not include raw secret-like values.
- Learning proposals must link to source artifact IDs.
- Launch is blocked when required provider capability probes fail.

## Role-Based Access

| Role | Access Level | Notes |
|------|--------------|-------|
| Local Operator | Launch, attach, validate, inspect metrics, review proposals | Uses local shell trust boundary. |
| Reviewer | Read session state, inspect evidence, run read-only validation | Cannot launch unless local policy allows it. |
| Architect | Approve runtime contracts and capability matrix shape | Required for F0002 handoff. |
| Security Reviewer | Review redaction, retrieval boundaries, and learning proposal safety | Required before closeout. |

## Success Criteria

- Operators can inspect run state and evidence without manually reading raw terminal logs first.
- Reviewers can trace every summary back to full local evidence.
- Capability failures block unsafe launch paths and show fallback guidance.
- Runtime metrics make stalled gates, failing validators, missing transcripts, and stale evidence visible.
- Failure-learning proposals improve process quality while preserving human control over instruction changes.

## Risks & Assumptions

- Risk: Summaries omit details needed for review. Mitigation: every summary links to full artifact retrieval.
- Risk: MCP tools become a mutation surface. Mitigation: F0003 MCP tools are read-only except explicitly named validator execution commands.
- Risk: Runtime state drifts from actual tmux sessions. Mitigation: session probes reconcile registry state before status is reported.
- Risk: Learning proposals overfit one failed run. Mitigation: proposals require human review and source evidence links.
- Assumption: F0001 provides the initial tmux session metadata and transcript capture hooks.

## Dependencies

- F0001 tmux-native session registry and transcript capture model.
- Existing lifecycle gates and evidence-contract prompts.
- Existing product-manager story and tracker validators.
- F0002 adapter contract will consume the runtime capability and event shapes after F0003 proves them locally.

## Related Stories

- [F0003-S0001](./F0003-S0001-runtime-command-surface-and-wrap-launch.md) - Runtime command surface and wrap launch
- [F0003-S0002](./F0003-S0002-provider-capability-matrix-and-launch-guards.md) - Provider capability matrix and launch guards
- [F0003-S0003](./F0003-S0003-mcp-status-and-evidence-tools.md) - MCP status and evidence tools
- [F0003-S0004](./F0003-S0004-evidence-artifact-store-and-retrieval-index.md) - Evidence artifact store and retrieval index
- [F0003-S0005](./F0003-S0005-deterministic-transcript-log-and-validator-summaries.md) - Deterministic transcript, log, and validator summaries
- [F0003-S0006](./F0003-S0006-runtime-metrics-and-failure-learning-review.md) - Runtime metrics and failure-learning review

## Rollout & Enablement

- Deliver as an opt-in local runtime layer after or alongside F0001 implementation.
- Keep direct native CLI and tmux attach usage available at all times.
- Require read-only status surfaces and evidence retrieval before adding managed-provider orchestration defaults.

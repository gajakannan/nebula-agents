# F0003 - Local Agent Runtime Control Plane

**Status:** Archived - implementation and G8 closeout complete
**Archived:** 2026-08-30
**Priority:** High
**Phase:** Platform Hardening

## Overview

F0003 adds a concrete local runtime control plane around native agent sessions. It turns session launch, status, evidence retrieval, summarization, metrics, provider capability reports, and reviewed failure learning into explicit commands and read-only tool surfaces.

The feature does not replace native provider CLIs. It makes the surrounding Nebula runtime observable and testable so F0001 has a practical control surface and F0002 has stable contracts to build on.

## Documents

| Document | Purpose |
|----------|---------|
| [PRD.md](./PRD.md) | Full product requirements for the local runtime control plane |
| [STATUS.md](./STATUS.md) | Delivery checklist and signoff tracking |
| [GETTING-STARTED.md](./GETTING-STARTED.md) | Developer and agent setup guide |

## Stories

| ID | Title | Status |
|----|-------|--------|
| [F0003-S0001](./F0003-S0001-runtime-command-surface-and-wrap-launch.md) | Runtime command surface and wrap launch | Not Started |
| [F0003-S0002](./F0003-S0002-provider-capability-matrix-and-launch-guards.md) | Provider capability matrix and launch guards | Not Started |
| [F0003-S0003](./F0003-S0003-mcp-status-and-evidence-tools.md) | MCP status and evidence tools | Not Started |
| [F0003-S0004](./F0003-S0004-evidence-artifact-store-and-retrieval-index.md) | Evidence artifact store and retrieval index | Not Started |
| [F0003-S0005](./F0003-S0005-deterministic-transcript-log-and-validator-summaries.md) | Deterministic transcript, log, and validator summaries | Not Started |
| [F0003-S0006](./F0003-S0006-runtime-metrics-and-failure-learning-review.md) | Runtime metrics and failure-learning review | Not Started |
| [F0003-S0007](./F0003-S0007-application-query-command-split.md) | Application query/command service split | Not Started |

**Total Stories:** 7
**Completed:** 0 / 7

## Architecture Review

**Phase B status:** Drafted 2026-08-19; operator approval outstanding. See [BLUEPRINT §5](../../BLUEPRINT.md) and the [runtime contract](../../architecture/f0003-runtime-contract.md).
**Execution Plan:** Implement as a local-only runtime layer with explicit CLI and MCP contracts.

### Key Findings

- Runtime state must be append-only or reconcilable from the actual local session state.
- Status and evidence tools are read-only by default so agents can inspect without mutating gates.
- Summaries are navigation aids, not authoritative evidence. Full local artifacts remain retrievable by stable ID.
- Failure learning must produce proposed corrections for review, not automatic instruction edits.

### Architecture Decisions

| ADR | Decision | Status |
|-----|----------|--------|
| [ADR-005](../../architecture/decisions/ADR-005-f0003-control-plane-packaging.md) | Extend the existing local package; no daemon, port, or second distributable | Proposed |
| [ADR-006](../../architecture/decisions/ADR-006-f0003-artifact-identity-and-index.md) | Artifact identity from the path relative to its owning approved root (longest-match, `ws`/`rt`/`ev`), not content; content hash links duplicates | Proposed (rev. 2026-08-21) |
| [ADR-007](../../architecture/decisions/ADR-007-f0003-readonly-mcp-surface.md) | Dependency-free stdio MCP server; read-only enforced structurally by a query-only facade | Proposed |
| [ADR-008](../../architecture/decisions/ADR-008-f0003-deterministic-summaries.md) | Rule-based deterministic summaries; no model call generates a summary | Proposed |
| [ADR-009](../../architecture/decisions/ADR-009-f0003-review-gated-learning-proposals.md) | Learning proposals are inert, allowlisted, and append-only reviewed | Proposed |

### Pilot Note

Running F0003 through the `feature` action G0–G8 is the intended subject of F0007's live
governed pilot (F0007-S0009), so this feature carries that dependency as well as its own.

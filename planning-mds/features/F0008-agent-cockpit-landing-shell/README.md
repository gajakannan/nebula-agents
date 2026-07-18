# F0008 - Agent Cockpit Landing Shell

**Status:** Planned (Draft) - core scaffold; Phase A PRD only
**Priority:** High
**Phase:** Operator Experience
**Roadmap:** Later

## Overview

F0008 gives the Nebula Agents cockpit a front door. F0001 delivered a working curses dashboard but boots
straight into a bare session table, with no landing screen, no primary-action menu, and no command palette.
F0008 adds a keyboard-first landing shell — product identity, a select-driven action menu, a `/` command
palette, and a grounded workspace-health panel — over F0001's existing application services, routing into
its session, gate, and evidence surfaces. It preserves the tmux-native boundary: interactive conversation
still runs in the native provider via `attach`; the shell adds no embedded chat, orchestration, or provider SDK.

## Documents

| Document | Purpose |
|----------|---------|
| [PRD.md](./PRD.md) | Phase A product requirements for the landing shell |
| [design/landing-shell-mockup.html](./design/landing-shell-mockup.html) | Interactive, TUI-faithful mockup of the landing screen and command palette (visual contract for Phase B) |
| [STATUS.md](./STATUS.md) | Delivery state and planning checklist |

## Stories

No story files have been authored yet. This feature was created as a **core scaffold**: the PRD captures
scope and boundaries, and story decomposition is deferred to a future Phase A pass. See
[PRD.md](./PRD.md) → *Proposed Stories (to be authored)* for the candidate breakdown.

## Relationship to F0001

F0008 is a presentation-layer superset of F0001's curses TUI, not a replacement of the runtime. It reuses
F0001's application, domain, and infrastructure modules unchanged and must not remove the tmux-native
execution boundary. Surfaces owned by other features — knowledge graph (F0003/F0006) and agent roles
(F0007) — appear as explicitly gated "not available" states until those backends exist.

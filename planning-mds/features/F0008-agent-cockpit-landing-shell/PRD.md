# F0008 - Agent Cockpit Landing Shell PRD

## Feature Header

**Feature ID:** F0008
**Feature Name:** Agent Cockpit Landing Shell
**Priority:** High
**Phase:** Operator Experience
**Status:** Draft (Planned)
**Roadmap:** Later

## Feature Statement

**As a** product build operator
**I want** a keyboard-first landing and navigation shell for the Nebula Agents cockpit
**So that** I can resume or start missions, reach run/gate/evidence surfaces, run commands from a palette, and see workspace health from one front door instead of memorizing subcommands.

## Business Objective

- **Goal:** Give the cockpit a coherent front door so operators navigate by selection, not recall.
- **Metric:** An operator can reach every F0001 surface (sessions, detail, gate, evidence, transcript) and resume the most recent run from the landing screen without typing a subcommand.
- **Baseline:** F0001 boots directly into a bare session table; there is no home screen, no primary-action menu, and no command palette. Free-form input is limited to tiny inline prompts, and discovery relies on the `?` help view.
- **Target:** A landing screen with select-driven actions, a `/` command palette, a grounded workspace-health panel, and graceful gating of not-yet-built surfaces.

## Problem Statement

- **Current State:** F0001's curses cockpit is a competent dashboard but has no landing or navigation layer. A new operator sees an empty table with no obvious "what can I do here." Raw stdlib `curses` also makes richer layout — a logo, a menu, a palette, considered empty states — expensive to build and maintain.
- **Desired State:** A terminal shell renders a home screen and routes into the existing F0001 views, reusing the same application services and read-only projections. A command palette provides free-form entry without embedding a chat.
- **Impact:** Improves first-run comprehension and day-to-day navigation without changing the runtime or the tmux-native execution boundary. It also creates the surface into which future F0003/F0006/F0007 capabilities can be exposed as they land.

## Scope & Boundaries

**In Scope:**
- Landing/home screen: product identity, primary-action menu, workspace status panel, and a keybind footer.
- Primary actions: Resume current/last mission, Start a new mission (F0001 launch), Explore knowledge graph, Choose agent role, and Review repository health (F0001 doctor/preflight).
- A `/` command palette for free-form command entry and fuzzy navigation over the same versioned command set.
- Navigation/routing into existing F0001 surfaces: session list, run detail, gate review, and evidence/transcript.
- Graceful capability gating: menu items whose backends are not present degrade to an explicit "not available in this workspace" state.
- Migration of the presentation layer from stdlib `curses` to a richer terminal-UI framework, reusing F0001 application/domain/infrastructure unchanged.
- Defined empty/first-run states: no runs, no graph, nothing to resume.

**Out of Scope:**
- Embedding a conversational chat pane. Interactive conversation continues to run in the native provider inside tmux via `attach`.
- Any new orchestration, provider SDK, managed execution, or removal of the tmux-native boundary (that is F0002).
- Building the knowledge-graph backend, MCP tools, metrics, or artifact index (F0003/F0006).
- Building the agent-role orchestration engine or spec-driven runtime (F0007).
- Remote/multi-user collaboration or cloud-hosted execution.

## Acceptance Criteria Overview

- [ ] The cockpit opens to a landing screen with product identity, a select-driven primary-action menu, a workspace status panel, and a keybind footer.
- [ ] Arrow / `j`-`k` selection and Enter activation work; a `/` command palette accepts free-form command entry over the versioned command set.
- [ ] "Resume" reaches the most recent recoverable or active run; "Start a new mission" invokes the F0001 launch flow; "Review repository health" runs the doctor preflight.
- [ ] Menu items whose backends are absent (knowledge graph, agent roles) render an explicit "not available" state rather than erroring.
- [ ] All existing F0001 surfaces (sessions, detail, gate, evidence, transcript) remain reachable and behave as in F0001.
- [ ] The shell reuses F0001 application services and adds no orchestration, provider SDK, or embedded chat; the native provider remains the source of truth via `attach`.
- [ ] Terminal resize, minimum-size, and reduced-motion behavior are defined and safe.

## UX / Screens

| Screen | Purpose | Key Actions |
|--------|---------|-------------|
| Landing / Home | Front door: identity, primary actions, and workspace health. | Select action, open command palette, resume, quit. |
| Command Palette | Free-form command and fuzzy navigation over versioned commands. | Type command, run, cancel. |
| Session List (reuse F0001) | Active and recent runs. | Inspect, attach, validate. |
| Run Detail / Gate / Evidence (reuse F0001) | One run's state, gate decisions, evidence and transcript. | Inspect, decide gate, preview transcript. |

**Key Workflows:**
1. Land - operator opens the cockpit and sees the home screen with a highlighted "Resume" default.
2. Navigate - operator selects a primary action or opens the `/` palette to jump directly.
3. Route - selecting a run-oriented action enters the existing F0001 surface for that run.
4. Degrade - selecting an unbuilt capability shows an explicit "not available" state, not an error.

## Screen Layout (ASCII)

### Landing / Home - Desktop

```text
+----------------------------------------------------------------------+
|   .  *  .        N E B U L A                                          |
|  .:*#*:.         roles - evidence - delivery                         |
+----------------------------------------------------------------------+
| > Resume current mission                                          >   |
|   Start a new mission                                                 |
|   Explore knowledge graph            (not available in this workspace)|
|   Choose agent role                  (not available in this workspace)|
|   Review repository health                                           |
+----------------------------------------------------------------------+
| Workspace: nebula-insurance-crm                                      |
| Branch:    feat/kg-projection                                        |
| State:     contracts loaded - 3 runs (1 recoverable) - preflight ok  |
+----------------------------------------------------------------------+
| up/down navigate   enter select   / command   ? help   q quit        |
+----------------------------------------------------------------------+
```

Identity, menu, health panel, and footer are the four bands. Aspirational status fields
(knowledge-graph symbol counts, agent-load, cache) render only when a backing source exists;
otherwise they are omitted rather than shown with placeholder numbers.

## Visual Identity & Design Reference

An interactive, TUI-faithful mockup of the landing screen and command palette is committed at
[`design/landing-shell-mockup.html`](./design/landing-shell-mockup.html) (self-contained; open in a
browser). It renders the shell the way a character-cell terminal (`curses` / Textual) actually paints
it — no gradients, glow, drop-shadow, or sub-cell effects — and is the visual contract for Phase B.

Decisions the mockup fixes:

- **Rendering model — character cells only.** Box-drawing chrome (`┌─┐│├┤└┘`), one monospace face, a
  flat palette. Everything aligns to a fixed column grid (the mockup uses a 68-column interior).
- **Wordmark — Braille dot-matrix.** "NEBULA" is a 5×7 dot font rendered into Braille cells
  (2×4 sub-dots per cell, U+2800–28FF), so it reads as individual dots and prints in any Unicode
  terminal. It degrades to plain `NEBULA` on narrow or low-color terminals.
- **Starfield — character constellation.** The `.:*#*:.` nebula core (violet/cyan) nested in a field
  of `.`/`*` stars, a few tinted gold / blue-white / rose for stellar variety; the wordmark runs a
  soft violet→cyan→green nebula gradient across its columns. All plain colored cells.
- **Motion — stepped, honest, optional.** No alpha fade exists in a terminal, so a few glyph cells
  "flare" and a few stars twinkle by stepping through small **truecolor** ramps on one timer (as
  Textual would). Color/flare granularity is one cell = one glyph. Motion is truecolor-gated and
  goes fully static under `prefers-reduced-motion` and on 16/256-color terminals.
- **Status panel — grounded fields only.** Workspace, branch, run counts (active / recoverable), and
  preflight readiness. Fields needing an absent backend (KG symbols, agents loaded, cache) are omitted,
  never shown with placeholder numbers.
- **Gating — degrade with a live "why".** "Explore knowledge graph" and "Choose agent role" render an
  explicit `(not available in this workspace)` state and, when selected, surface the reason
  (which backend they await: F0006/F0003, F0007) rather than erroring.
- **Command palette.** A `/` palette does fuzzy navigation over the versioned command set (mirrors the
  F0001 verbs today; sources from F0007's versioned command policy once available).

## Data Requirements

**Reused (read-only) projections from F0001:**
- `sessions`, `status`, `evidence`, recovery candidates, and preflight results.

**Landing status panel fields:**
- `workspace_root`, `branch` (read from git, read-only), run counts (active / recoverable), and preflight readiness.
- Fields that require a backend not present in this repository (knowledge-graph symbols, agents loaded, cache hit) are shown only when a real source exists; otherwise omitted.

**State:**
- No new persisted records. The shell holds only ephemeral view state (selection, palette buffer, current route).

## Authorization

F0008 introduces no new roles or visibility rules. It invokes F0001's use cases under F0001's existing
local operator/reviewer policy (see [`../../security/f0001-authorization-model.md`](../../security/f0001-authorization-model.md))
and renders only what those read projections already expose — reviewer output stays sanitized exactly as in F0001.

## Success Criteria

- A new operator can identify and reach every available action from the landing screen without prior knowledge of the CLI verbs.
- Every existing F0001 surface remains reachable and unchanged in behavior.
- No fabricated or placeholder status is shown; unbuilt capabilities are explicitly gated.
- The tmux-native execution boundary is preserved: conversation still happens in the native provider via `attach`.

## Risks & Assumptions

- **Risk:** Adopting a richer TUI framework (e.g., Textual) adds a runtime dependency. **Mitigation:** presentation-only change; F0001 application/domain/infrastructure stay unchanged, and the curses `tui` path can remain until parity is proven.
- **Risk:** Product identity (dot-matrix wordmark, particle field) could over-decorate. **Mitigation:** keep identity tasteful and optional; it must never obstruct navigation.
- **Risk:** Status fields could imply backends that do not exist. **Mitigation:** render only grounded metrics; gate the rest.
- **Assumption:** F0001 application services and read-only projections are stable and reusable as a library boundary from a new presentation layer.

## Dependencies

- F0001 application, domain, and infrastructure modules (reused as the service boundary).
- A terminal-UI framework selection is a Phase B (Architecture) decision; Textual is the leading candidate.
- Optional future data sources from F0003 (control plane / metrics), F0006 (compiled knowledge graph), and F0007 (agent roles / spec-driven runtime) for the gated menu items.

## Relationship to Other Features

- **F0001 (Tmux-Native Agent Cockpit, archived/done):** F0008 reuses its services and is a presentation-layer superset of its curses TUI, not a replacement of the runtime.
- **F0002 (Managed Agent Orchestration):** independent; F0008 must not remove the tmux-native boundary.
- **F0003 (Local Agent Runtime Control Plane) / F0006 (Compiled KG Projection):** provide the eventual backends for "Explore knowledge graph" and richer health/metrics; until then those surfaces are gated.
- **F0007 (Spec-Driven Orchestration):** provides the agent-role / spec-driven capability behind "Choose agent role"; gated until available.

## Proposed Stories (to be authored)

This feature is a **core scaffold** — Phase A PRD only; no story files exist yet. Candidate decomposition
for a future Phase A story pass:

- **F0008-S0001** — Landing screen and primary-action navigation
- **F0008-S0002** — Command palette and free-form command entry
- **F0008-S0003** — Workspace status and health panel (grounded fields only)
- **F0008-S0004** — Terminal-UI shell migration over F0001 services
- **F0008-S0005** — Graceful capability gating for absent backends
- **F0008-S0006** — Routing into F0001 session / gate / evidence surfaces

## Open Questions

- Terminal-UI framework: adopt Textual, or continue with stdlib `curses`?
  → **Leaning Textual.** The design mockup (`design/landing-shell-mockup.html`) validates the
  box-drawing chrome, full-row selection highlight, and command palette against a Textual-shaped model;
  stdlib `curses` would make the same layout expensive to build and maintain. Final ratification is a
  Phase B / Architecture decision.
- Identity treatment (dot-matrix wordmark, particle field): in-product, docs-only, or both?
  → **Resolved: in-product, TUI-faithful.** Braille dot-matrix wordmark + character starfield, with a
  plain-`NEBULA` fallback for narrow/low-color terminals. Kept tasteful; it must never obstruct navigation.
- Command-palette surface: mirror the CLI verbs exactly, or a curated subset?
  → **Mirror the versioned command set.** The mockup mirrors the F0001 verbs today and should source
  from F0007's versioned command policy once that lands, rather than hand-maintaining a list.
- Does F0008 replace the F0001 `tui` command, or ship as a new default `home` entrypoint with `tui`
  retained? *(Still open — the mockup assumes an opt-in surface with `tui` retained until parity; final
  entrypoint naming is a Phase B decision.)*

## Rollout & Enablement

- Deliver as an opt-in local surface; the F0001 curses `tui` remains available until parity is demonstrated.
- No provider, auth, or persistence changes.
- Require the tmux-native boundary and recovery path to remain intact before enablement.

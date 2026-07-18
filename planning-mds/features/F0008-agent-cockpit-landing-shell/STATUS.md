# F0008 - Agent Cockpit Landing Shell - Status

**Overall Status:** Planned
**Last Updated:** 2026-07-17

## Planning Status

| Item | State | Evidence |
|------|-------|----------|
| Phase A requirements | Draft available | `PRD.md` (core scaffold) |
| Phase A design mockup | Available | `design/landing-shell-mockup.html` (TUI-faithful landing + command palette; visual contract) |
| Story decomposition | Not started | Candidate stories listed in `PRD.md` → *Proposed Stories* |
| Phase B architecture | Not started | Framework leaning **Textual** (mockup validates the approach); ratification pending |
| Registration | Registered | `features/REGISTRY.md` (Planned), `features/ROADMAP.md` (Later), `BLUEPRINT.md` |

## Scope Note

This feature was created as a **core scaffold** at the operator's request: a registered Phase A PRD that
captures the landing-shell scope and boundaries, with story files deferred until scope firms up. It is
not yet in progress and carries no implementation or signoff provenance.

## Tracker Sync Checklist

- [x] `planning-mds/features/REGISTRY.md` — F0008 listed under Planned (generated from `kg-source/features/F0008.yaml`)
- [x] `planning-mds/features/ROADMAP.md` — F0008 placed in Later (generated)
- [x] `planning-mds/features/STORY-INDEX.md` — regenerated (no stories yet)
- [x] `planning-mds/BLUEPRINT.md` — F0008 feature line added (no stories yet)

## Next Steps

1. Ratify the terminal-UI framework at Phase B / Architecture — Textual is the leading candidate, and
   the design mockup (`design/landing-shell-mockup.html`) demonstrates the approach.
2. Confirm whether F0008 replaces the F0001 `tui` command or ships as a new default `home` entrypoint.
3. Author the Phase A story set once scope is confirmed (candidates in `PRD.md` → *Proposed Stories*).

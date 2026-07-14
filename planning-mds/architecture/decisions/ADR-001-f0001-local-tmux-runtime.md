# ADR-001: F0001 Uses a Local Python Cockpit Around Native Tmux Sessions

## Status

- [ ] Proposed
- [x] Accepted
- [ ] Superseded
- [ ] Rejected

**Accepted:** 2026-07-13T21:39:29-04:00 by explicit operator approval.

## Context

F0001 must preserve the interactive Codex and Claude Code terminal experience, existing subscription-authenticated sessions, human tool approvals, scrollback, and detach/reattach recovery. The repository currently consists primarily of Python validation/orchestration scripts and Markdown contracts. A hosted service or SDK-only runtime would introduce a second interaction model before native parity is understood.

## Decision Drivers

- Preserve provider-owned interactive UI and authentication.
- Keep the MVP single-host and recoverable after the cockpit exits.
- Reuse the repository's Python operational stack.
- Leave explicit seams for F0003 control-plane and F0002 managed-provider evolution.
- Avoid a server, database, or deployment requirement for the first usable surface.

## Decision

F0001 is a single local Python 3.11+ executable with CLI and full-screen TUI presentation over Application, Domain, and Infrastructure Adapter modules. The portable baseline renderer uses the POSIX terminal/curses capability behind a presentation interface; implementation may replace that renderer only if the same command, accessibility, resize, and lifecycle contracts remain intact.

Tmux owns session durability and hosts exactly one native provider CLI per run. The cockpit may launch, probe, attach, watch evidence, record explicit decisions, and render sanitized recovery state. It never screen-scrapes provider output to infer provider or lifecycle approval.

The MVP supports POSIX and WSL environments where tmux, Python, and the provider CLI share the same environment. It exposes no HTTP daemon, remote collaboration, database, MCP server, or provider SDK.

## Options Considered

1. **Local Python cockpit + tmux/native CLIs:** Selected.
2. **Managed provider SDK/service first:** Rejected for F0001; loses or must recreate native interaction and subscription-login behavior.
3. **Shell scripts only:** Rejected; insufficient state modeling, validation, testability, and TUI structure.
4. **Web UI with local daemon:** Rejected; adds transport, auth, deployment, and browser state without addressing the primary native-session risk.

## Pros / Cons

**Local Python cockpit**
- Pro: native provider remains source of truth.
- Pro: tmux survives TUI/process exit and supports direct fallback.
- Pro: clean adapter seams and deterministic local tests.
- Con: POSIX/WSL scope excludes native Windows tmux operation.
- Con: terminal compatibility and subprocess lifecycle require focused integration tests.

**Managed service first**
- Pro: richer structured events and remote control.
- Con: duplicates F0002/F0003 scope and risks premature loss of interactivity.

## Consequences

- F0001 implementation belongs in a Python package with explicit ports; no new .NET/React stack is introduced.
- Direct `tmux attach` remains an operator recovery path.
- F0003 must build on the run identity and read contracts instead of replacing tmux durability.
- F0002 cannot remove the native path until closeout evidence proves parity.
- The feature assembly plan created at G0 must name the renderer and module/file layout while respecting these boundaries.

## Security & Compliance Notes

- Provider login remains provider-owned; the cockpit cannot read credential bodies.
- OS identity is the local authentication boundary.
- A local TUI is not an authorization boundary; use cases enforce policy.

## References

- [F0001 PRD](../../features/F0001-tmux-native-agent-cockpit/PRD.md)
- [Codex authentication documentation](https://learn.chatgpt.com/docs/auth.md)
- [Codex CLI command documentation](https://learn.chatgpt.com/docs/developer-commands.md?surface=cli)
- [F0003 PRD](../../features/F0003-local-agent-runtime-control-plane/PRD.md)

## Follow-up Actions

- [x] Define local component and system diagrams.
- [x] Define persistence, execution, transcript, and authorization contracts.
- [ ] At feature G0, produce the implementation-level feature assembly plan.
- [x] Accepted through the Phase B operator approval gate.

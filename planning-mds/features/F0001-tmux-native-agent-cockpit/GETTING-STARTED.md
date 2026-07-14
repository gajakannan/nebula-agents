# F0001 - Tmux-Native Agent Cockpit - Getting Started

## Prerequisites

- [ ] `tmux` installed and available on `PATH`.
- [ ] At least one supported provider CLI installed: `codex` or `claude`.
- [ ] Provider CLI authenticated in the shell where Nebula Agents is launched.
- [ ] Workspace root points at `/home/gajap/uSandbox/repos/nebula/nebula-agents` or an explicitly supplied product root.

## Services to Run

F0001 is local terminal tooling. No server is required for the MVP.

```bash
# From the repository root, create an isolated environment and install F0001.
python3 -m venv .venv
.venv/bin/pip install -e 'engine[test]'

# Inspect readiness without creating runtime state.
.venv/bin/nebula-agents doctor --provider codex --action feature

# Launch one governed native provider session. Launch prints the run ID and
# exact TUI/attach next commands; it does not replace the native tmux UI.
.venv/bin/nebula-agents launch --feature F0001 --provider codex --action feature
.venv/bin/nebula-agents tui --run-id <RUN_ID>

# Inspect or reattach to a recorded run.
.venv/bin/nebula-agents sessions
.venv/bin/nebula-agents status --run-id <RUN_ID>
.venv/bin/nebula-agents attach --run-id <RUN_ID>
.venv/bin/nebula-agents recover --run-id <RUN_ID>
```

To run the installed command from another directory, set the product root once:

```bash
export NEBULA_AGENTS_PRODUCT_ROOT=/home/gajap/uSandbox/repos/nebula/nebula-agents
cd /tmp
/home/gajap/uSandbox/repos/nebula/nebula-agents/.venv/bin/nebula-agents doctor --provider codex --action feature
```

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `NEBULA_AGENTS_PRODUCT_ROOT` | Product root used for planning docs and evidence paths. | Current working directory |
| `NEBULA_AGENTS_RUNTIME_DIR` | Local runtime state directory for session registry and transient files. | `.nebula-agents/runtime` |
| `NEBULA_AGENTS_PROVIDER` | Optional preferred provider key. | Auto-detect |

## Seed Data

No seed data is required. The first launch creates local run metadata for the selected feature or story.

## How to Verify

1. Run `nebula-agents doctor --provider codex --action feature --format json` and confirm the overall status is `ready`.
2. Launch a tmux-backed provider session with `nebula-agents launch --feature F0001 --provider codex --action feature`.
3. Use either next command printed by launch: `nebula-agents tui --run-id <RUN_ID>` opens the cockpit, while `nebula-agents attach --run-id <RUN_ID>` enters the provider's native tmux UI.
4. Run an allowlisted validator with `nebula-agents validate --run-id <RUN_ID> --validator stories`.
5. Inspect sanitized run and evidence projections with `status` and `evidence`; enable transcript capture explicitly only when needed.
6. If the current snapshot becomes corrupt, `sessions` keeps the recoverable run discoverable and `recover --run-id <RUN_ID>` restores only a validated local state image; recovery never starts a provider or attaches automatically.

## Key Files

| Layer | Path | Purpose |
|-------|------|---------|
| Planning | `planning-mds/features/F0001-tmux-native-agent-cockpit/PRD.md` | Feature requirements |
| Planning | `planning-mds/features/F0001-tmux-native-agent-cockpit/F0001-S*.md` | Implementation stories |
| Prompts | `agents/templates/prompts/evidence-contract/` | Operator-friendly and automation-safe prompt contracts |
| Validation | `agents/product-manager/scripts/validate-stories.py` | Story completeness validation |
| Validation | `agents/product-manager/scripts/validate-trackers.py` | Tracker consistency validation |
| Runtime | `engine/src/nebula_agents/` | Domain, application, infrastructure, CLI, and TUI implementation |
| Tests | `engine/tests/` | Unit, contract, integration, security, and real-tmux coverage |

## Dev User Credentials

Provider credentials are not managed by Nebula Agents. Use the local provider CLI login flow before launching the TUI. F0001 must not ask users to paste subscription credentials or API keys into Nebula-managed prompts.

## Notes

- A tmux launch should inherit the authenticated shell environment. If a provider prompts for login, the native provider CLI owns that interaction.
- Transcript capture must assume terminal output can contain sensitive data and must redact before writing review evidence.
- Do not split long-running feature builds into disconnected prompts for this MVP; the tmux session is the continuity boundary.
- The MVP runtime target is POSIX or WSL with Python 3.11+, tmux, and the provider CLI installed inside the same environment.
- Transcript capture is disabled by default and must be enabled explicitly per run. A redaction failure stops transcript writes but does not disable attach.
- `launch`, `tui`, and `attach` are deliberately separate actions: launch creates the governed provider session, the TUI observes and controls it, and attach hands the terminal to the native provider UI.
- Runtime directories and files default to modes `0700` and `0600`. Moving the runtime root to a shared or permissive directory violates the architecture contract.
- F0001 has no HTTP daemon, database, MCP surface, artifact index, metrics store, or learning loop. Those capabilities remain in F0003/F0002.
- Phase B architecture is indexed from [`README.md`](./README.md); the implementation-level `feature-assembly-plan.md` was created and validated by the `feature` action at G0.

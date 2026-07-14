# Runtime Preflight — F0001-tmux-native-agent-cockpit run 2026-07-13-1cfbc5a0

## Feature

- Feature ID: F0001
- Run ID: `2026-07-13-1cfbc5a0`
- Date: 2026-07-13
- Owner: Feature Orchestrator acting in the DevOps preflight role

## Runtime Services / Containers / Jobs

F0001 is intentionally non-containerized. The runtime surfaces are the local Python interpreter and libraries, POSIX terminal/curses and file-lock support, local tmux server/socket, installed native Codex and Claude CLIs, committed evidence-contract prompts, and the product workspace/schema paths. There is no API, worker, database, frontend dev server, AI service, or network health endpoint.

## Command Evidence

- `python3 --version` -> Python 3.14.4, above the 3.11 compatibility floor.
- Python imports -> `jsonschema` 4.19.2, `curses`, and `fcntl` available.
- `tmux -V` -> tmux 3.6.
- `codex --version` -> codex-cli 0.144.3; `codex --help` exposes interactive optional prompt and `-C/--cd` workspace arguments.
- `claude --version` -> Claude Code 2.1.207; `claude --help` exposes the interactive prompt argument.
- Workspace/prompt/schema readability checks -> all required paths present and workspace writable.
- Sandboxed `tmux new-session` -> exit 1, `Operation not permitted` on the tmux socket; classified `runtime-blocked` by sandbox isolation.
- Exact elevated retry `tmux new-session -d -s nebula-g1-1cfbc5a0 "sleep 30"` -> exit 0.
- `tmux has-session -t nebula-g1-1cfbc5a0` -> exit 0.
- `tmux kill-session -t nebula-g1-1cfbc5a0` -> exit 0; temporary session removed.

No provider login, credential read, auth-cache inspection, model turn, API call, or persistent provider session was attempted.

## Health Status

| Service | Status | Notes |
|---------|--------|-------|
| Python runtime | Healthy | 3.14.4; stdlib curses/fcntl and jsonschema available. |
| Product workspace | Healthy | Planning, prompt, schema, and writable-root checks passed. |
| tmux runtime | Healthy | Real create/probe/destroy passed outside the filesystem sandbox. |
| Codex adapter target | Healthy for implementation | Executable/help/version available; startup/auth classification remains adapter-test scope. |
| Claude adapter target | Healthy for implementation | Executable/help/version available; startup/auth classification remains adapter-test scope. |
| Containers/network services | Not applicable | Approved architecture is a local process with no service topology. |

## Installed-Package Recheck

After `engine/pyproject.toml` and the console entry point existed, G1 was repeated before final acceptance/security evidence:

- `/tmp/f0001-venv/bin/python -c "import nebula_agents; ..."` -> version `0.1.0`, exit 0.
- `/tmp/f0001-venv/bin/nebula-agents --help` -> approved public command set, exit 0.
- `/tmp/f0001-venv/bin/nebula-agents doctor --provider codex --action feature --format json` -> `overall_status=ready`, tmux 3.6 and Codex CLI 0.144.3, exit 0.
- Final elevated real-tmux/fake-provider launch and attach -> one provider start, exit 0.

This recheck supersedes the earlier follow-up; no runtime-blocked condition remains.

## Restore Steps If Unavailable

- If tmux returns socket permission errors inside a restricted runner, rerun the exact preflight in an approved host/runtime context; do not edit product code first.
- If tmux is missing, install it in the same POSIX/WSL environment as the provider CLI and rerun `tmux -V` plus create/probe/destroy.
- If a provider executable is missing, install/select the other supported native CLI and rerun help/version; login remains provider-owned.
- If Python dependencies are absent, create an isolated environment from `engine/pyproject.toml` after Step 1 and rerun G1 before tests.

## Recommendations (when `WITH RECOMMENDATIONS`)

None.

## Result

PASS

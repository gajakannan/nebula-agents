# Runtime Preflight — F0001 remediation run 2026-07-14-b885d64c

## Environment Summary

- Product root: `/home/gajap/uSandbox/repos/nebula/nebula-agents`
- Isolated G1 runtime root: `/tmp/f0001-remediation-g1-b885d64c`
- Python: `3.14.4`
- tmux: `3.6` at `/usr/bin/tmux`
- Codex: `codex-cli 0.144.3` at `/home/gajap/.local/bin/codex`
- Claude Code: `2.1.207`
- Package: editable `nebula_agents` import resolves to `engine/src/nebula_agents`

## Checks Performed

| Check | Result | Notes |
|-------|--------|-------|
| Python and `jsonschema` imports | PASS | Editable package imports from this workspace. |
| Resolved dependency consistency | PASS | `pip check` reported no broken requirements; pip cache ownership warning is non-blocking and outside the environment. |
| Installed `nebula-agents --help` | PASS | CLI exposes doctor, launch, attach, sessions, status, evidence, validate, and tui. |
| Isolated Codex doctor JSON | PASS | `overall_status=ready`; absolute workspace, planning, runtime, prompt, tmux, and provider paths were present. |
| Provider executables | PASS | Codex and Claude version probes completed; Codex printed a non-blocking read-only alias warning. |
| Existing demo session isolation | PASS | `tmux has-session -t nebula-F0001-c3a640c7` returned absent; no create/attach/kill action targeted that name. |
| Unique tmux smoke | PASS | `nebula-g1-b885d64c` was created, found, and destroyed. |

## Runtime Initialization

Doctor used a remediation-only runtime root in `/tmp`. It reported that the directory will be initialized owner-only on the first authorized mutation. No provider session or registry run was created by the doctor probe.

## Blockers

None.

## Result

PASS

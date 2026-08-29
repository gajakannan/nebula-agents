# Runtime Preflight — F0003 run 2026-08-29-16075bda

**Gate:** G1 · **Role:** DevOps · **Date:** 2026-08-29 · **Result: PASS**

`runtime_bearing` is `true` (implementation lands in `engine/**`), so this artifact is
required rather than omitted.

## Environment Summary

| Item | Value |
|------|-------|
| Product root | `/home/gajap/uSandbox/repos/nebula/nebula-agents` |
| Isolated G1 runtime root | `/tmp/f0003-g1-16075bda` (never the workspace runtime dir) |
| Python (primary) | `3.14.4` |
| Python (CI matrix) | `3.11.15`, `3.12.13`, `3.14.4` |
| tmux | `3.6` at `/usr/bin/tmux` |
| Codex | `codex-cli 0.145.0` at `~/.local/bin/codex` |
| Claude Code | `2.1.251` at `~/.nvm/versions/node/v24.16.0/bin/claude` |
| Package | editable `nebula_agents` resolves to `engine/src/nebula_agents` |
| Declared runtime deps | `jsonschema>=4.18,<5` — **unchanged**, as ADR-005/ADR-007 require |

## Checks Performed

| Check | Result | Notes |
|-------|--------|-------|
| Editable package import | PASS | Resolves to this workspace, not a site-packages copy |
| Resolved dependency consistency | PASS | `pip check` — no broken requirements |
| Installed `nebula-agents --help` | PASS | Exposes F0001's nine commands; F0003 adds twelve more |
| `doctor` on an isolated runtime root | PASS | `overall_status=ready`, exit 0 |
| Runtime-directory ownership guard | PASS | See *Ownership Guard* below — the guard actively denied an unsafe root |
| tmux isolation | PASS | `nebula-g1-16075bda` confirmed absent before use; no existing session targeted |
| tmux lifecycle smoke | PASS | Unique session created, found, destroyed, confirmed absent |
| Real-tmux integration test | PASS | `test_real_tmux_lifecycle.py` **ran** — it did not skip |
| Six F0003 schemas resolve | ~~PASS~~ **CORRECTED — see below** | The claim was wrong; the registry allowlist accepted only `f0001-` names |
| ADR-006 root selection | PASS | See *Approved Roots* below |
| Dependency-free MCP precedent | PASS | `scripts/kg/mcp_server.py` uses stdlib plus local siblings only — no third-party package |
| Engine baseline, full CI matrix | PASS | **514 tests pass on 3.11, 3.12, and 3.14** |
| Security suite | PASS | 81 tests |
| Contract suite | PASS | 67 tests |

## Ownership Guard

A pre-created runtime root under the default umask (mode `0755`) was **denied** by `doctor`
with `runtime_directory: Runtime directory ownership or permissions are unsafe.` and exit 3.
The same root at mode `0700`, and an absent root, both returned `ready` and exit 0.

This is recorded because it is not incidental: BLUEPRINT §5.6 specifies F0003's artifact
index and proposal store as `0600` inside `0700` directories, and this guard is the existing
mechanism F0003 extends. It is verified working before that extension is built.

## Approved Roots

F0003 admits three approved roots. In this environment they **nest**, which is precisely the
condition ADR-006's longest-match rule exists to resolve:

| Root | Path | Mode |
|------|------|------|
| workspace | `<product root>` | `0755` |
| runtime | `<ws>/.nebula-agents/runtime` | `0700` |
| evidence | `<ws>/planning-mds/operations/evidence` | `0755` |

Both runtime and evidence sit *inside* workspace, so a fixed root order would give the wrong
answer. Longest-match with the `runtime > evidence > workspace` tiebreak was executed against
real paths in this environment:

| Path | Owning root | Expected |
|------|-------------|----------|
| `<ws>/.nebula-agents/runtime/runs/X/artifacts.json` | runtime | runtime |
| `<ws>/planning-mds/operations/evidence/runs/2026-08-29-16075bda/commands.log` | evidence | evidence |
| `<ws>/engine/src/nebula_agents/bootstrap.py` | workspace | workspace |
| `/tmp/outside/x.log` | none — policy violation | none |

All four match. The rule is well-defined in this environment before any code depends on it.

## Runtime Initialization

`doctor` used an isolated `/tmp` runtime root and reported that the directory is initialized
owner-only on the first authorized mutation. **No provider session, registry run, or
workspace runtime state was created by this preflight.** The temporary root and the temporary
tmux session were both removed.

## Configuration Gap Confirmed (not a blocker)

`RuntimeConfig` (`infrastructure/config.py`) currently carries `workspace_root`,
`runtime_root`, `schema_root`, `feature_root`, `prompt_root`, and `runs_root` — but **no
`evidence_root`**, which F0003 needs as its third approved root. The directory exists and is
readable; only the config field is absent. This is already an "Existing Code (Must Be
Modified)" row in the assembly plan, and G1 confirms the environment supports it.

## Correction — issued 2026-08-29 during Step 3

**The "six F0003 schemas resolve" row above was wrong**, and is corrected here rather than
edited away.

`JsonSchemaRegistry._load` allowlisted schema names beginning `f0001-` only. Every F0003
schema name was refused. The G1 probe called `registry.validate(name, {})` and read the
resulting `NebulaError` as "rejects an empty document" — the expected outcome — when it was
in fact "Schema name is not allowlisted". A refusal was mistaken for a validation.

The underlying capability claim — that the six schemas are loadable without rewriting the
registry — held. What was wrong was "no registry change": widening the allowlist to
`("f0001-", "f0003-")` is a real, if small, change, and it was made in Step 3.

The probe was weak in a specific way worth naming: it asserted only that *an* error was
raised, never which one. Any error would have passed it. The replacement,
`test_the_schema_registry_allowlists_f0003_but_not_arbitrary_names`, loads each F0003
schema and requires success, and separately requires refusal for a non-allowlisted name,
a traversal attempt, and a non-schema file.

This does not change the G1 verdict. No blocker was missed, and no other row depended on it.

## Blockers

None.

## Result

PASS

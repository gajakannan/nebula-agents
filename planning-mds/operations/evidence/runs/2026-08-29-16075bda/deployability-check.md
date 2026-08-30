# Deployability Check — F0003

**Run:** `2026-08-29-16075bda` · **Gate:** G2 · **Owner:** DevOps · **Date:** 2026-08-29
F0003 changes no deployment topology. It is a local CLI extension of an existing local
package: no service, daemon, port, database, or hosted component (ADR-005). "Deployment"
here means installation and first-run behaviour on an operator's machine.

## Probes executed

Each row was run, not described.

| Probe | Result |
|-------|--------|
| Clean `pip install ./engine` into an empty 3.11 venv | PASS |
| Runtime dependency closure | 6 packages — `jsonschema` and its transitive deps. **No new required dependency** |
| `nebula-agents --help` from the clean install | PASS — all 14 commands listed |
| `nebula-agents mcp serve` with no MCP SDK present | PASS — responds to `ping` and `tools/list` |
| `sessions` against an absent runtime directory | PASS — returns empty; **the directory is not created** |
| Installed package size | 1.3 MB |
| Compiled extensions in F0003 code | none (the one `.so` present is `rpds`, a `jsonschema` transitive dep) |
| Cold import of the CLI | ~17.6 ms cumulative |

## First-run behaviour

The runtime directory is created by the first authorized **mutation**, never by a read or
a probe — verified directly: `sessions` against an absent root leaves it absent. A
pre-existing directory with unsafe permissions is refused (`0755` denied, `0700` and
absent both accepted), which G1 confirmed and F0003's stores extend to the artifact index,
summaries, proposals, and capability reports.

## Rollback

Uninstalling reverts the command surface. F0003 writes only additive artifacts under the
runtime root — `artifacts.json`, `summaries/`, `proposals/`, `capabilities/` — and never
rewrites an F0001 record shape. A downgrade to a `1.0` client leaves those files unread
rather than misread, with one exception: **a strict `1.0` reader will reject the new
`event_type` values in `events.jsonl`** (finding S3-F1). That is the one place a rollback
is not clean, and it is the Architect decision carried to G3.

## Findings

### S9-F1 (Medium) — fixed at this gate

Outside a configured workspace, every MCP tool returned **success with an empty result**
instead of an error. A host pointed at the wrong directory produced an empty session list
and an empty evidence list — indistinguishable from a real run with no evidence. A
reviewer would read "this run has nothing" rather than "I am in the wrong tree".

`docs/mcp-host-configuration.md` already documented `WORKSPACE_NOT_CONFIGURED` for this
case: **the documentation was right and the code was not.** A workspace probe was added,
the tools now return that error, and three tests cover it. Found by running the documented
troubleshooting steps from outside a workspace rather than by reading them.

### S9-F2 (Low) — recorded, not fixed

`nebula-agents doctor` outside a workspace reports `SCHEMA_INVALID` — "Schema cannot be
loaded. Restore the committed schema." — and exits 9 (state-io). Nothing is corrupt; the
operator is in the wrong directory. The correct class is preflight/setup, exit 3.

This is **pre-existing F0001 behaviour** in the schema registry's load path, not F0003
code. It is recorded rather than fixed because reclassifying an F0001 error is a contract
change that belongs to whoever owns that path, and the 514-test regression boundary makes
it a reviewed change rather than a drive-by. The MCP documentation no longer sends
operators to `doctor` for this diagnosis.

## Recommendations

- [low] Reclassify `nebula-agents doctor` outside a workspace from `SCHEMA_INVALID` exit 9 to a preflight/setup error exit 3, so an operator in the wrong directory is not told their schemas are corrupt (S9-F2) — owner: Architect; follow-up: F0001 backlog, not this run
- [medium] Decide whether the `event_type` enum extension is acceptable given that a strict `1.0` reader rejects unknown values, which is the one place rollback is not clean (S3-F1) — owner: Architect; follow-up: decide at G3

## Result

PASS WITH RECOMMENDATIONS

Installation, first run, and rollback are clean. S9-F1 was found and fixed at this gate.

# KG Reconciliation — F0001-tmux-native-agent-cockpit run 2026-07-14-b885d64c

## Binding Delta

The as-built source confirms all six capabilities predicted at G0. The candidate implementation is frozen at `99d2020c8ccaa23f370eef526c27867395981c7e`, but this product repository has not adopted the compiled-projection source/toolchain required to author or validate the bindings.

| Capability / node | Required code-index binding (glob) | G0-declared? | Action |
|-------------------|------------------------------------|--------------|--------|
| `F0001.NativeSessionPreflight` | `engine/src/nebula_agents/application/preflight.py`, `engine/src/nebula_agents/infrastructure/providers.py`, `engine/src/nebula_agents/infrastructure/config.py` | yes | blocked — no `kg-source/bindings/**` contract exists |
| `F0001.TmuxSessionLifecycle` | `engine/src/nebula_agents/application/runs.py`, `engine/src/nebula_agents/infrastructure/tmux.py`, `engine/src/nebula_agents/presentation/session_entry.py` | yes | blocked — no binding compiler exists |
| `F0001.LocalRunRegistry` | `engine/src/nebula_agents/domain/**`, `engine/src/nebula_agents/infrastructure/filesystem_store.py` | yes | blocked — no binding compiler exists |
| `F0001.EvidenceAndGateControl` | `engine/src/nebula_agents/application/gates.py`, `engine/src/nebula_agents/infrastructure/watcher.py`, `engine/src/nebula_agents/presentation/tui.py` | yes | blocked — no binding compiler exists |
| `F0001.RedactedTranscriptRecovery` | `engine/src/nebula_agents/application/transcripts.py`, `engine/src/nebula_agents/infrastructure/transcript*.py`, `engine/src/nebula_agents/domain/redaction.py` | yes | blocked — no binding compiler exists |
| `F0001.ReadOnlyRunQueries` | `engine/src/nebula_agents/application/queries.py`, `engine/src/nebula_agents/presentation/cli.py`, `engine/src/nebula_agents/presentation/formatters.py` | yes | blocked — no binding compiler exists |

No shard or generated projection was fabricated. `planning-mds/features/TRACKER-GOVERNANCE.md` still states that `nebula-agents` has not adopted the shard model and tracks adoption as follow-up work. The F0001 assembly plan classifies this as a High closeout blocker requiring explicit governance/bootstrap resolution before G8.

## Canonical Nodes

The implementation introduces the six capability semantics listed above plus schema, authorization-policy, workflow, and ADR surfaces. They require canonical nodes/rationale when the product adopts the compiled graph. None can be truthfully authored or compiled now because `planning-mds/kg-source/`, its schema/README, and `planning-mds/knowledge-graph/` are absent.

## Validator Results

| Check | Command | Result |
|-------|---------|--------|
| Candidate reproducibility | compare `git diff --name-only main...99d2020c8ccaa23f370eef526c27867395981c7e` with `artifacts/diffs/changed-files.txt` | PASS — exact 160-path match |
| Product KG source audit | `test ! -e planning-mds/kg-source` | CONFIRMED ABSENT |
| Product KG compiler audit | `test ! -e scripts/kg/compile.py` | CONFIRMED ABSENT |
| Product KG validator audit | `test ! -e scripts/kg/validate.py` | CONFIRMED ABSENT |
| Compile projection | `python3 scripts/kg/compile.py` | BLOCKED — command does not exist; not invoked as a false validation |
| Symbol/decision regeneration and checks | `python3 scripts/kg/validate.py --regenerate-symbols --check-symbols --regenerate-decisions --check-decisions` | BLOCKED — command does not exist |
| Drift/reproducibility | `python3 scripts/kg/validate.py --check-drift` and `--check-reproducible` | BLOCKED — command does not exist |

`coverage-report.yaml` was not regenerated at G7, as required; no such product KG artifact/tool currently exists.

Result: BLOCKED

## Handoff to Closeout

The semantic graph is not green and G8 closeout is not authorized. Resolution requires an explicit governance choice outside the approved F0001 implementation candidate:

1. adopt the compiled KG source, compiler, validator, and initial F0001 feature/node/binding shards in this product repository; or
2. change the framework/product governance contract through an explicitly approved exception mechanism for products that have not adopted the KG toolchain.

Until one of those paths is approved and implemented, do not archive F0001, publish `latest-run.json`, mark the manifest approved, or claim G7/G8 success.

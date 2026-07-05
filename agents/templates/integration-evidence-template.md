# Integration Evidence Run — Template

Integration runs use the **base run** profile at
`{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}/`
(`RUN_ID` = `integrate-YYYYMMDD-HHMMSS`, UTC) plus the integration-specific
artifacts below. Runs are append-only: a re-run after a bounce, conflict
resolution, or failed gate-2 validation is a **new** run that references the
prior one — never an edit.

## Required files

| File | Content |
|------|---------|
| `action-context.md` | action=integrate, operator, UTC start/end, SOURCE branch/PR, INTEGRATION_BRANCH, merge-base SHA, mainline SHA at start, run outcome (`merged-pending-push` / `bounced` / `halted-conflicts` / `halted-validation` / `gate2-failed`) |
| `artifact-trace.md` | files merged (curated), files regenerated (generated), evidence artifacts written |
| `gate-decisions.md` | **Gate I0**: verdict reference or waiver + rationale + decider + timestamp. **Gate I6**: maintainer test-validation outcome (pass/fail) + what was exercised + timestamp. Both gates always recorded, even on halts (record “not reached”) |
| `commands.log` | every command with exit code (JSONL, §13 schema) |
| `lifecycle-gates.log` | `run-lifecycle-gates.py` output |
| `integration-report.json` | machine-readable summary (schema below) |
| `artifacts/merge3-*.json` | one merge3/tracker JSON report per merged file |

## `integration-report.json` schema

```json
{
  "schema_version": 1,
  "run_id": "integrate-YYYYMMDD-HHMMSS",
  "mode": "live | dry-run",
  "source": "<branch or PR ref>",
  "source_head_sha": "<sha>",
  "integration_branch": "<branch>",
  "merge_base_sha": "<sha>",
  "gate1": {"verdict_ref": "<ref-or-null>", "waiver": {"rationale": "...", "decided_by": "...", "date": "YYYY-MM-DD"}},
  "branch_verification": {"result": "pass | bounce", "details": "<what was stale, commands issued>"},
  "merges": [{"file": "<path>", "result": "clean | conflicts", "report": "artifacts/merge3-<name>.json"}],
  "regeneration": ["<commands run>"],
  "validation": [{"command": "...", "exit_code": 0}],
  "conflicts_routed": [{"kind": "...", "record_id": "...", "owning_role": "..."}],
  "prepared_merge_sha": "<sha-or-null>",
  "gate2": {"result": "pass | fail | not-reached", "exercised": "...", "recorded_by": "...", "date": "YYYY-MM-DD"},
  "pushed": false,
  "supersedes_run": "<prior-run-id-or-null>"
}
```

Rules:

- `pushed` is written by the maintainer after the push, as the final edit of
  the run before it freezes.
- Timestamps live here and in logs only — never in committed projections.
- A `dry-run` mode run must label every simulated input (e.g., a placeholder
  gate-1 waiver) as simulated inside `gate-decisions.md`.
- Conflict/bounce reports must be verbatim tool output (merge3 text + JSON),
  not paraphrase.

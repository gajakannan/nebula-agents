# Implementation Validation Report — run {run-id}

> Produced by `agents/actions/validate.md`. Script-driven validator output. Lives under `{NEBULA_PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{run-id}/` (§14). Not inside any feature evidence package.

## Run Identity

- Run ID: {run-id}
- Date: YYYY-MM-DD
- Reviewer: <Implementation Validator / Orchestrator>

## Validator Invocations

One row per validator call, with command, exit code, and the JSON output path.

| Validator | Command | Exit Code | Output |
|-----------|---------|-----------|--------|
| validate-feature-evidence | `python3 agents/product-manager/scripts/validate-feature-evidence.py --stage closeout --feature F#### --json` | 0 | `feature-evidence.json` |
| validate-trackers | `python3 agents/product-manager/scripts/validate-trackers.py` | 0 | `trackers.txt` |
| validate-templates | `python3 agents/scripts/validate_templates.py` | 0 | `templates.txt` |

## Findings By Rule ID

Each row cites the rule ID emitted by the producing validator (per §22), with severity, count, and the canonical file path:

| Rule ID | Severity | Count | File |
|---------|----------|------:|------|
| `commands_log_absolute_cwd_warns` | warning | 1 | `.../F0001-new/{run-id}/commands.log` |

Rule IDs must match the IDs emitted by `validate-feature-evidence.py` or `validate-trackers.py`. Template-alignment rule IDs (`tpl_*`) are owned by `validate_templates.py`.

## Recommendations (when `WITH RECOMMENDATIONS`)

§15 PM Acceptance Line Format applies. For validate-action runs, blocking severities require an in-report follow-up commitment per §14.

## Result

One of: `PASS`, `PASS WITH RECOMMENDATIONS`, `FAIL`.

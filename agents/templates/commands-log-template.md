# Commands Log Schema Guidance

> The actual file is `commands.log` — JSON Lines, no Markdown. This template documents the per-line schema per §13.

## Schema

Each non-empty line is one JSON object:

```json
{"schema_version":1,"timestamp":"2026-05-19T14:20:00-04:00","cwd":"{NEBULA_PRODUCT_ROOT}","command":"pnpm test","exit_code":0,"artifacts":["planning-mds/operations/evidence/runs/{run-id}/artifacts/test-results/pnpm-test.log"],"redactions":[]}
```

Field rules:

| Field | Type | Rule |
|-------|------|------|
| `schema_version` | integer | currently `1` |
| `timestamp` | ISO 8601 with timezone or `Z` | parseable |
| `cwd` | string | stable label: `{NEBULA_PRODUCT_ROOT}`, `{NEBULA_PRODUCT_ROOT}/relative/path`, `nebula-agents`, or `nebula-agents/relative/path` |
| `command` | string | non-empty, sanitized |
| `exit_code` | integer | required |
| `artifacts` | array of strings | durable repo-relative product paths that resolve where committed; external URLs OK |
| `redactions` | array of strings | classes or field names that were redacted by the logger |

## Append Helper

Use the framework helper instead of hand-writing command entries:

```bash
python3 agents/scripts/append-command-log.py \
  --log {NEBULA_PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}/commands.log \
  --product-root {NEBULA_PRODUCT_ROOT} \
  --framework-root {FRAMEWORK_ROOT} \
  --cwd "$PWD" \
  --command "python3 ..." \
  --exit-code 0 \
  --artifact {NEBULA_PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}/artifacts/test-results/output.log
```

The helper normalizes product-root artifacts to repo-relative paths, normalizes product/framework working directories to stable labels, creates the log parent directory when needed, and rejects artifacts outside the product repo. Artifact paths must be durable and committed under the product repo, usually under the run's `artifacts/` folder. Scratch paths such as `/tmp/...`, `/var/tmp/...`, or temporary command output locations are not durable evidence artifacts.

## Secret Patterns

Never write unredacted bearer tokens, cookies, private keys, raw connection strings, access keys, env dumps, or `.env` contents. The validator scans the `command` and `artifacts` strings (the "scanning surface" per §13). See `agents/product-manager/scripts/secret_patterns.json` for the framework's must-detect set.

When a command would emit a secret, redact it at source and add the redacted class to `redactions`.

## Empty Log Rule

Closeout validation (`status: approved`) fires `commands_log_empty_at_approved_fails` when the file has zero non-empty lines. Validator scripts log at least one entry by the time the run reaches approved.

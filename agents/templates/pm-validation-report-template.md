# PM Validation Report — run {run-id}

> Produced by `agents/actions/validate.md`. Lives under the non-feature/manual run folder at `{NEBULA_PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{run-id}/`, **not** inside a feature evidence package (§14).

## Run Identity

- Run ID: {run-id}
- Date: YYYY-MM-DD
- Reviewer: <Product Manager>
- Trigger: <what initiated the validate-action run>

## Validation Scope

Enumerate what the PM reviewed: feature(s) targeted, registry rows, signoff state, tracker outputs, evidence packages cross-referenced.

## PM Findings

Each finding includes severity, scope, and disposition. Use the §15 canonical bullet:

```text
- [severity] <finding text> — owner: <name-or-role>; follow-up: <ticket-id-or-deferred-no-followup>
```

## Recommendations (when `WITH RECOMMENDATIONS`)

Non-blocking items deferred via §15 PM Acceptance Line Format. For validate-action runs, blocking severities (`high`/`critical`) must include a follow-up commitment in this report (owner + target date) and the Result may not be `PASS`/`PASS WITH RECOMMENDATIONS` unless the recommendation explicitly states it is non-blocking for downstream consumers.

## Result

One of: `PASS`, `PASS WITH RECOMMENDATIONS`, `FAIL`.

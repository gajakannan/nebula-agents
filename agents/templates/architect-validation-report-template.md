# Architect Validation Report — run {run-id}

> Produced by `agents/actions/validate.md`. Lives under `{NEBULA_PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{run-id}/` (§14). Not inside any feature evidence package.

## Run Identity

- Run ID: {run-id}
- Date: YYYY-MM-DD
- Reviewer: <Architect>
- Trigger: <what initiated the validate-action run>

## Validation Scope

Enumerate the architectural surfaces reviewed: boundary policy, solution patterns, assembly plans, KG semantic deltas, deployment topology.

## Architect Findings

Each finding uses the §15 canonical bullet with severity and owner/follow-up:

```text
- [severity] <finding text> — owner: <name-or-role>; follow-up: <ticket-id-or-deferred-no-followup>
```

## Recommendations (when `WITH RECOMMENDATIONS`)

§15 PM Acceptance Line Format applies. For validate-action runs, blocking severities require an in-report follow-up commitment per §14.

## Result

One of: `PASS`, `PASS WITH RECOMMENDATIONS`, `FAIL`.

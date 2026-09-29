# Agentignore Retrieval Policy

`.agentignore` is a product-owned retrieval guard for agent sessions. It uses
gitignore-style patterns to mark files and directories that agents must not
broad-read, broad-search, or eagerly load into context.

It is not a Git ignore file. It does not change source ownership, validation
requirements, or audit retention. It only controls agent retrieval behavior.

## Session Rule

After resolving `{NEBULA_PRODUCT_ROOT}`, agents must check for
`{NEBULA_PRODUCT_ROOT}/.agentignore` before broad product discovery. When it exists:

- Honor its patterns for broad `Read`, `Glob`, `Grep`, `rg`, and file-list
  operations.
- Prefer running product searches from `{NEBULA_PRODUCT_ROOT}` with
  `rg --ignore-file .agentignore ...`.
- If a tool cannot consume `.agentignore`, scope the search to known hot paths
  instead of scanning the product root.
- Do not bypass ignored paths just because a search returned no results.

## Cold Archive Rule

`{NEBULA_PRODUCT_ROOT}/planning-mds/operations/**` is cold archive unless the current
task explicitly needs operations evidence, run history, validation proof,
failure triage, closeout audit, or operator-requested inspection.

For evidence retrieval, start from indexes:

1. `{NEBULA_PRODUCT_ROOT}/planning-mds/operations/evidence/README.md`
2. `{NEBULA_PRODUCT_ROOT}/planning-mds/operations/evidence/features/F####-*/latest-run.json`
3. `{NEBULA_PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{run-id}/evidence-manifest.json`

Then read only the specific evidence files named by the manifest, report, or
operator request. Do not load `{RUN_FOLDER}/**`, `artifacts/**`, legacy evidence
folders, screenshots, or logs unless the task requires that exact artifact.

## Bypass Rule

Bypass `.agentignore` only with an explicit reason:

- the user asked for an ignored path or artifact
- evidence validation or closeout audit requires it
- failure, CI, security, or quality triage needs a cited raw artifact
- a manifest or index points to an exact file needed for the current gate

When bypassing during a formal action run, record the reason and path in
`artifact-trace.md`.

## Product File Template

Product repos should place this file at `{NEBULA_PRODUCT_ROOT}/.agentignore`:

```gitignore
# Agent retrieval guard. Gitignore-style patterns for AI agents.
# This is not .gitignore; it does not change source control behavior.

# Treat operations evidence as cold archive by default.
/planning-mds/operations/**

# Re-allow only small index entry points.
!/planning-mds/operations/
!/planning-mds/operations/evidence/
!/planning-mds/operations/evidence/README.md
!/planning-mds/operations/evidence/features/
!/planning-mds/operations/evidence/features/**/
!/planning-mds/operations/evidence/features/**/latest-run.json
!/planning-mds/operations/evidence/frontend-quality/
!/planning-mds/operations/evidence/frontend-quality/README.md
!/planning-mds/operations/evidence/frontend-quality/latest-run.json
!/planning-mds/operations/evidence/frontend-ux/
!/planning-mds/operations/evidence/frontend-ux/README.md
```

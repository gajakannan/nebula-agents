# Artifact Trace — F####-{slug} run {run-id}

> Required per §8. Captures what was read, written, generated, referenced externally, and explicitly omitted/waived.

## Artifacts Read

Bulleted list of files the action consulted (planning docs, prior evidence, role inputs).

- `planning-mds/features/F####-{slug}/PRD.md`
- `planning-mds/operations/evidence/runs/{prior-run-id}/evidence-manifest.json` (if rerun)

## Artifacts Created Or Updated

- `evidence-manifest.json` — created/updated
- `g0-assembly-plan-validation.md` — created
- (etc.)

## Generated Evidence

Tool-produced outputs: coverage XML, test result XML, screenshots, scan exports. Cite the path within `artifacts/` or the external location.

## External Or Global Evidence References

References to global lanes (§20) or to other features' evidence that this run depends on. Each reference must resolve when validated.

- `planning-mds/operations/evidence/frontend-quality/latest-run.json`
- `planning-mds/operations/evidence/frontend-ux/ux-audit-YYYY-MM-DD.md`

## Omissions And Waivers

Mirror the manifest `omissions[]` and `waivers` entries for human review. Per §18 only non-required artifacts may be omitted.

## Run Environment (conditional)

Required only when `commands.log` carries an absolute `cwd`. One bullet per justified absolute path:

```text
- Absolute cwd: /workspace/some/path — sandboxed CI runner; NEBULA_PRODUCT_ROOT not stable
```

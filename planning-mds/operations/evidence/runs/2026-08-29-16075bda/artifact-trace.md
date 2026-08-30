# Artifact Trace — F0003-local-agent-runtime-control-plane run 2026-08-29-16075bda

## Artifacts Read

Planning package (the approved Phase B design):

- `planning-mds/features/F0003-local-agent-runtime-control-plane/PRD.md`
- `planning-mds/features/F0003-local-agent-runtime-control-plane/F0003-S0001..S0007*.md` — all 7 stories
- `planning-mds/features/F0003-local-agent-runtime-control-plane/STATUS.md`
- `planning-mds/BLUEPRINT.md` §5.1-§5.9
- `planning-mds/architecture/f0003-runtime-contract.md` (contract `1.1`)
- `planning-mds/architecture/decisions/ADR-005..ADR-009*.md` — all `Accepted`
- `planning-mds/security/f0001-authorization-model.md` § *F0003 Action Extensions*
- `planning-mds/schemas/f0003-{capability-report,artifact-index,artifact-summary,learning-proposal,metric-snapshot,mcp-response}.schema.json`

Prior evidence (read, not inherited):

- `planning-mds/operations/evidence/runs/2026-08-22-5ed12b9c/plan-review-report.md` — the READY verdict this run's entry rests on
- `planning-mds/operations/evidence/runs/2026-07-13-1cfbc5a0/g0-assembly-plan-validation.md` — F0001's G0 precedent for a Python CLI feature
- `planning-mds/features/archive/F0001-tmux-native-agent-cockpit/feature-assembly-plan.md` — template adaptation precedent

As-built source (read to make the plan's "Existing Code" rows concrete):

- `engine/src/nebula_agents/{domain,application,infrastructure,presentation}/*.py`
- `engine/src/nebula_agents/bootstrap.py`
- `agents/templates/feature-assembly-plan-template.md`
- `scripts/kg/lookup.py F0003` output — bindings, not hand-enumerated

## Artifacts Created Or Updated

- `planning-mds/features/F0003-local-agent-runtime-control-plane/feature-assembly-plan.md` — created (795 lines)
- `g0-assembly-plan-validation.md` — created
- `evidence-manifest.json` — updated: scope flags, required roles, `changed_paths`, `scm.head_ref`, status
- `gate-decisions.md` — G0 row and the scope declarations
- `artifacts/diffs/changed-files.txt` — generated
- `commands.log`, `lifecycle-gates.log` — appended by `run-gate.py`
- `g1-runtime-preflight.md` — created at G1
- `evidence-manifest.json` — updated at G1: `gate_results.runtime_preflight` PASS
- `gate-decisions.md` — G1 row appended; Step 3, 4, and 8 findings recorded
- `artifacts/facade-split/` — Checkpoint A audit-stream evidence and its harness
- `artifacts/test-results/{junit.xml,coverage.xml}` — created at Step 8
- `artifacts/test-coverage/acceptance-criteria-map.md` — created at Step 8
- `evidence-manifest.json` — `test_results` block recorded at Step 8
- `engine/**` — F0003 implementation, all 8 steps
- `docs/mcp-host-configuration.md` — created at Step 7; M1's resolution. Corrected at G2
- `g2-self-review.md`, `test-plan.md`, `test-execution-report.md`, `coverage-report.md`,
  `deployability-check.md` — created at G2
- `artifacts/security/{dependency-audit,secrets-scan,bandit-sast}.json` — created at G2

## Generated Evidence

- `artifacts/diffs/changed-files.txt` — changed-file list for this run

G2 executed three security scan classes (`pip-audit`, `detect-secrets`, `bandit`) whose
raw output is retained under `artifacts/security/`. The secrets scan carries its triage
inline. DAST did not run and is waived — no listening port exists.

G1 executed environment probes, a tmux lifecycle smoke on a unique session name, and the
engine suite on all three CI-matrix interpreters. Their results are recorded in
`g1-runtime-preflight.md`; no raw output artifact is retained, because the preflight created
no workspace state and its temporary runtime root and tmux session were both removed.

No coverage, test-result, scan, or screenshot artifacts exist yet; they are produced from
G2 onward.

## External Or Global Evidence References

None. F0003 has no frontend lane (CLI-only) and depends on no other feature's evidence.

## Omissions And Waivers

None. The manifest carries an empty `omissions[]` and `waivers` block.

The DAST scan class is expected to be waived at G2 — F0003 opens no port and runs no server
(BLUEPRINT §5.8) — following the precedent of F0001's Architect-owned waiver. It is not
waived yet, because no scan block exists at G0.

## Run Environment (conditional)

Not applicable. `commands.log` records `cwd` as the relative `nebula-agents`.

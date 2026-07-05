# Manual Orchestration Runbook (Public Preview)

## Purpose

This runbook defines how to execute the framework in the initial public preview, where orchestration is human-driven.

Use this document with:
- `agents/actions/*.md`
- `agents/<role>/SKILL.md`
- `agents/docs/AGENT-USE.md` (Session Setup section is mandatory pre-reading)
- `agents/docs/ORCHESTRATION-CONTRACT.md`
- `CONSUMER-CONTRACT.md`

## Scope

- Current mode: human operator runs actions, roles, and gates.
- Session working directory: `nebula-agents`. Implementation target: `{PRODUCT_ROOT}` (sibling product repo), resolved per `agents/docs/AGENT-USE.md` → Session Setup.
- No built-in automated orchestrator is required for this release.
- Evidence capture is mandatory for reproducibility and auditability.

## Pre-Run Checklist

Before creating a `RUN_ID`, confirm:

- [ ] Session is rooted in `nebula-agents`.
- [ ] `{PRODUCT_ROOT}` is resolved (environment, operator input, or default `../<product-repo>`) and echoed back as an absolute path.
- [ ] `{PRODUCT_ROOT}` exists and is writable.
- [ ] `{PRODUCT_ROOT}/lifecycle-stage.yaml` exists (or the action being run is `init`, which will scaffold it).

## Run ID And Evidence Location

For every action execution, create a run ID and evidence folder:

```bash
RUN_ID=<action>-$(date -u +%Y%m%d-%H%M%S)
mkdir -p {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/$RUN_ID
```

Store all run evidence under:
- `{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/<RUN_ID>/`

## Required Evidence Files

The authoritative artifact list, required headings, and schemas are defined
in `agents/docs/AGENT-OPS.md` (single source of truth). The list below is
the operator checklist; AGENT-OPS.md wins on any heading/schema detail.

Every run must include these files:

1. `action-context.md`
- action name, operator, UTC start time
- inputs used (files, prompts, assumptions)
- lifecycle stage from `lifecycle-stage.yaml`

2. `artifact-trace.md`
- artifacts read
- artifacts created/updated
- file paths only; no ambiguous references
- include report / coverage / log artifact paths when the action generates them

3. `gate-decisions.md`
- each approval/review gate encountered
- decision (`approve`, `request changes`, `reject`, etc.)
- timestamp and rationale

4. `commands.log`
- exact commands executed for validation and checks
- include command exit codes
- when testing or review actions run, capture layer-by-layer commands (unit/integration/e2e/a11y/coverage as applicable)

5. `lifecycle-gates.log`
- output of `python3 agents/scripts/run-lifecycle-gates.py`
- if stage override is used, include the exact command

If the action includes testing or review, the evidence package should also make these explicit in either `artifact-trace.md` or linked reports:
- which validation layers were executed
- artifact paths produced by those layers
- any skipped layers and the justification

## Execution Procedure

1. Start the run
- choose action and generate `RUN_ID`
- create evidence folder and initial `action-context.md`

2. Load contracts
- read `agents/actions/<action>.md`
- read each required role `SKILL.md`
- confirm prerequisites before writing artifacts

3. Execute action steps
- follow step order exactly (including parallel sections where applicable)
- record all artifact updates in `artifact-trace.md`

4. Handle gates
- stop at every required gate
- capture explicit user decision in `gate-decisions.md`
- do not bypass required gates

5. Run lifecycle gates
- execute `python3 agents/scripts/run-lifecycle-gates.py`
- append output and exit status to `lifecycle-gates.log`

6. Close the run
- add UTC end time and summary in `action-context.md`
- confirm required evidence files exist and are non-empty

## Minimum Completion Criteria

A manual run is complete only if:
- all action-required artifacts exist
- required gate decisions are captured with rationale
- lifecycle gate execution output is recorded
- artifact trace is complete and path-accurate

## Integration Runs (integrate action)

Maintainer procedure for merging a contributor branch (`agents/actions/integrate.md`
is authoritative; this is the operator checklist). Serial: one run at a time.

1. **Gate 1 — feature review.** Confirm a passing `feature-review` verdict for
   the source branch's feature, or decide and write a waiver with rationale.
   No verdict and no waiver → do not start the run.
2. **Run the integrator** via
   `agents/templates/prompts/evidence-contract/integrate-operator-friendly.md`
   with `SOURCE`, `INTEGRATION_BRANCH` (never `main`), and the verdict/waiver.
3. **Review the evidence run** (`integration-report.json`, merge reports,
   validator output). Bounces go back to the contributor; typed conflicts go
   to the named owning role (architect or PM); re-runs after fixes are new runs.
4. **Gate 2 — human test validation.** Exercise the delivered feature on the
   prepared merge worktree (start the app; verify the feature's headline
   behavior). Record pass/fail in `gate-decisions.md` and
   `integration-report.json`.
5. **Push** the prepared merge to the integration branch only on a recorded
   pass; then set `pushed: true` in the report. Confirm the integration branch
   is green before the next run.
6. **Promotion:** after the whole train completes, merge the integration
   branch to `main` once — that promotion merge is the only thing that ever
   touches `main`.

## Release Usage

Before publishing a preview release, verify manual-run completeness with:
- `agents/docs/PREVIEW-RELEASE-CHECKLIST.md`

## Feature Evidence Contract Notes

Which profile a run uses (base run vs. feature package), the full artifact
set, and the validation stages are defined in `agents/docs/AGENT-OPS.md`.
The operator-relevant points:

- Manual / operator-initiated runs (`agents/actions/validate.md`, ad-hoc
  preflight, release rehearsals) use the **base run** profile at
  `{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}/` — the six base
  files, no `evidence-manifest.json`. The three validate-action reports
  (`pm-validation-report.md`, `architect-validation-report.md`,
  `implementation-validation-report.md`) live here, not in a feature package.
- Feature completion closeouts (`agents/actions/feature.md`, and
  `agents/actions/build.md` when it archives a delivered feature) produce the
  full **feature package** at
  `{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}/`; the
  feature index pointer is
  `{PRODUCT_ROOT}/planning-mds/operations/evidence/features/F####-{slug}/latest-run.json`.
- At closeout, the supersession order is mandatory: run
  `patch-prior-manifest.py` **first**, then write `latest-run.json` — never
  the reverse (see AGENT-OPS.md → The Gate Timeline).

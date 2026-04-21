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
mkdir -p {PRODUCT_ROOT}/planning-mds/operations/evidence/$RUN_ID
```

Store all run evidence under:
- `{PRODUCT_ROOT}/planning-mds/operations/evidence/<RUN_ID>/`

## Required Evidence Files

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

## Release Usage

Before publishing a preview release, verify manual-run completeness with:
- `agents/docs/PREVIEW-RELEASE-CHECKLIST.md`

<!-- GENERATED from agents/actions/spec/defect-bugfix.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action defect-bugfix -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


This prompt encodes the **Feature Evidence Contract** (scope `base-run-only`, policy `2026-07-11`).

Required inputs:
- `DEFECT_SUMMARY` (format `short description of the bug or failure being chased`)
- `OBSERVED_BEHAVIOR` (format `what is currently happening`)
- `EXPECTED_BEHAVIOR` (format `what should happen instead`)

Optional inputs (defaults apply when omitted):
- `REPRO_STEPS`
- `AFFECTED_PATHS`
- `AGENT_ROLES` — default `architect,frontend-developer`
- `FEATURE_REFS`
- `ALLOW_FEATURE_PROPOSAL` — default `false`
- `PRODUCT_ROOT` — default `sister-repo`

Auto-resolved (do not set; SESSION_SETUP / the orchestrator compute these):
- `DEFECT_RUN_FOLDER` — {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{DEFECT_RUN_ID}
- `FEATURE_REF_PATHS` — feature paths resolved from REGISTRY.md only when FEATURE_REFS is set

Generate `DEFECT_RUN_ID` once at session start in the contract format `YYYY-MM-DD-[a-z0-9]{8}` using `python3 -c import secrets; print(secrets.token_hex(4))`. Do not use: uuid4.

Session setup: create the run under `planning-mds/operations/evidence/`, initialize `evidence-manifest.json` (status `draft`) with the active contract version stamped, create the base run files (README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log) and artifact subdirs (coverage, diffs, test-results, security, screenshots). Run `agents/scripts/init-run.py` to perform this.

Load context in this order, then navigate rather than eager-load:
1. `agents/ROUTER.md`
2. `agents/agent-map.yaml`
3. `agents/docs/AGENT-USE.md`
4. `role SKILLs for each entry in AGENT_ROLES`
5. `for FEATURE_REFS (read-only): each feature's README.md, PRD.md, feature-assembly-plan.md, STATUS.md; if archived, also its approved pm-closeout.md`

Gates (run each stage through `agents/scripts/run-gate.py`, in order):
- **D0 — Defect scope lock** (role: architect; artifacts: action-context.md, gate-decisions.md)
    - judgment: Confirm the bug statement (DEFECT_SUMMARY/OBSERVED_BEHAVIOR/EXPECTED_BEHAVIOR), reproduction info,
affected paths if known, active AGENT_ROLES, and whether feature proposal is allowed; record the row in
gate-decisions.md and the full scope (plus "Lifecycle Authority = none") in action-context.md before any
implementation.
- **D1 — Reproduction and triage** (role: architect; artifacts: none)
    - judgment: Reproduce the bug or explain why it cannot be reproduced; capture relevant logs/screenshots/test failures
under artifacts/; record initial findings in artifact-trace.md.
- **D2 — Root cause and fix plan** (role: architect; artifacts: architect-analysis.md)
    - judgment: Architect identifies the root cause and the SMALLEST correct fix (root-cause analysis, ownership boundary,
design constraints, fix strategy, risk). PM (when activated) confirms acceptance checks and non-goals. If
the issue needs durable product tracking, write feature-recommendation.md and STOP for approval when
ALLOW_FEATURE_PROPOSAL=true; otherwise record a follow-up.
- **D3 — Implementation** (role: frontend-developer; artifacts: none)
    - judgment: Implement the smallest correct code/docs/planning fix WITHIN the defect scope (the actual implementing role
follows AGENT_ROLES — frontend-developer and/or backend-developer); update or add focused regression tests
where practical. Each implementing role writes its fix report (frontend-fix-report.md / backend-fix-report.md).
- **D4 — Validation** (role: quality-engineer; artifacts: none)
    - judgment: Run the NARROWEST meaningful tests first, then broaden only when blast radius requires it; record commands,
exit codes, and artifacts. QE (when activated) owns quality-report.md with reproduction confirmation,
regression tests, and the validation matrix.
- **D5 — Review and closeout** (role: architect; artifacts: none)
    - judgment: Each activated role writes its report; README.md summarizes root cause / fix / validation / open
follow-ups; gate-decisions.md records the final defect-run verdict. Close when the bug is fixed and
validated, explicitly not reproducible with evidence, or intentionally escalated.

Severity gate profile: `none` (compute allowed outcomes with `agents/scripts/gate_policy.py`; coverage floor is 80%).

Ownership (strict):
- **architect** owns: architect-analysis.md
- **backend-developer** owns: backend-fix-report.md
- **frontend-developer** owns: frontend-fix-report.md
- **product-manager** owns: bugfix-brief.md, feature-recommendation.md
- **quality-engineer** owns: quality-report.md
- **security** owns: security-review-report.md

Forbidden:
- Generate DEFECT_RUN_ID with uuid4, or a second run ID for another activated agent.
- Create or modify planning-mds/features/* unless the operator promotes this run to formal feature work after a PM recommendation.
- Write into a feature folder (####-*/).
- Write evidence-manifest.json, latest-run.json, role signoff ledgers, or feature closeout artifacts.
- Treat this defect run as completed-feature evidence.
- Hide failed commands — record them and use them as evidence.

Stop conditions:
- The bug requires a new product capability rather than a defect fix and the operator has not approved feature promotion.
- Reproduction requires credentials/data/environment access that is unavailable.
- A required validator or test fails for reasons unrelated to the fix after one repair cycle.
- The fix would cross a security/privacy boundary without Security Reviewer involvement.
- INSUFFICIENT_CONTEXT occurs.

Conflict resolution:
- Architect recommends redesign but Frontend Developer can fix locally -> use the smallest correct local fix unless the redesign is needed to prevent recurrence; record the tradeoff in architect-analysis.md.
- PM says feature tracking is required but ALLOW_FEATURE_PROPOSAL=false -> stop and ask the operator whether to promote; do not create the feature.
- reproduction evidence disagrees with the user report -> preserve both, state what was verified, and keep the run open only with a concrete next diagnostic step.
- tests pass but manual reproduction still fails -> manual reproduction wins; continue debugging or record the environment-specific blocker.
- feature references disagree with current code behavior -> current code and reproducible behavior are authoritative for the fix; feature docs become follow-up context unless the operator promotes the work.

Note (evidence_outputs): Evidence lands only in {DEFECT_RUN_FOLDER} plus the actual code/docs/planning files changed by the fix.
README.md includes Run Summary, Status, Evidence Index, Validation Summary, Open Follow-ups. artifact-trace.md
lists artifacts read, artifacts created/updated, generated evidence, external/global references, and
omissions/waivers.

Note (promotion): If the operator approves promotion to formal feature work, STOP the defect run cleanly first: record the
promotion decision in gate-decisions.md, write {DEFECT_RUN_FOLDER}/feature-recommendation.md, and do not
continue editing as a defect run. The next session uses the formal plan/feature/build evidence contract with
its own feature-scoped run ID and evidence package.

Note (session_setup): Echo the resolved absolute {PRODUCT_ROOT} and the generated {DEFECT_RUN_ID} on the first turn before any
command. Mint DEFECT_RUN_ID once in contract format (an ISO YYYY-MM-DD date plus a secrets.token_hex(4)
suffix); never uuid4, never regenerate, and pass the same id + {DEFECT_RUN_FOLDER} to every activated agent.
Create {DEFECT_RUN_FOLDER} with the six §8 base run files and an artifacts/ folder (logs, screenshots, diffs,
traces, test output).

Note (telemetry): Append every shell command to {DEFECT_RUN_FOLDER}/commands.log per the §13 JSONL schema (schema_version,
timestamp with timezone, cwd, command, exit_code, artifacts[], redactions[]). Append validation milestones to
{DEFECT_RUN_FOLDER}/lifecycle-gates.log — a run audit log, NOT feature-stage validation.

<!-- GENERATED from agents/actions/spec/plan-review.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action plan-review -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


CONTRACT: Feature Evidence Contract | SCOPE: read-only-audit | POLICY: 2026-07-11

REQUIRED_INPUTS:
- PLAN_SCOPE
- TARGET [F#### | comma-separated F#### list | project]
OPTIONAL_INPUTS:
- DIFF_RANGE
- PRODUCT_ROOT =default:sister-repo
AUTO_RESOLVED:
- FEATURE_PATH = {PRODUCT_ROOT}/planning-mds/features/{TARGET}-{FEATURE_SLUG} when PLAN_SCOPE=feature
- FEATURE_SLUG = kebab-case slug for TARGET from REGISTRY.md when PLAN_SCOPE=feature
- PLAN_REVIEW_RUN_FOLDER = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{PLAN_REVIEW_RUN_ID}

RUN_ID: var=PLAN_REVIEW_RUN_ID format=YYYY-MM-DD-[a-z0-9]{8} method=python3 -c import secrets; print(secrets.token_hex(4)) forbidden=uuid4
SESSION_SETUP: init-run.py -> planning-mds/operations/evidence/... manifest=draft base_files=[README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log] artifacts=[coverage, diffs, test-results, security, screenshots]
CONTEXT: agents/ROUTER.md -> agents/agent-map.yaml -> agents/docs/AGENT-USE.md -> agents/actions/plan-review.md -> agents/actions/plan.md -> agents/actions/feature.md -> role SKILLs: agents/product-manager/SKILL.md, agents/architect/SKILL.md, agents/code-reviewer/SKILL.md -> feature scope: {FEATURE_PATH}/**; plus BLUEPRINT.md, REGISTRY.md, ROADMAP.md, KG + architecture/API/schema/security artifacts as needed

GATES:
- PR0 role=product-manager artifacts=[action-context.md]
- PR1 role=product-manager artifacts=[plan-review-report.md]
- PR2 role=product-manager artifacts=[]
    - run `python3 agents/product-manager/scripts/validate-stories.py {FEATURE_PATH}` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/validate-trackers.py` (cwd: framework, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - run `python3 agents/scripts/validate_templates.py` (cwd: framework, timeout: 300s)
- PR3 role=product-manager artifacts=[]
- PR4 role=product-manager artifacts=[]

SEVERITY_GATE: profile=review-family tool=gate_policy.py coverage_min_pct=80
OWNERSHIP:
- architect: Architecture Readiness section findings
- code-reviewer: Buildability Challenge section findings
- product-manager: Product Readiness section findings
FORBIDDEN:
- Generate PLAN_REVIEW_RUN_ID with uuid4.
- Edit plan artifacts, KG artifacts, trackers, stories, contracts, schemas, architecture files, or product source files.
- Write into any feature evidence package.
- Approve from prior approval tokens, summaries, or checklists without raw artifact inspection.
- Treat lookup/KG mappings as authoritative over raw artifacts.
- Require feature-assembly-plan.md as a plan deliverable.
- Downgrade missing build-critical detail to low severity.
- Widen review scope outside PLAN_SCOPE and TARGET except to record discovered impact.
STOP_CONDITIONS:
- The target scope cannot be identified.
- Required raw artifacts are missing and cannot be located.
- lookup.py returns only ambiguous or low-confidence matches for the declared target.
- A validator failure prevents evidence-backed readiness.
- Reviewers cannot cite concrete files/sections for PR4.
CONFLICT_RESOLUTION:
- raw artifact vs KG mapping -> raw wins; record a KG drift finding.
- prior approval vs current artifact gap -> the current artifact gap wins.
- PM and Architect disagree -> record both and escalate at PR4.
- missing build-critical owner -> NOT READY.
NOTE[preconditions]: plan.md completed for TARGET; Phase A and Phase B approval decisions are recorded (or missing approvals are
in review scope); tracker sync and ontology sync completed (or their failures are in review scope); TARGET
resolves to concrete feature, feature-set, or project planning artifacts.
NOTE[read_only]: plan-review READS but never writes plan / KG / tracker / feature evidence artifacts. Repair ownership stays
with the original lifecycle owners (plan.md / targeted rework); reviewers never repair during review — a
NOT READY / CONDITIONALLY READY verdict routes the fix back to the owner.
NOTE[report_sections]: plan-review-report.md required sections: Decision; Findings By Severity; Product Readiness; Architecture
Readiness; Buildability Challenge; Validation Evidence; Artifact Trace. README.md summarizes the readiness
state and open follow-ups; gate-decisions.md records PR0 through PR4.
NOTE[session_setup]: Echo the resolved absolute {PRODUCT_ROOT} on the first turn. Generate PLAN_REVIEW_RUN_ID once in contract
format (an ISO YYYY-MM-DD date plus a secrets.token_hex(4) suffix); never uuid4. Create
PLAN_REVIEW_RUN_FOLDER and its artifacts/ and initialize the six §8 base run files (README.md,
action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log).
NOTE[telemetry]: Append every shell command to {PLAN_REVIEW_RUN_FOLDER}/commands.log per the §13 JSONL schema
(schema_version, timestamp with timezone, cwd, command, exit_code, artifacts[], redactions[]).

<!-- GENERATED from agents/actions/spec/feature-review.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action feature-review -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


CONTRACT: Feature Evidence Contract | SCOPE: read-only-audit | POLICY: 2026-07-11

REQUIRED_INPUTS:
OPTIONAL_INPUTS:
- PR_URL
- FEATURE_ID
- MODE
- DIFF_RANGE
- FEATURE_RUN_ID
- RUN_DEVOPS =default:auto
- PRODUCT_ROOT =default:sister-repo
AUTO_RESOLVED:
- FEATURE_INDEX_ROOT = {PRODUCT_ROOT}/planning-mds/operations/evidence/features/{FEATURE_ID}-{FEATURE_SLUG}
- FEATURE_PATH = current or archived feature path for {FEATURE_ID}
- FEATURE_REVIEW_RUN_FOLDER = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{FEATURE_REVIEW_RUN_ID}
- FEATURE_RUN_FOLDER = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{FEATURE_RUN_ID} (closeout: FEATURE_RUN_ID defaults to latest-run.json run_id)
- FEATURE_SLUG = kebab-case slug for {FEATURE_ID} from REGISTRY.md

RUN_ID: var=FEATURE_REVIEW_RUN_ID format=YYYY-MM-DD-[a-z0-9]{8} method=python3 -c import secrets; print(secrets.token_hex(4)) forbidden=uuid4
SESSION_SETUP: init-run.py -> planning-mds/operations/evidence/... manifest=draft base_files=[README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log] artifacts=[coverage, diffs, test-results, security, screenshots]
CONTEXT: agents/ROUTER.md -> agents/agent-map.yaml -> agents/docs/AGENT-USE.md -> agents/actions/feature-review.md -> agents/actions/feature.md -> {FEATURE_PATH}/feature-assembly-plan.md, {FEATURE_PATH}/** -> {FEATURE_INDEX_ROOT}/latest-run.json (when present), {FEATURE_RUN_FOLDER}/evidence-manifest.json + manifest-cited role reports -> role SKILLs: agents/product-manager/SKILL.md, agents/architect/SKILL.md, agents/quality-engineer/SKILL.md, agents/code-reviewer/SKILL.md, agents/security/SKILL.md; agents/devops/SKILL.md when RUN_DEVOPS resolves to yes

GATES:
- FR0 role=product-manager artifacts=[action-context.md]
- FR1 role=product-manager artifacts=[feature-review-report.md]
- FR2 role=product-manager artifacts=[]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/validate-trackers.py` (cwd: framework, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-symbols` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - run `python3 agents/scripts/validate_templates.py` (cwd: framework, timeout: 300s)
- FR3 role=product-manager artifacts=[]
- FR4 role=product-manager artifacts=[]

SEVERITY_GATE: profile=review-family tool=gate_policy.py coverage_min_pct=80
OWNERSHIP:
- architect: Architecture and KG Alignment findings
- code-reviewer: Code Quality and merge-readiness findings
- devops: Deployability findings when RUN_DEVOPS resolves to yes
- product-manager: Requirements Satisfaction, Signoff and Closeout, Tracker Sync findings
- quality-engineer: Test Evidence and Coverage findings
- security: Security findings
FORBIDDEN:
- Generate FEATURE_REVIEW_RUN_ID with uuid4.
- Edit implementation code, tests, feature docs, closeout files, trackers, KG artifacts, or feature evidence packages.
- Write into {FEATURE_RUN_FOLDER}.
- Bulk-load {FEATURE_RUN_FOLDER}/**, raw logs, screenshots, or artifacts/** without a manifest citation, validator failure, or explicit operator request.
- Treat prior feature-action approval as proof the feature is done.
- Approve from report summaries without checking raw evidence paths.
- Substitute global evidence lanes for feature-scoped role evidence.
- Ignore uncommitted or unreviewed changed files.
- Declare TRULY DONE while required evidence validation fails.
- Widen scope beyond FEATURE_ID except to record cross-feature impact.
STOP_CONDITIONS:
- FEATURE_ID, FEATURE_PATH, FEATURE_RUN_ID, or FEATURE_RUN_FOLDER cannot be resolved.
- The feature evidence package is missing outside explicit candidate-audit mode.
- The changed-file set cannot be identified.
- Required evidence validation fails in a way that prevents completion review.
- Reviewers cannot cite concrete evidence for FR4.
CONFLICT_RESOLUTION:
- raw artifact vs evidence summary -> raw artifact wins; record an evidence-drift finding.
- latest-run.json points to a different run than FEATURE_RUN_ID in closeout-audit -> NOT DONE unless older-run review is explicit.
- role report passes but raw evidence contradicts it -> raw evidence wins.
- required evidence missing for a completed-terminal feature -> NOT DONE.
- a high finding accepted without owner, mitigation, and target date -> CONDITIONALLY DONE at best.
NOTE[modes]: closeout-audit audits the approved feature run (FEATURE_RUN_ID defaults to the latest-run.json run_id;
validate --stage closeout). candidate-audit audits an in-progress run (FEATURE_RUN_ID set, FEATURE_RUN_FOLDER
exists; validate --run-id {FEATURE_RUN_ID} --stage G6). Precondition: feature.md reached G6 or G8 for FEATURE_ID.
NOTE[read_only]: feature-review READS but never writes the canonical feature evidence package. Repair ownership stays with the
original lifecycle owners (feature.md / review.md / test.md / targeted rework); reviewers never repair during
review — a NOT DONE / CONDITIONALLY DONE verdict routes the fix back to the owner.
NOTE[report_sections]: feature-review-report.md required sections: Decision; Findings By Severity; Completion Checks; Validation
Evidence; Artifact Trace. README.md summarizes the done state and open follow-ups; gate-decisions.md records
FR0 through FR4.
NOTE[session_setup]: Echo the resolved absolute {PRODUCT_ROOT} on the first turn. Generate FEATURE_REVIEW_RUN_ID once in contract
format (an ISO YYYY-MM-DD date plus a secrets.token_hex(4) suffix); never uuid4. Resolve FEATURE_SLUG/PATH/
INDEX_ROOT/RUN_ID/RUN_FOLDER, then create FEATURE_REVIEW_RUN_FOLDER and its artifacts/ and initialize the six
§8 base run files.
NOTE[target]: PR_URL is the usual target: `gh pr checkout <PR#>`, then
`gh pr view <PR_URL> --json title,headRefName,baseRefName,state` -> FEATURE_ID from the F#### token in the
title/branch, DIFF_RANGE=origin/<baseRefName>..<headRefName>, MODE=candidate-audit if the PR is OPEN else
closeout-audit. Explicit inputs always override values derived from PR_URL.
NOTE[telemetry]: Append every shell command to {FEATURE_REVIEW_RUN_FOLDER}/commands.log per the §13 JSONL schema
(schema_version, timestamp with timezone, cwd, command, exit_code, artifacts[], redactions[]).

<!-- GENERATED from agents/actions/spec/review.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action review -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


CONTRACT: Feature Evidence Contract | SCOPE: base-run-only | POLICY: 2026-07-11

REQUIRED_INPUTS:
- MODE
OPTIONAL_INPUTS:
- PR_URL
- SCOPE
- PATHS
- FEATURE_ID
- RUN_ID
- PRODUCT_ROOT =default:sister-repo
AUTO_RESOLVED:
- FEATURE_PATH = {PRODUCT_ROOT}/planning-mds/features/{FEATURE_ID}-{FEATURE_SLUG} (feature-scoped only)
- FEATURE_SLUG = kebab-case slug for {FEATURE_ID} from REGISTRY.md (feature-scoped only)
- OUTPUT_FOLDER = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID} (feature-scoped only; MUST already exist, created by feature.md at G0)
- REVIEW_RUN_FOLDER = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{REVIEW_RUN_ID} (standalone only)

RUN_ID: var=REVIEW_RUN_ID format=YYYY-MM-DD-[a-z0-9]{8} method=python3 -c import secrets; print(secrets.token_hex(4)) forbidden=uuid4
SESSION_SETUP: init-run.py -> planning-mds/operations/evidence/... manifest=draft base_files=[README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log] artifacts=[coverage, diffs, test-results, security, screenshots]
CONTEXT: agents/ROUTER.md -> agents/agent-map.yaml -> agents/docs/AGENT-USE.md -> agents/actions/review.md -> feature-scoped only: {FEATURE_PATH}/feature-assembly-plan.md, {FEATURE_PATH}/STATUS.md, {OUTPUT_FOLDER}/evidence-manifest.json -> agents/code-reviewer/SKILL.md -> agents/security/SKILL.md (when SCOPE includes security review)

GATES:
- R0 role=code-reviewer artifacts=[gate-decisions.md]
- R1 role=code-reviewer artifacts=[code-review-report.md, security-review-report.md]
- R2 role=code-reviewer artifacts=[]
    - MANUAL checkpoint `review-approval`: User reviews the findings; reviewers record verdicts. Compute the allowed outcome with gate_policy.py profile review-family. (requires: code-review-report.md; produces: review verdicts recorded (evidence-manifest.json role_results in feature-scoped mode))
- R3 role=code-reviewer artifacts=[]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G3` (cwd: framework, timeout: 300s)

SEVERITY_GATE: profile=review-family tool=gate_policy.py coverage_min_pct=80
OWNERSHIP:
- code-reviewer: code-review-report.md
- security: security-review-report.md
FORBIDDEN:
- Generate run IDs with uuid4.
- Write role reports outside {OUTPUT_FOLDER} (feature-scoped) or {REVIEW_RUN_FOLDER} (standalone).
- Create a new run folder in feature-scoped mode — use the existing {OUTPUT_FOLDER} created by feature.md at G0.
- Mix feature-scoped and standalone outputs in one session.
- Skip security review when security_sensitive_scope=true in the feature manifest (security_required_missing_report_fails).
STOP_CONDITIONS:
- A critical code or security finding persists after one review cycle and the parent feature action expects this review to pass.
- Required security review is skipped when security_sensitive_scope=true (security_required_missing_report_fails).
- INSUFFICIENT_CONTEXT occurs — escalate, open raw artifacts, do not proceed on weak matches.
CONFLICT_RESOLUTION:
- code review APPROVED but security review FAIL -> blocking; resolve in the same change set or escalate.
- review reports disagree with manifest role_results -> fix the manifest at G5 signoff; the reports are authoritative.
- review attempted on a feature whose G2 has not yet passed -> halt; out of sequence.
NOTE[evidence_outputs]: code-review-report.md headings (§14): reviewed files, validation artifacts, severity-ranked findings,
recommendations with owner/follow-up, vertical-slice completeness, AC/test adequacy, architecture
compliance, coverage verification, Result. security-review-report.md headings (§14): reviewed surfaces,
threat boundary, auth/authz, validation, audit/logging, secrets/config, OWASP Top 10 coverage, findings,
recommendation disposition, Result. feature-scoped runs also append commands and validator results to the
parent feature run's commands.log and lifecycle-gates.log.
NOTE[modes]: feature-scoped: FEATURE_ID + RUN_ID (the parent feature run) are required; OUTPUT_FOLDER MUST already
exist (feature.md created it at G0) — do NOT create a new run folder; reports and manifest updates land
in the parent feature run. standalone: generate REVIEW_RUN_ID and create REVIEW_RUN_FOLDER; the run
produces NO feature evidence package and does NOT satisfy the per-feature review requirement — the
corresponding feature.md run must still produce its own G3 evidence.
NOTE[pr_target]: PR_URL is the usual target. `gh pr checkout <PR#>`, then
`gh pr view <PR_URL> --json title,headRefName,baseRefName,files` -> SCOPE=path-set, PATHS from
files[].path, DIFF_RANGE=origin/<baseRefName>..<headRefName>, and (feature-scoped) FEATURE_ID from the
F#### token in the title or headRefName. Explicit inputs always override values derived from PR_URL.
NOTE[session_setup]: Echo the resolved absolute {PRODUCT_ROOT} on the first turn before any command. Generate any run ID in
contract format (an ISO YYYY-MM-DD date plus a secrets.token_hex(4) suffix); never uuid4, never
regenerate after start. feature-scoped: no run-folder creation. standalone: mkdir REVIEW_RUN_FOLDER and
initialize the six §8 base run files (README.md, action-context.md, artifact-trace.md, gate-decisions.md,
commands.log, lifecycle-gates.log).
NOTE[telemetry]: Append every shell command to the chosen output folder's commands.log per the §13 JSONL schema
(schema_version, timestamp with timezone, cwd, command, exit_code, artifacts[], redactions[]). Do not
leak secrets — secret-pattern checks fail the run.

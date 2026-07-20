<!-- GENERATED from agents/actions/spec/review.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action review -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


This prompt encodes the **Feature Evidence Contract** (scope `base-run-only`, policy `2026-07-11`).

Required inputs:
- `MODE`

Optional inputs (defaults apply when omitted):
- `PR_URL`
- `SCOPE`
- `PATHS`
- `FEATURE_ID`
- `RUN_ID`
- `PRODUCT_ROOT` — default `sister-repo`

Auto-resolved (do not set; SESSION_SETUP / the orchestrator compute these):
- `FEATURE_PATH` — {PRODUCT_ROOT}/planning-mds/features/{FEATURE_ID}-{FEATURE_SLUG} (feature-scoped only)
- `FEATURE_SLUG` — kebab-case slug for {FEATURE_ID} from REGISTRY.md (feature-scoped only)
- `OUTPUT_FOLDER` — {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID} (feature-scoped only; MUST already exist, created by feature.md at G0)
- `REVIEW_RUN_FOLDER` — {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{REVIEW_RUN_ID} (standalone only)

Generate `REVIEW_RUN_ID` once at session start in the contract format `YYYY-MM-DD-[a-z0-9]{8}` using `python3 -c import secrets; print(secrets.token_hex(4))`. Do not use: uuid4.

Session setup: create the run under `planning-mds/operations/evidence/`, initialize `evidence-manifest.json` (status `draft`) with the active contract version stamped, create the base run files (README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log) and artifact subdirs (coverage, diffs, test-results, security, screenshots). Run `agents/scripts/init-run.py` to perform this.

Load context in this order, then navigate rather than eager-load:
1. `agents/ROUTER.md`
2. `agents/agent-map.yaml`
3. `agents/docs/AGENT-USE.md`
4. `agents/actions/review.md`
5. `feature-scoped only: {FEATURE_PATH}/feature-assembly-plan.md, {FEATURE_PATH}/STATUS.md, {OUTPUT_FOLDER}/evidence-manifest.json`
6. `agents/code-reviewer/SKILL.md`
7. `agents/security/SKILL.md (when SCOPE includes security review)`

Gates (run each stage through `agents/scripts/run-gate.py`, in order):
- **R0 — Review scope lock** (role: code-reviewer; artifacts: gate-decisions.md)
    - judgment: Confirm SCOPE and PATHS and record them in the run's gate-decisions.md (feature-scoped) or
action-context.md (standalone). When a PR_URL is set, derive SCOPE/PATHS/DIFF_RANGE/FEATURE_ID from
it first (see notes.pr_target); explicit inputs override derived values. Decide MODE up front and do
not mix feature-scoped and standalone outputs in one session.
- **R1 — Parallel reviews (code + security)** (role: code-reviewer; artifacts: code-review-report.md, security-review-report.md)
    - judgment: Code Reviewer and Security Reviewer run in parallel. security-review-report.md is required when
SCOPE includes security or the feature manifest carries security_sensitive_scope=true. Write reports
into {OUTPUT_FOLDER} (feature-scoped) or {REVIEW_RUN_FOLDER} (standalone) using the §14 headings (see
notes.evidence_outputs); in feature-scoped mode also update {OUTPUT_FOLDER}/evidence-manifest.json
role_results for Code Reviewer (and Security Reviewer when applicable). Compile/test/lint commands run
inside runtime containers with artifact paths recorded in commands.log.
- **R2 — Approval gate** (role: code-reviewer; artifacts: none)
    - MANUAL checkpoint `review-approval`: User reviews the findings; reviewers record verdicts. Compute the allowed outcome with gate_policy.py profile review-family. (requires: code-review-report.md; produces: review verdicts recorded (evidence-manifest.json role_results in feature-scoped mode))
    - judgment: Passing code-review verdicts are APPROVED, APPROVED WITH RECOMMENDATIONS, PASS, or PASS WITH
RECOMMENDATIONS (APPROVED family for change-set review, PASS family for codebase audits per
code-reviewer/SKILL.md); blocking verdicts are REQUEST CHANGES or REJECTED. security-review-report.md
Result is PASS, PASS WITH RECOMMENDATIONS, or FAIL.
- **R3 — Stage validation (feature-scoped only)** (role: code-reviewer; artifacts: none)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G3` (cwd: framework, timeout: 300s)
    - judgment: Run the op above ONLY in feature-scoped mode (it validates the parent feature run's G3 evidence).
In standalone mode there is no feature scope: confirm the six §8 base run files are complete and apply
no feature-stage validation.

Severity gate profile: `review-family` (compute allowed outcomes with `agents/scripts/gate_policy.py`; coverage floor is 80%).

Ownership (strict):
- **code-reviewer** owns: code-review-report.md
- **security** owns: security-review-report.md

Forbidden:
- Generate run IDs with uuid4.
- Write role reports outside {OUTPUT_FOLDER} (feature-scoped) or {REVIEW_RUN_FOLDER} (standalone).
- Create a new run folder in feature-scoped mode — use the existing {OUTPUT_FOLDER} created by feature.md at G0.
- Mix feature-scoped and standalone outputs in one session.
- Skip security review when security_sensitive_scope=true in the feature manifest (security_required_missing_report_fails).

Stop conditions:
- A critical code or security finding persists after one review cycle and the parent feature action expects this review to pass.
- Required security review is skipped when security_sensitive_scope=true (security_required_missing_report_fails).
- INSUFFICIENT_CONTEXT occurs — escalate, open raw artifacts, do not proceed on weak matches.

Conflict resolution:
- code review APPROVED but security review FAIL -> blocking; resolve in the same change set or escalate.
- review reports disagree with manifest role_results -> fix the manifest at G5 signoff; the reports are authoritative.
- review attempted on a feature whose G2 has not yet passed -> halt; out of sequence.

Note (evidence_outputs): code-review-report.md headings (§14): reviewed files, validation artifacts, severity-ranked findings,
recommendations with owner/follow-up, vertical-slice completeness, AC/test adequacy, architecture
compliance, coverage verification, Result. security-review-report.md headings (§14): reviewed surfaces,
threat boundary, auth/authz, validation, audit/logging, secrets/config, OWASP Top 10 coverage, findings,
recommendation disposition, Result. feature-scoped runs also append commands and validator results to the
parent feature run's commands.log and lifecycle-gates.log.

Note (modes): feature-scoped: FEATURE_ID + RUN_ID (the parent feature run) are required; OUTPUT_FOLDER MUST already
exist (feature.md created it at G0) — do NOT create a new run folder; reports and manifest updates land
in the parent feature run. standalone: generate REVIEW_RUN_ID and create REVIEW_RUN_FOLDER; the run
produces NO feature evidence package and does NOT satisfy the per-feature review requirement — the
corresponding feature.md run must still produce its own G3 evidence.

Note (pr_target): PR_URL is the usual target. `gh pr checkout <PR#>`, then
`gh pr view <PR_URL> --json title,headRefName,baseRefName,files` -> SCOPE=path-set, PATHS from
files[].path, DIFF_RANGE=origin/<baseRefName>..<headRefName>, and (feature-scoped) FEATURE_ID from the
F#### token in the title or headRefName. Explicit inputs always override values derived from PR_URL.

Note (session_setup): Echo the resolved absolute {PRODUCT_ROOT} on the first turn before any command. Generate any run ID in
contract format (an ISO YYYY-MM-DD date plus a secrets.token_hex(4) suffix); never uuid4, never
regenerate after start. feature-scoped: no run-folder creation. standalone: mkdir REVIEW_RUN_FOLDER and
initialize the six §8 base run files (README.md, action-context.md, artifact-trace.md, gate-decisions.md,
commands.log, lifecycle-gates.log).

Note (telemetry): Append every shell command to the chosen output folder's commands.log per the §13 JSONL schema
(schema_version, timestamp with timezone, cwd, command, exit_code, artifacts[], redactions[]). Do not
leak secrets — secret-pattern checks fail the run.

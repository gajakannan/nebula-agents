ACTION: agents/actions/review.md
CONTRACT: Feature Evidence Contract in CONSUMER-CONTRACT.md (effective 2026-05-19)
CONTRACT SCOPE: Review can run in two modes:
  (a) feature-scoped: writes code-review-report.md and security-review-report.md (when required) INTO an existing feature run folder under the canonical evidence package; the parent feature action drives the gates
  (b) standalone: writes review reports under a base run evidence folder; does NOT produce a feature evidence package

REQUIRED INPUTS (operator must set before SESSION_SETUP):
  MODE:                 {feature-scoped | standalone}
  # Review TARGET — set EITHER (a) PR_URL OR (b) SCOPE (+ PATHS / FEATURE_ID+RUN_ID):
  # (a) reviewing a PR (usual): `gh pr checkout <PR#>` + `gh pr view --json title,headRefName,baseRefName,files`
  #     → SCOPE=path-set, PATHS<-files[].path, DIFF_RANGE=origin/{baseRefName}..{headRefName},
  #       FEATURE_ID<-F#### in title/branch (feature-scoped). Explicit values override derived ones.
  PR_URL:               {GitHub PR URL}
  # (b) no PR: set SCOPE (+ PATHS for path-set; + FEATURE_ID/RUN_ID for feature-scoped) instead.
  SCOPE:                {feature | path-set | codebase}        # required unless PR_URL is set
  PATHS:                [path, path, ...]                      # required when SCOPE=path-set (auto from PR_URL)
  FEATURE_ID:           {F####}                                # required when MODE=feature-scoped (from PR_URL when set)
  RUN_ID:               {YYYY-MM-DD-[a-z0-9]{8}}               # required when MODE=feature-scoped; the parent feature run ID

OPTIONAL INPUTS (defaults apply when omitted):
  PRODUCT_ROOT:         absolute product repo root             # default: sister-repo per agents/docs/AGENT-USE.md

AUTO-RESOLVED (do not set; SESSION_SETUP and the orchestrator compute these):
  FEATURE_SLUG          = kebab-case slug for {FEATURE_ID} from REGISTRY.md (only when MODE=feature-scoped)
  FEATURE_PATH          = {PRODUCT_ROOT}/planning-mds/features/{FEATURE_ID}-{FEATURE_SLUG} (only when MODE=feature-scoped)
  OUTPUT_FOLDER         = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID} (only when MODE=feature-scoped)
  REVIEW_RUN_ID         = YYYY-MM-DD-{secrets.token_hex(4)} generated at SESSION_SETUP (only when MODE=standalone)
  REVIEW_RUN_FOLDER     = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{REVIEW_RUN_ID} (only when MODE=standalone)

SESSION_SETUP:
- Resolve {PRODUCT_ROOT} per agents/docs/AGENT-USE.md → Session Setup
- Echo resolved absolute {PRODUCT_ROOT}
- Determine MODE: feature-scoped or standalone
- Generate {REVIEW_RUN_ID} once at session start using contract format YYYY-MM-DD-[a-z0-9]{8} (suffix from `secrets.token_hex(4)`). DO NOT use uuid4.
- For MODE=feature-scoped:
    REQUIRED PARAM: FEATURE_ID, RUN_ID (the parent feature run ID)
    OUTPUT_FOLDER = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}/
    DO NOT create a new run folder; OUTPUT_FOLDER must already exist (created by feature.md at G0)
- For MODE=standalone:
    REVIEW_RUN_FOLDER = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{REVIEW_RUN_ID}/
    mkdir -p {REVIEW_RUN_FOLDER}
    Initialize base run files (README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log) per §8

PRECONDITIONS:
- For MODE=feature-scoped: feature run folder exists; manifest carries the feature run identity; G0 has been passed
- For MODE=standalone: REVIEW_RUN_FOLDER created with base run files
- Application runtime containers healthy if review covers runtime behavior

CONTEXT LOADING ORDER:
1. agents/ROUTER.md
2. agents/agent-map.yaml
3. agents/docs/AGENT-USE.md
4. agents/actions/review.md
5. For feature-scoped: {FEATURE_PATH}/feature-assembly-plan.md, {FEATURE_PATH}/STATUS.md, {OUTPUT_FOLDER}/evidence-manifest.json
6. agents/code-reviewer/SKILL.md
7. agents/security/SKILL.md (when SCOPE includes security review)

FORBIDDEN:
- Generating run IDs with uuid4
- Writing role reports outside {OUTPUT_FOLDER} or {REVIEW_RUN_FOLDER}
- For feature-scoped MODE: creating a new run folder during review (must use the existing {OUTPUT_FOLDER})
- Mixing feature-scoped and standalone outputs in one session
- Skipping security review when security_sensitive_scope=true in the feature manifest

REQUIRED TOOL INVOCATIONS:
- Append every shell command to commands.log per §13 JSONL schema (in OUTPUT_FOLDER or REVIEW_RUN_FOLDER)
- Compile/test/lint commands run inside runtime containers; record artifact paths in commands.log

OWNERSHIP:
- code-reviewer owns: code-review-report.md. Result values per §11 role_results: passing verdicts are APPROVED, APPROVED WITH RECOMMENDATIONS, PASS, or PASS WITH RECOMMENDATIONS (all four are valid; choose APPROVED-family for change-set review and PASS-family for codebase audits per code-reviewer/SKILL.md); blocking verdicts are REQUEST CHANGES or REJECTED
- security-reviewer owns: security-review-report.md (Result: PASS|PASS WITH RECOMMENDATIONS|FAIL); only when SCOPE includes security or feature security_sensitive_scope=true

EVIDENCE OUTPUTS:
For MODE=feature-scoped, write into {OUTPUT_FOLDER}:
- code-review-report.md (headings per §14: reviewed files, validation artifacts, severity-ranked findings, recommendations with owner/follow-up, vertical-slice completeness, AC/test adequacy, architecture compliance, coverage verification, Result)
- security-review-report.md when required (headings per §14: reviewed surfaces, threat boundary, auth/authz, validation, audit/logging, secrets/config, OWASP Top 10 coverage, findings, recommendation disposition, Result)
- Update {OUTPUT_FOLDER}/evidence-manifest.json role_results: Code Reviewer (and Security Reviewer when applicable) with current verdicts and required_artifacts
- Append commands and validator results to commands.log and lifecycle-gates.log of the feature run folder

For MODE=standalone, write into {REVIEW_RUN_FOLDER}:
- The same role reports, plus the six base run files per §8
- This run does NOT contribute to a feature evidence package and does NOT satisfy the per-feature requirement; the corresponding feature action must still run

GATES:
- R0  REVIEW SCOPE LOCK — confirm SCOPE and PATHS; record in gate-decisions.md (or action-context.md for standalone)
- R1  PARALLEL REVIEWS — code review and (when applicable) security review run in parallel
- R2  APPROVAL GATE — user reviews findings; reviewers record verdicts
- R3  STAGE VALIDATION (feature-scoped only) — `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G3` exit 0

STOP CONDITIONS:
- Critical code or security finding persists after one review cycle and the parent feature action expects this review to pass
- Required security review is skipped when security_sensitive_scope=true (rule security_required_missing_report_fails)
- INSUFFICIENT_CONTEXT

EXIT VALIDATION:
- For MODE=feature-scoped: `validate-feature-evidence.py --feature {FEATURE_ID} --run-id {RUN_ID} --stage G3` exit 0
- For MODE=standalone: confirm base run files complete; no feature-stage validation applies

CONFLICT RESOLUTION:
- code review APPROVED but security review FAIL → blocking; resolve in same change set or escalate
- review reports disagree with manifest role_results → fix manifest at G5 signoff; reports are authoritative
- review attempts on a feature whose G2 has not yet passed → halt; out of sequence

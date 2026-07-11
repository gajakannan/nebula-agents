ACTION: agents/actions/feature-review.md
CONTRACT: Feature Evidence Contract in CONSUMER-CONTRACT.md (effective 2026-05-19)
CONTRACT SCOPE: Feature review is a read-only post-feature completion audit. It answers "Is this feature truly done?" and writes a base run evidence package with feature-review-report.md. It reads, but never writes, the canonical feature evidence package.

REQUIRED INPUTS — set the review target as EITHER (a) PR_URL OR (b) the explicit trio:
  # (a) reviewing a PR (usual): resolve everything from it via `gh pr checkout <PR#>` +
  #     `gh pr view --json title,headRefName,baseRefName,state` → FEATURE_ID<-F#### in title/branch,
  #     DIFF_RANGE=origin/{baseRefName}..{headRefName}, MODE=candidate-audit if OPEN else closeout-audit.
  PR_URL:               {GitHub PR URL}
  # (b) no PR: set all three explicitly instead.
  FEATURE_ID:           {F####}                                # required unless PR_URL is set
  MODE:                 {closeout-audit | candidate-audit}     # required unless PR_URL is set
  DIFF_RANGE:           {base..head | working-tree | ...}       # required unless PR_URL is set
  # Explicit values override anything derived from PR_URL.

OPTIONAL INPUTS (defaults apply when omitted):
  FEATURE_RUN_ID:       {YYYY-MM-DD-[a-z0-9]{8}}              # required for candidate-audit or older-run review
  PRODUCT_ROOT:         absolute product repo root            # default: sister-repo per agents/docs/AGENT-USE.md
  RUN_DEVOPS:           {auto | yes | no}                     # default: auto

AUTO-RESOLVED (do not set; SESSION_SETUP and the orchestrator compute these):
  FEATURE_SLUG            = kebab-case slug for FEATURE_ID from REGISTRY.md
  FEATURE_PATH            = current or archived feature path for FEATURE_ID
  FEATURE_INDEX_ROOT       = {PRODUCT_ROOT}/planning-mds/operations/evidence/features/{FEATURE_ID}-{FEATURE_SLUG}
  FEATURE_RUN_ID          = latest-run.json run_id when MODE=closeout-audit and no override is set
  FEATURE_RUN_FOLDER      = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{FEATURE_RUN_ID}
  FEATURE_REVIEW_RUN_ID   = YYYY-MM-DD-{secrets.token_hex(4)} generated at SESSION_SETUP
  FEATURE_REVIEW_RUN_FOLDER = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{FEATURE_REVIEW_RUN_ID}

SESSION_SETUP:
- Resolve {PRODUCT_ROOT} per agents/docs/AGENT-USE.md -> Session Setup
- Echo resolved absolute {PRODUCT_ROOT}
- Generate FEATURE_REVIEW_RUN_ID once using YYYY-MM-DD-[a-z0-9]{8}; suffix from secrets.token_hex(4); do not use uuid4
- Resolve FEATURE_SLUG, FEATURE_PATH, FEATURE_INDEX_ROOT, FEATURE_RUN_ID, FEATURE_RUN_FOLDER
- Create FEATURE_REVIEW_RUN_FOLDER and artifacts/
- Initialize base run files per section 8: README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log

PRECONDITIONS:
- feature.md reached G6 or G8 for FEATURE_ID
- MODE=closeout-audit: FEATURE_INDEX_ROOT/latest-run.json exists unless FEATURE_RUN_ID intentionally targets an older run
- MODE=candidate-audit: FEATURE_RUN_ID is set and FEATURE_RUN_FOLDER exists
- DIFF_RANGE or explicit changed-file set can identify the changed files

CONTEXT LOADING ORDER:
1. agents/ROUTER.md
2. agents/agent-map.yaml
3. agents/docs/AGENT-USE.md
4. agents/actions/feature-review.md
5. agents/actions/feature.md
6. FEATURE_PATH/feature-assembly-plan.md
7. FEATURE_PATH/**
8. FEATURE_INDEX_ROOT/latest-run.json when present
9. FEATURE_RUN_FOLDER/evidence-manifest.json
10. Role reports and support artifacts named by the manifest and needed for the review question
11. agents/product-manager/SKILL.md
12. agents/architect/SKILL.md
13. agents/quality-engineer/SKILL.md
14. agents/code-reviewer/SKILL.md
15. agents/security/SKILL.md
16. agents/devops/SKILL.md when RUN_DEVOPS resolves to yes

FORBIDDEN:
- Editing implementation code, tests, feature docs, closeout files, trackers, KG artifacts, or feature evidence packages
- Writing into FEATURE_RUN_FOLDER
- Bulk-loading FEATURE_RUN_FOLDER/**, raw logs, screenshots, or artifacts/** without a manifest citation, validator failure, or explicit operator request
- Treating prior feature-action approval as proof that the feature is done
- Approving from report summaries without checking raw evidence paths
- Substituting global evidence lanes for feature-scoped role evidence
- Ignoring uncommitted or unreviewed changed files
- Declaring TRULY DONE while required evidence validation fails
- Widening scope beyond FEATURE_ID except to record cross-feature impact

REQUIRED TOOL INVOCATIONS:
- Resolve changed-file set from DIFF_RANGE, scm.diff_artifact, changed_paths[], or explicit operator list
- Append every shell command to FEATURE_REVIEW_RUN_FOLDER/commands.log per section 13 JSONL schema
- Run applicable validators:
  closeout-audit:
    1. python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout
  candidate-audit:
    1. python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {FEATURE_RUN_ID} --stage G6
  always:
    2. python3 agents/product-manager/scripts/validate-trackers.py
    3. python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/    # when story files changed
    4. python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-symbols
    5. python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift
    6. python3 agents/scripts/validate_templates.py

OWNERSHIP:
- product-manager owns: Requirements Satisfaction, Signoff and Closeout, Tracker Sync findings in feature-review-report.md
- architect owns: Architecture and KG Alignment findings
- quality-engineer owns: Test Evidence and Coverage findings
- code-reviewer owns: Code Quality and merge-readiness findings
- security owns: Security findings
- devops owns: Deployability findings when RUN_DEVOPS resolves to yes
- repair ownership remains with the original lifecycle owners through feature.md, review.md, test.md, or targeted rework; reviewers do not repair during review

GATES:
- FR0 FEATURE RUN AND DIFF LOCK
  - Record FEATURE_ID, MODE, FEATURE_RUN_ID, FEATURE_PATH, FEATURE_RUN_FOLDER, DIFF_RANGE, changed-file set, and RUN_DEVOPS decision in action-context.md
- FR1 PARALLEL COMPLETION REVIEW
  - Product Manager: stories, AC disposition, signoffs, closeout, trackers, archive state, mitigation acceptance
  - Architect: feature-assembly-plan alignment, API/schema, data/workflow, authorization, ADR, KG, code-index, drift
  - Quality Engineer: AC-to-test mapping, runtime evidence, coverage, skipped layers, failure/retry history
  - Code Reviewer: changed code scope, vertical slice completeness, review findings, hidden TODO/debug/dead paths, merge readiness
  - Security: server-side authorization, inputs, external calls, audit/timeline, secrets/config, security-sensitive scope
  - DevOps: runtime/deployment/env/CI/deployability when included
- FR2 VALIDATOR PASS
  - Run applicable commands listed under REQUIRED TOOL INVOCATIONS
  - Record exit code, summary, and artifact path for each command
- FR3 SELF-REVIEW GATE
  - Each reviewer verifies findings cite exact evidence and skipped items are justified
- FR4 DONE GATE
  - evidence validation fail or critical > 0 -> NOT DONE
  - evidence validation pass, critical = 0, high > 0 -> CONDITIONALLY DONE
  - evidence validation pass, critical = 0, high = 0 -> TRULY DONE

EVIDENCE OUTPUTS:
- FEATURE_REVIEW_RUN_FOLDER/README.md
- FEATURE_REVIEW_RUN_FOLDER/action-context.md
- FEATURE_REVIEW_RUN_FOLDER/artifact-trace.md
- FEATURE_REVIEW_RUN_FOLDER/gate-decisions.md
- FEATURE_REVIEW_RUN_FOLDER/commands.log
- FEATURE_REVIEW_RUN_FOLDER/lifecycle-gates.log
- FEATURE_REVIEW_RUN_FOLDER/feature-review-report.md
- FEATURE_REVIEW_RUN_FOLDER/artifacts/* when command output is captured

FEATURE-REVIEW-REPORT REQUIRED SECTIONS:
- Decision
- Findings By Severity
- Completion Checks
- Validation Evidence
- Artifact Trace

STOP CONDITIONS:
- FEATURE_ID, FEATURE_PATH, FEATURE_RUN_ID, or FEATURE_RUN_FOLDER cannot be resolved
- Feature evidence package is missing outside explicit candidate-audit mode
- Changed-file set cannot be identified
- Required evidence validation fails in a way that prevents completion review
- Reviewers cannot cite concrete evidence for FR4

EXIT VALIDATION:
- feature-review-report.md exists and answers "Is this feature truly done?"
- Findings are severity-ranked and cite concrete files/evidence paths
- Validator command results are recorded or justified as skipped
- README.md summarizes done state and open follow-ups
- gate-decisions.md records FR0 through FR4
- Reviewed feature run and changed-file set are identified
- No implementation, feature, tracker, KG, source, or feature evidence artifacts were edited

CONFLICT RESOLUTION:
- Raw artifact vs evidence summary -> raw artifact wins; record evidence drift finding
- latest-run.json points to a different run than FEATURE_RUN_ID in closeout-audit -> NOT DONE unless older-run review is explicit
- Role report passes but raw evidence contradicts it -> raw evidence wins
- Required evidence missing for completed terminal feature -> NOT DONE
- High finding accepted without owner, mitigation, and target date -> CONDITIONALLY DONE at best

<!-- GENERATED from agents/actions/spec/feature-review.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action feature-review -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


This prompt encodes the **Feature Evidence Contract** (scope `read-only-audit`, policy `2026-07-11`).

Required inputs:

Optional inputs (defaults apply when omitted):
- `PR_URL`
- `FEATURE_ID`
- `MODE`
- `DIFF_RANGE`
- `FEATURE_RUN_ID`
- `RUN_DEVOPS` — default `auto`
- `PRODUCT_ROOT` — default `sister-repo`

Auto-resolved (do not set; SESSION_SETUP / the orchestrator compute these):
- `FEATURE_INDEX_ROOT` — {PRODUCT_ROOT}/planning-mds/operations/evidence/features/{FEATURE_ID}-{FEATURE_SLUG}
- `FEATURE_PATH` — current or archived feature path for {FEATURE_ID}
- `FEATURE_REVIEW_RUN_FOLDER` — {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{FEATURE_REVIEW_RUN_ID}
- `FEATURE_RUN_FOLDER` — {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{FEATURE_RUN_ID} (closeout: FEATURE_RUN_ID defaults to latest-run.json run_id)
- `FEATURE_SLUG` — kebab-case slug for {FEATURE_ID} from REGISTRY.md

Generate `FEATURE_REVIEW_RUN_ID` once at session start in the contract format `YYYY-MM-DD-[a-z0-9]{8}` using `python3 -c import secrets; print(secrets.token_hex(4))`. Do not use: uuid4.

Session setup: create the run under `planning-mds/operations/evidence/`, initialize `evidence-manifest.json` (status `draft`) with the active contract version stamped, create the base run files (README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log) and artifact subdirs (coverage, diffs, test-results, security, screenshots). Run `agents/scripts/init-run.py` to perform this.

Load context in this order, then navigate rather than eager-load:
1. `agents/ROUTER.md`
2. `agents/agent-map.yaml`
3. `agents/docs/AGENT-USE.md`
4. `agents/actions/feature-review.md`
5. `agents/actions/feature.md`
6. `{FEATURE_PATH}/feature-assembly-plan.md, {FEATURE_PATH}/**`
7. `{FEATURE_INDEX_ROOT}/latest-run.json (when present), {FEATURE_RUN_FOLDER}/evidence-manifest.json + manifest-cited role reports`
8. `role SKILLs: agents/product-manager/SKILL.md, agents/architect/SKILL.md, agents/quality-engineer/SKILL.md, agents/code-reviewer/SKILL.md, agents/security/SKILL.md; agents/devops/SKILL.md when RUN_DEVOPS resolves to yes`

Gates (run each stage through `agents/scripts/run-gate.py`, in order):
- **FR0 — Feature run and diff lock** (role: product-manager; artifacts: action-context.md)
    - judgment: Record FEATURE_ID, MODE, FEATURE_RUN_ID, FEATURE_PATH, FEATURE_RUN_FOLDER, DIFF_RANGE, the resolved
changed-file set, and the RUN_DEVOPS decision in action-context.md. Resolve the changed-file set from
DIFF_RANGE, scm.diff_artifact, the manifest changed_paths[], or an explicit operator list.
- **FR1 — Parallel completion review** (role: product-manager; artifacts: feature-review-report.md)
    - judgment: Six role lanes in parallel (each owns its report section): PM — stories, AC disposition, signoffs,
closeout, trackers, archive state, mitigation acceptance; Architect — assembly-plan alignment, API/schema,
data/workflow, authorization, ADR, KG, code-index, drift; QE — AC-to-test mapping, runtime evidence,
coverage, skipped layers, failure/retry history; Code Reviewer — changed code scope, vertical-slice
completeness, review findings, hidden TODO/debug/dead paths, merge readiness; Security — server-side
authorization, inputs, external calls, audit/timeline, secrets/config, security-sensitive scope; DevOps —
runtime/deployment/env/CI/deployability when RUN_DEVOPS=yes. Reviewers do NOT repair during review.
- **FR2 — Validator pass** (role: product-manager; artifacts: none)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/validate-trackers.py` (cwd: framework, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-symbols` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - run `python3 agents/scripts/validate_templates.py` (cwd: framework, timeout: 300s)
    - judgment: The op above is the CLOSEOUT-AUDIT validator; for candidate-audit swap the first op for
`validate-feature-evidence.py --feature {FEATURE_ID} --run-id {FEATURE_RUN_ID} --stage G6`. When story
files changed, also run `generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/` as a CURRENCY
CHECK — a non-zero diff is a finding, not a repair (this read-only audit never commits the regeneration).
Record exit code, summary, and artifact path for each command in lifecycle-gates.log.
- **FR3 — Self-review gate** (role: product-manager; artifacts: none)
    - judgment: Each reviewer verifies that its findings cite exact evidence (raw files/paths, not report summaries) and
that any skipped item is explicitly justified.
- **FR4 — Done gate** (role: product-manager; artifacts: none)
    - judgment: Compute the completion verdict with gate_policy.py (profile review-family): evidence validation FAIL or
critical > 0 -> NOT DONE; validation PASS, critical = 0, high > 0 -> CONDITIONALLY DONE (each high needs
owner + mitigation + target date); validation PASS, critical = 0, high = 0 -> TRULY DONE. Never declare
TRULY DONE while required evidence validation fails.

Severity gate profile: `review-family` (compute allowed outcomes with `agents/scripts/gate_policy.py`; coverage floor is 80%).

Ownership (strict):
- **architect** owns: Architecture and KG Alignment findings
- **code-reviewer** owns: Code Quality and merge-readiness findings
- **devops** owns: Deployability findings when RUN_DEVOPS resolves to yes
- **product-manager** owns: Requirements Satisfaction, Signoff and Closeout, Tracker Sync findings
- **quality-engineer** owns: Test Evidence and Coverage findings
- **security** owns: Security findings

Forbidden:
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

Stop conditions:
- FEATURE_ID, FEATURE_PATH, FEATURE_RUN_ID, or FEATURE_RUN_FOLDER cannot be resolved.
- The feature evidence package is missing outside explicit candidate-audit mode.
- The changed-file set cannot be identified.
- Required evidence validation fails in a way that prevents completion review.
- Reviewers cannot cite concrete evidence for FR4.

Conflict resolution:
- raw artifact vs evidence summary -> raw artifact wins; record an evidence-drift finding.
- latest-run.json points to a different run than FEATURE_RUN_ID in closeout-audit -> NOT DONE unless older-run review is explicit.
- role report passes but raw evidence contradicts it -> raw evidence wins.
- required evidence missing for a completed-terminal feature -> NOT DONE.
- a high finding accepted without owner, mitigation, and target date -> CONDITIONALLY DONE at best.

Note (modes): closeout-audit audits the approved feature run (FEATURE_RUN_ID defaults to the latest-run.json run_id;
validate --stage closeout). candidate-audit audits an in-progress run (FEATURE_RUN_ID set, FEATURE_RUN_FOLDER
exists; validate --run-id {FEATURE_RUN_ID} --stage G6). Precondition: feature.md reached G6 or G8 for FEATURE_ID.

Note (read_only): feature-review READS but never writes the canonical feature evidence package. Repair ownership stays with the
original lifecycle owners (feature.md / review.md / test.md / targeted rework); reviewers never repair during
review — a NOT DONE / CONDITIONALLY DONE verdict routes the fix back to the owner.

Note (report_sections): feature-review-report.md required sections: Decision; Findings By Severity; Completion Checks; Validation
Evidence; Artifact Trace. README.md summarizes the done state and open follow-ups; gate-decisions.md records
FR0 through FR4.

Note (session_setup): Echo the resolved absolute {PRODUCT_ROOT} on the first turn. Generate FEATURE_REVIEW_RUN_ID once in contract
format (an ISO YYYY-MM-DD date plus a secrets.token_hex(4) suffix); never uuid4. Resolve FEATURE_SLUG/PATH/
INDEX_ROOT/RUN_ID/RUN_FOLDER, then create FEATURE_REVIEW_RUN_FOLDER and its artifacts/ and initialize the six
§8 base run files.

Note (target): PR_URL is the usual target: `gh pr checkout <PR#>`, then
`gh pr view <PR_URL> --json title,headRefName,baseRefName,state` -> FEATURE_ID from the F#### token in the
title/branch, DIFF_RANGE=origin/<baseRefName>..<headRefName>, MODE=candidate-audit if the PR is OPEN else
closeout-audit. Explicit inputs always override values derived from PR_URL.

Note (telemetry): Append every shell command to {FEATURE_REVIEW_RUN_FOLDER}/commands.log per the §13 JSONL schema
(schema_version, timestamp with timezone, cwd, command, exit_code, artifacts[], redactions[]).

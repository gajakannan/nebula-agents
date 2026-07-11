This prompt encodes the feature-review action under the Feature Evidence Contract in `CONSUMER-CONTRACT.md` (effective `2026-05-19`). Feature review is a read-only post-feature completion audit. It answers: `Is this feature truly done?` It produces a base run evidence package per section 8 with `feature-review-report.md`; it reads the feature evidence package but does NOT write into it.

REQUIRED INPUTS — set the review target as EITHER (a) or (b):
- (a) `PR_URL={GitHub PR URL}` — the usual case. The agent derives everything else from the PR: `gh pr checkout <PR#>`, then `gh pr view <PR_URL> --json title,headRefName,baseRefName,state` → `FEATURE_ID` = the `F####` token in the title/`headRefName`, `DIFF_RANGE` = `origin/{baseRefName}..{headRefName}`, `MODE` = `candidate-audit` when the PR is OPEN else `closeout-audit`. Echo the resolved values.
- (b) `FEATURE_ID={F####}` + `MODE={closeout-audit | candidate-audit}` + `DIFF_RANGE={base..head | working-tree | explicit changed-file set}` — when NOT reviewing a PR.

Explicit values always override anything derived from `PR_URL`.

OPTIONAL INPUTS (defaults apply when omitted):
- `FEATURE_RUN_ID={YYYY-MM-DD-[a-z0-9]{8}}` - required only when `MODE=candidate-audit` or when `latest-run.json` should not be used
- `PRODUCT_ROOT=` - default: sister-repo resolved per `agents/docs/AGENT-USE.md` -> Session Setup; override only for non-standard layouts
- `RUN_DEVOPS={auto | yes | no}` - default: `auto`; run DevOps when runtime, deployment, environment, CI, or deployability evidence is in scope

AUTO-RESOLVED (do not set; SESSION_SETUP and the orchestrator compute these):
- `FEATURE_SLUG` - kebab-case slug for `{FEATURE_ID}` from `REGISTRY.md`
- `FEATURE_PATH` - `{PRODUCT_ROOT}/planning-mds/features/{FEATURE_ID}-{FEATURE_SLUG}` or archive path when closed
- `FEATURE_INDEX_ROOT` - `{PRODUCT_ROOT}/planning-mds/operations/evidence/features/{FEATURE_ID}-{FEATURE_SLUG}`
- `FEATURE_RUN_ID` - from `{FEATURE_INDEX_ROOT}/latest-run.json` when `MODE=closeout-audit` and no override is set
- `FEATURE_RUN_FOLDER` - `{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{FEATURE_RUN_ID}`
- `FEATURE_REVIEW_RUN_ID` - `YYYY-MM-DD-{secrets.token_hex(4)}` generated once at session start
- `FEATURE_REVIEW_RUN_FOLDER` - `{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{FEATURE_REVIEW_RUN_ID}`

Echo the resolved absolute `{PRODUCT_ROOT}` path on your first turn before any shell command. Generate `FEATURE_REVIEW_RUN_ID` once using the contract format `YYYY-MM-DD-[a-z0-9]{8}` with an 8-character suffix from cryptographic randomness. Do not use `uuid4`. Create `{FEATURE_REVIEW_RUN_FOLDER}` and initialize the six section-8 base run files from templates: `README.md`, `action-context.md`, `artifact-trace.md`, `gate-decisions.md`, empty `commands.log`, and empty `lifecycle-gates.log`. Create `artifacts/` for command output capture.

Run `agents/actions/feature-review.md` with `FEATURE_ID`, `MODE`, `DIFF_RANGE`, and `FEATURE_RUN_ID` when provided.

Load context in this order: `agents/ROUTER.md` -> `agents/agent-map.yaml` -> `agents/docs/AGENT-USE.md` -> `agents/actions/feature-review.md` -> `agents/actions/feature.md` -> `{FEATURE_PATH}/feature-assembly-plan.md` -> `{FEATURE_PATH}/**` -> `{FEATURE_INDEX_ROOT}/latest-run.json` when present -> `{FEATURE_RUN_FOLDER}/evidence-manifest.json` -> role reports and support artifacts named by the manifest and needed for the review question -> `agents/product-manager/SKILL.md` -> `agents/architect/SKILL.md` -> `agents/quality-engineer/SKILL.md` -> `agents/code-reviewer/SKILL.md` -> `agents/security/SKILL.md` -> `agents/devops/SKILL.md` when DevOps runs.

Read source artifacts directly. Resolve the changed-file set from `DIFF_RANGE`, feature evidence (`scm.diff_artifact`, `changed_paths[]`), or the explicit operator list. For code review, inspect the changed files under `{PRODUCT_ROOT}/engine/`, `{PRODUCT_ROOT}/experience/`, and `{PRODUCT_ROOT}/neuron/` as applicable. Use KG tools as routing aids only; raw feature, evidence, source, API, schema, policy, and runtime artifacts win on conflict.

Don't write into the feature evidence package. Don't bulk-load `{FEATURE_RUN_FOLDER}/**`, raw logs, screenshots, or `artifacts/**` without a manifest citation, validator failure, or explicit operator request. Don't edit implementation code, tests, feature docs, closeout files, trackers, KG files, or evidence artifacts. Don't treat a prior feature-action approval as proof that the feature is done. Don't approve from report summaries without checking raw evidence paths. Don't substitute global lanes for feature-scoped role evidence. Don't ignore uncommitted or unreviewed changed files. Don't declare `TRULY DONE` while required evidence validation fails.

Keep ownership strict:
- Product Manager completion review owns requirement, story, signoff, closeout, tracker, archive, and status findings inside `feature-review-report.md`
- Architect completion review owns assembly-plan, API, schema, workflow, authorization, ADR, KG, code-index, and drift findings
- Quality Engineer completion review owns acceptance-criteria test mapping, runtime test evidence, coverage, and skipped-layer findings
- Code Reviewer completion review owns changed-code, scope, quality, hidden TODO/debug/dead-path, and merge-readiness findings
- Security completion review owns authorization, input validation, audit/timeline, secrets/config, and security-sensitive-scope findings
- DevOps completion review owns runtime, deployment, environment, CI, and deployability findings when it runs
- Reviewers produce findings only; owning lifecycle roles repair findings later through `feature.md`, `review.md`, `test.md`, or targeted rework

Follow these gates exactly:

- `FR0 FEATURE RUN AND DIFF LOCK` - record `FEATURE_ID`, `MODE`, `FEATURE_RUN_ID`, `FEATURE_PATH`, `FEATURE_RUN_FOLDER`, `DIFF_RANGE`, changed-file set, and DevOps inclusion decision in `action-context.md`
- `FR1 PARALLEL COMPLETION REVIEW`:
  - Product Manager checks whether stories, closeout, signoffs, trackers, archive state, and mitigations prove completion
  - Architect checks whether delivered behavior matches `feature-assembly-plan.md`, architecture, API/schema, authorization, KG, and code-index expectations
  - Quality Engineer checks whether tests and coverage prove every acceptance criterion or justify manual verification
  - Code Reviewer checks whether changed code is scoped, reviewed, merge-ready, and free of hidden incomplete paths
  - Security checks whether auth, inputs, secrets, audit, and security review evidence are complete
  - DevOps checks runtime/deployability evidence when `RUN_DEVOPS=yes` or `auto` resolves to yes
- `FR2 VALIDATOR PASS` - run applicable validator commands and append every command to `commands.log`:
  - closeout audit: `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout`
  - candidate audit: `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {FEATURE_RUN_ID} --stage G6`
  - `python3 agents/product-manager/scripts/validate-trackers.py`
  - `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/` when story files changed
  - `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-symbols`
  - `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift`
  - `python3 agents/scripts/validate_templates.py`
- `FR3 SELF-REVIEW GATE` - each reviewer verifies findings cite exact files, lines, report sections, or evidence paths; severities match done impact; skipped commands are justified; and no hidden fixes were made
- `FR4 DONE GATE` - produce the done decision:
  - failed required evidence validation or any critical finding -> `NOT DONE`
  - no critical but any high finding -> `CONDITIONALLY DONE`
  - no critical/high and evidence validation passes -> `TRULY DONE`

Evidence outputs land in `{FEATURE_REVIEW_RUN_FOLDER}`:
- section-8 base run files
- `feature-review-report.md`
- `artifacts/` command output captures when useful

`feature-review-report.md` must include: feature ID, feature run ID, review run ID, date, mode, review question, decision, rationale, next action, findings by severity, Completion Checks, Validation Evidence, and Artifact Trace.

Stop immediately if the feature or feature evidence run cannot be resolved, the feature evidence package is missing outside explicit `candidate-audit` mode, the changed-file set cannot be identified, required evidence validation fails in a way that prevents review, or reviewers cannot cite concrete evidence for the done decision.

Close the run when `feature-review-report.md` is complete, `README.md` summarizes the done decision and open follow-ups, `gate-decisions.md` records FR0 through FR4, every applicable validator result is recorded, the reviewed feature run and changed-file set are identified, and no implementation, feature, tracker, KG, or evidence artifacts were edited by this review action.

Resolve conflicts like this:
- Feature evidence summary vs raw artifact -> raw artifact wins; record evidence drift as a finding
- latest-run.json points to a different run than `FEATURE_RUN_ID` in closeout mode -> `NOT DONE` unless explicitly reviewing an older run
- Code/security/test report says pass but raw evidence contradicts it -> raw evidence wins
- Required evidence missing for a completed terminal feature -> `NOT DONE`
- High finding accepted without owner, mitigation, and target date -> `CONDITIONALLY DONE` at best

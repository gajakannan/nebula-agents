<!-- GENERATED from agents/actions/spec/feature.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action feature -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


This prompt encodes the **Feature Evidence Contract** (scope `feature-completion`, policy `2026-07-11`).

Required inputs:
- `FEATURE_ID` (format `F####`)

Optional inputs (defaults apply when omitted):
- `MODE` — default `clean`
- `SLICE_ORDER_SOURCE` — default `assembly-plan`
- `SLICE_ORDER`
- `PRODUCT_ROOT` — default `sister-repo`

Auto-resolved (do not set; SESSION_SETUP / the orchestrator compute these):
- `ARCHIVE_FEATURE_PATH` — {PRODUCT_ROOT}/planning-mds/features/archive/{FEATURE_ID}-{FEATURE_SLUG}
- `FEATURE_INDEX_ROOT` — {PRODUCT_ROOT}/planning-mds/operations/evidence/features/{FEATURE_ID}-{FEATURE_SLUG}
- `FEATURE_PATH` — {PRODUCT_ROOT}/planning-mds/features/{FEATURE_ID}-{FEATURE_SLUG}
- `FEATURE_SLUG` — kebab-case slug for {FEATURE_ID} from REGISTRY.md
- `RERUN_OF` — null, or {RUN_ID_PRIOR} when this run regenerates evidence only
- `RUN_FOLDER` — {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}
- `RUN_ID_PRIOR` — prior approved run_id from {FEATURE_INDEX_ROOT}/latest-run.json (null if absent)

Generate `RUN_ID` once at session start in the contract format `YYYY-MM-DD-[a-z0-9]{8}` using `python3 -c import secrets; print(secrets.token_hex(4))`. Do not use: uuid4.

Session setup: create the run under `planning-mds/operations/evidence/`, initialize `evidence-manifest.json` (status `draft`) with the active contract version stamped, create the base run files (README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log) and artifact subdirs (coverage, diffs, test-results, security, screenshots). Run `agents/scripts/init-run.py` to perform this.

Retrieval tier defaults: clean: [1, 2]; drift-reconcile: [3, 4]

Load context in this order, then navigate rather than eager-load:
1. `agents/ROUTER.md`
2. `agents/agent-map.yaml`
3. `agents/docs/AGENT-USE.md`
4. `agents/actions/feature.md`
5. `python3 {PRODUCT_ROOT}/scripts/kg/lookup.py {FEATURE_ID} --tier {start_tier} --run-id {RUN_ID}`
6. `{FEATURE_PATH}`

Gates (run each stage through `agents/scripts/run-gate.py`, in order):
- **G0 — Architect assembly plan authoring and validation** (role: architect; artifacts: g0-assembly-plan-validation.md)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G0` (cwd: framework, timeout: 300s)
    - judgment: Step 0 (author): if PRIMARY_SPEC (feature-assembly-plan.md) is absent, author it from the
template using the feature stories, BLUEPRINT.md, SOLUTION-PATTERNS.md, and API contracts; on
drift-reconcile/rerun, reconcile the existing plan instead of overwriting. Step 0.5 (validate):
check scope split, agent dependencies, integration checkpoints, and artifact ownership, and
initialize the Required Signoff Roles matrix in STATUS.md. Flip manifest status to in-progress
after G0 passes.
- **G1 — Runtime preflight** (role: devops; artifacts: g1-runtime-preflight.md)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G1` (cwd: framework, timeout: 300s)
    - judgment: Write g1-runtime-preflight.md when runtime_bearing=true; otherwise record the manifest omission.
- **G2 — Self-review, QE, and deployability** (role: quality-engineer; artifacts: g2-self-review.md, test-plan.md, test-execution-report.md, coverage-report.md, g2-deployability-check.md)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G2` (cwd: framework, timeout: 600s)
    - judgment: Reconcile the manifest conditional booleans against discovered scope FIRST (see
notes.scope_booleans). Any false->true flip forces the corresponding required role and artifact.
coverage-report.md must exist even when waived. Booleans that change after G2 force re-running G2.
Coverage floor is `coverage_min_pct` (owned by _contract.yaml); do not restate the number.
- **G3 — Code and security review (parallel)** (role: code-reviewer; artifacts: code-review-report.md, security-review-report.md)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G3` (cwd: framework, timeout: 300s)
    - judgment: Code Reviewer and Security Reviewer run in parallel. security-review-report.md is required when
security_sensitive_scope=true or Security is required in STATUS.md.
- **G4 — Approval** (role: product-manager; artifacts: gate-decisions.md)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G4` (cwd: framework, timeout: 300s)
    - judgment: Approval requires critical=0; any high requires an explicit mitigation token recorded in
gate-decisions.md. Compute the allowed outcome with gate_policy.py (profile `standard`).
- **G5 — Signoff** (role: product-manager; artifacts: signoff-ledger.md)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G5` (cwd: framework, timeout: 300s)
    - judgment: Every Required=Yes role records verdict, reviewer, ISO date, and an evidence path under
RUN_FOLDER. A `WITH RECOMMENDATIONS` verdict must satisfy all five §15 closeout-passing conditions
in the underlying role report (non-blocking/deferred, severity, owner+follow-up, named PM
acceptance, no blocking language with a passing verdict).
- **G6 — Candidate evidence validation** (role: quality-engineer; artifacts: feature-action-execution.md)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G6` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID}` (cwd: framework, timeout: 300s)
    - judgment: Pre-closeout candidate: no pm_closeout, no tracker_sync, no latest-run.json yet. Confirm G0–G5
evidence present and passing; changed_paths[] populated; conditional booleans cross-check against
the §7 path-class globs; non-required absent artifacts appear in manifest omissions[].
- **G7 — Architect knowledge-graph reconciliation** (role: architect; artifacts: kg-reconciliation.md)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/compile.py` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --regenerate-symbols --check-symbols --regenerate-decisions --check-decisions` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - constraint: `--write-coverage-report` forbidden — path-sensitive; deferred to G8 after the archive move relocates evidence paths
    - judgment: MUST switch role (read agents/architect/SKILL.md). Bind the as-built source into the SEMANTIC
graph via kg-source/bindings/** and kg-source/nodes/** shards, then compile.py regenerates the
projection trio + tracker regions — never hand-edit knowledge-graph/*.yaml. CODE paths only
(stable across the G8 archive move). Manifest stays in-progress; record gate_results.kg_reconciliation.
- **G8 — PM closeout** (role: product-manager; artifacts: pm-closeout.md)
    - MANUAL checkpoint `archive-move`: VERIFY (do not re-author) the G7 graph, update trackers (STATUS/REGISTRY/ROADMAP/BLUEPRINT + kg-source feature shard), and move the feature folder to its archived path when Done/Completed. (requires: pm-closeout.md, signoff-ledger.md, kg-reconciliation.md; produces: archived-feature-folder)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/compile.py` (cwd: product, timeout: 300s)
    - run `python3 agents/product-manager/scripts/patch-prior-manifest.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --new-run-id {RUN_ID}` (cwd: framework, timeout: 120s)
    - write `latest-run.json` after `patch-prior-manifest`
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID}` (cwd: framework, timeout: 300s)
    - judgment: MUST switch role (read agents/product-manager/SKILL.md). Manifest status becomes `approved` only
here, when latest-run.json is written — and only after patch-prior-manifest.py exits 0. Run
--write-coverage-report ONLY after the archive move (path-sensitive). Finalize the manifest
(status approved, feature_state Done/Completed/Archived, feature_path_at_closeout resolved).

Severity gate profile: `standard` (compute allowed outcomes with `agents/scripts/gate_policy.py`; coverage floor is 80%).

Ownership (strict):
- **architect** owns: feature-assembly-plan.md, g0-assembly-plan-validation.md, kg-reconciliation.md, ADRs, canonical shared semantics, API contracts + schemas
- **code-reviewer** owns: code-review-report.md
- **devops** owns: g1-runtime-preflight.md, g2-deployability-check.md
- **product-manager** owns: pm-closeout.md, signoff-ledger.md, latest-run.json, STATUS.md final state, trackers + archive move, manifest finalize (status approved), prior-manifest supersession
- **quality-engineer** owns: test-plan.md, test-execution-report.md, coverage-report.md
- **security** owns: security-review-report.md

Forbidden:
- Generate RUN_ID with uuid4 or any non-contract format.
- Write or consume current-run.json.
- Write latest-run.json before G8 final validation passes.
- Leave a prior approved manifest at status approved after writing a new approval.
- Skip per-gate validate-feature-evidence.py --stage calls.
- Write terminal-feature role reports into FEATURE_PATH instead of RUN_FOLDER.
- Cite the global frontend evidence lane as a substitute for a feature-level role report.
- Hand-enumerate schema/ADR/contract files when lookup output is available.
- Treat lookup/KG mappings as authoritative over raw artifacts.
- Edit code without prior hint.py, or shared semantics without prior blast.py.
- Skip any gate G0 through G8, or declare Done without the PM role switch at G8.
- Widen scope outside FEATURE_ID, or pass --evidence-effective-date earlier than the framework default.

Stop conditions:
- Runtime preflight cannot be restored.
- A critical code or security finding persists after one review cycle.
- Required signoff is missing reviewer, date, or evidence.
- A canonical node edit is attempted outside the Architect role.
- Scope drifts outside FEATURE_ID.
- validate.py or validate.py --check-drift cannot be auto-repaired.
- validate-feature-evidence.py at any stage exits non-zero and the cause is not addressable in this run.
- Two approved manifests are detected for the same feature without supersession.
- INSUFFICIENT_CONTEXT occurs — escalate, open raw artifacts, do not proceed on weak matches.

Conflict resolution:
- raw artifact vs KG mapping -> raw wins; repair KG in the same change set.
- feature-assembly-plan vs story text -> plan wins; log via workstate.py decision --topic plan-story-reconcile.
- code vs contract/policy/KG -> reconcile to contract; never silently redefine canonical semantics.
- shared-semantics change detected -> halt and route to Architect.
- STATUS.md story value not in the feature's local breakdown -> fix STATUS.md (STORY-INDEX.md is cross-check only).
- manifest conditional boolean false but changed_paths has a forced path class -> set the boolean true and add the required role/artifact.

Note (concurrent_run_check): Before starting, inspect only evidence-manifest.json files under
{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/*/ for any run other than RUN_FOLDER whose
manifest has feature_id={FEATURE_ID} and status draft or in-progress. If one exists, HALT and
reconcile externally — the contract assumes serial feature actions per feature. Acceptable prior
states: approved (superseded at G8), superseded, or no prior runs.

Note (scope_booleans): At G2 set frontend_in_scope=true when any changed_paths[] entry matches experience/** frontend
globs; runtime_bearing=true for engine/** runtime/tests/AI-runtime globs; deployment_config_changed
=true for Dockerfile/compose/.github-workflows/ci/env/config/migration globs; security_sensitive_
scope=true for auth/identity/permissions/security/secrets globs.

Note (session_setup): Echo the resolved absolute {PRODUCT_ROOT} on the first turn before any command. Create
FEATURE_INDEX_ROOT, RUN_FOLDER, and RUN_FOLDER/artifacts/{coverage,diffs,test-results,security,
screenshots}. Initialize evidence-manifest.json (status draft, contract version stamped, all
required keys, skeleton gate_results/role_results/files). Create the base run files and touch empty
commands.log and lifecycle-gates.log. Capture a prior latest-run.json run_id as RUN_ID_PRIOR.

Note (telemetry): Append every shell command to RUN_FOLDER/commands.log via append-command-log.py (--log,
--product-root, --framework-root, --cwd, --command, --exit-code, repeatable --artifact). Artifact
paths must be durable product-repo paths under artifacts/; scratch paths (/tmp/...) are not
durable. Do not leak secrets — secret-pattern checks fail the run.

Note (validator_defect_flow): If a validator defect blocks closeout, prefer to fix the validator and re-run. Mid-stage (G0..G6)
defects are logged as open follow-ups in README.md (not waivers yet); if unresolved at G8, record a
waivers.validator_defect entry in the manifest and mirror it in pm-closeout.md. Never bypass with an
earlier-than-default --evidence-effective-date.

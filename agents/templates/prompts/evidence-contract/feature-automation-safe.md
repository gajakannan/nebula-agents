<!-- GENERATED from agents/actions/spec/feature.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action feature -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


CONTRACT: Feature Evidence Contract | SCOPE: feature-completion | POLICY: 2026-07-11

REQUIRED_INPUTS:
- FEATURE_ID [F####]
OPTIONAL_INPUTS:
- MODE =default:clean
- SLICE_ORDER_SOURCE =default:assembly-plan
- SLICE_ORDER
- PRODUCT_ROOT =default:sister-repo
AUTO_RESOLVED:
- ARCHIVE_FEATURE_PATH = {PRODUCT_ROOT}/planning-mds/features/archive/{FEATURE_ID}-{FEATURE_SLUG}
- FEATURE_INDEX_ROOT = {PRODUCT_ROOT}/planning-mds/operations/evidence/features/{FEATURE_ID}-{FEATURE_SLUG}
- FEATURE_PATH = {PRODUCT_ROOT}/planning-mds/features/{FEATURE_ID}-{FEATURE_SLUG}
- FEATURE_SLUG = kebab-case slug for {FEATURE_ID} from REGISTRY.md
- RERUN_OF = null, or {RUN_ID_PRIOR} when this run regenerates evidence only
- RUN_FOLDER = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}
- RUN_ID_PRIOR = prior approved run_id from {FEATURE_INDEX_ROOT}/latest-run.json (null if absent)

RUN_ID: var=RUN_ID format=YYYY-MM-DD-[a-z0-9]{8} method=python3 -c import secrets; print(secrets.token_hex(4)) forbidden=uuid4
SESSION_SETUP: init-run.py -> planning-mds/operations/evidence/... manifest=draft base_files=[README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log] artifacts=[coverage, diffs, test-results, security, screenshots]
RETRIEVAL_TIERS: clean=[1, 2]; drift-reconcile=[3, 4]
CONTEXT: agents/ROUTER.md -> agents/agent-map.yaml -> agents/docs/AGENT-USE.md -> agents/actions/feature.md -> python3 {PRODUCT_ROOT}/scripts/kg/lookup.py {FEATURE_ID} --tier {start_tier} --run-id {RUN_ID} -> {FEATURE_PATH}

GATES:
- G0 role=architect artifacts=[g0-assembly-plan-validation.md]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G0` (cwd: framework, timeout: 300s)
- G1 role=devops artifacts=[g1-runtime-preflight.md]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G1` (cwd: framework, timeout: 300s)
- G2 role=quality-engineer artifacts=[g2-self-review.md, test-plan.md, test-execution-report.md, coverage-report.md, g2-deployability-check.md]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G2` (cwd: framework, timeout: 600s)
- G3 role=code-reviewer artifacts=[code-review-report.md, security-review-report.md]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G3` (cwd: framework, timeout: 300s)
- G4 role=product-manager artifacts=[gate-decisions.md]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G4` (cwd: framework, timeout: 300s)
- G5 role=product-manager artifacts=[signoff-ledger.md]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G5` (cwd: framework, timeout: 300s)
- G6 role=quality-engineer artifacts=[feature-action-execution.md]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G6` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID}` (cwd: framework, timeout: 300s)
- G7 role=architect artifacts=[kg-reconciliation.md]
    - run `python3 {PRODUCT_ROOT}/scripts/kg/compile.py` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --regenerate-symbols --check-symbols --regenerate-decisions --check-decisions` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - FORBID --write-coverage-report :: path-sensitive; deferred to G8 after the archive move relocates evidence paths
- G8 role=product-manager artifacts=[pm-closeout.md]
    - MANUAL checkpoint `archive-move`: VERIFY (do not re-author) the G7 graph, update trackers (STATUS/REGISTRY/ROADMAP/BLUEPRINT + kg-source feature shard), and move the feature folder to its archived path when Done/Completed. (requires: pm-closeout.md, signoff-ledger.md, kg-reconciliation.md; produces: archived-feature-folder)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/compile.py` (cwd: product, timeout: 300s)
    - run `python3 agents/product-manager/scripts/patch-prior-manifest.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --new-run-id {RUN_ID}` (cwd: framework, timeout: 120s)
    - write `latest-run.json` after `patch-prior-manifest`
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID}` (cwd: framework, timeout: 300s)

SEVERITY_GATE: profile=standard tool=gate_policy.py coverage_min_pct=80
OWNERSHIP:
- architect: feature-assembly-plan.md, g0-assembly-plan-validation.md, kg-reconciliation.md, ADRs, canonical shared semantics, API contracts + schemas
- code-reviewer: code-review-report.md
- devops: g1-runtime-preflight.md, g2-deployability-check.md
- product-manager: pm-closeout.md, signoff-ledger.md, latest-run.json, STATUS.md final state, trackers + archive move, manifest finalize (status approved), prior-manifest supersession
- quality-engineer: test-plan.md, test-execution-report.md, coverage-report.md
- security: security-review-report.md
FORBIDDEN:
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
STOP_CONDITIONS:
- Runtime preflight cannot be restored.
- A critical code or security finding persists after one review cycle.
- Required signoff is missing reviewer, date, or evidence.
- A canonical node edit is attempted outside the Architect role.
- Scope drifts outside FEATURE_ID.
- validate.py or validate.py --check-drift cannot be auto-repaired.
- validate-feature-evidence.py at any stage exits non-zero and the cause is not addressable in this run.
- Two approved manifests are detected for the same feature without supersession.
- INSUFFICIENT_CONTEXT occurs — escalate, open raw artifacts, do not proceed on weak matches.
CONFLICT_RESOLUTION:
- raw artifact vs KG mapping -> raw wins; repair KG in the same change set.
- feature-assembly-plan vs story text -> plan wins; log via workstate.py decision --topic plan-story-reconcile.
- code vs contract/policy/KG -> reconcile to contract; never silently redefine canonical semantics.
- shared-semantics change detected -> halt and route to Architect.
- STATUS.md story value not in the feature's local breakdown -> fix STATUS.md (STORY-INDEX.md is cross-check only).
- manifest conditional boolean false but changed_paths has a forced path class -> set the boolean true and add the required role/artifact.
NOTE[concurrent_run_check]: Before starting, inspect only evidence-manifest.json files under
{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/*/ for any run other than RUN_FOLDER whose
manifest has feature_id={FEATURE_ID} and status draft or in-progress. If one exists, HALT and
reconcile externally — the contract assumes serial feature actions per feature. Acceptable prior
states: approved (superseded at G8), superseded, or no prior runs.
NOTE[scope_booleans]: At G2 set frontend_in_scope=true when any changed_paths[] entry matches experience/** frontend
globs; runtime_bearing=true for engine/** runtime/tests/AI-runtime globs; deployment_config_changed
=true for Dockerfile/compose/.github-workflows/ci/env/config/migration globs; security_sensitive_
scope=true for auth/identity/permissions/security/secrets globs.
NOTE[session_setup]: Echo the resolved absolute {PRODUCT_ROOT} on the first turn before any command. Create
FEATURE_INDEX_ROOT, RUN_FOLDER, and RUN_FOLDER/artifacts/{coverage,diffs,test-results,security,
screenshots}. Initialize evidence-manifest.json (status draft, contract version stamped, all
required keys, skeleton gate_results/role_results/files). Create the base run files and touch empty
commands.log and lifecycle-gates.log. Capture a prior latest-run.json run_id as RUN_ID_PRIOR.
NOTE[telemetry]: Append every shell command to RUN_FOLDER/commands.log via append-command-log.py (--log,
--product-root, --framework-root, --cwd, --command, --exit-code, repeatable --artifact). Artifact
paths must be durable product-repo paths under artifacts/; scratch paths (/tmp/...) are not
durable. Do not leak secrets — secret-pattern checks fail the run.
NOTE[validator_defect_flow]: If a validator defect blocks closeout, prefer to fix the validator and re-run. Mid-stage (G0..G6)
defects are logged as open follow-ups in README.md (not waivers yet); if unresolved at G8, record a
waivers.validator_defect entry in the manifest and mirror it in pm-closeout.md. Never bypass with an
earlier-than-default --evidence-effective-date.

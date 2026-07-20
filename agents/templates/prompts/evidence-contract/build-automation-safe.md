<!-- GENERATED from agents/actions/spec/build.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action build -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


CONTRACT: Feature Evidence Contract | SCOPE: base-run-only | POLICY: 2026-07-11

REQUIRED_INPUTS:
- BUILD_SCOPE [[F####, F####, ...] — features closed/archived in this build (may be empty for non-feature builds)]
OPTIONAL_INPUTS:
- MODE =default:clean
- PRODUCT_ROOT =default:sister-repo
AUTO_RESOLVED:
- BUILD_RUN_FOLDER = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{BUILD_RUN_ID}
- FEATURE_INDEX_ROOT = {PRODUCT_ROOT}/planning-mds/operations/evidence/features/{FEATURE_ID}-{FEATURE_SLUG}
- FEATURE_PATH = {PRODUCT_ROOT}/planning-mds/features/{FEATURE_ID}-{FEATURE_SLUG}
- FEATURE_SLUG = per FEATURE_ID in BUILD_SCOPE: kebab-case slug from REGISTRY.md
- RERUN_OF = null, or {RUN_ID_PRIOR} for an evidence-only rerun with empty changed_paths[]
- RUN_FOLDER = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}
- RUN_ID = per-feature run id minted when a new feature package is produced (contract format YYYY-MM-DD-token_hex(4))
- RUN_ID_PRIOR = prior approved run_id from {FEATURE_INDEX_ROOT}/latest-run.json (null if absent)

RUN_ID: var=BUILD_RUN_ID format=YYYY-MM-DD-[a-z0-9]{8} method=python3 -c import secrets; print(secrets.token_hex(4)) forbidden=uuid4
SESSION_SETUP: init-run.py -> planning-mds/operations/evidence/... manifest=draft base_files=[README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log] artifacts=[coverage, diffs, test-results, security, screenshots]
CONTEXT: agents/ROUTER.md -> agents/agent-map.yaml -> agents/docs/AGENT-USE.md -> agents/actions/build.md -> {PRODUCT_ROOT}/planning-mds/features/REGISTRY.md -> per FEATURE_ID in BUILD_SCOPE: {FEATURE_PATH}/STATUS.md and {FEATURE_INDEX_ROOT}/latest-run.json (if present; absence is normal for a first-time close)

GATES:
- B0 role=product-manager artifacts=[action-context.md, gate-decisions.md]
- B1 role=product-manager artifacts=[]
- B2 role=product-manager artifacts=[]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G6` (cwd: framework, timeout: 300s)
- B3 role=product-manager artifacts=[]
    - run `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT}` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/` (cwd: framework, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - run `python3 agents/scripts/validate_templates.py` (cwd: framework, timeout: 300s)
- B4 role=product-manager artifacts=[pm-closeout.md]
    - run `python3 agents/product-manager/scripts/patch-prior-manifest.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --new-run-id {RUN_ID}` (cwd: framework, timeout: 120s)
    - write `latest-run.json` after `b4-patch-prior-manifest`
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout` (cwd: framework, timeout: 300s)
- B4.5 role=product-manager artifacts=[]
    - MANUAL checkpoint `build-approval`: User reviews the aggregated per-feature closeouts (every pm-closeout.md from B4) plus the B3 lifecycle validator results. On refusal: HALT — do not proceed to B5; any further changes restart at B1 for the affected features. (requires: every pm-closeout.md from B4, B3 lifecycle validator results in lifecycle-gates.log; produces: build-approved (recorded as the B4.5 row in gate-decisions.md))
- B5 role=product-manager artifacts=[README.md, action-context.md, artifact-trace.md, gate-decisions.md]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT}` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/` (cwd: framework, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --regenerate-symbols --check-symbols --regenerate-decisions --check-decisions` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - run `python3 agents/scripts/validate_templates.py` (cwd: framework, timeout: 300s)

SEVERITY_GATE: profile=none tool=gate_policy.py coverage_min_pct=80
OWNERSHIP:
- build-orchestrator: BUILD_RUN_FOLDER base run files, sequencing across features, lifecycle-gates.log aggregation
- product-manager: pm-closeout.md, manifest finalize (status approved), prior-manifest supersession, latest-run.json, signoff-ledger.md, STATUS/REGISTRY/ROADMAP/BLUEPRINT + KG mappings, build-level archive decisions + REGISTRY.md updates
FORBIDDEN:
- Generate BUILD_RUN_ID or any feature RUN_ID with uuid4.
- Close a feature without a canonical evidence package at {FEATURE_INDEX_ROOT}/latest-run.json with status approved.
- Call validate-trackers.py before per-feature G6 candidate validation has passed for every feature being closed.
- Write per-feature role reports (g0-*, test-*, code-review-*, etc.) into BUILD_RUN_FOLDER instead of the feature run folder.
- Use the build run folder as a substitute for any feature's evidence package.
- Place a feature evidence package under BUILD_RUN_FOLDER.
- Mark a feature Archived in REGISTRY.md while its latest-run.json is missing or non-approved.
- Pass --evidence-effective-date earlier than the framework default.
STOP_CONDITIONS:
- Any feature in BUILD_SCOPE fails G6 candidate validation and the cause is not addressable in this build.
- Tracker validation fails and cannot be auto-repaired.
- A feature's prior approved manifest cannot be patched to superseded (write fails or schema rejects).
- Two approved manifests are detected for the same feature after B4 (two_approved_runs_without_supersession_fails).
- INSUFFICIENT_CONTEXT occurs for any feature in BUILD_SCOPE.
- validate.py or --check-drift fails after one repair cycle.
CONFLICT_RESOLUTION:
- feature evidence package present but STATUS.md missing current signoff rows -> halt; the feature is not closeout-ready.
- REGISTRY.md says Archived but feature evidence package missing or non-approved -> halt; fix REGISTRY.md, do not backfill pre-contract evidence.
- per-feature manifest disagrees with STATUS.md current verdicts -> fix the feature (re-run its G5) before continuing the build.
- build re-closing a feature with an existing approved package -> mint a NEW RUN_ID, set RERUN_OF appropriately, and run patch-prior-manifest.py before writing the new latest-run.json at B4.
NOTE[build_loop]: build is feature-in-a-loop at the ORCHESTRATION layer: it does not re-derive feature's G0-G8 gates —
it invokes the feature action per FEATURE_ID (B1 -> feature G0-G6; B4 -> feature G8) and wraps them
with build-level scope lock (B0), aggregate lifecycle validation (B3), a holistic user approval (B4.5),
and a build closeout + exit sweep (B5). Per-feature ownership of role reports inherits from the feature
action; this spec owns only the build-level base run files and cross-feature sequencing.
NOTE[non_feature_build]: A build with an empty BUILD_SCOPE still produces the base run package at {BUILD_RUN_FOLDER} (the six
base files) per §8. It does NOT produce a feature evidence package and does NOT call
validate-feature-evidence.py (no feature scope). Tracker validation still runs as a sanity check.
NOTE[preconditions]: {BUILD_RUN_FOLDER} created with base run files present; every feature in BUILD_SCOPE has either an
existing approved package referenced by {FEATURE_INDEX_ROOT}/latest-run.json or a planned package to be
produced during this build; `python3 {PRODUCT_ROOT}/scripts/kg/validate.py` exits 0 at start.
NOTE[session_setup]: Echo the resolved absolute {PRODUCT_ROOT} on the first turn before any command. Generate BUILD_RUN_ID
once at session start in contract format (an ISO YYYY-MM-DD date plus a secrets.token_hex(4) suffix);
never uuid4, never regenerate it after start. Create {BUILD_RUN_FOLDER} and initialize the base run
files from templates: README.md,
action-context.md, artifact-trace.md, gate-decisions.md, an empty commands.log (JSONL), and an empty
lifecycle-gates.log. The build run folder is a base run package, NOT a feature evidence package — every
feature closed in this build keeps its own package at that feature's {RUN_FOLDER}, produced by the
delegated feature action's own session setup (which mints each per-feature {RUN_ID}).
NOTE[telemetry]: Append every shell command to {BUILD_RUN_FOLDER}/commands.log as JSON Lines per the §13 schema
(schema_version, timestamp with timezone, cwd, command, exit_code, artifacts[], redactions[]). Append
every lifecycle validator command (tracker, story-index, KG, validate_templates, and each per-feature
validate-feature-evidence call) to {BUILD_RUN_FOLDER}/lifecycle-gates.log.

<!-- GENERATED from agents/actions/spec/build.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action build -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


This prompt encodes the **Feature Evidence Contract** (scope `base-run-only`, policy `2026-07-11`).

Required inputs:
- `BUILD_SCOPE` (format `[F####, F####, ...] — features closed/archived in this build (may be empty for non-feature builds)`)

Optional inputs (defaults apply when omitted):
- `MODE` — default `clean`
- `PRODUCT_ROOT` — default `sister-repo`

Auto-resolved (do not set; SESSION_SETUP / the orchestrator compute these):
- `BUILD_RUN_FOLDER` — {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{BUILD_RUN_ID}
- `FEATURE_INDEX_ROOT` — {PRODUCT_ROOT}/planning-mds/operations/evidence/features/{FEATURE_ID}-{FEATURE_SLUG}
- `FEATURE_PATH` — {PRODUCT_ROOT}/planning-mds/features/{FEATURE_ID}-{FEATURE_SLUG}
- `FEATURE_SLUG` — per FEATURE_ID in BUILD_SCOPE: kebab-case slug from REGISTRY.md
- `RERUN_OF` — null, or {RUN_ID_PRIOR} for an evidence-only rerun with empty changed_paths[]
- `RUN_FOLDER` — {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}
- `RUN_ID` — per-feature run id minted when a new feature package is produced (contract format YYYY-MM-DD-token_hex(4))
- `RUN_ID_PRIOR` — prior approved run_id from {FEATURE_INDEX_ROOT}/latest-run.json (null if absent)

Generate `BUILD_RUN_ID` once at session start in the contract format `YYYY-MM-DD-[a-z0-9]{8}` using `python3 -c import secrets; print(secrets.token_hex(4))`. Do not use: uuid4.

Session setup: create the run under `planning-mds/operations/evidence/`, initialize `evidence-manifest.json` (status `draft`) with the active contract version stamped, create the base run files (README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log) and artifact subdirs (coverage, diffs, test-results, security, screenshots). Run `agents/scripts/init-run.py` to perform this.

Load context in this order, then navigate rather than eager-load:
1. `agents/ROUTER.md`
2. `agents/agent-map.yaml`
3. `agents/docs/AGENT-USE.md`
4. `agents/actions/build.md`
5. `{PRODUCT_ROOT}/planning-mds/features/REGISTRY.md`
6. `per FEATURE_ID in BUILD_SCOPE: {FEATURE_PATH}/STATUS.md and {FEATURE_INDEX_ROOT}/latest-run.json (if present; absence is normal for a first-time close)`

Gates (run each stage through `agents/scripts/run-gate.py`, in order):
- **B0 — Build scope lock** (role: product-manager; artifacts: action-context.md, gate-decisions.md)
    - judgment: Confirm the BUILD_SCOPE list and record it in {BUILD_RUN_FOLDER}/action-context.md as the first
artifact. Confirm each feature's current state in REGISTRY.md and STATUS.md. Order BUILD_SCOPE by
dependency before B1: if any feature's manifest changed_paths[] or feature-mappings.yaml references
files newly bound by another feature in scope, the dependency must close first; ties resolve by
FEATURE_ID ascending. Record the resolved order in gate-decisions.md as the B0 row.
- **B1 — Per-feature evidence package production (delegates to feature G0-G6)** (role: product-manager; artifacts: none)
    - judgment: For each FEATURE_ID in BUILD_SCOPE WITHOUT an approved package: invoke the feature action
(evidence-contract/feature-automation-safe.md, or its operator-friendly mirror) with a fresh
{RUN_ID} and rerun_of=null, and run that feature through G0-G6 candidate. For each FEATURE_ID being
re-closed (already had an approved package, changing again now): mint a NEW {RUN_ID}; set rerun_of=null
if implementation changed, or rerun_of={RUN_ID_PRIOR} for an evidence-only rerun with empty
changed_paths[] (§11). For each FEATURE_ID with an existing approved package re-validated without
changes: confirm latest-run.json resolves and its manifest status=approved; do NOT create a new run
folder. Per-feature role reports live at each feature's {RUN_FOLDER}, never under {BUILD_RUN_FOLDER}.
- **B2 — Per-feature G6 candidate validation** (role: product-manager; artifacts: none)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G6` (cwd: framework, timeout: 300s)
    - judgment: Run the op above for EACH FEATURE_ID in BUILD_SCOPE (the argv shows the per-feature form). Every
in-progress run must pass candidate validation before any tracker sync at B3.
- **B3 — Lifecycle validators (tracker, story-index, KG drift, templates)** (role: product-manager; artifacts: none)
    - run `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT}` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/` (cwd: framework, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - run `python3 agents/scripts/validate_templates.py` (cwd: framework, timeout: 300s)
    - judgment: validate-trackers.py iterates BUILD_SCOPE and internally calls validate-feature-evidence.py
--stage G6 per §22. Append every command + exit code here to {BUILD_RUN_FOLDER}/lifecycle-gates.log.
- **B4 — Per-feature G8 PM closeout (delegates to feature G8)** (role: product-manager; artifacts: pm-closeout.md)
    - run `python3 agents/product-manager/scripts/patch-prior-manifest.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --new-run-id {RUN_ID}` (cwd: framework, timeout: 120s)
    - write `latest-run.json` after `b4-patch-prior-manifest`
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout` (cwd: framework, timeout: 300s)
    - judgment: MUST switch to the PM role (read agents/product-manager/SKILL.md). For EACH FEATURE_ID in
BUILD_SCOPE being closed, execute the feature G8 PM CLOSEOUT CHECKLIST: write {RUN_FOLDER}/pm-closeout.md;
finalize that feature's manifest (status=approved, feature_state, feature_path_at_closeout); run
patch-prior-manifest.py (idempotent — patches all prior approved manifests for the feature to
superseded); write {FEATURE_INDEX_ROOT}/latest-run.json ONLY after the patch script exits 0; update
STATUS/REGISTRY/ROADMAP/BLUEPRINT + KG mappings; move the feature folder to archive/ when Done/Completed.
- **B4.5 — Build-level approval gate** (role: product-manager; artifacts: none)
    - MANUAL checkpoint `build-approval`: User reviews the aggregated per-feature closeouts (every pm-closeout.md from B4) plus the B3 lifecycle validator results. On refusal: HALT — do not proceed to B5; any further changes restart at B1 for the affected features. (requires: every pm-closeout.md from B4, B3 lifecycle validator results in lifecycle-gates.log; produces: build-approved (recorded as the B4.5 row in gate-decisions.md))
- **B5 — Build closeout and exit validation sweep** (role: product-manager; artifacts: README.md, action-context.md, artifact-trace.md, gate-decisions.md)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT}` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/` (cwd: framework, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --regenerate-symbols --check-symbols --regenerate-decisions --check-decisions` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - run `python3 agents/scripts/validate_templates.py` (cwd: framework, timeout: 300s)
    - judgment: Update {BUILD_RUN_FOLDER}/README.md, action-context.md, artifact-trace.md, and gate-decisions.md
with the build-level summary; gate-decisions.md carries one row per feature pointing to that
feature's pm-closeout.md. Then run the exit validation sweep IN ORDER, all exit 0: per-feature
closeout validation for each FEATURE_ID (the first op's per-feature form), then the build-once
tracker / story-index / KG symbols+decisions / coverage / drift / templates checks. --write-coverage-report
is path-sensitive and safe here because every feature's archive move already completed at B4.

Severity gate profile: `none` (compute allowed outcomes with `agents/scripts/gate_policy.py`; coverage floor is 80%).

Ownership (strict):
- **build-orchestrator** owns: BUILD_RUN_FOLDER base run files, sequencing across features, lifecycle-gates.log aggregation
- **product-manager** owns: pm-closeout.md, manifest finalize (status approved), prior-manifest supersession, latest-run.json, signoff-ledger.md, STATUS/REGISTRY/ROADMAP/BLUEPRINT + KG mappings, build-level archive decisions + REGISTRY.md updates

Forbidden:
- Generate BUILD_RUN_ID or any feature RUN_ID with uuid4.
- Close a feature without a canonical evidence package at {FEATURE_INDEX_ROOT}/latest-run.json with status approved.
- Call validate-trackers.py before per-feature G6 candidate validation has passed for every feature being closed.
- Write per-feature role reports (g0-*, test-*, code-review-*, etc.) into BUILD_RUN_FOLDER instead of the feature run folder.
- Use the build run folder as a substitute for any feature's evidence package.
- Place a feature evidence package under BUILD_RUN_FOLDER.
- Mark a feature Archived in REGISTRY.md while its latest-run.json is missing or non-approved.
- Pass --evidence-effective-date earlier than the framework default.

Stop conditions:
- Any feature in BUILD_SCOPE fails G6 candidate validation and the cause is not addressable in this build.
- Tracker validation fails and cannot be auto-repaired.
- A feature's prior approved manifest cannot be patched to superseded (write fails or schema rejects).
- Two approved manifests are detected for the same feature after B4 (two_approved_runs_without_supersession_fails).
- INSUFFICIENT_CONTEXT occurs for any feature in BUILD_SCOPE.
- validate.py or --check-drift fails after one repair cycle.

Conflict resolution:
- feature evidence package present but STATUS.md missing current signoff rows -> halt; the feature is not closeout-ready.
- REGISTRY.md says Archived but feature evidence package missing or non-approved -> halt; fix REGISTRY.md, do not backfill pre-contract evidence.
- per-feature manifest disagrees with STATUS.md current verdicts -> fix the feature (re-run its G5) before continuing the build.
- build re-closing a feature with an existing approved package -> mint a NEW RUN_ID, set RERUN_OF appropriately, and run patch-prior-manifest.py before writing the new latest-run.json at B4.

Note (build_loop): build is feature-in-a-loop at the ORCHESTRATION layer: it does not re-derive feature's G0-G8 gates —
it invokes the feature action per FEATURE_ID (B1 -> feature G0-G6; B4 -> feature G8) and wraps them
with build-level scope lock (B0), aggregate lifecycle validation (B3), a holistic user approval (B4.5),
and a build closeout + exit sweep (B5). Per-feature ownership of role reports inherits from the feature
action; this spec owns only the build-level base run files and cross-feature sequencing.

Note (non_feature_build): A build with an empty BUILD_SCOPE still produces the base run package at {BUILD_RUN_FOLDER} (the six
base files) per §8. It does NOT produce a feature evidence package and does NOT call
validate-feature-evidence.py (no feature scope). Tracker validation still runs as a sanity check.

Note (preconditions): {BUILD_RUN_FOLDER} created with base run files present; every feature in BUILD_SCOPE has either an
existing approved package referenced by {FEATURE_INDEX_ROOT}/latest-run.json or a planned package to be
produced during this build; `python3 {PRODUCT_ROOT}/scripts/kg/validate.py` exits 0 at start.

Note (session_setup): Echo the resolved absolute {PRODUCT_ROOT} on the first turn before any command. Generate BUILD_RUN_ID
once at session start in contract format (an ISO YYYY-MM-DD date plus a secrets.token_hex(4) suffix);
never uuid4, never regenerate it after start. Create {BUILD_RUN_FOLDER} and initialize the base run
files from templates: README.md,
action-context.md, artifact-trace.md, gate-decisions.md, an empty commands.log (JSONL), and an empty
lifecycle-gates.log. The build run folder is a base run package, NOT a feature evidence package — every
feature closed in this build keeps its own package at that feature's {RUN_FOLDER}, produced by the
delegated feature action's own session setup (which mints each per-feature {RUN_ID}).

Note (telemetry): Append every shell command to {BUILD_RUN_FOLDER}/commands.log as JSON Lines per the §13 schema
(schema_version, timestamp with timezone, cwd, command, exit_code, artifacts[], redactions[]). Append
every lifecycle validator command (tracker, story-index, KG, validate_templates, and each per-feature
validate-feature-evidence call) to {BUILD_RUN_FOLDER}/lifecycle-gates.log.

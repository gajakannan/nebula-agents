ACTION: agents/actions/feature.md
CONTRACT: Feature Evidence Contract in CONSUMER-CONTRACT.md (effective 2026-05-19)

REQUIRED INPUTS (operator must set before SESSION_SETUP):
  FEATURE_ID:           {F####}

OPTIONAL INPUTS (defaults apply when omitted):
  MODE:                 {clean | drift-reconcile}             # default: clean
  SLICE_ORDER_SOURCE:   {assembly-plan | override}            # default: assembly-plan
  SLICE_ORDER:          # only when SLICE_ORDER_SOURCE=override; brackets = parallel within entry
                        #   - {F####-S####}
                        #   - [{F####-S####}, {F####-S####}]
  PRODUCT_ROOT:         absolute product repo root            # default: sister-repo per agents/docs/AGENT-USE.md

AUTO-RESOLVED (do not set; SESSION_SETUP and the orchestrator compute these):
  FEATURE_SLUG          = kebab-case slug for {FEATURE_ID} from REGISTRY.md
  FEATURE_PATH          = {PRODUCT_ROOT}/planning-mds/features/{FEATURE_ID}-{FEATURE_SLUG}
  ARCHIVE_FEATURE_PATH  = {PRODUCT_ROOT}/planning-mds/features/archive/{FEATURE_ID}-{FEATURE_SLUG}
  FEATURE_INDEX_ROOT    = {PRODUCT_ROOT}/planning-mds/operations/evidence/features/{FEATURE_ID}-{FEATURE_SLUG}
  RUN_ID                = YYYY-MM-DD-{secrets.token_hex(4)} generated at SESSION_SETUP (e.g. 2026-05-19-5ab6f922)
  RUN_FOLDER            = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}
  RUN_ID_PRIOR          = prior approved run_id read from {FEATURE_INDEX_ROOT}/latest-run.json (null if absent)
  RERUN_OF              = null | {RUN_ID_PRIOR} when this run regenerates evidence only

SESSION_SETUP:
- Resolve {PRODUCT_ROOT} per agents/docs/AGENT-USE.md → Session Setup
- Echo the resolved absolute {PRODUCT_ROOT} path on the first turn before any shell command
- Generate {RUN_ID} once at session start using the contract format:
    date  = local date in ISO YYYY-MM-DD
    suffix = `python3 -c "import secrets; print(secrets.token_hex(4))"`
    RUN_ID = {date}-{suffix}                  # example: 2026-05-19-5ab6f922
  DO NOT use uuid4. DO NOT regenerate {RUN_ID} after the session starts.
- Create the feature index root and canonical run folder:
    mkdir -p {FEATURE_INDEX_ROOT}
    mkdir -p {RUN_FOLDER}/artifacts/{coverage,diffs,test-results,security,screenshots}
- Initialize {RUN_FOLDER}/evidence-manifest.json from agents/templates/evidence-manifest-template.json with:
    schema_version=1, feature_id={FEATURE_ID}, feature_slug={FEATURE_SLUG}, run_id={RUN_ID},
    status="draft", recorded_on={today}, contract_effective_date=2026-05-25,
    feature_path_at_run_start={FEATURE_PATH}, feature_path_at_closeout=null,
    feature_state="In Progress", rerun_of=null,
    changed_paths=[], scm={base_ref, head_ref, diff_artifact:"artifacts/diffs/changed-files.txt"},
    runtime_bearing/deployment_config_changed/frontend_in_scope/security_sensitive_scope = false (revise as scope is discovered),
    required_roles=[], gate_results={}, files={...skeleton...}, role_results={...skeleton...},
    omissions=[], waivers={}, global_evidence_refs={}
- Create {RUN_FOLDER}/README.md, action-context.md, artifact-trace.md, gate-decisions.md from templates
- Touch {RUN_FOLDER}/commands.log and {RUN_FOLDER}/lifecycle-gates.log (empty JSONL/log)
- Capture prior approved {RUN_ID_PRIOR} if {FEATURE_INDEX_ROOT}/latest-run.json exists (for G8 supersession patch)
- Concurrent-run check: inspect only `evidence-manifest.json` files under `{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/*/` for any run other than `{RUN_FOLDER}` whose manifest has `feature_id={FEATURE_ID}` and carries status="draft" or status="in-progress". If one exists, HALT and reconcile externally before proceeding; the Feature Evidence Contract assumes serial feature actions per feature. Acceptable states for prior runs: status="approved" with prior-run supersession handled at G8, status="superseded", or no prior runs at all.
- All paths and commands below assume the above resolution and run folder

TIER DEFAULTS (start_tier, max_auto_tier; selected by MODE):
  clean:            1, 2
  drift-reconcile:  3, 4

PRIMARY_SPEC: {FEATURE_PATH}/feature-assembly-plan.md

PRECONDITIONS:
- Plan action signed off for {FEATURE_ID} (feature stories and architecture available)
- PRIMARY_SPEC (feature-assembly-plan.md) is NOT a precondition — it is authored in G0 Step 0 of this run (per feature.md Step 0 / plan.md): absent on a clean first run, present on drift-reconcile/rerun
- Required runtime containers healthy (per feature.md "Runtime Preflight & Failure Triage")
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py` exits 0 at start
- {RUN_FOLDER} created and initial evidence-manifest.json present
- {RUN_FOLDER} is empty other than skeleton files (no stale artifacts from a prior session)

CONTEXT LOADING ORDER (navigate; do not eager-load):
1. agents/ROUTER.md
2. agents/agent-map.yaml
3. agents/docs/AGENT-USE.md
4. agents/actions/feature.md
5. `python3 {PRODUCT_ROOT}/scripts/kg/lookup.py {FEATURE_ID} --tier {start_tier} --run-id {RUN_ID} --telemetry-file {PRODUCT_ROOT}/.kg-state/telemetry.jsonl`
   — FIRST-PASS scope resolver; raw artifacts win on conflict.
6. {FEATURE_PATH}/**   (PRIMARY_SPEC is required reading once it exists; on a clean first run it is authored in G0 Step 0 before slice work)

ON-DEMAND (only if linked by lookup, required by current gate, or required by drift repair):
- {PRODUCT_ROOT}/planning-mds/knowledge-graph/solution-ontology.yaml
- {PRODUCT_ROOT}/planning-mds/api/<openapi-spec>.yaml
- {PRODUCT_ROOT}/planning-mds/security/authorization-matrix.md
- {PRODUCT_ROOT}/planning-mds/security/policies/policy.csv
- {PRODUCT_ROOT}/planning-mds/knowledge-graph/*.yaml beyond what lookup output already covers
- agents/<role>/references/** — only with a ROUTER.md row match

FORBIDDEN:
- Generating {RUN_ID} with uuid4 or any non-contract format
- Writing or consuming `current-run.json` for any reason
- Writing `latest-run.json` before G8 final validation passes
- Leaving a prior approved manifest at `status: approved` after writing a new approval (must be patched to `superseded`)
- Skipping per-gate `validate-feature-evidence.py --stage` calls
- Writing terminal-feature role reports into {FEATURE_PATH} instead of {RUN_FOLDER}
- Citing the global frontend evidence lane (frontend-quality/ or frontend-ux/) as a substitute for a feature-level role report (rule frontend_global_substituted_for_feature_report_fails); global lanes may be LINKED from feature evidence but never replace the feature's test-execution-report.md or other role reports
- Hand-enumerating schema/ADR/contract files when lookup output is available
- Treating lookup/KG mappings as authoritative over raw artifacts
- Editing code without prior `hint.py <path>`
- Editing shared semantics without prior `blast.py <node>`
- Continuing after runtime-blocked failure without re-running preflight
- Skipping any gate (G0–G8)
- Declaring Done without PM agent switch at G8
- Scope widening outside {FEATURE_ID}
- Climbing past max_auto_tier without a workstate.py escalate event
- Passing `--evidence-effective-date` earlier than the framework default

REQUIRED TOOL INVOCATIONS:
- `python3 {PRODUCT_ROOT}/scripts/kg/workstate.py --state-file {PRODUCT_ROOT}/.kg-state/{FEATURE_ID}-feature.yaml init --role feature --scope {FEATURE_ID} --run-id {RUN_ID} --mode {MODE}`
- `workstate.py decision --topic <slug>` after each gate pass
- `workstate.py touch <path>` after significant file changes
- `workstate.py dump --compact` after any compaction event
- `workstate.py escalate <reason>` on INSUFFICIENT_CONTEXT
- `hint.py <path> --run-id {RUN_ID} --telemetry-file {PRODUCT_ROOT}/.kg-state/telemetry.jsonl` before any Grep/Glob on code
- `blast.py <node-id> --run-id {RUN_ID} --telemetry-file {PRODUCT_ROOT}/.kg-state/telemetry.jsonl` before shared-semantics edits
- `cochange.py --coverage-gaps` once per feature in clean mode (at session start); at start + before closeout in drift-reconcile; NOT per slice
- Stage validation for every feature evidence gate from G0 through G6 after the gate's artifact is written:
  `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage {GATE}` (must exit 0; warnings allowed)
- Every shell command must be appended as a JSONL line to {RUN_FOLDER}/commands.log per §13 schema (schema_version, timestamp with timezone, cwd, command, exit_code, artifacts[], redactions[])

OWNERSHIP:
- product-manager owns: STATUS.md closeout, trackers, archive moves, feature-mappings.yaml path/status updates, pm-closeout.md, evidence-manifest.json finalize (status: approved), prior-manifest supersession patch, latest-run.json write, signoff-ledger.md
- architect owns: feature-assembly-plan.md, canonical-nodes.yaml, solution-ontology.yaml, ADRs, API contracts, schemas, authorization, g0-assembly-plan-validation.md
- quality-engineer owns: test-plan.md, test-execution-report.md, coverage-report.md (and any waiver entry inside it)
- code-reviewer owns: code-review-report.md
- security-reviewer owns: security-review-report.md (when required by security_sensitive_scope or STATUS matrix)
- devops owns: g1-runtime-preflight.md (when runtime_bearing), deployability-check.md
- feature orchestrator owns: g2-self-review.md, feature-action-execution.md, artifact-trace.md, gate-decisions.md, scope booleans in manifest, changed_paths[]
- other roles: flag drift; do not redefine canonical shared semantics

SLICE EXECUTION:
- SLICE_ORDER_SOURCE=assembly-plan: read sequence from PRIMARY_SPEC; do not reorder
- SLICE_ORDER_SOURCE=override: follow SLICE_ORDER verbatim; brackets = parallel within that entry only; no cross-slice parallelism

MODE BEHAVIOR:
- clean: assume alignment; drift discovered blocks approval until reconciled
- drift-reconcile: repair code/contract/policy/KG divergence in the same change set; silent reconciliation FORBIDDEN

GATES (sequential, all mandatory; manifest status transitions: draft@G0 → in-progress@G1..G7 → approved@G8 → superseded later):

G0   ARCHITECT ASSEMBLY PLAN VALIDATION — and authoring on clean first run
     - Step 0 (author): if PRIMARY_SPEC absent, Architect authors {FEATURE_PATH}/feature-assembly-plan.md from agents/templates/feature-assembly-plan-template.md using feature stories, BLUEPRINT.md, SOLUTION-PATTERNS.md, API contracts (per feature.md Step 0). On drift-reconcile/rerun: reconcile the existing plan, do not overwrite; log via workstate.py decision --topic plan-story-reconcile
     - Step 0.5 (validate): scope split, agent dependencies, integration checkpoints, artifact ownership; initialize Required Signoff Roles matrix in {FEATURE_PATH}/STATUS.md
     - Produce {RUN_FOLDER}/g0-assembly-plan-validation.md (Result: PASS|PASS WITH RECOMMENDATIONS|FAIL)
     - Update manifest gate_results.assembly_plan_validation, status="draft" (initial) then "in-progress" after G0 pass
     - `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G0` exit 0

G1   RUNTIME PREFLIGHT
     - If runtime_bearing=true: produce {RUN_FOLDER}/g1-runtime-preflight.md with command evidence; else record manifest omission per §10
     - `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G1` exit 0

G2   SELF-REVIEW + QE + DEPLOYABILITY (per role, with evidence paths)
     - Reconcile manifest conditional booleans against discovered scope BEFORE running G2 stage validation:
         * frontend_in_scope = true if any changed_paths[] entry matches experience/** or other frontend globs (§7)
         * runtime_bearing = true if any entry matches engine/** runtime, tests, or AI runtime globs
         * deployment_config_changed = true if any entry matches Dockerfile, docker-compose, .github/workflows, ci/, env/config globs, or migrations
         * security_sensitive_scope = true if any entry matches auth/identity/permissions/security/secrets globs
       Any flip from false→true also forces the corresponding required role and artifact per §7; update required_roles[] and role_results accordingly. Booleans that change after G2 also force re-running --stage G2.
     - {RUN_FOLDER}/g2-self-review.md
     - {RUN_FOLDER}/test-plan.md, test-execution-report.md, coverage-report.md (report always exists; waiver allowed inside report when coverage cannot be produced)
     - {RUN_FOLDER}/deployability-check.md (always required; booleans must match manifest)
     - Update manifest gate_results.self_review and role_results.Quality Engineer / DevOps
     - `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G2` exit 0

G3   CODE + SECURITY REVIEW (parallel)
     - {RUN_FOLDER}/code-review-report.md (Result: APPROVED|APPROVED WITH RECOMMENDATIONS|REQUEST CHANGES|REJECTED)
     - {RUN_FOLDER}/security-review-report.md when security_sensitive_scope=true or Security required in STATUS
     - `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G3` exit 0

G4   APPROVAL — critical=0; high requires explicit mitigation token recorded in gate-decisions.md
     - After the approval decision is recorded, `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G4` exit 0

G5 SIGNOFF
     - Every Required=Yes role: verdict={PASS|APPROVED}(|WITH RECOMMENDATIONS), reviewer, ISO date, evidence path under {RUN_FOLDER}/**
     - STATUS.md story rows updated (append-only); Story column values match `F####-S####` and feature's local story breakdown
     - {RUN_FOLDER}/signoff-ledger.md mirrors current STATUS rows
     - For any verdict ending in WITH RECOMMENDATIONS, the underlying role report must satisfy ALL 5 §15 closeout-passing conditions (else the verdict is blocking, not passing):
         1. each recommendation marked non-blocking or deferred (rule recommendation_ambiguous_fails)
         2. each recommendation has severity (rule recommendation_missing_severity_fails)
         3. each recommendation has owner and follow-up disposition (rule recommendation_missing_owner_fails)
         4. PM acceptance recorded in pm-closeout.md (and optionally signoff-ledger.md) — landed at G8, but the role report must already name what PM is being asked to accept
         5. no blocking findings hidden as recommendations (rule blocking_language_with_pass_fails) — high/critical or blocking language with a passing verdict fails unless explicitly mitigated
     - `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G5` exit 0

G6 CANDIDATE EVIDENCE VALIDATION (no PM closeout artifacts yet)
     - {RUN_FOLDER}/feature-action-execution.md present (gate timeline)
     - Manifest is a pre-closeout candidate (pm_closeout, tracker_sync, latest-run.json all pending)
     - `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G6` exit 0
     - THEN: `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID}` exit 0
       (validate-trackers.py internally calls validate-feature-evidence.py --stage G6 per §22 integration)
     - Append every lifecycle validator command (tracker, story-index, KG validators, validate_templates) to {RUN_FOLDER}/lifecycle-gates.log

G7 ARCHITECT KG RECONCILIATION (Architect agent role switch is mandatory; runs after G6, before G8 closeout)
     - MUST read agents/architect/SKILL.md before executing (explicit role switch)
     - Reconcile the SEMANTIC graph against the as-built source by AUTHORING SHARDS: add/update kg-source/bindings/** (directory-glob, not file-by-file; confirm existing-glob coverage) and kg-source/nodes/** for new capabilities/shared semantics (logical F####/ doc refs only); diff against the G0 "Knowledge-Graph Binding Plan" baseline
     - `python3 {PRODUCT_ROOT}/scripts/kg/compile.py` MUST regenerate the projection trio + trackers from the shards; never hand-edit knowledge-graph/*.yaml
     - Bind CODE paths only (stable across the G8 archive move); do NOT run `--write-coverage-report` here (path-sensitive; deferred to G8 after the move)
     - `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --regenerate-symbols --check-symbols --regenerate-decisions --check-decisions` exit 0 (refreshes symbol-index.yaml, unbound-but-referenced.yaml, and decisions-index.yaml; cannot be skipped)
     - `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` exit 0
     - Write {RUN_FOLDER}/kg-reconciliation.md (binding delta, new/affirmed canonical nodes, green generated-layer + drift results)
     - Manifest stays status="in-progress"; record gate_results.kg_reconciliation

G8 PM CLOSEOUT (PM agent role switch is mandatory)
     - MUST read agents/product-manager/SKILL.md before executing (explicit role switch)
     - VERIFY (do not re-author) the G7 semantic graph: kg-reconciliation.md present + its symbol/drift checks green. A binding gap found here routes back to the Architect for a G7 delta pass, not a closeout edit
     - Write {RUN_FOLDER}/pm-closeout.md (Result: APPROVED|APPROVED WITH RECOMMENDATIONS|REJECTED)
     - Finalize {RUN_FOLDER}/evidence-manifest.json: status="approved", feature_state in {Done|Completed|Archived}, feature_path_at_closeout resolved, all gate_results present (incl. kg_reconciliation, pm_closeout, tracker_sync)
     - Move the feature folder to features/archive/ and edit the feature shard kg-source/features/F####.yaml path:/status: (lifecycle-coupled, PM-owned), then run `python3 {PRODUCT_ROOT}/scripts/kg/compile.py` — it regenerates feature-mappings.yaml + trackers; archiving is one shard path: edit with no repoint anywhere
     - AFTER the archive move, regenerate the path-sensitive coverage layer: `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report` (running it before the move re-stales it), then `--check-drift` exit 0
     - Run `python3 agents/product-manager/scripts/patch-prior-manifest.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --new-run-id {RUN_ID}`; it is idempotent and patches all prior approved manifests for the same feature to `status="superseded"` (rule two_approved_runs_without_supersession_fails)
     - Write {FEATURE_INDEX_ROOT}/latest-run.json (schema per §12) pointing to {RUN_FOLDER} only after patch-prior-manifest.py exits 0
     - Final validation: `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout` exit 0 (no --run-id; resolves via latest-run.json)
     - Scoped tracker validation: `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID}` exit 0

Checklist for G6 (Candidate Evidence Validation):
- Confirm all G0–G5 evidence present and verdicts passing
- feature-action-execution.md complete with gate-by-gate timeline
- Manifest status="in-progress", gate_results through signoff present, pm_closeout/tracker_sync absent or required:false
- changed_paths[] populated; conditional booleans cross-check against §7 path-class globs (rule scope_boolean_false_with_changed_paths_fails)
- scm.diff_artifact resolves and lists changed files (or empty only if RERUN_OF set)
- All non-required role/gate artifacts that are absent appear in manifest omissions[] (do not double-count when role_results.<role>.required=false; see §11)

Checklist for G8 (PM Closeout) — run after G6 + tracker sync:
- Read agents/product-manager/SKILL.md (explicit role switch)
- Update {FEATURE_PATH}/STATUS.md: final overall status, deferred follow-ups, mitigation notes, signoff provenance (append-only; no mutation)
- Update {PRODUCT_ROOT}/planning-mds/features/REGISTRY.md: status/path transitions (include archive move; set Archived Date when archiving)
- Update {PRODUCT_ROOT}/planning-mds/features/ROADMAP.md: Now/Next/Later/Completed placement
- Update {PRODUCT_ROOT}/planning-mds/BLUEPRINT.md: feature/story status labels and links
- IF overall_status in {Done|Completed}: move {FEATURE_PATH} to {ARCHIVE_FEATURE_PATH}/ and fix impacted links
- Update {PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml: feature path, status, story status
- Do NOT hand-edit the generated knowledge-graph/*.yaml or tracker tables in closeout — the Architect's G7 shard pass + compile.py must already have produced them; route any gap back to G7 (author shards, recompile)
- Capture orphaned stories and deferred follow-ups in pm-closeout.md
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report` (mandatory after the G8 archive move)
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` MUST exit 0
- Write pm-closeout.md (Final Story Status, Archive Decision, Deferred Follow-ups, Recommendation Acceptances, Tracker Updates, Validator Results)
- Finalize evidence-manifest.json (status="approved")
- Run `python3 agents/product-manager/scripts/patch-prior-manifest.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --new-run-id {RUN_ID}`; it is idempotent and patches all prior approved manifests for the same feature to `status="superseded"`
- Write {FEATURE_INDEX_ROOT}/latest-run.json (schema_version=1, feature_id, run_id={RUN_ID}, run_path, manifest_path, status="approved", approved_on={today}) only after patch-prior-manifest.py exits 0
- Run final `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout` and confirm exit 0
- Run scoped `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID}` and confirm exit 0

VALIDATOR-DEFECT FALLBACK (only if a validator defect blocks closeout):
- Fix the validator and re-run is preferred
- Mid-stage discovery (G0..G6): do NOT create the waiver entry yet. Log the defect as an open follow-up in the run's README.md "Open Follow-ups" section with the defect description and affected rule IDs; continue to the next gate. If the defect is fixed before G8, remove the follow-up. If not fixed by G8, convert the follow-up to the waiver entry below.
- G8 discovery or unresolved mid-stage follow-up: record `waivers.validator_defect` in evidence-manifest.json with defect_description, affected_rule_ids[], approved_by, approved_on, follow_up_owner, follow_up_target_date (ISO date by which the defect must be fixed)
- Mirror the waiver in pm-closeout.md under a "Validator Defects" subsection
- DO NOT bypass via `--evidence-effective-date` (rejected for earlier-than-default; warns when in use)

STOP CONDITIONS:
- runtime preflight fails and cannot be restored
- critical code or security finding persists after one review cycle
- required signoff missing reviewer/date/evidence
- canonical node edit attempted outside Architect role
- scope drift outside {FEATURE_ID}
- INSUFFICIENT_CONTEXT (see plan template); escalate and open raw artifacts
- validate.py or --check-drift fails and cannot be auto-repaired
- `validate-feature-evidence.py` at any stage exits non-zero and the cause is not addressable in this run
- Two approved manifests detected for the same feature without supersession (two_approved_runs_without_supersession_fails)

EXIT VALIDATION (run in order; all exit 0; record evidence paths under {PRODUCT_ROOT}/planning-mds/operations/evidence/**):
- Applicable backend/frontend/test commands for changed surfaces (inside runtime containers; evidence paths recorded)
- `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G6`
- `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID}` (scoped tracker validation; calls feature-evidence at --stage G6 per §22)
- After §17 step 4 (`patch-prior-manifest.py` then `latest-run.json`): `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout`
- `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/` (if stories changed)
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --regenerate-symbols --check-symbols --regenerate-decisions --check-decisions`
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report` (mandatory after the G8 archive move)
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift`
- `python3 agents/scripts/validate_templates.py`
- `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout --json` → capture to {RUN_FOLDER}/artifacts/feature-evidence-validation.json for post-hoc analysis

CONFLICT RESOLUTION:
- raw artifact vs KG mapping → raw wins; repair KG in same change set
- feature-assembly-plan vs story text → plan wins; log reconciliation via workstate.py decision --topic plan-story-reconcile
- code vs contract/policy/KG → reconcile to contract; never silently redefine canonical semantics
- shared-semantics change detected → halt and route to Architect
- STATUS.md Story value not in feature's local story breakdown → fix STATUS.md; STORY-INDEX.md is cross-check only (rule status_story_value_unknown_story_fails / story_index_disagrees_with_feature_breakdown_fails)
- manifest conditional boolean false but changed_paths contains a forced path class → set boolean true and add the required role/artifact (rule scope_boolean_false_with_changed_paths_fails)

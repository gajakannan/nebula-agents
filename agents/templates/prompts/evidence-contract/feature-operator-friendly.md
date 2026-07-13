This prompt encodes the Feature Evidence Contract in `CONSUMER-CONTRACT.md` (effective `2026-05-19`).

REQUIRED INPUTS (you must set):
- `FEATURE_ID={F0038}`

OPTIONAL INPUTS (defaults apply when omitted):
- `MODE={clean | drift-reconcile}` — default: `clean`
- `SLICE_ORDER_SOURCE={assembly-plan | override}` — default: `assembly-plan`
- `SLICE_ORDER=` — required only when `SLICE_ORDER_SOURCE=override`; one entry per slice, brackets denote parallel execution within that entry
- `PRODUCT_ROOT=` — default: sister-repo resolved per `agents/docs/AGENT-USE.md` → Session Setup; override only for non-standard layouts

AUTO-RESOLVED (do not set; SESSION_SETUP and the orchestrator compute these):
- `FEATURE_SLUG` — kebab-case slug for `{FEATURE_ID}` from `REGISTRY.md`
- `FEATURE_PATH` — `{PRODUCT_ROOT}/planning-mds/features/{FEATURE_ID}-{FEATURE_SLUG}`
- `ARCHIVE_FEATURE_PATH` — `{PRODUCT_ROOT}/planning-mds/features/archive/{FEATURE_ID}-{FEATURE_SLUG}`
- `FEATURE_INDEX_ROOT` — `{PRODUCT_ROOT}/planning-mds/operations/evidence/features/{FEATURE_ID}-{FEATURE_SLUG}`
- `RUN_ID` — `YYYY-MM-DD-{secrets.token_hex(4)}` generated once at session start (e.g. `2026-05-19-5ab6f922`)
- `RUN_FOLDER` — `{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}`
- `RUN_ID_PRIOR` — prior approved `run_id` read from `{FEATURE_INDEX_ROOT}/latest-run.json` (null if absent)
- `RERUN_OF` — null, or `{RUN_ID_PRIOR}` when this run regenerates evidence only

Echo the resolved absolute `{PRODUCT_ROOT}` path on your first turn before any shell command; every command below assumes that resolution.

Generate `{RUN_ID}` once at session start using the contract format `YYYY-MM-DD-[a-z0-9]{8}` — the date is the local date and the 8-character suffix comes from cryptographic randomness, e.g. `python3 -c "import secrets; print(secrets.token_hex(4))"`. Do not use `uuid4`. Do not regenerate `{RUN_ID}` after the session starts. Example: `2026-05-19-5ab6f922`.

Set up the evidence package at session start using `RUN_FOLDER` as the canonical run location and `FEATURE_INDEX_ROOT` only for feature pointers. Create `FEATURE_INDEX_ROOT`, `RUN_FOLDER`, and `RUN_FOLDER/artifacts/{coverage,diffs,test-results,security,screenshots}`. Initialize `evidence-manifest.json` in `RUN_FOLDER` from the manifest template with `status: "draft"`, `rerun_of: null` (unless this is an evidence-only rerun), all required keys present, and skeleton `gate_results`/`role_results`/`files`. Create the base run files (`README.md`, `action-context.md`, `artifact-trace.md`, `gate-decisions.md`) from templates and touch empty `commands.log` and `lifecycle-gates.log`. If `{FEATURE_INDEX_ROOT}/latest-run.json` already exists, capture its `run_id` as `{RUN_ID_PRIOR}` so you can patch it to `superseded` at G8.

Concurrent-run check: inspect only `evidence-manifest.json` files under `{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/*/` for any run other than `{RUN_FOLDER}` whose manifest has `feature_id={FEATURE_ID}` and carries `status: "draft"` or `status: "in-progress"`. If one exists, HALT and reconcile externally before proceeding — the Feature Evidence Contract assumes serial feature actions per feature. Acceptable states for prior runs are `status: "approved"` (with prior-run supersession handled at G8), `status: "superseded"`, or no prior runs at all.

Run `agents/actions/feature.md` for `{FEATURE_ID}` at `{FEATURE_PATH}` with `MODE`, `SLICE_ORDER_SOURCE`, and `RUN_ID` set as above. If this run is an evidence-only rerun, set `RERUN_OF={RUN_ID_PRIOR}`; otherwise leave it null. If you use an override, keep `SLICE_ORDER` verbatim and only parallelize slices inside the same bracketed entry.

Use these tier defaults exactly:
- `clean: 1, 2`
- `drift-reconcile: 3, 4`

`PRIMARY_SPEC` is `{FEATURE_PATH}/feature-assembly-plan.md`. It is **not** a precondition — `feature-assembly-plan.md` is not a `plan` deliverable; it is authored in G0 Step 0 of this run (per `agents/actions/feature.md` Step 0 and `plan.md`). Start only when the plan action is already signed off (feature stories and architecture are available), the required runtime containers are healthy per `feature.md`, `python3 {PRODUCT_ROOT}/scripts/kg/validate.py` already exits 0, and `RUN_FOLDER` is initialized with an empty skeleton (no stale artifacts). On a clean first run `PRIMARY_SPEC` does not exist yet — G0 creates it; on a `drift-reconcile` or evidence-only rerun it already exists and G0 reconciles it.

Load context in this order and navigate instead of eager-loading:
1. `agents/ROUTER.md`
2. `agents/agent-map.yaml`
3. `agents/docs/AGENT-USE.md`
4. `agents/actions/feature.md`
5. `python3 {PRODUCT_ROOT}/scripts/kg/lookup.py {FEATURE_ID} --tier {start_tier} --run-id {RUN_ID} --telemetry-file {PRODUCT_ROOT}/.kg-state/telemetry.jsonl`
6. `{FEATURE_PATH}/**` — `PRIMARY_SPEC` is required reading once it exists; on a clean first run it is authored in G0 Step 0 before any slice work

Treat `lookup.py` as a FIRST-PASS scope resolver only. Raw artifacts win on conflict. Open these only when lookup links them, the current gate needs them, or drift repair requires them: `{PRODUCT_ROOT}/planning-mds/knowledge-graph/solution-ontology.yaml`, `{PRODUCT_ROOT}/planning-mds/api/<openapi-spec>.yaml`, `{PRODUCT_ROOT}/planning-mds/security/authorization-matrix.md`, `{PRODUCT_ROOT}/planning-mds/security/policies/policy.csv`, `{PRODUCT_ROOT}/planning-mds/knowledge-graph/*.yaml` beyond the already returned subset, and `agents/<role>/references/**` only with a `ROUTER.md` row match.

Use these commands and keep them verbatim:
- `python3 {PRODUCT_ROOT}/scripts/kg/workstate.py --state-file {PRODUCT_ROOT}/.kg-state/{FEATURE_ID}-feature.yaml init --role feature --scope {FEATURE_ID} --run-id {RUN_ID} --mode {MODE}`
- `workstate.py decision --topic <slug>` after each gate pass
- `workstate.py touch <path>` after significant file changes
- `workstate.py dump --compact` after any compaction event
- `workstate.py escalate <reason>` on INSUFFICIENT_CONTEXT
- `hint.py <path> --run-id {RUN_ID} --telemetry-file {PRODUCT_ROOT}/.kg-state/telemetry.jsonl` before any Grep/Glob on code
- `blast.py <node-id> --run-id {RUN_ID} --telemetry-file {PRODUCT_ROOT}/.kg-state/telemetry.jsonl` before shared-semantics edits
- `cochange.py --coverage-gaps` once per feature in clean mode (at session start); at start + before closeout in drift-reconcile; NOT per slice

For every feature evidence gate from `G0` through `G6`, after the gate's artifact is written, run stage validation against the new run folder: `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage {GATE}`. It must exit 0; warnings and informational notices are acceptable.

Append every shell command you run to `{RUN_FOLDER}/commands.log` with `python3 agents/scripts/append-command-log.py`, passing `--log`, `--product-root`, `--framework-root`, `--cwd`, `--command`, `--exit-code`, and repeatable `--artifact` values as needed. Artifact paths must be durable product-repo paths, usually under the run's `artifacts/` folder; scratch paths such as `/tmp/...` are not durable evidence artifacts. Do not leak secrets — the secret-pattern checks will fail the run.

Respect slice execution and mode behavior:
- `SLICE_ORDER_SOURCE=assembly-plan: read sequence from PRIMARY_SPEC; do not reorder`
- `SLICE_ORDER_SOURCE=override: follow SLICE_ORDER verbatim; brackets = parallel within that entry only; no cross-slice parallelism`
- `clean: assume alignment; drift discovered blocks approval until reconciled`
- `drift-reconcile: repair code/contract/policy/KG divergence in the same change set; silent reconciliation FORBIDDEN`

Keep ownership strict:
- `product-manager owns`: feature closeout, trackers, `STATUS.md` final state, archive moves, `feature-mappings.yaml` path/status updates, `pm-closeout.md`, evidence-manifest.json finalize (`status: approved`), prior-manifest supersession patch, `latest-run.json` write, `signoff-ledger.md`
- `architect owns`: `feature-assembly-plan.md`, ADRs, canonical shared semantics, API contracts, schemas, authorization artifacts, `g0-assembly-plan-validation.md`
- `quality-engineer owns`: `test-plan.md`, `test-execution-report.md`, `coverage-report.md` (and any waiver inside it)
- `code-reviewer owns`: `code-review-report.md`
- `security-reviewer owns`: `security-review-report.md` when `security_sensitive_scope=true` or Security required in `STATUS.md`
- `devops owns`: `g1-runtime-preflight.md` when `runtime_bearing=true`, `deployability-check.md`
- feature orchestrator owns: `g2-self-review.md`, `feature-action-execution.md`, `artifact-trace.md`, `gate-decisions.md`, manifest scope booleans, `changed_paths[]`
- implementation agents (backend, frontend, AI, QE, DevOps) edit only their own runtime layer + their feature-level role report under `{RUN_FOLDER}`; shared-semantics changes route back to architect, and other roles flag drift but do not silently redefine canonical shared semantics

Follow these gates exactly. Manifest `status` transitions: `draft` at G0, `in-progress` from G1 through G7 (candidate validation + architect KG reconciliation), `approved` only at G8 when `latest-run.json` is written, `superseded` later only when a newer approved run replaces this one.

- `G0 ARCHITECT ASSEMBLY PLAN AUTHORING + VALIDATION` — **Step 0 (author):** if `PRIMARY_SPEC` is absent, the Architect authors `{FEATURE_PATH}/feature-assembly-plan.md` from `agents/templates/feature-assembly-plan-template.md` using the feature stories, `BLUEPRINT.md`, `SOLUTION-PATTERNS.md`, and API contracts (per `feature.md` Step 0); on `drift-reconcile`/rerun, reconcile the existing plan instead of overwriting and log it via `workstate.py decision --topic plan-story-reconcile`. **Step 0.5 (validate):** check scope split, agent dependencies, integration checkpoints, and artifact ownership, and initialize the `Required Signoff Roles` matrix in `{FEATURE_PATH}/STATUS.md`. Then write `g0-assembly-plan-validation.md`; run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G0` exit 0; flip manifest `status` to `in-progress` after G0 passes
- `G1 RUNTIME PREFLIGHT` — write `g1-runtime-preflight.md` if `runtime_bearing=true`, else record the manifest omission; run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G1`
- `G2 SELF-REVIEW + QE + DEPLOYABILITY` — first, reconcile the manifest conditional booleans against discovered scope. Set `frontend_in_scope=true` if any `changed_paths[]` entry matches `experience/**` or other frontend globs (§7); `runtime_bearing=true` for `engine/**` runtime/tests/AI runtime globs; `deployment_config_changed=true` for Dockerfile, docker-compose, `.github/workflows`, `ci/`, env/config globs, or migrations; `security_sensitive_scope=true` for auth/identity/permissions/security/secrets globs. Any flip from false→true also forces the corresponding required role and artifact per §7. Then write `g2-self-review.md`, `test-plan.md`, `test-execution-report.md`, `coverage-report.md` (file must exist even when waived), and `deployability-check.md`; run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G2`. Booleans that change after G2 force re-running `--stage G2`.
- `G3 CODE + SECURITY REVIEW (parallel)` — write `code-review-report.md` and `security-review-report.md` when required; run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G3`
- `G4 APPROVAL` — critical=0; high requires explicit mitigation token in `gate-decisions.md`; after the approval decision is recorded, run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G4`
- `G5 SIGNOFF` — every Required=Yes role: verdict, reviewer, ISO date, evidence path under `{RUN_FOLDER}/**`; STATUS.md story values match `F####-S####` and the feature's local story breakdown; write `signoff-ledger.md`; run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G5`. Any `WITH RECOMMENDATIONS` verdict must satisfy all 5 §15 closeout-passing conditions in the underlying role report: each recommendation is marked non-blocking/deferred (`recommendation_ambiguous_fails`), has severity (`recommendation_missing_severity_fails`), has owner and follow-up disposition (`recommendation_missing_owner_fails`), names what PM is being asked to accept at G8, and contains no high/critical or blocking language with a passing verdict (`blocking_language_with_pass_fails`)
- `G6 CANDIDATE EVIDENCE VALIDATION` (no PM closeout yet) — write `feature-action-execution.md`; manifest is a pre-closeout candidate (no `pm_closeout`, no `tracker_sync`, no `latest-run.json` yet); run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G6`; then run `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID}` (it internally calls `validate-feature-evidence.py --stage G6`); append every lifecycle validator command (tracker, story-index, KG, validate_templates) to `lifecycle-gates.log`
- `G7 ARCHITECT KG RECONCILIATION` — MUST switch role: read `agents/architect/SKILL.md`; bind the as-built source into the SEMANTIC graph (`code-index.yaml` glob bindings + `canonical-nodes.yaml`) so the next feature's architect reads a correct graph at G0; CODE paths only (stable across the G8 archive move); write `kg-reconciliation.md`; symbol + drift validators exit 0 (see reconciliation checklist below)
- `G8 PM CLOSEOUT` — MUST switch role: read `agents/product-manager/SKILL.md` before executing (see closeout checklist below); VERIFY (not re-author) the G7 graph; finalize manifest, patch prior manifest, write `latest-run.json`, run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout` exit 0, then run scoped tracker validation with `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID}` exit 0

At `G6 CANDIDATE`, do all of this:
- Confirm all G0–G5 evidence is present and verdicts are passing
- `feature-action-execution.md` complete with a gate-by-gate timeline
- Manifest `status=in-progress`; `gate_results` through `signoff` present; `pm_closeout`/`tracker_sync` absent or `required=false`
- `changed_paths[]` populated; conditional booleans cross-check against §7 path-class globs (rule `scope_boolean_false_with_changed_paths_fails`)
- `scm.diff_artifact` resolves and lists changed files (empty only when `RERUN_OF` is set)
- Non-required role/gate artifacts that are absent appear in manifest `omissions[]` (do not double-count when `role_results.<role>.required=false`)

At `G7 ARCHITECT KG RECONCILIATION`, do all of this:
- `Read agents/architect/SKILL.md (explicit role switch)`
- `Diff the as-built source against the G0 "Knowledge-Graph Binding Plan" baseline to find the binding delta`
- `Author {PRODUCT_ROOT}/planning-mds/kg-source/bindings/** shards: directory-glob bindings for every new capability/shared-semantic source surface (e.g. experience/src/features/forms/**); confirm existing-glob coverage rather than duplicating file-by-file`
- `Author {PRODUCT_ROOT}/planning-mds/kg-source/nodes/** shards for new shared semantics (logical F####/ doc refs only), or state "none introduced; reuses existing"`
- `python3 {PRODUCT_ROOT}/scripts/kg/compile.py` MUST regenerate the projection trio + tracker regions from the shards; never hand-edit knowledge-graph/*.yaml
- `Do NOT run --write-coverage-report here (path-sensitive; deferred to G8 after the archive move)`
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --regenerate-symbols --check-symbols --regenerate-decisions --check-decisions MUST exit 0` (refreshes `symbol-index.yaml`, `unbound-but-referenced.yaml`, and `decisions-index.yaml`; symbols/decisions stay validate.py-driven; cannot be skipped)
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift MUST exit 0`
- Write `kg-reconciliation.md` (binding delta, new/affirmed canonical nodes, green generated-layer + drift results)
- Manifest stays `status=in-progress`; record `gate_results.kg_reconciliation`

At `G8 PM CLOSEOUT`, do all of this:
- `Read agents/product-manager/SKILL.md (explicit role switch)`
- `VERIFY (do not re-author) the G7 semantic graph: kg-reconciliation.md present + symbol/drift green. A binding gap found here routes back to the Architect for a G7 delta pass`
- `Update {FEATURE_PATH}/STATUS.md: final overall status, deferred follow-ups, mitigation notes, signoff provenance (append-only; no mutation)`
- `Update {PRODUCT_ROOT}/planning-mds/features/REGISTRY.md: status/path transitions (include archive move; set Archived Date when archiving)`
- `Update {PRODUCT_ROOT}/planning-mds/features/ROADMAP.md: Now/Next/Later/Completed placement`
- `Update {PRODUCT_ROOT}/planning-mds/BLUEPRINT.md: feature/story status labels and links`
- `IF overall_status in {Done|Completed}: move {FEATURE_PATH} to {ARCHIVE_FEATURE_PATH}/ and fix impacted links`
- `Edit the feature shard {PRODUCT_ROOT}/planning-mds/kg-source/features/F####.yaml` (`path:`/`status:`, lifecycle-coupled, PM-owned), then run `python3 {PRODUCT_ROOT}/scripts/kg/compile.py` — it regenerates feature-mappings.yaml + the REGISTRY/ROADMAP tracker regions. Archiving is one shard path: edit, no repoint anywhere
- `Do NOT hand-edit the generated knowledge-graph/*.yaml or tracker tables — author kg-source/ shards; the Architect's G7 shard pass + compile.py produce them (closeout only verifies green)`
- `Capture orphaned stories and deferred follow-ups in pm-closeout.md`
- `AFTER the archive move: python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report (mandatory; path-sensitive — binds the relocated feature-doc paths; running it before the move re-stales it)`
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift MUST exit 0 on the post-move graph`
- Write `pm-closeout.md` with `Final Story Status`, `Archive Decision`, `Deferred Follow-ups`, `Recommendation Acceptances`, `Tracker Updates`, `Validator Results`
- Finalize `evidence-manifest.json`: set `status=approved`, `feature_state` in `{Done|Completed|Archived}`, `feature_path_at_closeout` resolved, all `gate_results` present
- Run `python3 agents/product-manager/scripts/patch-prior-manifest.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --new-run-id {RUN_ID}`; it is idempotent and patches all prior approved manifests for the same feature to `status=superseded` (rule `two_approved_runs_without_supersession_fails`)
- Write `{FEATURE_INDEX_ROOT}/latest-run.json` per §12 schema pointing to `{RUN_FOLDER}` only after `patch-prior-manifest.py` exits 0
- Run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout` and confirm exit 0
- Run `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID}` and confirm exit 0

If a validator defect blocks closeout: prefer to fix the validator and re-run. For defects discovered mid-stage (G0..G6), do NOT create the waiver entry yet — log the defect as an open follow-up in the run's `README.md` "Open Follow-ups" section with the defect description and affected rule IDs and continue to the next gate; if the defect is fixed before G8, remove the follow-up. If the defect is unresolved at G8 (or first discovered at G8), record a `waivers.validator_defect` entry in `evidence-manifest.json` with `defect_description`, `affected_rule_ids[]`, `approved_by`, `approved_on`, `follow_up_owner`, and `follow_up_target_date`, and mirror it in `pm-closeout.md` under a `Validator Defects` subsection. Do not bypass with `--evidence-effective-date` — earlier-than-default values are rejected and any override warns.

Don't generate `{RUN_ID}` with `uuid4` or any non-contract format. Don't write or consume `current-run.json`. Don't write `latest-run.json` before G8 final validation passes. Don't leave a prior approved manifest at `status: approved` after writing a new approval. Don't skip per-gate `validate-feature-evidence.py --stage` calls. Don't write terminal-feature role reports into `{FEATURE_PATH}` instead of `{RUN_FOLDER}`. Don't cite the global frontend evidence lane (`frontend-quality/` or `frontend-ux/`) as a substitute for a feature-level role report (`frontend_global_substituted_for_feature_report_fails`) — global lanes may be LINKED from feature evidence but never replace the feature's `test-execution-report.md` or other role reports. Don't hand-enumerate schema, ADR, or contract files when lookup output is available. Don't treat lookup/KG mappings as authoritative over raw artifacts. Don't edit code without prior `hint.py <path>`. Don't edit shared semantics without prior `blast.py <node>`. Don't continue after a runtime-blocked failure without re-running preflight. Don't skip any gate from `G0` through `G8`. Don't declare Done without the PM switch at `G8`. Don't widen scope outside `{FEATURE_ID}`. Don't climb past `max_auto_tier` without a `workstate.py escalate` event. Don't pass `--evidence-effective-date` earlier than the framework default.

Stop immediately if runtime preflight cannot be restored, if a critical code or security finding persists after one review cycle, if required signoff is missing reviewer/date/evidence, if a canonical node edit is attempted outside Architect role, if scope drifts outside `{FEATURE_ID}`, if `validate.py` or `validate.py --check-drift` cannot be auto-repaired, if `validate-feature-evidence.py` at any stage exits non-zero and the cause is not addressable in this run, if two approved manifests are detected for the same feature without supersession, or if `INSUFFICIENT_CONTEXT` occurs. `INSUFFICIENT_CONTEXT` means the same thing as in the plan prompt: escalate, open the raw artifacts, and do not proceed with weak matches.

Close the run by executing these in order (evidence paths recorded under `{PRODUCT_ROOT}/planning-mds/operations/evidence/**`):
- `Applicable backend/frontend/test commands for changed surfaces (inside runtime containers; evidence paths recorded)`
- `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G6`
- `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID}` (scoped tracker validation; calls feature-evidence at --stage G6 per §22)
- After §17 step 4 (`patch-prior-manifest.py` then `latest-run.json`): `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout`
- `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/` (if stories changed)
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --regenerate-symbols --check-symbols --regenerate-decisions --check-decisions`
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report` (mandatory after the G8 archive move)
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift`
- `python3 agents/scripts/validate_templates.py`
- `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout --json` and capture the output to `{RUN_FOLDER}/artifacts/feature-evidence-validation.json` for post-hoc analysis

Resolve conflicts like this:
- `raw artifact vs KG mapping → raw wins; repair KG in same change set`
- `feature-assembly-plan vs story text → plan wins; log reconciliation via workstate.py decision --topic plan-story-reconcile`
- `code vs contract/policy/KG → reconcile to contract; never silently redefine canonical semantics`
- `shared-semantics change detected → halt and route to Architect`
- `STATUS.md Story value not in feature's local story breakdown → fix STATUS.md; STORY-INDEX.md is cross-check only (rules status_story_value_unknown_story_fails / story_index_disagrees_with_feature_breakdown_fails)`
- `manifest conditional boolean false but changed_paths contains a forced path class → set boolean true and add the required role/artifact (rule scope_boolean_false_with_changed_paths_fails)`

Before starting, resolve `{PRODUCT_ROOT}` per `agents/docs/AGENT-USE.md` → Session Setup and echo its absolute path on your first turn; every command below assumes that resolution.

Run `agents/actions/feature.md` for `{FEATURE_ID}` at `{PRODUCT_ROOT}/planning-mds/features/{F####-slug}` with `MODE={clean | drift-reconcile}`, `SLICE_ORDER_SOURCE={assembly-plan | override}`, and `RUN_ID={uuid4 generated at session start}`. If you use an override, keep `SLICE_ORDER` verbatim and only parallelize slices inside the same bracketed entry.

Use these tier defaults exactly:
- `clean: 1, 2`
- `drift-reconcile: 3, 4`

`PRIMARY_SPEC` is `{FEATURE_PATH}/feature-assembly-plan.md`. Start only when the plan action is already signed off, `PRIMARY_SPEC` exists, the required runtime containers are healthy per feature.md, and `python3 {PRODUCT_ROOT}/scripts/kg/validate.py` already exits 0.

Load context in this order and navigate instead of eager-loading:
1. `agents/ROUTER.md`
2. `agents/agent-map.yaml`
3. `agents/docs/AGENT-USE.md`
4. `agents/actions/feature.md`
5. `python3 {PRODUCT_ROOT}/scripts/kg/lookup.py {FEATURE_ID} --tier {start_tier} --run-id {RUN_ID} --telemetry-file {PRODUCT_ROOT}/.kg-state/telemetry.jsonl`
6. `{FEATURE_PATH}/**` with `PRIMARY_SPEC` treated as required reading

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

Respect slice execution and mode behavior:
- `SLICE_ORDER_SOURCE=assembly-plan: read sequence from PRIMARY_SPEC; do not reorder`
- `SLICE_ORDER_SOURCE=override: follow SLICE_ORDER verbatim; brackets = parallel within that entry only; no cross-slice parallelism`
- `clean: assume alignment; drift discovered blocks approval until reconciled`
- `drift-reconcile: repair code/contract/policy/KG divergence in the same change set; silent reconciliation FORBIDDEN`

Keep ownership strict:
- `product-manager owns` feature closeout, trackers, `STATUS.md` final state, archive moves, and `feature-mappings.yaml` path/status updates
- `architect owns` `feature-assembly-plan.md`, ADRs, canonical shared semantics, API contracts, schemas, and authorization artifacts
- implementation roles stay in their runtime layers plus shared feature evidence surfaces

Follow these gates exactly:
- `G0   ARCHITECT ASSEMBLY PLAN VALIDATION`
- `G1   RUNTIME PREFLIGHT`
- `G2   SELF-REVIEW (per role, with evidence paths)`
- `G3   CODE + SECURITY REVIEW (parallel)`
- `G4   APPROVAL — critical=0; high requires explicit mitigation token`
- `G4.5 SIGNOFF — every Required=Yes role: verdict=PASS, reviewer, date, evidence path under {PRODUCT_ROOT}/planning-mds/operations/evidence/**`
- `G4.6 PM CLOSEOUT — MUST switch role: read agents/product-manager/SKILL.md before executing (see closeout checklist below)`
- `G4.7 TRACKER SYNC — validate-trackers.py exit 0`

At `G4.6 PM CLOSEOUT`, do all of this:
- `Read agents/product-manager/SKILL.md (explicit role switch)`
- `Update {FEATURE_PATH}/STATUS.md: final overall status, deferred follow-ups, mitigation notes, signoff provenance (append-only; no mutation)`
- `Update {PRODUCT_ROOT}/planning-mds/features/REGISTRY.md: status/path transitions (include archive move)`
- `Update {PRODUCT_ROOT}/planning-mds/features/ROADMAP.md: Now/Next/Later/Completed placement`
- `Update {PRODUCT_ROOT}/planning-mds/BLUEPRINT.md: feature/story status labels and links`
- `IF overall_status == "Done": move {FEATURE_PATH} to {PRODUCT_ROOT}/planning-mds/features/archive/{F####-slug}/ and fix impacted links`
- `Update {PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml: feature path, status, story status`
- `Update {PRODUCT_ROOT}/planning-mds/knowledge-graph/code-index.yaml: bindings for every new source file introduced by this feature`
- `Update canonical-nodes.yaml ONLY if new shared semantics introduced (route to Architect if so)`
- `Capture orphaned stories and deferred follow-ups`
- `IF KG changed: python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report`
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift MUST exit 0`

Don’t hand-enumerate schema, ADR, or contract files when lookup output is available. Don’t treat lookup/KG mappings as authoritative over raw artifacts. Don’t edit code without prior `hint.py <path>`. Don’t edit shared semantics without prior `blast.py <node>`. Don’t continue after a runtime-blocked failure without re-running preflight. Don’t skip any gate from `G0` through `G4.7`. Don’t declare Done without the PM switch at `G4.6`. Don’t widen scope outside `{FEATURE_ID}`. Don’t climb past `max_auto_tier` without a `workstate.py escalate` event.

Stop immediately if runtime preflight cannot be restored, if a critical code or security finding persists after one review cycle, if required signoff is missing reviewer/date/evidence, if a canonical node edit is attempted outside Architect role, if scope drifts outside `{FEATURE_ID}`, if `validate.py` or `validate.py --check-drift` cannot be auto-repaired, or if `INSUFFICIENT_CONTEXT` occurs. `INSUFFICIENT_CONTEXT` means the same thing as in the plan prompt: escalate, open the raw artifacts, and do not proceed with weak matches.

Close the run by executing these in order:
- `Applicable backend/frontend/test commands for changed surfaces (inside runtime containers; evidence paths recorded)`
- `python3 agents/product-manager/scripts/validate-trackers.py`
- `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/   (if stories changed)`
- `IF KG changed: python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report`
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py`
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift`
- `python3 agents/scripts/validate_templates.py`

Resolve conflicts like this:
- `raw artifact vs KG mapping → raw wins; repair KG in same change set`
- `feature-assembly-plan vs story text → plan wins; log reconciliation via workstate.py decision --topic plan-story-reconcile`
- `code vs contract/policy/KG → reconcile to contract; never silently redefine canonical semantics`
- `shared-semantics change detected → halt and route to Architect`

Before starting, resolve `{PRODUCT_ROOT}` per `agents/docs/AGENT-USE.md` → Session Setup and echo its absolute path on your first turn; every command below assumes that resolution.

Run `agents/actions/plan.md` for `{FEATURE_ID}` at `{PRODUCT_ROOT}/planning-mds/features/{F####-slug}` in `{greenfield | refinement | drift-reconcile}` mode with `RUN_ID={uuid4 generated at session start}`.

Use these tier defaults exactly:
- `greenfield: file-centric, 2`
- `refinement: 2, 3`
- `drift-reconcile: 3, 4`

Start only when `agents/ROUTER.md`, `agents/docs/AGENT-USE.md`, `agents/actions/plan.md`, and `{PRODUCT_ROOT}/planning-mds/knowledge-graph/{solution-ontology,canonical-nodes,feature-mappings,code-index,coverage-report}.yaml` exist. `{FEATURE_PATH}` must exist when the mode is not `greenfield`, and `python3 {PRODUCT_ROOT}/scripts/kg/validate.py` should already exit 0.

Load context in this order and navigate instead of eager-loading:
1. `agents/ROUTER.md` and only the task-matched references
2. `agents/agent-map.yaml`
3. `agents/docs/AGENT-USE.md`
4. `agents/actions/plan.md`
5. `python3 {PRODUCT_ROOT}/scripts/kg/lookup.py {FEATURE_ID} --tier {start_tier} --allow-missing --run-id {RUN_ID} --telemetry-file {PRODUCT_ROOT}/.kg-state/telemetry.jsonl`
6. `{FEATURE_PATH}/**` when it exists

Treat `lookup.py` as a FIRST-PASS scope resolver only. Raw artifacts win on conflict. If `MODE=greenfield` and lookup returns empty scope, stay file-centric for Phase A. Open these only when lookup links them, the current gate needs them, or drift repair requires them: `{PRODUCT_ROOT}/planning-mds/api/<openapi-spec>.yaml`, `{PRODUCT_ROOT}/planning-mds/security/authorization-matrix.md`, `{PRODUCT_ROOT}/planning-mds/security/policies/policy.csv`, `{PRODUCT_ROOT}/planning-mds/knowledge-graph/*.yaml` beyond the already returned subset, and `agents/<role>/references/**` only with a `ROUTER.md` row match.

Use these commands and keep them verbatim:
- `python3 {PRODUCT_ROOT}/scripts/kg/workstate.py --state-file {PRODUCT_ROOT}/.kg-state/{FEATURE_ID}-plan.yaml init --role plan --scope {FEATURE_ID} --run-id {RUN_ID} --mode {MODE}`
- `workstate.py decision --topic <slug>` after each gate pass
- `workstate.py escalate <reason> [--nodes ...] [--opened-raw ...]` on every INSUFFICIENT_CONTEXT event
- `hint.py <path> --run-id {RUN_ID} --telemetry-file {PRODUCT_ROOT}/.kg-state/telemetry.jsonl` before any Glob/Grep on an unfamiliar code path
- `blast.py <node-id> --run-id {RUN_ID} --telemetry-file {PRODUCT_ROOT}/.kg-state/telemetry.jsonl` before editing any canonical node, shared entity, workflow, schema, or policy rule
- `cochange.py --coverage-gaps` once at session start when MODE ∈ {refinement, drift-reconcile}; skip in greenfield; re-run before closeout in drift-reconcile

Keep ownership strict:
- `product-manager owns: feature-mappings.yaml, stories, PRD, personas, trackers`
- `architect owns: canonical-nodes.yaml, solution-ontology.yaml, ADRs, API contracts, schemas, authorization`
- `other roles: flag drift; do not edit canonical semantics`

Mode behavior is fixed:
- `greenfield: file-centric Phase A; PM seeds minimal feature-mappings stub by end of Phase A; rerun lookup.py (without --allow-missing) as a Phase B precondition`
- `refinement: reconcile existing artifacts; MUST NOT recreate from scratch`
- `drift-reconcile: repair code/contract/policy/KG divergence before Phase B approval`

Produce PM artifacts, Architect artifacts, KG mapping updates, and tracker updates in `{PRODUCT_ROOT}/planning-mds/features/REGISTRY.md`, `{PRODUCT_ROOT}/planning-mds/features/ROADMAP.md`, and `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`. Do not produce `feature-assembly-plan.md` here; that belongs to `agents/actions/feature.md Step 0`.

Follow these gates exactly:
- `G1 CLARIFICATION` — halt on vague ACs; require user input
- `G2 TRACKER SYNC (A)` — `validate-stories.py + generate-story-index.py + validate-trackers.py` exit 0
- `G3 PHASE A APPROVAL` — explicit user `"approve"`; `workstate.py decision --topic phase-a-approval`
- `G4 ONTOLOGY SYNC (B)` — if KG changed: `validate.py --write-coverage-report`, THEN `validate.py`, THEN `validate.py --check-drift`
- `G5 PHASE B APPROVAL` — explicit user `"approve"`; `workstate.py decision --topic phase-b-approval`

Don’t hand-enumerate schemas, ADRs, or contract files when lookup output exists. Don’t load `agents/<role>/references/**` without a `ROUTER.md` row match. Don’t treat lookup/KG mappings as authoritative over raw artifacts. Don’t let non-architect roles edit `canonical-nodes.yaml` or `solution-ontology.yaml`. Don’t proceed past any gate without an explicit APPROVED token. Don’t widen scope outside `{FEATURE_ID}`. Don’t climb past `max_auto_tier` without a `workstate.py escalate` event.

Stop immediately if `validate.py` exits non-zero and cannot be auto-repaired within scope, if a gate lacks the required approval token, if scope drifts outside `{FEATURE_ID}`, if a canonical node edit is attempted by a non-architect role, or if `INSUFFICIENT_CONTEXT` occurs. `INSUFFICIENT_CONTEXT` means lookup returns empty for a declared in-scope node, only ambiguous/low-confidence matches on a node about to be edited, or the workflow needs to climb past `max_auto_tier`; in all of those cases use `workstate.py escalate`, open the raw artifacts, and log the opened paths.

Close the run by executing these in order:
- `python3 agents/product-manager/scripts/validate-stories.py {FEATURE_PATH}`
- `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/`
- `python3 agents/product-manager/scripts/validate-trackers.py`
- `IF KG changed: python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report`
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py`
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift`
- `python3 agents/scripts/validate_templates.py`

Resolve conflicts like this:
- `raw artifact vs KG mapping → raw wins; repair KG in same change set`
- `plan vs story text → halt and clarify; no silent override`
- `PM Phase A stub vs Architect Phase B binding → Architect binding wins at closeout`

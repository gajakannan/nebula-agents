ACTION: agents/actions/feature.md

SESSION_SETUP:
- Resolve {PRODUCT_ROOT} per agents/docs/AGENT-USE.md → Session Setup
- Echo the resolved absolute {PRODUCT_ROOT} path on the first turn before any shell command
- All paths and commands below assume that resolution

PARAMETERS:
  FEATURE_ID:          {F####}
  FEATURE_PATH:        {PRODUCT_ROOT}/planning-mds/features/{F####-slug}   # POSIX
  MODE:                {clean | drift-reconcile}
  SLICE_ORDER_SOURCE:  {assembly-plan | override}
  # If override:
  # SLICE_ORDER:
  #   - {F####-S####}
  #   - [{F####-S####}, {F####-S####}]   # brackets = parallel within entry
  RUN_ID:              {uuid4 generated at session start}

TIER DEFAULTS (start_tier, max_auto_tier):
  clean:            1, 2
  drift-reconcile:  3, 4

PRIMARY_SPEC: {FEATURE_PATH}/feature-assembly-plan.md

PRECONDITIONS:
- Plan action signed off for {FEATURE_ID}
- PRIMARY_SPEC exists
- Required runtime containers healthy (per feature.md "Runtime Preflight & Failure Triage")
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py` exits 0 at start

CONTEXT LOADING ORDER (navigate; do not eager-load):
1. agents/ROUTER.md
2. agents/agent-map.yaml
3. agents/docs/AGENT-USE.md
4. agents/actions/feature.md
5. `python3 {PRODUCT_ROOT}/scripts/kg/lookup.py {FEATURE_ID} --tier {start_tier} --run-id {RUN_ID} --telemetry-file {PRODUCT_ROOT}/.kg-state/telemetry.jsonl`
   — FIRST-PASS scope resolver; raw artifacts win on conflict.
6. {FEATURE_PATH}/**   (PRIMARY_SPEC is required reading)

ON-DEMAND (only if linked by lookup, required by current gate, or required by drift repair):
- {PRODUCT_ROOT}/planning-mds/knowledge-graph/solution-ontology.yaml
- {PRODUCT_ROOT}/planning-mds/api/<openapi-spec>.yaml
- {PRODUCT_ROOT}/planning-mds/security/authorization-matrix.md
- {PRODUCT_ROOT}/planning-mds/security/policies/policy.csv
- {PRODUCT_ROOT}/planning-mds/knowledge-graph/*.yaml beyond what lookup output already covers
- agents/<role>/references/** — only with a ROUTER.md row match

FORBIDDEN:
- Hand-enumerating schema/ADR/contract files when lookup output is available
- Treating lookup/KG mappings as authoritative over raw artifacts
- Editing code without prior `hint.py <path>`
- Editing shared semantics without prior `blast.py <node>`
- Continuing after runtime-blocked failure without re-running preflight
- Skipping any gate (G0–G4.7)
- Declaring Done without PM agent switch at G4.6
- Scope widening outside {FEATURE_ID}
- Climbing past max_auto_tier without a workstate.py escalate event

REQUIRED TOOL INVOCATIONS:
- `python3 {PRODUCT_ROOT}/scripts/kg/workstate.py --state-file {PRODUCT_ROOT}/.kg-state/{FEATURE_ID}-feature.yaml init --role feature --scope {FEATURE_ID} --run-id {RUN_ID} --mode {MODE}`
- `workstate.py decision --topic <slug>` after each gate pass
- `workstate.py touch <path>` after significant file changes
- `workstate.py dump --compact` after any compaction event
- `workstate.py escalate <reason>` on INSUFFICIENT_CONTEXT
- `hint.py <path> --run-id {RUN_ID} --telemetry-file {PRODUCT_ROOT}/.kg-state/telemetry.jsonl` before any Grep/Glob on code
- `blast.py <node-id> --run-id {RUN_ID} --telemetry-file {PRODUCT_ROOT}/.kg-state/telemetry.jsonl` before shared-semantics edits
- `cochange.py --coverage-gaps` once per feature in clean mode (at session start); at start + before closeout in drift-reconcile; NOT per slice

OWNERSHIP:
- product-manager owns: STATUS.md closeout, trackers, archive moves, feature-mappings.yaml path/status updates
- architect owns: feature-assembly-plan.md, canonical-nodes.yaml, solution-ontology.yaml, ADRs, API contracts, schemas, authorization
- other roles: flag drift; do not redefine canonical shared semantics

SLICE EXECUTION:
- SLICE_ORDER_SOURCE=assembly-plan: read sequence from PRIMARY_SPEC; do not reorder
- SLICE_ORDER_SOURCE=override: follow SLICE_ORDER verbatim; brackets = parallel within that entry only; no cross-slice parallelism

MODE BEHAVIOR:
- clean: assume alignment; drift discovered blocks approval until reconciled
- drift-reconcile: repair code/contract/policy/KG divergence in the same change set; silent reconciliation FORBIDDEN

GATES (sequential, all mandatory):
G0   ARCHITECT ASSEMBLY PLAN VALIDATION
G1   RUNTIME PREFLIGHT
G2   SELF-REVIEW (per role, with evidence paths)
G3   CODE + SECURITY REVIEW (parallel)
G4   APPROVAL — critical=0; high requires explicit mitigation token
G4.5 SIGNOFF — every Required=Yes role: verdict=PASS, reviewer, date, evidence path under {PRODUCT_ROOT}/planning-mds/operations/evidence/**
G4.6 PM CLOSEOUT — MUST switch role: read agents/product-manager/SKILL.md before executing (see closeout checklist below)
G4.7 TRACKER SYNC — validate-trackers.py exit 0

G4.6 PM CLOSEOUT CHECKLIST:
- Read agents/product-manager/SKILL.md (explicit role switch)
- Update {FEATURE_PATH}/STATUS.md: final overall status, deferred follow-ups, mitigation notes, signoff provenance (append-only; no mutation)
- Update {PRODUCT_ROOT}/planning-mds/features/REGISTRY.md: status/path transitions (include archive move)
- Update {PRODUCT_ROOT}/planning-mds/features/ROADMAP.md: Now/Next/Later/Completed placement
- Update {PRODUCT_ROOT}/planning-mds/BLUEPRINT.md: feature/story status labels and links
- IF overall_status == "Done": move {FEATURE_PATH} to {PRODUCT_ROOT}/planning-mds/features/archive/{F####-slug}/ and fix impacted links
- Update {PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml: feature path, status, story status
- Update {PRODUCT_ROOT}/planning-mds/knowledge-graph/code-index.yaml: bindings for every new source file introduced by this feature
- Update canonical-nodes.yaml ONLY if new shared semantics introduced (route to Architect if so)
- Capture orphaned stories and deferred follow-ups
- IF KG changed: python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report
- python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift MUST exit 0

STOP CONDITIONS:
- runtime preflight fails and cannot be restored
- critical code or security finding persists after one review cycle
- required signoff missing reviewer/date/evidence
- canonical node edit attempted outside Architect role
- scope drift outside {FEATURE_ID}
- INSUFFICIENT_CONTEXT (see plan template); escalate and open raw artifacts
- validate.py or --check-drift fails and cannot be auto-repaired

EXIT VALIDATION (run in order; all exit 0):
- Applicable backend/frontend/test commands for changed surfaces (inside runtime containers; evidence paths recorded)
- python3 agents/product-manager/scripts/validate-trackers.py
- python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/   (if stories changed)
- IF KG changed: python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report
- python3 {PRODUCT_ROOT}/scripts/kg/validate.py
- python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift
- python3 agents/scripts/validate_templates.py

CONFLICT RESOLUTION:
- raw artifact vs KG mapping → raw wins; repair KG in same change set
- feature-assembly-plan vs story text → plan wins; log reconciliation via workstate.py decision --topic plan-story-reconcile
- code vs contract/policy/KG → reconcile to contract; never silently redefine canonical semantics
- shared-semantics change detected → halt and route to Architect

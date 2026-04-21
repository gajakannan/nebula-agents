ACTION: agents/actions/plan.md

SESSION_SETUP:
- Resolve {PRODUCT_ROOT} per agents/docs/AGENT-USE.md → Session Setup
- Echo the resolved absolute {PRODUCT_ROOT} path on the first turn before any shell command
- All paths and commands below assume that resolution

PARAMETERS:
  FEATURE_ID:    {F####}
  FEATURE_PATH:  {PRODUCT_ROOT}/planning-mds/features/{F####-slug}   # POSIX; forward slashes
  MODE:          {greenfield | refinement | drift-reconcile}
  RUN_ID:        {uuid4 generated at session start}

TIER DEFAULTS (start_tier, max_auto_tier):
  greenfield:       file-centric, 2
  refinement:       2, 3
  drift-reconcile:  3, 4

PRECONDITIONS:
- agents/ROUTER.md, agents/docs/AGENT-USE.md, agents/actions/plan.md exist
- {PRODUCT_ROOT}/planning-mds/knowledge-graph/{solution-ontology,canonical-nodes,feature-mappings,code-index,coverage-report}.yaml exist
- {FEATURE_PATH} exists when MODE != greenfield
- `python3 {PRODUCT_ROOT}/scripts/kg/validate.py` exits 0 at start

CONTEXT LOADING ORDER (navigate; do not eager-load):
1. agents/ROUTER.md (load only task-matched references)
2. agents/agent-map.yaml
3. agents/docs/AGENT-USE.md
4. agents/actions/plan.md
5. `python3 {PRODUCT_ROOT}/scripts/kg/lookup.py {FEATURE_ID} --tier {start_tier} --allow-missing --run-id {RUN_ID} --telemetry-file {PRODUCT_ROOT}/.kg-state/telemetry.jsonl`
   — FIRST-PASS scope resolver. Use its output to discover schemas, APIs, ADRs, canonical nodes, policy rules.
   — NOT authoritative; raw artifacts win on conflict.
   — If MODE=greenfield AND lookup returns empty scope, proceed with file-centric Phase A.
6. {FEATURE_PATH}/** (when present)

ON-DEMAND (only if linked by lookup, required by current gate, or required by drift repair):
- {PRODUCT_ROOT}/planning-mds/api/<openapi-spec>.yaml
- {PRODUCT_ROOT}/planning-mds/security/authorization-matrix.md
- {PRODUCT_ROOT}/planning-mds/security/policies/policy.csv
- {PRODUCT_ROOT}/planning-mds/knowledge-graph/*.yaml beyond what lookup output already covers
- agents/<role>/references/** — only with a ROUTER.md row match

AUTHORITY:
- raw artifacts win over lookup/KG output in all cases
- lookup is a retrieval aid, not a source of truth
- KG drift must be repaired in the same change set

FORBIDDEN:
- Hand-enumerating schemas, ADRs, or contract files when lookup output is available
- Loading agents/<role>/references/** without a ROUTER.md row match
- Treating lookup/KG mappings as authoritative over raw artifacts
- Non-architect roles editing canonical-nodes.yaml or solution-ontology.yaml
- Proceeding past any gate without explicit APPROVED token
- Scope widening outside {FEATURE_ID}
- Climbing past max_auto_tier without a workstate.py escalate event

REQUIRED TOOL INVOCATIONS:
- `python3 {PRODUCT_ROOT}/scripts/kg/workstate.py --state-file {PRODUCT_ROOT}/.kg-state/{FEATURE_ID}-plan.yaml init --role plan --scope {FEATURE_ID} --run-id {RUN_ID} --mode {MODE}`
- `workstate.py decision --topic <slug>` after each gate pass (topic slug enables supersession)
- `workstate.py escalate <reason> [--nodes ...] [--opened-raw ...]` on every INSUFFICIENT_CONTEXT event
- `hint.py <path> --run-id {RUN_ID} --telemetry-file {PRODUCT_ROOT}/.kg-state/telemetry.jsonl` before any Glob/Grep on an unfamiliar code path
- `blast.py <node-id> --run-id {RUN_ID} --telemetry-file {PRODUCT_ROOT}/.kg-state/telemetry.jsonl` before editing any canonical node, shared entity, workflow, schema, or policy rule
- `cochange.py --coverage-gaps` once at session start when MODE ∈ {refinement, drift-reconcile}; skip in greenfield; re-run before closeout in drift-reconcile

OWNERSHIP:
- product-manager owns: feature-mappings.yaml, stories, PRD, personas, trackers
- architect owns: canonical-nodes.yaml, solution-ontology.yaml, ADRs, API contracts, schemas, authorization
- other roles: flag drift; do not edit canonical semantics

MODE BEHAVIOR:
- greenfield: file-centric Phase A; PM seeds minimal feature-mappings stub by end of Phase A; rerun lookup.py (without --allow-missing) as a Phase B precondition
- refinement: reconcile existing artifacts; MUST NOT recreate from scratch
- drift-reconcile: repair code/contract/policy/KG divergence before Phase B approval

DELIVERABLES:
- PM artifacts (PRD, stories, personas, trackers)
- Architect artifacts (data model, workflow state machines, API contract changes, ADRs, authorization deltas)
- KG mapping (feature-mappings update; canonical-nodes updates only for new shared semantics)
- Trackers (REGISTRY, ROADMAP, STORY-INDEX, BLUEPRINT)
- NOT feature-assembly-plan.md — that belongs to agents/actions/feature.md Step 0

GATES (sequential, all mandatory):
G1 CLARIFICATION     — halt on vague ACs; require user input
G2 TRACKER SYNC (A)  — validate-stories.py + generate-story-index.py + validate-trackers.py exit 0
G3 PHASE A APPROVAL  — explicit user "approve"; workstate.py decision --topic phase-a-approval
G4 ONTOLOGY SYNC (B) — if KG changed: validate.py --write-coverage-report, THEN validate.py, THEN validate.py --check-drift
G5 PHASE B APPROVAL  — explicit user "approve"; workstate.py decision --topic phase-b-approval

STOP CONDITIONS:
- validate.py exits non-zero and cannot be auto-repaired within scope
- gate lacks explicit approval token
- scope drift outside {FEATURE_ID}
- canonical node edit attempted by non-architect role
- INSUFFICIENT_CONTEXT: lookup returns empty for a declared in-scope node, OR only ambiguous/low-confidence matches on a node about to be edited, OR climbing past max_auto_tier — escalate via workstate.py escalate, open raw artifacts, log opened paths

EXIT VALIDATION (run in order; all exit 0):
- python3 agents/product-manager/scripts/validate-stories.py {FEATURE_PATH}
- python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/
- python3 agents/product-manager/scripts/validate-trackers.py
- IF KG changed: python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report
- python3 {PRODUCT_ROOT}/scripts/kg/validate.py
- python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift
- python3 agents/scripts/validate_templates.py

CONFLICT RESOLUTION:
- raw artifact vs KG mapping → raw wins; repair KG in same change set
- plan vs story text → halt and clarify; no silent override
- PM Phase A stub vs Architect Phase B binding → Architect binding wins at closeout

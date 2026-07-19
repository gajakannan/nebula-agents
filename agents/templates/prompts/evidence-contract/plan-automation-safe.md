<!-- GENERATED from agents/actions/spec/plan.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action plan -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


CONTRACT: Plan (Phase A + B) | SCOPE: base-run-only | POLICY: 2026-07-11

REQUIRED_INPUTS:
- FEATURE_ID [F####]
- PHASE
- FEATURE_MODE
OPTIONAL_INPUTS:
- PRODUCT_ROOT =default:sister-repo
AUTO_RESOLVED:
- FEATURE_INDEX_ROOT = {PRODUCT_ROOT}/planning-mds/operations/evidence/features/{FEATURE_ID}-{FEATURE_SLUG}
- FEATURE_PATH = {PRODUCT_ROOT}/planning-mds/features/{FEATURE_ID}-{FEATURE_SLUG}
- FEATURE_SLUG = kebab-case slug for {FEATURE_ID} from REGISTRY.md
- PLAN_RUN_FOLDER = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{PLAN_RUN_ID}

RUN_ID: var=PLAN_RUN_ID format=YYYY-MM-DD-[a-z0-9]{8} method=python3 -c import secrets; print(secrets.token_hex(4)) forbidden=uuid4
SESSION_SETUP: init-run.py -> planning-mds/operations/evidence/... manifest=draft base_files=[README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log] artifacts=[coverage, diffs, test-results, security, screenshots]
CONTEXT: agents/ROUTER.md -> agents/agent-map.yaml -> agents/docs/AGENT-USE.md -> agents/actions/plan.md -> {PRODUCT_ROOT}/planning-mds/features/REGISTRY.md -> {PRODUCT_ROOT}/planning-mds/features/ROADMAP.md -> {PRODUCT_ROOT}/planning-mds/BLUEPRINT.md -> {PRODUCT_ROOT}/planning-mds/knowledge-graph/solution-ontology.yaml -> {PRODUCT_ROOT}/planning-mds/knowledge-graph/canonical-nodes.yaml -> {PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml

GATES:
- G1 role=product-manager artifacts=[]
- G2 role=product-manager artifacts=[]
- G3 role=product-manager artifacts=[gate-decisions.md]
    - MANUAL checkpoint `approve-phase-a`: User reviews requirements; PM records the explicit approval token in gate-decisions.md. (requires: gate-decisions.md; produces: phase-a-approved)
- G4 role=architect artifacts=[]
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
- G5 role=architect artifacts=[gate-decisions.md]
    - run `python3 agents/product-manager/scripts/validate-stories.py {FEATURE_PATH}` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/` (cwd: framework, timeout: 120s)
    - run `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --skip-feature-evidence` (cwd: framework, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - run `python3 agents/scripts/validate_templates.py` (cwd: framework, timeout: 300s)
    - MANUAL checkpoint `approve-phase-b`: User reviews architecture; the Architect records the explicit approval token in gate-decisions.md after exit validation is green. (requires: gate-decisions.md; produces: phase-b-approved)

SEVERITY_GATE: profile=none tool=gate_policy.py coverage_min_pct=80
OWNERSHIP:
- architect: feature-assembly-plan.md, ADRs, API contract updates, schema updates, canonical-nodes.yaml, solution-ontology.yaml, feature-mappings.yaml
- product-manager: PRD.md, persona files, acceptance-criteria-checklist.md, story breakdown, STATUS.md skeleton
FORBIDDEN:
- Generate PLAN_RUN_ID with uuid4 or any non-contract format.
- Write or consume current-run.json for any reason.
- Produce role reports (g0-*, test-*, code-review-*, etc.) — those belong to the feature action.
- Create a feature evidence package at FEATURE_INDEX_ROOT during plan.
- Skip the APPROVAL or ONTOLOGY SYNC gates.
- Edit canonical-nodes.yaml or solution-ontology.yaml outside the Architect phase.
- Treat lookup/KG mappings as authoritative over raw artifacts.
- Climb past max_auto_tier without recording a workstate.py escalate event.
STOP_CONDITIONS:
- PRD approval refused by user.
- Architecture approval refused by user.
- Ontology sync gate fails and cannot be reconciled.
- kg validate.py --check-drift fails after one repair cycle.
- A canonical node edit is attempted outside the Architect role.
CONFLICT_RESOLUTION:
- PRD vs architecture conflict -> resolve in Phase B before architecture approval; do not silently change the PRD.
- existing assembly plan vs new architecture -> log reconciliation in gate-decisions.md; never silently overwrite.
- ontology binding conflict -> halt; resolve in canonical-nodes.yaml first.
NOTE[dependency_audit]: Identify direct/impacted feature dependencies from the PRD, architecture notes, feature-mappings.yaml,
and KG lookup output; record approved dependency evidence references or "audit pending" notes in
artifact-trace.md or gate-decisions.md. Do not substitute repo-wide feature-evidence validation.
NOTE[feature_path_outputs]: In {FEATURE_PATH}: PRD.md, persona files, acceptance-criteria-checklist.md, story files, STATUS.md
skeleton (Phase A); feature-assembly-plan.md, ADRs, README.md, GETTING-STARTED.md (Phase B).
feature-assembly-plan.md is NOT a plan deliverable in the run folder — it is authored here but
belongs to the feature action's G0 for the same FEATURE_ID.
NOTE[phase_mode_matrix]: PHASE=A,new -> create {FEATURE_PATH} and scaffold PRD/personas/stories/STATUS skeleton.
PHASE=A,existing -> update existing planning artifacts; STATUS.md story provenance rows are
append-only. PHASE=B,new -> REJECT (run architecture only after requirements exist).
PHASE=B,existing -> update feature-assembly-plan.md + ontology bindings.
PHASE=A+B -> Phase A then Phase B.
NOTE[session_setup]: Resolve {PRODUCT_ROOT} and echo the absolute path on the first turn, THEN run
`python3 agents/scripts/init-run.py --action plan --feature {FEATURE_ID} --product-root {PRODUCT_ROOT}`.
It mints {PLAN_RUN_ID}, resolves {FEATURE_SLUG}/{FEATURE_PATH}/{PLAN_RUN_FOLDER} from REGISTRY.md, and
creates the base-run skeleton (base run files under runs/{PLAN_RUN_ID}/). Use its JSON output for every
variable below — resolve {FEATURE_SLUG} now, at session setup, not on demand at a later gate. init-run
is base-run-only for plan: it does NOT create a feature evidence package (the feature index root is
created later by the feature action for the same FEATURE_ID).

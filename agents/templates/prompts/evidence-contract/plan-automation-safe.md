<!-- GENERATED from agents/actions/spec/plan.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action plan -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


CONTRACT: Plan (Phase A + B) | SCOPE: base-run-only | POLICY: 2026-07-11

NEBULA_PRODUCT_ROOT_BINDING: Before setup, discovery, or resume, bind the product root once. NEBULA_PRODUCT_ROOT is the canonical input in both a pasted prompt and the shell environment. An explicit operator value wins over the environment; stop for clarification if explicit selections disagree. Use only NEBULA_PRODUCT_ROOT for the input and all root placeholders. A value supplied in this prompt is valid even when the shell environment is empty; pass it explicitly to the resolver. Resolve relative paths (including ../) against the session's starting directory, normally nebula-agents, before changing directories: run `python3 agents/scripts/_product_root.py --product-root "<supplied path>"` from that directory, or omit the flag to read the environment. Replace the input value with the returned absolute NEBULA_PRODUCT_ROOT and echo it with its source. Pass that same absolute path as --product-root to every product-aware script, including init-run.py and resume-brief.py, and include it in every agent handoff. Do not rely on an export persisting between shell calls. On resume, reuse the recorded absolute root and reject a conflicting selection. If no value is supplied, ask for the product path; never infer it from a feature ID, scan siblings to choose a product, or default to a particular repository.

REQUIRED_INPUTS:
- FEATURE_ID [F####]
- PHASE enum:[A|B|A+B]
- FEATURE_MODE enum:[new|existing]
OPTIONAL_INPUTS:
- NEBULA_PRODUCT_ROOT =default:environment; required if unset
AUTO_RESOLVED:
- FEATURE_INDEX_ROOT = {NEBULA_PRODUCT_ROOT}/planning-mds/operations/evidence/features/{FEATURE_ID}-{FEATURE_SLUG}
- FEATURE_PATH = {NEBULA_PRODUCT_ROOT}/planning-mds/features/{FEATURE_ID}-{FEATURE_SLUG}
- FEATURE_SLUG = kebab-case slug for {FEATURE_ID} from REGISTRY.md
- PLAN_RUN_FOLDER = {NEBULA_PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{PLAN_RUN_ID}

RUN_ID: var=PLAN_RUN_ID format=YYYY-MM-DD-[a-z0-9]{8} method=python3 -c import secrets; print(secrets.token_hex(4)) forbidden=uuid4
SESSION_SETUP: init-run.py --product-root {NEBULA_PRODUCT_ROOT} -> planning-mds/operations/evidence/... manifest=draft base_files=[README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log] artifacts=[coverage, diffs, test-results, security, screenshots]
CONTEXT: agents/ROUTER.md -> agents/agent-map.yaml -> agents/docs/AGENT-USE.md -> agents/docs/PROJECT-EXTENSIONS.md -> agents/actions/plan.md -> {NEBULA_PRODUCT_ROOT}/planning-mds/features/REGISTRY.md -> {NEBULA_PRODUCT_ROOT}/planning-mds/features/ROADMAP.md -> {NEBULA_PRODUCT_ROOT}/planning-mds/BLUEPRINT.md -> {NEBULA_PRODUCT_ROOT}/planning-mds/knowledge-graph/solution-ontology.yaml -> {NEBULA_PRODUCT_ROOT}/planning-mds/knowledge-graph/canonical-nodes.yaml -> {NEBULA_PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml
PRODUCT_CONTEXT: resolve NEBULA_PRODUCT_ROOT explicitly; run `python3 agents/scripts/project_context.py --product-root {NEBULA_PRODUCT_ROOT} --action plan`; read returned instructions before work and after resume; context error blocks action; absent manifest preserves existing procedure.

GATES:
- G1 role=product-manager artifacts=[]
- G2 role=product-manager artifacts=[]
- G3 role=product-manager artifacts=[gate-decisions.md]
    - MANUAL checkpoint `approve-phase-a`: User reviews requirements; PM records the explicit approval token in gate-decisions.md. (requires: gate-decisions.md; produces: phase-a-approved)
- G4 role=architect artifacts=[]
    - run `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/compile.py` (cwd: product, timeout: 300s)
    - run `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
- G5 role=architect artifacts=[gate-decisions.md]
    - run `python3 agents/product-manager/scripts/validate-stories.py {FEATURE_PATH}` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/generate-story-index.py {NEBULA_PRODUCT_ROOT}/planning-mds/features/` (cwd: framework, timeout: 120s)
    - run `python3 agents/product-manager/scripts/validate-trackers.py --product-root {NEBULA_PRODUCT_ROOT} --skip-feature-evidence` (cwd: framework, timeout: 300s)
    - run `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report` (cwd: product, timeout: 300s)
    - run `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - run `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/validate.py --check-reproducible` (cwd: product, timeout: 300s)
    - run `python3 agents/scripts/validate_templates.py` (cwd: framework, timeout: 300s)
    - MANUAL checkpoint `approve-phase-b`: User reviews architecture; the Architect records the explicit approval token in gate-decisions.md after exit validation is green. (requires: gate-decisions.md; produces: phase-b-approved)

SEVERITY_GATE: profile=none tool=gate_policy.py coverage_min_pct=80
OWNERSHIP:
- architect: feature-assembly-plan.md, ADRs, API contract updates, schema updates, kg-source/** shards (nodes/** + the feature shard) — compiled by compile.py into canonical-nodes.yaml/feature-mappings.yaml/solution-ontology.yaml + REGISTRY/ROADMAP regions; never hand-edit the generated files
- product-manager: PRD.md, persona files, acceptance-criteria-checklist.md, story breakdown, STATUS.md skeleton
FORBIDDEN:
- Generate PLAN_RUN_ID with uuid4 or any non-contract format.
- Write or consume current-run.json for any reason.
- Produce role reports (g0-*, test-*, code-review-*, etc.) — those belong to the feature action.
- Create a feature evidence package at FEATURE_INDEX_ROOT during plan.
- Skip the APPROVAL or ONTOLOGY SYNC gates.
- Edit canonical-nodes.yaml or solution-ontology.yaml outside the Architect phase.
- Hand-edit the compiled KG projections (canonical-nodes/feature-mappings/code-index/solution-ontology.yaml) or the REGISTRY/ROADMAP/STORY-INDEX generated regions — edit kg-source/** shards and run compile.py (the kg-reproducibility CI gate rejects hand-edited generated files).
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
NOTE[kg_generated_files]: The KG projections (knowledge-graph/{canonical-nodes,feature-mappings,code-index,solution-ontology}.yaml)
and the REGISTRY/ROADMAP/STORY-INDEX generated regions are COMPILED from planning-mds/kg-source/** by
scripts/kg/compile.py — never hand-edit them (the product's kg-reproducibility CI gate, validate.py
--check-reproducible, fails a PR when a committed generated file != compile(source)). To map the feature
at Phase B: (1) edit the feature shard kg-source/features/{FEATURE_ID}.yaml — set status (e.g. planned),
name, rationale; remove any coverage_excluded; add affects/depends_on/governed_by/uses_api_contract/
uses_schema and inline story_mappings (story path = full path); (2) add node shards under kg-source/nodes/
(capabilities = one file per node; adrs/endpoints/schemas = aggregate files); node source_docs use logical
F####/file.md refs resolved via the feature shard path. Then run compile.py (G4 kg-compile), then
validate.py --check-drift (G4) and --check-reproducible (G5). A pre-commit hook mirroring the CI gate is
recommended in the product repo so drift is caught before push.
NOTE[phase_mode_matrix]: PHASE=A,new -> create {FEATURE_PATH} and scaffold PRD/personas/stories/STATUS skeleton.
PHASE=A,existing -> update existing planning artifacts; STATUS.md story provenance rows are
append-only. PHASE=B,new -> REJECT (run architecture only after requirements exist).
PHASE=B,existing -> update feature-assembly-plan.md + ontology bindings.
PHASE=A+B -> Phase A then Phase B.
NOTE[session_setup]: Resolve {NEBULA_PRODUCT_ROOT} and echo the absolute path on the first turn, THEN run
`python3 agents/scripts/init-run.py --action plan --feature {FEATURE_ID} --product-root {NEBULA_PRODUCT_ROOT}`.
It mints {PLAN_RUN_ID}, resolves {FEATURE_SLUG}/{FEATURE_PATH}/{PLAN_RUN_FOLDER} from REGISTRY.md, and
creates the base-run skeleton (base run files under runs/{PLAN_RUN_ID}/). Use its JSON output for every
variable below — resolve {FEATURE_SLUG} now, at session setup, not on demand at a later gate. init-run
is base-run-only for plan: it does NOT create a feature evidence package (the feature index root is
created later by the feature action for the same FEATURE_ID).

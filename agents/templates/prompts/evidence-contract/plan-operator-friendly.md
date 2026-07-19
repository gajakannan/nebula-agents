<!-- GENERATED from agents/actions/spec/plan.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action plan -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


This prompt encodes the **Plan (Phase A + B)** (scope `base-run-only`, policy `2026-07-11`).

Required inputs:
- `FEATURE_ID` (format `F####`)
- `PHASE`
- `FEATURE_MODE`

Optional inputs (defaults apply when omitted):
- `PRODUCT_ROOT` — default `sister-repo`

Auto-resolved (do not set; SESSION_SETUP / the orchestrator compute these):
- `FEATURE_INDEX_ROOT` — {PRODUCT_ROOT}/planning-mds/operations/evidence/features/{FEATURE_ID}-{FEATURE_SLUG}
- `FEATURE_PATH` — {PRODUCT_ROOT}/planning-mds/features/{FEATURE_ID}-{FEATURE_SLUG}
- `FEATURE_SLUG` — kebab-case slug for {FEATURE_ID} from REGISTRY.md
- `PLAN_RUN_FOLDER` — {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{PLAN_RUN_ID}

Generate `PLAN_RUN_ID` once at session start in the contract format `YYYY-MM-DD-[a-z0-9]{8}` using `python3 -c import secrets; print(secrets.token_hex(4))`. Do not use: uuid4.

Session setup: create the run under `planning-mds/operations/evidence/`, initialize `evidence-manifest.json` (status `draft`) with the active contract version stamped, create the base run files (README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log) and artifact subdirs (coverage, diffs, test-results, security, screenshots). Run `agents/scripts/init-run.py` to perform this.

Load context in this order, then navigate rather than eager-load:
1. `agents/ROUTER.md`
2. `agents/agent-map.yaml`
3. `agents/docs/AGENT-USE.md`
4. `agents/actions/plan.md`
5. `{PRODUCT_ROOT}/planning-mds/features/REGISTRY.md`
6. `{PRODUCT_ROOT}/planning-mds/features/ROADMAP.md`
7. `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`
8. `{PRODUCT_ROOT}/planning-mds/knowledge-graph/solution-ontology.yaml`
9. `{PRODUCT_ROOT}/planning-mds/knowledge-graph/canonical-nodes.yaml`
10. `{PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml`

Gates (run each stage through `agents/scripts/run-gate.py`, in order):
- **G1 — Clarification** (role: product-manager; artifacts: none)
    - judgment: Step 1.5 Requirements Clarification: the PM resolves open requirement questions before approval.
- **G2 — Tracker sync (Phase A)** (role: product-manager; artifacts: none)
    - judgment: Step 1.75 mandatory tracker synchronization (REGISTRY.md / ROADMAP.md / BLUEPRINT.md /
STORY-INDEX.md) before Phase A approval.
- **G3 — Phase A approval** (role: product-manager; artifacts: gate-decisions.md)
    - MANUAL checkpoint `approve-phase-a`: User reviews requirements; PM records the explicit approval token in gate-decisions.md. (requires: gate-decisions.md; produces: phase-a-approved)
    - judgment: Step 2 Phase A review. No gate may be passed without an explicit approval token recorded in
gate-decisions.md.
- **G4 — Ontology sync (Phase B)** (role: architect; artifacts: none)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - judgment: Step 3.5: feature-mappings.yaml + canonical-nodes.yaml + solution-ontology.yaml aligned with the
assembly plan; kg validate --check-drift must exit 0. Only the Architect edits canonical-nodes.yaml
or solution-ontology.yaml.
- **G5 — Phase B approval and exit validation** (role: architect; artifacts: gate-decisions.md)
    - run `python3 agents/product-manager/scripts/validate-stories.py {FEATURE_PATH}` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/` (cwd: framework, timeout: 120s)
    - run `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --skip-feature-evidence` (cwd: framework, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - run `python3 agents/scripts/validate_templates.py` (cwd: framework, timeout: 300s)
    - MANUAL checkpoint `approve-phase-b`: User reviews architecture; the Architect records the explicit approval token in gate-decisions.md after exit validation is green. (requires: gate-decisions.md; produces: phase-b-approved)
    - judgment: Step 4 Phase B review. Exit-validation commands run in order and all exit 0 before approval.
Do NOT call validate-feature-evidence.py at plan — there is no feature evidence package yet.
Do NOT run validate-trackers.py --all-feature-evidence as plan closeout; repo-wide feature-evidence validation is an explicit health/audit action.

Severity gate profile: `none` (compute allowed outcomes with `agents/scripts/gate_policy.py`; coverage floor is 80%).

Ownership (strict):
- **architect** owns: feature-assembly-plan.md, ADRs, API contract updates, schema updates, canonical-nodes.yaml, solution-ontology.yaml, feature-mappings.yaml
- **product-manager** owns: PRD.md, persona files, acceptance-criteria-checklist.md, story breakdown, STATUS.md skeleton

Forbidden:
- Generate PLAN_RUN_ID with uuid4 or any non-contract format.
- Write or consume current-run.json for any reason.
- Produce role reports (g0-*, test-*, code-review-*, etc.) — those belong to the feature action.
- Create a feature evidence package at FEATURE_INDEX_ROOT during plan.
- Skip the APPROVAL or ONTOLOGY SYNC gates.
- Edit canonical-nodes.yaml or solution-ontology.yaml outside the Architect phase.
- Treat lookup/KG mappings as authoritative over raw artifacts.
- Climb past max_auto_tier without recording a workstate.py escalate event.

Stop conditions:
- PRD approval refused by user.
- Architecture approval refused by user.
- Ontology sync gate fails and cannot be reconciled.
- kg validate.py --check-drift fails after one repair cycle.
- A canonical node edit is attempted outside the Architect role.

Conflict resolution:
- PRD vs architecture conflict -> resolve in Phase B before architecture approval; do not silently change the PRD.
- existing assembly plan vs new architecture -> log reconciliation in gate-decisions.md; never silently overwrite.
- ontology binding conflict -> halt; resolve in canonical-nodes.yaml first.

Note (dependency_audit): Identify direct/impacted feature dependencies from the PRD, architecture notes, feature-mappings.yaml,
and KG lookup output; record approved dependency evidence references or "audit pending" notes in
artifact-trace.md or gate-decisions.md. Do not substitute repo-wide feature-evidence validation.

Note (feature_path_outputs): In {FEATURE_PATH}: PRD.md, persona files, acceptance-criteria-checklist.md, story files, STATUS.md
skeleton (Phase A); feature-assembly-plan.md, ADRs, README.md, GETTING-STARTED.md (Phase B).
feature-assembly-plan.md is NOT a plan deliverable in the run folder — it is authored here but
belongs to the feature action's G0 for the same FEATURE_ID.

Note (phase_mode_matrix): PHASE=A,new -> create {FEATURE_PATH} and scaffold PRD/personas/stories/STATUS skeleton.
PHASE=A,existing -> update existing planning artifacts; STATUS.md story provenance rows are
append-only. PHASE=B,new -> REJECT (run architecture only after requirements exist).
PHASE=B,existing -> update feature-assembly-plan.md + ontology bindings.
PHASE=A+B -> Phase A then Phase B.

Note (session_setup): Resolve {PRODUCT_ROOT} and echo the absolute path on the first turn, THEN run
`python3 agents/scripts/init-run.py --action plan --feature {FEATURE_ID} --product-root {PRODUCT_ROOT}`.
It mints {PLAN_RUN_ID}, resolves {FEATURE_SLUG}/{FEATURE_PATH}/{PLAN_RUN_FOLDER} from REGISTRY.md, and
creates the base-run skeleton (base run files under runs/{PLAN_RUN_ID}/). Use its JSON output for every
variable below — resolve {FEATURE_SLUG} now, at session setup, not on demand at a later gate. init-run
is base-run-only for plan: it does NOT create a feature evidence package (the feature index root is
created later by the feature action for the same FEATURE_ID).

<!-- GENERATED from agents/actions/spec/validate.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action validate -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


CONTRACT: Feature Evidence Contract | SCOPE: base-run-only | POLICY: 2026-07-11

REQUIRED_INPUTS:
- VALIDATION_SCOPE
OPTIONAL_INPUTS:
- FEATURE_ID
- STAGE =default:closeout
- RUN_ID
- EFFECTIVE_DATE =default:2026-05-19 (framework default; earlier values rejected per §22)
- PRODUCT_ROOT =default:sister-repo
AUTO_RESOLVED:
- FEATURE_INDEX_ROOT = {PRODUCT_ROOT}/planning-mds/operations/evidence/features/{FEATURE_ID}-{FEATURE_SLUG} (only when FEATURE_ID is set)
- FEATURE_SLUG = kebab-case slug for {FEATURE_ID} from REGISTRY.md (only when FEATURE_ID is set)
- VALIDATE_RUN_FOLDER = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{VALIDATE_RUN_ID}

RUN_ID: var=VALIDATE_RUN_ID format=YYYY-MM-DD-[a-z0-9]{8} method=python3 -c import secrets; print(secrets.token_hex(4)) forbidden=uuid4
SESSION_SETUP: init-run.py -> planning-mds/operations/evidence/... manifest=draft base_files=[README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log] artifacts=[coverage, diffs, test-results, security, screenshots]
CONTEXT: agents/ROUTER.md -> agents/agent-map.yaml -> agents/docs/AGENT-USE.md -> agents/actions/validate.md -> agents/product-manager/SKILL.md (requirements validation mode) -> agents/architect/SKILL.md (architecture validation mode) -> agents/product-manager/scripts/README.md (validator commands + exit codes; only when scope includes implementation)

GATES:
- V0 role=product-manager artifacts=[action-context.md]
- V1 role=product-manager artifacts=[pm-validation-report.md, architect-validation-report.md, implementation-validation-report.md]
    - run `python3 agents/product-manager/scripts/validate-trackers.py` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --json` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/` (cwd: framework, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-symbols` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - run `python3 agents/scripts/validate_templates.py` (cwd: framework, timeout: 300s)
- V2 role=product-manager artifacts=[]
- V3 role=product-manager artifacts=[]
    - MANUAL checkpoint `validate-approval`: User reviews all produced reports and decides next steps. Errors must never be hidden as warnings. (requires: the in-scope per-agent validation reports (pm / architect / implementation); produces: validate approval (V3 row in gate-decisions.md))

SEVERITY_GATE: profile=none tool=gate_policy.py coverage_min_pct=80
OWNERSHIP:
- architect: architect-validation-report.md
- product-manager: pm-validation-report.md, implementation-validation-report.md
FORBIDDEN:
- Generate VALIDATE_RUN_ID with uuid4.
- Write into any feature evidence package — validate is read-only with respect to feature packages.
- Treat validator script output as a substitute for the PM/Architect agent-level validation work.
- Pass --evidence-effective-date earlier than the framework default.
- Call --stage G8 or --stage closeout when invoked transitively from validate-trackers.py (§17 step 2: tracker integration uses --stage G6 only).
- Produce validation summaries that hide errors as warnings.
- Skip the SELF-REVIEW gate for any producing agent.
- Bypass the APPROVAL gate before reporting results upstream.
STOP_CONDITIONS:
- Any validator returns exit code 2 (validator invocation error) — escalate to the user.
- An error-severity rule fires on a governed completed-terminal feature and the operator does not authorize the validator-defect waiver path in agents/docs/AGENT-OPS.md.
- KG drift detected and not auto-repairable.
- Effective-date override attempted with an earlier-than-default value.
- Two approved manifests detected for the same feature (two_approved_runs_without_supersession_fails) — escalate to PM.
- Either agent's SELF-REVIEW finds its own report materially incomplete.
- User refuses the APPROVAL gate.
CONFLICT_RESOLUTION:
- PM findings disagree with Architect findings on the same artifact -> escalate to the user at V3; do not silently reconcile.
- validate-trackers.py reports a rule that validate-feature-evidence.py owns -> defer to the feature evidence validator (single source of truth §22).
- validate-feature-evidence.py reports an error the operator believes is a validator defect -> do NOT bypass via --evidence-effective-date; route to the Phase 5 validator-defect fallback (waivers.validator_defect at G8 for in-progress features; mid-stage follow-up otherwise).
- registry-wide scan reports a pre-contract archived feature requiring evidence -> check Evidence Reentry Date on that archived row; absence means no reentry claimed, so the requirement is the bug.
NOTE[evidence_outputs]: In {VALIDATE_RUN_FOLDER}: the six base run files; pm-validation-report.md (Completeness, Vision &
Non-Goals, Personas, Feature Traceability, Story Testability, Acceptance Criteria, Findings, Result);
architect-validation-report.md (Ontology Integrity, Canonical Nodes, Feature Mappings, API Contracts,
Schemas, Authorization, Assembly-Plan Alignment, Findings, Result); implementation-validation-report.md
(commands executed, exit codes, errors/warnings/info, KG drift status, template alignment, Findings
cross-referenced to §22 rule IDs, Result); artifacts/feature-evidence-validation.json when the
implementation lane ran. This run does NOT write into any feature evidence package.
NOTE[implementation_feature_variant]: When FEATURE_ID is set the implementation lane runs the per-feature commands instead of the registry-wide
ops: (i) validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} [--run-id {RUN_ID}]
--stage {STAGE} --json -> artifacts/feature-evidence-validation.json; (ii) validate-trackers.py --feature
{FEATURE_ID} [--run-id {RUN_ID}]; (iii) {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift;
(iv) agents/scripts/validate_templates.py.
NOTE[scope_conditionality]: V1 lanes are conditional on VALIDATION_SCOPE. requirements/all -> PM requirements validation
(preconditions: BLUEPRINT.md, REGISTRY.md, ROADMAP.md exist). architecture/all -> Architect architecture
validation (preconditions: solution-ontology.yaml, canonical-nodes.yaml, feature-mappings.yaml exist).
implementation/all -> the validator run ops (precondition: at least one completed-terminal feature in
REGISTRY.md OR FEATURE_ID set). When implementation targets an in-progress feature with STAGE in
{G0..G5}, --run-id is mandatory; at STAGE G8/closeout, {FEATURE_INDEX_ROOT}/latest-run.json must exist.
NOTE[session_setup]: Echo the resolved absolute {PRODUCT_ROOT} on the first turn before any command. Generate
VALIDATE_RUN_ID once at session start in contract format (an ISO YYYY-MM-DD date plus a
secrets.token_hex(4) suffix); never uuid4. Create {VALIDATE_RUN_FOLDER}/artifacts and initialize the
six §8 base run files (README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log,
lifecycle-gates.log).
NOTE[telemetry]: Append every validator and KG command to {VALIDATE_RUN_FOLDER}/commands.log per the §13 JSONL schema
(schema_version, timestamp with timezone, cwd, command, exit_code, artifacts[], redactions[]) and their
exit codes/summaries to {VALIDATE_RUN_FOLDER}/lifecycle-gates.log.

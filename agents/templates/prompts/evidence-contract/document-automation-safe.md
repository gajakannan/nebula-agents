<!-- GENERATED from agents/actions/spec/document.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action document -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


CONTRACT: Feature Evidence Contract | SCOPE: base-run-only | POLICY: 2026-07-11

REQUIRED_INPUTS:
- DOC_SCOPE
- TARGETS [[path, ...] destination doc files]
OPTIONAL_INPUTS:
- SOURCE_CODE
- FEATURE_REF
- PRODUCT_ROOT =default:sister-repo
AUTO_RESOLVED:
- DOC_RUN_FOLDER = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{DOC_RUN_ID}
- FEATURE_REF_PATH = {PRODUCT_ROOT}/planning-mds/features/{FEATURE_REF}-{FEATURE_REF_SLUG} (only when FEATURE_REF is set)
- FEATURE_REF_SLUG = kebab-case slug for {FEATURE_REF} from REGISTRY.md (only when FEATURE_REF is set)

RUN_ID: var=DOC_RUN_ID format=YYYY-MM-DD-[a-z0-9]{8} method=python3 -c import secrets; print(secrets.token_hex(4)) forbidden=uuid4
SESSION_SETUP: init-run.py -> planning-mds/operations/evidence/... manifest=draft base_files=[README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log] artifacts=[coverage, diffs, test-results, security, screenshots]
CONTEXT: agents/ROUTER.md -> agents/agent-map.yaml -> agents/docs/AGENT-USE.md -> agents/actions/document.md -> agents/technical-writer/SKILL.md -> SOURCE_CODE paths (read-only) -> for FEATURE_REF (read-only context): {FEATURE_REF_PATH}/README.md, PRD.md, feature-assembly-plan.md

GATES:
- D0 role=technical-writer artifacts=[gate-decisions.md]
- D1 role=technical-writer artifacts=[]
- D2 role=technical-writer artifacts=[]
- D3 role=technical-writer artifacts=[]
    - MANUAL checkpoint `doc-approval`: The user reviews the documentation and approves or requests changes. (requires: the TARGETS drafted at D1; produces: doc approval recorded in gate-decisions.md)
    - run `python3 agents/scripts/validate_templates.py` (cwd: framework, timeout: 300s)

SEVERITY_GATE: profile=none tool=gate_policy.py coverage_min_pct=80
OWNERSHIP:
- technical-writer: every produced doc file (the TARGETS)
FORBIDDEN:
- Generate DOC_RUN_ID with uuid4.
- Write into any feature evidence package (####-*/).
- Cite documentation as a substitute for required feature evidence reports (e.g. test-execution-report.md, code-review-report.md).
- Execute compile/lint/runtime commands outside runtime containers.
- Skip the SELF-REVIEW or APPROVAL gates.
STOP_CONDITIONS:
- Self-review identifies factual errors that cannot be resolved against source code.
- Runtime verification fails and the doc would mislead users.
- The user refuses the approval gate.
CONFLICT_RESOLUTION:
- doc disagrees with code -> code wins; update the doc, not the code.
- doc disagrees with an API contract -> the contract wins; route to plan/architect if the contract itself is wrong.
- doc cites a runtime example that does not work -> fix or remove the example; do not ship docs that mislead.
NOTE[evidence_outputs]: In {DOC_RUN_FOLDER}: README.md (Run Summary = "Documentation run", Status, Evidence Index pointing to
TARGETS, Validation Summary, Open Follow-ups); action-context.md (Scope Boundaries = "Documentation only; not
feature evidence", Lifecycle Stage = "Document"); artifact-trace.md (which TARGETS were created/updated +
SOURCE_CODE pointers); gate-decisions.md (D0..D3); commands.log; lifecycle-gates.log. The documentation files
themselves land at the TARGETS.
NOTE[session_setup]: Echo the resolved absolute {PRODUCT_ROOT} on the first turn. Mint DOC_RUN_ID once in contract format (an ISO
YYYY-MM-DD date plus a secrets.token_hex(4) suffix); never uuid4. Create {DOC_RUN_FOLDER} and initialize the
six §8 base run files.
NOTE[telemetry]: Append every shell command to {DOC_RUN_FOLDER}/commands.log per the §13 JSONL schema (schema_version,
timestamp with timezone, cwd, command, exit_code, artifacts[], redactions[]).

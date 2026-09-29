<!-- GENERATED from agents/actions/spec/test.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action test -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


CONTRACT: Feature Evidence Contract | SCOPE: base-run-only | POLICY: 2026-07-11

NEBULA_PRODUCT_ROOT_BINDING: Before setup, discovery, or resume, bind the product root once. NEBULA_PRODUCT_ROOT is the canonical input in both a pasted prompt and the shell environment. An explicit operator value wins over the environment; stop for clarification if explicit selections disagree. Use only NEBULA_PRODUCT_ROOT for the input and all root placeholders. A value supplied in this prompt is valid even when the shell environment is empty; pass it explicitly to the resolver. Resolve relative paths (including ../) against the session's starting directory, normally nebula-agents, before changing directories: run `python3 agents/scripts/_product_root.py --product-root "<supplied path>"` from that directory, or omit the flag to read the environment. Replace the input value with the returned absolute NEBULA_PRODUCT_ROOT and echo it with its source. Pass that same absolute path as --product-root to every product-aware script, including init-run.py and resume-brief.py, and include it in every agent handoff. Do not rely on an export persisting between shell calls. On resume, reuse the recorded absolute root and reject a conflicting selection. If no value is supplied, ask for the product path; never infer it from a feature ID, scan siblings to choose a product, or default to a particular repository.

REQUIRED_INPUTS:
- MODE enum:[feature-scoped|standalone]
- TEST_SCOPE enum:[unit|component|integration|e2e|api|accessibility|regression|all]
OPTIONAL_INPUTS:
- FEATURE_ID required_when:[MODE=feature-scoped]
- RUN_ID required_when:[MODE=feature-scoped]
- STORIES
- NEBULA_PRODUCT_ROOT =default:environment; required if unset
AUTO_RESOLVED:
- ARTIFACTS_FOLDER = {OUTPUT_FOLDER}/artifacts/test-results (feature-scoped; raw test output)
- COVERAGE_FOLDER = {OUTPUT_FOLDER}/artifacts/coverage (feature-scoped; raw coverage output)
- FEATURE_PATH = {NEBULA_PRODUCT_ROOT}/planning-mds/features/{FEATURE_ID}-{FEATURE_SLUG} (feature-scoped only)
- FEATURE_SLUG = kebab-case slug for {FEATURE_ID} from REGISTRY.md (feature-scoped only)
- OUTPUT_FOLDER = {NEBULA_PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID} (feature-scoped only; MUST already exist)
- SCREENSHOTS_FOLDER = {OUTPUT_FOLDER}/artifacts/screenshots (feature-scoped; visual-regression snapshots when applicable)
- TEST_RUN_FOLDER = {NEBULA_PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{TEST_RUN_ID} (standalone only)

RUN_ID: var=TEST_RUN_ID format=YYYY-MM-DD-[a-z0-9]{8} method=python3 -c import secrets; print(secrets.token_hex(4)) forbidden=uuid4
SESSION_SETUP: init-run.py --product-root {NEBULA_PRODUCT_ROOT} -> planning-mds/operations/evidence/... manifest=draft base_files=[README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log] artifacts=[coverage, diffs, test-results, security, screenshots]
CONTEXT: agents/ROUTER.md -> agents/agent-map.yaml -> agents/docs/AGENT-USE.md -> agents/docs/PROJECT-EXTENSIONS.md -> agents/actions/test.md -> agents/quality-engineer/SKILL.md -> feature-scoped only: {FEATURE_PATH}/feature-assembly-plan.md, {FEATURE_PATH}/STATUS.md, the feature's story files, {OUTPUT_FOLDER}/evidence-manifest.json
PRODUCT_CONTEXT: resolve NEBULA_PRODUCT_ROOT explicitly; run `python3 agents/scripts/project_context.py --product-root {NEBULA_PRODUCT_ROOT} --action test`; read returned instructions before work and after resume; context error blocks action; absent manifest preserves existing procedure.

GATES:
- T0 role=quality-engineer artifacts=[test-plan.md]
- T1 role=quality-engineer artifacts=[test-execution-report.md]
- T2 role=quality-engineer artifacts=[coverage-report.md]
- T3 role=quality-engineer artifacts=[]
- T4 role=quality-engineer artifacts=[]
- T5 role=quality-engineer artifacts=[]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {NEBULA_PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G2` (cwd: framework, timeout: 600s)

SEVERITY_GATE: profile=none tool=gate_policy.py coverage_min_pct=80
OWNERSHIP:
- quality-engineer: test-plan.md, test-execution-report.md, coverage-report.md
FORBIDDEN:
- Generate run IDs with uuid4.
- Write QE reports outside {OUTPUT_FOLDER} (feature-scoped) or {TEST_RUN_FOLDER} (standalone).
- Create a new run folder in feature-scoped mode — use the existing {OUTPUT_FOLDER}.
- Skip coverage-report.md — the file must exist even when coverage is waived (§10).
- Mock runtime layers in integration/E2E tests when raw runtime is available.
- Cite summary prose alone as evidence for a passing gate; artifact paths are required.
- Apply generic universal coverage thresholds; coverage targets are feature-scoped per §29 risk mitigation.
STOP_CONDITIONS:
- coverage-report.md missing (missing_coverage_report_fails).
- test-execution-report.md missing (missing_test_execution_fails).
- test-plan.md missing (missing_test_plan_fails).
- A coverage waiver is requested without PM acceptance at closeout (handled at G8).
- INSUFFICIENT_CONTEXT occurs — escalate, open raw artifacts, do not proceed on weak matches.
CONFLICT_RESOLUTION:
- coverage target met but a story has no test -> fail; add a test or document the AC exception.
- coverage-report.md exists but raw artifacts missing -> fail (coverage_claim_without_artifact_fails).
- test-execution-report.md cites an artifact path that does not resolve -> fail (test_results_reference_missing_fails).
- coverage-report.md waiver missing PM acceptance at closeout -> handled by G8 (coverage_waiver_missing_pm_acceptance_fails).
NOTE[evidence_outputs]: In feature-scoped mode also update {OUTPUT_FOLDER}/evidence-manifest.json role_results for Quality Engineer
with required_artifacts=[test-plan.md, test-execution-report.md, coverage-report.md] and
verdict_artifact=test-execution-report.md; when coverage is waived, populate waivers.coverage with
required/reason/owner/approved_on/follow_up. Copy or reference raw test results, coverage, and (when
applicable) visual-regression screenshots under the run's artifacts/ subfolders.
NOTE[modes]: feature-scoped: FEATURE_ID + RUN_ID (the parent feature run) are required; OUTPUT_FOLDER MUST already exist
(do NOT create a new run folder); the QE reports and manifest updates land in the parent feature run and feed
its G2/G5. standalone: generate TEST_RUN_ID and create TEST_RUN_FOLDER; the run produces NO feature evidence
package and does NOT satisfy the per-feature QE requirement — the corresponding feature.md run must still
produce its own G2 evidence.
NOTE[session_setup]: Echo the resolved absolute {NEBULA_PRODUCT_ROOT} after root binding, before product discovery or writes. Generate TEST_RUN_ID once in
contract format (an ISO YYYY-MM-DD date plus a secrets.token_hex(4) suffix); never uuid4. feature-scoped: no
run-folder creation; ensure the artifacts/test-results, artifacts/coverage, and artifacts/screenshots
subfolders exist under OUTPUT_FOLDER. standalone: mkdir TEST_RUN_FOLDER/artifacts/{test-results,coverage} and
initialize the six §8 base run files.
NOTE[telemetry]: Test commands run inside application runtime containers; append every shell command to the run's commands.log
per the §13 JSONL schema (schema_version, timestamp with timezone, cwd, command, exit_code, artifacts[],
redactions[]) with artifact paths recorded. Do not leak secrets — secret-pattern checks fail the run.

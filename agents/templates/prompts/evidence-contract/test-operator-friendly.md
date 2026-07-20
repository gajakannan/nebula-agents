<!-- GENERATED from agents/actions/spec/test.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action test -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


This prompt encodes the **Feature Evidence Contract** (scope `base-run-only`, policy `2026-07-11`).

Required inputs:
- `MODE`
- `TEST_SCOPE`

Optional inputs (defaults apply when omitted):
- `FEATURE_ID`
- `RUN_ID`
- `STORIES`
- `PRODUCT_ROOT` — default `sister-repo`

Auto-resolved (do not set; SESSION_SETUP / the orchestrator compute these):
- `ARTIFACTS_FOLDER` — {OUTPUT_FOLDER}/artifacts/test-results (feature-scoped; raw test output)
- `COVERAGE_FOLDER` — {OUTPUT_FOLDER}/artifacts/coverage (feature-scoped; raw coverage output)
- `FEATURE_PATH` — {PRODUCT_ROOT}/planning-mds/features/{FEATURE_ID}-{FEATURE_SLUG} (feature-scoped only)
- `FEATURE_SLUG` — kebab-case slug for {FEATURE_ID} from REGISTRY.md (feature-scoped only)
- `OUTPUT_FOLDER` — {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID} (feature-scoped only; MUST already exist)
- `SCREENSHOTS_FOLDER` — {OUTPUT_FOLDER}/artifacts/screenshots (feature-scoped; visual-regression snapshots when applicable)
- `TEST_RUN_FOLDER` — {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{TEST_RUN_ID} (standalone only)

Generate `TEST_RUN_ID` once at session start in the contract format `YYYY-MM-DD-[a-z0-9]{8}` using `python3 -c import secrets; print(secrets.token_hex(4))`. Do not use: uuid4.

Session setup: create the run under `planning-mds/operations/evidence/`, initialize `evidence-manifest.json` (status `draft`) with the active contract version stamped, create the base run files (README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log) and artifact subdirs (coverage, diffs, test-results, security, screenshots). Run `agents/scripts/init-run.py` to perform this.

Load context in this order, then navigate rather than eager-load:
1. `agents/ROUTER.md`
2. `agents/agent-map.yaml`
3. `agents/docs/AGENT-USE.md`
4. `agents/actions/test.md`
5. `agents/quality-engineer/SKILL.md`
6. `feature-scoped only: {FEATURE_PATH}/feature-assembly-plan.md, {FEATURE_PATH}/STATUS.md, the feature's story files, {OUTPUT_FOLDER}/evidence-manifest.json`

Gates (run each stage through `agents/scripts/run-gate.py`, in order):
- **T0 — Test plan** (role: quality-engineer; artifacts: test-plan.md)
    - judgment: Produce and review test-plan.md with the §14 headings: story-to-AC mapping; unit/component/integration/
E2E/API/accessibility strategy; the developer-vs-QE test-ownership split; test data/fixtures; and the
happy/edge/error/auth/accessibility/regression case matrix. Result recorded.
- **T1 — Test execution** (role: quality-engineer; artifacts: test-execution-report.md)
    - judgment: Run tests INSIDE the application runtime containers; do not mock runtime layers in integration/E2E when
raw runtime is available. test-execution-report.md (§14): commands executed, pass/fail counts, skipped
tests + rationale, raw test artifact paths, failed/retried command history, AC coverage, Result. Copy or
reference raw output under {OUTPUT_FOLDER}/artifacts/test-results (or {TEST_RUN_FOLDER}/artifacts).
- **T2 — Coverage** (role: quality-engineer; artifacts: coverage-report.md)
    - judgment: coverage-report.md ALWAYS exists — even when coverage is waived (§10). §14 headings: coverage target and
actual per layer, raw artifact paths, feature-scoped notes, and (if coverage cannot be produced) a waiver
with owner/date/scope/follow-up, Result. Coverage targets are feature-scoped per §29 risk mitigation — do
not apply generic universal thresholds. Store raw coverage output under the coverage artifacts folder.
- **T3 — Self-review gate** (role: quality-engineer; artifacts: none)
    - judgment: QE self-checks the three reports for completeness and accuracy: every planned layer is executed or its
skip is justified, findings cite specific files, and every artifact path in the reports resolves (unresolved
test-result or screenshot references fail — test_results_reference_missing_fails / screenshot_reference_missing_fails).
- **T4 — Quality gate** (role: quality-engineer; artifacts: none)
    - judgment: The feature-scoped coverage and pass-rate thresholds are met, or a waiver is accepted (a coverage waiver
still needs PM acceptance at closeout, handled at G8). Artifact paths are required — summary prose alone is
not evidence for a passing gate.
- **T5 — Stage validation (feature-scoped only)** (role: quality-engineer; artifacts: none)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G2` (cwd: framework, timeout: 600s)
    - judgment: Run the op above ONLY in feature-scoped mode — G2 is where the QE reports are first required (they are
reconfirmed at the parent feature's G5). In standalone mode there is no feature scope: confirm the six §8
base run files are complete and apply no feature-stage validation.

Severity gate profile: `none` (compute allowed outcomes with `agents/scripts/gate_policy.py`; coverage floor is 80%).

Ownership (strict):
- **quality-engineer** owns: test-plan.md, test-execution-report.md, coverage-report.md

Forbidden:
- Generate run IDs with uuid4.
- Write QE reports outside {OUTPUT_FOLDER} (feature-scoped) or {TEST_RUN_FOLDER} (standalone).
- Create a new run folder in feature-scoped mode — use the existing {OUTPUT_FOLDER}.
- Skip coverage-report.md — the file must exist even when coverage is waived (§10).
- Mock runtime layers in integration/E2E tests when raw runtime is available.
- Cite summary prose alone as evidence for a passing gate; artifact paths are required.
- Apply generic universal coverage thresholds; coverage targets are feature-scoped per §29 risk mitigation.

Stop conditions:
- coverage-report.md missing (missing_coverage_report_fails).
- test-execution-report.md missing (missing_test_execution_fails).
- test-plan.md missing (missing_test_plan_fails).
- A coverage waiver is requested without PM acceptance at closeout (handled at G8).
- INSUFFICIENT_CONTEXT occurs — escalate, open raw artifacts, do not proceed on weak matches.

Conflict resolution:
- coverage target met but a story has no test -> fail; add a test or document the AC exception.
- coverage-report.md exists but raw artifacts missing -> fail (coverage_claim_without_artifact_fails).
- test-execution-report.md cites an artifact path that does not resolve -> fail (test_results_reference_missing_fails).
- coverage-report.md waiver missing PM acceptance at closeout -> handled by G8 (coverage_waiver_missing_pm_acceptance_fails).

Note (evidence_outputs): In feature-scoped mode also update {OUTPUT_FOLDER}/evidence-manifest.json role_results for Quality Engineer
with required_artifacts=[test-plan.md, test-execution-report.md, coverage-report.md] and
verdict_artifact=test-execution-report.md; when coverage is waived, populate waivers.coverage with
required/reason/owner/approved_on/follow_up. Copy or reference raw test results, coverage, and (when
applicable) visual-regression screenshots under the run's artifacts/ subfolders.

Note (modes): feature-scoped: FEATURE_ID + RUN_ID (the parent feature run) are required; OUTPUT_FOLDER MUST already exist
(do NOT create a new run folder); the QE reports and manifest updates land in the parent feature run and feed
its G2/G5. standalone: generate TEST_RUN_ID and create TEST_RUN_FOLDER; the run produces NO feature evidence
package and does NOT satisfy the per-feature QE requirement — the corresponding feature.md run must still
produce its own G2 evidence.

Note (session_setup): Echo the resolved absolute {PRODUCT_ROOT} on the first turn before any command. Generate TEST_RUN_ID once in
contract format (an ISO YYYY-MM-DD date plus a secrets.token_hex(4) suffix); never uuid4. feature-scoped: no
run-folder creation; ensure the artifacts/test-results, artifacts/coverage, and artifacts/screenshots
subfolders exist under OUTPUT_FOLDER. standalone: mkdir TEST_RUN_FOLDER/artifacts/{test-results,coverage} and
initialize the six §8 base run files.

Note (telemetry): Test commands run inside application runtime containers; append every shell command to the run's commands.log
per the §13 JSONL schema (schema_version, timestamp with timezone, cwd, command, exit_code, artifacts[],
redactions[]) with artifact paths recorded. Do not leak secrets — secret-pattern checks fail the run.

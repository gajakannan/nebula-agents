<!-- GENERATED from agents/actions/spec/feature.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action feature -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


CONTRACT: Feature Evidence Contract | SCOPE: feature-completion | POLICY: 2026-07-11

REQUIRED_INPUTS:
- FEATURE_ID [F####]
OPTIONAL_INPUTS:
- MODE =default:clean
- SLICE_ORDER_SOURCE =default:assembly-plan
- SLICE_ORDER
- PRODUCT_ROOT =default:sister-repo

RUN_ID: var=RUN_ID format=YYYY-MM-DD-[a-z0-9]{8} method=python3 -c import secrets; print(secrets.token_hex(4)) forbidden=uuid4
SESSION_SETUP: init-run.py -> planning-mds/operations/evidence/... manifest=draft base_files=[README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log] artifacts=[coverage, diffs, test-results, security, screenshots]
CONTEXT_PREAMBLE: agents/ROUTER.md -> agents/agent-map.yaml -> agents/docs/AGENT-USE.md

GATES:
- G0 role=architect artifacts=[g0-assembly-plan-validation.md]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G0` (cwd: framework, timeout: 300s)
- G1 role=devops artifacts=[g1-runtime-preflight.md]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G1` (cwd: framework, timeout: 300s)
- G2 role=backend-developer artifacts=[g2-self-review.md, g2-deployability-check.md]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G2` (cwd: framework, timeout: 300s)
- G3 role=quality-engineer artifacts=[test-plan.md, test-execution-report.md]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G3` (cwd: framework, timeout: 600s)
- G4 role=quality-engineer artifacts=[coverage-report.md]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G4` (cwd: framework, timeout: 300s)
- G5 role=code-reviewer artifacts=[code-review-report.md, signoff-ledger.md]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G5` (cwd: framework, timeout: 300s)
- G6 role=security artifacts=[security-review-report.md]
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G6` (cwd: framework, timeout: 300s)
- G7 role=architect artifacts=[kg-reconciliation.md]
    - run `python3 {PRODUCT_ROOT}/scripts/kg/compile.py` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - FORBID --write-coverage-report :: path-sensitive; deferred to G8 after the archive move relocates evidence paths
- G8 role=product-manager artifacts=[pm-closeout.md]
    - MANUAL checkpoint `archive-move`: Update trackers and move the feature folder to its archived path. (requires: pm-closeout.md, signoff-ledger.md; produces: archived-feature-folder)
    - run `python3 agents/product-manager/scripts/patch-prior-manifest.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --new-run-id {RUN_ID}` (cwd: framework, timeout: 120s)
    - write `latest-run.json` after `patch-prior-manifest`
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout` (cwd: framework, timeout: 300s)

SEVERITY_GATE: profile=standard tool=gate_policy.py coverage_min_pct=80
FORBIDDEN:
- Authoring kg-source shards during PM closeout (G7 owns shaping; G8 verifies).
- Running gate validation commands directly instead of through the gate driver.
STOP_CONDITIONS:
- A historical evidence fixture changes verdict without an approved new contract version.
- An executable string or shell invocation becomes reachable from spec content.
NOTE[g2_scope_booleans]: Set frontend_in_scope=true when any changed_paths[] entry matches
experience/**; security_sensitive_scope=true for auth, secrets, or crypto
changes; runtime_bearing=true when a service boot path changes.

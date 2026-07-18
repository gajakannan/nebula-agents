<!-- GENERATED from agents/actions/spec/feature.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action feature -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


This prompt encodes the **Feature Evidence Contract** (scope `feature-completion`, policy `2026-07-11`).

Required inputs:
- `FEATURE_ID` (format `F####`)

Optional inputs (defaults apply when omitted):
- `MODE` — default `clean`
- `SLICE_ORDER_SOURCE` — default `assembly-plan`
- `SLICE_ORDER`
- `PRODUCT_ROOT` — default `sister-repo`

Generate `RUN_ID` once at session start in the contract format `YYYY-MM-DD-[a-z0-9]{8}` using `python3 -c import secrets; print(secrets.token_hex(4))`. Do not use: uuid4.

Session setup: create the run under `planning-mds/operations/evidence/`, initialize `evidence-manifest.json` (status `draft`) with the active contract version stamped, create the base run files (README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log) and artifact subdirs (coverage, diffs, test-results, security, screenshots). Run `agents/scripts/init-run.py` to perform this.

Load context in this order, then navigate rather than eager-load:
1. `agents/ROUTER.md`
2. `agents/agent-map.yaml`
3. `agents/docs/AGENT-USE.md`

Gates (run each stage through `agents/scripts/run-gate.py`, in order):
- **G0 — Architect assembly plan authoring and validation** (role: architect; artifacts: g0-assembly-plan-validation.md)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G0` (cwd: framework, timeout: 300s)
    - judgment: Author or reconcile the assembly plan; validate scope split, dependencies,
checkpoints, and ownership; initialize the Required Signoff Roles matrix.
- **G1 — DevOps runtime preflight** (role: devops; artifacts: g1-runtime-preflight.md)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G1` (cwd: framework, timeout: 300s)
    - judgment: Verify the runtime boots and required services are reachable when the
slice is runtime-bearing; otherwise record the waiver rationale.
- **G2 — Implementation self-review and deployability** (role: backend-developer; artifacts: g2-self-review.md, g2-deployability-check.md)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G2` (cwd: framework, timeout: 300s)
    - judgment: Set scope booleans (frontend_in_scope, security_sensitive_scope,
runtime_bearing, deployment_config_changed) from changed_paths; review the
slice against acceptance criteria before handoff.
- **G3 — Quality engineering test execution** (role: quality-engineer; artifacts: test-plan.md, test-execution-report.md)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G3` (cwd: framework, timeout: 600s)
- **G4 — Coverage floor** (role: quality-engineer; artifacts: coverage-report.md)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G4` (cwd: framework, timeout: 300s)
    - judgment: Coverage floor is `coverage_min_pct` (owned by _contract.yaml). Do not
restate the numeric threshold in prose.
- **G5 — Code review signoff** (role: code-reviewer; artifacts: code-review-report.md, signoff-ledger.md)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G5` (cwd: framework, timeout: 300s)
- **G6 — Security review** (role: security; artifacts: security-review-report.md)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G6` (cwd: framework, timeout: 300s)
- **G7 — Architect knowledge-graph reconciliation** (role: architect; artifacts: kg-reconciliation.md)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/compile.py` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - constraint: `--write-coverage-report` forbidden — path-sensitive; deferred to G8 after the archive move relocates evidence paths
- **G8 — Product manager closeout** (role: product-manager; artifacts: pm-closeout.md)
    - MANUAL checkpoint `archive-move`: Update trackers and move the feature folder to its archived path. (requires: pm-closeout.md, signoff-ledger.md; produces: archived-feature-folder)
    - run `python3 agents/product-manager/scripts/patch-prior-manifest.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --new-run-id {RUN_ID}` (cwd: framework, timeout: 120s)
    - write `latest-run.json` after `patch-prior-manifest`
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout` (cwd: framework, timeout: 300s)

Severity gate profile: `standard` (compute allowed outcomes with `agents/scripts/gate_policy.py`; coverage floor is 80%).

Forbidden:
- Authoring kg-source shards during PM closeout (G7 owns shaping; G8 verifies).
- Running gate validation commands directly instead of through the gate driver.

Stop conditions:
- A historical evidence fixture changes verdict without an approved new contract version.
- An executable string or shell invocation becomes reachable from spec content.

Note (g2_scope_booleans): Set frontend_in_scope=true when any changed_paths[] entry matches
experience/**; security_sensitive_scope=true for auth, secrets, or crypto
changes; runtime_bearing=true when a service boot path changes.

<!-- GENERATED from agents/actions/spec/plan-review.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action plan-review -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


This prompt encodes the **Feature Evidence Contract** (scope `read-only-audit`, policy `2026-07-11`).

Required inputs:
- `PLAN_SCOPE`
- `TARGET` (format `F#### | comma-separated F#### list | project`)

Optional inputs (defaults apply when omitted):
- `DIFF_RANGE`
- `PRODUCT_ROOT` — default `sister-repo`

Auto-resolved (do not set; SESSION_SETUP / the orchestrator compute these):
- `FEATURE_PATH` — {PRODUCT_ROOT}/planning-mds/features/{TARGET}-{FEATURE_SLUG} when PLAN_SCOPE=feature
- `FEATURE_SLUG` — kebab-case slug for TARGET from REGISTRY.md when PLAN_SCOPE=feature
- `PLAN_REVIEW_RUN_FOLDER` — {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{PLAN_REVIEW_RUN_ID}

Generate `PLAN_REVIEW_RUN_ID` once at session start in the contract format `YYYY-MM-DD-[a-z0-9]{8}` using `python3 -c import secrets; print(secrets.token_hex(4))`. Do not use: uuid4.

Session setup: create the run under `planning-mds/operations/evidence/`, initialize `evidence-manifest.json` (status `draft`) with the active contract version stamped, create the base run files (README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log) and artifact subdirs (coverage, diffs, test-results, security, screenshots). Run `agents/scripts/init-run.py` to perform this.

Load context in this order, then navigate rather than eager-load:
1. `agents/ROUTER.md`
2. `agents/agent-map.yaml`
3. `agents/docs/AGENT-USE.md`
4. `agents/actions/plan-review.md`
5. `agents/actions/plan.md`
6. `agents/actions/feature.md`
7. `role SKILLs: agents/product-manager/SKILL.md, agents/architect/SKILL.md, agents/code-reviewer/SKILL.md`
8. `feature scope: {FEATURE_PATH}/**; plus BLUEPRINT.md, REGISTRY.md, ROADMAP.md, KG + architecture/API/schema/security artifacts as needed`

Gates (run each stage through `agents/scripts/run-gate.py`, in order):
- **PR0 — Scope lock** (role: product-manager; artifacts: action-context.md)
    - judgment: Record PLAN_SCOPE, TARGET, DIFF_RANGE, the resolved paths, and the review boundaries in
action-context.md. Use lookup.py for feature routing when PLAN_SCOPE includes a feature — treat its
output as first-pass context only, never authoritative over raw artifacts.
- **PR1 — Parallel readiness review** (role: product-manager; artifacts: plan-review-report.md)
    - judgment: Three role lanes in parallel (each owns its report section): PM — requirements, stories, mutation
contracts, UI/screen readiness, trackers; Architect — API/schema, data/workflow, authorization, ADR/NFR,
KG/ontology alignment; Code Reviewer — vertical-slice buildability, role handoffs, testability,
dependencies, risk hotspots. Do NOT require feature-assembly-plan.md as a plan deliverable. Reviewers do
not repair plan artifacts during review.
- **PR2 — Validator pass** (role: product-manager; artifacts: none)
    - run `python3 agents/product-manager/scripts/validate-stories.py {FEATURE_PATH}` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/validate-trackers.py` (cwd: framework, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - run `python3 agents/scripts/validate_templates.py` (cwd: framework, timeout: 300s)
    - judgment: validate-stories.py {FEATURE_PATH} applies in feature scope; iterate it per feature for feature-set and
skip it (record why) for project scope. All PR2 validators are read-only. Record exit code, summary, and
artifact path for each command in lifecycle-gates.log.
- **PR3 — Self-review gate** (role: product-manager; artifacts: none)
    - judgment: Each reviewer verifies that its findings cite exact files/sections and that any skipped item is
explicitly justified. Do not downgrade missing build-critical detail to low severity.
- **PR4 — Readiness gate** (role: product-manager; artifacts: none)
    - judgment: Compute the readiness verdict with gate_policy.py (profile review-family): critical > 0 -> NOT READY;
critical = 0 and high > 0 -> CONDITIONALLY READY; critical = 0 and high = 0 -> READY. A missing
build-critical owner is NOT READY.

Severity gate profile: `review-family` (compute allowed outcomes with `agents/scripts/gate_policy.py`; coverage floor is 80%).

Ownership (strict):
- **architect** owns: Architecture Readiness section findings
- **code-reviewer** owns: Buildability Challenge section findings
- **product-manager** owns: Product Readiness section findings

Forbidden:
- Generate PLAN_REVIEW_RUN_ID with uuid4.
- Edit plan artifacts, KG artifacts, trackers, stories, contracts, schemas, architecture files, or product source files.
- Write into any feature evidence package.
- Approve from prior approval tokens, summaries, or checklists without raw artifact inspection.
- Treat lookup/KG mappings as authoritative over raw artifacts.
- Require feature-assembly-plan.md as a plan deliverable.
- Downgrade missing build-critical detail to low severity.
- Widen review scope outside PLAN_SCOPE and TARGET except to record discovered impact.

Stop conditions:
- The target scope cannot be identified.
- Required raw artifacts are missing and cannot be located.
- lookup.py returns only ambiguous or low-confidence matches for the declared target.
- A validator failure prevents evidence-backed readiness.
- Reviewers cannot cite concrete files/sections for PR4.

Conflict resolution:
- raw artifact vs KG mapping -> raw wins; record a KG drift finding.
- prior approval vs current artifact gap -> the current artifact gap wins.
- PM and Architect disagree -> record both and escalate at PR4.
- missing build-critical owner -> NOT READY.

Note (preconditions): plan.md completed for TARGET; Phase A and Phase B approval decisions are recorded (or missing approvals are
in review scope); tracker sync and ontology sync completed (or their failures are in review scope); TARGET
resolves to concrete feature, feature-set, or project planning artifacts.

Note (read_only): plan-review READS but never writes plan / KG / tracker / feature evidence artifacts. Repair ownership stays
with the original lifecycle owners (plan.md / targeted rework); reviewers never repair during review — a
NOT READY / CONDITIONALLY READY verdict routes the fix back to the owner.

Note (report_sections): plan-review-report.md required sections: Decision; Findings By Severity; Product Readiness; Architecture
Readiness; Buildability Challenge; Validation Evidence; Artifact Trace. README.md summarizes the readiness
state and open follow-ups; gate-decisions.md records PR0 through PR4.

Note (session_setup): Echo the resolved absolute {PRODUCT_ROOT} on the first turn. Generate PLAN_REVIEW_RUN_ID once in contract
format (an ISO YYYY-MM-DD date plus a secrets.token_hex(4) suffix); never uuid4. Create
PLAN_REVIEW_RUN_FOLDER and its artifacts/ and initialize the six §8 base run files (README.md,
action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log).

Note (telemetry): Append every shell command to {PLAN_REVIEW_RUN_FOLDER}/commands.log per the §13 JSONL schema
(schema_version, timestamp with timezone, cwd, command, exit_code, artifacts[], redactions[]).

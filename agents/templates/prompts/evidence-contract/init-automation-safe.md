<!-- GENERATED from agents/actions/spec/init.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action init -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


CONTRACT: Feature Evidence Contract | SCOPE: base-run-only | POLICY: 2026-07-11

REQUIRED_INPUTS:
- PROJECT_NAME [string]
- DOMAIN_DESCRIPTION [1-2 sentence summary]
- TARGET_USERS [[role, role, ...]]
- CORE_ENTITIES [[entity, entity, ...]]
OPTIONAL_INPUTS:
- PRODUCT_ROOT =default:NEBULA_PRODUCT_ROOT env var, or sister-repo ../<product-repo>
AUTO_RESOLVED:
- INIT_RUN_FOLDER = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{INIT_RUN_ID}

RUN_ID: var=INIT_RUN_ID format=YYYY-MM-DD-[a-z0-9]{8} method=python3 -c import secrets; print(secrets.token_hex(4)) forbidden=uuid4
SESSION_SETUP: init-run.py -> planning-mds/operations/evidence/... manifest=draft base_files=[README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log] artifacts=[coverage, diffs, test-results, security, screenshots]
CONTEXT: agents/ROUTER.md -> agents/agent-map.yaml -> agents/docs/AGENT-USE.md -> agents/actions/init.md -> agents/product-manager/SKILL.md (initialization mode) -> agents/templates/** (templates for the scaffolded files)

GATES:
- I0 role=product-manager artifacts=[action-context.md]
- I1 role=product-manager artifacts=[]
- I2 role=product-manager artifacts=[BLUEPRINT.md]
- I3 role=product-manager artifacts=[REGISTRY.md, ROADMAP.md]
- I4 role=product-manager artifacts=[]
- I5 role=product-manager artifacts=[]
- I6 role=product-manager artifacts=[]
    - run `python3 agents/product-manager/scripts/validate-trackers.py` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT}` (cwd: framework, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-symbols` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - run `python3 agents/scripts/validate_templates.py` (cwd: framework, timeout: 300s)

SEVERITY_GATE: profile=none tool=gate_policy.py coverage_min_pct=80
OWNERSHIP:
- product-manager: every scaffolded file (initialization mode)
FORBIDDEN:
- Generate INIT_RUN_ID with uuid4.
- Scaffold into a non-empty {PRODUCT_ROOT} without explicit operator confirmation.
- Skip the evidence directory bootstrap — the product must have planning-mds/operations/evidence/ ready for the first feature run.
- Pre-populate REGISTRY.md with non-empty Archived or Retired tables; both start empty.
- Set the Evidence Contract Effective Date earlier than the framework default (must be 2026-05-19 or later for new products).
STOP_CONDITIONS:
- The operator refuses to confirm scaffolding into a non-empty {PRODUCT_ROOT}.
- Any validator exits non-zero at I6 (fix the root cause before init can complete).
- INSUFFICIENT_CONTEXT for any required input.
CONFLICT_RESOLUTION:
- operator wants an effective date earlier than the framework default -> refuse; new products inherit the framework default at minimum.
- operator wants to backfill historical features during init -> out of scope for init; init creates an empty registry only.
NOTE[evidence_readme]: The product's planning-mds/operations/evidence/README.md gets the sections Base Run Profile (§8), Feature
Evidence Profile (§9), and Global Lanes (§20), plus a Path Class Extensions section (§7) that starts empty —
the operator fills product-specific globs there after I4 for non-default layouts.
NOTE[preconditions]: nebula-agents is checked out and is the current session working directory; {PRODUCT_ROOT} is resolved and
either empty or accepting scaffold; the operator has basic project context (domain, goals, target users,
initial entities).
NOTE[session_setup]: Resolve {PRODUCT_ROOT} per agents/docs/AGENT-USE.md (operator input, the NEBULA_PRODUCT_ROOT env var, or the
default ../<product-repo>) and echo the resolved absolute path. Confirm it is empty or a new repo accepting
scaffold. Mint INIT_RUN_ID once in contract format (an ISO YYYY-MM-DD date plus a secrets.token_hex(4)
suffix); never uuid4. Create {INIT_RUN_FOLDER} (after scaffolding lands operations/evidence/) and initialize
the six §8 base run files.
NOTE[telemetry]: Append every shell command to {INIT_RUN_FOLDER}/commands.log per the §13 JSONL schema (schema_version,
timestamp with timezone, cwd, command, exit_code, artifacts[], redactions[]) once the folder exists.

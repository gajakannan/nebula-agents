<!-- GENERATED from agents/actions/spec/init.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action init -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


This prompt encodes the **Feature Evidence Contract** (scope `base-run-only`, policy `2026-07-11`).

Required inputs:
- `PROJECT_NAME` (format `string`)
- `DOMAIN_DESCRIPTION` (format `1-2 sentence summary`)
- `TARGET_USERS` (format `[role, role, ...]`)
- `CORE_ENTITIES` (format `[entity, entity, ...]`)

Optional inputs (defaults apply when omitted):
- `PRODUCT_ROOT` — default `NEBULA_PRODUCT_ROOT env var, or sister-repo ../<product-repo>`

Auto-resolved (do not set; SESSION_SETUP / the orchestrator compute these):
- `INIT_RUN_FOLDER` — {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{INIT_RUN_ID}

Generate `INIT_RUN_ID` once at session start in the contract format `YYYY-MM-DD-[a-z0-9]{8}` using `python3 -c import secrets; print(secrets.token_hex(4))`. Do not use: uuid4.

Session setup: create the run under `planning-mds/operations/evidence/`, initialize `evidence-manifest.json` (status `draft`) with the active contract version stamped, create the base run files (README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log) and artifact subdirs (coverage, diffs, test-results, security, screenshots). Run `agents/scripts/init-run.py` to perform this.

Load context in this order, then navigate rather than eager-load:
1. `agents/ROUTER.md`
2. `agents/agent-map.yaml`
3. `agents/docs/AGENT-USE.md`
4. `agents/actions/init.md`
5. `agents/product-manager/SKILL.md (initialization mode)`
6. `agents/templates/** (templates for the scaffolded files)`

Gates (run each stage through `agents/scripts/run-gate.py`, in order):
- **I0 — Project inputs captured** (role: product-manager; artifacts: action-context.md)
    - judgment: Record PROJECT_NAME, DOMAIN_DESCRIPTION, TARGET_USERS, and CORE_ENTITIES in action-context.md
(Lifecycle Stage = "Init", Scope Boundaries = "Bootstrap only").
- **I1 — PRODUCT_ROOT scaffold** (role: product-manager; artifacts: none)
    - judgment: Confirm {PRODUCT_ROOT} is empty or a new repo willing to accept scaffolded files (do not scaffold into a
non-empty root without explicit operator confirmation), then create the canonical directory structure.
- **I2 — BLUEPRINT template** (role: product-manager; artifacts: BLUEPRINT.md)
    - judgment: Produce {PRODUCT_ROOT}/planning-mds/BLUEPRINT.md from the template.
- **I3 — Registry + roadmap** (role: product-manager; artifacts: REGISTRY.md, ROADMAP.md)
    - judgment: Produce REGISTRY.md with EMPTY Active/Planned/Archived/Retired sections and ROADMAP.md with EMPTY
Now/Next/Later/Completed sections. Never pre-populate the Archived or Retired tables.
- **I4 — Evidence infrastructure** (role: product-manager; artifacts: none)
    - judgment: Create planning-mds/operations/evidence/ with a README explaining base run vs feature profile vs global
lanes (§§7, 8, 9, 20) and a Path Class Extensions section (§7) EMPTY by default. If the product's intended
top-level layout differs from the framework defaults (engine/, experience/) — e.g. a monorepo using
apps/api/, apps/web/, or services/ — the operator MUST populate Path Class Extensions before the first
feature action; init emits an info notice when BLUEPRINT.md mentions a non-default layout and the
extensions section is still empty. The Evidence Contract Effective Date must be the framework default
(2026-05-19) or later — never earlier.
- **I5 — KG infrastructure** (role: product-manager; artifacts: none)
    - judgment: Create planning-mds/knowledge-graph/ with empty solution-ontology.yaml, canonical-nodes.yaml,
feature-mappings.yaml, and code-index.yaml.
- **I6 — Validator sanity** (role: product-manager; artifacts: none)
    - run `python3 agents/product-manager/scripts/validate-trackers.py` (cwd: framework, timeout: 300s)
    - run `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT}` (cwd: framework, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-symbols` (cwd: product, timeout: 300s)
    - run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` (cwd: product, timeout: 300s)
    - run `python3 agents/scripts/validate_templates.py` (cwd: framework, timeout: 300s)
    - judgment: Run all validators against the freshly-scaffolded empty product; each must exit 0 (this is also the exit
validation sweep). The registry-wide validate-feature-evidence scan should report 0 governed features and
0 retired records. Any non-zero exit means the root cause must be fixed before init can complete.

Severity gate profile: `none` (compute allowed outcomes with `agents/scripts/gate_policy.py`; coverage floor is 80%).

Ownership (strict):
- **product-manager** owns: every scaffolded file (initialization mode)

Forbidden:
- Generate INIT_RUN_ID with uuid4.
- Scaffold into a non-empty {PRODUCT_ROOT} without explicit operator confirmation.
- Skip the evidence directory bootstrap — the product must have planning-mds/operations/evidence/ ready for the first feature run.
- Pre-populate REGISTRY.md with non-empty Archived or Retired tables; both start empty.
- Set the Evidence Contract Effective Date earlier than the framework default (must be 2026-05-19 or later for new products).

Stop conditions:
- The operator refuses to confirm scaffolding into a non-empty {PRODUCT_ROOT}.
- Any validator exits non-zero at I6 (fix the root cause before init can complete).
- INSUFFICIENT_CONTEXT for any required input.

Conflict resolution:
- operator wants an effective date earlier than the framework default -> refuse; new products inherit the framework default at minimum.
- operator wants to backfill historical features during init -> out of scope for init; init creates an empty registry only.

Note (evidence_readme): The product's planning-mds/operations/evidence/README.md gets the sections Base Run Profile (§8), Feature
Evidence Profile (§9), and Global Lanes (§20), plus a Path Class Extensions section (§7) that starts empty —
the operator fills product-specific globs there after I4 for non-default layouts.

Note (preconditions): nebula-agents is checked out and is the current session working directory; {PRODUCT_ROOT} is resolved and
either empty or accepting scaffold; the operator has basic project context (domain, goals, target users,
initial entities).

Note (session_setup): Resolve {PRODUCT_ROOT} per agents/docs/AGENT-USE.md (operator input, the NEBULA_PRODUCT_ROOT env var, or the
default ../<product-repo>) and echo the resolved absolute path. Confirm it is empty or a new repo accepting
scaffold. Mint INIT_RUN_ID once in contract format (an ISO YYYY-MM-DD date plus a secrets.token_hex(4)
suffix); never uuid4. Create {INIT_RUN_FOLDER} (after scaffolding lands operations/evidence/) and initialize
the six §8 base run files.

Note (telemetry): Append every shell command to {INIT_RUN_FOLDER}/commands.log per the §13 JSONL schema (schema_version,
timestamp with timezone, cwd, command, exit_code, artifacts[], redactions[]) once the folder exists.

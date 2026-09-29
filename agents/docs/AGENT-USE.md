# Agent and Action Usage Guide

## Purpose

This guide shows how to invoke the framework in a fresh session:

- how to set up the session so `{NEBULA_PRODUCT_ROOT}` resolves
- when to use an **action** versus a direct **agent**
- how to structure prompts so agents read the right artifacts
- what each agent typically reads, updates, and validates

Use this guide with:

- `agents/README.md`
- `agents/actions/README.md`
- `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md`
- `agents/agent-map.yaml`
- `CONSUMER-CONTRACT.md`

`agents/agent-map.yaml` is the authoritative action-to-agent wiring source. Action `.md` files remain the human-readable execution docs.

## Session Setup

The framework is consumed as a sibling repo. Every session runs with these two fixed ideas:

- **Session working directory:** `nebula-agents` — the agent reads role definitions, actions, and templates from `agents/` here.
- **Implementation target:** `{NEBULA_PRODUCT_ROOT}` — a sibling product repo. All product-owned artifacts — `{NEBULA_PRODUCT_ROOT}/planning-mds/`, `{NEBULA_PRODUCT_ROOT}/engine/`, `{NEBULA_PRODUCT_ROOT}/experience/`, `{NEBULA_PRODUCT_ROOT}/neuron/`, and `{NEBULA_PRODUCT_ROOT}/scripts/kg/` — live under the product repo.

### Expected workspace layout

```
WORKSPACE_ROOT/
  nebula-agents/          # session working directory (this repo)
  <product-repo>/         # {NEBULA_PRODUCT_ROOT}, e.g. nebula-insurance-crm
```

`WORKSPACE_ROOT` must be outside any source backup of `nebula-crm`.

### Resolving `{NEBULA_PRODUCT_ROOT}`

`NEBULA_PRODUCT_ROOT` is the canonical product selection, whether supplied in a
pasted action prompt or exported in the shell. Normalize its value once to an
absolute path, then use `{NEBULA_PRODUCT_ROOT}` throughout the action.

1. Explicit operator selection (prompt `NEBULA_PRODUCT_ROOT` or script
   `--product-root`) wins over the environment. Conflicting explicit selections
   require clarification; no alternate root variable is supported.
2. Otherwise read the `NEBULA_PRODUCT_ROOT` environment variable.
3. If neither is supplied, ask for a product path. Scripts fail with an error.
   There is no default sibling product and no automatic selection of CWD.

A prompt value is valid even when the shell environment is empty. Pass that value
explicitly to the resolver; do not discard it because an environment check is empty.
Resolve `../` against the session's starting directory (normally `nebula-agents`)
**once, before changing directories**, using:

```sh
python3 agents/scripts/_product_root.py --product-root ../my-product
```

Omit the flag only when reading the actual environment. The command prints the
absolute path to stdout and its source to stderr. Echo that selection before
product discovery or writes. Use this absolute value for every `{NEBULA_PRODUCT_ROOT}`
reference, every `--product-root` argument (including init and resume), and every
agent handoff. An export in one tool shell may not persist into the next shell.
On resume, reuse the recorded absolute root and reject a conflicting selection.
Never infer the product from a feature ID or choose among sibling repositories.

Example pasted prompt (no shell export required):

```text
NEBULA_PRODUCT_ROOT = "../my-product"
FEATURE_ID = "F0002"
Follow agents/templates/prompts/evidence-contract/feature-operator-friendly.md.
```

Keep run-specific values in the invocation, rather than editing generated templates.

### Honoring `.agentignore`

For an opted-in product, load its blueprint and declared instruction text before work and after resume with `python3 agents/scripts/project_context.py --product-root <absolute-product-root> --action <action>`. Resolve the root explicitly; extension commands do not use the legacy fallback. A context error blocks the action. See [Project extensions](PROJECT-EXTENSIONS.md) for gate/CI usage and the current native-launcher limitation.

After resolving `{NEBULA_PRODUCT_ROOT}`, check for `{NEBULA_PRODUCT_ROOT}/.agentignore`
before broad product discovery. This file is a gitignore-style retrieval guard
for agents, not a Git ignore file. Honor it for broad reads, globs, greps, and
file-list operations. For product searches, prefer running from
`{NEBULA_PRODUCT_ROOT}` with `rg --ignore-file .agentignore ...`.

Bypass ignored paths only for explicit audit, validation, closeout, failure
triage, or user-requested inspection, and then read exact files rather than
whole folders. Full semantics live in `agents/docs/AGENTIGNORE.md`.

### What `{NEBULA_PRODUCT_ROOT}` prefixes

Every reference from `agents/**` to product-owned paths uses the `{NEBULA_PRODUCT_ROOT}` placeholder. At baseline the placeholder prefixes all product-owned trees: `{NEBULA_PRODUCT_ROOT}/scripts/kg/...`, `{NEBULA_PRODUCT_ROOT}/planning-mds/...`, `{NEBULA_PRODUCT_ROOT}/engine/...`, `{NEBULA_PRODUCT_ROOT}/experience/...`, `{NEBULA_PRODUCT_ROOT}/neuron/...`, and `{NEBULA_PRODUCT_ROOT}/bruno/...`.

Examples:

- `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/lookup.py <feature-id>` (product-owned KG tool)
- `pnpm --dir {NEBULA_PRODUCT_ROOT}/experience lint` (product frontend)
- Write scope: `{NEBULA_PRODUCT_ROOT}/engine/**` (product backend)

Framework-owned scripts stay framework-relative (no `{NEBULA_PRODUCT_ROOT}` prefix): `python3 agents/scripts/validate-genericness.py`, `python3 agents/scripts/run-lifecycle-gates.py`, `python3 agents/scripts/validate_templates.py`.

### Discovering product-specific concretes

Framework docs and templates do not hardcode product namespaces, API filenames, or entity names. The agent discovers these at session time from the product repo:

- **Tech stack** → `{NEBULA_PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`
- **Entity-to-file bindings** → `{NEBULA_PRODUCT_ROOT}/planning-mds/knowledge-graph/code-index.yaml` and `canonical-nodes.yaml`
- **API spec location** → declared in `{NEBULA_PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`; agents do not assume a filename

## Default Rule

Prefer **actions** for end-to-end workflows, approval gates, and multi-agent sequencing.

Use a direct **agent** prompt when:

- the work belongs to one role
- you are revising only one phase artifact set
- a gate requested targeted rework from a specific role
- you already know the exact feature and artifact scope

## Prompt Anatomy

Good direct-agent prompts usually include these parts:

1. Explicit activation
2. Target feature or scope path
3. Current status or problem statement
4. Ontology context when coverage exists
5. Required context files to read
6. Deliverables to create or update
7. Precedence rules if artifacts conflict
8. Validation commands and tracker updates

### Direct Agent Template

```text
Switch to <Agent Name> agent mode (agents/<role>/SKILL.md).

Work on <feature or scope> at <path>. The current state is <status>.

Read:
- <required file 1>
- <required file 2>
- <dependent artifacts>

Deliverables:
1. <deliverable 1>
2. <deliverable 2>

Constraints:
- <scope boundary>
- <precedence rule if artifacts conflict>

When done:
- update <status/tracker/docs files>
- run <validation command(s)>
```

### Ontology-Backed Addendum

When the target feature or story exists in
`{NEBULA_PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml`, add this block before the
raw file list:

```text
Ontology context:
- target: <feature or story id>
- retrieve via the CLIs (they join the KG yamls for you — do not load raw yamls into context):
  - python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/lookup.py <feature or story id>   # feature/story slice
  - python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/hint.py <path>                    # before any code search
  - python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/blast.py <node-or-file>          # impact radius before editing shared semantics
- use the returned slice (matching mapping entry + one hop) as the first-pass routing context
- open raw yamls under {NEBULA_PRODUCT_ROOT}/planning-mds/knowledge-graph/ ONLY to verify a
  detail or repair drift — never as the default retrieval path
- source precedence: raw feature/ADR/schema/API artifacts win over ontology mappings
- if ontology drift is found, repair the authoritative source first if needed,
  then repair the ontology mapping in the same change set
```

Use the ontology to resolve canonical workflow, workflow state, capability,
schema, ADR, and entity links. Do not treat it as a substitute for reading the linked raw
artifacts when details or verification matter. See
`agents/docs/CONTEXT-ENGINEERING.md` for *why* retrieval goes through the CLIs:
query an index, do not read the repo — raw yamls never enter context by default.

### KG CLI Tools

All KG tools are agent-agnostic and work from any terminal. The full CLI
reference, mental model, lifecycle triggers, and failure modes live in
**`agents/docs/KNOWLEDGE-GRAPH.md`**. For *why* these tools are shaped the way
they are — the select/compress/write/isolate strategy they serve — see
**`agents/docs/CONTEXT-ENGINEERING.md`**.

Most-common session invocations:

| When | Command |
|------|---------|
| Before any code search | `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/hint.py <path>` |
| Starting feature work | `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/lookup.py <feature-id>` |
| Before editing shared semantics | `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/blast.py <node-or-file>` |
| Long session start | `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/workstate.py --state-file <path> init --role <role> --scope <id> --run-id <uuid>` |
| Post-compaction recovery | `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/workstate.py --state-file <path> dump --compact` |
| Framework prompt-template check | `python3 agents/scripts/validate_templates.py` |

Agent-specific hook adapters (e.g., `.claude/settings.json` for Claude
Code) can wire `hint.py` into pre-search hooks, but the tools work
standalone.

### Action Template

```text
Run the <action> action defined in agents/actions/<action>.md.

Scope:
- <feature, repo, or release target>

Inputs:
- <required files or feature folders>

Execution notes:
- stop at required gates
- capture evidence per agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md
```

## Action Prompt Templates

Use the prompt templates in `agents/templates/prompts/` as canonical operator
starting points for action sessions. The evidence-contract variants are the
preferred prompts when the action must produce or review formal evidence.

- `agents/templates/prompts/plan-automation-safe.md`
- `agents/templates/prompts/plan-operator-friendly.md`
- `agents/templates/prompts/feature-automation-safe.md`
- `agents/templates/prompts/feature-operator-friendly.md`
- `agents/templates/prompts/evidence-contract/plan-review-automation-safe.md`
- `agents/templates/prompts/evidence-contract/plan-review-operator-friendly.md`
- `agents/templates/prompts/evidence-contract/feature-review-automation-safe.md`
- `agents/templates/prompts/evidence-contract/feature-review-operator-friendly.md`

These templates encode the current retrieval budget, gate IDs, required tool
invocations, and exit-validation order. Keep them aligned with the action docs
via `python3 agents/scripts/validate_templates.py`.

## Common Prompt Clauses

Use these clauses when they apply:

- `Before loading references, consult agents/ROUTER.md and load only the task-matched subset.`
- `Before broad product discovery, load {NEBULA_PRODUCT_ROOT}/.agentignore if present and honor it as a gitignore-style agent retrieval guard.`
- `Before searching code, run python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/hint.py <path> to get KG routing context.`
- `If ontology coverage exists, load the matching knowledge-graph entry before reading raw files.`
- `Use ontology mappings as compressed retrieval context only; source artifacts win on conflict.`
- `Treat {NEBULA_PRODUCT_ROOT}/planning-mds/operations/** as cold archive; start from evidence README, latest-run.json, and evidence-manifest.json, then read only exact files required by the task.`
- `If shared solution semantics changed, repair ontology drift in the same change set.`
- `Read the full feature folder at {NEBULA_PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}.`
- `Where the feature-assembly-plan conflicts with raw story text, follow the feature-assembly-plan.`
- `Do not invent scope outside the current feature boundary.`
- `Update STATUS.md before concluding.`
- `If trackers changed, re-run tracker validation before declaring done.`
- `If commands or examples are unverified, mark them explicitly instead of implying they were run.`
- `Do not restate context already loaded; reference it (path/id) instead of repeating it — output tokens are generated and uncached, the most expensive kind.`
- `Prefer structured/templated output; keep reports and STATUS rows within their length ceilings rather than narrating.`

## Ontology Ownership

Ownership rules (architect owns canonical shared layer; PM owns feature/
story/persona mappings; implementation agents flag drift rather than
silently redefine; reviewers treat unresolved drift as a consistency
issue) are documented in `agents/docs/KNOWLEDGE-GRAPH.md` § File Inventory
and § Lifecycle.

## STATUS.md Evidence Semantics

`STATUS.md` evidence rows are append-only audit history. To query "the current
verdict per (story, role)," compute it as a view over the table (latest row per
key), not by mutating or removing prior rows. The full signoff contract
(required columns, baseline/forced roles, evidence-path rules) lives in
`agents/docs/AGENT-OPS.md` → STATUS.md signoff.

## Agent Quick Reference

| Agent | Use When | Read First | Usually Updates | Typical Validation |
|------|----------|------------|-----------------|--------------------|
| `product-manager` | refining PRDs, stories, personas, MVP/future scope, tracker sync | `{NEBULA_PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`, feature folder, dependency PRDs, `TRACKER-GOVERNANCE.md` | feature `PRD.md`, stories, `README.md`, `STATUS.md`, trackers | `python3 agents/product-manager/scripts/validate-stories.py`, `python3 agents/product-manager/scripts/generate-story-index.py {NEBULA_PRODUCT_ROOT}/planning-mds/features/`, `python3 agents/product-manager/scripts/validate-trackers.py` |
| `architect` | data model, workflows, API contracts, ADRs, authorization, assembly plans | feature folder, `{NEBULA_PRODUCT_ROOT}/planning-mds/architecture/decisions/`, `{NEBULA_PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`, dependent PRDs | `{NEBULA_PRODUCT_ROOT}/planning-mds/architecture/**`, `{NEBULA_PRODUCT_ROOT}/planning-mds/api/*.yaml`, `{NEBULA_PRODUCT_ROOT}/planning-mds/schemas/*.json`, feature `feature-assembly-plan.md`, feature `STATUS.md` | `python3 agents/architect/scripts/validate-architecture.py {NEBULA_PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`, `python3 agents/architect/scripts/validate-api-contract.py <api-file>`, `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/blast.py <node>` before shared entity/workflow changes, `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` after ontology changes, tracker validation if trackers changed |
| `backend-developer` | implementing `{NEBULA_PRODUCT_ROOT}/engine/` changes from approved feature plans | feature folder, `feature-assembly-plan.md`, `{NEBULA_PRODUCT_ROOT}/planning-mds/api/`, `{NEBULA_PRODUCT_ROOT}/planning-mds/schemas/`, `{NEBULA_PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md` | `{NEBULA_PRODUCT_ROOT}/engine/**`, feature `STATUS.md`, feature `GETTING-STARTED.md` | `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/hint.py <path>` before searching, `sh agents/backend-developer/scripts/run-tests.sh --strict` or repo-standard backend test command |
| `frontend-developer` | implementing `{NEBULA_PRODUCT_ROOT}/experience/` screens, forms, API wiring, UX fixes | feature folder, `feature-assembly-plan.md`, screen specs, `{NEBULA_PRODUCT_ROOT}/planning-mds/api/`, `{NEBULA_PRODUCT_ROOT}/planning-mds/schemas/`, `agents/frontend-developer/references/ux-audit-ruleset.md` | `{NEBULA_PRODUCT_ROOT}/experience/**`, feature `STATUS.md`, feature `GETTING-STARTED.md` | `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/hint.py <path>` before searching, `pnpm --dir {NEBULA_PRODUCT_ROOT}/experience lint`, `pnpm --dir {NEBULA_PRODUCT_ROOT}/experience lint:theme`, `pnpm --dir {NEBULA_PRODUCT_ROOT}/experience build`, `pnpm --dir {NEBULA_PRODUCT_ROOT}/experience test`, plus `pnpm --dir {NEBULA_PRODUCT_ROOT}/experience test:visual:theme` when theme/styling changed |
| `ai-engineer` | implementing `{NEBULA_PRODUCT_ROOT}/neuron/`, LLM integrations, MCP servers, prompts, agent workflows | feature folder, architecture docs, AI requirements, backend integration contracts | `{NEBULA_PRODUCT_ROOT}/neuron/**`, feature `STATUS.md`, feature `GETTING-STARTED.md`, `{NEBULA_PRODUCT_ROOT}/neuron/README.md` | `pytest {NEBULA_PRODUCT_ROOT}/neuron/tests/` and project-standard AI integration/evaluation commands |
| `quality-engineer` | test planning, automated tests, coverage checks, E2E, performance, accessibility | stories, acceptance criteria, `feature-assembly-plan.md`, changed code, quality strategy | `{NEBULA_PRODUCT_ROOT}/engine/tests/**`, `{NEBULA_PRODUCT_ROOT}/experience/tests/**`, `{NEBULA_PRODUCT_ROOT}/neuron/tests/**`, feature `STATUS.md` | tier-specific test commands plus coverage artifacts; require evidence-backed pass decisions |
| `devops` | Docker, compose, CI/CD, env wiring, deployment architecture, ops scripts | architecture docs, changed app code, deployment requirements | `Dockerfile`, `docker-compose*.yml`, `.github/workflows/**`, `scripts/**`, deployment docs, feature `STATUS.md` | repo-standard container, CI, and health-check commands |
| `code-reviewer` | code quality review, acceptance criteria coverage, architecture/pattern compliance | changed code, feature folder, `{NEBULA_PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`, review action doc | feature `STATUS.md` and review findings artifacts | `python3 agents/code-reviewer/scripts/check-code-quality.py <path>`, `sh agents/code-reviewer/scripts/check-lint.sh`, `sh agents/code-reviewer/scripts/check-test-coverage.sh --min 80 --auto` as applicable |
| `security` | threat modeling, auth/authz review, OWASP review, security findings | feature folder, architecture/security artifacts, changed code | `{NEBULA_PRODUCT_ROOT}/planning-mds/security/**`, feature `STATUS.md` | `python3 agents/security/scripts/security-audit.py {NEBULA_PRODUCT_ROOT}/planning-mds/security`, plus available scan wrappers in `agents/security/scripts/` |
| `technical-writer` | API docs, runbooks, READMEs, developer guides, operator docs | implemented code, planning artifacts, architecture docs, existing docs | `docs/**`, `README.md` files, operator docs | validate commands/paths/links or mark them unverified |
| `blogger` | devlogs, release notes, technical posts, retrospectives | completed work, ADRs, feature docs, evidence artifacts | `docs/blog/**` or `blog/**` | technical accuracy review, redaction review, audience/objective check |

## Direct-Agent Prompt Starters

Use these as starting lines in fresh sessions:

- `product-manager`: `Switch to Product Manager agent mode (agents/product-manager/SKILL.md).`
- `architect`: `Switch to Architect agent mode (agents/architect/SKILL.md).`
- `backend-developer`: `Switch to Backend Developer agent mode (agents/backend-developer/SKILL.md).`
- `frontend-developer`: `Switch to Frontend Developer agent mode (agents/frontend-developer/SKILL.md).`
- `ai-engineer`: `Switch to AI Engineer agent mode (agents/ai-engineer/SKILL.md).`
- `quality-engineer`: `Switch to Quality Engineer agent mode (agents/quality-engineer/SKILL.md).`
- `devops`: `Switch to DevOps agent mode (agents/devops/SKILL.md).`
- `code-reviewer`: `Switch to Code Reviewer agent mode (agents/code-reviewer/SKILL.md).`
- `security`: `Switch to Security agent mode (agents/security/SKILL.md).`
- `technical-writer`: `Switch to Technical Writer agent mode (agents/technical-writer/SKILL.md).`
- `blogger`: `Switch to Blogger agent mode (agents/blogger/SKILL.md).`

## Detailed Examples

### Product Manager Example

```text
Switch to Product Manager agent mode (agents/product-manager/SKILL.md).

Refine F{NNNN} <feature slug> workflow ({NEBULA_PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}).

The PRD currently has a high-level feature statement, scope, architecture hints,
and traceability but zero user stories, no persona references, no screen specs,
and no workflows. The feature is in Draft status.

Read:
- {NEBULA_PRODUCT_ROOT}/planning-mds/BLUEPRINT.md
- {NEBULA_PRODUCT_ROOT}/planning-mds/COMMERCIAL-PC-CRM-RELEASE-PLAN.md
- the PRDs for F0006 dependency features
- {NEBULA_PRODUCT_ROOT}/planning-mds/features/TRACKER-GOVERNANCE.md

Deliverables:
1. Refine the target feature PRD and sharpen scope boundaries.
2. Clarify MVP versus Future scope explicitly.
3. Add user stories with acceptance criteria.
4. Update README.md and STATUS.md in the feature folder.
5. Update REGISTRY.md, ROADMAP.md, STORY-INDEX.md, and BLUEPRINT.md as needed.

Constraints:
- Clarify what this feature owns versus what it delegates to dependency features.
- Determine applicable rules and document them within the appropriate stories.

When done:
- run `python3 agents/product-manager/scripts/validate-stories.py {NEBULA_PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}`
- run `python3 agents/product-manager/scripts/generate-story-index.py {NEBULA_PRODUCT_ROOT}/planning-mds/features/`
- run `python3 agents/product-manager/scripts/validate-trackers.py`
```

### Architect Example

```text
Switch to Architect agent mode (agents/architect/SKILL.md).

Design the technical solution for F{NNNN} <feature slug> at
{NEBULA_PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}.

The Product Manager has completed story breakdown. Read the full feature folder
for PRD, stories, and acceptance criteria.

Also read:
- ontology files in `{NEBULA_PRODUCT_ROOT}/planning-mds/knowledge-graph/` first when the target feature has coverage
- {NEBULA_PRODUCT_ROOT}/planning-mds/architecture/decisions/
- {NEBULA_PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md
- dependent feature PRDs

Deliverables as applicable:
1. Data model
2. Workflow state machine
3. API contract
4. Authorization model
5. ADRs to create or update
6. `feature-assembly-plan.md` with implementation sequence, agent handoffs,
   integration checkpoints, and dependency stubs

Constraints:
- Cross-check data model, API, schemas, ERD, and Casbin alignment.
- Read the full feature folder. The feature-assembly-plan is the primary
  implementation spec.
- Where the assembly plan conflicts with raw story acceptance criteria, follow
  the assembly plan.

When done:
- update feature `STATUS.md`
- run `python3 agents/architect/scripts/validate-architecture.py {NEBULA_PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`
- run `python3 agents/architect/scripts/validate-api-contract.py <api-file>` for each changed contract
- run `python3 agents/product-manager/scripts/validate-trackers.py` if planning trackers changed
```

### Backend Developer Example

```text
Switch to Backend Developer agent mode (agents/backend-developer/SKILL.md).

Implement the backend slice for <feature> in `{NEBULA_PRODUCT_ROOT}/engine/`.

Read:
- the full feature folder
- `{NEBULA_PRODUCT_ROOT}/planning-mds/features/<feature>/feature-assembly-plan.md`
- `{NEBULA_PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
- relevant files in `{NEBULA_PRODUCT_ROOT}/planning-mds/api/` and `{NEBULA_PRODUCT_ROOT}/planning-mds/schemas/`

Deliverables:
1. Implement the planned `{NEBULA_PRODUCT_ROOT}/engine/` changes.
2. Add or update backend tests in `{NEBULA_PRODUCT_ROOT}/engine/tests/`.
3. Update feature `STATUS.md` and `GETTING-STARTED.md` with evidence and key paths.

Constraints:
- Follow the feature-assembly-plan when it conflicts with raw story text.
- Do not widen scope beyond the assigned backend slice.

When done:
- run `sh agents/backend-developer/scripts/run-tests.sh --strict`
```

## Action Quick Reference

| Action | Use When | Composes | Example Prompt |
|--------|----------|----------|----------------|
| `init` | starting a new repo or bootstrapping framework files | Product Manager | `Run the init action defined in agents/actions/init.md for this repository.` |
| `plan` | moving from idea to approved product and architecture specs | Product Manager -> Architect | `Run the plan action defined in agents/actions/plan.md for <feature or project>.` |
| `plan-review` | independently checking whether completed planning is ready to build | Product Manager + Architect + Code Reviewer | `Run the plan-review action defined in agents/actions/plan-review.md for <feature or project>.` |
| `build` | implementing a larger approved scope across the stack | Architect -> implementation agents -> reviews | `Run the build action defined in agents/actions/build.md for the approved scope in <feature folders>.` |
| `feature` | shipping one vertical slice end to end | Architect -> implementation agents -> parallel reviews | `Run the feature action defined in agents/actions/feature.md for <feature folder>.` |
| `feature-review` | independently checking whether a completed feature is truly done | PM + Architect + QE + Code Reviewer + Security (+ DevOps when needed) | `Run the feature-review action defined in agents/actions/feature-review.md for <feature folder>.` |
| `review` | getting code-quality and security review on changed work | Code Reviewer + Security | `Run the review action defined in agents/actions/review.md for the current diff and affected feature folders.` |
| `validate` | checking planning, architecture, and implementation alignment | Product Manager + Architect | `Run the validate action defined in agents/actions/validate.md for <feature or repo scope>.` |
| `test` | expanding or executing automated test coverage | Quality Engineer | `Run the test action defined in agents/actions/test.md for <feature or changed components>.` |
| `document` | producing READMEs, API docs, runbooks, or operator guides | Technical Writer | `Run the document action defined in agents/actions/document.md for <implemented scope>.` |
| `blog` | creating devlogs, retrospectives, and technical posts | Blogger | `Run the blog action defined in agents/actions/blog.md for <change set or release>.` |

## Action Usage Notes

- Use the action docs as the execution checklist.
- Capture evidence per `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md`.
- Stop at explicit approval, review, quality, or tracker-sync gates.
- If you need a one-role revision after a gate, switch back to the responsible agent directly instead of re-running the whole action blindly.

## Recommended Operator Pattern

1. Start with an **action** if the work spans multiple roles.
2. Switch to a direct **agent** only for targeted, scoped follow-up.
3. Keep prompts explicit about files, outputs, and validation.
4. Treat `STATUS.md` and tracker updates as part of the work, not optional cleanup.
5. For implementation work, prefer the feature folder and `feature-assembly-plan.md` over ad hoc verbal summaries.

## Feature Evidence Contract Quick Reference

Full contract — package shape, gate timeline, manifest, telemetry,
verdicts, validation, eligibility, waivers — lives in
**`agents/docs/AGENT-OPS.md`**. This is the per-role quick reference only.

Roles producing feature-evidence artifacts write into the canonical feature run folder:

```text
{NEBULA_PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}/
```

| Role | Required artifact(s) at the canonical run folder | Verdict artifact |
|------|--------------------------------------------------|------------------|
| Architect | `g0-assembly-plan-validation.md` (when required by STATUS.md) | same |
| Quality Engineer | `test-plan.md`, `test-execution-report.md`, `coverage-report.md` | `test-execution-report.md` |
| DevOps | `deployability-check.md`; `g1-runtime-preflight.md` when `runtime_bearing = true` | `deployability-check.md` |
| Code Reviewer | `code-review-report.md` | same |
| Security Reviewer | `security-review-report.md` (when forced or required) | same |
| Product Manager | `signoff-ledger.md`, `pm-closeout.md`, and the feature-index `latest-run.json` | n/a (PM closeout is a gate, not a role-results row by default) |

Recommendation severity is `low` / `medium` / `high` / `critical`; `high`/`critical` require a PM Acceptance Line in `pm-closeout.md` (see AGENT-OPS.md → Verdicts & Recommendations). `agents/actions/validate.md` runs write three validation reports into the **base run** path, not a feature package (see AGENT-OPS.md → The Gate Timeline).

# Agent and Action Usage Guide

## Purpose

This guide shows how to invoke the framework in a fresh session:

- how to set up the session so `{PRODUCT_ROOT}` resolves
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
- **Implementation target:** `{PRODUCT_ROOT}` — a sibling product repo. All product-owned artifacts — `{PRODUCT_ROOT}/planning-mds/`, `{PRODUCT_ROOT}/engine/`, `{PRODUCT_ROOT}/experience/`, `{PRODUCT_ROOT}/neuron/`, and `{PRODUCT_ROOT}/scripts/kg/` — live under the product repo.

### Expected workspace layout

```
WORKSPACE_ROOT/
  nebula-agents/          # session working directory (this repo)
  <product-repo>/         # {PRODUCT_ROOT}, e.g. nebula-insurance-crm
```

`WORKSPACE_ROOT` must be outside any source backup of `nebula-crm`.

### Resolving `{PRODUCT_ROOT}`

At session start, resolve `{PRODUCT_ROOT}` in this order:

1. Environment variable `NEBULA_PRODUCT_ROOT`, if set
2. Operator-provided value at session start ("the product repo is at X")
3. Default fallback: `../<product-repo>` relative to `nebula-agents` (for the reference insurance CRM consumer this is `../nebula-insurance-crm`)

Echo the resolved absolute path back as the first agent turn's output before any shell command runs.

### What `{PRODUCT_ROOT}` prefixes

Every reference from `agents/**` to product-owned paths uses the `{PRODUCT_ROOT}` placeholder. At baseline the placeholder prefixes all product-owned trees: `{PRODUCT_ROOT}/scripts/kg/...`, `{PRODUCT_ROOT}/planning-mds/...`, `{PRODUCT_ROOT}/engine/...`, `{PRODUCT_ROOT}/experience/...`, `{PRODUCT_ROOT}/neuron/...`, and `{PRODUCT_ROOT}/bruno/...`.

Examples:

- `python3 {PRODUCT_ROOT}/scripts/kg/lookup.py <feature-id>` (product-owned KG tool)
- `pnpm --dir {PRODUCT_ROOT}/experience lint` (product frontend)
- Write scope: `{PRODUCT_ROOT}/engine/**` (product backend)

Framework-owned scripts stay framework-relative (no `{PRODUCT_ROOT}` prefix): `python3 agents/scripts/validate-genericness.py`, `python3 agents/scripts/run-lifecycle-gates.py`, `python3 agents/scripts/validate_templates.py`.

### Discovering product-specific concretes

Framework docs and templates do not hardcode product namespaces, API filenames, or entity names. The agent discovers these at session time from the product repo:

- **Tech stack** → `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`
- **Entity-to-file bindings** → `{PRODUCT_ROOT}/planning-mds/knowledge-graph/code-index.yaml` and `canonical-nodes.yaml`
- **API spec location** → declared in `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`; agents do not assume a filename

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
`{PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml`, add this block before the
raw file list:

```text
Ontology context:
- target: <feature or story id>
- load:
  - {PRODUCT_ROOT}/planning-mds/knowledge-graph/solution-ontology.yaml
  - {PRODUCT_ROOT}/planning-mds/knowledge-graph/canonical-nodes.yaml
  - {PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml
  - {PRODUCT_ROOT}/planning-mds/knowledge-graph/code-index.yaml (when code routing or reverse lookup is needed)
  - {PRODUCT_ROOT}/planning-mds/knowledge-graph/coverage-report.yaml (when coverage/freshness status matters)
- use the matching mapping entry as the first-pass routing context
- source precedence: raw feature/ADR/schema/API artifacts win over ontology mappings
- if ontology drift is found, repair the authoritative source first if needed,
  then repair the ontology mapping in the same change set
```

Use the ontology to resolve canonical workflow, workflow state, capability,
schema, ADR, and entity links. Do not treat it as a substitute for reading the linked raw
artifacts when details or verification matter.

### KG CLI Tools

All tools are agent-agnostic and work from any terminal or agent runtime.

| Command | Purpose |
|---------|---------|
| `python3 {PRODUCT_ROOT}/scripts/kg/lookup.py <id>` | Materialize first-pass ontology scope for a feature or story ID. Use `--tier`, `--fields`, and `--allow-missing` to control retrieval budget and greenfield fallback. |
| `python3 {PRODUCT_ROOT}/scripts/kg/lookup.py --file <path>` | Reverse lookup from a code file to ontology nodes |
| `python3 {PRODUCT_ROOT}/scripts/kg/hint.py <path>` | Quick KG routing hint before searching — outputs matched nodes, features, stories, and Casbin rules for a file or directory. Use `--json` for structured output, plus `--run-id` and `--telemetry-file` for correlation. |
| `python3 {PRODUCT_ROOT}/scripts/kg/blast.py <node-id>` | Compute blast radius for a canonical node — all impacted features, stories, code bindings, Casbin rules, and resolved files. Supports `--run-id` and `--telemetry-file`. |
| `python3 {PRODUCT_ROOT}/scripts/kg/blast.py --file <path>` | Blast radius starting from a code file (reverse-binds to nodes first) |
| `python3 {PRODUCT_ROOT}/scripts/kg/blast.py <feature-id>` | Blast radius for a feature by expanding its canonical node references. Use `--compact` for summary only. |
| `python3 {PRODUCT_ROOT}/scripts/kg/validate.py` | Validate KG integrity (IDs, references, paths, coverage) |
| `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` | Run drift checks: Casbin policy cross-check (policy_rule nodes vs policy.csv resource/action/role alignment). Add `--memory-dir <path>` to scan an external agent memory directory for stale repo-path references. |
| `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report` | Refresh the committed `coverage-report.yaml` artifact |
| `python3 agents/scripts/validate_templates.py` | Validate prompt templates against the action-contract sections in `plan.md` and `feature.md` (framework-owned) |
| `python3 {PRODUCT_ROOT}/scripts/kg/eval.py --since <ref>` | Score retrieval quality offline against historical closeout commits and telemetry |
| `python3 {PRODUCT_ROOT}/scripts/kg/telemetry_rotate.py {PRODUCT_ROOT}/.kg-state/telemetry.jsonl` | Rotate and prune local retrieval telemetry JSONL files (state lives under the product repo since it tracks product KG retrieval) |
| `python3 {PRODUCT_ROOT}/scripts/kg/pagerank.py --top N` | Compute PageRank over the knowledge graph to surface hub nodes. Use `--type entity` to filter by node type. |
| `python3 {PRODUCT_ROOT}/scripts/kg/cochange.py --top N` | Discover git co-change edges between canonical nodes. Use `--coverage-gaps` to find unbound files that co-change with bound files. |
| `python3 {PRODUCT_ROOT}/scripts/kg/workstate.py --state-file <path> init --role <role> --scope <id> --run-id <uuid>` | Initialize a session working-state file for compaction resilience and correlation. Add `--mode <name>` when applicable. |
| `python3 {PRODUCT_ROOT}/scripts/kg/workstate.py --state-file <path> decision "<summary>" --topic <slug>` | Record a decision to working state. Use `--files`, `--rationale`, and `--supersedes` for detail and current-view supersession. |
| `python3 {PRODUCT_ROOT}/scripts/kg/workstate.py --state-file <path> escalate "<reason>"` | Record an explicit insufficient-context escalation, including raw artifacts opened during escalation. |
| `python3 {PRODUCT_ROOT}/scripts/kg/workstate.py --state-file <path> dump --compact` | Dump compact working state for post-compaction context recovery |
| `python3 {PRODUCT_ROOT}/scripts/kg/workstate.py --state-file <path> dump --current-view` | Dump the current-view projection with superseded topic decisions filtered out |

### When to Use Each Tool

- **Before searching code**: run `hint.py <path>` to get KG context. This
  replaces blind Glob/Grep with ontology-routed exploration.
- **Before editing a shared entity, workflow, or schema**: run
  `blast.py <node-id>` to see what features, Casbin rules, and code files
  would be impacted.
- **When planning a feature implementation**: run `lookup.py <feature-id>` to
  materialize a first-pass ontology scope as a starting context.
- **After ontology changes**: run `validate.py --write-coverage-report` to
  refresh freshness tracking, and `validate.py --check-drift` to catch
  cross-artifact misalignment.

- **During long sessions**: run `workstate.py init` at the start, then
  `workstate.py decision` after key decisions and `workstate.py touch` after
  significant file changes.  After context compaction, run
  `workstate.py dump --compact` to recover structured session state instead
  of re-deriving it from compressed conversation history.
- **When assessing architectural risk**: run `pagerank.py --type entity` to
  find hub entities that need the most ABAC and test coverage attention.
- **When checking for undeclared dependencies**: run `cochange.py --coverage-gaps`
  to find files that frequently co-change with bound files but have no
  code-index binding.

Agent-specific hook adapters (e.g., `.claude/settings.json` for Claude Code)
can wire `hint.py` into their pre-search hooks, but the tools work
standalone without any hook configuration.

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

Use the prompt templates in `agents/templates/prompts/` as the canonical
operator starting points for `plan` and `feature` action sessions:

- `agents/templates/prompts/plan-automation-safe.md`
- `agents/templates/prompts/plan-operator-friendly.md`
- `agents/templates/prompts/feature-automation-safe.md`
- `agents/templates/prompts/feature-operator-friendly.md`

These templates encode the current retrieval budget, gate IDs, required tool
invocations, and exit-validation order. Keep them aligned with the action docs
via `python3 agents/scripts/validate_templates.py`.

## Common Prompt Clauses

Use these clauses when they apply:

- `Before loading references, consult agents/ROUTER.md and load only the task-matched subset.`
- `Before searching code, run python3 {PRODUCT_ROOT}/scripts/kg/hint.py <path> to get KG routing context.`
- `If ontology coverage exists, load the matching knowledge-graph entry before reading raw files.`
- `Use ontology mappings as compressed retrieval context only; source artifacts win on conflict.`
- `If shared solution semantics changed, repair ontology drift in the same change set.`
- `Read the full feature folder at {PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}.`
- `Where the feature-assembly-plan conflicts with raw story text, follow the feature-assembly-plan.`
- `Do not invent scope outside the current feature boundary.`
- `Update STATUS.md before concluding.`
- `If trackers changed, re-run tracker validation before declaring done.`
- `If commands or examples are unverified, mark them explicitly instead of implying they were run.`

## Ontology Ownership

- Architect owns the canonical shared layer in `{PRODUCT_ROOT}/planning-mds/knowledge-graph/`
  for entities, workflows, workflow states, capabilities, schemas, API
  contracts, and ADR links.
- Product Manager owns feature/story/persona mappings and keeps feature and
  story links current.
- Implementation agents should not silently redefine canonical solution
  semantics. When they discover drift, they should flag it and route the update
  back to the Architect or Product Manager unless explicitly acting in that
  role.
- Code Reviewer and Security should treat unresolved ontology drift as a
  cross-artifact consistency issue when shared semantics changed.

## STATUS.md Evidence Semantics

`STATUS.md` evidence rows are append-only audit history. To query "the current
verdict per (story, role)," compute it as a view over the table (latest row per
key), not by mutating or removing prior rows.

## Agent Quick Reference

| Agent | Use When | Read First | Usually Updates | Typical Validation |
|------|----------|------------|-----------------|--------------------|
| `product-manager` | refining PRDs, stories, personas, MVP/future scope, tracker sync | `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`, feature folder, dependency PRDs, `TRACKER-GOVERNANCE.md` | feature `PRD.md`, stories, `README.md`, `STATUS.md`, trackers | `python3 agents/product-manager/scripts/validate-stories.py`, `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/`, `python3 agents/product-manager/scripts/validate-trackers.py` |
| `architect` | data model, workflows, API contracts, ADRs, authorization, assembly plans | feature folder, `{PRODUCT_ROOT}/planning-mds/architecture/decisions/`, `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`, dependent PRDs | `{PRODUCT_ROOT}/planning-mds/architecture/**`, `{PRODUCT_ROOT}/planning-mds/api/*.yaml`, `{PRODUCT_ROOT}/planning-mds/schemas/*.json`, feature `feature-assembly-plan.md`, feature `STATUS.md` | `python3 agents/architect/scripts/validate-architecture.py {PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`, `python3 agents/architect/scripts/validate-api-contract.py <api-file>`, `python3 {PRODUCT_ROOT}/scripts/kg/blast.py <node>` before shared entity/workflow changes, `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` after ontology changes, tracker validation if trackers changed |
| `backend-developer` | implementing `{PRODUCT_ROOT}/engine/` changes from approved feature plans | feature folder, `feature-assembly-plan.md`, `{PRODUCT_ROOT}/planning-mds/api/`, `{PRODUCT_ROOT}/planning-mds/schemas/`, `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md` | `{PRODUCT_ROOT}/engine/**`, feature `STATUS.md`, feature `GETTING-STARTED.md` | `python3 {PRODUCT_ROOT}/scripts/kg/hint.py <path>` before searching, `sh agents/backend-developer/scripts/run-tests.sh --strict` or repo-standard backend test command |
| `frontend-developer` | implementing `{PRODUCT_ROOT}/experience/` screens, forms, API wiring, UX fixes | feature folder, `feature-assembly-plan.md`, screen specs, `{PRODUCT_ROOT}/planning-mds/api/`, `{PRODUCT_ROOT}/planning-mds/schemas/`, `agents/frontend-developer/references/ux-audit-ruleset.md` | `{PRODUCT_ROOT}/experience/**`, feature `STATUS.md`, feature `GETTING-STARTED.md` | `python3 {PRODUCT_ROOT}/scripts/kg/hint.py <path>` before searching, `pnpm --dir {PRODUCT_ROOT}/experience lint`, `pnpm --dir {PRODUCT_ROOT}/experience lint:theme`, `pnpm --dir {PRODUCT_ROOT}/experience build`, `pnpm --dir {PRODUCT_ROOT}/experience test`, plus `pnpm --dir {PRODUCT_ROOT}/experience test:visual:theme` when theme/styling changed |
| `ai-engineer` | implementing `{PRODUCT_ROOT}/neuron/`, LLM integrations, MCP servers, prompts, agent workflows | feature folder, architecture docs, AI requirements, backend integration contracts | `{PRODUCT_ROOT}/neuron/**`, feature `STATUS.md`, feature `GETTING-STARTED.md`, `{PRODUCT_ROOT}/neuron/README.md` | `pytest {PRODUCT_ROOT}/neuron/tests/` and project-standard AI integration/evaluation commands |
| `quality-engineer` | test planning, automated tests, coverage checks, E2E, performance, accessibility | stories, acceptance criteria, `feature-assembly-plan.md`, changed code, quality strategy | `{PRODUCT_ROOT}/engine/tests/**`, `{PRODUCT_ROOT}/experience/tests/**`, `{PRODUCT_ROOT}/neuron/tests/**`, feature `STATUS.md` | tier-specific test commands plus coverage artifacts; require evidence-backed pass decisions |
| `devops` | Docker, compose, CI/CD, env wiring, deployment architecture, ops scripts | architecture docs, changed app code, deployment requirements | `Dockerfile`, `docker-compose*.yml`, `.github/workflows/**`, `scripts/**`, deployment docs, feature `STATUS.md` | repo-standard container, CI, and health-check commands |
| `code-reviewer` | code quality review, acceptance criteria coverage, architecture/pattern compliance | changed code, feature folder, `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`, review action doc | feature `STATUS.md` and review findings artifacts | `python3 agents/code-reviewer/scripts/check-code-quality.py <path>`, `sh agents/code-reviewer/scripts/check-lint.sh`, `sh agents/code-reviewer/scripts/check-test-coverage.sh --min 80 --auto` as applicable |
| `security` | threat modeling, auth/authz review, OWASP review, security findings | feature folder, architecture/security artifacts, changed code | `{PRODUCT_ROOT}/planning-mds/security/**`, feature `STATUS.md` | `python3 agents/security/scripts/security-audit.py {PRODUCT_ROOT}/planning-mds/security`, plus available scan wrappers in `agents/security/scripts/` |
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

Refine F{NNNN} <feature slug> workflow ({PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}).

The PRD currently has a high-level feature statement, scope, architecture hints,
and traceability but zero user stories, no persona references, no screen specs,
and no workflows. The feature is in Draft status.

Read:
- {PRODUCT_ROOT}/planning-mds/BLUEPRINT.md
- {PRODUCT_ROOT}/planning-mds/COMMERCIAL-PC-CRM-RELEASE-PLAN.md
- the PRDs for F0006 dependency features
- {PRODUCT_ROOT}/planning-mds/features/TRACKER-GOVERNANCE.md

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
- run `python3 agents/product-manager/scripts/validate-stories.py {PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}`
- run `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/`
- run `python3 agents/product-manager/scripts/validate-trackers.py`
```

### Architect Example

```text
Switch to Architect agent mode (agents/architect/SKILL.md).

Design the technical solution for F{NNNN} <feature slug> at
{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}.

The Product Manager has completed story breakdown. Read the full feature folder
for PRD, stories, and acceptance criteria.

Also read:
- ontology files in `{PRODUCT_ROOT}/planning-mds/knowledge-graph/` first when the target feature has coverage
- {PRODUCT_ROOT}/planning-mds/architecture/decisions/
- {PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md
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
- run `python3 agents/architect/scripts/validate-architecture.py {PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`
- run `python3 agents/architect/scripts/validate-api-contract.py <api-file>` for each changed contract
- run `python3 agents/product-manager/scripts/validate-trackers.py` if planning trackers changed
```

### Backend Developer Example

```text
Switch to Backend Developer agent mode (agents/backend-developer/SKILL.md).

Implement the backend slice for <feature> in `{PRODUCT_ROOT}/engine/`.

Read:
- the full feature folder
- `{PRODUCT_ROOT}/planning-mds/features/<feature>/feature-assembly-plan.md`
- `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
- relevant files in `{PRODUCT_ROOT}/planning-mds/api/` and `{PRODUCT_ROOT}/planning-mds/schemas/`

Deliverables:
1. Implement the planned `{PRODUCT_ROOT}/engine/` changes.
2. Add or update backend tests in `{PRODUCT_ROOT}/engine/tests/`.
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
| `build` | implementing a larger approved scope across the stack | Architect -> implementation agents -> reviews | `Run the build action defined in agents/actions/build.md for the approved scope in <feature folders>.` |
| `feature` | shipping one vertical slice end to end | Architect -> implementation agents -> parallel reviews | `Run the feature action defined in agents/actions/feature.md for <feature folder>.` |
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

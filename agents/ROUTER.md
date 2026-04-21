# Reference Router

20,700+ lines of reference docs across 11 agent roles. Loading all references
for a role wastes context on material irrelevant to the current task.

**Rule**: Before loading any file from `agents/<role>/references/`, consult
the table below and load only the references matched to your current task.
Load multiple rows when the task spans categories. Skip this router only
when the full reference corpus is explicitly requested.

## How to Use

1. Identify your active agent role.
2. Find the task row(s) that match what you are doing.
3. Load only those reference files.
4. If no row matches, load nothing — the SKILL.md and solution-specific
   artifacts in `{PRODUCT_ROOT}/planning-mds/` are usually sufficient.

---

## Architect (9,080 lines → ~700–1,000 per task)

| Task | References to Load |
|------|--------------------|
| API endpoint design, OpenAPI contracts | `references/api-design-guide.md` |
| Data model, entity design, ERD | `references/data-modeling-guide.md` |
| Workflow, state machine design | `references/workflow-design.md` |
| Authorization, Casbin, ABAC | `references/authorization-patterns.md` |
| JSON Schema contracts, validation | `references/json-schema-validation-architecture.md` |
| Security architecture review | `references/security-architecture-guide.md` |
| Performance, scaling, caching | `references/performance-design-guide.md` |
| Service boundaries, module design | `references/service-architecture-patterns.md` |
| AI/ML integration architecture | `references/ai-integration-patterns.md`, `references/ai-architecture-patterns.md` |
| General architecture review, ADR | `references/architecture-best-practices.md` |
| Architecture examples | `references/architecture-examples.md` |

All paths relative to `agents/architect/`.

## Frontend Developer (5,184 lines → ~700–900 per task)

**Always load**: `references/ux-audit-ruleset.md` (mandatory UX gate on every UI change, 133 lines)

| Task | References to Load |
|------|--------------------|
| React component implementation | `references/code-patterns.md`, `references/react-best-practices.md` |
| Form handling, JSON Schema forms | `references/json-schema-forms-guide.md` |
| API calls, data fetching, caching | `references/tanstack-query-guide.md` |
| Frontend testing (Vitest, RTL) | `references/testing-guide.md` |
| Accessibility, WCAG compliance | `references/accessibility-guide.md` |
| UX principles, interaction design | `references/ux-principles.md` |
| Layout, visual design, inspiration | `references/design-inspiration.md` |
| TypeScript patterns | `references/typescript-patterns.md` |
| Legacy form comparison only | `references/form-handling-guide.md` |

All paths relative to `agents/frontend-developer/`.

## Product Manager (2,382 lines → ~300–600 per task)

| Task | References to Load |
|------|--------------------|
| Blueprint refinement, project scope | `references/blueprint-requirements.md` |
| User story writing, acceptance criteria | `references/story-examples.md`, `references/vertical-slicing-guide.md` |
| Persona definition | `references/persona-examples.md` |
| Prioritization, backlog management | `references/prioritization-frameworks.md`, `references/prioritization-examples.md` |
| Screen specification | `references/screen-spec-examples.md` |
| Feature definition, MVP scoping | `references/feature-examples.md`, `references/pm-best-practices.md` |
| General PM practices | `references/pm-best-practices.md` |

All paths relative to `agents/product-manager/`.

## DevOps (1,754 lines → ~650–1,085 per task)

| Task | References to Load |
|------|--------------------|
| Docker, Compose, containerization | `references/containerization-guide.md` |
| CI/CD pipelines, deployment scripts | `references/code-patterns.md` |
| General DevOps practices | `references/devops-best-practices.md` |

All paths relative to `agents/devops/`.

## Backend Developer (701 lines → ~665 per task)

| Task | References to Load |
|------|--------------------|
| Domain entities, services, endpoints | `references/code-patterns.md` |
| Clean architecture patterns | `references/clean-architecture-guide.md` |
| .NET best practices | `references/dotnet-best-practices.md` |
| EF Core, database patterns | `references/ef-core-patterns.md` |

All paths relative to `agents/backend-developer/`.

## AI Engineer (610 lines)

| Task | References to Load |
|------|--------------------|
| Python AI/LLM implementation | `references/code-patterns.md` |

All paths relative to `agents/ai-engineer/`.

## Quality Engineer (577 lines → ~555 per task)

| Task | References to Load |
|------|--------------------|
| Test implementation, patterns | `references/code-patterns.md` |
| Test case mapping, coverage | `references/test-case-mapping.md` |
| E2E testing | `references/e2e-testing-guide.md` |
| Performance testing | `references/performance-testing-guide.md` |
| General testing practices | `references/testing-best-practices.md` |

All paths relative to `agents/quality-engineer/`.

## Code Reviewer (314 lines)

| Task | References to Load |
|------|--------------------|
| Code quality review | `references/clean-code-guide.md`, `references/code-smells-guide.md` |
| Review checklist | `references/code-review-checklist.md` |

All paths relative to `agents/code-reviewer/`.

## Security (116 lines)

| Task | References to Load |
|------|--------------------|
| Threat modeling | `references/threat-modeling-guide.md` |
| OWASP review | `references/owasp-top-10-guide.md` |
| Secure coding standards | `references/secure-coding-standards.md` |
| General security practices | `references/security-best-practices.md` |

All paths relative to `agents/security/`.

## Blogger (14 lines), Technical Writer (15 lines)

These roles have minimal references. Load on demand — no routing needed.

---

## KG Tools

Before searching code or assessing impact, use the knowledge-graph CLI tools
(documented in `agents/docs/AGENT-USE.md` § KG CLI Tools):

| When | Command |
|------|---------|
| Before searching code | `python3 {PRODUCT_ROOT}/scripts/kg/hint.py <path>` |
| Before editing shared entities/workflows | `python3 {PRODUCT_ROOT}/scripts/kg/blast.py <node-or-file>` |
| When starting feature work | `python3 {PRODUCT_ROOT}/scripts/kg/lookup.py <feature-id>` (use `--tier`, `--fields`, and `--allow-missing` as needed) |
| After ontology changes | `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` |
| Starting a long session | `python3 {PRODUCT_ROOT}/scripts/kg/workstate.py --state-file <path> init --role <role> --scope <id> --run-id <uuid>` |
| After a key decision | `python3 {PRODUCT_ROOT}/scripts/kg/workstate.py --state-file <path> decision "<summary>" --topic <slug>` |
| When retrieval is insufficient | `python3 {PRODUCT_ROOT}/scripts/kg/workstate.py --state-file <path> escalate "<reason>" --nodes <id> ... --opened-raw <path> ...` |
| After compaction | `python3 {PRODUCT_ROOT}/scripts/kg/workstate.py --state-file <path> dump --compact` |
| Hub/impact analysis | `python3 {PRODUCT_ROOT}/scripts/kg/pagerank.py --top 20` |
| Undeclared structural edges | `python3 {PRODUCT_ROOT}/scripts/kg/cochange.py --top 20 --coverage-gaps` |

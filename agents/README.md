# Generic Agent Roles — Agent-Driven Builder Framework

## Purpose

This directory contains **generic, reusable** agent role definitions for building software using an agent-driven builder methodology. The `agents/` tree is consumed *in place* from the `nebula-agents` repo — it is **not** copied into downstream product repos. A session rooted in `nebula-agents` reads these roles, actions, and templates, and performs implementation work in a sibling product repo at `{PRODUCT_ROOT}`.

See the framework root `README.md` and `CONSUMER-CONTRACT.md` for the full consumption model.

## Framework Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Agent-Driven Builder Framework                         │
│                    Plan → Spec → Design → Build → Ship                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  ACTION FLOW (User-Facing Compositions)                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  init       │ Bootstrap product structure in {PRODUCT_ROOT}                 │
│  plan       │ Phase A (PM) → Phase B (Architect) [2 approval gates]         │
│  build      │ Backend + Frontend + AI* + QA + DevOps → Review [2 gates]     │
│  feature    │ Single vertical slice (Backend + Frontend + AI* + QA + DevOps) │
│  review     │ Code Reviewer + Security [1 gate]                             │
│  validate   │ Architect + PM validation (read-only)                         │
│  test       │ Quality Engineer testing workflow                             │
│  document   │ Technical Writer documentation                                │
│  blog       │ Blogger dev logs & articles                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
* AI Engineer runs when stories include AI/LLM/MCP scope. Architect orchestrates implementation sequencing.
                                        ↓
                              Actions compose Agents
                                        ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENTS (Role-Based Specialists) — 11 Agents                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Planning Phase (Phase A-B)                                                 │
│  ├─ product-manager    │ Requirements, stories, acceptance criteria         │
│  └─ architect          │ Design, data model, API contracts, patterns        │
│                                                                              │
│  Implementation Phase (Phase C)                                             │
│  ├─ backend-developer  │ Backend services, domain logic ({PRODUCT_ROOT}/engine/)       │
│  ├─ frontend-developer │ UI, forms, API wiring ({PRODUCT_ROOT}/experience/)            │
│  ├─ ai-engineer        │ LLMs, agents, MCP, workflows ({PRODUCT_ROOT}/neuron/) 🧠       │
│  ├─ quality-engineer   │ Unit, integration, E2E tests                       │
│  └─ devops             │ Docker, docker-compose, deployment                 │
│                                                                              │
│  Quality & Documentation                                                    │
│  ├─ code-reviewer      │ Code quality, standards, patterns                  │
│  ├─ security           │ OWASP, auth/authz, vulnerabilities                 │
│  ├─ technical-writer   │ API docs, README, runbooks                         │
│  └─ blogger            │ Dev logs, technical articles                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                        ↓
                        Agents read from & write to
                                        ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  SOLUTION-SPECIFIC CONTENT ({PRODUCT_ROOT}/planning-mds/)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Single Source of Truth                                                     │
│  └─ BLUEPRINT.md       │ Master specification (Sections 0-6)                │
│                                                                              │
│  Domain Knowledge                                                           │
│  └─ domain/            │ Glossary, competitive analysis                     │
│                                                                              │
│  Architecture                                                               │
│  ├─ architecture/                                                           │
│  │  ├─ SOLUTION-PATTERNS.md  │ Solution-specific patterns ⭐                │
│  │  ├─ decisions/            │ ADRs                                         │
│  │  └─ ...                   │ Data model docs, testing strategy, patterns  │
│                                                                              │
│  API Contracts                                                              │
│  └─ api/               │ OpenAPI specifications (*.yaml)                    │
│                                                                              │
│  Examples & Artifacts                                                       │
│  ├─ examples/          │ Personas, features, stories, screens               │
│  ├─ security/          │ Threat models, security reviews                    │
│  └─ ...                                                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

─────────────────────────────────────────────────────────────────────────────

  9 Actions · 11 Agents · 1 Source of Truth (BLUEPRINT.md)
  SOLUTION-PATTERNS.md for institutional knowledge
  {PRODUCT_ROOT}/neuron/ for AI intelligence layer 🧠
```

## Framework Files

All framework files live under `nebula-agents/` and are consumed in place from that repo. Downstream products do **not** copy `agents/` into their own tree.

| Path (in nebula-agents) | Purpose |
|-------------------------|---------|
| `agents/` (this directory) | Agent roles, actions, templates, scripts, and framework docs |
| `agents/docs/` | Framework documentation (orchestration contract, onboarding, FAQ, container strategy, agent/action usage guide) |
| `agents/actions/` | User-facing action compositions (init, plan, build, feature, review, etc.) |
| `agents/templates/` | Reusable artifact templates (stories, features, ADRs, lifecycle config, CI workflows) |
| `agents/scripts/` | Framework-level validation and gate scripts |

The `init` action scaffolds product-level files **into `{PRODUCT_ROOT}`** (the sibling product repo), not into `nebula-agents`:

| Scaffolded File (at {PRODUCT_ROOT}) | Template Source (in nebula-agents) |
|-------------------------------------|------------------------------------|
| `{PRODUCT_ROOT}/lifecycle-stage.yaml` | `agents/templates/lifecycle-stage-template.yaml` |
| `{PRODUCT_ROOT}/CONTRIBUTING.md` | `agents/templates/contributing-template.md` |
| `{PRODUCT_ROOT}/.github/workflows/ci-gates.yml` | `agents/templates/ci-gates-template.yml` |

Framework-repo-level files that stay in `nebula-agents` and apply to the framework itself:

| File (in nebula-agents) | Purpose |
|-------------------------|---------|
| `BOUNDARY-POLICY.md` | Separation rules between generic (`agents/`) and solution-specific (`{PRODUCT_ROOT}/planning-mds/`) content |
| `lifecycle-stage.yaml` | Framework-local lifecycle stage and gate matrix (framework-only gates) |
| `CONTRIBUTING.md` | Framework contribution guidelines |
| `CONSUMER-CONTRACT.md` | Formal interface with downstream product repos |

## Context Efficiency

20,700+ lines of reference docs across 11 roles. Do not load all references
for a role — load the task-matched subset.

- **[ROUTER.md](./ROUTER.md)** — maps task types to the specific reference
  files needed. Consult before loading any `references/` file.
- **[KG tools](./docs/AGENT-USE.md)** — run `python3 {PRODUCT_ROOT}/scripts/kg/hint.py <path>`
  before searching code, `python3 {PRODUCT_ROOT}/scripts/kg/blast.py <node>` before editing
  shared entities.

## How to Use

### For Users
1) Open a session rooted in `nebula-agents` with `{PRODUCT_ROOT}` resolved (see `agents/docs/AGENT-USE.md` → Session Setup).
2) Use **[Action Flow](./actions/README.md)** to compose agents for common workflows (init, plan, build, review, etc.).
3) Actions provide user-friendly entry points that orchestrate agents automatically.
4) Example: `"Run the plan action"` → PM (Phase A) → Architect (Phase B) with approval gates.
5) For direct fresh-session prompts and role-by-role usage, see **[AGENT-USE.md](./docs/AGENT-USE.md)**.

### For New Products
1) Clone `nebula-agents` and your product repo as siblings under a shared workspace root.
2) Resolve `{PRODUCT_ROOT}` via `NEBULA_PRODUCT_ROOT` / operator input / default `../<product-repo>`.
3) Run the **[init action](./actions/init.md)** from a `nebula-agents` session to scaffold product-level files and `{PRODUCT_ROOT}/planning-mds/`.
4) Use the agents in place from `nebula-agents`; all solution-specific content must live under `{PRODUCT_ROOT}/planning-mds/`.
5) For the full bootstrap-to-first-feature workflow, see `agents/docs/FORK-AND-BUILD-APP.md`.

## Single Source of Truth

All agents read requirements from `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` and related planning artifacts.

## Agent Action Flow

The **[Action Flow](./actions/README.md)** provides a user-friendly interface for composing agents to accomplish complete workflows:

- **[init](./actions/init.md)** - Bootstrap a new product in `{PRODUCT_ROOT}`
- **[plan](./actions/plan.md)** - Complete planning (Phase A + B)
- **[build](./actions/build.md)** - Full implementation workflow
- **[feature](./actions/feature.md)** - Single vertical slice
- **[review](./actions/review.md)** - Code and security review
- **[validate](./actions/validate.md)** - Validate alignment
- **[test](./actions/test.md)** - Test suite development
- **[document](./actions/document.md)** - Technical documentation
- **[blog](./actions/blog.md)** - Development logs and articles

See **[actions/README.md](./actions/README.md)** for complete action flow documentation.

## Tech Stack Assumptions

The framework is opinionated about delivery practices and provides stack-specific references in some agent guides. The default references assume a modern .NET + React + PostgreSQL stack, but the framework is stack-agnostic at the contract level. If your product uses a different stack, keep the agent roles and action contracts; replace the stack-specific reference guides and examples with ones that match your stack (see `agents/TECH-STACK-ADAPTATION.md`).

---

If you're starting a new product, see the framework root `README.md` and `CONSUMER-CONTRACT.md` for setup instructions, and `{PRODUCT_ROOT}/planning-mds/README.md` (after `init`) for a minimal setup checklist.

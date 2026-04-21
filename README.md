# nebula-agents

A tool-agnostic, orchestrator-agnostic agent-driven development framework. Plain markdown contract, sibling-repo consumption model, works with any AI coding tool.

---

## What it is

`nebula-agents` is the framework layer extracted from the original `nebula-crm` mono-repo. It provides role definitions, action protocols, prompt templates, genericness enforcement, and a builder runtime for agent-driven software development — with no dependency on any specific AI tool, orchestrator, or problem domain.

Downstream products consume it as a **sibling repo**. Agents open a session inside `nebula-agents/` and implement into a sibling product repo resolved as `{PRODUCT_ROOT}`.

## What it owns

- **Role definitions** — `agents/<role>/SKILL.md`, references, and scripts for each framework role (architect, product-manager, backend-developer, frontend-developer, security, devops, code-reviewer, quality-engineer, blogger, etc.)
- **Action protocols** — `agents/actions/*.md` for plan, feature, build, review, blog, and other action flows
- **Prompt templates** — `agents/templates/prompts/` automation-safe and operator-friendly variants
- **Genericness enforcement** — `agents/scripts/validate-genericness.py` with an embedded domain-term denylist
- **Bootstrap guidance** — `agents/docs/AGENT-USE.md`, `agents/docs/FORK-AND-BUILD-APP.md`, `agents/docs/ONBOARDING.md`
- **Builder runtime** — framework-only Docker image (`Dockerfile`, `docker/`, `docker-compose.agent-builder.yml`) with orchestration utilities only, no stack SDKs

## What it does not own

- Domain planning (BLUEPRINT.md, glossary, API spec, knowledge graph) — product repo
- Application source code (backend, frontend, AI runtime) — product repo
- Product runtime infrastructure and deployment scripts — product repo
- Product-local lifecycle gates (`knowledge_graph_sync`, `solution_contract`, `frontend_quality`) — product repo

See [CONSUMER-CONTRACT.md](CONSUMER-CONTRACT.md) for the full ownership split.

## How downstream products consume it

Open a session in `nebula-agents/`. Keep the product repo as a sibling directory. All references from `agents/**` to product-owned paths use the `{PRODUCT_ROOT}` placeholder, resolved once at session start.

```
WORKSPACE_ROOT/
  nebula-agents/        # session working directory (this repo)
  <product-repo>/       # {PRODUCT_ROOT} — e.g. nebula-insurance-crm
```

The framework makes no assumption about which AI tool or orchestrator drives the session — the contract is plain markdown plus a short set of Python validators.

## Quick start

1. Clone `nebula-agents` next to your product repo:
   ```
   git clone https://github.com/gajakannan/nebula-agents.git
   ```
2. Resolve `{PRODUCT_ROOT}` via one of:
   - CLI flag `--product-root <path>` on framework scripts
   - Environment variable `NEBULA_PRODUCT_ROOT=<path>`
   - Default fallback: `../<product-repo>` relative to `nebula-agents/`
3. Read [CONSUMER-CONTRACT.md](CONSUMER-CONTRACT.md) to understand the ownership split and required planning structure.
4. Follow [agents/docs/AGENT-USE.md](agents/docs/AGENT-USE.md) for session setup and prompt anatomy, or [agents/docs/FORK-AND-BUILD-APP.md](agents/docs/FORK-AND-BUILD-APP.md) to scaffold a new product.

## Available actions

See [agents/actions/README.md](agents/actions/README.md) for the action catalogue. Each action has an automation-safe and operator-friendly prompt template under `agents/templates/prompts/`.

## Framework architecture

```
┌────────────────────────────────────────────────┐
│          nebula-agents (this repo)             │
│                                                │
│   agents/<role>/SKILL.md     → role contracts  │
│   agents/actions/*.md         → action flows   │
│   agents/templates/prompts/  → prompt shapes   │
│   agents/scripts/            → framework gates │
│   Dockerfile                 → builder runtime │
└───────────────────┬────────────────────────────┘
                    │ sibling-repo contract
                    │ (plain markdown + {PRODUCT_ROOT})
                    ▼
┌────────────────────────────────────────────────┐
│          {PRODUCT_ROOT} (product repo)         │
│                                                │
│   planning-mds/    → domain + KG + features    │
│   <backend>/       → backend source            │
│   <frontend>/      → frontend source           │
│   <ai-runtime>/    → AI layer                  │
│   scripts/kg/      → product KG tooling        │
│   lifecycle-stage.yaml → product-local gates   │
└────────────────────────────────────────────────┘
```

## Validation

From the `nebula-agents/` root:

```bash
python3 agents/scripts/validate-genericness.py   # domain-term denylist
python3 agents/scripts/validate_templates.py     # action ↔ template alignment
python3 agents/scripts/run-skill-regression.py   # skill metadata regression
```

These three validators are the framework-owned gates declared in [lifecycle-stage.yaml](lifecycle-stage.yaml). They run with no product repo present.

## License and contribution

- [LICENSE](LICENSE)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CHANGELOG.md](CHANGELOG.md)

## Provenance

Split from `gajakannan/nebula-crm` at commit `d2fa37c4216147b7a0be399e4133dac59ef75d9f` on 2026-04-20. See [CHANGELOG.md](CHANGELOG.md) and [agents/docs/migration-from-nebula-crm.md](agents/docs/migration-from-nebula-crm.md).

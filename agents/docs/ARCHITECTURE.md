# Workspace Architecture (Conceptual)

This diagram shows how the framework repository and a product repository relate under the sibling-repo consumption model.

```
WORKSPACE_ROOT/
┌───────────────────────────────┐        ┌───────────────────────────────────────┐
│  nebula-agents/ (framework)   │        │  {NEBULA_PRODUCT_ROOT}/ (product repo)       │
│  (GENERIC, reusable)          │        │  (SOLUTION-SPECIFIC)                  │
│                               │        │                                       │
│  • 11 role definitions        │        │  • {NEBULA_PRODUCT_ROOT}/planning-mds/       │
│    (agents/<role>/SKILL.md)   │        │    - BLUEPRINT.md                     │
│  • Actions, templates         │        │    - domain, features, examples       │
│  • Framework docs             │        │    - architecture, api, security      │
│  • Framework scripts          │        │    - knowledge-graph                  │
│    (agents/scripts/)          │        │  • {NEBULA_PRODUCT_ROOT}/engine (backend)    │
│  • Framework builder          │        │  • {NEBULA_PRODUCT_ROOT}/experience          │
│    (Dockerfile)               │        │  • {NEBULA_PRODUCT_ROOT}/neuron (AI layer)   │
│                               │        │  • {NEBULA_PRODUCT_ROOT}/scripts/kg (KG)     │
│  Session working directory ───┼───────▶│  Implementation target                │
└───────────────────────────────┘        └───────────────────────────────────────┘
          ▲                                                  ▲
          │                                                  │
   agent reads roles,                           agent writes implementation,
   actions, templates                          reads product planning + KG
          │                                                  │
          └───────────────── a single AI session ────────────┘
                             (no build-time coupling)
```

## How the two repos relate

- **`nebula-agents` is the session working directory.** The operator (or AI tool) opens a session rooted in `nebula-agents` and reads framework guidance from `agents/`.
- **`{NEBULA_PRODUCT_ROOT}` is the implementation target.** All product-owned planning artifacts and code live there.
- **`{NEBULA_PRODUCT_ROOT}` is resolved at session start** in this order:
  1. Explicit operator `NEBULA_PRODUCT_ROOT` selection (pass as `--product-root` to scripts)
  2. Otherwise the `NEBULA_PRODUCT_ROOT` environment variable
  3. Missing selection is an error; no default product. Resolve relative paths once at session start and pass the absolute path thereafter (see `AGENT-USE.md`).
- **There is no build-time or runtime coupling.** The product repo does not import or depend on `nebula-agents`. The connection is process-level: the agent running the session looks left for framework guidance and right for product artifacts.
- **`agents/` is not copied into `{NEBULA_PRODUCT_ROOT}`.** The framework lives in `nebula-agents` only.

## Init action behavior

The `init` action, run from a `nebula-agents` session against a resolved `{NEBULA_PRODUCT_ROOT}`, scaffolds:

- `{NEBULA_PRODUCT_ROOT}/lifecycle-stage.yaml` — product-local gate matrix (seeded from `agents/templates/lifecycle-stage-template.yaml`)
- `{NEBULA_PRODUCT_ROOT}/CONTRIBUTING.md` — product contribution guide (seeded from `agents/templates/contributing-template.md`)
- `{NEBULA_PRODUCT_ROOT}/.github/workflows/ci-gates.yml` — starter product CI (seeded from `agents/templates/ci-gates-template.yml`)
- `{NEBULA_PRODUCT_ROOT}/planning-mds/` — full planning directory structure, with `BLUEPRINT.md`, `domain/glossary.md`, `architecture/SOLUTION-PATTERNS.md`, and feature trackers seeded from `agents/templates/`

## Validation ownership

- **Framework-owned validators** run from `nebula-agents` against `nebula-agents` content: `agents/scripts/validate-genericness.py`, `agents/scripts/run-lifecycle-gates.py`, `agents/scripts/validate_templates.py`, skill-regression tests. These enforce framework boundary and template/action alignment.
- **Product-local validators** run from `{NEBULA_PRODUCT_ROOT}` against product content: KG validation (`{NEBULA_PRODUCT_ROOT}/scripts/kg/validate.py`), API contract, frontend quality, security audits. These stay product-side.
- **Agent-invoked scripts that live in `nebula-agents` but read product state** (for example `validate-stories.py`, `validate-architecture.py`) resolve `{NEBULA_PRODUCT_ROOT}` via CLI flag / env var / default. See `CONSUMER-CONTRACT.md`.

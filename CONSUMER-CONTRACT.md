# CONSUMER-CONTRACT.md

This document is the formal interface between `nebula-agents` (framework) and any downstream product repo that consumes it. Any downstream repo that honors this contract can use the framework without framework-side changes.

---

## 1. `{PRODUCT_ROOT}` path-indirection convention

Every reference from `agents/**` to a product-owned path uses the `{PRODUCT_ROOT}` placeholder. At baseline the placeholder prefixes all product-owned trees:

- `{PRODUCT_ROOT}/scripts/kg/...`
- `{PRODUCT_ROOT}/planning-mds/...`
- Product implementation layer roots (backend, frontend, AI runtime) — named per the product's own conventions

### Resolution order

At session start (or when a framework script runs), `{PRODUCT_ROOT}` resolves in this order:

1. **Explicit CLI flag** `--product-root <path>` on any framework script
2. **Environment variable** `NEBULA_PRODUCT_ROOT`, if set
3. **Default fallback**: `../<product-repo>` relative to the framework working directory

The resolved absolute path must be echoed on the first line of framework-script output so it is visible in CI logs and session transcripts. See `agents/docs/AGENT-USE.md` → Session Setup.

### What framework references never prefix

Framework-owned paths (inside this repo) stay framework-relative:

- `agents/scripts/validate-genericness.py`
- `agents/scripts/validate_templates.py`
- `agents/scripts/run-skill-regression.py`
- `agents/<role>/scripts/*.py`
- `agents/templates/prompts/*.md`
- Root-level framework files: `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `BOUNDARY-POLICY.md`, `lifecycle-stage.yaml`, `Dockerfile`, `docker-compose.agent-builder.yml`

---

## 2. Required planning structure

The framework assumes these files exist under `{PRODUCT_ROOT}`:

| Path | Purpose |
|---|---|
| `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` | Tech stack, layer boundaries, API spec filename, canonical directory names |
| `{PRODUCT_ROOT}/planning-mds/domain/glossary.md` | Domain vocabulary, plus the `Genericness-Blocked Terms` section used by `validate-genericness.py --glossary` |
| `{PRODUCT_ROOT}/planning-mds/api/<api>.yaml` | OpenAPI spec — filename declared in BLUEPRINT.md, not hardcoded here |
| `{PRODUCT_ROOT}/planning-mds/knowledge-graph/canonical-nodes.yaml` | Canonical entity → file binding |
| `{PRODUCT_ROOT}/planning-mds/knowledge-graph/code-index.yaml` | Implementation-file index per entity |
| `{PRODUCT_ROOT}/planning-mds/knowledge-graph/solution-ontology.yaml` | Role ownership per layer; consumed by `validate_templates.py` |
| `{PRODUCT_ROOT}/planning-mds/features/REGISTRY.md` | Authoritative feature registry |
| `{PRODUCT_ROOT}/planning-mds/features/ROADMAP.md` | Active/planned feature sequencing |
| `{PRODUCT_ROOT}/lifecycle-stage.yaml` | Product-local lifecycle gates (distinct from the framework-local file in this repo) |

`{PRODUCT_ROOT}/scripts/kg/` holds the product's KG tooling (`lookup.py`, `validate.py`, `hint.py`, `workstate.py`, `blast.py`, etc.). It is product-owned runtime state because it reads `{PRODUCT_ROOT}/planning-mds/knowledge-graph/*.yaml`.

---

## 3. Implementation layer path convention

Backend, frontend, and AI-runtime paths are always referenced as product-owned paths under `{PRODUCT_ROOT}`. The framework does not assume specific directory names — actual names (e.g. `engine/`, `experience/`, `neuron/`) are declared in `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` and bound in `code-index.yaml`.

Any reference to an implementation-layer path inside `agents/**` uses `{PRODUCT_ROOT}/<layer-name>/...`, never a framework-root-relative path.

---

## 4. Discovery convention for product-specific concretes

Framework agents do NOT hardcode:

- Product namespaces (e.g. C# root namespace, Python package name)
- API spec filename
- Entity names, table names, or aggregate roots
- Layer directory names

They discover these at session time from:

- `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` → tech stack and filename conventions
- `{PRODUCT_ROOT}/planning-mds/knowledge-graph/code-index.yaml` + `canonical-nodes.yaml` → real file bindings
- `{PRODUCT_ROOT}/planning-mds/knowledge-graph/solution-ontology.yaml` → role ownership

Templates in `agents/templates/prompts/` are **shape-only skeletons**. Concrete values flow from the product's knowledge graph into each prompt at runtime.

---

## 5. Required action artifact paths

Each framework action produces artifacts in well-known locations:

| Action | Primary artifact |
|---|---|
| `plan` | `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/feature-assembly-plan.md` |
| `feature` | `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/**` (stories, ADRs, test-plan, evidence) |
| `build` | Implementation under `{PRODUCT_ROOT}/<layer>/**`; evidence under `{PRODUCT_ROOT}/planning-mds/operations/evidence/**` |
| `review` | Code-review report in `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/review/` |
| `blog` | Blog post under `../nebula-blog/posts/YYYY-MM-DD-slug.md`; channel derivatives under `../nebula-blog/amplification/` |
| `init` | Scaffolds new product into `{PRODUCT_ROOT}` (not into the framework repo) |

See individual `agents/actions/*.md` files for each action's deliverables contract.

---

## 6. Lifecycle gate contract

Two distinct `lifecycle-stage.yaml` files exist:

- **Framework-local** (`./lifecycle-stage.yaml` in this repo) declares framework-only gates: `boundary_genericness`, `skill_regression`. It governs validation of this repo itself.
- **Product-local** (`{PRODUCT_ROOT}/lifecycle-stage.yaml` in the downstream product repo) declares product gates and points to product-local validator scripts.

Valid `current_stage` values: `framework-bootstrap`, `planning`, `implementation`, `release-readiness`. See `agents/templates/lifecycle-stage-template.yaml` for the canonical shape.

A product's lifecycle file must declare each gate with an explicit `command:` list. Framework-owned validator scripts may be invoked only when the product has a vendored copy or when the framework repo is on `PYTHONPATH` — otherwise product CI is expected to carry product-local equivalents.

---

## 7. Validation ownership model

**Framework-owned validations** live in this repo and run against the resolved `{PRODUCT_ROOT}` when product context is needed:

- `agents/scripts/validate-genericness.py` — embedded domain-term denylist, overridable via `--glossary`
- `agents/scripts/validate_templates.py` — action ↔ template alignment
- `agents/scripts/run-skill-regression.py` — skill metadata and routing regression
- Planning-governance validators under `agents/product-manager/scripts/` (`validate-stories.py`, `generate-story-index.py`, `validate-trackers.py`)
- Role-specific validators under `agents/<role>/scripts/` that the framework owns (e.g. `agents/architect/scripts/validate-architecture.py`, `agents/architect/scripts/validate-api-contract.py`, `agents/devops/scripts/validate-infrastructure.py`, `agents/security/scripts/security-audit.py`)

**Product-local validations** live in the product repo and must be runnable with no `agents/**` directory present:

- `{PRODUCT_ROOT}/scripts/kg/validate.py` (knowledge-graph sync)
- `{PRODUCT_ROOT}/planning-mds/testing/validate-nebula-api-contract.py` (solution contract)
- `{PRODUCT_ROOT}/planning-mds/testing/validate-frontend-quality-gate.py` (frontend quality)
- Additional product-local equivalents for `api_contract`, `infra_strict`, `security_planning_strict` as each product matures

---

## 8. Genericness contract

No framework file may reference product-specific terms.

Enforcement has two layers:

- **Domain-term denylist** via `python3 agents/scripts/validate-genericness.py`. The denylist is embedded in the script as a transitional safeguard; pass `--glossary <path>` to extend with product-specific terms during a split or migration.
- **Path / brand / namespace grep gates** (see `BOUNDARY-POLICY.md`). These catch leaks the domain-term validator cannot see: product-owned directory names (`planning-mds/`, backend/frontend/AI layer names, `scripts/kg/`), brand namespaces (e.g. `Nebula.<PascalCase>`), and product API filenames.

CI runs the domain-term validator automatically (`lifecycle-stage.yaml` → `boundary_genericness` gate). The grep gates are run manually during framework-side refactors and major migrations.

---

## 9. Workspace layout convention

```
WORKSPACE_ROOT/
  nebula-agents/        # framework (this repo)
  <product-repo>/       # {PRODUCT_ROOT}
```

`WORKSPACE_ROOT` must be outside any backup copy of the original `nebula-crm` repo. Resolving `{PRODUCT_ROOT}` to a path inside a backup tree is undefined behavior and will be rejected by framework scripts where possible.

---

## 10. API reference path convention

Product repos own their OpenAPI spec. Framework agents never hardcode an API filename. The filename is declared in `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` and — when needed — passed explicitly to framework scripts (e.g. `python3 agents/architect/scripts/validate-api-contract.py {PRODUCT_ROOT}/planning-mds/api/<api>.yaml`).

---

## 11. Versioning policy

Downstream products pin to a `nebula-agents` version by git tag or commit ref. The framework follows semantic-ish versioning where:

- **Major** — breaking change to this contract (path conventions, required planning structure, gate semantics)
- **Minor** — new actions, new validators, new templates, or non-breaking additions to this contract
- **Patch** — internal framework fixes that do not change this contract

A product repo should pin to a specific tag (e.g. `v0.1.0`) during initial adoption. See [CHANGELOG.md](CHANGELOG.md).

---

## 12. Stack adaptation

The framework is stack-agnostic. Products change tech stacks by editing their own `BLUEPRINT.md`, `code-index.yaml`, and `canonical-nodes.yaml` — the framework reads these at runtime with no code change on the framework side.

Stack-specific reference guides under `agents/<role>/references/**` are illustrative and editable per product. Replace them as needed; the framework does not enforce their content.

See `TECH-STACK-ADAPTATION.md` (when present) for stack-swap walkthroughs.

---

## 13. What this contract does not cover

- Which AI tool, orchestrator, or IDE drives the session — the framework is deliberately plain markdown and any tool can consume it
- Choice of version control host, CI system, or artifact registry
- Product-specific security, privacy, or compliance requirements — those live in product repos and product CI

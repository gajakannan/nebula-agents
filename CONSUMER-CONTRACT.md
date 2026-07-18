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
| `{PRODUCT_ROOT}/planning-mds/knowledge-graph/symbol-index.yaml` | Symbol-level layer (methods, classes, functions) extracted from declared code paths. Required once product implementation has begun; omit during framework-bootstrap stage. |
| `{PRODUCT_ROOT}/planning-mds/knowledge-graph/decisions-index.yaml` | Inline decision marker layer (`// WHY:`, `// DECISION:`, `// TRADEOFF:`, `// SUPERSEDES:`) harvested from declared code paths. Optional — present once inline decision markers exist in product code. |
| `{PRODUCT_ROOT}/planning-mds/knowledge-graph/coverage-report.yaml` | KG coverage roll-up produced by `validate.py --write-coverage-report`. May include additive Phase 3 freshness fields per canonical node — `hotspot_rank`, `hotspot_score`, `primary_owner`, `primary_owner_pct`, `bus_factor_flag`, `last_modified` — when `scripts/kg/hotspots.py` is wired in. Consumers may omit any of these; reviewers/architect/security only act on fields that are present. |
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

- `{PRODUCT_ROOT}/scripts/kg/validate.py` (knowledge-graph sync; `--check-symbols` validates the symbol layer, `--check-decisions` validates the inline decision marker layer)
- `{PRODUCT_ROOT}/scripts/kg/symbols.py` (symbol-index generator; invoked directly or via `validate.py --regenerate-symbols`)
- `{PRODUCT_ROOT}/scripts/kg/decisions.py` (inline decision marker harvester; invoked directly or via `validate.py --regenerate-decisions`)
- `{PRODUCT_ROOT}/scripts/kg/risk.py` (Phase 4 risk-score aggregator; combines blast/hotspot/cochange/ownership/test-gap into a 0–10 score per canonical node, file, or symbol — pre-flight gate, not authoritative)
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

## Feature Evidence Contract

Effective `2026-05-19`. This section is the public normative contract for framework run evidence and completed-terminal feature evidence. It replaces the legacy `feature` artifact row.

The evidence validator, fixtures, and prompt templates use stable section labels as rule taxonomy:

| Label | Public contract area |
|-------|----------------------|
| `§7` | Conditional scope booleans and forced roles |
| `§8` | Base run evidence |
| `§9` / `§10` | Feature completion profile and artifact matrix |
| `§11` | Manifest schema, role results, gate results, and reruns |
| `§12` | `latest-run.json` schema |
| `§13` | `commands.log` JSONL schema and command evidence |
| `§14` | Role report headings and result values |
| `§15` | Recommendation and PM acceptance format |
| `§16` | `STATUS.md` signoff provenance |
| `§17` | Stage validation, run resolution, and closeout publish order |
| `§18` | Waivers, omissions, and deferrals |
| `§20` | Global frontend evidence lanes |
| `§21` | Cross-artifact consistency |
| `§22` | Feature evidence validator behavior |
| `§23` | Required fixture coverage |
| `§24` / `§25` | Framework file and template alignment |

### Eligibility And Effective Date

The feature evidence profile applies to governed completed-terminal feature runs:

- Archived completed features with `REGISTRY.md` `Archived Date` before `2026-05-19` are skipped by feature evidence validation, while normal tracker/link validation still applies.
- Archived completed features with `Archived Date` on or after `2026-05-19` require a canonical feature evidence package.
- Active `Done`/`Complete`/`Completed` terminal features require canonical evidence unless `STATUS.md` has a `Closeout Summary` table row named `Closeout review date` with a parseable ISO date before `2026-05-19`.
- Missing, placeholder, or malformed active closeout dates do not qualify for the pre-contract skip; validators treat those features as governed by the current validation date.
- A pre-contract archived feature that is reopened, materially changed, or re-closed after the effective date must carry `Evidence Reentry Date = YYYY-MM-DD` on the archived registry row. A reentry date on or after `2026-05-19` requires canonical evidence.
- Retired features with `Terminal Status = Abandoned` or `Superseded` are registry-only records. They are skipped by feature evidence validation and never satisfy completed-feature evidence requirements.
- The framework does not migrate, normalize, index, or backfill pre-contract archived feature evidence.

### Base Run Evidence

Every orchestrated run produces a base evidence package. Non-feature/manual runs (e.g. `agents/actions/validate.md`) use the base path:

```text
{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}/
  README.md
  action-context.md
  artifact-trace.md
  gate-decisions.md
  commands.log
  lifecycle-gates.log
```

### Feature Completion Profile

Feature completion runs (`agents/actions/feature.md` and `agents/actions/build.md` when archiving a delivered feature) write to the feature profile path with the full artifact matrix:

```text
{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}/
  <base files above>
  evidence-manifest.json
  feature-action-execution.md
  g0-assembly-plan-validation.md
  g1-runtime-preflight.md         # when runtime_bearing = true
  g2-self-review.md
  test-plan.md
  test-execution-report.md
  coverage-report.md
  deployability-check.md
  code-review-report.md
  security-review-report.md       # when security-sensitive
  signoff-ledger.md
  pm-closeout.md
  artifacts/{coverage,diffs,test-results,security,screenshots}/

{PRODUCT_ROOT}/planning-mds/operations/evidence/features/F####-{slug}/
  latest-run.json                 # pointer to approved run + manifest
```

Run IDs use `YYYY-MM-DD-XXXXXXXX`, where the date is local-at-session-start and `XXXXXXXX` is 8 lowercase hex characters from cryptographic randomness. The run ID is recorded at run creation and carried unchanged through closeout.

`evidence-manifest.json` is required for feature profile runs. It records feature identity, run identity, status, effective date, feature start/closeout paths, changed paths, SCM diff evidence, conditional scope booleans, required roles, gate results, role results, files, omissions, waivers, and global evidence references. Paths in manifest fields must be repo-relative and must not traverse upward.

Contract version selection (F0007): newly initialized runs carry `contract_version` (stamped by `init-run.py` from the active action policy) in addition to `contract_effective_date`. When `contract_version` is present it is the explicit policy selection; it must be a published version (`agents/actions/spec/history/<version>.yaml`) and its date must equal `contract_effective_date`, or validation fails closed (`manifest_unknown_contract_version_fails`, `manifest_version_date_conflict_fails`, `manifest_malformed_contract_version_fails`). Legacy manifests without `contract_version` continue to resolve by `contract_effective_date` to the newest policy whose `effective_from` is not later than that date. Published historical policy is immutable, and an active-policy update never changes a historical run's verdict. The versioned policy and the validator's date-gated matrix are proven equivalent by the dual-read diagnostic (`agents/product-manager/scripts/contract_compat.py --matrix`); the validator's private matrix is removed only after a recorded zero-disagreement decision.

The conditional scope booleans are explicit and must not be inferred from prose alone:

- `runtime_bearing` — runtime source, runtime tests, AI runtime, migrations, executable workflows, or runtime-affecting docs changed.
- `deployment_config_changed` — Dockerfiles, compose files, CI/deployment jobs, env/config contracts, migrations, startup scripts, secrets/config docs, or runtime topology changed. This forces DevOps evidence.
- `frontend_in_scope` — frontend application, UI tests, routes, components, styling, UX/accessibility behavior, screenshots, or visual evidence changed.
- `security_sensitive_scope` — auth, authorization, identity, permissions, secrets, policy enforcement, PII, audit logging, or dependency/security controls changed. This forces Security evidence.

Quality Engineer and Code Reviewer evidence is required for every governed completed-terminal feature. DevOps is required when `deployment_config_changed = true` or marked required in `STATUS.md`. Security Reviewer is required when `security_sensitive_scope = true` or marked required in `STATUS.md`. Architect evidence is required when marked required in `STATUS.md`; the feature action also requires G0 assembly-plan validation and, for runs effective on or after `2026-06-01`, G7 knowledge-graph reconciliation at closeout.

`latest-run.json` lives under the feature index root and is written only for an approved run. It points to the approved run and manifest, uses repo-relative paths, and must agree with the approved manifest.

### Stage Validation And Closeout

Validators must not create or consume `current-run.json`, and must not infer the active run by sorting run folders. Before `latest-run.json` exists, the action provides the active run through `--run-id`.

- `G0` through `G5` validation requires an explicit `--run-id`.
- `G6` candidate validation uses `--run-id` and runs before tracker/story-index/KG/template closeout results are finalized.
- `G7` records architect knowledge-graph reconciliation for the as-built source.
- `G8`/`closeout` validation requires `latest-run.json`, `kg-reconciliation.md` when applicable, `pm-closeout.md`, and tracker/story-index/KG/template validator results recorded in `lifecycle-gates.log` and summarized in `pm-closeout.md`.

When publishing a newly approved run, closeout must first run `agents/product-manager/scripts/patch-prior-manifest.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --new-run-id {RUN_ID}` to mark prior approved manifests for the feature as `superseded`. Only after that helper exits 0 may closeout write the feature's new `latest-run.json`. If the helper fails, do not publish the new pointer; follow the partial-closeout recovery guidance in `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md`.

### Validation Modes

- Plan runs perform tracker/base-run validation only: `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --skip-feature-evidence`. Plan operators must not call `validate-feature-evidence.py` for the current plan run. Plan closeout also records a dependency impact evidence audit for direct or impacted feature dependencies; automated dependency discovery/validation may be added by a later framework step.
- Feature gates `G0` through `G6` run scoped evidence validation for the current feature/run: `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage <GATE>`.
- Feature closeout runs scoped current feature/run validation: closeout evidence via `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout`, and tracker sync via `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID}`.
- Repo health/audit validation is explicit only: `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --all-feature-evidence` performs repo-wide feature-evidence validation after tracker validation. This mode is not an implicit blocker for every plan or feature closeout.

### Global Frontend Lanes

`planning-mds/operations/evidence/frontend-quality/` and `planning-mds/operations/evidence/frontend-ux/` remain valid global lanes. They may be referenced from feature evidence (`global_evidence_refs` in the manifest) but do not substitute for feature-level role reports.

### Validators

- `agents/product-manager/scripts/validate-feature-evidence.py` — feature evidence package consistency, effective-date eligibility, manifest schema, role/gate reconciliation, stage validation, and cross-artifact checks.
- `agents/product-manager/scripts/validate-trackers.py` — tracker/registry consistency. Tracker-only/base-run validation is available with `--skip-feature-evidence`; scoped feature closeout validation uses `--feature {FEATURE_ID} --run-id {RUN_ID}` and invokes feature-evidence validation at `--stage G6`; repo-wide feature-evidence validation requires explicit `--all-feature-evidence`.
- `agents/product-manager/scripts/patch-prior-manifest.py` — closeout supersession helper called before writing `latest-run.json`.
- `agents/scripts/validate_templates.py` — template/action alignment, including evidence-template alignment rules.

# Action: Init

## User Intent

Bootstrap a new product with the proper directory structure, blueprint template, and initial planning artifacts under `{PRODUCT_ROOT}` (the sibling product repo). Runs before any feature exists, and writes only to `{PRODUCT_ROOT}` — never to the framework repo (`nebula-agents`).

## Agent Flow

```
I0  Project inputs captured
  ↓
I1  PRODUCT_ROOT scaffold      (canonical directory structure)
  ↓
I2  BLUEPRINT template
  ↓
I3  Registry + roadmap         (empty sections)
  ↓
I4  Evidence infrastructure    (planning-mds/operations/evidence/ + README + Path Class Extensions)
  ↓
I5  KG infrastructure          (empty knowledge-graph/ yaml files)
  ↓
I6  Validator sanity           (all validators exit 0 against the empty product)
Init Complete
```

**Flow Type:** Single agent — Product Manager (initialization mode) owns every scaffolded file.

---

## Contract (generated — the spec is the source of truth)

The fixed procedure for this action — the `I0`–`I6` gates, inputs (`PROJECT_NAME`, `DOMAIN_DESCRIPTION`,
`TARGET_USERS`, `CORE_ENTITIES`), the I6 validator sweep, forbidden actions, stop conditions, and conflict
resolution — is declared once in [`agents/actions/spec/init.yaml`](spec/init.yaml) and compiled into the
operator/automation prompt pair at
`agents/templates/prompts/evidence-contract/init-operator-friendly.md` and `init-automation-safe.md`.
Regenerate with `python3 agents/scripts/render-prompts.py`; the `prompt_drift` lifecycle gate fails if the
committed prompts drift from the spec. **Edit the spec, not this doc or the generated prompts.**

- **Scope** — `base-run-only`: init runs before any feature exists, so it produces no feature evidence
  package; it still writes a base run package under `{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{INIT_RUN_ID}/`
  so the bootstrap is auditable.
- **Key invariants** — REGISTRY.md starts with **empty** Active/Planned/Archived/Retired sections;
  ROADMAP.md with empty Now/Next/Later/Completed; the Evidence Contract Effective Date is the framework
  default (`2026-05-19`) or later, never earlier; do not scaffold into a non-empty `{PRODUCT_ROOT}` without
  explicit operator confirmation.

Drive the gates with `python3 agents/scripts/run-gate.py --action init --stage <I0..I6> ...` (`--list` prints
the ordered runbook; I6 carries the validator sweep). Init is idempotent — safe to re-run on an existing
product (existing files are skipped; structure is validated).

---

## Scaffolded outputs (all under `{PRODUCT_ROOT}`)

### Product-level framework files

```
{PRODUCT_ROOT}/
  lifecycle-stage.yaml              # from agents/templates/lifecycle-stage-template.yaml (current_stage: framework-bootstrap)
  CONTRIBUTING.md                   # from agents/templates/contributing-template.md
  .github/workflows/ci-gates.yml    # from agents/templates/ci-gates-template.yml
```

Boundary policy is framework-owned in `nebula-agents/BOUNDARY-POLICY.md` and applies across all consuming products; `init` does not scaffold a per-product copy.

### Planning directory structure

```
{PRODUCT_ROOT}/planning-mds/
├── BLUEPRINT.md              # master spec — Sections 0–2 filled from inputs, 3–6 as TODO
├── README.md                 # planning directory overview
├── domain/glossary.md        # domain terminology skeleton
├── features/
│   ├── REGISTRY.md           # empty Active/Planned/Archived/Retired
│   ├── ROADMAP.md            # empty Now/Next/Later/Completed
│   ├── STORY-INDEX.md        # placeholder (regenerated when stories are added)
│   ├── TRACKER-GOVERNANCE.md # from agents/templates/tracker-governance-template.md
│   └── archive/              # empty
├── architecture/
│   ├── SOLUTION-PATTERNS.md  # from agents/templates/solution-patterns-template.md
│   └── decisions/            # empty (ready for Architect)
├── security/                 # empty (ready for Security)
├── operations/evidence/      # base run vs feature vs global lanes README + Path Class Extensions (§7, empty)
└── knowledge-graph/          # empty solution-ontology / canonical-nodes / feature-mappings / code-index .yaml
```

If the product's top-level layout differs from the framework defaults (`engine/`, `experience/`) — e.g. a monorepo using `apps/api/`, `apps/web/`, `services/` — the operator must populate the evidence README's **Path Class Extensions** section before the first feature action runs.

---

## Prerequisites

- [ ] `nebula-agents` is checked out and is the session working directory.
- [ ] `{PRODUCT_ROOT}` is resolved via `NEBULA_PRODUCT_ROOT`, operator input, or the default `../<product-repo>`.
- [ ] `{PRODUCT_ROOT}` is empty or a new repository willing to accept scaffolded files.
- [ ] The operator has basic project context (domain, goals, target users, initial entities).

## Post-Initialization Next Steps

1. Review `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` sections 0–2.
2. Refine the domain glossary in `{PRODUCT_ROOT}/planning-mds/domain/glossary.md`.
3. Run the **[plan action](./plan.md)** for Phase A + B.

## Related Actions

- **Next:** [plan action](./plan.md) — complete requirements and architecture.
- **Alternative:** manually populate `BLUEPRINT.md` if you prefer full control.

## Notes

- Idempotent — safe to run on an existing product (skips existing files, validates structure only).
- Writes only to `{PRODUCT_ROOT}`; never modifies `nebula-agents` content.

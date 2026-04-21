# Action: Init

## User Intent

Bootstrap a new product with the proper directory structure, blueprint document template, and initial planning artifacts under `{PRODUCT_ROOT}` (the sibling product repo).

## Agent Flow

```
Product Manager (initialization mode)
```

**Flow Type:** Single agent

## Prerequisites

- [ ] `nebula-agents` is checked out and is the session working directory
- [ ] `{PRODUCT_ROOT}` is resolved via `NEBULA_PRODUCT_ROOT`, operator input, or the default `../<product-repo>`
- [ ] `{PRODUCT_ROOT}` points to an empty or new repository (or one willing to accept scaffolded files)
- [ ] User has basic project context (domain, goals, target users)

## Inputs

### Required
- Project name
- Domain description (1-2 sentences)
- Target users (list of roles)
- Core entities (initial baseline list)

### Optional
- Tech stack preferences (defaults to .NET + React + PostgreSQL)
- Phase scope (MVP features to include/exclude)

## Outputs

All outputs are written into `{PRODUCT_ROOT}`. Nothing is written into the framework repo (`nebula-agents`).

### Product-Level Framework Files
```
{PRODUCT_ROOT}/
  lifecycle-stage.yaml                    # Product-local gate matrix (from agents/templates/lifecycle-stage-template.yaml)
  CONTRIBUTING.md                         # Product contribution guide (from agents/templates/contributing-template.md)
  .github/workflows/
    ci-gates.yml                          # Starter CI workflow (from agents/templates/ci-gates-template.yml)
```

Boundary policy is framework-owned in `nebula-agents/BOUNDARY-POLICY.md` and applies across all consuming products. `init` does not scaffold a per-product `BOUNDARY-POLICY.md` by default.

### Planning Directory Structure
```
{PRODUCT_ROOT}/planning-mds/
├── BLUEPRINT.md              # Master specification (template populated)
├── README.md                 # Planning directory overview
├── domain/
│   └── glossary.md           # Domain-specific terminology (skeleton)
├── features/
│   ├── REGISTRY.md           # Feature number tracker + index
│   ├── ROADMAP.md            # Sequencing view (Now / Next / Later / Completed)
│   ├── STORY-INDEX.md        # Story rollup (generated)
│   ├── TRACKER-GOVERNANCE.md # Tracker synchronization contract
│   └── archive/              # (empty, completed features move here)
├── examples/
│   ├── personas/             # (empty, ready for PM)
│   ├── features/             # (empty, ready for PM)
│   └── stories/              # (empty, ready for PM)
├── architecture/
│   ├── SOLUTION-PATTERNS.md  # Solution conventions for all implementation agents
│   └── decisions/            # (empty, ready for Architect)
└── security/                 # (empty, ready for Security)
```

### Populated Files
- **`{PRODUCT_ROOT}/lifecycle-stage.yaml`** — Seeded from `agents/templates/lifecycle-stage-template.yaml` with `current_stage: framework-bootstrap`
- **`{PRODUCT_ROOT}/CONTRIBUTING.md`** — Seeded from `agents/templates/contributing-template.md`
- **`{PRODUCT_ROOT}/.github/workflows/ci-gates.yml`** — Seeded from `agents/templates/ci-gates-template.yml`
- **`{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`** — Sections 0-2 filled with user inputs, sections 3-6 as TODOs
- **`{PRODUCT_ROOT}/planning-mds/README.md`** — Overview of planning artifacts and how to use them
- **`{PRODUCT_ROOT}/planning-mds/domain/glossary.md`** — Domain glossary skeleton ready for population
- **`{PRODUCT_ROOT}/planning-mds/features/TRACKER-GOVERNANCE.md`** — Copied from `agents/templates/tracker-governance-template.md`
- **`{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`** — Scaffolded from `agents/templates/solution-patterns-template.md`

## Agent Responsibilities

### Product Manager (Init Mode)
1. Confirm `{PRODUCT_ROOT}` is resolved and writable before any scaffolding runs. Echo the resolved absolute path.
2. Interview user to gather required inputs (if not provided)
3. Scaffold product-level framework files into `{PRODUCT_ROOT}` (skip if they already exist):
   - Copy `agents/templates/lifecycle-stage-template.yaml` to `{PRODUCT_ROOT}/lifecycle-stage.yaml`
   - Copy `agents/templates/contributing-template.md` to `{PRODUCT_ROOT}/CONTRIBUTING.md`
   - Copy `agents/templates/ci-gates-template.yml` to `{PRODUCT_ROOT}/.github/workflows/ci-gates.yml`
4. Create `{PRODUCT_ROOT}/planning-mds/` directory structure
5. Populate `BLUEPRINT.md` template with baseline information:
   - Section 0: Process and roles
   - Section 1: Product context (name, domain, purpose, users, entities, workflows)
   - Section 2: Technology baseline (if specified)
   - Sections 3-6: Marked as TODO with clear instructions
6. Create domain glossary skeleton
7. Initialize feature trackers:
   - Create `{PRODUCT_ROOT}/planning-mds/features/REGISTRY.md`
   - Create `{PRODUCT_ROOT}/planning-mds/features/ROADMAP.md`
   - Create `{PRODUCT_ROOT}/planning-mds/features/STORY-INDEX.md` (placeholder; regenerated when stories are added)
   - Copy `agents/templates/tracker-governance-template.md` to `{PRODUCT_ROOT}/planning-mds/features/TRACKER-GOVERNANCE.md`
8. Copy `agents/templates/solution-patterns-template.md` to `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
9. Validate that all required inputs are captured and all writes landed under `{PRODUCT_ROOT}` (not the framework repo)

## Validation Criteria

- [ ] `{PRODUCT_ROOT}/lifecycle-stage.yaml` exists
- [ ] `{PRODUCT_ROOT}/CONTRIBUTING.md` exists
- [ ] `{PRODUCT_ROOT}/.github/workflows/ci-gates.yml` exists
- [ ] `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` exists with Sections 0-2 populated
- [ ] Directory structure matches template
- [ ] Domain glossary skeleton created
- [ ] `{PRODUCT_ROOT}/planning-mds/features/TRACKER-GOVERNANCE.md` exists
- [ ] `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md` exists
- [ ] No placeholder text remains (or is clearly marked as TODO)
- [ ] No framework-repo files (`nebula-agents/**`) were modified by `init`
- [ ] User can immediately proceed to Phase A (planning) or Phase B (architecture)

## Example Usage

### Scenario 1: B2B SaaS Platform
```
User: "Initialize a new B2B SaaS project called TeamSync at ../teamsync"

Init Action:
  ↓
Resolves {PRODUCT_ROOT} = ../teamsync (operator-provided)
  ↓
Product Manager prompts:
  - Domain: "Team collaboration and project management"
  - Users: "Project managers, team leads, administrators"
  - Core entities: "Project, Task, Team, Member, Activity"
  ↓
Creates {PRODUCT_ROOT}/planning-mds/ with populated BLUEPRINT.md
```

### Scenario 2: E-commerce Platform
```
User: "Bootstrap an e-commerce project called ShopFlow"

Init Action:
  ↓
Resolves {PRODUCT_ROOT} = ../shopflow (default sibling)
  ↓
Product Manager prompts:
  - Domain: "B2C E-commerce"
  - Users: "Customers, store administrators, fulfillment staff"
  - Core entities: "Product, Order, Cart, Customer, Inventory"
  ↓
Creates {PRODUCT_ROOT}/planning-mds/ with populated BLUEPRINT.md
```

## Post-Initialization Next Steps

After running init action:
1. Review `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` sections 0-2
2. Refine domain glossary in `{PRODUCT_ROOT}/planning-mds/domain/glossary.md`
3. Ready to run **[plan action](./plan.md)** for Phase A + B

## Related Actions

- **Next:** [plan action](./plan.md) - Complete requirements and architecture
- **Alternative:** Manually populate `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` if you prefer full control

## Notes

- Init action is idempotent — safe to run on existing products (will skip existing files)
- If `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` already exists, init will validate structure only
- User can always manually edit files after init completes
- Init writes only to `{PRODUCT_ROOT}`. It never modifies `nebula-agents` content.

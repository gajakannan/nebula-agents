# Build an App With the Framework

This guide is the fastest path from a fresh `nebula-agents` checkout to a first feature delivered in your product repo.

The framework is consumed as a sibling repo, not a fork to copy into your product. You do **not** copy `agents/` into the product tree. Instead, you open a session rooted in `nebula-agents` and let it work on your product repo at `{NEBULA_PRODUCT_ROOT}`.

## Outcome

After following this guide, you will have:
- A clean `nebula-agents` checkout used as your framework session root.
- A product repo at `{NEBULA_PRODUCT_ROOT}` with the `{NEBULA_PRODUCT_ROOT}/planning-mds/` tree initialized.
- A first feature spec ready to implement through the action flow.

## Prerequisites

- You can run your preferred agent runtime (human-orchestrated preview is supported by default).
- You understand the boundary: `agents/` is generic framework content in `nebula-agents`; `{NEBULA_PRODUCT_ROOT}/planning-mds/` is solution-specific content in the product repo.
- You have a new product name, target users, and initial core entities.
- `nebula-agents` and the product repo are (or will be) checked out as siblings under a shared workspace root.

## Choose Your Starting Mode

### Mode A: Greenfield product (recommended)

Use this when you want to start a fresh product on top of the framework.

Setup:
- Clone `nebula-agents`.
- Create or clone an empty product repo as a sibling (e.g., `../my-product`).
- Resolve `{NEBULA_PRODUCT_ROOT}` and run the `init` action from a `nebula-agents` session.

### Mode B: Adopt the framework for an existing product

Use this when you already have a product repo and want to introduce the framework.

Setup:
- Clone `nebula-agents` next to your existing product repo.
- Resolve `{NEBULA_PRODUCT_ROOT}` to your existing product.
- Run `init` — it is idempotent and will skip files that already exist. Migrate existing planning docs into `{NEBULA_PRODUCT_ROOT}/planning-mds/` incrementally.

## Step 1: Workspace Layout

```
WORKSPACE_ROOT/
  nebula-agents/          # framework, session working dir
  <product-repo>/         # your product, e.g. my-product or nebula-insurance-crm
```

`WORKSPACE_ROOT` must sit outside any other repo. Clone both repos at this level.

## Step 2: Resolve `{NEBULA_PRODUCT_ROOT}`

At session start, `{NEBULA_PRODUCT_ROOT}` resolves in this order:
1. Explicit operator `NEBULA_PRODUCT_ROOT` selection (pass as `--product-root` to scripts)
2. Otherwise the `NEBULA_PRODUCT_ROOT` environment variable
3. Missing selection is an error; no default product. Resolve relative paths once at session start and pass the absolute path thereafter (see `AGENT-USE.md`).

Confirm the absolute resolved path before running any action.

## Step 3: Initialize Your Product Context

Run the `init` action from `agents/actions/init.md` with your agent runtime, from a session rooted in `nebula-agents`.

Provide:
- Project name
- Domain description
- Target users
- Core entities
- Optional stack preferences

Expected outputs (all written into `{NEBULA_PRODUCT_ROOT}`):
- `{NEBULA_PRODUCT_ROOT}/lifecycle-stage.yaml`
- `{NEBULA_PRODUCT_ROOT}/CONTRIBUTING.md`
- `{NEBULA_PRODUCT_ROOT}/.github/workflows/ci-gates.yml`
- `{NEBULA_PRODUCT_ROOT}/planning-mds/` structure
- Seeded `{NEBULA_PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`

`init` writes only to `{NEBULA_PRODUCT_ROOT}`. It does not modify `nebula-agents`.

## Step 4: Replace Defaults with Your Product Context

1. Add or update a root `README.md` in your product repo for your product.
2. Populate `{NEBULA_PRODUCT_ROOT}/planning-mds/domain/glossary.md` with your domain terms.
3. Keep all generic role/action content in `nebula-agents/agents/` unchanged — do not copy it into the product.
4. If your stack differs from the framework default, follow `agents/TECH-STACK-ADAPTATION.md` in `nebula-agents`.
5. Confirm the boundary rules in `nebula-agents/BOUNDARY-POLICY.md` still hold for your product.

## Step 5: Create Your First Feature Pack

1. Add your first feature folder: `{NEBULA_PRODUCT_ROOT}/planning-mds/features/F0001-<slug>/`
2. Add one story file in that folder using `agents/templates/story-template.md` in `nebula-agents`.
3. Update `{NEBULA_PRODUCT_ROOT}/planning-mds/features/REGISTRY.md`.
4. Add any required API contract docs under `{NEBULA_PRODUCT_ROOT}/planning-mds/api/`.

## Step 6: Execute the Build Flow

From the `nebula-agents` session, use action flow in this sequence:
1. `plan` (PM + Architect)
2. `feature` or `build` (implementation roles, writing into `{NEBULA_PRODUCT_ROOT}/engine`, `{NEBULA_PRODUCT_ROOT}/experience`, and/or `{NEBULA_PRODUCT_ROOT}/neuron`)
3. `review` (Code Reviewer + Security)
4. `test` and `validate`

Action definitions live in `agents/actions/README.md` in `nebula-agents`. Each run records an evidence package under `{NEBULA_PRODUCT_ROOT}/planning-mds/operations/evidence/`; a completed `feature`/`build` run produces the full feature package (see `agents/docs/AGENT-OPS.md`).

## Step 7: Run Gates Before PRs

From the `nebula-agents` session root:

```bash
python3 -m pip install -r agents/scripts/requirements.txt
python3 agents/scripts/run-lifecycle-gates.py --list
python3 agents/scripts/run-lifecycle-gates.py
python3 agents/scripts/validate-genericness.py
python3 agents/product-manager/scripts/validate-stories.py
```

These framework-owned validators resolve `{NEBULA_PRODUCT_ROOT}` via an explicit CLI flag or `NEBULA_PRODUCT_ROOT` (no default product) and operate on product content without needing a `cd` into the product repo.

Product-local gates (for example `{NEBULA_PRODUCT_ROOT}/scripts/kg/validate.py`) run from `{NEBULA_PRODUCT_ROOT}` and are wired into the product's own CI via `{NEBULA_PRODUCT_ROOT}/.github/workflows/ci-gates.yml`.

## Common Mistakes to Avoid

- Copying `nebula-agents/agents/` into the product repo — the framework is consumed in place, not vendored.
- Putting project-specific terms into `agents/` (the framework repo).
- Keeping stale reference content in `{NEBULA_PRODUCT_ROOT}/planning-mds/` after importing from a previous product.
- Adapting templates/roles before proving baseline flow with one real feature.
- Skipping lifecycle stage updates in `{NEBULA_PRODUCT_ROOT}/lifecycle-stage.yaml`.

## Related Docs

- `nebula-agents/README.md`
- `nebula-agents/CONSUMER-CONTRACT.md`
- `agents/README.md`
- `agents/actions/README.md`
- `agents/docs/ONBOARDING.md`
- `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md`
- `agents/docs/AGENT-OPS.md`
- `agents/TECH-STACK-ADAPTATION.md`
- `BOUNDARY-POLICY.md`

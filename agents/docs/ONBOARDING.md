# New Project Onboarding Checklist

Initial preview mode note:
- Human-orchestrated execution is the default for this release.
- Use `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md` for required evidence capture.

## Step 1: Workspace Setup (15 minutes)

The framework runs from a session rooted in `nebula-agents`. The product repo is a sibling.

- [ ] Clone `nebula-agents` and the product repo as siblings under a shared workspace root:
  ```
  WORKSPACE_ROOT/
    nebula-agents/          # session working directory (this repo)
    <product-repo>/         # implementation target, e.g. nebula-insurance-crm
  ```
- [ ] `WORKSPACE_ROOT` must sit outside any other repo.
- [ ] Read `README.md` and `CONSUMER-CONTRACT.md` in `nebula-agents`.
- [ ] Read `BOUNDARY-POLICY.md` in `nebula-agents`.
- [ ] Review `agents/docs/AGENT-USE.md` (Session Setup section for `{NEBULA_PRODUCT_ROOT}` resolution).
- [ ] Review `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md`.
- [ ] Review `agents/docs/PREVIEW-RELEASE-CHECKLIST.md`.
- [ ] (Optional) Build the framework builder container: `docker build -t nebula-agent-builder .`

## Step 2: Resolve {NEBULA_PRODUCT_ROOT} (5 minutes)

At session start, resolve `{NEBULA_PRODUCT_ROOT}` in this order:
1. Explicit operator `NEBULA_PRODUCT_ROOT` selection (pass as `--product-root` to scripts)
2. Otherwise the `NEBULA_PRODUCT_ROOT` environment variable
3. Missing selection is an error; no default product. Resolve relative paths once at session start and pass the absolute path thereafter (see `AGENT-USE.md`).

Confirm the resolved absolute path after root binding, before product discovery or writes.

## Step 3: Bootstrap Planning (2–4 hours)

Run the `init` action from a session rooted in `nebula-agents` against the resolved `{NEBULA_PRODUCT_ROOT}`. It scaffolds:

- [ ] `{NEBULA_PRODUCT_ROOT}/lifecycle-stage.yaml` (product-local gate matrix)
- [ ] `{NEBULA_PRODUCT_ROOT}/CONTRIBUTING.md`
- [ ] `{NEBULA_PRODUCT_ROOT}/.github/workflows/ci-gates.yml`
- [ ] `{NEBULA_PRODUCT_ROOT}/planning-mds/` structure
- [ ] `{NEBULA_PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` seeded from template
- [ ] `{NEBULA_PRODUCT_ROOT}/planning-mds/domain/glossary.md` skeleton
- [ ] 3–5 initial personas in `{NEBULA_PRODUCT_ROOT}/planning-mds/examples/personas/`

## Step 4: First Sprint (1 week)

- [ ] Product Manager: Define first 3 features
- [ ] Architect: Draft first ADR
- [ ] Backend: Implement first endpoint
- [ ] Frontend: Implement first screen
- [ ] QA: Write first test cases

## Validation

Run framework validators from the `nebula-agents` session root:

- [ ] Install framework script dependencies: `python3 -m pip install -r agents/scripts/requirements.txt`
- [ ] Review `{NEBULA_PRODUCT_ROOT}/lifecycle-stage.yaml` and confirm `current_stage` is correct
- [ ] Run framework-level gates: `python3 agents/scripts/run-lifecycle-gates.py --list`
- [ ] Run framework-level gates: `python3 agents/scripts/run-lifecycle-gates.py`
- [ ] Run story validation (product-root-aware): `python3 agents/product-manager/scripts/validate-stories.py`
- [ ] (Optional strict mode) `python3 agents/product-manager/scripts/validate-stories.py --strict-warnings`
- [ ] Verify no solution-specific content leaked into `agents/`: `python3 agents/scripts/validate-genericness.py`
- [ ] Confirm all specs follow templates under `agents/templates/`

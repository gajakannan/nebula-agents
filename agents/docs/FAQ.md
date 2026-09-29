# Frequently Asked Questions

## Can I use this framework with a different tech stack?

Yes. The roles and templates are reusable; only stack-specific references and examples need changes. Keep the builder runtime stack-agnostic, and run stack-specific compile/test/security in application runtime containers. See `agents/TECH-STACK-ADAPTATION.md`.

## Can I use this for non-CRM projects?

Yes. The framework is domain-agnostic. See `blueprint-setup/examples/` for non-insurance examples.

## How do I start a new project?

You do **not** copy `agents/`. The framework is consumed in place: clone `nebula-agents` and your product repo as siblings under a shared workspace root, open a session rooted in `nebula-agents`, and resolve `{NEBULA_PRODUCT_ROOT}` to your product repo (see `agents/docs/AGENT-USE.md` → Session Setup).

Run the `init` action from that session. It scaffolds product-side files into `{NEBULA_PRODUCT_ROOT}` — `lifecycle-stage.yaml`, `CONTRIBUTING.md`, a starter CI workflow (`.github/workflows/ci-gates.yml`), and the `planning-mds/` tree — from templates bundled in `agents/`. Boundary policy stays framework-owned in `nebula-agents/BOUNDARY-POLICY.md`; `init` does not scaffold a per-product copy.

See `agents/docs/FORK-AND-BUILD-APP.md` for the full walkthrough.

## Where do I find a step-by-step onboarding checklist?

See `agents/docs/ONBOARDING.md`.

## How do I know if something belongs in agents/ vs {NEBULA_PRODUCT_ROOT}/planning-mds/?

Use the boundary rules in `BOUNDARY-POLICY.md`.

## Can I modify agent roles?

Yes, but keep them generic. Put project-specific notes and requirements in `{NEBULA_PRODUCT_ROOT}/planning-mds/`.

## What if my agents need different workflows?

Adapt the `SKILL.md` files, but keep them reusable across similar projects. Use `{NEBULA_PRODUCT_ROOT}/planning-mds/` for project-specific variations.

## Does this repo include an automated orchestrator right now?

No. The initial public preview is human-orchestrated. A human operator runs actions and gates from the documented contracts.

## How do I execute the framework in manual mode?

Use `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md`. It defines required evidence capture for approvals, gate decisions, and artifact traceability.

## How do I know if the repo is complete enough for preview release?

Use `agents/docs/PREVIEW-RELEASE-CHECKLIST.md` and ensure every required item is checked before tagging a public preview.

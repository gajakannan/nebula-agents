# Frequently Asked Questions

## Can I use this framework with a different tech stack?

Yes. The roles and templates are reusable; only stack-specific references and examples need changes. Keep the builder runtime stack-agnostic, and run stack-specific compile/test/security in application runtime containers. See `agents/TECH-STACK-ADAPTATION.md`.

## Can I use this for non-CRM projects?

Yes. The framework is domain-agnostic. See `blueprint-setup/examples/` for non-insurance examples.

## What do I copy to start a new project?

Copy:
- `agents/` (includes framework docs, templates, scripts, and all agent roles)

Create new:
- `{PRODUCT_ROOT}/planning-mds/` from scratch

The `init` action scaffolds root-level framework files (`lifecycle-stage.yaml`, `BOUNDARY-POLICY.md`, `CONTRIBUTING.md`, starter CI workflow) from templates bundled in `agents/`.

## Where do I find a step-by-step onboarding checklist?

See `agents/docs/ONBOARDING.md`.

## How do I know if something belongs in agents/ vs {PRODUCT_ROOT}/planning-mds/?

Use the boundary rules in `BOUNDARY-POLICY.md`.

## Can I modify agent roles?

Yes, but keep them generic. Put project-specific notes and requirements in `{PRODUCT_ROOT}/planning-mds/`.

## What if my agents need different workflows?

Adapt the `SKILL.md` files, but keep them reusable across similar projects. Use `{PRODUCT_ROOT}/planning-mds/` for project-specific variations.

## Does this repo include an automated orchestrator right now?

No. The initial public preview is human-orchestrated. A human operator runs actions and gates from the documented contracts.

## How do I execute the framework in manual mode?

Use `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md`. It defines required evidence capture for approvals, gate decisions, and artifact traceability.

## How do I know if the repo is complete enough for preview release?

Use `agents/docs/PREVIEW-RELEASE-CHECKLIST.md` and ensure every required item is checked before tagging a public preview.

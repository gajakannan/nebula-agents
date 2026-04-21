# Preview Release Checklist

Use this checklist before tagging an initial public preview of the framework.

## 1) Scope And Messaging

- [ ] `README.md` clearly states this release is human-orchestrated.
- [ ] `README.md` explicitly states there is no built-in automated orchestrator yet.
- [ ] `agents/docs/ORCHESTRATION-CONTRACT.md` includes manual-mode expectations.
- [ ] `agents/docs/FAQ.md` answers manual-vs-automated orchestration clearly.

## 2) Boundary Discipline

- [ ] `python3 agents/scripts/validate-genericness.py` passes.
- [ ] No solution-specific terms appear in `agents/` except approved exceptions.
- [ ] Boundary policy remains consistent with validator behavior.

## 3) Manual Orchestration Reproducibility

- [ ] `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md` exists and is linked from `README.md`.
- [ ] At least one representative run evidence package exists under `{PRODUCT_ROOT}/planning-mds/operations/evidence/`.
- [ ] Evidence package contains all required files:
  - [ ] `action-context.md`
  - [ ] `artifact-trace.md`
  - [ ] `gate-decisions.md`
  - [ ] `commands.log`
  - [ ] `lifecycle-gates.log`

## 4) Lifecycle And CI Clarity

- [ ] `lifecycle-stage.yaml` reflects current preview posture.
- [ ] CI workflow messaging states checks are stage-scoped.
- [ ] Team understands green CI at current stage is not release-readiness completion.

## 5) Documentation Consistency

- [ ] No stale status notes conflict with current action docs.
- [ ] Key docs section in `README.md` links to runbook and preview checklist.
- [ ] Onboarding docs reference current execution model.

## 6) Known Deferred Items (Track, Do Not Hide)

- [ ] Automated orchestrator implementation is explicitly marked as future work.
- [ ] Strict implementation/release gates are tracked for later phases:
  - [ ] `infra_strict`
  - [ ] `security_planning_strict`

## Decision

- [ ] Preview Go
- [ ] Preview No-Go
- [ ] Follow-up issue list created for all unchecked items

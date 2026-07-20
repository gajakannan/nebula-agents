# Action: Plan Review

## User Intent

Independently review completed `plan.md` output and answer one question: **is this plan ready to build?** Concretely — could a competent implementation agent begin `feature.md` Step 0 without inventing product rules, architecture decisions, API contracts, workflow states, authorization rules, or acceptance criteria?

This is a read-only post-plan readiness audit. It does not replace the approval, tracker-sync, ontology-sync, or validation gates inside `plan.md`; it gives a fresh reviewer a focused way to challenge the completed planning package before `feature.md` or `build.md` starts.

## Agent Flow

```
PR0  Scope lock
  ↓
PR1  Parallel readiness review  (Product Manager + Architect + Code Reviewer)
  ↓
PR2  Validator pass
  ↓
PR3  Self-review gate           (reviewers verify evidence-backed findings)
  ↓
PR4  Readiness gate             (Ready / Conditionally Ready / Not Ready)
Plan Review Complete
```

**Flow Type:** Parallel read-only review with a readiness gate.

---

## Contract (generated — the spec is the source of truth)

The fixed procedure for this action — the `PR0`–`PR4` gates, inputs (`PLAN_SCOPE`, `TARGET`, `DIFF_RANGE`),
the validator commands, ownership, forbidden actions, stop conditions, and conflict resolution — is declared
once in [`agents/actions/spec/plan-review.yaml`](spec/plan-review.yaml) and compiled into the
operator/automation prompt pair at
`agents/templates/prompts/evidence-contract/plan-review-operator-friendly.md` and
`plan-review-automation-safe.md`. Regenerate with `python3 agents/scripts/render-prompts.py`; the
`prompt_drift` lifecycle gate fails if the committed prompts drift from the spec.
**Edit the spec, not this doc or the generated prompts.**

- **Scope** — `read-only-audit`: writes a base run package with `plan-review-report.md` under
  `{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{PLAN_REVIEW_RUN_ID}/`, and never creates or modifies
  a feature evidence package (owned by `feature.md`/`build.md`) or any plan artifact.
- **Ownership** — each role owns its `plan-review-report.md` section: PM → Product Readiness; architect →
  Architecture Readiness; code-reviewer → Buildability Challenge. Report sections and the validator list are
  in the spec's `notes.report_sections` / PR2.
- **Severity** — the PR4 readiness gate uses the `review-family` profile (`gate_policy.py`): critical > 0 →
  **NOT READY**; critical = 0 + high > 0 → **CONDITIONALLY READY** (fix before `feature.md`, or capture
  explicit user risk acceptance with owner + target date); critical = 0 + high = 0 → **READY**. A missing
  build-critical owner is NOT READY.

Drive the gates with `python3 agents/scripts/run-gate.py --action plan-review --stage <PR0..PR4> ...`
(`--list` prints the ordered runbook, including the read-only PR2 validators). `validate-stories.py` applies
in feature scope, iterates per feature for feature-set, and is skipped (with a recorded reason) for project
scope.

---

## Reviewer Independence Contract

- Prefer running this action in a fresh session or a different coding tool than the one that produced the plan.
- Reviewers inspect source artifacts **directly** — never approve from a summary, chat transcript, or generated checklist alone, or from `plan.md`'s prior approval tokens.
- The action is read-only except for writing the review report under the base run evidence folder.
- Findings route back to `plan.md` or a targeted owning-role rework prompt. Reviewers do not silently repair planning artifacts while reviewing.

## Reviewer judgment — per-role readiness checks

The spec owns the evidence contract; the checklists below are each reviewer's method (keep aligned with the
role SKILLs). Each role owns the matching `plan-review-report.md` section.

- **Product Manager (Product Readiness)** — every feature has clear user value + explicit non-goals; every story has specific testable acceptance criteria; mutation stories name entry points, editable/read-only states, persistence evidence, roles, lifecycle constraints, validation failures, and audit/timeline expectations; "display/capture", "view/edit", "manage" language isn't satisfiable by read-only rendering when a write path is intended; UI-bearing scope has screen responsibilities + ASCII layouts (or a written "No UI" justification); personas/workflow goals/priorities consistent; no TODOs/placeholders/vague words in build-critical areas; no invented business rules without traceable need or explicit assumption.
- **Architect (Architecture Readiness)** — architecture can satisfy every in-scope story without new decisions; API contracts (or an explicit no-API justification) exist for story-driven backend behavior; data model/workflow states/lifecycle transitions support the requirements; authorization model names resources/actions/roles/constraints; NFRs measurable enough for implementation + testing; ADRs exist for consequential decisions; KG feature-mappings + canonical bindings reflect the raw artifacts; `feature-assembly-plan.md` can be produced from available plan artifacts without guessing.
- **Code Reviewer (Buildability Challenge)** — reviews the plan as an implementation handoff, not code: feature is small enough to build as a vertical slice; backend/frontend/AI/QE/DevOps responsibilities are inferable without role conflict; acceptance criteria map to unit/integration/component/E2E/security/deployability checks; planned changes have enough file/API/schema direction to avoid broad code search or speculative implementation; dependencies/sequencing/cross-feature impacts explicit; risky high-blast-radius nodes flagged for extra review.

> Do not require `feature-assembly-plan.md` as a plan deliverable — it belongs to `feature.md` Step 0. Do not
> downgrade missing build-critical detail to a low-severity documentation note.

---

## Prerequisites

- [ ] `plan.md` has completed for the target scope.
- [ ] Phase A and Phase B approval decisions are recorded (or missing approvals are in review scope).
- [ ] Tracker sync and ontology sync have completed (or their failures are in scope for this review).
- [ ] The feature, feature set, or planning target to review is identified (`PLAN_SCOPE` + `TARGET`).

## Related Actions

- **Before:** [plan action](./plan.md) — produce requirements and architecture.
- **Alternative:** [validate action](./validate.md) — broad artifact alignment.
- **After passing:** [feature action](./feature.md) — build a vertical slice.
- **After findings:** return to [plan action](./plan.md) or direct owning-role rework for targeted repairs.

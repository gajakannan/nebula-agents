# Action: Feature Review

## User Intent

Independently review a completed feature and answer one question: **is this feature truly done?**

This is a read-only post-completion audit. It does not replace the code, security, signoff, closeout, tracker-sync, or feature-evidence gates inside `feature.md`; it gives a fresh reviewer a focused way to challenge the completed vertical slice before merge, release, or stakeholder acceptance.

## Agent Flow

```
FR0  Feature run and diff lock
  ↓
FR1  Parallel completion review  (PM + Architect + QE + Code Reviewer + Security + DevOps*)
  ↓
FR2  Validator pass
  ↓
FR3  Self-review gate            (reviewers verify evidence-backed findings)
  ↓
FR4  Done gate                   (Truly Done / Conditionally Done / Not Done)
Feature Review Complete
```

`DevOps*` runs when runtime, deployment, environment, CI, or infrastructure artifacts changed, or when deployability evidence is missing or disputed (`RUN_DEVOPS`).

---

## Contract (generated — the spec is the source of truth)

The fixed procedure for this action — the `FR0`–`FR4` gates, the two modes, inputs (`PR_URL`/`FEATURE_ID`/
`MODE`/`DIFF_RANGE`, `FEATURE_RUN_ID`, `RUN_DEVOPS`), the validator commands, ownership, forbidden actions,
stop conditions, and conflict resolution — is declared once in
[`agents/actions/spec/feature-review.yaml`](spec/feature-review.yaml) and compiled into the
operator/automation prompt pair at
`agents/templates/prompts/evidence-contract/feature-review-operator-friendly.md` and
`feature-review-automation-safe.md`. Regenerate with `python3 agents/scripts/render-prompts.py`; the
`prompt_drift` lifecycle gate fails if the committed prompts drift from the spec.
**Edit the spec, not this doc or the generated prompts.**

- **Scope** — `read-only-audit`: writes a base run package with `feature-review-report.md` under
  `{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{FEATURE_REVIEW_RUN_ID}/`, and reads — but never
  writes — the canonical feature evidence package (owned by `feature.md`/`build.md`).
- **Modes** — `closeout-audit` audits the approved run (`FEATURE_RUN_ID` defaults to `latest-run.json`;
  validate `--stage closeout`); `candidate-audit` audits an in-progress run (`FEATURE_RUN_ID` set; validate
  `--run-id --stage G6`). PR target: an OPEN PR ⇒ candidate-audit, else closeout-audit.
- **Ownership** — each role owns its `feature-review-report.md` section (PM: requirements/signoff/tracker;
  architect: architecture + KG; QE: test evidence + coverage; code-reviewer: code quality + merge-readiness;
  security: security; devops: deployability when `RUN_DEVOPS=yes`). Report sections and validator list are in
  the spec's `notes.report_sections` / FR2.
- **Severity** — the FR4 done gate uses the `review-family` profile (`gate_policy.py`): validation FAIL or
  critical > 0 → **NOT DONE**; PASS + critical = 0 + high > 0 → **CONDITIONALLY DONE** (each high needs
  owner + mitigation + target date); PASS + critical = 0 + high = 0 → **TRULY DONE**.

Drive the gates with `python3 agents/scripts/run-gate.py --action feature-review --stage <FR0..FR4> ...`
(`--list` prints the ordered runbook, including the FR2 validators). Note FR2's `generate-story-index.py`
currency check (run only when story files changed) is a **finding source, not a repair** — this read-only
audit never commits the regeneration.

---

## Reviewer Independence Contract

- Prefer running this action in a fresh session or a different coding tool than the one that implemented the feature.
- Reviewers inspect the completed feature artifacts, evidence package, current diff, and runtime evidence **directly** — not report summaries.
- The action is read-only except for writing the review report under the base run evidence folder.
- Findings route back to `feature.md`, `review.md`, `test.md`, or targeted owning-role rework. Reviewers do not silently fix implementation or evidence artifacts while reviewing.

## Reviewer judgment — per-role completion checks

The spec owns the evidence contract; the checklists below are each reviewer's method (keep aligned with the
role SKILLs). Each role owns the matching `feature-review-report.md` section.

- **Product Manager** — every in-scope story has an explicit pass/fail disposition; ACs map to implementation + test evidence; deferred items are explicit, owned, non-build-critical; required signoff roles have passing reviewer/date/evidence; status/archive/registry/roadmap/blueprint/story-index/feature-mappings agree; remaining high findings have explicit mitigation acceptance.
- **Architect** — implementation matches the feature-assembly-plan (or reconciles deviations in evidence); API contracts + schemas match delivered behavior; workflow states/data model/authorization/ADRs aligned; KG bindings + code-index cover new/moved source; drift passes or unresolved drift is documented as blocking.
- **Quality Engineer** — every AC has test evidence or a justified manual path; tests ran in the required runtime containers/CI; runtime preflight evidence precedes validation; summary coverage matches raw artifacts; failure/retry history distinguishes runtime-blocked from code defects; no critical layer skipped without justification.
- **Code Reviewer** — changed code is limited to feature scope and implements the planned vertical slice end to end; existing review findings fixed/justified/non-blocking; no hidden TODOs, debug code, dead paths, or unreviewed files; error handling/naming/boundaries/test quality merge-ready; non-obvious changes carry rationale/decision evidence.
- **Security** — server-side authorization enforced for new/changed actions; inputs, file/document handling, and external calls validated; mutations create required audit/timeline evidence; no hardcoded secrets/unsafe config/data leakage; security findings fixed or explicitly mitigated; required security review not skipped for security-sensitive scope.
- **DevOps (conditional)** — feature starts and runs in the declared runtime; new env vars/services/ports/jobs/secrets documented; container/CI changes don't break existing services; deployability command evidence is current and feature-scoped.

---

## Prerequisites

- [ ] `feature.md` has reached G6 or G8 for the target feature.
- [ ] Feature evidence run ID is known or resolvable from `latest-run.json`.
- [ ] Changed-file set or diff range is available.
- [ ] The review mode (`candidate-audit` vs `closeout-audit`) is identified (or a `PR_URL` is supplied).

## Related Actions

- **Before:** [feature action](./feature.md) — build and close out the feature.
- **Feeds:** [integrate action](./integrate.md) — supplies its I0 `REVIEW_VERDICT_REF`.
- **Alternative:** [review action](./review.md) — code/security review only; [validate action](./validate.md) — broad artifact alignment.
- **After findings:** return to [feature](./feature.md), [review](./review.md), [test](./test.md), or direct owning-role rework for targeted repairs.

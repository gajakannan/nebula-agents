# Action: Defect / Bugfix

## User Intent

Chase down and fix an ad hoc defect with a small, evidence-backed run — reproduce the bug, find the root cause, apply the smallest correct fix, and validate it — without pretending the run is completed-feature evidence.

## Agent Flow

```
D0  Defect scope lock
  ↓
D1  Reproduction and triage
  ↓
D2  Root cause and fix plan      (Architect)
  ↓
D3  Implementation               (smallest correct fix, within scope)
  ↓
D4  Validation                   (narrowest meaningful tests first)
  ↓
D5  Review and closeout
Defect Run Complete
```

Roles are activated per `AGENT_ROLES` (default `architect,frontend-developer`; add `product-manager`, `backend-developer`, `quality-engineer`, or `security` only when relevant).

---

## Contract (generated — the spec is the source of truth)

The fixed procedure for this action — the `D0`–`D5` gates, inputs (`DEFECT_SUMMARY`/`OBSERVED_BEHAVIOR`/
`EXPECTED_BEHAVIOR`, `REPRO_STEPS`, `AFFECTED_PATHS`, `AGENT_ROLES`, `FEATURE_REFS`,
`ALLOW_FEATURE_PROPOSAL`), per-role ownership, forbidden actions, stop conditions, and conflict resolution —
is declared once in [`agents/actions/spec/defect-bugfix.yaml`](spec/defect-bugfix.yaml) and compiled into the
operator prompt at `agents/templates/prompts/evidence-contract/defect-bugfix-operator-friendly.md`
(defect-bugfix has only the operator-friendly variant). Regenerate with
`python3 agents/scripts/render-prompts.py`; the `prompt_drift` lifecycle gate fails if the committed prompt
drifts from the spec. **Edit the spec, not this doc or the generated prompt.**

- **Scope** — `base-run-only`, and explicitly **outside the feature-completion profile**. A defect run may
  change code, docs, tests, or planning notes, but it produces **no** feature evidence package, satisfies no
  closeout requirement, and never writes `evidence-manifest.json` / `latest-run.json` / signoff ledgers.
  Evidence lands only in `{DEFECT_RUN_FOLDER}` (the six §8 base run files + `artifacts/`) plus the actual
  files changed by the fix. Record `Lifecycle Authority = none` in `action-context.md`.
- **Ownership** — each activated role owns its report: PM → `bugfix-brief.md` / `feature-recommendation.md`;
  architect → `architect-analysis.md`; frontend/backend → `frontend-fix-report.md` / `backend-fix-report.md`;
  QE → `quality-report.md`; security → `security-review-report.md`.
- **Promotion** — if the bug actually needs a new product capability, the operator can promote the run to
  formal feature work: stop the defect run cleanly, record the decision, write `feature-recommendation.md`,
  and start a fresh `plan`/`feature`/`build` run with its own feature-scoped evidence. A defect run never
  creates `planning-mds/features/*` on its own.

Drive the gates with `python3 agents/scripts/run-gate.py --action defect-bugfix --stage <D0..D5> ...`
(`--list` prints the ordered runbook). The fix's tests are chosen at D4 (narrowest meaningful first), so the
gates carry no fixed typed commands.

---

## Related Actions

- **Promote to:** [plan action](./plan.md) / [feature action](./feature.md) / [build action](./build.md) — when the defect needs durable, feature-scoped product work.
- **Related:** [review action](./review.md) — for standalone code/security review of a change set.

## Notes

- Keep the fix the smallest correct change within the defect scope; broaden validation only when blast radius requires it.
- Never hide failed commands — record them in `commands.log` and use them as evidence.
- Stop and escalate if reproduction needs unavailable credentials/data/env, if the fix crosses a security/privacy boundary without Security involvement, or if the work really needs a feature rather than a fix.

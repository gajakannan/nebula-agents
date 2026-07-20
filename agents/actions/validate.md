# Action: Validate

## User Intent

Validate that requirements, architecture, and implementation are aligned and that all artifacts are complete and consistent — Product Manager validates requirements and Architect validates architecture in parallel, and (when implementation is in scope) the framework validators run as tools. Non-destructive analysis; produces a base run evidence package, never writes into a feature evidence package.

## Agent Flow

```
V0  Scope lock
  ↓
V1  Parallel validation  (PM requirements + Architect architecture + implementation validators)
  ↓
V2  Self-review gate      (each agent checks its own report)
  ↓
V3  Approval gate         (user reviews findings, decides next steps)
Validation Complete
```

**Flow Type:** Parallel validation with a self-review gate and an approval gate.

---

## Contract (generated — the spec is the source of truth)

The fixed procedure for this action — the `V0`–`V3` gates, inputs (`VALIDATION_SCOPE`, `FEATURE_ID`,
`STAGE`, `RUN_ID`), the implementation-validator commands, ownership, forbidden actions, stop conditions,
and conflict resolution — is declared once in [`agents/actions/spec/validate.yaml`](spec/validate.yaml)
and compiled into the operator/automation prompt pair at
`agents/templates/prompts/evidence-contract/validate-operator-friendly.md` and
`validate-automation-safe.md`. Regenerate with `python3 agents/scripts/render-prompts.py`; the
`prompt_drift` lifecycle gate fails if the committed prompts drift from the spec.
**Edit the spec, not this doc or the generated prompts.**

- **Scope** — `VALIDATION_SCOPE ∈ {requirements | architecture | implementation | all}` selects which V1
  lanes run (see the spec's `notes.scope_conditionality`). `FEATURE_ID` narrows the implementation lane to
  one feature; `STAGE` (default `closeout`) and `RUN_ID` apply then (`--run-id` mandatory for `G0..G5`).
- **Output location (§8/§14)** — reports live under the base run at
  `{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{VALIDATE_RUN_ID}/`, governed by the six base run
  files; **no** `evidence-manifest.json` (that profile is `feature.md`/`build.md` only). This action reads
  any targeted feature run **read-only** and emits findings into its own run folder.
- **Ownership** — `product-manager` owns `pm-validation-report.md` and `implementation-validation-report.md`
  (templates `agents/templates/pm-validation-report-template.md`,
  `implementation-validation-report-template.md`); `architect` owns `architect-validation-report.md`
  (template `architect-validation-report-template.md`). Report section headings are in the spec's
  `notes.evidence_outputs`.
- **Severity** — V3 is a plain approval (no severity arithmetic: `severity_gate: none`). Blocking
  (`high`/`critical`) findings on a validate run require an in-report follow-up commitment (owner + target
  date), since a validate run has no `pm-closeout.md` to carry a PM Acceptance Line.

Drive the gates with `python3 agents/scripts/run-gate.py --action validate --stage <V0..V3> ...`
(`--list` prints the ordered runbook, including the implementation-validator commands).

---

## Runtime Execution Boundary

- The builder runtime orchestrates the validation flow and gate decisions; it remains stack-agnostic.
- If implementation validation is in scope, stack-specific checks (compile, test, schema comparison) must run in application runtime containers (or CI jobs built from those container definitions).
- Validation reports cite evidence from builder-side artifact inspection and (when applicable) application runtime execution.

---

## Validator judgment (not encoded in the spec)

The spec owns the evidence contract and the validator commands; the analytical checklists below are the
agents' judgment — keep them aligned with `agents/product-manager/SKILL.md` and `agents/architect/SKILL.md`.

### Requirements validation (Product Manager)

- **Completeness:** BLUEPRINT.md Section 3 subsections filled, no TODO/placeholder text, every feature has a folder (PRD/README/STATUS/GETTING-STARTED) and at least one story.
- **Vision & non-goals:** vision is a clear 1–2 sentence outcome, non-goals explicit, success metrics defined.
- **Personas:** each has name/role/goals/pain points; primary vs secondary identified; represent real users.
- **Traceability:** every feature maps to a persona need with clear user value and MVP-vs-future priority.
- **Story testability (per story, not sampled):** "As a / I want / So that" structure; specific measurable acceptance criteria; no banned vague words ("should", "fast", "secure", …) without specifics; quantified performance (< Xms), error scenarios, edge cases, and dependencies.
- **Anti-patterns to flag:** "system should be fast" → "API < 200ms p95"; "secure auth" → "JWT, HTTPS only, 30-min timeout"; "easy interface" → "3-click max to create customer".
- **Consistency:** no conflicting requirements, terminology aligned with the glossary, real priorities (not "all critical"), no invented business rules, assumptions documented.

### Architecture validation (Architect)

- **Completeness:** BLUEPRINT.md Section 4 subsections; service/module boundaries; data model + relationships; API contracts for every story-driven endpoint; authorization model covers all resources/actions; workflow state machines; measurable NFRs; ADRs for key decisions.
- **Requirements alignment:** architecture satisfies Phase A requirements; every story has an API endpoint or UI path; data model supports all features; authorization supports all personas.
- **Pattern compliance (when SOLUTION-PATTERNS.md exists):** authorization pattern (e.g. Casbin ABAC), audit fields on mutable entities, endpoint naming, ProblemDetails errors, clean-architecture layers, append-only workflow transitions, timeline events on mutations.
- **Implementation alignment (when code exists):** schema matches data model, endpoints match contracts, entities match architecture, no drift.
- **Ontology hygiene (release-readiness):** `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-orphans` reports zero unresolved orphans; `python3 {PRODUCT_ROOT}/scripts/kg/dead-code.py --safe-only` candidates triaged (removed / wired up / justified false positive); new orphans since the last release explained (reference `agents/architect/references/dead-code-review-guide.md`).

## Validation Severity Levels

- **Critical:** missing required BLUEPRINT sections, major requirement contradictions, fundamental architecture flaws, no authorization defined, data model can't support required features.
- **High:** incomplete specs (TODOs), ambiguous requirements (banned words without specifics), missing API contracts, unmet acceptance criteria, non-measurable NFRs.
- **Medium:** minor inconsistencies, optimization opportunities, documentation gaps, non-critical naming.
- **Low:** style suggestions, nice-to-haves, alternative approaches.

---

## Prerequisites

Before running the validate action:
- [ ] `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` exists with planning content
- [ ] Architecture artifacts exist (for architecture validation)
- [ ] Optional: implementation code exists (for implementation alignment) or `FEATURE_ID` is set
- [ ] User has specified `VALIDATION_SCOPE`

---

## Related Actions

- **Before building:** run validate after the [plan action](./plan.md)
- **During building:** run validate to check alignment
- **After building / continuous:** run validate before deployment and regularly to catch drift

---

## Notes

- Validate is non-destructive (read-only analysis w.r.t. feature packages and code); it only reports findings and, in the implementation lane, regenerates the story index.
- Can run at any phase; re-run after fixing issues to confirm resolution.
- The validator scripts are tools — they never substitute for the PM/Architect agent-level validation, and validation summaries must never hide errors as warnings.

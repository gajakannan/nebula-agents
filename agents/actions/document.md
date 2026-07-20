# Action: Document

## User Intent

Generate technical documentation — API docs, README files, runbooks, developer guides, release notes — based on implemented code and architecture. Produces a base run evidence package so the run is auditable, but is **not** feature evidence and is never cited as a substitute for a feature's role reports.

## Agent Flow

```
D0  Scope lock
  ↓
D1  Draft            (produce or update the TARGETS)
  ↓
D2  Self-review gate (accuracy + quality against source)
  ↓
D3  Approval gate    (user reviews; then validate_templates)
Document Complete
```

**Flow Type:** Single agent — Technical Writer owns every produced doc file.

---

## Contract (generated — the spec is the source of truth)

The fixed procedure for this action — the `D0`–`D3` gates, inputs (`DOC_SCOPE`, `TARGETS`, `SOURCE_CODE`,
`FEATURE_REF`), forbidden actions, stop conditions, and conflict resolution — is declared once in
[`agents/actions/spec/document.yaml`](spec/document.yaml) and compiled into the operator/automation prompt
pair at `agents/templates/prompts/evidence-contract/document-operator-friendly.md` and
`document-automation-safe.md`. Regenerate with `python3 agents/scripts/render-prompts.py`; the `prompt_drift`
lifecycle gate fails if the committed prompts drift from the spec.
**Edit the spec, not this doc or the generated prompts.**

- **Scope** — `base-run-only`, and **outside the feature evidence contract**: no role reports, not evidence
  for a completed feature. `DOC_SCOPE ∈ {api | readme | runbook | developer-guide | release-notes | mixed}`;
  the run writes a base run package under `{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{DOC_RUN_ID}/`
  and the docs themselves at the `TARGETS`.
- **Exit validation** — after approval, `validate_templates.py` (exit 0); `kg/validate.py --check-drift` only
  when KG references changed; never `validate-feature-evidence.py`.

Drive the gates with `python3 agents/scripts/run-gate.py --action document --stage <D0..D3> ...` (`--list`
prints the ordered runbook; D3 pauses at the user approval checkpoint).

---

## Runtime Execution Boundary

- The builder runtime orchestrates documentation flow and gates; it remains stack-agnostic.
- Documentation that references runtime behavior (API examples, CLI commands, health checks) should be verified against application runtime containers when possible.
- The Technical Writer inspects code artifacts but does not compile or execute them — any execution validation runs in application runtime containers.

---

## Writer judgment (not encoded in the spec)

The spec owns the evidence contract; the method below is the Technical Writer's craft (keep aligned with
`agents/technical-writer/SKILL.md`).

### Per-type generation guidance

- **API docs** — generate/update the OpenAPI spec from code; endpoint purpose + behavior; realistic request/response examples; auth/authz requirements; error responses (codes + ProblemDetails); pagination/filtering/sorting; curl/SDK usage examples.
- **README** — project overview + tech stack with versions; prerequisites; a clone-to-running quick start; project structure; dev setup; testing; deployment (or link to a runbook); contributing (or link). Component READMEs cover component-specific setup + key files.
- **Runbooks** — numbered step-by-step with a verification step after each major action; troubleshooting for common failures; and rollback procedures (deployment, operations, migrations, backup/recovery).
- **Developer guides** — architecture overview with diagrams; code organization; dev workflow (branch → PR → review → merge); testing guide; common-tasks guide. Explain the "why", link rather than duplicate.

### Self-review checklist (D2)

- **Accuracy:** code references (paths, class names, endpoints), API examples, env vars, prerequisites, and version numbers all match the actual codebase.
- **Completeness:** every endpoint documented (API); quick start covers clone-to-running; runbooks include verification + rollback; error scenarios and auth documented.
- **Clarity:** no unexplained jargon; numbered sequential steps; syntax-highlighted examples; valid internal links; no TODO/placeholder text.
- **Testability:** commands are copy-pasteable and execute; the quick start works on a fresh clone; API examples return the expected responses.

### Best practices

Prefer OpenAPI/Swagger and realistic field values over generic descriptions ("Gets data"); keep API docs in sync with code; never skip error documentation or prerequisites; avoid ambiguous runbook language ("usually works"); don't duplicate README content in guides.

---

## Prerequisites

- [ ] Implementation code exists (backend and/or frontend).
- [ ] Architecture artifacts available in `{PRODUCT_ROOT}/planning-mds/`.
- [ ] API endpoints are stable and tested (for API docs).
- [ ] The application is deployable (for runbook verification).

## Related Actions

- **After:** [build action](./build.md) or [feature action](./feature.md) — document after building.
- **With:** [blog action](./blog.md) — docs for reference, blogs for narrative.

## Notes

- Version docs with the code and keep them co-located when possible; update docs in the same PR as the code change.
- Test all commands and examples before finalizing; treat documentation as part of the Definition of Done.
- Automate API doc generation from code annotations when available.

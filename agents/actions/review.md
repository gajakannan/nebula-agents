# Action: Review

## User Intent

Perform comprehensive code quality and security review on implemented features or the entire codebase, with an approval gate. Runs in two modes: **feature-scoped** (reports land in an existing feature run folder driven by `feature.md` G3) or **standalone** (reports land in a base run folder and satisfy no per-feature evidence requirement).

## Agent Flow

```
R0  Review scope lock
  ↓
R1  Parallel reviews  (Code Reviewer + Security)
  ↓
R2  Approval gate     (user reviews findings; reviewers record verdicts)
  ↓
R3  Stage validation  (feature-scoped only: validate-feature-evidence --stage G3)
Review Complete
```

**Flow Type:** Parallel reviews with a single approval gate; feature-scoped runs also validate the parent feature's G3 evidence.

---

## Contract (generated — the spec is the source of truth)

The fixed procedure for this action — the `R0`–`R3` gates, the two modes, inputs (`MODE`,
`PR_URL`/`SCOPE`/`PATHS`, `FEATURE_ID`/`RUN_ID`), ownership, forbidden actions, stop conditions, and
conflict resolution — is declared once in [`agents/actions/spec/review.yaml`](spec/review.yaml) and
compiled into the operator/automation prompt pair at
`agents/templates/prompts/evidence-contract/review-operator-friendly.md` and
`review-automation-safe.md`. Regenerate with `python3 agents/scripts/render-prompts.py`; the
`prompt_drift` lifecycle gate fails if the committed prompts drift from the spec.
**Edit the spec, not this doc or the generated prompts.**

- **Modes** — *feature-scoped*: pass `FEATURE_ID` + `RUN_ID` (the parent feature run); `OUTPUT_FOLDER`
  MUST already exist (created by `feature.md` at G0) — do not create a new run folder. *standalone*:
  generate `REVIEW_RUN_ID`, create `REVIEW_RUN_FOLDER` with the six §8 base run files; this run produces
  no feature evidence package and does **not** satisfy the per-feature review requirement.
- **Target** — usually a PR: `gh pr checkout <PR#>` + `gh pr view --json title,headRefName,baseRefName,files`
  derives `SCOPE=path-set`, `PATHS`, `DIFF_RANGE`, and (feature-scoped) `FEATURE_ID`. Explicit inputs
  override derived values.
- **Ownership** — `code-reviewer` owns `code-review-report.md`; `security` owns `security-review-report.md`
  (required when scope includes security or the feature manifest carries `security_sensitive_scope=true`).
  Report headings follow §14 (see the spec's `notes.evidence_outputs`).
- **Severity** — the R2 approval gate uses the `review-family` profile; compute allowed outcomes with
  `python3 agents/scripts/gate_policy.py --profile review-family ...`. Passing code verdicts:
  `APPROVED` / `APPROVED WITH RECOMMENDATIONS` (change-set) or `PASS` / `PASS WITH RECOMMENDATIONS`
  (codebase audit); blocking: `REQUEST CHANGES` / `REJECTED`.

Drive the gates with `python3 agents/scripts/run-gate.py --action review --stage <R0..R3> ...`
(`--list` prints the ordered runbook). Per-gate acceptance in feature-scoped mode is
`validate-feature-evidence.py --stage G3` (invoked by `run-gate.py`).

---

## Runtime Execution Boundary

- The builder runtime orchestrates review flow and gate decisions; it remains stack-agnostic.
- Stack-specific compile/test/lint/security execution must run in application runtime containers (or CI jobs built from those container definitions).
- Review gate decisions must reference evidence generated from those application runtime executions.

---

## Reviewer judgment (not encoded in the spec)

The spec owns the evidence contract; the analytical method below is the reviewers' judgment — keep it
aligned with `agents/code-reviewer/SKILL.md` and `agents/security/SKILL.md`.

### Code review checklist

- Structure/organization, SOLID, clean-architecture boundaries, naming, error handling, and
  over/under-engineering; SOLUTION-PATTERNS.md compliance; frontend UX rule-set compliance when UI changed.
- Test coverage and quality; require a fast-layer proof for changed behavior or a justified skip.
- Acceptance-criteria mapping; treat a non-obvious change without a `// WHY:` (or language equivalent) marker as a blocker.
- If inline decision markers changed, require `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --regenerate-decisions --check-decisions` evidence.
- When `coverage-report.yaml` carries Phase 3 freshness signals, apply hotspot/ownership gates per touched node:
  `hotspot_rank` ≤ 5 (or `hotspot_score` ≥ 0.80) → require explicit second-reviewer evidence;
  `bus_factor_flag: true` → require `primary_owner` acknowledgement on the PR
  (thresholds: `agents/architect/references/hotspot-review-guide.md`).
- Run `python3 {PRODUCT_ROOT}/scripts/kg/risk.py <node-id|--file|--symbol>` per touched canonical node:
  `kg.risk` ≥ 7 (high) → require an additional reviewer beyond the PR author;
  `kg.risk` ≥ 9 (critical) → require a `workstate.py decision --topic risk-acknowledgement` entry referenced from the PR before merge
  (weights/bands: `agents/architect/references/risk-scoring-guide.md`).
- Run `python3 {PRODUCT_ROOT}/scripts/kg/diff-impact.py <pr-range>` and attach `affected_nodes` to the review notes; surface unanticipated canonical nodes as a discussion item (not an auto-fail).
- For symbol names the diff introduces or moves, run `python3 {PRODUCT_ROOT}/scripts/kg/lookup.py --defines <name>` to detect duplicate/near-duplicate surface elsewhere.

### Security review checklist

- OWASP Top 10 (A01 Broken Access Control … A10 SSRF), authorization (Casbin ABAC, per-endpoint,
  server-side only), input validation/sanitization, secrets management (no hardcoded secrets), audit
  logging completeness, error messages (no info leakage), HTTPS/TLS, CORS, and dependency vulnerabilities.

## Review Severity Levels

- **Code — Critical:** breaks architecture, causes bugs, violates core principles, prevents deployment. **High:** code smells, poor patterns, missing tests, maintainability. **Medium:** style/minor improvements. **Low:** suggestions.
- **Security — Critical:** actively exploitable (SQLi, auth bypass, XSS). **High:** conditional vulnerabilities, significant gaps. **Medium:** defense-in-depth gaps, non-critical misconfig. **Low:** hardening recommendations.

---

## Prerequisites

Before running the review action:
- [ ] Implementation completed (features or full codebase)
- [ ] Tests written and passing
- [ ] Code committed to version control (a PR for the usual PR-scoped flow)
- [ ] SOLUTION-PATTERNS.md exists
- [ ] For feature-scoped mode: the feature run folder exists and `feature.md` G0 has passed

---

## Related Actions

- **Before:** [build action](./build.md) or [feature action](./feature.md) — implement first
- **After:** [document action](./document.md) — document after approval
- **Part of:** [feature action](./feature.md) G3 / [build action](./build.md) drive review as the feature-scoped mode

---

## Notes

- Review runs on any scope (feature, PR, full codebase); both reviews run in parallel for efficiency.
- Critical issues block approval; high issues require explicit mitigation justification if approved (agents recommend, the user decides within the gate constraints).
- Automated tools supplement but do not replace agent reviews.
- Don't mix feature-scoped and standalone outputs in one session; don't skip security review when `security_sensitive_scope=true`.

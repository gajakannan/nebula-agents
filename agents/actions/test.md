# Action: Test

## User Intent

Develop comprehensive test suites and execute testing to ensure quality, coverage, and correctness. Runs in two modes: **feature-scoped** (the QE reports land in an existing feature run folder and feed `feature.md` G2/G5) or **standalone** (reports land in a base run folder and satisfy no per-feature evidence requirement).

## Agent Flow

```
T0  Test plan          (test-plan.md)
  ↓
T1  Test execution     (test-execution-report.md, raw artifact paths)
  ↓
T2  Coverage           (coverage-report.md — always exists, waiver inline if applicable)
  ↓
T3  Self-review gate   (QE self-checks the three reports)
  ↓
T4  Quality gate       (coverage + pass-rate thresholds met, or waiver accepted)
  ↓
T5  Stage validation   (feature-scoped only: validate-feature-evidence --stage G2)
Test Complete
```

**Flow Type:** Single agent (Quality Engineer) with a self-review gate and a quality gate.

---

## Contract (generated — the spec is the source of truth)

The fixed procedure for this action — the `T0`–`T5` gates, the two modes, inputs (`MODE`, `TEST_SCOPE`,
`FEATURE_ID`/`RUN_ID`, `STORIES`), ownership, forbidden actions, stop conditions, and conflict resolution —
is declared once in [`agents/actions/spec/test.yaml`](spec/test.yaml) and compiled into the
operator/automation prompt pair at
`agents/templates/prompts/evidence-contract/test-operator-friendly.md` and `test-automation-safe.md`.
Regenerate with `python3 agents/scripts/render-prompts.py`; the `prompt_drift` lifecycle gate fails if the
committed prompts drift from the spec. **Edit the spec, not this doc or the generated prompts.**

- **Modes** — *feature-scoped*: pass `FEATURE_ID` + `RUN_ID` (the parent feature run); `OUTPUT_FOLDER` MUST
  already exist — do not create a new run folder; the reports feed the parent feature's G2/G5. *standalone*:
  generate `TEST_RUN_ID`, create `TEST_RUN_FOLDER` with the six §8 base run files; this run produces no
  feature evidence package and does **not** satisfy the per-feature QE requirement.
- **Scope** — `TEST_SCOPE ∈ {unit | component | integration | e2e | api | accessibility | regression | all}`.
- **Ownership & outputs** — `quality-engineer` owns `test-plan.md`, `test-execution-report.md`, and
  `coverage-report.md` (all three required for completed-terminal features per §10). `coverage-report.md`
  **always exists**, even when coverage is waived. Raw test/coverage/screenshot output lives under the run's
  `artifacts/{test-results,coverage,screenshots}` subfolders; report section headings are in the spec's
  `notes.evidence_outputs`. Coverage targets are **feature-scoped** (per §29) — not universal thresholds.
- **Severity** — T4 is a threshold quality gate, not severity arithmetic (`severity_gate: none`). Artifact
  paths are required — summary prose alone is not evidence for a passing gate.

Drive the gates with `python3 agents/scripts/run-gate.py --action test --stage <T0..T5> ...`
(`--list` prints the ordered runbook). Per-gate acceptance in feature-scoped mode is
`validate-feature-evidence.py --stage G2` (invoked by `run-gate.py`).

---

## Runtime Execution Boundary

- The builder runtime orchestrates test planning and gate decisions; it remains stack-agnostic.
- All test execution (unit, integration, E2E, performance) must run in application runtime containers (or CI jobs built from those container definitions).
- Coverage reports, pass/fail results, and performance baselines are produced by application runtime executions and cited as evidence — with artifact paths, not summary prose alone.

---

## QE judgment (not encoded in the spec)

The spec owns the evidence contract; the method below is the Quality Engineer's judgment — keep it aligned
with `agents/quality-engineer/SKILL.md`.

### Test-coverage discovery

- For each touched canonical node, run `python3 {PRODUCT_ROOT}/scripts/kg/lookup.py --untested <node-id>`; each finding names a bound symbol with no caller in a `*.tests` bucket.
- Add each finding to the story-to-test mapping as a candidate case, or record an explicit exemption (`--untested-exempt-node <node-id>`) with rationale in the plan. Use `validate.py --check-untested` for whole-repo release-readiness checks.

### Test quality self-review (T3)

- Every acceptance criterion has a corresponding test; tests are independent/isolated with clear arrange-act-assert structure and descriptive names; no flaky (non-deterministic) tests.
- Edge cases (empty lists, max values, nulls, boundaries) and error scenarios (validation failures, not-found, unauthorized) are covered; fixtures are realistic; mocks accurately represent real behavior.
- Layer discipline: unit fast (< 1s), integration reasonable (< 5s), E2E covers the complete flow. If a fast layer is skipped, the reason is explicit and defensible; don't approve a behavior change on slow-layer evidence alone when faster-layer coverage is expected and missing.
- Required evidence artifacts exist and every cited path resolves.

### Test pyramid

- **Unit** — functions/methods/components; fast, dependencies mocked; the most tests.
- **Integration** — API endpoints, DB operations, service integrations; real test DB, mocked external services.
- **E2E** — complete user workflows across the full stack in containers; fewest, critical paths only.
- **Performance (when in scope)** — API latency, DB queries, UI rendering baselines in a production-like environment.

---

## Prerequisites

Before running the test action:
- [ ] Implementation code exists (backend and/or frontend)
- [ ] User stories with acceptance criteria available in `{PRODUCT_ROOT}/planning-mds/features/`
- [ ] Test framework and tools configured in the project
- [ ] Application runtime containers can build and run
- [ ] For feature-scoped mode: the feature run folder exists and `feature.md` G1 has passed

---

## Related Actions

- **Part of:** [feature action](./feature.md) G2 / [build action](./build.md) — testing is part of implementation
- **Before:** [review action](./review.md) — review validates test quality
- **After:** implementation — always test after building

---

## Notes

- Test can run standalone or as the feature-scoped QE lane of build/feature; focus on quality over quantity and prefer fast, focused tests (many unit, fewer integration, fewest E2E).
- `coverage-report.md` must exist even when coverage is waived; a coverage waiver still needs PM acceptance at closeout (handled at the feature's G8).
- All test execution runs in application runtime containers, not the builder runtime; run tests in CI/CD for continuous validation.

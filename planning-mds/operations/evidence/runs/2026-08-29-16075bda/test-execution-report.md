# Test Execution Report — F0003

**Run:** `2026-08-29-16075bda` · **Gate:** G2 · **Owner:** Quality Engineer · **Date:** 2026-08-29
**Result: PASS**

## Execution

| Interpreter | Tests | Failures | Errors | Skipped |
|-------------|-------|----------|--------|---------|
| Python 3.14.4 | **727** | 0 | 0 | 0 |
| Python 3.12.13 | **727** | 0 | 0 | 0 |
| Python 3.11.15 | **727** | 0 | 0 | 0 |

`artifacts/test-results/junit.xml` records the 3.14 execution. Nothing is skipped —
including `test_real_tmux_lifecycle.py`, which skips silently when the package is
installed in a way it cannot detect, and does not here.

Framework suites outside `engine/`: 375 (`agents`) and 186 + 1 skipped (`scripts/kg`).

## Composition

| Suite | Tests | What it holds |
|-------|-------|---------------|
| F0001 regression | 514 | Pass **unmodified** — S0007's acceptance criterion |
| F0003 unit | 70 | Identity, domain records, capability matrix, metric derivation |
| F0003 contract | 66 | Schemas, facade split, layering, determinism, MCP, CLI, packaging |
| F0003 integration | 35 | Index, wrap, summarize, proposals, full lifecycle |
| F0003 security | 12 | Modes, containment, sentinel sweep, allowlist |

## Determinism (S0005)

| Check | Result |
|-------|--------|
| Repeated calls, one process | identical |
| Separate processes | identical — catches any set iteration, which the in-process check cannot |
| 3.11 / 3.12 / 3.14 | identical corpus digest |

## Regression boundaries held

| Boundary | Result |
|----------|--------|
| 514 F0001 tests unmodified | PASS |
| Audit stream byte-identical vs pre-split `main` | PASS — re-verified at Steps 3–6 |
| Summary corpus digest stable across steps | PASS |
| No new required runtime dependency | PASS — verified against a clean install |

## Defects found by testing during this run

Recorded because "all green" is only meaningful alongside what the tests actually caught.

| Defect | Found by | Status |
|--------|----------|--------|
| Validator rule-name regex swallowed the delimiting colon, so every failed rule was reported as `out_of_scope_present:` | Fixture corpus authored **before** the extractor | Fixed, Step 5 |
| `infer_kind` filed `validator.txt` as `status`, which has no failure rules — so a real validator failure could **never** reach a learning proposal | End-to-end smoke. Every layer's unit tests passed; the defect was in the seam | Fixed, Step 6 |
| An unknown MCP tool produced a non-schema-conformant envelope | Validating responses against the committed schema in test | Fixed, Step 7 |
| `assert` guarding the MCP handler/contract invariant is stripped under `python -O` | bandit B101, triaged at G2 rather than dismissed as "low" | Fixed, G2 |
| Layering violation: `application/evidence.py` imported `infrastructure.summarizers` | Reading — no test existed | Fixed and a guard added, Step 5 |
| `.gitignore` excluded committed coverage evidence; F0001's archived runs carry the same dangling reference | `git status` after staging | Fixed, Step 8 |

Two of these — the seam defect and the layering violation — were invisible to the layer's
own tests. Both now have a lane that would catch a recurrence.

## Known gaps

Stated in `artifacts/test-coverage/acceptance-criteria-map.md` and repeated here so the
gate does not have to go looking:

1. Provider and tmux seams are faked in F0003's tests; real-process coverage is F0001's.
   F0003 adds no new subprocess path.
2. No third-party MCP host conformance suite is run.
3. `gate_wait_seconds` approximates from the gate's `updated_at`.

## Verdict

**PASS.** No failures, no errors, nothing skipped, on all three supported interpreters.

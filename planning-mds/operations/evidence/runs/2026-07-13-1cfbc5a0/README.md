# Feature Evidence README — F0001-tmux-native-agent-cockpit run 2026-07-13-1cfbc5a0

## Run Summary

The Architect started the governed `feature` action for F0001, created the implementation-level assembly plan and launch-descriptor contract, initialized required signoffs, and moved the active planning trackers to `In Progress`. Implementation and G2 quality evidence completed, but the second-cycle code review returned `REQUEST CHANGES`; this run therefore stops at G3 before approval.

## Status

Final state for this run: `in-progress — G3 blocked`.

## Evidence Index

- `evidence-manifest.json` — schema v1 run index and scope declaration
- `action-context.md` — run identity, inputs, assumptions, scope, and current gate
- `artifact-trace.md` — artifacts read, created, updated, and intentionally deferred
- `gate-decisions.md` — lifecycle gate decisions
- `commands.log` — JSON Lines command telemetry
- `lifecycle-gates.log` — stage validator results
- `g0-assembly-plan-validation.md` — Architect G0 review
- `g1-runtime-preflight.md` — non-containerized Python/tmux/provider preflight
- `g2-self-review.md` — implementation self-review
- `test-plan.md`, `test-execution-report.md`, `coverage-report.md` — QE plan and verified results
- `deployability-check.md` — local package/runtime readiness
- `code-review-report.md` — blocking `REQUEST CHANGES` review
- `security-review-report.md` — `PASS WITH RECOMMENDATIONS` security review
- `artifacts/diffs/changed-files.txt` — current SCM scope snapshot

## Validation Summary

G0 assembly-plan validation, G1 runtime preflight, and G2 quality/deployability are `PASS`. The final acceptance suite is 424/424 at 90.03% line coverage, and the real-tmux lifecycle passes. Security review is `PASS WITH RECOMMENDATIONS` with three Low items and no open Medium/High/Critical security finding. Code review is `REQUEST CHANGES` with six Critical, one High, and one Medium blocking finding, so G3 is blocked and G4-G8 were not run.

## Open Follow-ups

- Close every blocking finding in `code-review-report.md`, including the committed branch-coverage gate, before requesting a new G3 verdict.
- Reconcile the pytest major-version contract between the assembly plan and `engine/pyproject.toml`.
- Preserve the three Low security recommendations in `security-review-report.md` for a future release-hardening pass.
- Do not open G4 or attempt G5-G8 from this blocked run.

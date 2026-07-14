# Feature Evidence README — F0001 remediation run 2026-07-14-b885d64c

## Run Summary

This is a separately authorized F0001 `feature` remediation run linked to blocked run `2026-07-13-1cfbc5a0`. It reopens G0-G3 only to close the eight code-review blockers and the two operator-visible demo gaps before presenting a new G4 decision.

## Status

Current state: `in-progress — G6 passed; G7 blocked by the documented product KG/compiler bootstrap limitation; G8 closed`.

## Evidence Index

- `evidence-manifest.json` — schema v1 run index with `rerun_of`
- `action-context.md` — run identity, inputs, scope, and lifecycle stage
- `artifact-trace.md` — exact governed artifacts read and changed
- `gate-decisions.md` — gate decisions for this remediation run
- `commands.log` — append-only JSON Lines command telemetry
- `lifecycle-gates.log` — staged evidence-validator results
- `g0-assembly-plan-validation.md` — Architect remediation-plan reconciliation
- `g1-runtime-preflight.md` — isolated package/provider/tmux readiness
- `test-plan.md` — R1-R10 acceptance strategy and pass criteria
- `test-execution-report.md` — final 514-test execution and remediation mapping
- `coverage-report.md` — official line/branch evidence and risk-module gates
- `deployability-check.md` — clean-package, runtime, security, and rollback checks
- `g2-self-review.md` — implementation/QE closure matrix and G3 handoff
- `code-review-report-cycle-1.md` — immutable first G3 Code Reviewer `REQUEST CHANGES` verdict
- `security-review-report-cycle-1.md` — immutable first G3 Security Reviewer `REQUEST CHANGES` verdict
- `code-review-report-cycle-2.md` — immutable second G3 Code Reviewer `PASS WITH RECOMMENDATIONS` verdict
- `security-review-report-cycle-2.md` — immutable second G3 Security Reviewer `REQUEST CHANGES` verdict
- `code-review-report-cycle-3.md` — immutable third G3 Code Reviewer `REQUEST CHANGES` verdict
- `security-review-report-cycle-3.md` — immutable third G3 Security Reviewer `REQUEST CHANGES` verdict
- `code-review-report-cycle-4.md` — immutable fourth G3 Code Reviewer `REQUEST CHANGES` verdict
- `security-review-report-cycle-4.md` — immutable fourth G3 Security Reviewer `REQUEST CHANGES` verdict
- `code-review-report.md` and `security-review-report.md` — final cycle-5 canonical `PASS WITH RECOMMENDATIONS` verdicts
- `signoff-ledger.md` — current per-story passing evidence for every required role
- `feature-action-execution.md` — gate-by-gate remediation and review timeline
- `kg-reconciliation.md` — as-built binding map and truthful G7 bootstrap blocker

## Validation Summary

G0-G2 passed. Final G3 cycle 5 independently closed H-01 through H-06. Code and Security both returned `PASS WITH RECOMMENDATIONS`, with zero Critical or High findings. The final package has 514 passing tests, 90.67% line coverage, all mandatory risk branches at 100%, clean dependency/secrets scans, 13 Low/0 Medium/0 High SAST findings, and passing real-tmux/descriptor lanes.

## Open Follow-ups

- Approved implementation candidate frozen at `99d2020c8ccaa23f370eef526c27867395981c7e`; exact 160-path diff reconciled.
- G7 requires an explicit governance choice: adopt the compiled KG toolchain in this repo, or approve and implement a framework/product exception mechanism for non-adopter repositories.
- Do not start G8 archive/publish closeout while G7 is blocked.
- Disposition all non-blocking Code and Security recommendations in `pm-closeout.md`.

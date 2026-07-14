# F0001 Remediation Test Plan — run 2026-07-14-b885d64c

## Scope

This acceptance lane validates the R1-R10 remediation addendum and all six approved F0001 stories without expanding the local Python/tmux architecture:

- R1: exact doctor path diagnostics and absolute missing paths.
- R2: fail-closed attach authorization and launch compensation when tmux setup fails.
- R3: last-valid evidence reconciliation, bounded JSON/YAML/Markdown validation, and complete production watch paths.
- R4: descriptor-bound validator scripts, workspace root, and governed feature path.
- R5: transcript pipe liveness, crash-consistent completed/failed sidecars, and bounded durable failure reasons.
- R6: owner-only recovery and discovery of corrupt run records in CLI and TUI projections.
- R7: official branch-enabled Cobertura evidence, with 100% branch coverage in authorization, transitions, redaction, and session entry.
- R8: reproducible clean test-toolchain installation on the upstream security-fixed pytest line.
- R9: product-root discovery through explicit option, `NEBULA_AGENTS_PRODUCT_ROOT`, then current working directory.
- R10: launch output that explains the separate TUI and tmux attach commands.

## Test Levels

- Unit: authorization, transitions, runs, transcripts, preflight, watcher/validator, adapters, and TUI state/actions.
- Contract: CLI grammar and output, schemas, formatters, committed dependency contract, and documentation assertions.
- Integration: bootstrap, filesystem recovery, process/provider execution, transcript pipe/filter, descriptor validators, and real tmux lifecycle.
- Security: no-shell process boundaries, descriptor containment, default-deny authorization, secret redaction, unsafe-path rejection, crash consistency, and corrupt-state recovery.
- Smoke: installed console entry, help, doctor from outside the repository, compileall, governed validators, and diff hygiene.

## Pass Criteria

- All tests pass with zero failures, errors, skips, or expected failures.
- Line coverage is at least 85%, without waiver.
- Branch coverage is exactly 100% for `authorization.py`, `transitions.py`, `redaction.py`, and `session_entry.py`.
- The real-tmux integration test passes in an approved host-runtime lane and cleans up its unique session.
- Dependency and secret scans are clean; SAST findings are preserved for independent Security Reviewer disposition.
- Story, tracker, template, architecture, schema, compile, and whitespace checks pass.

## Environment

- Python 3.14.4 in `/tmp/f0001-remediation-venv` with the package installed editable from `engine[test]`.
- pytest 9.1.1, pytest-cov 6.3.0, and jsonschema 4.26.0.
- tmux 3.6 in the approved host-runtime lane.
- No real provider model turn, provider credential inspection, HTTP listener, or remote deployment is part of this plan.

The initial clean-environment audit reproduced CVE-2025-71176 on the prior pytest-8 constraint. The plan and package contract were therefore reconciled to the upstream fixed `pytest>=9.0.3,<10` range before the final acceptance run.

## Result

PASS — the final refreshed suite completed all planned acceptance, failure-injection, coverage, runtime, and static validation criteria with 514 passing tests.

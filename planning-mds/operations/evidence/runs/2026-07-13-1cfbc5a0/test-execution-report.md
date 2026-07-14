# F0001 Test Execution Report — run 2026-07-13-1cfbc5a0

## Acceptance Command

```text
/tmp/f0001-venv/bin/pytest -q engine/tests --cov=nebula_agents --cov-report=term-missing --cov-report=xml:planning-mds/operations/evidence/runs/2026-07-13-1cfbc5a0/artifacts/test-results/coverage.xml --cov-fail-under=85 --junitxml=planning-mds/operations/evidence/runs/2026-07-13-1cfbc5a0/artifacts/test-results/junit.xml
```

The exact command ran in the approved host-runtime context because the filesystem sandbox denies access to the tmux socket.

## Results

| Measure | Result |
|---------|--------|
| Tests | 424 passed |
| Failures / errors | 0 / 0 |
| Skipped / xfail | 0 / 0 |
| Duration | 1.76 seconds (JUnit suite time: 1.749 seconds) |
| Line coverage | 90.03% (3,577 / 3,973 statements) |
| Required coverage | 85% |
| Focused contract regressions | 131 passed in 0.25 seconds |
| Real tmux lifecycle | 1 passed in 0.47 seconds |

JUnit reports `tests=424`, `failures=0`, `errors=0`, and `skipped=0`. With no skipped records, the expected-failure count is also zero. Coverage XML reports `lines-covered=3577`, `lines-valid=3973`, and line-rate `0.9003`.

## Story And Risk Coverage

- S0001: ready/unavailable/permission preflight paths, exact planning-doc and missing-path results, prompt symlink rejection, provider argv isolation, policy/identity errors, and read-only doctor behavior.
- S0002: launch rollback, bounded colliding-session errors, descriptor/feature/story ownership and containment, fake provider execution, real tmux attach, exactly-one start, and stale-session projection.
- S0003: concurrent first use, atomic state/events, recovery images, immutable aggregate identity, bounded retention, canonical evidence-run discovery, malformed/missing observations that preserve persisted last-valid state, restoration reconciliation, and semantic dedupe.
- S0004: validator pass/fail/timeout/exception and feature-root containment, terminal audit events, evidence symlink rejection, reviewer path/secret suppression, authorization, evidence eligibility, decision confirmation, hold reasons, and stale revision.
- S0005: enable/complete/failure compensation, delayed completion and post-disable failure, durable ongoing filter failure, safe preview, transcript symlinks/missing files, chunk-boundary secrets, private-key EOF, GitHub tokens, findings recovery, and attach-after-transcript-failure.
- S0006: CLI success/error envelopes, bounded records, control stripping, JSON/table stability, TUI selection/resize/timeout auto-reconcile, confirmations, transcript controls, and safe evidence/status projection.

## Frontend / Terminal UX Notes

`frontend_in_scope=true` refers to the curses terminal UI. Feature-level behavioral tests exercise keyboard navigation, confirmation screens, selection preservation, resize handling, 500 ms background reconciliation, gate availability, transcript enable/complete/retry/preview controls, sanitized error display, and small-terminal rendering. No browser, DOM, CSS, or network frontend exists. A manual live curses resize session is a residual usability check, not a release-blocking correctness gap, because mutations and rendering behavior are covered through the fake-window contract lane.

## Defects Found And Closed

QE and first-cycle review exposed prompt misbinding, disconnected evidence reconciliation, fail-open private-key EOF redaction, descriptor rollback, validator terminalization, transcript symlink/error handling, streaming output bounds, tmux pipe disable, runtime override propagation, authorization/CAS/recovery invariants, GID bindings, policy symlinks, TUI polling, and transcript lifecycle gaps. Production owners fixed them and regression tests are included in the final green count.

## Raw Artifacts

- `artifacts/test-results/junit.xml` — 62,864 bytes; SHA-256 `632209797c2ff935a528b5e22c6c2f566621c918aad27ffc5bf03d1539fd379c`
- `artifacts/test-results/coverage.xml` — 149,476 bytes; SHA-256 `482883b0e1b1808cc985d09c88cea31eafa181ff83a4e731c6d42d1ac5d32b73`

## Result

PASS

# F0001 Remediation Test Execution Report — run 2026-07-14-b885d64c

## Acceptance Command

```text
/tmp/f0001-remediation-venv/bin/pytest -q engine/tests --cov=nebula_agents --cov-branch --cov-config=engine/pyproject.toml --cov-report=term-missing --cov-report=xml:<COVERAGE_XML> --cov-fail-under=85 --junitxml=<JUNIT_XML>
```

The exact final command ran in the approved host-runtime context because the filesystem sandbox cannot access the tmux server socket.

## Results

| Measure | Result |
|---------|--------|
| Tests | 514 passed |
| Failures / errors | 0 / 0 |
| Skipped / xfail | 0 / 0 |
| Wall duration | 3.07 seconds (JUnit suite time: 3.053 seconds) |
| Line coverage | 90.67% (4,189 / 4,620) |
| Aggregate branch coverage | 81.32% (1,197 / 1,472) |
| Required risk-module branches | 100% in all four modules |
| Required line coverage | 85% |
| Focused real tmux lifecycle | 1 passed in 0.48 seconds |

JUnit reports `tests=514`, `failures=0`, `errors=0`, and `skipped=0`. The final Cobertura XML reports `lines-covered=4189`, `lines-valid=4620`, `line-rate=0.9067`, `branches-covered=1197`, `branches-valid=1472`, and `branch-rate=0.8132`.

## Remediation Coverage

- R1: exact full PATHS rendering and absolute missing-path behavior are covered in preflight, formatter, CLI, and manual outside-root doctor tests.
- R2: failed/exited attach denial and tmux-session compensation are covered in service and adapter failure tests. Cycle 2 adds exact real-repository pre-publication and post-`os.replace`/pre-directory-`fsync` faults and proves `LaunchFailed` terminalization from the recovered authoritative revision.
- R3: malformed JSON/YAML/Markdown handling, preservation of the durable last-valid projection, restoration, and the full lifecycle watch set are covered.
- R4: the child now consumes bounded story bytes from a pinned inherited feature descriptor with `dir_fd`, `O_NOFOLLOW`, safe metadata, and stable double-read fingerprints. Real-subprocess tests reject pre-existing symlinks, a post-parent-check outside-target swap, unsafe modes, and FIFO inputs; all three production validators still return 0.
- R5: pipe liveness, completed/failed sidecars, delayed terminalization, post-disable failure, recovery, and durable sanitized `failure_reason` behavior are covered. Cycle 2 adds exact real-repository commit faults and proves only a recovered `Active` state restores capture; recovered `Completed`/`Failed` states never restart it.
- R6: corrupt record discovery and recovery are covered through repository, query, CLI, formatter, and TUI tests.
- R7: the final official XML contains branch counters and the four mandatory modules each have branch-rate `1`.
- R8: the final environment uses pytest 9.1.1, `pip check` is clean, and the resolved dependency audit is clean.
- R9: explicit option, environment, and cwd product-root precedence is covered; an installed doctor command succeeded from `/tmp` using the environment variable.
- R10: CLI/formatter contracts assert actionable post-launch `tui` and `nebula-agents attach --run-id ...` guidance.
- H-04/H-04R: terminal/non-active state is published only after pipe disable succeeds and liveness verifies inactive. If conservative `TranscriptEnabled`/`Active` compensation cannot be published or recovered as Active, the application terminates the immutable owning tmux session and proves it absent before returning `STATE_IO`.
- H-05: production tmux pipe and session probes accept only their documented success/absence values. Timeouts, nonstandard exit codes, and malformed pipe output raise stable `COMMAND_FAILED`; transcript status propagation cannot convert an unavailable probe into a false terminal fact.
- H-06: direct and launch first-authoritative-recovery failures now take the same verified owning-session termination path and return stable `STATE_IO`; a transcript failure whose pipe was already verified stopped does not kill the provider session.

## Additional Validation

- Story validators: all six F0001 story contracts passed.
- Trackers, templates, architecture, schemas, scoped code-quality checks, and changed-file Ruff checks: passed.
- Python source and test compileall: passed.
- `git diff --check`: passed.
- Dependency scan: clean after the pytest security reconciliation.
- Secret scan: clean.
- Bandit SAST: 13 Low, 0 Medium, 0 High findings over the final source and changed story validator; independent Security Reviewer disposition is required at the fresh G3 follow-up.

## Feature-Level Frontend Notes

F0001's frontend is the curses terminal UI under `engine/src/nebula_agents/presentation/tui.py`; there is no browser or web frontend. Fake-window unit and behavioral tests cover session list/detail rendering, gate and validator views, keyboard navigation, resize behavior, bounded/sanitized output, and TUI actions. Contract tests also verify the CLI/TUI projection boundary. These lanes are included in the 514 passing tests and the 90.67% coverage result.

## Raw Artifacts

- `artifacts/test-results/junit.xml` — 76,548 bytes; SHA-256 `df160ca44d33a73feef73e9dc62c44cfc50898bd1bab3ece6abe0cc4320679a6`
- `artifacts/test-results/coverage.xml` — 212,114 bytes; SHA-256 `aa55e2cdb15495bb1c573703922a20cf13e716fb141c3dd53f669bafe9bc906f`

## Result

PASS

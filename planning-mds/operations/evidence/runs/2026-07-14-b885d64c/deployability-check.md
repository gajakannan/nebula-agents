# F0001 Remediation Deployability Check — run 2026-07-14-b885d64c

## Scope

F0001 is a local Python package and tmux process, not a hosted deployment. This check covers clean package composition, the installed console entry, product-root and runtime discovery, host dependencies, validation execution, transcript/recovery behavior, and safe cleanup. No Docker, HTTP service, database migration, CI/CD promotion, or remote environment is in scope, and no deployment configuration changed.

## Checks

| Check | Result | Evidence |
|-------|--------|----------|
| Clean editable install | PASS | `/tmp/f0001-remediation-venv` installed from `engine[test]` |
| Security-fixed test toolchain | PASS | pytest 9.1.1 satisfies committed `pytest>=9.0.3,<10`; prior pytest-8 constraint was rejected after CVE reproduction |
| Dependency consistency | PASS | `pip check` and resolved dependency audit are clean |
| Installed import and console help | PASS | package imports; `nebula-agents --help` includes `recover` |
| Product root outside repository | PASS | doctor from `/tmp` succeeded with `NEBULA_AGENTS_PRODUCT_ROOT` |
| Exact doctor diagnostics | PASS | table output includes workspace, planning, runtime, prompt, tmux, and provider executable paths |
| Runtime and provider preflight | PASS | Python 3.14.4, tmux 3.6, Codex 0.144.3, and Claude 2.1.207 were probed successfully |
| Full acceptance suite | PASS | 514 passed; zero failures/errors/skips/xfails; 90.67% line coverage |
| Risk-module branches | PASS | authorization, transitions, redaction, and session entry each report 100% |
| Real tmux lifecycle | PASS | focused host-runtime integration passed in 0.48 seconds and cleaned up its unique session |
| Governed validators | PASS | production descriptor runner returned 0 for stories, trackers, and templates |
| Recovery and compensation | PASS | exact pre/post-publication launch and transcript commit faults reconcile authoritative revision/event state before tmux/pipe compensation |
| Descendant validator containment | PASS | pinned descriptor child reads reject pre-existing and post-check symlink swaps, unsafe modes, and FIFO inputs through a real subprocess |
| Transcript stop truthfulness | PASS | terminal state requires positively verified inactive capture; unavailable probes and first recovery failure fail closed, while failed truthful-Active publication or unrecoverable ambiguity terminates and verifies absence of the owning session before stable STATE_IO |
| Compile and diff hygiene | PASS | source/tests compile, `git diff --check`, architecture, schemas, stories, trackers, and templates pass |

## Security Evidence

- Dependency audit: clean; 0 known vulnerabilities in the resolved environment.
- Secret scan: clean; no detected secrets.
- Bandit SAST: 13 Low, 0 Medium, 0 High findings across 7,199 scanned lines; retained for the final Security Reviewer disposition.
- DAST: not run because the approved local CLI/TUI architecture exposes no network listener or HTTP target. Architect records the no-target waiver; Security Reviewer must independently confirm or reject it at G3.

## Operational Requirements

- POSIX/WSL environment with Python 3.11+, tmux, curses, fcntl, and `/proc/self/fd` support for descriptor-bound validators.
- At least one supported native provider CLI installed; login and credentials remain provider-owned.
- A product root containing the governed feature, schema, validator, and prompt contracts.
- Custom runtime roots must be owner-only and non-symlinked.

## Rollback

Uninstall the Python package and remove only the operator-owned `.nebula-agents/runtime` directory after terminating recorded tmux sessions. The feature creates no database, remote resource, service, or migration requiring a separate rollback plane.

## Result

PASS

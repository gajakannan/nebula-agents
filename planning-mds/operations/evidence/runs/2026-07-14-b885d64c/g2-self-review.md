# G2 Self Review — F0001 remediation run 2026-07-14-b885d64c

## Scope Review

The remediation remains inside the approved local Python/tmux cockpit. It changes `engine/`, F0001 planning/architecture/schema/operator documentation, this linked evidence run, and the G7 knowledge-graph source/compiler/CI governance surface. It does not introduce automatic TUI entry, automatic tmux attachment, managed providers, HTTP services, databases, hosted deployment, or cross-feature runtime behavior.

Manifest scope is reconciled after G7: runtime-bearing `true`, deployment-config-changed `true` for `.github/workflows/kg-reproducibility.yml`, frontend-in-scope `true` for curses, and security-sensitive-scope `true` for authorization, local process execution, filesystem containment, evidence, recovery, and transcripts. The false-to-true deployment change adds DevOps to the required-role and story-signoff matrices; `deployability-check.md` contains the fresh CI review.

## R1-R10 Closure

| Item | Closure | Evidence |
|------|---------|----------|
| R1 | PASS | Absolute missing paths plus exact full doctor PATHS block in source, tests, and outside-root smoke |
| R2 | PASS | Attach denies failed/exited runs; exact post-publication faults recover the authoritative revision, kill tmux, and append `LaunchFailed` from that revision |
| R3 | PASS | Last-valid durable projection is preserved; bounded JSON/YAML/Markdown readers and full watch set are tested |
| R4 | PASS | Child story bytes are read below the pinned inherited descriptor with no-follow/stable metadata; the reproduced outside-target swap now fails closed |
| R5 | PASS | Ambiguous completion/enable outcomes recover current durable state before pipe compensation; terminal state never restarts capture |
| R6 | PASS | Corrupt records are discoverable and owner-recoverable in repository, query, CLI, formatter, and TUI paths |
| R7 | PASS | Official Cobertura XML includes branches; all four mandated risk modules are at 100% |
| R8 | PASS | Clean environment uses security-fixed pytest 9.1.1; metadata, plan, test, and dependency audit agree |
| R9 | PASS | Explicit option → environment → cwd product-root precedence is implemented, tested, and manually smoked from `/tmp` |
| R10 | PASS | Successful launch output prints separate TUI and tmux attach next steps |
| H-04/H-04R | PASS | Terminal transcript state requires verified inactive capture; if conservative Active persistence cannot be established, the owning tmux session is terminated and verified absent before STATE_IO |
| H-05 | PASS | Pipe/session probe timeouts, nonstandard exits, and malformed output fail closed and cannot authorize a terminal transcript fact |
| H-06 | PASS | First authoritative recovery failure in direct enable or launch triggers verified owning-session termination and stable STATE_IO; already-stopped failure paths preserve the provider |

## Acceptance Criteria Review

The final acceptance suite reports 514 passed with zero failures, errors, skips, or expected failures. Line coverage is 90.67% against the unwaived 85% gate. Authorization, transitions, redaction, and session entry each report 100% branch coverage. The focused real-tmux lifecycle passes in 0.48 seconds, and the production descriptor-bound runner passes all three allowlisted validators.

## Security Review Handoff

The final resolved dependency audit and expanded secret scan pass. Bandit reports 13 Low, 0 Medium, and 0 High findings across engine source plus the changed story validator; these are deliberately not self-waived and require fresh Security Reviewer interpretation. DAST has no valid target because this architecture opens no listener; the Architect records that no-target disposition for independent G3 confirmation.

G3 cycle 1 reports are preserved as `code-review-report-cycle-1.md` and `security-review-report-cycle-1.md`. Their H-01/H-02/H-03 reproductions are now committed as boundary-level regression tests in `test_commit_reconciliation.py` and `test_story_validator_descriptor_boundary.py`. Each failed review is preserved in its numbered cycle archive; canonical reports are regenerated only by the next independent reviewers.

G3 cycle 2 closed H-01/H-02/H-03 but Security opened H-04. Cycle 3 confirmed that the first H-04 patch still allowed a failed pre-publication Active compensation or failed tmux liveness query to recreate a false inactive fact (H-04R/H-05). Those exact cases are now regressions: direct enable and launch double-prepublication faults terminate the owning session; recovery, authorization-denial, termination-failure, post-publication, legacy-adapter, active/inactive, timeout, nonzero, malformed-output, and transcript-status propagation controls are covered. The focused application/adapter/reconciliation lane reports 145 passing tests.

G3 cycle 4 closed H-04R/H-05 but found H-06 before the compensation branch: the first authoritative recovery read could itself fail and return before capture was stopped. Direct and launch tests now inject that first-recovery failure and prove stable `STATE_IO`, durable non-Active state only with capture stopped, and verified owning-session absence. A separate failed-transcript commit/recovery control proves the provider is preserved when capture was already verified stopped. The final focused lane reports 149 passing tests.

The initial pytest-8 clean environment was not accepted after its audit reproduced CVE-2025-71176. The plan, package contract, and test assertion were reconciled to `pytest>=9.0.3,<10`, the environment was rebuilt on pytest 9.1.1, and the final full suite and clean dependency scan were rerun.

## Implementation Risks

- No real provider model turn or credential login was attempted; provider auth remains native-CLI behavior and credential files were not inspected.
- No manual interactive curses usability session was recorded in G2; behavior and rendering contracts are covered by fake-window tests and the user already exercised the installed launch path.
- `/proc/self/fd` is required by the fail-closed validator execution design and is documented as an operational requirement.
- The compiled KG contract is now product-owned and passes G7 reconciliation. The adopted CI uses mutable major action tags and unpinned Python packages; DevOps records this as a non-blocking release-hardening recommendation.

## Validation Evidence

- `test-plan.md`
- `test-execution-report.md`
- `coverage-report.md`
- `deployability-check.md`
- `artifacts/test-results/junit.xml`
- `artifacts/test-results/coverage.xml`
- `artifacts/security/dependency-audit.json`
- `artifacts/security/secrets-scan.json`
- `artifacts/security/bandit-sast.json`

Artifact integrity: JUnit SHA-256 `df160ca44d33a73feef73e9dc62c44cfc50898bd1bab3ece6abe0cc4320679a6`; coverage SHA-256 `aa55e2cdb15495bb1c573703922a20cf13e716fb141c3dd53f669bafe9bc906f`.

## Result

PASS — H-01/H-02/H-03/H-04/H-04R/H-05/H-06 implementation and final QE evidence are complete; final Code, Security, and G7-added DevOps evidence pass with non-blocking recommendations for Product Manager disposition.

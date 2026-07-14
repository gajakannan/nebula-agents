# Code Review Report — F0001 run 2026-07-14-b885d64c, G3 cycle 5

## Summary

- Reviewer: Code Reviewer, independent of the H06 implementation and final G2 refresh.
- Assessment: `PASS WITH RECOMMENDATIONS`.
- Open findings: Critical 0; High 0; Medium 1; Low 1.
- Release-blocking findings: none.
- Archived cycle reports remain immutable: cycle 1 SHA-256 `58060c7d1d00ceee2acf787ed54f58c376d6b22b835c51cf4515bbc75f856dd5`, cycle 2 `8d415b4567460783e35ea20a79097a862eb6f1ad755b30db63cd221502a38aa6`, cycle 3 `916bb455e41e5f65b2940e6f43cd8136c2b2b86f10d49df58b3db4c1e21898e2`, and cycle 4 `db48c21678d88ac0e0ad1442051f599fa5d0798a14210131e8199dba751695d6`.

H06 is closed. When an original `TranscriptEnabled` commit fails before publication and the first authoritative recovery is unavailable, both direct enable and launch-with-transcript now terminate the immutable owning session, verify its absence, and return stable operation-specific `STATE_IO`; they do not leave a durable inactive transcript fact while capture remains active. A termination/probe failure remains a distinct unresolved operation and is never reported as successful. The already-stopped `TranscriptFailed` path preserves the provider session, and postpublication ambiguity continues to recover the published `Active` fact without destructive compensation.

## Reviewed Scope

The review covered the canonical 156-path inventory in `artifacts/diffs/changed-files.txt` (SHA-256 `249c918658dabe44534f012c25c6a71f140899b7f58c043c626e6dd0e3885312`), with detailed inspection of:

- `engine/src/nebula_agents/application/runs.py`, `application/transcripts.py`, and the associated ports and authorization boundaries.
- `engine/src/nebula_agents/infrastructure/tmux.py` and the transcript adapter.
- H01–H06 commit ambiguity, compensation, liveness, session-ownership, authorization, recovery, and R1–R10 regressions.
- The 514-test JUnit and Cobertura packages, raw dependency/secrets/Bandit results, deployability evidence, and final G2 self-review.
- `ADR-004-f0001-transcript-redaction.md`, `f0001-workflows.md`, the feature assembly plan, S0005, and `security/data-protection.md` (combined sorted path-bound SHA-256 `cc700fcc72a9fcd72b507cd9fcaec44fc1ccbc8a079cd0a13521de7391f52673`).

The frozen Python source/test snapshot plus `engine/pyproject.toml` and the story validator has sorted path-bound SHA-256 `a2ab63a7b342688f4b90bc9d028d566bf2aa0be0b72598180fa6c1a23725dc50`.

## Validation Evidence

- Official JUnit: 514 tests, 514 passed, zero failures/errors/skips; 76,548 bytes; SHA-256 `df160ca44d33a73feef73e9dc62c44cfc50898bd1bab3ece6abe0cc4320679a6`.
- Official Cobertura: 4,189/4,620 lines (90.67%) and 1,197/1,472 branches (81.32%); 212,114 bytes; SHA-256 `aa55e2cdb15495bb1c573703922a20cf13e716fb141c3dd53f669bafe9bc906f`.
- Mandatory risk modules remain 100%: authorization 42/42, transitions 24/24, redaction 26/26, and session entry 60/60.
- Independent compound reconciliation lane: 23 passed in 0.54 seconds.
- Independent tmux/transcript/authorization/application selection: 94 passed, 61 deselected, in 0.61 seconds.
- Independent full non-host suite: 513 passed in 2.29 seconds.
- Independent real-tmux lifecycle: 1 passed in 0.48 seconds.
- Independent 14-case reviewer probe: 14 passed in 0.20 seconds, covering direct and launch H06 paths, termination failure, already-stopped failure preservation, postpublication ambiguity, and strict tmux probe semantics.
- Dependency scan: 11 dependencies, zero vulnerabilities; SHA-256 `8498dee8525ab7f7ca2090e1d7c8ad027e203d89955a29f70178a68377f856f6`.
- Secrets scan: zero findings; SHA-256 `9fc0dbecfaca2a617631238ceef05847066b9ac694a24b4a304fb6d8704dd192`.
- Bandit: 13 Low and zero Medium/High findings across 7,199 lines; SHA-256 `7a39591751de590b4618d09939c9cfe5488c954d55a93500f124dcedbbce1f94`. The DAST waiver remains valid because this feature exposes no local HTTP/network target.
- Code-quality checks: zero TODO/FIXME markers, no oversized source file, 185 advisory long lines, tracker validator PASS with zero errors/warnings, and `git diff --check` PASS.

## H06 and Prior High-Risk Controls

| Control | Result | Independent confirmation |
|---|---|---|
| Direct original `TranscriptEnabled` prepublication fault plus unavailable first recovery | PASS | Stable `STATE_IO` operation `transcript-enable-commit-recovery`; durable transcript remained `Disabled`, capture was inactive, and the immutable owning session was absent. |
| Launch original `TranscriptEnabled` prepublication fault plus unavailable first recovery | PASS | Stable `STATE_IO` operation `launch-transcript-enable-commit-recovery`; durable transcript remained `Disabled`, pipe was inactive, and the provider session was absent. |
| Direct termination or absence-verification failure | PASS fail-closed | Stable operation `transcript-enable-commit-recovery-session-termination`; capture/session may remain live, but no false termination or successful transcript transition is reported. |
| Launch termination or absence-verification failure | PASS fail-closed | Stable operation `launch-transcript-enable-commit-recovery-session-termination`; no false success is returned. |
| `TranscriptFailed` first recovery unavailable after verified pipe stop | PASS | Stable `launch-transcript-failure-commit-recovery`; durable state is `Disabled`, pipe remains inactive, and the provider session is preserved without a kill. |
| Direct and launch postpublication `TranscriptEnabled` ambiguity | PASS | Authoritative recovery observes durable `Active`; capture and provider session remain live, with no destructive termination. |
| Strict `pipe_active` values | PASS | Only successful exact `1` and `0` outputs map to active/inactive. Timeout, nonzero exit, and malformed output raise stable `COMMAND_FAILED`. |
| Strict `has_session` values | PASS | Documented presence/absence statuses remain distinct; timeout and unexpected exit raise stable `COMMAND_FAILED`. |
| Lock-time authorization and immutable ownership | PASS | Caller authorization is rechecked where required; safety compensation targets only the immutable owning session and does not grant a new public capability. |
| H01–H05 regressions | PASS | Launch compensation, descriptor-bound validation, completion ambiguity, conservative `Active` compensation, capture-status propagation, and termination fallback remain green. |

## Severity-Ranked Findings and Recommendations

No Critical or High defect was found in the reviewed implementation, tests, or architecture.

### Medium — CR-GOV-01: reviewed implementation is not reproducible from the current commit

- Pattern: evidence and publication governance.
- Evidence: `HEAD`, `main`, and `origin/main` all resolve to `eadc990b3fbf77364368297196db32dde8d75438`; the reviewed F0001 implementation and evidence remain uncommitted/untracked workspace content.
- Impact: the final G7/PR diff cannot yet be reproduced from an immutable commit even though the reviewed workspace snapshot is internally consistent.
- Recommendation: intentionally commit the approved scope, regenerate or verify the canonical manifest against that immutable commit, and confirm the final diff before G7 publication.
- Owner/follow-up: Feature Orchestrator; before G7/PR publication. Non-blocking for the implementation review, blocking only for publication readiness.

### Low — CR-TOOL-01: backend lint enforcement is not configured

- Pattern: static-analysis completeness.
- Evidence: the lint wrapper passes but explicitly skips Python backend lint because no backend linter is configured; the direct quality checks remain clean apart from 185 advisory long lines.
- Impact: style and selected static defects rely on review/tests instead of an enforced backend lint gate.
- Recommendation: configure a Python backend linter or document the intentional absence and accepted compensating controls.
- Owner/follow-up: Backend Engineer; deferred, no release follow-up required.

## R1–R10 and Acceptance Criteria

| Requirement | Result | Disposition |
|---|---|---|
| R1 | PASS | Doctor path and absolute-path contracts remain green. |
| R2 | PASS | H01 launch compensation, failed/exited attach behavior, and session lifecycle remain closed. |
| R3 | PASS | Last-valid evidence reconciliation remains green. |
| R4 | PASS | H02 descriptor-bound validator behavior remains closed. |
| R5 | PASS | H03–H06 transcript publication, truthful recovery, redaction-before-write, and verified termination controls are closed. |
| R6 | PASS | Corrupt-state recovery and authorization controls remain green. |
| R7 | PASS | Official branch-enabled coverage and all mandatory risk-module gates pass. |
| R8 | PASS | pytest 9.1.1 satisfies the audited `>=9.0.3,<10` contract. |
| R9 | PASS | Explicit option → environment → cwd product-root precedence remains green. |
| R10 | PASS | Exact `tui --run-id` and `nebula-agents attach --run-id` recovery guidance is implemented and reconciled. |

All six stories satisfy their acceptance criteria. In particular, S0005 now has independent confirmation for happy-path capture, redact-before-write, bounded preview, restart recovery, ordinary failure isolation, prepublication ambiguity, failed first recovery, conservative compensation, and strict liveness/termination behavior.

## Architecture, Quality, and Test Assessment

- Correctness and error handling: ambiguity paths establish authoritative durable truth or fail closed with operation-specific errors. The code never interprets an unavailable liveness proof as inactivity and never claims successful termination without verified absence.
- Boundaries and SOLID: application services depend on narrow ports; tmux and transcript details remain infrastructure concerns; domain code does not import infrastructure. Session termination is an internal safety compensation, not a new user-facing authorization path.
- Security and authorization: capture truth, redaction-before-write, immutable session ownership, and audited authorization denial remain consistent with ADR-004 and the security documentation. Raw scans have no blocking result.
- Tests: the 514-test package and independent focused probes exercise success, prepublication, postpublication, recovery-unavailable, termination-failure, probe-failure, and already-stopped failure branches. Coverage exceeds the 90% line gate and mandatory risk modules are fully covered.
- Performance and complexity: reconciliation is bounded, uses no new unbounded polling or external service, and introduces no material performance concern. The shared termination result/helper is proportionate to the privacy invariant.
- Readability and maintainability: operation names distinguish the failed phase, comments explain the non-obvious fail-safe, and no duplicate public state machine was introduced.
- Tracker and architecture governance: stories and assembly R1–R10 validate cleanly; final documentation consistently describes the implemented termination fallback. The repository has no compiled KG/symbol/hotspot toolchain, so graph, bus-factor, and graph-risk gates remain not applicable and no graph evidence is inferred.

## Recommendation

`PASS WITH RECOMMENDATIONS`

G3 Code Review has no implementation blocker. H01–H06 are closed, the requested H06 adversarial probes pass, and the final source/docs/evidence package is internally consistent. Complete CR-GOV-01 before G7/PR publication; CR-TOOL-01 may be handled as deferred engineering hygiene.

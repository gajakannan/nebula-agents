# Code Review Report — F0001 run 2026-07-14-b885d64c, G3 cycle 4 (archived)

## Summary

- Reviewer: Code Reviewer, independent of the H04R/H05 implementation and QE refresh.
- Assessment: `REQUEST CHANGES`.
- Open findings: Critical 0; High 1; Medium 0; Low 0.
- Prior reports `code-review-report-cycle-1.md`, `code-review-report-cycle-2.md`, and `code-review-report-cycle-3.md` remain immutable.

The cycle-4 remediation closes the two cycle-3 findings for the tested double-prepublication and tmux-probe paths. One adjacent first-recovery path still violates the same truthful transcript-state invariant and blocks G3.

## Reviewed Scope

The review covered the canonical 152-path inventory in `artifacts/diffs/changed-files.txt` (SHA-256 `8245ce5896827bb9fc84559d8d9752ec8b075372211dd650e7626c645376ec1b`), with detailed inspection of:

- `engine/src/nebula_agents/application/ports.py`, `application/runs.py`, and `application/transcripts.py`.
- `engine/src/nebula_agents/infrastructure/tmux.py` and `infrastructure/transcript.py`.
- Compound reconciliation, tmux adapter, transcript adapter, authorization, recovery, and full R1–R10 regression tests.
- Final G2 JUnit, Cobertura, test, coverage, deployability, and scan evidence.
- Final termination-fallback documentation in `ADR-004-f0001-transcript-redaction.md`, `f0001-workflows.md`, the assembly plan R5/Step 5, S0005, and `security/data-protection.md`.

The final documentation consistently limits session termination to the case where capture cannot be proved inactive and truthful durable `Active` compensation cannot be established. That is an appropriate privacy fail-safe and remains inside the approved local modular architecture.

## Validation Evidence

- Official JUnit: 510 tests, 510 passed, zero failures/errors/skips; 75,917 bytes; SHA-256 `8ee029b04675b6893c71db889282299228fb94a16fa850dc992d08ded386fc5c`.
- Official Cobertura: 4,176/4,607 lines (90.64%) and 1,191/1,464 branches (81.35%); 211,420 bytes; SHA-256 `8c74fc257fa1c14de0975f5f55cd4c1f7fed7dde0dafd62a427daf107dac02b7`.
- Mandatory branches remain 100%: authorization 42/42, transitions 24/24, redaction 26/26, and session entry 60/60.
- Independent compound reconciliation lane: 19 passed in 0.43 seconds, preserving the H-01/H-02/H-03 publication and compensation regressions.
- Independent tmux/transcript adapter lanes: 29 passed in 0.55 seconds.
- Independent authorization/recovery/transcript selection: 61 passed in 0.11 seconds.
- Independent full non-host suite: 509 passed in 2.24 seconds. The official host-runtime package separately records the real-tmux lifecycle passing in 0.48 seconds.
- Independent 14-case `/tmp` reviewer probe: all assertions completed in 0.20 seconds. Thirteen assertions confirmed the intended direct/launch termination, authorization/recovery controls, strict liveness contract, and capture-status propagation; the fourteenth reproduced the blocking first-recovery outcome below for both direct enable and launch-with-transcript.
- Code-quality scan: zero TODO/FIXME and no oversized source file; 185 long-line advisories. The lint wrapper passed while explicitly skipping an unconfigured backend linter.
- Final raw scans remain clean for dependencies and secrets; Bandit reports 13 Low and zero Medium/High for independent Security disposition.

## Closed Cycle-3 Controls

| Control | Result | Independent confirmation |
|---|---|---|
| Direct double-prepublication original plus compensating-Active failure | PASS | Durable transcript remained `Disabled`, capture stopped, and the immutable owning session was verified absent before `STATE_IO`. |
| Launch-with-transcript double-prepublication failure | PASS | Provider session was killed exactly once, verified absent, pipe inactive, and no false `Active` event was fabricated. |
| Lock-time fallback authorization denial | PASS | The denial remained audited; internal safety termination still stopped capture and verified session absence without granting a new user capability. |
| Second compensation recovery unavailable | PASS | Session termination and absence verification completed before the unresolved recovery error returned. |
| Termination cannot be verified | PASS fail-closed | The application retained a stable unresolved `STATE_IO` operation and did not claim successful termination. |
| `pipe_active` exact active/inactive values | PASS | Only exit 0 plus exact `1`/`0` maps to `True`/`False`. |
| `pipe_active` timeout/nonzero/malformed | PASS | All raise stable `COMMAND_FAILED`; unavailable proof is never inactive. |
| `has_session` timeout/unexpected exit | PASS | Timeout and nonstandard exit raise stable `COMMAND_FAILED`; documented presence/absence values remain distinct. |
| `capture_status` probe propagation | PASS | Pipe-probe failure propagates and cannot be converted into a terminal transcript fact. |
| H-01/H-02/H-03 | PASS | Authoritative launch/completion recovery and descriptor-bound validation remain covered and unchanged. |

## Severity-Ranked Finding

### High — CR-H04R-01: failure of the first authoritative recovery bypasses every capture compensation

- Location: `engine/src/nebula_agents/application/transcripts.py:59-62, 177-196`; analogous launch path at `engine/src/nebula_agents/application/runs.py:596-625`.
- What: after the original `TranscriptEnabled` commit errors, both callers first invoke `authoritative_after_commit_error`. If that first recovery is unavailable, direct enable immediately raises `unresolved_commit_outcome`, while launch propagates the recovery exception. Neither path attempts pipe disable, conservative `Active` publication, nor verified owning-session termination.
- Independent direct reproduction: the original `TranscriptEnabled` commit failed before publication and the first `recover()` call failed. The result was durable transcript `Disabled`, pipe active, owning session present, and `STATE_IO` returned to the caller.
- Independent launch reproduction: the same first-recovery fault left durable transcript `Disabled`, the provider tmux session present, and the capture pipe active; the recovery exception escaped before the new fallback ran.
- Impact: registry, UI, and audit consumers can still report capture inactive while terminal collection continues. This is the exact confidentiality/consent and truthful-state failure H-04/H04R is required to eliminate. The fact that durable commit outcome is unknown makes verified session termination more—not less—necessary: terminating is safe whether the hidden commit published `Active` or remained `Disabled`.
- Remediation: when the first authoritative read cannot be established after a possibly configured pipe, terminate the immutable owning session through the transcript port and positively verify absence before returning a stable unresolved error. Apply the same bounded helper in direct enable and launch-with-transcript. Add exact first-recovery-unavailable tests for both paths, including termination/probe failure variants.
- Owner/follow-up: Backend Engineer + Architect + Security Reviewer; `F0001-G3-CR-H04R-01`.

## R1–R10 and Acceptance Criteria

| Requirement | Result | Disposition |
|---|---|---|
| R1 | PASS | Doctor path/absolute-path contracts remain green. |
| R2 | PASS | H-01 launch compensation and failed/exited attach behavior remain closed. |
| R3 | PASS | Last-valid evidence reconciliation remains green. |
| R4 | PASS | H-02 descriptor-bound validators remain closed. |
| R5 | **FAIL** | H-03 remains closed, but CR-H04R-01 violates crash-consistent and truthful transcript recovery. |
| R6 | PASS | Corrupt-state recovery and authorization controls remain green. |
| R7 | PASS | Official branch-enabled coverage and all risk-module gates pass. |
| R8 | PASS | pytest 9.1.1 satisfies the audited `>=9.0.3,<10` contract. |
| R9 | PASS | Explicit option → environment → cwd product-root precedence remains green. |
| R10 | PASS | Exact `tui --run-id` and `nebula-agents attach --run-id` guidance is implemented and final evidence prose is reconciled. |

S0001, S0002, S0003, S0004, and S0006 remain complete. S0005 is blocked only at the compound first-recovery failure above; happy-path transcript capture, redact-before-write, bounded preview, attach/recovery guidance, restart recovery, and ordinary failure isolation remain covered.

## Architecture, Quality, and Test Assessment

- Clean Architecture direction is preserved: application services depend on narrow ports; tmux and transcript implementations remain infrastructure adapters; domain imports no infrastructure.
- Session termination is correctly modeled as internal compensation after an already-authorized operation, not as a new caller permission. Immutable run/session identity bounds its target.
- Event sequencing remains append-only and contiguous whenever persistence is available; fallback authorization denial is auditable.
- The new termination abstraction is proportionate and readable. It avoids adding a public workflow state and carries rationale comments for the non-obvious privacy fallback.
- Error handling is complete for the tested second-recovery and liveness branches but incomplete at the first authoritative recovery boundary.
- Tests are deterministic and behavior-focused, but the missing first-recovery tests are material because that branch bypasses all newly added safety controls.
- No new performance issue, unbounded operation, layer leak, duplicate abstraction, or UI behavior regression was found.
- The repository still has no compiled KG/symbol/risk toolchain; graph, hotspot, bus-factor, and graph-risk gates remain not applicable and no graph evidence is inferred.

## Recommendation

`REQUEST CHANGES`

CR-H04R-01 is a High release blocker. Remediate both direct and launch first-recovery branches, add the exact regressions, refresh affected G2 evidence, and request another independent G3 Code Review impact confirmation.

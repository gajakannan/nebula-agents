# Code Review Report — F0001-tmux-native-agent-cockpit run 2026-07-14-b885d64c, H-04 impact confirmation (archived cycle 3)

> Fresh independent reassessment after the H-04 remediation. The reviewer did not implement the remediation. Immutable cycle-1 and cycle-2 reports remain preserved as `code-review-report-cycle-1.md` and `code-review-report-cycle-2.md`.

## Reviewed Files and Frozen Scope

The review covered the final 152-path inventory in `artifacts/diffs/changed-files.txt`, with detailed inspection of:

- `engine/src/nebula_agents/application/ports.py`, `application/runs.py`, and `application/transcripts.py`.
- `engine/src/nebula_agents/infrastructure/transcript.py` and `infrastructure/tmux.py`.
- `engine/tests/integration/test_commit_reconciliation.py`, transcript/tmux adapter tests, authorization tests, and the unchanged R1–R10 regression surface.
- The F0001 assembly plan and story contracts, Security cycle-2 H-04 report, final JUnit/Cobertura/scans, evidence manifest, and G2 prose.

Frozen SHA-256 values:

- Source/test snapshot (`engine/src/**/*.py`, `engine/tests/**/*.py`, `engine/pyproject.toml`, and `agents/product-manager/scripts/validate-stories.py`, sorted path-bound hashes): `d16b0b14d56e680ba7799cadd884a005c440cd737dce12e84e14447dac58f6ab`.
- Canonical changed-file inventory: `8245ce5896827bb9fc84559d8d9752ec8b075372211dd650e7626c645376ec1b`.
- Preserved cycle-1 report: `58060c7d1d00ceee2acf787ed54f58c376d6b22b835c51cf4515bbc75f856dd5`.
- Preserved cycle-2 report: `8d415b4567460783e35ea20a79097a862eb6f1ad755b30db63cd221502a38aa6`.

`HEAD`, `main`, and `origin/main` remain `eadc990b3fbf77364368297196db32dde8d75438`; the implementation is still an uncommitted/untracked worktree, so the frozen hashes—not the Git head—define the reviewed source. The repository has no product KG/toolchain, so graph, hotspot, bus-factor, and graph-risk gates are not applicable.

## Validation Artifacts

- Official JUnit: 496 tests, 496 passed, zero failures/errors/skips; 73,899 bytes; SHA-256 `fc99c11dcf9a8e6af089050e9d9ff1a4761bf8cc8431203e282ffb494eb2c3f4`. Direct XML inspection confirms all 14 compound reconciliation cases are present.
- Official Cobertura: 4,126/4,572 lines (90.24%) and 1,180/1,454 branches (81.16%); 209,925 bytes; SHA-256 `c23f2747d9fd23fd7631ad3b758e5725089f9abfd00e46c39620c2533d66b99e`.
- Exact compound reconciliation lane: 14 passed in 0.35 seconds.
- Independent broad run inside the filesystem sandbox: all 495 non-host cases passed; the real-tmux case was blocked by sandbox access to `/tmp/tmux-1000/default`, not by an application assertion. The same focused real-tmux lane passed outside that sandbox in 0.49 seconds and cleaned up its session.
- Two bounded reviewer probes reproduced the blockers below in 0.08 seconds. These were independent `/tmp` probes and were not added to the product suite.
- Raw dependency audit: 11 resolved dependencies and zero vulnerabilities; SHA-256 `8498dee8525ab7f7ca2090e1d7c8ad027e203d89955a29f70178a68377f856f6`.
- Raw secret scan: zero results; SHA-256 `d71aba4912403c83f9180f4aea6fc9d0bf7a042eba924bbe8048a9d1c2af42ad`.
- Raw Bandit: 13 Low, zero Medium/High across 7,093 LOC; SHA-256 `301150a19ec88ad4edd8614583548d4a9c0a2b91443cdca541af0b8fe493b8af`.

## H-04 Requirements and Impact

Security cycle 2 required callers to stop suppressing failed disable compensation, verify pipe liveness, persist a truthful `Active`/explicit unresolved-compensation fact when capture cannot be stopped, or terminate the owning tmux session. It also required exact coverage across direct enable, launch-with-transcript, observed failure, and compensation ambiguity.

The remediation materially improves the design:

- `TranscriptPipePort.is_active` and the tmux `#{pane_pipe}` query introduce an explicit liveness seam.
- `stop_and_verify_capture` requires disable and probe success before a terminal transition.
- Direct enable, partial configure, launch-with-transcript, observed failure, and owner reconciliation retain `Active` when stop compensation is unverified.
- `persist_truthful_capture_active` publishes a compensating `TranscriptEnabled` event with `disable-unverified`, `possibly-active`, and operation context.
- Post-publication ambiguity for that compensating event recovers correctly, and event sequencing in the checked-in compound tests is contiguous.

Those changes close the original single-compensation reproduction, but they do not close H-04 at the final fail-safe boundary.

## Severity-Ranked Findings

Open findings: Critical 0; High 2; Medium 0; Low 1.

### High — CR-H04-01: pre-publication failure of the compensating Active commit restores the false Disabled/live-pipe state

- Location: `engine/src/nebula_agents/application/runs.py:201-256`; callers at `engine/src/nebula_agents/application/transcripts.py:76-93, 134-194` and `engine/src/nebula_agents/application/runs.py:518-569`.
- What: `persist_truthful_capture_active` retries the truth-preserving state as a normal authorized `TranscriptEnabled` commit. If that commit fails before publication, recovery still returns non-Active and the helper raises `STATE_IO`; it does not terminate the owning tmux session or otherwise make the durable fact truthful.
- Independent reproduction: the original `TranscriptEnabled` commit failed before publication, pipe disable failed, and the compensating `TranscriptEnabled` commit also failed before publication. The caller received `STATE_IO`, but recovery returned transcript `Disabled`, the pipe remained active, and the event sequence contained only `LaunchRequested`, `RunLaunched`.
- Impact: status/UI/audit still claim capture is inactive while collection can continue. This is the exact confidentiality/consent and audit-integrity outcome H-04 was intended to eliminate. A persistent local state-store fault or lock-time compensation denial makes the scenario reachable; returning an unresolved error does not correct later read projections.
- Required fix: if compensating Active publication cannot be proven durable, terminate and verify absence of the owning tmux session, or durably represent unresolved/live capture through a fail-safe repository path that does not depend on a newly granted user mutation. Add pre- and post-publication tests for the compensating commit itself.
- Owner/follow-up: Backend Engineer + Architect + Security Reviewer; `F0001-G3-CR-H04-01`.

### High — CR-H04-02: tmux liveness query failure is classified as proved inactive

- Location: `engine/src/nebula_agents/infrastructure/tmux.py:98-107`; consumed by `engine/src/nebula_agents/infrastructure/transcript.py:280-282` and `engine/src/nebula_agents/application/runs.py:183-198`.
- What: `TmuxAdapter.pipe_active` returns `False` for every nonzero or timed-out `tmux display-message` result. `stop_and_verify_capture` therefore cannot distinguish an authoritative `#{pane_pipe}=0` response from a failed liveness query.
- Independent reproduction: a bounded runner returned exit 124 with `timed_out=True`; `pipe_active()` returned `False` rather than raising or returning unknown.
- Impact: after a nominal disable call, an unavailable/control-path-failed liveness query satisfies `verified_stopped` and permits `Completed`/`Failed` publication without proof that capture is inactive. This invalidates the security-critical proof boundary added for H-04.
- Required fix: return inactive only for exit 0 plus exact `#{pane_pipe}=0`; raise a stable error (or return an explicit unknown state) on timeout, nonzero exit, malformed output, or truncation. Cover exit 0 values `0`/`1`, timeout, nonzero, and malformed output through the real adapter and application compensation path.
- Owner/follow-up: Backend Engineer + Security Reviewer; `F0001-G3-CR-H04-02`.

### Low — CR-EVID-01: exact post-launch command prose remains partially stale

- `README.md` and the canonical counts are refreshed to 496, so the former count mismatch is fixed; historical 476/488 gate entries correctly remain as chronology.
- `test-execution-report.md:38` still describes the tested next step as tmux `attach-session` guidance, and `g2-self-review.md:22` says “tmux attach next steps.” R10 requires and the implementation prints exact `nebula-agents attach --run-id ...` guidance.
- Fix the two narrative lines during the next evidence refresh. This is non-blocking relative to the two High code findings.

## Non-Blocking Recommendations

- [medium] Commit the reviewed implementation and regenerate the manifest/diff against an immutable head before G7/PR publication — owner: Feature Orchestrator; follow-up: before-G7-publication.
- [low] Configure a Python backend linter or document its intentional absence; the current wrapper can pass while skipping that lane — owner: Backend Engineer; follow-up: deferred-no-followup.

## R1–R10 Regression Matrix

| Requirement | Result | Independent disposition |
|---|---|---|
| R1 | PASS | Doctor/path contracts remain covered in the broad run. |
| R2 | PASS | H-01 launch reconciliation remains green in the exact compound lane; failed/exited attach behavior regressed neither in source nor tests. |
| R3 | PASS | Evidence reconciliation and last-valid projection tests remain green. |
| R4 | PASS | H-02 descriptor-bound validator tests remain green; no changed H-04 code touches that boundary. |
| R5 | **FAIL** | H-03 remains closed, but H-04 still violates transcript crash-consistency and truthful-state requirements through CR-H04-01/02. |
| R6 | PASS | Corrupt-state recovery and authorization projection tests remain green. |
| R7 | PASS | Official branch-enabled coverage exceeds 85%; all four mandated risk modules remain 100% branch covered. |
| R8 | PASS | pytest remains 9.1.1 under the `>=9.0.3,<10` contract; dependency audit is clean. |
| R9 | PASS | Product-root precedence tests remain green. |
| R10 | PASS implementation / prose fix | Exact CLI guidance behavior remains covered; two evidence descriptions need the Low wording correction above. |

H-01/R2, H-02/R4, and H-03 remain closed. No regression was found in authorization policy: the broad run exercised deny-by-default bindings, ownership, explicit reviewer grants, lock-time reauthorization, foreign-owner projection minimization, and session-entry authorization boundaries. The new H-04 compensation event remains authorized and contiguous when it can publish; CR-H04-01 concerns failure of that safety publication itself.

## Pattern and Architecture Compliance

- Clean Architecture direction remains intact: application code consumes repository/tmux/transcript ports, while concrete tmux liveness stays in infrastructure.
- External effects remain bounded and use typed argv with `shell=False` outside the documented tmux command seam.
- The conservative Active concept is appropriate and avoids overengineering a new public workflow state.
- The fail-safe is incomplete because its final truth publication depends on the same fallible commit boundary and the liveness adapter collapses unknown into false. These are correctness defects, not style preferences.
- Focused docstrings/comments explain the compensation intent; readability is adequate and no new performance hotspot was found.

## Vertical-Slice Completeness

All six stories remain wired across domain, application, adapters, schemas, CLI/TUI, and tests. H-04 reaches every intended application caller, but its infrastructure and persistence failure endpoints are incomplete: the application can neither prove pipe inactivity after a failed query nor guarantee truthful durable state when compensating Active publication fails. The slice is therefore not releasable.

## AC / Test Adequacy

The official 496-case suite and 14-case compound lane are broad and deterministic, and they preserve H-01–H-03 plus R1–R10 coverage. The H-04 lane tests post-publication ambiguity of the compensating Active event, but not pre-publication failure of that event. Adapter tests cover `True`/`False` liveness values from a fake tmux object, but not timeout/nonzero/malformed real-adapter results. Those two omitted cases map exactly to the two reproduced High findings.

## Coverage Verification

Manifest, JUnit, Cobertura, `coverage-report.md`, and `test-execution-report.md` agree on 496 passing cases, 4,126/4,572 lines (90.24%), and 1,180/1,454 branches (81.16%). Authorization, transitions, redaction, and session entry remain at 100% branch coverage. Numeric coverage passes, but it does not cover the two missing failure semantics above and cannot override reproduced blockers.

## Result

`REQUEST CHANGES`

CR-H04-01 and CR-H04-02 are High release blockers. H-04 remains open; G3 Code Review cannot pass until both are remediated, added as regression tests, and independently retested.

# Code Review Report — F0001-tmux-native-agent-cockpit run 2026-07-14-b885d64c, G3 cycle 2

> Fresh independent reassessment after the cycle-1 remediation. The reviewer did not implement the fixes. The immutable first-pass report remains `code-review-report-cycle-1.md`.

## Reviewed Files and Frozen Scope

The review covered all 152 paths in the manifest's canonical `scm.diff_artifact`, `artifacts/diffs/changed-files.txt`, with detailed inspection of:

- `engine/src/nebula_agents/**`, especially authoritative commit reconciliation, launch/tmux compensation, transcript state/pipe compensation, filesystem publication/recovery, validator execution, and unchanged R1–R10 application/presentation paths.
- `agents/product-manager/scripts/validate-stories.py`, including its inherited descriptor traversal, stable byte reads, public CLI compatibility, and failure behavior.
- All `engine/tests/**`, with focused review of the new real-repository and real-subprocess boundary suites.
- `engine/pyproject.toml`, the F0001 PRD and six story contracts, the assembly-plan remediation addendum, solution patterns, CLI/workflow/data contracts, schemas, tracker/status artifacts, and current G0–G2 evidence.
- Raw JUnit, Cobertura, dependency-audit, secrets-scan, and Bandit artifacts for the refreshed run.
- The exact archived cycle-1 Code Reviewer and Security Reviewer reports and their H-01/R2, H-02/R4, and H-03/R5 reproductions.

The refreshed code/test snapshot was frozen before independent execution and rechecked after all probes. SHA-256 values:

- Source/test snapshot (`engine/src/**/*.py`, `engine/tests/**/*.py`, `engine/pyproject.toml`, and `agents/product-manager/scripts/validate-stories.py`, with sorted path-bound hashes): `d0e4b37ceaab895e9d89dcb4f4325ecb4513d67bad909b167e88d3c8aa96f23e`.
- Canonical changed-file inventory: `054d38de01633e9dd6a0272bb1db6e9505b513cd6f66c9f2ff1efbef43eac0ff`.
- Preserved cycle-1 Code Reviewer report: `58060c7d1d00ceee2acf787ed54f58c376d6b22b835c51cf4515bbc75f856dd5`.

`HEAD`, `main`, and `origin/main` remain `eadc990b3fbf77364368297196db32dde8d75438`, while the F0001 implementation is still an uncommitted/untracked worktree. The hashes above therefore define this review's exact source boundary; the named feature branch alone does not reproduce it. The repository has no product knowledge graph, symbol index, hotspot report, or `scripts/kg` toolchain, so KG, hotspot, bus-factor, and risk-score gates are not applicable and no graph evidence is inferred.

## Validation Artifacts

- Official JUnit: 488 cases, 488 passed, 0 failures, 0 errors, 0 skipped; 72,639 bytes; SHA-256 `0dfdb5a419b759ed9f77d78d810b7d68cd62ae126545d4888a154cb7b58b7369`. Direct XML inspection confirmed that the new before/after publication and real-subprocess replacement cases are present.
- Official Cobertura: 4,064/4,519 lines (89.93%) and 1,162/1,434 branches (81.03%); 207,495 bytes; SHA-256 `c85cffadbc74edb1cd09b16bc7f6861f7191e0b8772217ee2a52d1071306a07e`. Direct XML parsing matched the manifest and reports.
- Independent exact cycle-2 boundary files: 12 passed in 0.34 seconds.
- Independent full suite excluding only host tmux: 487 passed in 1.97 seconds.
- Independent focused real-tmux lifecycle: 1 passed in 0.49 seconds and cleaned up its unique test session.
- Independent original-shape H-01/H-03 post-publication probes used the production filesystem repository behind a wrapper that raised only after the targeted production commit returned. H-01 ended `Failed`, revision 2, tmux absent, with `LaunchRequested`, `RunLaunched`, `LaunchFailed`. H-03 ended `Completed`, revision 3, pipe inactive, one disable, and zero reconfigurations.
- Independent original-shape H-02 probe replaced the governed story with an outside-target symlink after the parent opened its descriptors and delegated to the real subprocess runner. The child exited 1, reported descriptor-bound validation failure, and did not accept the outside story.
- Installed `doctor` from `/tmp`, under a five-second hard timeout and `NEBULA_AGENTS_PRODUCT_ROOT`, returned ready and rendered the exact workspace, planning, runtime, prompt, tmux executable, and provider executable paths. It did not create the configured runtime directory.
- Coverage validation accepted 89.93% against the unwaived 85% floor. Code-quality scan passed with 0 TODO/FIXME and no oversized file; 189 long-line advisories remain. The lint wrapper passed while explicitly skipping an absent backend linter. Tracker validation and `git diff --check` passed.
- `pip check` passed. The refreshed dependency artifact contains 11 resolved dependencies, pytest 9.1.1, and zero vulnerabilities; the secrets artifact is empty; Bandit records 16 Low, 0 Medium, and 0 High findings for separate Security Reviewer disposition.
- The reconciled `pytest>=9.0.3,<10` requirement appears in `engine/pyproject.toml`, the assembly plan, and its contract test. This remains correct: NVD lists pytest through 9.0.2 as affected by CVE-2025-71176, and the official pytest 9.0.3 release records the fix ([NVD](https://nvd.nist.gov/vuln/detail/CVE-2025-71176), [pytest 9.0.3](https://github.com/pytest-dev/pytest/releases/tag/9.0.3)).

## Cycle-1 Critical-Finding Closure

| Finding | Cycle-2 disposition | Independent evidence |
|---|---|---|
| H-01 / R2 — launch post-publication compensation used a stale revision | **Closed** | `authoritative_after_commit_error` recovers against the event stream/state images (`engine/src/nebula_agents/application/runs.py:131-154`); launch reconciles before tmux compensation, terminalizes from the recovered revision, and reconciles an ambiguous terminal commit (`runs.py:338-393`). The exact real-repository before/after-fsync tests are at `engine/tests/integration/test_commit_reconciliation.py:240-309`. The independent original wrapper probe produced durable `Failed`, no tmux session, and an explicit compensating `LaunchFailed` after `RunLaunched`. |
| H-02 / R4 — descendant story content remained pathname mutable | **Closed** | The parent passes the inherited feature fd and keeps it open through the subprocess (`engine/src/nebula_agents/infrastructure/watcher.py:428-474`). The child walks with `dir_fd`, `O_NOFOLLOW`, bounded entry/depth/size limits, owner/mode/type checks, retained file descriptors, stable metadata fingerprints, and double-read byte equality (`agents/product-manager/scripts/validate-stories.py:44-104`, `:383-450`, `:486-550`). Real subprocess tests cover pre-existing symlink, post-parent-check swap, unsafe mode, FIFO, stable success, and public CLI compatibility (`engine/tests/integration/test_story_validator_descriptor_boundary.py:112-215`). The independent swap probe failed closed with exit 1. |
| H-03 / R5 — published `Completed` could restart capture from stale `Active` | **Closed** | Transcript compensation now recovers authoritative durable state and restores capture only when that state is `Active` (`engine/src/nebula_agents/application/transcripts.py:45-104`). Enable, failure, completed-sidecar, and compatibility completion branches share the protocol (`transcripts.py:106-282`); launch-time transcript enablement also consults authoritative state (`engine/src/nebula_agents/application/runs.py:409-442`). Real repository before/after tests are at `engine/tests/integration/test_commit_reconciliation.py:311-400`. The independent original wrapper probe kept durable `Completed` with the pipe disabled and no reconfiguration. |

No Critical or High finding remains from cycle 1, and no new Critical or High finding was identified.

## R1–R10 Regression Matrix

| Requirement | Result | Cycle-2 evidence |
|---|---|---|
| R1 doctor paths / absolute missing paths | PASS | Absolute missing paths remain in `application/preflight.py`; table/JSON formatter contracts pass; the bounded installed non-repository-cwd smoke printed the complete exact path block. |
| R2 fail-closed launch and attach | PASS | H-01 is closed as above. Failed/exited runs remain attach-disabled, attach re-probes exact tmux presence, and launch compensation records a terminal event from authoritative revision. |
| R3 last-valid complete evidence reconciliation | PASS | Public service and CLI continue through `reconcile_paths`; JSON/YAML/Markdown and full lifecycle/status/story path tests pass without overwriting last valid durable observations. The H-02 runner changes did not alter watcher reconciliation. |
| R4 descriptor-bound validators | PASS | H-02 is closed as above. Production stories use stable descriptor bytes; script/workspace/feature ancestry and no-follow checks remain; trackers/templates continue through the fixed allowlist. |
| R5 transcript crash consistency | PASS | H-03 is closed as above. Completed/failed sidecars, sanitized failure reasons, restart recovery, and pre-/post-publication enable/completion outcomes pass. |
| R6 corrupt-state recovery UX | PASS | Repository discovery, safe recovery projection, CLI `recover`, merged session listing, TUI selection/action, last gate/event, safe transcript path, and exact revision-bound command tests remain green. |
| R7 branch-enabled official coverage | PASS | Official XML has branch counters. Authorization 42/42, transitions 24/24, redaction 26/26, and session entry 60/60 branches are each 100%; no waiver applies. |
| R8 pytest CVE/toolchain | PASS | Metadata, plan, contract test, installed pytest 9.1.1, `pip check`, and the zero-vulnerability resolved audit agree on `pytest>=9.0.3,<10`. |
| R9 product-root precedence | PASS | Explicit invocation input → `NEBULA_AGENTS_PRODUCT_ROOT` → cwd remains implemented and covered for doctor/TUI/status/launch; bounded installed doctor smoke from `/tmp` passed. |
| R10 explicit post-launch interaction | PASS | Human launch output still prints exact `nebula-agents tui --run-id ...` and `nebula-agents attach --run-id ...` next steps; JSON omits presentation-only guidance; launch is called once and does not auto-attach. |

All other cycle-1 resolved findings remain closed: prompt binding, bounded subprocess capture, runtime override propagation, tmux pipe-disable argv, reachable transcript actions, last-valid dedupe, run-id recovery validation, fresh tmux projection, denial auditing, group ownership checks, policy symlink rejection, bounded state images, collision details, and reviewer projection filtering.

## Severity-Ranked Findings

No Critical, High, or Medium code-correctness finding was identified.

The recommendations below are non-blocking and do not weaken R1–R10 acceptance.

## Non-Blocking Recommendations With Owner/Follow-up

- [medium] Commit the reviewed implementation and regenerate the manifest/diff against an immutable head revision before G7/PR publication; the current branch name and `HEAD` do not reproduce the reviewed worktree even though this pass records a frozen source hash — owner: Feature Orchestrator; follow-up: before-G7-publication
- [low] Reconcile stale evidence prose before G4: `README.md:22` still says 476 tests while the manifest/JUnit/report say 488, and `test-execution-report.md:38` / `g2-self-review.md:22` say tmux-attach guidance although the approved and implemented next step is `nebula-agents attach --run-id ...` — owner: Quality Engineer + Architect; follow-up: before-G4-evidence-sync
- [low] Configure a Python backend linter or document its intentional absence in the repository quality contract; the current lint wrapper exits successfully after skipping the backend lane — owner: Backend Developer; follow-up: deferred-no-followup

## Pattern Compliance

- [x] Clean Architecture dependencies point inward; no new domain-to-infrastructure/presentation import was introduced.
- [x] Filesystem, subprocess, tmux, watcher, and transcript effects remain behind application ports/adapters.
- [x] SOLID responsibilities remain separated among services, repository, runner, and validator byte reader.
- [x] Atomic snapshot/event recovery and explicit workflow states follow `SOLUTION-PATTERNS.md`.
- [x] Non-obvious reconciliation and descriptor decisions carry rationale in focused docstrings/comments.
- [x] Error paths fail closed with stable domain errors or preserve the primary exception only after authoritative reconciliation.
- [x] Curses UI behavior remains keyboard driven, resize-safe, and text/symbol paired with color; the web-only `experience/` UX ruleset has no changed web surface to audit.
- [x] Bounded reads, entry counts, traversal depth, result lists, transcript preview, and subprocess output avoid unbounded hot-path work.

## Vertical-Slice Completeness

The six stories remain wired end to end across domain transitions and models, application authorization/use cases, filesystem/tmux/provider/watcher/transcript adapters, JSON contracts, CLI/TUI projections, and unit/contract/integration/security tests. The cycle-2 fixes specifically close the former gaps between durable lifecycle facts and external tmux/pipe effects, and between parent path checks and child-consumed story bytes. No partial layer, duplicate provider start, hidden automatic attach, network service, database, or managed-provider dependency was introduced.

## AC / Test Adequacy

The suite maps every story's happy path and stated edge cases to automated behavior, with manual installed smoke only where composition/path visibility adds value. The new tests exercise actual `FilesystemRunRepository` publication before and after `os.replace`/directory-`fsync`, actual subprocess fd inheritance, and actual post-check symlink replacement rather than only test doubles. Independent probes reused the original cycle-1 failure shapes and observed corrected external/durable outcomes. Tests are deterministic and bounded; the only host-specific lane is the isolated real-tmux lifecycle, which passed separately. No AC lacks implementation or traceable test proof in this pass.

## Architecture Compliance

The implementation complies with the approved local modular process, default-deny application authorization, append-only event timeline, versioned CLI/JSON boundary, owner-only atomic persistence, explicit workflow transitions, typed process argv, native tmux provider boundary, redact-before-write transcript design, bounded polling/evidence projection, and keyboard TUI contracts. The new recovery helper depends only on the application repository port, and the descriptor consumer remains a product validator invoked by the infrastructure runner rather than leaking infrastructure into the domain. No new runtime dependency or architecture scope was added.

## Coverage Verification

Raw XML, the manifest, `coverage-report.md`, and `test-execution-report.md` agree at 4,064/4,519 lines (89.93%) and 1,162/1,434 branches (81.03%). The independent coverage validator passed the 85% line threshold. Direct condition-counter summation confirmed the four mandatory modules at 42/42, 24/24, 26/26, and 60/60 branches. The new boundary tests are present in the official JUnit and contribute to the refreshed artifact rather than relying on narrative-only proof.

## Result

`PASS WITH RECOMMENDATIONS`

Cycle-2 G3 Code Review has no Critical or High blocker. H-01/R2, H-02/R4, and H-03/R5 are independently closed.

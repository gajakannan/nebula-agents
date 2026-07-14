# Code Review Report — F0001-tmux-native-agent-cockpit run 2026-07-13-1cfbc5a0

> Required per §10 for every completed terminal feature. Code Reviewer-owned.

## Reviewed Files

The canonical changed-file set is `scm.diff_artifact` at `artifacts/diffs/changed-files.txt`. The review covered that complete set, with detailed inspection of:

- `engine/src/nebula_agents/**` and `engine/tests/**`, including the application services, filesystem and policy persistence, provider/tmux/process adapters, watcher/validator runner, transcript worker and filter, CLI/TUI/session entry, formatters, and all unit, contract, integration, security, and real-tmux tests.
- `engine/pyproject.toml` for runtime, test, and dependency declarations.
- `planning-mds/features/F0001-tmux-native-agent-cockpit/**`, including the PRD, status, stories, and feature assembly plan.
- The F0001 architecture contracts, ADRs, schemas, authorization model, workflows, CLI contract, data model, and solution patterns listed in the changed-file artifact.
- The run evidence manifest and all referenced G0/G1/G2, test, coverage, deployability, security, lifecycle, command-audit, and raw test artifacts.

Review scope used the workspace diff from `base_revision: 06db42e1d354d88307839ff03a283d51f77cd95f` to `head_revision: worktree` recorded in `evidence-manifest.json`. The supplied diff artifact contains uncommitted workspace files and therefore does not establish a named Git branch or immutable head commit; this branch/worktree discrepancy is material to reproducibility and was treated as an explicit review limitation rather than silently inferred.

## Validation Artifacts

- Official `artifacts/test-results/junit.xml`: 424 tests, 424 passed, 0 failures, 0 errors, 0 skipped; SHA-256 `632209797c2ff935a528b5e22c6c2f566621c918aad27ffc5bf03d1539fd379c`.
- Independent non-real-tmux rerun: 423 passed in 1.12 seconds. The separately exercised real-tmux lifecycle test passed (1 test).
- Official raw coverage XML referenced by `coverage-report.md`: 3,973 valid lines, 3,577 covered lines, line rate 90.03%, but 0 valid branches; SHA-256 `482883b0e1b1808cc985d09c88cea31eafa181ff83a4e731c6d42d1ac5d32b73`.
- Independent `--cov-branch` rerun: 423 tests passed and 1,010/1,222 branches were covered (82.65%). Required risk-area results included authorization 37/42 (88.10%), gates 25/32 (78.12%), transitions 22/24 (91.67%), redaction 25/26 (96.15%), and session entry 52/60 (86.67%).
- `agents/code-reviewer/scripts/check-code-quality.py engine`: exit 0; 0 TODO/FIXME markers, no file over 500 KB, and 182 long-line warnings.
- Repository lint wrapper: exit 0, while reporting that no backend linter is configured.
- Planning tracker validation: exit 0 with no warnings.
- Manual failure-injection and boundary probes were used for doctor output/path reporting, authorization after provider exit, launch commit compensation, evidence parsing and persistence, validator-script symlinks, transcript commit/sidecar failures, corrupt-run recovery reachability, and streaming redaction edge cases.

## Severity-Ranked Findings

- [critical] The default `doctor` table in `engine/src/nebula_agents/presentation/formatters.py:248` reports only statuses/versions and omits the workspace, planning, runtime, prompt, tmux executable, and provider executable paths required by the contract; the human-readable repro contained none of them. In addition, `engine/src/nebula_agents/application/preflight.py:143` emits relative `missing_paths` even though path validation and operator remediation require absolute paths. This leaves the primary preflight surface unable to explain which concrete resources were checked or failed. — owner: Frontend Developer + Backend Developer; follow-up: deferred-no-followup
- [critical] Session lifecycle and launch persistence are not fail-closed. `engine/src/nebula_agents/application/authorization.py:136` can authorize attachment to a `Failed` run (`status=Failed can_attach=True`) after the provider is gone, and a forced `RunLaunched` commit failure in `engine/src/nebula_agents/application/runs.py:304` persisted `Failed` while leaving the tmux session alive. The latter attempted both `RunLaunched` and `LaunchFailed` events but did not compensate the external tmux side effect, violating attach-disabled terminal behavior and the one-provider/atomic-launch invariant. — owner: Backend Developer; follow-up: deferred-no-followup
- [critical] Evidence projection is inconsistent across public entry points and incomplete across required artifact types. Although watcher reconciliation now preserves the last valid projection, `RunService.observe_evidence` in `engine/src/nebula_agents/application/runs.py:499` still persists a malformed observation over it (`projected=Malformed Blocked`, `persisted=Malformed Blocked`). `engine/src/nebula_agents/infrastructure/watcher.py:46` only parses JSON, while invalid YAML and Markdown were reported `Available` with no parse-error category. The production watch set is limited to the current gate rather than all known lifecycle logs, status/story artifacts, and expected missing paths, and the CLI evidence flow does not consistently use reconciliation. — owner: Backend Developer; follow-up: deferred-no-followup
- [critical] Validator execution does not close the path-containment boundary. `engine/src/nebula_agents/infrastructure/watcher.py:268` and `:282` execute repository-relative validator scripts without descriptor-bound validation of the script path; a pre-existing symlink at the canonical validator location resolved outside the workspace and was passed to Python. Prompt reads now use a directory descriptor and no-follow behavior, and pre-existing feature/story/evidence symlinks are generally rejected, but feature/evidence validation remains pathname-based across validation and later use, leaving a TOCTOU seam for security-sensitive paths. — owner: Backend Developer + Architect; follow-up: deferred-no-followup
- [critical] Transcript completion and failure recovery are not crash-consistent. `TranscriptService.complete` in `engine/src/nebula_agents/application/transcripts.py:119` disables tmux piping before the terminal event commits; a forced `TranscriptCompleted` commit failure left the persisted transcript `Active` with piping disabled and no reconfiguration. `RunService.reconcile` at `engine/src/nebula_agents/application/runs.py:436` reconciles failed sidecars but ignores completed sidecars after a crash. A worker-output failure combined with sidecar-write failure exited 8 while leaving a durable `active` sidecar and no application observation, and the transcript projection has no durable failure reason. — owner: Backend Developer; follow-up: deferred-no-followup
- [critical] Corrupt-run recovery is unreachable through the supported operator surfaces. `engine/src/nebula_agents/infrastructure/filesystem_store.py:159` omits corrupt snapshots from listings, the TUI clears a missing initial selection at `engine/src/nebula_agents/presentation/tui.py:96`, and the CLI parser in `engine/src/nebula_agents/presentation/cli.py:67` exposes no recovery command. Consequently `RunService.recover` cannot be reached for the corrupt state it is intended to repair. The recovery view also omits the last audit event and an explicit sanitized recovery command. — owner: Frontend Developer + Backend Developer; follow-up: deferred-no-followup
- [high] Branch coverage does not meet the approved assembly-plan gate and the official artifact cannot substantiate branch coverage at all. The official XML records 0 valid branches, while an explicit branch rerun covered only 1,010/1,222 branches (82.65%); authorization, gates, transitions, redaction, and session-entry branches were all below 100%. The feature assembly plan requires 100% branch coverage for transition guards, authorization decisions, descriptor validation, streaming redaction, and related critical paths, with no documented waiver. — owner: Quality Engineer; follow-up: deferred-no-followup
- [medium] The implemented test dependency drifts from the approved plan: `engine/pyproject.toml:13` requires `pytest>=9.0.3,<10`, while the feature assembly plan specifies `pytest>=8,<9`. No plan reconciliation or architecture decision explains the major-version change, so the evidence was produced under an undeclared toolchain contract. — owner: Architect + Backend Developer; follow-up: deferred-no-followup

## Non-Blocking Recommendations With Owner/Follow-up

None. The eight findings above are blocking for this review result.

## Prior-Finding Closure Matrix

| Prior finding | Status in this pass | Evidence / residual risk |
|---|---|---|
| Prompt construction did not bind feature/build/story context | Resolved | The committed prompts bind `FEATURE_ID`, `BUILD_SCOPE`, and the story focus. |
| Evidence lifecycle and gate eligibility accepted stale/invalid evidence | Partial / reopened | Fresh approval revision/digest/semantic binding and watcher reconciliation are fixed, but the public `observe_evidence` path can still overwrite the last valid projection and YAML/Markdown parsing remains absent. |
| Streaming private-key redaction could leak oversized or unterminated blocks | Resolved | Oversized, unterminated, false-terminator, and matching-end probes were redacted without disclosure. |
| Eager composition caused runtime mutation during reads | Resolved | Policy/repository work is deferred and read queries did not write state. |
| Descriptor failure left runs stuck in `Launching` | Resolved | The failure path records `LaunchFailed`; the separate orphaned-tmux commit-compensation defect remains in the new critical finding. |
| Validator-runner exception had no terminal outcome | Resolved | The path records `ValidatorCancelled` and blocks the gate. |
| Subprocess output capture was unbounded | Resolved | The provider adapter uses bounded selector-driven streams. |
| Runtime override was absent from session/filter processes | Resolved | The configured environment is propagated. |
| Tmux pipe disable used invalid empty `-o` arguments | Resolved | Pipe disable uses the supported `pipe-pane` form. |
| Transcript completion, preview, and filter actions were unreachable | Resolved | They are exposed in the TUI; crash consistency is tracked separately above. |
| Authorization/side effects/CAS failures could leave stale external state | Reopened | Launch commit failure can orphan a tmux session and transcript commit failure can disable piping while state remains active. |
| Watcher dedupe/malformed input replaced the last valid observation | Partial / reopened | Reconciliation preserves valid state, but `observe_evidence` bypasses it and invalid YAML/Markdown are classified as available. |
| Immutable identity/recovery lacked run-id validation | Resolved | Run identity is validated during recovery. |
| Query status could remain `Active` after tmux disappeared | Resolved | QueryService performs a fresh tmux probe. |
| Authorization denials lacked a durable audit event | Resolved | `AuthorizationDenied` is recorded. |
| File ownership checks ignored group identity | Resolved | Group identity is included in the ownership checks. |
| Policy reads followed pre-existing symlinks | Resolved for the reported policy path | Policy reads now fail closed on the tested pre-existing symlink. Validator-script containment and remaining pathname TOCTOU are tracked separately above. |
| Run state images grew without bound | Resolved | Snapshot/event retention is bounded. |
| Preflight collision details and reviewer-validator output were incorrect/noisy | Resolved | Collision details are populated and reviewer-only validator summaries are suppressed. |

## Vertical-Slice Completeness

The feature has broad end-to-end implementation across persisted domain state, application services, filesystem/tmux/provider adapters, CLI and TUI presentation, and automated tests. The slice is not complete because essential operator paths and failure transitions are disconnected: corrupt runs cannot reach recovery, terminal provider state can still authorize attach, evidence behavior differs by entry point, and transcript/launch external side effects are not compensated when durable commits fail. These are cross-layer gaps, not isolated presentation defects.

## AC / Test Adequacy

The suite maps substantial happy-path and adversarial behavior to the feature ACs, and all 424 official tests pass. It does not adequately prove the blocking contracts above. Missing or insufficient cases include default doctor path rendering and absolute missing paths; attach denial after provider exit; tmux compensation on `RunLaunched` persistence failure; consistency between watcher reconciliation and public `observe_evidence`; invalid YAML/Markdown evidence; validator-script symlink containment and descriptor-bound use; transcript completion commit compensation and completed-sidecar reconciliation; combined transcript output/sidecar failure; corrupt-state CLI/TUI recovery reachability; and the assembly-plan branch-coverage gate. Existing passing tests therefore do not establish terminal feature acceptance.

## Architecture Compliance

The code generally follows the documented domain/application/port/adapter/presentation layering, immutable event/state approach, local-only tmux/provider boundary, explicit runtime configuration, and streaming-redaction pattern. The remaining critical findings violate the architecture's fail-closed authorization, path-containment, atomic transition, crash-recovery, and complete operator-workflow guarantees. The pytest major-version drift also differs from the approved assembly plan without an ADR or reconciled plan update. No unrelated new external runtime dependency was identified.

## Coverage Verification

The line figures in `coverage-report.md` match the official raw XML: 3,577/3,973 lines, or 90.03%. The branch claim cannot be verified from that official artifact because it contains 0 valid branches. An independent branch-enabled rerun yielded 82.65% aggregate branch coverage, with every inspected risk category below the plan's 100% requirement. Thus there is both an evidence-shape discrepancy (official artifact has no branch measurements) and a substantive gate failure (the branch-enabled result is below target); no waiver is recorded.

## Result

`REQUEST CHANGES`

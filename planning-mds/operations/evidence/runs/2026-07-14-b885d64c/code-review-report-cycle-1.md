# Code Review Report — F0001-tmux-native-agent-cockpit run 2026-07-14-b885d64c

> Required G3 Code Reviewer evidence for the linked F0001 remediation run. This review was independent of remediation implementation.

## Reviewed Files and Frozen Scope

The canonical changed-file set is the run manifest's `scm.diff_artifact`, `artifacts/diffs/changed-files.txt`, whose verified SHA-256 is `dbf596347d770a6cde69b3e6b17222de538b5f0dbfe599e5cb99ecbbfa67e148`. The review covered that complete set, with detailed inspection of:

- `engine/src/nebula_agents/**` and `engine/tests/**`, including launch/session lifecycle, authorization, filesystem persistence, evidence reconciliation, validator execution, transcript capture/reconciliation, recovery, CLI/TUI composition, and formatters.
- `engine/pyproject.toml` and the test/dependency toolchain declarations.
- The F0001 PRD, all six stories, feature assembly plan, status artifacts, CLI/workflow/data/authorization contracts, schemas, security contracts, and solution patterns.
- The current run's G0/G1/G2, test, coverage, deployability, command, lifecycle, manifest, and raw test artifacts.
- Every blocking item in the prior run's `2026-07-13-1cfbc5a0/code-review-report.md`, including remediation requirements R1–R10.

The reviewed source snapshot was frozen before failure injection and rechecked immediately before this report. The aggregate hash over `engine`, the F0001 feature directory, `planning-mds/architecture`, `planning-mds/schemas`, and `planning-mds/security` remained:

`68e0150048b557fd5298be60528198ccf65a2921065ac9059b34910cc300881d`

The supplied diff contains uncommitted and untracked workspace files. `HEAD`, `main`, `origin/main`, and the named feature branch all resolve to `eadc990b3fbf77364368297196db32dde8d75438`, so neither the branch name nor an immutable head commit identifies the reviewed implementation. This remains a material reproducibility limitation. In particular, `check-pr-size.sh --base main` reports zero changed files because the implementation is untracked; that output is not meaningful for this review. The manifest diff artifact and frozen aggregate hash are therefore the exact review boundary.

## Validation Artifacts

- Official JUnit artifact: 476 tests, 476 passed, 0 failed, 0 errors, 0 skipped; SHA-256 `988f4a1d239a19e20aa6b097ffe84e72c6a718385cfe1690c99a1f20d4a16c1f` and 70,652 bytes.
- Independent safe rerun excluding only the real-tmux lifecycle: 475 passed in 1.70 seconds, with no skips or xfails. The supplied official suite includes the separately passing real-tmux lifecycle test.
- Official branch-enabled coverage XML: 4,019/4,482 lines (89.67%) and 1,146/1,418 branches (80.82%); SHA-256 `bb248602f5a7e082bcee7bb41a64ce32d096e1a18ded975c1729604749237b44` and 205,719 bytes. Direct XML parsing matched the report and manifest.
- Declared critical modules reached 100% branch coverage: `application/authorization.py` 42/42, `domain/transitions.py` 24/24, `domain/redaction.py` 26/26, and `presentation/session_entry.py` 60/60.
- The coverage validator accepted 89.67% against the 85% minimum. Code-quality validation exited 0 with no TODO/FIXME markers and no oversized files. The repository lint wrapper exited 0 while noting that no backend linter is configured. Tracker validation exited 0 with no warnings.
- The environment used Python 3.14.4, pytest 9.1.1, and a clean `pip check`; dependency evidence reports no pytest vulnerability. The reconciled `pytest>=9.0.3,<10` range is present in both the assembly plan and `engine/pyproject.toml`. Pytest 9.0.3 is the upstream security-fix release for CVE-2025-71176 ([NVD](https://nvd.nist.gov/vuln/detail/CVE-2025-71176), [pytest releases](https://github.com/pytest-dev/pytest/releases)).
- Installed-CLI smoke from `/tmp` with `NEBULA_AGENTS_PRODUCT_ROOT` set to this repository produced table and JSON doctor output with the exact workspace, planning, runtime, prompt, tmux executable, and provider executable paths, and did not create the configured runtime directory.
- Targeted real-filesystem, subprocess-boundary, and side-effect failure injection was performed for the three findings below. All probes used temporary state outside the repository.

## Severity-Ranked Findings

### [critical] R2 launch compensation can publish `Active` and then kill the only tmux session

`RunService.launch` treats every exception from the `RunLaunched` commit as if publication did not occur. It kills the created tmux session and then attempts `LaunchFailed` using the original revision (`engine/src/nebula_agents/application/runs.py:303-332`). The filesystem repository can raise after replacing `run.json` with the new snapshot, most directly during the directory `fsync` after `os.replace` (`engine/src/nebula_agents/infrastructure/filesystem_store.py:258-270`, `:292-336`). In that state the fallback commit is stale and its failure is swallowed.

An exact real-repository probe used a `FilesystemRunRepository` subclass that called the production commit and then raised immediately after `RunLaunched`, modeling a post-publication durability error. The result was:

```text
raised RuntimeError post-publish failure
persisted_status Active
persisted_revision 1
last_event_sequence 2
tmux_present False
events ['LaunchRequested', 'RunLaunched']
```

The durable state advertises a launched active provider after the external session has been killed, and there is no terminal `LaunchFailed` audit event. The existing forced-failure unit test uses a fake repository that raises before updating its record and does not cover this partial-publication boundary. This violates R2's terminal, attach-disabled, no-orphan invariant.

Owner: Backend Developer. Required correction: make the commit result unambiguous or reload/reconcile the published revision before choosing compensation and the expected revision for a durable terminal event; add a real-filesystem post-publication test.

### [critical] R4 descriptor-bound feature root does not bind descendant story reads

The validator runner safely opens the workspace, script, and feature directory descriptors (`engine/src/nebula_agents/infrastructure/watcher.py:410-465`), but the child story validator enumerates descendants with pathname `rglob` and later reads them with `Path.read_text` (`agents/product-manager/scripts/validate-stories.py:49-53`, `:323-327`). Holding a descriptor to the parent directory neither freezes descendant directory entries nor applies `O_NOFOLLOW` to story files.

The boundary probe began with a regular invalid story inside the governed feature directory. After the runner completed its parent-side checks and descriptor opens, the process seam replaced that story with a symlink to a valid story outside the governed feature and then delegated to the real subprocess runner. The child followed the replacement and returned success:

```text
replacement_is_symlink True
child_exit 0
child_mentions_original_path True
runner_exit 0
```

The validator therefore accepted out-of-scope content under an in-scope pathname. Existing tests freeze the validator script descriptor and reject pre-existing root symlinks, but do not exercise descendant replacement after the feature descriptor is opened. This violates R4's descriptor-bound stable/no-symlink governed-input requirement.

Owner: Backend Developer + Architect. Required correction: enumerate and open governed story inputs relative to trusted directory descriptors with no-follow semantics, then validate those stable bytes, or pass an equivalent descriptor-backed manifest to the child; add the demonstrated replacement-race test.

### [critical] R5 transcript completion can durably publish `Completed` and restart the pipe

`TranscriptService.complete` also assumes any commit exception means the old `Active` snapshot remains durable. Both completion branches catch broadly and reconfigure the pipe using the old active record (`engine/src/nebula_agents/application/transcripts.py:177-205`, `:206-226`). A filesystem commit can publish the `TranscriptCompleted` snapshot/event and raise afterward at the same directory durability seam.

An exact real-filesystem probe used a repository subclass that called production `commit_authorized` and raised immediately after `TranscriptCompleted`. The result was:

```text
raised RuntimeError post-publish failure
persisted_status Completed
persisted_revision 1
pipe_disabled 1
pipe_reconfigured 1
reconfigured_with_old_status Active
event_types ['RunCreated', 'TranscriptCompleted']
```

The durable registry says capture is terminal while the application has restarted external piping, so later terminal output can be appended after the recorded completion. The existing compensation test configures its fake repository to fail before storing and therefore proves only the pre-publication case. Completed/failed sidecar reconciliation and durable failure reasons otherwise work, but they do not resolve this ambiguous commit result. This violates R5 crash consistency.

Owner: Backend Developer. Required correction: reload the authoritative snapshot after an ambiguous commit failure and compensate according to the persisted transcript state; add real-filesystem pre- and post-publication failure cases.

## Prior-Finding and R1–R10 Closure Matrix

| Requirement / prior blocker | Status | Evidence and residual risk |
|---|---|---|
| R1 doctor paths and absolute missing paths | Resolved | Human output includes a non-truncated `PATHS` block for workspace, planning, runtime, prompt, tmux, and provider executable paths; JSON contains the same absolute values. `PreflightService` emits absolute missing paths. Installed-CLI table/JSON and ready/missing-path contract tests pass. |
| R2 terminal launch/attach behavior | **Open — Critical** | Failed/exited authorization and attach guards are corrected, and ordinary pre-publication commit failure kills tmux and records terminal state. The post-publication failure probe above leaves durable `Active` with no session. |
| R3 uniform complete evidence reconciliation | Resolved | Public observation uses the reconciliation path, malformed JSON/YAML/governed Markdown is categorized and blocked without overwriting last valid evidence, and the production path set covers required lifecycle/status/story artifacts and expected missing paths. Focused watcher/service/CLI tests pass. |
| R4 descriptor-bound validator inputs | **Open — Critical** | Validator script and root descriptors are hardened, but descendant story enumeration/read remains pathname-based and follows a post-check symlink replacement, as reproduced above. |
| R5 transcript crash consistency | **Open — Critical** | Worker failure reasons, failed/completed sidecar recovery, and pre-publication compensation are present. The post-publication completion probe above produces durable `Completed` with piping restarted. |
| R6 corrupt-run recovery UX | Resolved | Corrupt snapshots are discoverable through `list_recoverable`, merged into CLI sessions and TUI selection, and recoverable through explicit owner-only CLI/TUI actions. Projections show the last gate, last audit event, safe transcript path, and exact revision-bound command. |
| R7 official branch coverage | Resolved | Official XML contains branch counters, aggregate line coverage exceeds 85%, and the four declared critical modules are each 100% branch covered with no waiver. Artifact hashes and counters match the manifest/report. |
| R8 pytest security/toolchain contract | Resolved | Plan and metadata both specify audited `pytest>=9.0.3,<10`; the suite ran on 9.1.1 with clean package/dependency checks. |
| R9 product-root composition | Resolved | CLI/TUI composition honors explicit programmatic input first, then `NEBULA_AGENTS_PRODUCT_ROOT`, then cwd. Installed doctor from a non-repository cwd resolved the repository and all committed paths correctly. |
| R10 launch interaction guidance | Resolved | Successful human launch output prints exact `nebula-agents tui --run-id ...` and `nebula-agents attach --run-id ...` commands. JSON remains structured without presentation-only text, and tests prove launch starts only one provider and does not auto-attach. |

All other prior findings remain resolved: prompt feature/build/story binding, bounded subprocess capture, runtime override propagation, valid tmux pipe-disable arguments, reachable transcript actions, last-valid evidence dedupe, run-id recovery validation, fresh tmux status projection, durable authorization-denial auditing, group ownership checks, policy symlink rejection, bounded state images, collision details, and reviewer-validator output filtering. No additional blocker was established in this pass.

## Non-Blocking Recommendations

- Commit the reviewed implementation and regenerate the manifest/diff against an immutable head revision before final closeout so branch identity, PR size, and reviewer scope are reproducible. Owner: Feature Orchestrator; follow-up: before G7/PR publication.
- Configure a backend linter or explicitly document why the repository lint wrapper intentionally has no Python backend check. Owner: Backend Developer; follow-up: backlog.

## Vertical-Slice Completeness

The feature is broadly wired across domain models and transitions, application services, filesystem/tmux/provider adapters, schemas, CLI/TUI presentation, operator guidance, and automated tests. R1, R3, and R6–R10 now form complete operator-visible slices. The slice is not terminally complete because the R2 and R5 external-side-effect transitions cannot distinguish pre-publication from post-publication persistence failure, and R4 still validates mutable pathname descendants rather than the descriptor-bound bytes that passed containment checks. Those are cross-layer atomicity and trust-boundary failures, not isolated test or presentation gaps.

## AC and Test Adequacy

The 476-test official suite and the independent 475-test safe rerun provide strong happy-path, authorization, contract, failure, and boundary coverage. The official branch artifact now satisfies the declared risk-module coverage gate. The suite is nevertheless inadequate for terminal acceptance because all three reproduced critical failures occur at untested seams:

- filesystem publication succeeds and then the launch commit reports an error;
- a story descendant is replaced after the trusted feature directory descriptor is opened;
- filesystem publication succeeds and then the transcript-completion commit reports an error.

Passing tests do not establish the corresponding R2/R4/R5 contracts until those exact cases are included.

## Architecture Compliance

The implementation otherwise follows the documented domain/application/port/adapter/presentation layering, immutable event/snapshot model, local-only provider/tmux boundary, explicit runtime composition, sanitized output, owner-only persistence, recovery projection, and streaming-redaction design. No unrelated runtime dependency or layer inversion was identified. The three critical findings violate the architecture's fail-closed atomic-transition and governed-input-containment guarantees. The uncommitted worktree boundary also prevents immutable source provenance despite internally consistent evidence hashes.

## Coverage Verification

The raw XML and coverage report agree: 4,019/4,482 lines (89.67%) and 1,146/1,418 branches (80.82%). Authorization, transitions, streaming redaction, and descriptor-validation entrypoint modules each report 100% branch coverage. The official artifact is branch-enabled and its hash/size match the evidence manifest. Coverage therefore closes R7, but it does not negate the missing post-publication and descendant-replacement behaviors demonstrated above.

## Result

`REQUEST CHANGES`

The three Critical findings block G3 approval. No High finding or additional blocker was established.

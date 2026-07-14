# Artifact Trace — F0001 remediation run 2026-07-14-b885d64c

## Artifacts Read

- `agents/actions/feature.md`
- `agents/architect/SKILL.md`
- `agents/ROUTER.md`
- `agents/agent-map.yaml`
- `agents/docs/AGENT-USE.md`
- `agents/docs/AGENT-OPS.md`
- `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/PRD.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/README.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/GETTING-STARTED.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/STATUS.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/F0001-S0001-provider-auth-and-environment-preflight.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/F0001-S0002-tmux-session-launch-and-attach.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/F0001-S0003-run-registry-and-evidence-watchers.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/F0001-S0004-gate-and-validator-dashboard.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/F0001-S0005-native-session-transcript-and-recovery.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/F0001-S0006-readonly-review-and-status-commands.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/feature-assembly-plan.md`
- `planning-mds/operations/evidence/runs/2026-07-13-1cfbc5a0/README.md`
- `planning-mds/operations/evidence/runs/2026-07-13-1cfbc5a0/evidence-manifest.json`
- `planning-mds/operations/evidence/runs/2026-07-13-1cfbc5a0/gate-decisions.md`
- `planning-mds/operations/evidence/runs/2026-07-13-1cfbc5a0/code-review-report.md`
- `planning-mds/operations/evidence/runs/2026-07-13-1cfbc5a0/security-review-report.md`

## Artifacts Created Or Updated

- `planning-mds/features/F0001-tmux-native-agent-cockpit/feature-assembly-plan.md` — added the bounded remediation contract and ownership map.
- `planning-mds/operations/evidence/runs/2026-07-14-b885d64c/` — initialized this canonical linked run package.
- `planning-mds/operations/evidence/runs/2026-07-14-b885d64c/g1-runtime-preflight.md` — recorded isolated package/provider/tmux readiness.
- `planning-mds/schemas/f0001-run-record.schema.json` — added the bounded nullable durable transcript failure reason.
- `planning-mds/architecture/data-model.md` — reconciled absolute missing paths and durable transcript failure metadata.
- `planning-mds/architecture/f0001-workflows.md` — specified transcript sidecar/compensation recovery.
- `planning-mds/architecture/f0001-cli-contract.md` — made corrupt-state recovery a supported owner-only CLI operation.
- `planning-mds/features/F0001-tmux-native-agent-cockpit/GETTING-STARTED.md` — documented product-root use, explicit launch/TUI/attach flow, and corrupt-state recovery.
- `planning-mds/features/F0001-tmux-native-agent-cockpit/README.md` — recorded the operator interaction model and active remediation run.
- `planning-mds/features/F0001-tmux-native-agent-cockpit/STATUS.md` — linked the active remediation run without claiming G2/G3 completion.
- `engine/pyproject.toml`, `engine/tests/contract/test_contract_files.py`, and the assembly plan — reconciled the test dependency to security-fixed `pytest>=9.0.3,<10` after the clean pytest-8 audit reproduced CVE-2025-71176.
- `engine/src/nebula_agents/` — closed R1-R6, R9, and R10 across domain, application, infrastructure, and presentation boundaries.
- `engine/tests/` — added and reconciled unit, contract, integration, security, TUI, descriptor, branch, and real-tmux regressions for R1-R10.
- `planning-mds/operations/evidence/runs/2026-07-14-b885d64c/test-plan.md` — recorded the remediation acceptance strategy.
- `planning-mds/operations/evidence/runs/2026-07-14-b885d64c/test-execution-report.md` — recorded the final official test results and R1-R10 coverage.
- `planning-mds/operations/evidence/runs/2026-07-14-b885d64c/coverage-report.md` — recorded official line/branch results and four 100% risk-module branch gates.
- `planning-mds/operations/evidence/runs/2026-07-14-b885d64c/deployability-check.md` — recorded clean-environment, runtime, security, and rollback readiness.
- `planning-mds/operations/evidence/runs/2026-07-14-b885d64c/g2-self-review.md` — recorded the Architect/QE closure matrix and G3 handoff.
- `planning-mds/operations/evidence/runs/2026-07-14-b885d64c/code-review-report-cycle-1.md` — archived the exact first G3 Code Reviewer report (SHA-256 `58060c7d1d00ceee2acf787ed54f58c376d6b22b835c51cf4515bbc75f856dd5`).
- `planning-mds/operations/evidence/runs/2026-07-14-b885d64c/security-review-report-cycle-1.md` — archived the exact first G3 Security Reviewer report (SHA-256 `9ed763cd55549ced503697ff9fa25e1a94f923b4bfd2a6c83daec3ff43b3c6f2`).
- `engine/src/nebula_agents/application/runs.py` and `application/transcripts.py` — added recovery-first ambiguous-commit reconciliation before tmux or pipe compensation.
- `engine/src/nebula_agents/infrastructure/watcher.py` and `agents/product-manager/scripts/validate-stories.py` — added pinned feature-descriptor child traversal with no-follow bounded stable story reads.
- `engine/tests/integration/test_commit_reconciliation.py` — added exact pre-publication and post-`os.replace`/pre-directory-`fsync` launch/transcript faults.
- `engine/tests/integration/test_story_validator_descriptor_boundary.py` — added real-subprocess stable, symlink-swap, unsafe-mode, and FIFO boundary tests.
- `planning-mds/operations/evidence/runs/2026-07-14-b885d64c/code-review-report-cycle-2.md` — archived exact cycle-2 Code Review PASS WITH RECOMMENDATIONS (SHA-256 `8d415b4567460783e35ea20a79097a862eb6f1ad755b30db63cd221502a38aa6`).
- `planning-mds/operations/evidence/runs/2026-07-14-b885d64c/security-review-report-cycle-2.md` — archived exact cycle-2 Security REQUEST CHANGES (SHA-256 `f41fb619f6af4e976c389f72b03257ce74c27631c5d4e0ae68ecdf74779c1e57`).
- `engine/src/nebula_agents/application/ports.py`, `application/runs.py`, `application/transcripts.py`, and `infrastructure/transcript.py` — added explicit pipe-liveness proof, conservative Active compensation, and no-terminal-publication behavior for H-04.
- `engine/tests/integration/test_commit_reconciliation.py` and `engine/tests/unit/test_application_services.py` — added 14 compound H-04 cases covering direct enable, launch, configure failure, observed failure, status reconciliation, legacy adapters, and ambiguous compensation commits.
- `planning-mds/operations/evidence/runs/2026-07-14-b885d64c/code-review-report-cycle-3.md` — archived the cycle-3 Code Review `REQUEST CHANGES` verdict and H-04R/H-05 reproductions (SHA-256 `916bb455e41e5f65b2940e6f43cd8136c2b2b86f10d49df58b3db4c1e21898e2`).
- `planning-mds/operations/evidence/runs/2026-07-14-b885d64c/security-review-report-cycle-3.md` — archived the cycle-3 Security Review `REQUEST CHANGES` verdict and independent H-04R/H-05 probes (SHA-256 `a37d79bf96902dc989d1d50b287044604b14c142bf1342456720af64702355a6`).
- `engine/src/nebula_agents/application/ports.py`, `application/runs.py`, `application/transcripts.py`, `infrastructure/tmux.py`, and `infrastructure/transcript.py` — made probe failures explicit and added verified owning-session termination when truthful Active compensation cannot be established.
- `engine/tests/unit/test_tmux_adapter.py`, `engine/tests/integration/test_transcript_adapter.py`, `engine/tests/integration/test_commit_reconciliation.py`, and focused service tests — added H-04R/H-05 direct, launch, authorization, recovery, termination, exact probe-value, probe-error, and propagation regressions.
- `planning-mds/architecture/decisions/ADR-004-f0001-transcript-redaction.md`, `planning-mds/architecture/f0001-workflows.md`, the F0001 assembly plan and S0005 story, and `planning-mds/security/data-protection.md` — documented the narrow last-resort owning-session termination exception without changing ordinary capture-failure/attach behavior.
- `planning-mds/operations/evidence/runs/2026-07-14-b885d64c/code-review-report-cycle-4.md` — archived cycle-4 Code Review `REQUEST CHANGES` and its direct/launch first-recovery H-06 reproduction (SHA-256 `db48c21678d88ac0e0ad1442051f599fa5d0798a14210131e8199dba751695d6`).
- `planning-mds/operations/evidence/runs/2026-07-14-b885d64c/security-review-report-cycle-4.md` — archived cycle-4 Security Review `REQUEST CHANGES`, independent H-06 reproduction, and H-04R/H-05 closure matrix (SHA-256 `a34d17233081e4526d3d9bed0421753e9c8c1c7716c488f00e168be961f06ff1`).
- `engine/src/nebula_agents/application/transcripts.py` and `application/runs.py` — extended verified owning-session termination to the first authoritative-recovery failure after a possibly-published transcript transition and normalized launch failure to stable STATE_IO.
- `engine/tests/integration/test_commit_reconciliation.py` — added H-06 direct, launch, termination-failure, and already-stopped-provider-preservation regressions.
- `planning-mds/operations/evidence/runs/2026-07-14-b885d64c/code-review-report.md` — final cycle-5 Code Review `PASS WITH RECOMMENDATIONS`; SHA-256 `afba7a7a8bdd25de5c5120a13436f72bfa38fc7a10fbe7cfa2ed046703bfa91a`.
- `planning-mds/operations/evidence/runs/2026-07-14-b885d64c/security-review-report.md` — final cycle-5 Security Review `PASS WITH RECOMMENDATIONS`; SHA-256 `b86ee09526ca61a02de4b6d9b17348a7e106352237922c89e70c3413b39e5810`.
- `planning-mds/operations/evidence/runs/2026-07-14-b885d64c/kg-reconciliation.md` — mapped the six as-built capability surfaces and recorded the missing product KG source/compiler/validator contract as the assembly plan's blocking G7 governance condition; no graph artifact was fabricated.

## Generated Evidence

- `artifacts/diffs/changed-files.txt` — exact 160-path branch worktree inventory for the G6 implementation candidate; SHA-256 `a3652a451e98b3fa9b6615635f8c21066dd09d995accb35ef14f660a5fa98eff`. The final G3 reports retain their immutable 156-path reviewed-snapshot identity; the four later paths are gate/evidence closeout documents, not implementation changes.
- `artifacts/test-results/junit.xml` — final canonical 514-test JUnit result; SHA-256 `df160ca44d33a73feef73e9dc62c44cfc50898bd1bab3ece6abe0cc4320679a6`.
- `artifacts/test-results/coverage.xml` — final 90.67% line / 81.32% aggregate-branch Cobertura result; SHA-256 `aa55e2cdb15495bb1c573703922a20cf13e716fb141c3dd53f669bafe9bc906f`.
- `artifacts/security/dependency-audit.json` — final clean resolved-environment audit.
- `artifacts/security/secrets-scan.json` — final clean expanded source/changed-validator secret scan; SHA-256 `9fc0dbecfaca2a617631238ceef05847066b9ac694a24b4a304fb6d8704dd192`.
- `artifacts/security/bandit-sast.json` — final raw 13-Low/0-Medium/0-High findings for Security Reviewer disposition; SHA-256 `7a39591751de590b4618d09939c9cfe5488c954d55a93500f124dcedbbce1f94`.
- G0-G2 validation output is recorded in `lifecycle-gates.log` and the stage reports.

## External Or Global Evidence References

None. The previous F0001 run is a local, explicitly selected failure-triage input and is linked through `rerun_of` rather than reused as passing evidence.

The approved G6 implementation candidate is frozen at commit `99d2020c8ccaa23f370eef526c27867395981c7e`. Its `main...HEAD` path set matches all 160 entries in `artifacts/diffs/changed-files.txt`, closing Code Review recommendation CR-GOV-01 before G7.

## Omissions And Waivers

- G3 cycles 1-4 are archived and final cycle 5 passed with recommendations. G4-G8 remain pending.
- No coverage or blocking-finding waiver is planned.
- Architect recorded a DAST no-target waiver because the local CLI/TUI opens no listener; Security must independently confirm or reject it at G3.
- KG lookup/hint/compiler scripts and `planning-mds/knowledge-graph`/`kg-source` are absent; no graph evidence is fabricated.

## Run Environment

The absolute product-root path is recorded because F0001 path behavior is itself under remediation and the operator reproduced a cwd-dependent failure outside the repository.

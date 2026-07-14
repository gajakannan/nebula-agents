# Artifact Trace — F0001 run 2026-07-13-1cfbc5a0

## Artifacts Read

- `agents/actions/feature.md`
- `agents/architect/SKILL.md`
- `agents/templates/feature-assembly-plan-template.md`
- `agents/templates/evidence-manifest-template.json`
- `agents/templates/feature-evidence-readme-template.md`
- `agents/templates/artifact-trace-template.md`
- `agents/templates/gate-decisions-template.md`
- `agents/templates/commands-log-template.md`
- `agents/templates/lifecycle-gates-log-template.md`
- `CONSUMER-CONTRACT.md` Feature Evidence Contract
- `agents/docs/AGENT-OPS.md`
- `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md`
- `planning-mds/BLUEPRINT.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/PRD.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/F0001-S0001-provider-auth-and-environment-preflight.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/F0001-S0002-tmux-session-launch-and-attach.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/F0001-S0003-run-registry-and-evidence-watchers.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/F0001-S0004-gate-and-validator-dashboard.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/F0001-S0005-native-session-transcript-and-recovery.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/F0001-S0006-readonly-review-and-status-commands.md`
- `planning-mds/features/F0001-tmux-native-agent-cockpit/STATUS.md`
- `planning-mds/architecture/SOLUTION-PATTERNS.md`
- `planning-mds/architecture/data-model.md`
- `planning-mds/architecture/f0001-cli-contract.md`
- `planning-mds/architecture/f0001-workflows.md`
- `planning-mds/architecture/decisions/ADR-001-f0001-local-tmux-runtime.md`
- `planning-mds/architecture/decisions/ADR-002-f0001-runtime-persistence.md`
- `planning-mds/architecture/decisions/ADR-003-f0001-provider-execution-boundary.md`
- `planning-mds/architecture/decisions/ADR-004-f0001-transcript-redaction.md`
- `planning-mds/security/f0001-authorization-model.md`
- `planning-mds/schemas/f0001-*.json`
- `agents/product-manager/scripts/validate-feature-evidence.py` and its focused G0/security/SCM fixtures
- `planning-mds/operations/evidence/README.md` and the selected F0006 `latest-run.json`/manifest convention for formal evidence-contract audit only

## Artifacts Created Or Updated

- `planning-mds/features/F0001-tmux-native-agent-cockpit/feature-assembly-plan.md` — created
- `planning-mds/architecture/feature-assembly-plan.md` — created
- `planning-mds/schemas/f0001-launch-descriptor.schema.json` — created
- `planning-mds/architecture/data-model.md` — updated with descriptor schema
- `planning-mds/architecture/f0001-cli-contract.md` — updated with descriptor schema
- `planning-mds/features/F0001-tmux-native-agent-cockpit/STATUS.md` — moved to In Progress and recorded G0
- `planning-mds/features/REGISTRY.md` — F0001 moved to In Progress
- `planning-mds/features/ROADMAP.md` — F0001 moved to In Progress
- `planning-mds/BLUEPRINT.md` — F0001 start and assembly-plan link recorded
- `planning-mds/operations/evidence/runs/2026-07-13-1cfbc5a0/` — canonical run package initialized
- `engine/src/nebula_agents/` and `engine/pyproject.toml` — local CLI/TUI implementation and package metadata created
- `engine/tests/` — unit, contract, integration, security, presentation, and real-tmux coverage created
- `planning-mds/security/` — F0001 threat, authorization, data-protection, secrets, OWASP, and dated security-review artifacts created or updated
- Feature README, getting-started guide, STATUS checklist, six story completion checklists, and generated story index — updated to the as-built G3-blocked state

## Generated Evidence

- `artifacts/diffs/changed-files.txt` — current changed-file inventory used by manifest SCM reconciliation
- G0 scoped evidence-validator output is summarized in `lifecycle-gates.log`; no separate raw JSON was requested for this gate
- Architecture, all six stories, tracker/base-run, templates, all five F0001 schemas, and whitespace/diff checks passed at G0
- G2 acceptance: 424 tests passed, 90.03% line coverage, and the real-tmux lifecycle passed; raw JUnit and coverage XML are under `artifacts/test-results/`
- Final security scans are under `artifacts/security/`; security review passed with three Low recommendations
- `code-review-report.md` records six Critical, one High, and one Medium blocking finding; G3 is `REQUEST CHANGES`

## External Or Global Evidence References

None. This run does not rely on global frontend evidence or an external evidence store.

## Omissions And Waivers

- No required G0-G3 artifact is omitted.
- Dependency, secrets, and SAST scans ran; DAST retains the dated no-target waiver because the approved architecture exposes no network listener or HTTP surface.
- G4-G8 artifacts are not omitted or waived; those stages were never opened because G3 is blocked.
- The repository's absent self-hosted KG/compiler contract remains documented, but G7 was not reached.

The first story-validator invocation used an unsupported `--feature` flag and exited 2. The plan allowlist was corrected to pass the feature directory positionally, and the rerun validated all six stories successfully.

# F0007 - Spec-Driven Orchestration and Prompt Compilation - Status

**Overall Status:** Implemented and merged to `main` (S0001–S0009, PRs #55–#61); rollout **HOLD** pending required role signoffs and a live governed product pilot
**Last Updated:** 2026-08-17

## Story Checklist

| Story | Title | Phase | Status |
|-------|-------|-------|--------|
| F0007-S0001 | Versioned action policy and schema | A | [x] Merged (#55); pending review/signoff |
| F0007-S0002 | Contract conformance and behavioral diff | A | [x] Merged (#55); pending review/signoff |
| F0007-S0003 | Run initialization and product scaffolding | B | [x] Merged (#55); pending review/signoff |
| F0007-S0004 | Typed command runtime and complete telemetry | B | [x] Merged (#55, #61); pending review/signoff |
| F0007-S0005 | Gate driver, durable checkpoints, and severity policy | B | [x] Merged (#55, #59); pending review/signoff |
| F0007-S0006 | Generated evidence prompts and drift gate | C | [x] Cutover **complete**: all 13 actions are spec-driven and all 24 evidence prompts are generated under `agents/templates/prompts/evidence-contract/` (#55 feature/plan, #56 build/feature-review/integrate/review/test/validate, #57 blog/defect-bugfix/document/init/plan-review). `prompt_drift` gate green. Independent semantic-equivalence signoff by role owners is still outstanding |
| F0007-S0007 | Version-aware validator convergence | C | [x] Merged (#55); dual-read parity proven zero-disagreement across all cutovers. Private date constants in `validate-feature-evidence.py` are **still active** — removal remains a recorded decision (see Open Decisions) |
| F0007-S0008 | Shared policy consumers and prose thinning | C | [x] Consumer tooling merged (#55) and prose thinning **done** (#57, #58): 12 action docs cut 6788→2869 lines (~58%, exceeding the 40% target), shared Retrieval Guard extracted to an `AGENTIGNORE.md` pointer, FEC trailers pointerized to `CONSUMER-CONTRACT.md`, all 11 role SKILLs brought under the 500-line regression cap. `feature.md` (976) and `plan.md` (785) remain the two heavy actions. Private-constant removal is tracked under S0007 |
| F0007-S0009 | Governed rollout and compatibility pilot | D | [~] Lifecycle gates adopted + end-to-end pilot rehearsal + rollback rehearsal + rollout report merged (#55). **LIVE** product pilot and independent all-role review remain outstanding |

## Phase Gates

| Gate | Required Evidence | Status |
|------|-------------------|--------|
| A - Policy foundation | Schema report, behavioral diff fixture, historical baseline matrix | Merged (pending signoff) |
| B - Runtime | Concurrency tests, shell-free subprocess tests, checkpoint failure/resume tests, telemetry samples | Merged (pending signoff) |
| C - Compilation | Prompt snapshots, semantic-equivalence review, dual-read parity report, literal-owner audit | Merged (24/24 prompts generated, parity zero-disagreement, prose thinned); **semantic-equivalence review by role owners pending** |
| D - Rollout | Pilot run evidence, closeout validator result, migration/rollback report | Merged (rehearsal + rollback report; `rollout-report.md`); live pilot outstanding |

## Required Signoff Roles

| Role | Required | Why Required | Set By | Date |
|------|----------|--------------|--------|------|
| Architect | Yes | Owns versioning, source-of-truth boundaries, typed operations, and compatibility model. | Planning | 2026-07-12 |
| Quality Engineer | Yes | Owns historical fixtures, failure paths, concurrency tests, and pilot regression evidence. | Planning | 2026-07-12 |
| Code Reviewer | Yes | Reviews script safety, generator correctness, common-mode policy risk, and maintainability. | Planning | 2026-07-12 |
| DevOps | Yes | Owns CI drift/conformance wiring and generated-artifact workflow. | Planning | 2026-07-12 |
| Security Reviewer | Yes | Reviews command execution, path containment, redaction, state integrity, and lock behavior. | Planning | 2026-07-12 |

## Story Signoff Provenance

Complete these rows before moving the feature to `Done`.

| Story | Role | Reviewer | Verdict | Evidence | Date | Notes |
|-------|------|----------|---------|----------|------|-------|
| F0007-S0001 | Architect | TBD | TBD | TBD | TBD | Policy/version approval |
| F0007-S0002 | Quality Engineer | TBD | TBD | TBD | TBD | Historical and independent conformance suite |
| F0007-S0003 | Code Reviewer | TBD | TBD | TBD | TBD | Initialization/scaffolding implementation |
| F0007-S0004 | Security Reviewer | TBD | TBD | TBD | TBD | Shell-free execution and telemetry boundary |
| F0007-S0005 | Architect | TBD | TBD | TBD | TBD | Checkpoint and severity-policy semantics |
| F0007-S0006 | DevOps | TBD | TBD | TBD | TBD | Generated prompt CI workflow |
| F0007-S0007 | Quality Engineer | TBD | TBD | TBD | TBD | Dual-read parity and historical verdicts |
| F0007-S0008 | Code Reviewer | TBD | TBD | TBD | TBD | Consumer consolidation and prose thinning |
| F0007-S0009 | DevOps | TBD | TBD | TBD | TBD | Rollout and lifecycle adoption |

## Open Decisions

The three planning decisions below were all resolved during implementation.

| Decision | Options | Owner | Resolution |
|----------|---------|-------|------------|
| Prompt renderer | Jinja2 or a stdlib renderer | Architect | **Stdlib renderer** — `render-prompts.py` takes no third-party dependency |
| Lock primitive | Portable lock-file protocol or platform-specific advisory lock with fallback | Architect + Security | **Portable lock file** — `run-gate.py` uses `O_CREAT\|O_EXCL` with a timeout and fails closed |
| Historical bundle granularity | Full multi-action bundle per version or per-action snapshots with a signed index | Architect | **Full multi-action bundle per version** — five bundles published under `agents/actions/spec/history/`, each currently snapshotting the `feature` action (the only action with versioned historical evidence) |

One decision remains open.

| Decision | Options | Owner | Due Before |
|----------|---------|-------|------------|
| Private-constant removal (S0007/S0008) | Remove the date-gated requirement matrix from `validate-feature-evidence.py` and read policy only, or keep the dual-read indefinitely | Architect + QE | Feature closeout. Parity evidence is in hand — `contract_compat.py --matrix` reports zero disagreement across all cutovers — so this is a recorded decision, not further implementation |

## Tracker Sync Checklist

- [x] F0007 allocated in `REGISTRY.md`; next number advanced to F0008.
- [x] F0007 added to `ROADMAP.md`.
- [x] F0007 stories added to `STORY-INDEX.md`.
- [x] F0007 feature and stories added to `BLUEPRINT.md`.
- [x] Story implementation evidence recorded (PRs #55–#61 merged to `main`; all six framework lifecycle gates green).
- [ ] Required signoffs complete.
- [ ] Canonical knowledge-graph mappings bound (the F0007 shard still carries `coverage_excluded`; capability nodes and `node_bindings` for the spec-driven surface are deferred to closeout KG reconciliation).
- [ ] Feature closeout and archive decision recorded.

## Remaining Work to Close

1. **Live governed pilot** (S0009 D-gate) — one real feature run end-to-end through `run-gate.py` to closeout. `test_pilot_end_to_end.py` proves the toolchain against a fixture product root; it does not substitute for a live run. F0003 is the recommended pilot subject: it is next on the roadmap and its entry criteria are already met.
2. **Five role signoffs** — Architect, Quality Engineer, Code Reviewer, DevOps, Security Reviewer; every row in *Story Signoff Provenance* is still `TBD`.
3. **Semantic-equivalence review of the generated prompts** (S0006) — the cutover shipped; role-owner acceptance that generated output preserves the accepted semantics has not been recorded.
4. **Private-constant removal decision** (S0007/S0008) — see *Open Decisions*.
5. **Canonical KG mappings** — bind the spec-driven surface and drop `coverage_excluded` from the F0007 shard.

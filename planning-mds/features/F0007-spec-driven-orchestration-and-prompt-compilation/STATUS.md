# F0007 - Spec-Driven Orchestration and Prompt Compilation - Status

**Overall Status:** Implemented (S0001–S0009); rollout **HOLD** pending required role signoffs and a live governed product pilot
**Last Updated:** 2026-07-18

## Story Checklist

| Story | Title | Phase | Status |
|-------|-------|-------|--------|
| F0007-S0001 | Versioned action policy and schema | A | [x] Implemented (branch `feat/F0007-spec-driven-orchestration`; pending review/signoff) |
| F0007-S0002 | Contract conformance and behavioral diff | A | [x] Implemented (branch `feat/F0007-spec-driven-orchestration`; pending review/signoff) |
| F0007-S0003 | Run initialization and product scaffolding | B | [x] Implemented (branch `feat/F0007-spec-driven-orchestration`; pending review/signoff) |
| F0007-S0004 | Typed command runtime and complete telemetry | B | [x] Implemented (branch `feat/F0007-spec-driven-orchestration`; pending review/signoff) |
| F0007-S0005 | Gate driver, durable checkpoints, and severity policy | B | [x] Implemented (branch `feat/F0007-spec-driven-orchestration`; pending review/signoff) |
| F0007-S0006 | Generated evidence prompts and drift gate | C | [~] Machinery implemented (renderer + drift/semantic gate + CI wiring + `feature` pilot); remaining-action rollout & semantic-equivalence cutover of the 24 hand-written prompts are human-gated (PM + role owners) and deferred |
| F0007-S0007 | Version-aware validator convergence | C | [x] Implemented (version-aware selection + dual-read parity proven zero-disagreement across all cutovers; private constants kept — their removal is deferred to S0008 per the parity-approval gate) |
| F0007-S0008 | Shared policy consumers and prose thinning | C | [~] Consumer tooling implemented (contract-value resolver + inverse-literal/drift audit, vague-language linter, coverage-script migration); prose thinning (40% reduction, retrieval-guard extraction, disposition inventory) and private-constant removal are role-owner-gated and deferred (removal also follows the S0009 pilot per PRD rollout) |
| F0007-S0009 | Governed rollout and compatibility pilot | D | [~] CI/lifecycle gates adopted + end-to-end pilot rehearsal + rollback rehearsal + rollout report; LIVE product pilot and independent all-role review are human-gated and deferred |

## Phase Gates

| Gate | Required Evidence | Status |
|------|-------------------|--------|
| A - Policy foundation | Schema report, behavioral diff fixture, historical baseline matrix | Implemented (pending signoff) |
| B - Runtime | Concurrency tests, shell-free subprocess tests, checkpoint failure/resume tests, telemetry samples | Implemented (pending signoff) |
| C - Compilation | Prompt snapshots, semantic-equivalence review, dual-read parity report, literal-owner audit | Not Started |
| D - Rollout | Pilot run evidence, closeout validator result, migration/rollback report | Implemented (rehearsal + rollback report; `rollout-report.md`); live pilot deferred |

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

| Decision | Options | Owner | Due Before |
|----------|---------|-------|------------|
| Prompt renderer | Jinja2 or a stdlib renderer | Architect | S0006 kickoff |
| Lock primitive | Portable lock-file protocol or platform-specific advisory lock with fallback | Architect + Security | S0003 kickoff |
| Historical bundle granularity | Full multi-action bundle per version or per-action snapshots with a signed index | Architect | S0001 completion |

## Tracker Sync Checklist

- [x] F0007 allocated in `REGISTRY.md`; next number advanced to F0008.
- [x] F0007 added to `ROADMAP.md`.
- [x] F0007 stories added to `STORY-INDEX.md`.
- [x] F0007 feature and stories added to `BLUEPRINT.md`.
- [ ] Story implementation evidence recorded.
- [ ] Required signoffs complete.
- [ ] Feature closeout and archive decision recorded.

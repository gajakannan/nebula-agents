# F0007 - Spec-Driven Orchestration and Prompt Compilation - Status

**Overall Status:** Planned
**Last Updated:** 2026-07-12

## Story Checklist

| Story | Title | Phase | Status |
|-------|-------|-------|--------|
| F0007-S0001 | Versioned action policy and schema | A | [ ] Not Started |
| F0007-S0002 | Contract conformance and behavioral diff | A | [ ] Not Started |
| F0007-S0003 | Run initialization and product scaffolding | B | [ ] Not Started |
| F0007-S0004 | Typed command runtime and complete telemetry | B | [ ] Not Started |
| F0007-S0005 | Gate driver, durable checkpoints, and severity policy | B | [ ] Not Started |
| F0007-S0006 | Generated evidence prompts and drift gate | C | [ ] Not Started |
| F0007-S0007 | Version-aware validator convergence | C | [ ] Not Started |
| F0007-S0008 | Shared policy consumers and prose thinning | C | [ ] Not Started |
| F0007-S0009 | Governed rollout and compatibility pilot | D | [ ] Not Started |

## Phase Gates

| Gate | Required Evidence | Status |
|------|-------------------|--------|
| A - Policy foundation | Schema report, behavioral diff fixture, historical baseline matrix | Not Started |
| B - Runtime | Concurrency tests, shell-free subprocess tests, checkpoint failure/resume tests, telemetry samples | Not Started |
| C - Compilation | Prompt snapshots, semantic-equivalence review, dual-read parity report, literal-owner audit | Not Started |
| D - Rollout | Pilot run evidence, closeout validator result, migration/rollback report | Not Started |

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

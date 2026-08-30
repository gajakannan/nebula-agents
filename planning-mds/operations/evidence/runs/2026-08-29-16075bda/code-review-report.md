# Code Review Report — F0003

**Run:** `2026-08-29-16075bda` · **Gate:** G3 · **Owner:** Code Reviewer · **Date:** 2026-08-29

## Scope Review

Reviewed: 15 new modules and 12 modified across `engine/src/nebula_agents/**`, plus
`docs/mcp-host-configuration.md`. The 514 F0001 tests pass unmodified, which bounds the
blast radius of every change to F0001 code.

Read for defects, not for conformance — conformance is `test_layering.py`,
`test_package_contract.py`, `test_facade_split.py`, and the schema tests, all of which
were verified to fail when their target is broken rather than assumed to work.

## Findings

### CR-1 (Medium) — two stores commit independently; a failure between them diverges state

`EvidenceService.index_artifacts` commits the artifact index, then appends the
`ArtifactIndexed` runtime event in a **separate** transaction against a different store.
`summarize` and `LearningService.review`/`decide` share the shape.

If the second commit fails — a stale run revision is the realistic case, since another
process may have advanced the run — the projection is updated and the audit entry is not.
BLUEPRINT §5.3 requires indexing to create a runtime event, so the states disagree.

**Severity is medium, not high, for two reasons.** The index is a projection: re-indexing
is idempotent and is the documented recovery path, so the divergence is repairable without
data loss. And the failure is loud — the caller sees the error rather than a silent
success.

**Not fixed in this run.** A fix means either a two-phase commit across two stores or
folding the index into the run record, and the second contradicts ADR-006's decision to
keep the index a separate projection. That is an architecture question, not a code fix.

### CR-2 (Low) — stale-evidence blocking is run-wide, not proposal-wide

`LearningService._require_usable_evidence` refuses to draft when **any** entry in the run
is stale or missing, including entries unrelated to the failure that would drive a
proposal. S0006's acceptance criterion says exactly this ("Evidence is stale or missing;
proposal generation is blocked"), so it matches the contract. Noted because the behaviour
is stricter than a reader might expect, and a single missing artifact silences the whole
run's learning.

### CR-3 (Low) — `metrics` gate-wait uses a proxy timestamp

`gate_wait_seconds` derives from the gate's `updated_at`, falling back to the run's. That
is an approximation: neither is a gate-transition time. Already recorded in the coverage
audit; repeated here because it is the one metric whose value is not exactly what its name
says.

## Design decisions I checked and agree with

Recorded because a review that lists only faults tells a reader nothing about what was
examined and found sound.

- **ADR-002 primitives extracted rather than copied** into `infrastructure/atomic.py`. A
  second hand-written locking and fsync routine is how two copies drift; the 514 tests
  verified the refactor changed no behaviour.
- **The artifact index takes its own lock**, not the run lock. A projection must never
  block a launch.
- **One `ArtifactIndexed` event per index call**, not per artifact. The repository pairs
  every event with a state image and a revision bump, so N artifacts would cost N commits
  for one logical operation; the payload carries every artifact's id and policy result.
- **`ArtifactRedactionStatus` kept separate** from F0001's `RedactionStatus`. They look
  mergeable and are not — merging would change an F0001 record shape. The bridge is total
  and asserted.
- **Retrieval policy derived, never asserted** by a caller, with `Blocked` outranking
  `Missing` because `Missing` reads as recoverable.
- **Usage validation moved ahead of the application build.** A usage error must not depend
  on a workspace being resolvable.
- **`--format` on subparsers uses `SUPPRESS`.** argparse applies subparser defaults after
  the parent parses; a plain default would silently downgrade `evidence --format json list`.

## Contract conformance

F0001's nine commands parse and behave identically; contract `1.1` is additive at the
command surface. Two F0001 **schemas** changed, both additively and both recorded for the
Architect: `f0001-runtime-event` gained eleven `event_type` members (S3-F1) and
`f0001-local-policy` gained `proposal_grants` (SEC-1). Neither changes an existing field,
type, or member, but a strict `1.0` reader rejects the new event types.

## Implementation Risks

- The two schema extensions are the only places contract `1.1` is not transparent to a
  `1.0` reader. Both are Architect decisions at G4.
- CR-1's divergence window is repairable but real, and it will recur in any future store
  F0003 adds unless the pattern is settled.

## Validation Evidence

732 tests on 3.11/3.12/3.14; line 92.3%, branch 82.7%. Guards were each verified to fail
when their target is broken — the layering rule, the query-facade surface, the schema
conformance in both directions, and the MCP handler/contract invariant under `python -O`.

## Recommendations

- [medium] Settle whether a projection-store commit and its audit event must be atomic, or whether repairable divergence is accepted as the pattern for F0003's stores (CR-1) — owner: Architect; follow-up: decide at G4; affects any future store
- [low] Consider narrowing stale-evidence blocking from run-wide to the artifacts backing each proposal, if operators find a single missing artifact silences learning too often (CR-2) — owner: Product Manager; follow-up: post-closeout backlog
- [low] Replace the gate-wait proxy timestamp with a real gate-transition time when gate state is next revisited (CR-3) — owner: Architect; follow-up: F0001 backlog

## Result

PASS WITH RECOMMENDATIONS

Critical: 0. High: 0. Three recommendations routed; CR-1 is the one that needs an
architecture decision rather than a code change.

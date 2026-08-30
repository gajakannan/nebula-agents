# PM Closeout — F0003 Local Agent Runtime Control Plane

**Run:** `2026-08-29-16075bda` · **Gate:** G8 · **Owner:** Product Manager
**Date:** 2026-08-30 · **Role switched:** read `agents/product-manager/SKILL.md`

## Final Story Status

All seven stories are terminal. The Orphaned Story Rule is satisfied: no story is archived
in `Not Started` or `In Progress`, and nothing required a rehoming decision.

| Story | Title | Status |
|-------|-------|--------|
| F0003-S0001 | Runtime command surface and wrap launch | Done |
| F0003-S0002 | Provider capability matrix and launch guards | Done |
| F0003-S0003 | MCP status and evidence tools | Done |
| F0003-S0004 | Evidence artifact store and retrieval index | Done |
| F0003-S0005 | Deterministic transcript, log, and validator summaries | Done |
| F0003-S0006 | Runtime metrics and failure-learning review | Done |
| F0003-S0007 | Application query/command service split | Done |

Delivered: twelve `nebula-agents` commands and six read-only MCP tools, over 732 engine
tests green on Python 3.11, 3.12, and 3.14 at 92.3% line coverage.

## Archive Decision

**Archive.** F0003 reached `Done` with no remaining blocking work: G0–G7 all passed, four
required roles signed, and the operator approved at G4 with every carried decision
confirmed.

The feature folder moves from `planning-mds/features/F0003-local-agent-runtime-control-plane/`
to `planning-mds/features/archive/F0003-local-agent-runtime-control-plane/`.

Knowledge-graph bindings were written at G7 as **CODE paths only** precisely so this move
cannot break them: no binding points at a feature-doc path, so the archive transition
relocates documentation without orphaning a single node.

## Deferred Follow-ups

| Follow-up | Why deferred | Owner | Tracking |
|-----------|--------------|-------|----------|
| CR-2 — narrow stale-evidence blocking from run-wide to per-proposal | Matches S0006's acceptance criterion as written; a change would revise the contract, not fix a defect | Product Manager | Post-closeout backlog |
| CR-3 — replace the `gate_wait_seconds` proxy timestamp with a real gate-transition time | Requires gate-state changes owned by F0001 | Architect | F0001 backlog |
| S9-F2 — reclassify `doctor` outside a workspace from `SCHEMA_INVALID` exit 9 to preflight exit 3 | Pre-existing F0001 behaviour; reclassifying an F0001 error is a contract change with a 514-test regression boundary | Architect | F0001 backlog |
| SEC-2 — document `proposal_grants` in the authorization model | Documentation of a mechanism already implemented and tested | Architect | Before F0002 consumes the contract |

None is blocking. Each has a named owner, and none is a defect in delivered behaviour.

## Framework Findings — routed to F0007, not to this feature

This run was **F0007-S0009's live governed pilot**. Nine findings concern the framework
rather than F0003, and they are the pilot's actual product. They are recorded here so
F0007's rollout report can collect them, and they do **not** gate this closeout.

| ID | Severity | Finding |
|----|----------|---------|
| — | **High** | `validate-feature-evidence.py` **silently skips** the deep check for an Active non-terminal feature, so every gate's own validator exits 0 having checked nothing mid-flight. Forcing it caught real failures at **seven** gates |
| S8-F1 | Low | Manifest `test_results.artifacts` paths are never verified to resolve, while prose references are checked strictly |
| S10-F1 | Low | `artifact_references()` matches greedily, so a path written naturally in prose is extracted with its trailing backtick and full stop |
| S9-F3 | Low | `feature.yaml` names the G2 artifact `g2-deployability-check.md`; the validator requires `deployability-check.md` |
| S11-F1 | Medium | `parse_status_required_roles` reads a section named exactly `Required Role Matrix`; a differently-titled section is silently unreadable, and nothing says so until G5 |
| S12-F1 | Medium | `validate.py` emits an `Errors:` block, prints `[PASS]`, and exits 1 — three signals, three conclusions |
| S12-F2 | Low | `agents/architect/SKILL.md` says confirm `validate.py` exit 0; `feature.yaml` G7 forbids the only command that produces it |
| S8-F1b | Low | `.gitignore`'s repo-root `coverage.xml` rule excluded committed run evidence. **F0001's archived runs carried the same dangling reference**; their genuine artifacts are now committed |
| S3-F2 | Low | A G1 probe asserted only that *an* error was raised, so a schema-allowlist refusal was misread as a validation |

The first is the one worth acting on: a gate green means nothing while a feature is in
flight, and this run only produced trustworthy evidence because the deep check was forced
by hand at every gate.

## Recommendation Acceptances

Identifiers below match recommendation IDs carried in the role reports. The **DAST waiver
is deliberately not listed here**: it lives under `security_scans.dast.waiver` with reason,
owner, and approval date, and is validated by the security-scan completeness check rather
than by a PM acceptance line. `manifest.waivers` is empty, so there is no waiver key to
accept.


- Accepted: SEC-1 — mitigation: the caller-declared reviewer role was removed entirely and authority is now derived from the target document and verified against `proposal_grants` in the owner-only policy file, deny by default, with three regression tests including cross-class isolation; the defect was fixed inside the G3 review cycle rather than carried
- Accepted: S3-F1 — mitigation: the `event_type` enum extension is confirmed as the one F0001 schema change contract `1.1` makes; runtime-contract §9 records it explicitly, including that a strict `1.0` reader rejects unknown event types and that this is the one place rollback is not clean, and every event written under `1.0` remains valid
- Accepted: S9-F2 — mitigation: `doctor` misreporting outside a workspace is pre-existing F0001 behaviour, not F0003 code; the MCP documentation no longer routes operators to it for that diagnosis, and reclassification is tracked on the F0001 backlog
- Accepted: S9-F3 — mitigation: the validator's artifact name is authoritative in practice because it is what fails the gate; `deployability-check.md` is what this run wrote, and the spec/validator disagreement routes to F0007's rollout report
- Accepted: CR-2 — mitigation: run-wide stale-evidence blocking matches S0006's acceptance criterion as written, so narrowing it would revise the contract rather than fix a defect; deferred to the post-closeout backlog with the Product Manager as owner
- Accepted: CR-3 — mitigation: the `gate_wait_seconds` proxy timestamp is documented in the coverage audit and the code review as an approximation rather than left implicit; a real gate-transition time requires gate-state changes owned by F0001
- Accepted: S4-F1 — mitigation: the persisted `ProviderCapabilityReport` is the durable sanitized record for a blocked launch, because the guard runs before any run exists and creating one to record that none was created would defeat the ordering it protects
- Accepted: CR-1 — mitigation: projection-store commits and their audit events need not be atomic, provided the projection is rebuildable and the failure surfaces to the caller; recorded at G4 as a standing pattern decision for future F0003 stores rather than a one-off

## Tracker Updates

| Tracker | Update |
|---------|--------|
| `REGISTRY.md` | F0003 moves from Active Features to Archived Features with the archived date and path |
| `ROADMAP.md` | F0003 moves from `Now` to `Completed` |
| `STORY-INDEX.md` | Regenerated after the archive move |
| `BLUEPRINT.md` | Feature Plan links updated to the archived path |
| `STATUS.md` | Overall Status `Done`; Closeout Summary filled; all seven stories terminal |

Trackers are **compiled** from `kg-source/features/F0003.yaml`, not hand-edited — the
shard's `status`, `registry_section`, `roadmap_section`, and `path` change and `compile.py`
regenerates the fenced regions. `--check-reproducible` confirms the committed generated
files equal `compile(source)`.

## Validator Results

| Validator | Result |
|-----------|--------|
| `validate-feature-evidence.py --stage closeout` | PASS |
| `validate-stories.py` | PASS — 7 stories, no issues |
| `validate-trackers.py` | PASS — 0 errors, 0 warnings |
| `generate-story-index.py` | Regenerated after the move |
| `scripts/kg/validate.py` | PASS, exit 0 after `--write-coverage-report` |
| `scripts/kg/validate.py --check-drift` | PASS |
| `scripts/kg/validate.py --check-reproducible` | OK |
| Six framework lifecycle gates | PASS |
| Engine test suite | 732 passed on 3.11 / 3.12 / 3.14 |

`--write-coverage-report` was run **after** the archive move, as G7's constraint required:
the report records evidence paths, and running it before the move would have written paths
the move immediately invalidated.

## Result

PASS

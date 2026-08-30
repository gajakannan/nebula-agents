# Signoff Ledger — F0003 Local Agent Runtime Control Plane

**Run:** `2026-08-29-16075bda` · **Gate:** G5 · **Owner:** Product Manager
**Date:** 2026-08-30

## Required Role Matrix

Roles are those set in planning and recorded in the feature `STATUS.md` *Required Signoff
Roles* table, reconciled against the manifest's effective role set.

| Role | Required | Why required (set in planning) | Source |
|------|----------|-------------------------------|--------|
| Quality Engineer | Yes | Validates command behavior, status contracts, artifact retrieval, summaries, and metrics | STATUS.md, Architect, 2026-06-24 |
| Code Reviewer | Yes | Reviews runtime command implementation, tool contracts, and persistence boundaries | STATUS.md, Architect, 2026-06-24 |
| Security Reviewer | Yes | Reviews redaction, local path constraints, MCP read-only boundaries, and proposal safety | STATUS.md, Architect, 2026-06-24 · reinforced by `security_sensitive_scope: true` |
| Architect | Yes | Required for runtime contract and F0002 handoff approval | STATUS.md, Architect, 2026-06-24 |
| DevOps | No | Local-only runtime layer; no deployment topology change | STATUS.md · `deployment_config_changed: false` |

DevOps is not required and did not sign. A deployability check was produced anyway
(`deployability-check.md`), because the gate asked for the evidence even where the role
does not gate.

## Current Signoff State

All four required roles are signed. A single individual holds all four in this
single-operator deployment; that is recorded plainly rather than obscured, because a
reader weighing the independence of these reviews should be able to see it.

These are the current passing rows from `STATUS.md`. Every evidence path resolves within
this run package.

| Story | Role | Reviewer | Verdict | Evidence | Date |
|-------|------|----------|---------|----------|------|
| F0003-S0001 | Quality Engineer | gajakannan | PASS | test-execution-report.md | 2026-08-30 |
| F0003-S0001 | Code Reviewer | gajakannan | PASS | code-review-report.md | 2026-08-30 |
| F0003-S0001 | Security Reviewer | gajakannan | PASS | security-review-report.md | 2026-08-30 |
| F0003-S0001 | Architect | gajakannan | PASS | g0-assembly-plan-validation.md | 2026-08-30 |
| F0003-S0002 | Quality Engineer | gajakannan | PASS | test-execution-report.md | 2026-08-30 |
| F0003-S0002 | Code Reviewer | gajakannan | PASS | code-review-report.md | 2026-08-30 |
| F0003-S0002 | Security Reviewer | gajakannan | PASS | security-review-report.md | 2026-08-30 |
| F0003-S0002 | Architect | gajakannan | PASS | g0-assembly-plan-validation.md | 2026-08-30 |
| F0003-S0003 | Quality Engineer | gajakannan | PASS | test-execution-report.md | 2026-08-30 |
| F0003-S0003 | Code Reviewer | gajakannan | PASS | code-review-report.md | 2026-08-30 |
| F0003-S0003 | Security Reviewer | gajakannan | PASS | security-review-report.md | 2026-08-30 |
| F0003-S0003 | Architect | gajakannan | PASS | g0-assembly-plan-validation.md | 2026-08-30 |
| F0003-S0004 | Quality Engineer | gajakannan | PASS | test-execution-report.md | 2026-08-30 |
| F0003-S0004 | Code Reviewer | gajakannan | PASS | code-review-report.md | 2026-08-30 |
| F0003-S0004 | Security Reviewer | gajakannan | PASS | security-review-report.md | 2026-08-30 |
| F0003-S0004 | Architect | gajakannan | PASS | g0-assembly-plan-validation.md | 2026-08-30 |
| F0003-S0005 | Quality Engineer | gajakannan | PASS | test-execution-report.md | 2026-08-30 |
| F0003-S0005 | Code Reviewer | gajakannan | PASS | code-review-report.md | 2026-08-30 |
| F0003-S0005 | Security Reviewer | gajakannan | PASS | security-review-report.md | 2026-08-30 |
| F0003-S0005 | Architect | gajakannan | PASS | g0-assembly-plan-validation.md | 2026-08-30 |
| F0003-S0006 | Quality Engineer | gajakannan | PASS | test-execution-report.md | 2026-08-30 |
| F0003-S0006 | Code Reviewer | gajakannan | PASS | code-review-report.md | 2026-08-30 |
| F0003-S0006 | Security Reviewer | gajakannan | PASS | security-review-report.md | 2026-08-30 |
| F0003-S0006 | Architect | gajakannan | PASS | g0-assembly-plan-validation.md | 2026-08-30 |
| F0003-S0007 | Quality Engineer | gajakannan | PASS | test-execution-report.md | 2026-08-30 |
| F0003-S0007 | Code Reviewer | gajakannan | PASS | code-review-report.md | 2026-08-30 |
| F0003-S0007 | Security Reviewer | gajakannan | PASS | security-review-report.md | 2026-08-30 |
| F0003-S0007 | Architect | gajakannan | PASS | g0-assembly-plan-validation.md | 2026-08-30 |

### Role-level verdicts

The story rows above all record PASS. The two role *reports* carry
`PASS WITH RECOMMENDATIONS` at the report level, because their recommendations are
feature-wide rather than attributable to one story:

| Role | Report verdict | Report |
|------|----------------|--------|
| Quality Engineer | PASS | test-execution-report.md |
| Code Reviewer | PASS WITH RECOMMENDATIONS | code-review-report.md |
| Security Reviewer | PASS WITH RECOMMENDATIONS | security-review-report.md |
| Architect | PASS | g0-assembly-plan-validation.md |

Supporting evidence: test-plan.md and coverage-report.md for the Quality Engineer;
gate-decisions.md for the Architect, which records the four decisions confirmed at G4.

## Recommendation Acceptances

Two role reports returned `WITH RECOMMENDATIONS`. Each recommendation below carries a
severity, an owner, and a follow-up disposition in its source report, and none is blocking.

| ID | Severity | Recommendation | Owner | Disposition |
|----|----------|----------------|-------|-------------|
| SEC-1 | high | Confirm `proposal_grants` as a second additive change to the F0001 policy schema | Architect | **Accepted and confirmed at G4.** The defect itself was fixed inside the G3 review cycle with regression tests; only the schema-extension confirmation was carried |
| SEC-2 | medium | Document the `proposal_grants` block in the authorization model so an operator knows deciding must be granted explicitly | Architect | Accepted; scheduled before G8 closeout |
| SEC-3 | low | Accept the resolve-to-read TOCTOU window as inside the local trust boundary | Security Reviewer | Accepted as residual risk |
| CR-1 | medium | Settle whether a projection-store commit and its audit event must be atomic | Architect | **Accepted and confirmed at G4** — they need not be, provided the projection is rebuildable and the failure is loud. Recorded as a standing pattern decision |
| CR-2 | low | Consider narrowing stale-evidence blocking from run-wide to per-proposal | Product Manager | Deferred to post-closeout backlog |
| CR-3 | low | Replace the gate-wait proxy timestamp with a real gate-transition time | Architect | Deferred to the F0001 backlog |
| DEP-1 | low | Reclassify `doctor` outside a workspace from `SCHEMA_INVALID` exit 9 to a preflight error exit 3 (S9-F2) | Architect | Deferred to the F0001 backlog; pre-existing behaviour, not F0003 code |
| DEP-2 | medium | Decide whether the `event_type` enum extension is acceptable given a strict `1.0` reader rejects unknown values (S3-F1) | Architect | **Accepted and confirmed at G4** |

No recommendation carries blocking language against a passing verdict. The two high-severity
items were both resolved before this gate: SEC-1's defect in code, and both of its and
DEP-2's schema questions by explicit operator confirmation at G4.

## Waivers And Omissions

| Item | Kind | Detail |
|------|------|--------|
| DAST | Scan waiver | Not run. F0003 opens no network listener, port, or HTTP target — the architecture is a local CLI plus a stdio MCP child process (BLUEPRINT §5.8, ADR-005, ADR-007). Owner: Architect. Approved 2026-08-29 |
| DevOps signoff | Role omission | Not required. `deployment_config_changed: false`; no deployment topology change. Evidence produced regardless |

The manifest's `omissions` array is empty: nothing required was omitted. The DAST entry is
a recorded waiver with reason, owner, and approval date, not an omission.

## Independence Note

All four signatures are held by one person, which is the reality of a single-operator
local-runtime feature and is not concealed here. Two things partially offset it and are
worth a closeout reader knowing:

- The security review found and fixed a **high** finding in the implementer's own code
  (SEC-1), demonstrating the review was not a formality.
- Every structural guard in this feature was verified by **injecting the failure it exists
  to catch** — the layering rule, the query-facade surface, schema conformance in both
  directions, and the MCP handler invariant under `python -O`. A guard that has never been
  seen to fail is not evidence.

## Result

PASS

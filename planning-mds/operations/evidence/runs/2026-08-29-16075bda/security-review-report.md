# Security Review Report — F0003

**Run:** `2026-08-29-16075bda` · **Gate:** G3 · **Owner:** Security Reviewer · **Date:** 2026-08-29

## Scope Review

F0003's security surface is four claims made by the approved architecture: path
containment for evidence retrieval, redaction before persistence, a structurally
read-only MCP surface, and per-target-class authority over learning-proposal decisions.
Each was reviewed against the built code, not against the plan.

Trust boundary is unchanged from F0001: single host, OS identity, no network listener, no
credential storage.

## Findings

One high finding was raised and fixed during this review. It is recorded in full because
the defect and its fix are both instructive.

### SEC-1 (High) — `DecideProposal` trusted a caller-declared role · FIXED

`learn decide` took `--role` from the command line. `LearningService.decide` then compared
that **declared** role to the role the target document requires — and never asked whether
the actor held it.

Demonstrated before the fix: a `LocalOperator` who owned the run passed `--role architect`
and successfully accepted a proposal targeting
`planning-mds/architecture/SOLUTION-PATTERNS.md`.

That defeats the security model's central claim about this action:

> Owning the run does **not** confer the right to decide its proposals. A `LocalOperator`
> may draft; deciding requires the role that owns the target.

It is also the escalation path ADR-009's `DraftProposal`/`DecideProposal` split exists to
close, reopened from the other side: the split stops one capability covering both, but a
caller-supplied role made the second capability self-granting.

**Fix.** The reviewer role is now *derived* from the target document and *verified*
against the committed policy:

- `f0001-local-policy.schema.json` gains a `proposal_grants` object —
  `can_decide_architecture`, `can_decide_security`, `can_decide_planning` — deny by
  default, absent meaning all false.
- `AuthorizationService.decider_roles(subject)` reads it from the `0600` policy file
  inside a `0700` directory, returning the empty set for an unbound subject, an unreadable
  policy, or an absent block.
- `--role` is **removed**. A role the caller can name is a role the caller can claim.

Verified after the fix: an owning `LocalOperator` with no grant is refused (exit 5);
`--role` is rejected by the parser; a grant for one target class does not carry to
another. Three tests cover it, including the cross-class regression.

**This is a second additive change to an F0001 schema**, the same class as S3-F1. It is
unavoidable: `reviewer_grants` is closed and `bindings` knows only
`LocalOperator|Reviewer|System`, so expressing "this subject may decide architecture
proposals" requires new policy state. Recorded for the Architect alongside S3-F1.

## Path containment

| Property | Verified |
|----------|----------|
| Symlinks resolved **before** the containment check | Yes — a link inside an approved root pointing out of it is refused, not followed |
| Traversal escaping every approved root | Refused, `PATH_DENIED`, exit 5 |
| Traversal landing back inside an approved root | Allowed, correctly — containment is about where a path *resolves*, not whether it contains `..` |
| Refusal is a recorded policy violation, not a crash | Yes |

**Residual (accepted):** a TOCTOU window exists between resolution and read. Exploiting it
requires write access to the workspace, which is inside the local trust boundary F0001
established — an attacker with that access does not need this path.

## Redaction

Redaction runs on **bytes, before decoding**. A lossy decode first could split a
credential into halves no byte pattern matches, and the summary would carry the pieces.

An end-to-end sentinel sweep over every persisted runtime file — index, summaries,
proposals, capability reports, event stream — found no credential material. A
secret-bearing provider version string is stored redacted with the marker visible, never
dropped silently.

`redaction_status: Fail` forces `retrieval_policy: Blocked` by construction, and
`nebula_evidence_show` refuses content whenever redaction is not `Pass`.

## MCP surface

Read-only is structural at two levels, and both are asserted: the adapter holds only the
query facade (instance check), and the module cannot import a mutating application service
(import check). The instance check alone is insufficient — a handler could construct one
itself.

Every response is schema-conformant. Errors carry no stack traces and no paths outside an
approved root. Responses are paged. No authentication exists, correctly: it is a
host-spawned stdio child running as the invoking user, which is the F0001 trust boundary.

## Proposal target allowlist

Enforced at **generation**, so `learn decide` never evaluates an out-of-allowlist path.
Refuses absolute paths, traversal, and — checked specifically — `planning-mds/schemas/**`
and `.nebula-agents/runtime/policy.json`. A proposal able to name those would turn a review
suggestion into a route to the trust boundary.

## Scan results

Dependency **clean** (0 vulnerabilities across the 6-package runtime closure). Secrets
**clean** (7 candidates, all triaged: synthetic fixtures, their echoes in pytest
parametrize IDs, and manifest digests). SAST **0 high, 0 medium, 17 low** — all
pre-existing F0001 or false positives after the one real B101 was fixed at G2. DAST
**waived**: no listening port exists.

## Implementation Risks

- The `proposal_grants` mechanism is only as good as the policy file's integrity. It is
  `0600` inside `0700` and validated against its schema on every load, which is the same
  protection F0001's other grants rely on.
- Learning proposals remain inert: nothing in F0003 opens a target document. If that ever
  changes, `DecideProposal` becomes a write capability and this review does not cover it.

## Validation Evidence

732 tests green on 3.11/3.12/3.14. `tests/security/test_f0003_boundaries.py` (12 tests)
covers modes, containment, the sentinel sweep, and the allowlist.
`tests/integration/test_learning_proposals.py` covers the authorization fix including
cross-class isolation.

Scan artifacts:

- artifacts/security/dependency-audit.json
- artifacts/security/secrets-scan.json
- artifacts/security/bandit-sast.json

## Recommendations

- [high] Confirm `proposal_grants` as a second additive change to `f0001-local-policy.schema.json`; expressing per-target-class decision authority requires new policy state and no smaller fix exists (SEC-1) — owner: Architect; follow-up: decide at G4 with S3-F1
- [medium] Document the `proposal_grants` block in the authorization model so an operator knows deciding must be granted explicitly — owner: Architect; follow-up: before G8 closeout
- [low] Accept the resolve-to-read TOCTOU window as inside the local trust boundary — owner: Security Reviewer; follow-up: revisit only if F0003 ever runs under a different trust model

## Result

PASS WITH RECOMMENDATIONS

Critical: 0. High: 0 remaining — SEC-1 was found and fixed within this review cycle, with
regression tests. The three recommendations are routed, not resolved here.

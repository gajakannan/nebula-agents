# F0001 Security Review

Status: Completed
Date: 2026-07-13
Reviewer: Security Reviewer
Assessment: PASS WITH RECOMMENDATIONS
Feature: F0001 tmux-native agent cockpit
Evidence run: `2026-07-13-1cfbc5a0`

## Executive decision

F0001 is approved for its declared local CLI/TUI scope with Low hardening recommendations. No Critical, High, or Medium security issue remains open. The former gate-freshness High and four Medium authorization/disclosure/redaction issues were reproduced against the frozen source as fixed.

This decision assumes the documented single-host trust model: the owning OS UID is trusted for its own files, provider credentials remain provider-owned, and F0001 exposes no network listener. It is not an approval for a daemon, remote multi-user deployment, HTTP API, or hostile same-UID isolation.

## Scope and reviewed evidence

Manual review covered architecture, ADR-001 through ADR-004, PRD/stories, assembly plans, schemas, the local authorization model, runtime/application/presentation source, and security-focused tests. Specific boundaries reviewed were identity and policy resolution, reviewer projections, reconcile persistence, gate validator/evidence binding, filesystem containment, direct process execution, transcript redaction, failure handling, and audit output.

The F0001 run manifest records dependency, secrets, and SAST artifacts under `artifacts/security/`, plus a dated no-listener DAST waiver. The final QE baseline records 424 passing tests with zero failures, errors, skips, or xfails, 90.03% coverage, and one successful real tmux smoke test. An independent final focused security run completed 307 tests with no failure.

## Former finding verification

| Prior severity and issue | Frozen-source verification | Result |
|---|---|---|
| HIGH: approval trusted cached/latest validator evidence | `application/gates.py:93-112,176-188,211-255` binds gate ID, revision, semantic readiness, and evidence digest; `filesystem_store.py:306-339` revalidates under the commit lock. Deleted, mismatched, and concurrent-change regressions pass. | CLOSED |
| MEDIUM: hold reason could persist a secret | `domain/transitions.py:78-84` applies streaming redaction before terminal sanitation. Direct reproduction with a bearer sentinel returned only `[REDACTED]`. | CLOSED |
| MEDIUM: reviewer projection leaked paths/session/transcript guidance | `application/authorization.py:136-181` minimizes non-owner fields; TUI/formatters consume explicit capabilities. Projection and presentation regressions pass. | CLOSED |
| MEDIUM: reviewer `READ_STATE` could persist reconcile/evidence changes | Query/run services return non-owner observations in memory; repository revision remains unchanged in regression tests. | CLOSED |
| MEDIUM: duplicate/contradictory policy bindings enabled order-dependent roles | Policy loading rejects duplicate subjects; `infrastructure/identity.py:21-68` gives UID precedence and rejects conflicting effective roles. Identity/policy regressions pass. | CLOSED |
| MEDIUM: non-owner validator summary disclosed paths despite projection minimization | `application/authorization.py:151-157` replaces untrusted validator output with a stable generic summary. Path and bearer-sentinel regressions pass. | CLOSED |
| MEDIUM: evidence, prompt, feature, story, or validator paths could follow symlinks outside governed roots | Watcher, preflight, launch, and validator helpers now require canonical ancestry, reject symlink components/leaves, and use no-follow descriptor reads where content is consumed. External-root regressions pass. | CLOSED |
| MEDIUM: transcript completion could publish success before a worker failure became durable | `application/transcripts.py:121-181` waits for a bounded validated terminal status and commits `Failed` unless the worker reports `Completed`; delayed-success and post-disable failure regressions pass. | CLOSED |

## Ten-dimension review

| Review dimension | Result | Assessment |
|---|---|---|
| 1. Injection Resistance | PASS | Typed argv and `shell=False`; `shlex.join` only at intentional tmux shell-string boundaries; strict descriptor/path/schema/identifier checks. |
| 2. Authentication Robustness | PASS / limited applicability | OS UID is authoritative, display labels are not; provider login, token lifetime, MFA, and revocation remain provider-native. |
| 3. Access Control Correctness | PASS | Deny-by-default action policy, ownership, explicit reviewer grants, projection minimization, current-policy recheck, and commit-lock authorization. |
| 4. Sensitive Data Exposure | PASS WITH RECOMMENDATION | Owner-only storage, opt-in redact-before-write transcripts, bounded output, and hidden reviewer internals; finite pattern coverage is residual Low risk. |
| 5. Security Configuration | PASS | No listener, root bypass, remote policy, permissive CORS/cookie surface, or unsafe default; runtime and policy are private and schema-validated. |
| 6. Component Risk | PASS WITH RECOMMENDATION | Dependency audit is clean; dependency ranges are not a hash-locked release set. |
| 7. Observability and Auditability | PASS WITH RECOMMENDATION | Sequenced sanitized events cover protected actions and denials; same-UID tamper evidence is not cryptographic. |
| 8. Secrets and Key Management | PASS | F0001 reads/stores no provider credentials, forwards an environment allowlist, redacts credential-like output, and has a clean secrets scan. |
| 9. API Abuse and Resilience | PASS / limited applicability | No remote API or brute-force surface. Revision CAS, digest binding, idempotent transitions, timeouts, and size limits resist local replay/resource abuse. |
| 10. Error and Failure Safety | PASS | Policy/identity/redaction/storage failures deny or stop safely; stable errors avoid raw credentials/environments; transcript failure never falls back to raw writes. |

## OWASP and STRIDE disposition

All OWASP Top 10 (2021) categories are evaluated in `planning-mds/security/owasp-top-10-results.md`. A01, A03, A04, and A05 controls are fully applicable and pass. A02/A07 are limited by the provider/OS auth design, A10 is not applicable without URL fetching, and A06/A08/A09 carry only Low recommendations.

The threat model covers every STRIDE category. Spoofing and elevation are controlled by OS identity and unambiguous policy; tampering and replay by containment, digests, revisions, and commit-lock validation; repudiation by sequenced audit events; disclosure by projection/redaction; and denial of service by size, time, and buffer bounds.

## Scanner results and dispositions

| Scanner | Result | Disposition |
|---|---|---|
| `pip-audit` | exit 0; no known vulnerabilities | PASS |
| `detect-secrets 1.5.0` | exit 0; empty findings | PASS |
| `bandit 1.9.4` | 0 High, 0 Medium, 17 Low across 5,572 lines | REVIEWED/PASS |
| DAST | not run; no HTTP/listener target | APPROVED NOT-APPLICABLE WAIVER |

Bandit's Low findings are B110 best-effort audit/compensation handlers, B404 subprocess imports, B603 direct argv calls with `shell=False`, B101 an internal post-`Popen` invariant, and B606 validated `execvpe`. None provides a command-injection path or suppresses an authorization failure. The narrow exception handlers do not grant access and preserve the primary failure.

## Low recommendations

### L-01 Deterministic dependency release set

- Severity: Low
- Location: `engine/pyproject.toml:10-13`
- Risk: compatible version ranges let separate installs resolve different dependency builds after the reviewed audit.
- Remediation: generate a reviewed, hash-verified lock/constraints artifact for packaged or CI release environments and audit that exact set.
- Owner: DevOps
- Follow-up: deferred-no-followup

### L-02 Optional audit tamper evidence

- Severity: Low
- Location: `engine/src/nebula_agents/infrastructure/filesystem_store.py:209-223`
- Risk: an already-compromised process acting as the owning UID can rewrite its local JSONL event stream without cryptographic evidence.
- Remediation: if cross-process accountability becomes a requirement, add hash chaining, signed export, or an OS-protected external audit sink before expanding beyond the local trust model.
- Owner: Security Reviewer
- Follow-up: deferred-no-followup

### L-03 Redaction format maintenance

- Severity: Low
- Location: `engine/src/nebula_agents/domain/redaction.py:11-20`
- Risk: a novel credential syntax not represented by the finite patterns could appear in an opted-in transcript.
- Remediation: maintain provider-format and adversarial split-chunk regression cases, and continue to fail closed on redaction/capture errors.
- Owner: Security Reviewer
- Follow-up: deferred-no-followup

## Residual risk and release recommendation

The recommendations do not create a realistic privilege escalation or credential-disclosure path inside the approved local boundary. Current compensating controls are a clean dependency set, no intentional credential access, transcript opt-in, owner-only storage, fail-closed policy, bounded redaction, and commit-time gate freshness.

Release recommendation: PASS WITH RECOMMENDATIONS for F0001 local use. Re-review is mandatory if network exposure, remote users, stronger same-UID isolation, plugin downloads, or application-managed secrets enter scope.

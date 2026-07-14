---
template: security-review
version: 2.0
feature_id: F0001
run_id: 2026-07-14-b885d64c
review_cycle: 5
---

# Security Review Report — F0001 G3 remediation, cycle 5

## Result

**PASS WITH RECOMMENDATIONS**

Open findings: Critical 0; High 0; Medium 0; Low 5.

H-06 is closed. When the original `TranscriptEnabled` publication raises and the first authoritative recovery is unavailable, both direct enable and launch-with-transcript now terminate the immutable owning tmux session, strictly verify absence, and return bounded `STATE_IO`. Independent production-code probes observed durable `Disabled`, inactive capture, and no live session. If termination or its proof also fails, the operation is explicitly named `...-session-termination`, returns `STATE_IO`, and emits no hidden success or false terminal event. A separate already-stopped `TranscriptFailed` recovery-failure path preserves the live provider session.

No release-blocking security weakness remains in the reviewed source, documentation, tests, or evidence snapshot. Five Low hardening recommendations remain; none changes the final G3 disposition.

## Scope and Threat Boundary

- Feature: `F0001-tmux-native-agent-cockpit`; run `2026-07-14-b885d64c`.
- Review boundary: local Python CLI/TUI, filesystem run repository, native tmux/provider process, transcript capture/redaction, governed story discovery, authorization, audit, and failure reconciliation.
- Principal trust boundary: the owning OS UID. There is no HTTP listener, database, remote API, URL fetcher, application credential store, cookie/token session, or cross-UID daemon in this snapshot.
- Security invariants: protected operations are authorized at use time; untrusted values never become shell syntax; artifacts remain within descriptor-relative/no-follow boundaries; transcript capture requires consent; durable transcript facts conservatively reflect possible collection; failure paths never silently succeed.
- Adversary/fault model: a same-host caller without the required grant, malicious feature/story or descriptor content, symlink/path replacement, provider output containing secrets, repository failures before or after publication, unavailable/malformed tmux evidence, capture stop failure, and owning-session termination failure.

## H-06 Independent Fault Probes

The reviewer exercised production services with the real filesystem repository and independently supplied fault wrappers/fakes. The decisive observations were:

```text
direct-first-recovery STATE_IO transcript-enable-commit-recovery Disabled False False
launch-first-recovery STATE_IO launch-transcript-enable-commit-recovery Disabled False False
direct-termination-fail STATE_IO transcript-enable-commit-active-compensation-session-termination Disabled True True
launch-stopped-transcript-failed-recovery STATE_IO launch-transcript-failure-commit-recovery Disabled False True []
```

The last three columns are durable transcript state, capture activity, and owning/provider session presence; `[]` is the provider-session kill list in the already-stopped control.

- Direct enable: `TranscriptService._reconcile_pipe_after_commit_error` handles failure of its first authoritative recovery by using the immutable fallback run to terminate and verify the owning session (`engine/src/nebula_agents/application/transcripts.py:49-78,203-212`). Result: stable `STATE_IO`, durable `Disabled`, capture inactive, session absent, and only the prior `LaunchRequested`/`RunLaunched` events.
- Launch with transcript: the equivalent branch terminates and verifies the launched session before returning stable `STATE_IO` (`engine/src/nebula_agents/application/runs.py:606-630`). Result: durable `Disabled`, capture inactive, session absent, and no `TranscriptEnabled` event.
- Termination-failure control: termination failure plus a positive presence proof remains an explicit `...session-termination` `STATE_IO`. It does not return success, publish `Active`, or publish a false terminal fact. The caller and operation metadata therefore retain the unresolved state. This is the unavoidable compounded failure of persistence, stop/compensation, and the last-resort owned-session control, not the H-06 bypass.
- Already-stopped `TranscriptFailed` control: a configuration failure followed by successful capture stop, failure of the `TranscriptFailed` pre-publication commit, and unavailable recovery returns `launch-transcript-failure-commit-recovery`. The transcript remains inactive/`Disabled`, while the provider session remains present and its kill list stays empty. The new fail-safe is therefore scoped to possibly-live capture and does not destroy an unrelated provider session.

Committed regressions independently corroborate these properties at `engine/tests/integration/test_commit_reconciliation.py:701-771,928-1039`.

## Prior Finding Disposition

| Finding | Final disposition | Security basis |
|---|---|---|
| H-01 — launch publication ambiguity | Closed | Authoritative recovery prevents killing a session after recovered `Active` publication and preserves the durable/audit fact. |
| H-02 — descendant story-validator replacement | Closed | Descriptor-relative no-follow traversal plus bounded stable reads preserve the governed feature boundary. |
| H-03 — completion ambiguity can restart capture | Closed | Recovered terminal states do not restart the transcript pipe. |
| H-04R — compensating `Active` publication also fails | Closed | If capture cannot be proven stopped and truthful `Active` cannot be established, the owning session is terminated and absence strictly verified. |
| H-05 — tmux evidence errors reported as inactive/absent | Closed | Exact `1`/`0` responses are accepted; timeout, nonzero, malformed output, and probe exceptions fail explicitly. |
| H-06 — first recovery failure bypasses capture fail-safe | **Closed** | Direct and launch production-code probes now return stable `STATE_IO` with durable `Disabled`, inactive capture, and verified session absence. |

Strict H-01–H-05 reconfirmation produced no regression: double-pre-publication direct and launch failures terminate the owning session; fallback authorization denial remains audited and fail-safe; a second recovery failure is bounded; tmux active/inactive values map only from exact valid output; timeout, nonzero, and malformed values return `COMMAND_FAILED`; capture-status probe exceptions propagate rather than becoming terminal/inactive truth.

## Threat Model (STRIDE)

| Threat | Assessment |
|---|---|
| Spoofing | OS UID identity, run ownership, named grants, and lock-time authorization remain authoritative. No bearer-token or remote-auth surface exists. |
| Tampering | Schema validation, atomic repository publication, descriptor-relative/no-follow access, bounded stable reads, immutable session ownership, and strict transition checks constrain record, descriptor, story, and transcript manipulation. |
| Repudiation | Authorization decisions and lifecycle/transcript transitions are recorded with actor and bounded operation context. Same-UID filesystem tampering is a documented residual; cryptographic audit chaining remains Low L-02. |
| Information disclosure | Foreign-owner projections are minimized; runtime paths are owner-only; transcript consent, strict liveness proof, verified cleanup, terminal sidecars, and redaction controls prevent a hidden live capture state under ordinary or single-control failure. |
| Denial of service | Process output/time limits, bounded reads/retries, strict tmux errors, and stable `STATE_IO` avoid hangs and false success. A simultaneous repository/stop/session-termination failure can still require operator response and is explicitly observable. |
| Elevation of privilege | Authorization is enforced in application services; provider and tmux arguments are typed/validated; subprocesses use argv with `shell=False`; the one tmux shell seam is derived from a validated, quoted descriptor path. No escalation path was found. |

## Ten-Dimension Security Assessment

1. **Injection resistance — Pass.** Typed provider keys, validated run/session identifiers, descriptor validation, `shell=False`, argument vectors, and quoted tmux descriptor construction prevent command-text interpretation. No SQL/template/URL surface exists.
2. **Authentication robustness — Pass / not remotely applicable.** The authenticated principal is the local OS UID. There are no passwords, bearer tokens, cookies, MFA, or remote sessions in scope; tmux session identity is bounded and immutable per run.
3. **Access-control correctness — Pass.** Ownership/named grants and deny-by-default service authorization cover launch, attach, transcript configuration, status, and review actions. Fallback transcript compensation is separately authorized and denials are audited without preserving hidden collection.
4. **Sensitive-data exposure — Pass with Low hardening.** Owner-only runtime modes, minimized projections, opt-in transcript capture, failure-safe cleanup, and redaction protect provider output. Expanding the adversarial redaction corpus remains L-03.
5. **Security configuration — Pass / locally scoped.** No CORS, HTTP headers, or cookies apply. Safe environment allowlists, bounded command execution, strict filesystem modes, and absence of a listener are appropriate to the approved local architecture.
6. **Component risk — Pass with Low hardening.** The resolved 11-package environment reports no known vulnerabilities. A deterministic release lock/hash graph remains L-01.
7. **Observability and auditability — Pass with Low hardening.** Security denials, transcript transitions, compensation state, and bounded failure operations are recorded; unresolved cleanup is explicit rather than hidden. Tamper evidence and an operator alert/runbook for compounded cleanup failure remain L-02/L-05.
8. **Secrets and key management — Pass.** The expanded committed-content scan reports no secret; the application introduces no key store or hardcoded credential. Provider authentication stays external to the feature and environment propagation is allowlisted.
9. **API abuse and resilience — Pass.** There is no network API requiring throttling or brute-force controls. Revision checks, authorization-at-commit, idempotent reconciliation, strict state transitions, timeouts, bounded output, and verified cleanup address replay/race/failure abuse at the CLI boundary.
10. **Error and failure safety — Pass.** Repository ambiguity, tmux probe failure, stop failure, and first-recovery failure use stable bounded errors and conservative truth. The termination-failure control is an explicit error with no hidden success; the stopped-failure branch avoids an unsafe provider kill.

## OWASP Top 10 Mapping

- A01 Broken Access Control: no bypass found; ownership, named grants, use-time checks, and minimized projections are enforced.
- A02 Cryptographic Failures: no application secret or network cryptography is introduced; audit non-repudiation beyond the same-UID boundary remains L-02.
- A03 Injection: argv-based execution, validation, canonicalization, and the reviewed quoted tmux seam resist command injection.
- A04 Insecure Design: the external-capture/durable-state race is explicitly threat-modeled and H-01/H-03/H-04R/H-06 are closed by recovery plus verified cleanup.
- A05 Security Misconfiguration: local modes, environment allowlists, bounded errors, and no listener are appropriate; no web configuration applies.
- A06 Vulnerable and Outdated Components: resolved audit is clean; deterministic release locking remains recommended.
- A07 Identification and Authentication Failures: local OS identity is the approved mechanism; no remote credential flow exists.
- A08 Software and Data Integrity Failures: schema-validated atomic records and descriptor/story traversal controls pass; release/audit hash hardening remains recommended.
- A09 Security Logging and Monitoring Failures: denials and lifecycle/failure events are captured; alerting for the compounded session-termination residual remains L-05.
- A10 Server-Side Request Forgery: not applicable; no URL fetch or server-side request functionality exists.

## Verification and Evidence Integrity

- Official immutable evidence: 514/514 passed, zero failures/errors/skips/xfails; 4,189/4,620 lines (90.67%) and 1,197/1,472 branches (81.32%); mandatory authorization, transition, redaction, and session-entry risk modules meet 100% branch coverage.
- Independent focused lane: 149/149 passed across application services, tmux adapter, transcript adapter, and commit reconciliation.
- Independent full rerun: 513 non-host-tmux tests passed in the restricted sandbox; the sole real-tmux lifecycle test then passed against the permitted host tmux socket (1/1). This exactly accounts for 514 tests.
- Official JUnit SHA-256: `df160ca44d33a73feef73e9dc62c44cfc50898bd1bab3ece6abe0cc4320679a6`.
- Reviewed H06 source/test SHA-256: `runs.py` `15f35725537791b15db030ee6020226f4c0e9a083f50f4eb466c916086a7fba1`; `transcripts.py` `80d13f26a17eae2efbfd96d8df884f192cbe6c232235d14bd7dbeb72d4d27c0b`; reconciliation tests `9945bf4210cab2221f39d5186b85491f0a155634bfabb56f3358153face38323`.
- Synchronized design/security document SHA-256: ADR-004 `a3fb2dec77c5b0f590794aa5ebc2b8a6ed1876503a62ddc752eef23f91609794`; workflows `5af1217d6dc57070238db22f03aadb09f969d01b537c65070f46e3a3391bd387`; feature assembly plan `6dc6443fa41463b43e89aea5953da7bd15bde72428ec3ca0bd09a9aa5da46e32`; S0005 `f96abef8cc4868f43f56d829416e7bcd0df4f982a68b3c9b84207beae3da2c6d`; data protection `c444b066e53ef252b698df2f2ee1fd1aef490ccbaaec543b7ed14d60cb7880ab`.
- Evidence manifest SHA-256 remained `24c929adc4908fc8f653818401fa8948d9b1daee226826d85e26717afce88a44` during review.
- Archived Security cycles 1–4 remained immutable: `9ed763cd…c3b6f2`, `f41fb619…c1e57`, `a37d79bf…55a6`, and `a34d1723…06ff1` respectively.

## Scan Accountability

| Class | Result | Disposition |
|---|---|---|
| Dependency audit | Clean | 11 resolved packages; no known vulnerability or fix reported. Pytest is 9.1.1, beyond the vulnerable/fixed history previously reviewed. |
| Secrets scan | Clean | `detect-secrets` 1.5.0 expanded detector set; `results` is empty. |
| Bandit SAST | 13 Low, 0 Medium, 0 High across 7,199 LOC | Five B110 best-effort/reconciliation handlers, two B404 imports, two B603 bounded subprocess calls, one B101 internal postcondition, two transcript B110 cleanup handlers, and one B606 shell-free session process. Manual review found no exploitable flow; retain as accepted Low scanner signals. |
| DAST | Not run — no target | The Architect-owned waiver remains valid: this snapshot exposes no listener, HTTP endpoint/client, remote service, webhook, or URL-fetch surface. Any such future surface invalidates the waiver and requires DAST. |

Security artifact SHA-256 values: Bandit `7a39591751de590b4618d09939c9cfe5488c954d55a93500f124dcedbbce1f94`; dependency audit `8498dee8525ab7f7ca2090e1d7c8ad027e203d89955a29f70178a68377f856f6`; secrets scan `9fc0dbecfaca2a617631238ceef05847066b9ac694a24b4a304fb6d8704dd192`.

## Low Findings / Recommendations

| ID | Severity | Location | Recommendation |
|---|---|---|---|
| L-01 | Low | `engine/pyproject.toml`; release packaging | Produce a deterministic, hash-locked release dependency graph and verify it in release CI. Owner: Release Engineering; before first distributable release. |
| L-02 | Low | `engine/src/nebula_agents/infrastructure/filesystem_store.py`; `events.jsonl` | If non-repudiation must extend beyond the owning-UID boundary, add cryptographic event chaining or an independently controlled append-only sink. Owner: Architect/Security; before broad multi-user deployment. |
| L-03 | Low | transcript redaction tests and fixtures | Maintain a versioned adversarial corpus covering encoded, fragmented, multiline, Unicode, and newly observed credential formats. Owner: Security/Quality; ongoing, beginning next hardening iteration. |
| L-04 | Low | `engine/src/nebula_agents/infrastructure/story_validator.py` | Consider rejecting story files containing more than one governed feature link to strengthen provenance defense in depth. Owner: Product/Backend; backlog. |
| L-05 | Low | session-termination reconciliation operations in `runs.py`/`transcripts.py` | Alert on `*-session-termination` `STATE_IO` and document immediate operator verification/cleanup of the named immutable tmux session. Owner: Operations; before operational rollout. |

## Residual Risk and Gate Disposition

The principal residual is an intentionally visible compounded failure: repository publication/recovery, transcript stop or conservative compensation, and owning-session termination/absence proof can all fail together. The implementation cannot truthfully claim cleanup in that state, so it returns stable `STATE_IO` with `session-termination` operation context and no success/terminal event. Operational monitoring and runbook handling are recommended in L-05. Same-UID event tampering and imperfect heuristic redaction remain Low hardening concerns, not release blockers for the approved local trust model.

H-06 and all earlier High findings are closed. Dependency, secrets, authorization, audit/redaction/privacy, strict tmux evidence, and no-DAST-target assessments pass. The final Security Reviewer recommendation is **PASS WITH RECOMMENDATIONS** for G3.

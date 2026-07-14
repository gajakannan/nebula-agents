---
template: security-review
version: 2.0
feature_id: F0001
run_id: 2026-07-14-b885d64c
review_cycle: 4
---

# Security Review Report — F0001 G3 remediation, cycle 4 (archived)

## Result

**REQUEST CHANGES**

Open findings: Critical 0; High 1; Medium 0; Low 4.

H-04R's double-pre-publication failure paths and H-05's strict tmux pipe/session probes are closed. One adjacent first-recovery failure remains: after the original `TranscriptEnabled` commit raises, failure of the first authoritative repository recovery exits before any verified pipe stop, conservative `Active` publication, or owning-session termination. Direct enable and launch-with-transcript can therefore leave durable `Disabled` while the pipe and session remain live. H-06 is release blocking and keeps G3 at `REQUEST CHANGES`.

## Scope and Threat Boundary

- Feature: `F0001-tmux-native-agent-cockpit`
- Run: `2026-07-14-b885d64c`
- Review: independent Security cycle 4, limited to the final transcript failure-safety changes and refreshed G2 evidence
- Deployment: local Python CLI/TUI with native tmux/provider processes; no HTTP listener, database, daemon, remote API, URL fetcher, or application credential store
- Trust boundary: the owning OS UID; the feature still promises fail-closed authorization, transcript consent, lifecycle truth, and bounded audit behavior when repository or tmux operations fail

The review checked direct transcript enable, launch-with-transcript, original and compensating publication ambiguity, pipe disable/liveness proof, session termination/liveness proof, and error normalization. Prior cycle reports remain the finding ledger for H-01 through H-05.

## Independent Probes

The current H-04R remediation correctly handles both double-pre-publication shapes when authoritative recovery is available:

- original `TranscriptEnabled` commit fails before publication;
- pipe disable cannot be verified;
- compensating conservative `Active` publication also fails before publication;
- the owning tmux session is terminated and absence is strictly verified before control returns.

The H-05 controls also distinguish exact inactive/absent results from unavailable evidence. Timeout, nonzero, and malformed tmux pipe/session responses no longer become false inactive proofs.

The remaining cycle-4 probe faults the *first* authoritative recovery immediately after the original `TranscriptEnabled` commit error. In both direct and launch paths, execution leaves before stop/compensation/session-termination controls run:

```text
original TranscriptEnabled commit: error
first authoritative recovery: error
durable transcript: Disabled
pipe active: True
tmux session live: True
```

The launch path also leaks the raw repository `OSError` rather than returning the stable application `STATE_IO` contract. This is not merely an error-shaping issue: the early exit preserves live collection behind a non-active durable consent fact.

The narrower compounded case where persistence, pipe disable, and owning-session termination all fail is explicitly surfaced as `STATE_IO`; it is not hidden success and does not publish a false terminal transcript fact. That multi-control residual should remain visible in operations and regression coverage. It does not mitigate H-06, whose earlier recovery exception bypasses those controls entirely.

## Evidence Reviewed

- Full suite: 510 passed; zero failures, errors, skips, or xfails.
- Coverage: 4,176/4,607 lines (90.64%) and 1,191/1,464 branches (81.35%).
- Mandatory authorization, transition, redaction, and session-entry risk modules: 100% branch coverage.
- Resolved dependency audit: clean; no known vulnerable dependency reported.
- Expanded secrets scan: clean; no detected committed secret.
- Bandit SAST: 13 Low, 0 Medium, 0 High across 7,159 LOC.
- DAST: not run; no deployable listener, HTTP route/client, remote target, or URL-fetch surface was present, so the existing no-target waiver remains applicable.

Passing tests and aggregate coverage do not close H-06 because the independently reproduced first-recovery fault is not covered by the successful failure matrix.

## Prior Finding Disposition

| Finding | Cycle-4 disposition | Basis |
|---|---|---|
| H-01 — launch publication ambiguity | Closed | Authoritative reconciliation prevents killing a session after recovered `Active` publication and preserves terminal audit truth. |
| H-02 — descendant story-validator replacement | Closed | Descriptor-relative no-follow traversal and stable bounded reads preserve the governed feature boundary. |
| H-03 — completion ambiguity can restart capture | Closed | Recovered terminal states never restart the transcript pipe. |
| H-04R — compensating `Active` also fails before publication | Closed for reviewed double-pre-publication paths | Verified owning-session termination supplies the fail-safe when truthful `Active` cannot be persisted. |
| H-05 — tmux probe errors reported as inactive | Closed | Pipe/session probes accept only strict active/inactive or present/absent output; timeout, nonzero, and malformed output fail explicitly. |
| H-06 — first authoritative recovery failure bypasses transcript fail-safe | **Open — High** | Direct and launch probes retain durable `Disabled` with live capture/session; launch also leaks raw `OSError`. |

## Finding

### High — H-06: first authoritative recovery failure bypasses every capture fail-safe

After an original `TranscriptEnabled` commit error, the service first attempts to determine whether the write published. If this authoritative recovery raises, the direct and launch paths exit before invoking verified pipe shutdown, persisting a conservative `Active` fact, or terminating and verifying absence of the owning tmux session.

Impact: transcript collection can continue while durable state and the audit stream still say `Disabled`. Operators and later lifecycle consumers have no conservative active-capture fact, and launch callers receive an unbounded infrastructure exception. This violates transcript consent, sensitive-output minimization, audit truth, and the fail-closed terminal-state invariant.

Required closure:

1. Treat the first recovery attempt as fallible input to the same fail-safe state machine, not as an early-return prerequisite.
2. If publication cannot be authoritatively resolved, attempt bounded pipe disable and strict inactivity proof; if that cannot be proven, terminate the owned session and strictly verify absence.
3. Never publish or retain a non-active transcript fact while capture may continue. If all independent controls fail, return stable `STATE_IO` with bounded operation metadata and no false success/terminal event.
4. Normalize repository recovery exceptions, including launch, to the stable application error contract.
5. Add direct enable and launch-with-transcript regression cases for first-recovery failure, including stop success, stop failure plus verified session termination, session-probe failure, and the existing multi-control failure residual.

Owner: Backend Developer. Release blocking.

## Security and Audit Disposition

Authentication and authorization remain deny by default: OS identity, ownership, named grants, lock-time authorization, and minimized foreign-owner projections were not bypassed. Provider launch remains typed, bounded, and `shell=False`; descriptor and validator boundaries remain intact. No new injection, elevation-of-privilege, or committed-secret issue was found.

H-06 is instead a consent, data-exposure, integrity, and auditability failure. A live transcript pipe behind durable `Disabled` may continue collecting provider output, and the event stream omits the fact necessary for operators and recovery consumers to reason safely. A raised raw exception does not compensate for that hidden live state.

Four non-blocking Low hardening recommendations remain unchanged:

- produce a deterministic hash-locked release dependency graph;
- add cryptographic chaining or an append-only sink if audit non-repudiation must extend beyond the owning-UID boundary;
- maintain a versioned adversarial transcript-redaction corpus;
- consider rejecting multi-link story files for stronger provenance defense in depth.

## Scan Accountability

| Class | Result | Disposition |
|---|---|---|
| Dependency | Clean | No known vulnerability in the resolved environment. |
| Secrets | Clean | Expanded scan found no committed secret. |
| SAST | 13 Low, 0 Medium, 0 High; 7,159 LOC | Scanner findings remain accepted bounded subprocess/best-effort-audit patterns; manual review found H-06. |
| DAST | No target | Existing waiver remains valid for this local snapshot; any future listener, remote service, webhook, URL fetcher, or cross-UID daemon invalidates it. |

## Gate Disposition

G3 Security cannot pass while H-06 is open. Remediate the first-authoritative-recovery exception path, refresh the official JUnit/Cobertura and security artifacts, and obtain another independent Code and Security review. Until then, the only valid verdict is **REQUEST CHANGES**.

# ADR-004: Transcript Capture Is Opt-In and Redacts Before First Write

## Status

- [ ] Proposed
- [x] Accepted
- [ ] Superseded
- [ ] Rejected

**Accepted:** 2026-07-13T21:39:29-04:00 by explicit operator approval.

## Context

Native terminal output can contain source code, filesystem paths, account identifiers, tokens, or other sensitive data. F0001 needs recovery and review artifacts but must not create an unredacted copy and attempt cleanup afterward. Ordinary transcript failure must not make the native tmux session unavailable; an unresolvable mismatch between durable consent state and possibly-live capture must favor stopping the owning session.

## Decision Drivers

- No raw secret-bearing transcript at rest.
- Recovery context remains available when explicitly requested.
- Redaction handles secrets split across stream chunks.
- Capture and attach failure domains remain independent except for the last-resort privacy compensation required when capture cannot be stopped or recorded truthfully.
- Review rendering is bounded and sanitized.

## Decision

Transcript capture defaults to `Disabled` for each run and requires an explicit authorized enable action. Tmux pane output is sent to a dedicated transcript-filter process. The filter holds a bounded overlap window, applies the shared secret-pattern policy before any append, and writes only owner-only redacted bytes.

If redaction initialization or streaming fails, the filter closes the output, capture moves to `Failed`, and no unredacted fallback is written. Attach remains available whenever capture inactivity is verified or durable state truthfully remains `Active`. Preview reads a bounded number of redacted bytes/lines and never opens an unredacted source. Disable or clean session exit moves capture to `Completed`. If disabling capture is unverified and the compensating `Active` fact cannot be published or recovered, the application terminates the recorded tmux session and positively verifies absence before surfacing `STATE_IO`.

## Options Considered

1. **Opt-in, redact-before-write stream:** Selected.
2. **Capture raw then post-process:** Rejected; creates a secret-bearing artifact even when cleanup succeeds.
3. **Capture enabled by default:** Rejected for MVP because operators may not expect terminal persistence.
4. **No transcript:** Rejected; fails recovery and review requirements.
5. **Periodic tmux screen snapshots:** Rejected as primary capture; loses chronology and complicates deduplication.

## Pros / Cons

**Redact-before-write**
- Pro: strongest local evidence boundary.
- Pro: ordinary capture failure does not terminate the session; the narrow compound-failure fallback prevents hidden capture.
- Pro: same sanitized artifact supports review and recovery.
- Con: imperfect redaction remains a residual risk.
- Con: streaming overlap and terminal escape handling require focused tests.

## Consequences

- Redaction policy changes are security-sensitive and require Security Reviewer signoff.
- Tests must include secrets split across arbitrary chunk boundaries and terminal control sequences.
- Transcript status must distinguish `Disabled`, `Active`, `Failed`, and `Completed`.
- F0003 summarization may consume only the redacted artifact and must retain provenance to it.

## Security & Compliance Notes

- Transcript files use mode `0600` under an approved runtime/evidence directory.
- Error messages contain categories/counts, not matching secret text.
- A failed redaction status blocks preview and evidence publication.

## References

- [F0001-S0005](../../features/F0001-tmux-native-agent-cockpit/F0001-S0005-native-session-transcript-and-recovery.md)
- [Solution patterns](../SOLUTION-PATTERNS.md)
- [Security authorization model](../../security/f0001-authorization-model.md)

## Follow-up Actions

- [ ] At feature G0, define the stream framing, overlap bound, and shared pattern loader.
- [ ] Require failure-injection and no-raw-sentinel tests.
- [x] Accepted through the Phase B operator approval gate.

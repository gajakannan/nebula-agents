# Nebula Agents Solution Patterns

## Metadata

- Project: Nebula Agents local runtime
- Version: 1.0
- Last Updated: 2026-07-13
- Owners: Architect; Security co-signs authorization and transcript changes
- Scope: F0001 local cockpit and the F0001 -> F0003 -> F0002 runtime line

`MUST` is mandatory, `SHOULD` requires a documented exception, and `MAY` is optional.

## 1. Local Modular Process

**Scope:** Hybrid — Python local CLI/TUI.

- The runtime MUST be one local process with Presentation, Application, Domain, and Infrastructure Adapter modules.
- Dependencies MUST point inward. The domain MUST NOT import terminal, subprocess, filesystem, tmux, or provider libraries.
- Provider, tmux, filesystem, watcher, clock, and OS identity behavior MUST sit behind ports owned by the Application layer.
- F0001 MUST NOT add an HTTP daemon, remote transport, database, MCP server, or managed-provider SDK.

Rationale: a local modular process preserves the native terminal trust boundary while keeping adapters replaceable for F0002.

## 2. Authorization

**Scope:** Hybrid — default-deny ABAC semantics with local OS identity.

- Every mutation MUST evaluate `subject`, `resource`, and `action` attributes at the application boundary.
- Subjects use OS user/group identity plus configured role; display labels are non-authoritative.
- `LocalOperator` MAY mutate owned runs. `Reviewer` is read-only except for explicitly granted validator, attach, hold, or approve actions.
- Unknown role, missing policy, policy parse error, or identity lookup failure MUST deny mutation.
- Authorization decisions for mutations and all denials MUST append a sanitized runtime event.

The tuple shape is compatible with a future Casbin adapter, but F0001 does not require a policy server or database.

## 3. Audit and Timeline

**Scope:** Universal.

- Every successful state mutation and every blocked/denied mutation MUST append a `RuntimeEvent`.
- Events MUST have a per-run monotonic sequence, UTC timestamp, actor identity, event type, and sanitized payload.
- Events MUST be append-only JSONL. No application method may update or delete an existing event.
- The current snapshot MAY cache the latest validator/gate state, but it MUST NOT replace event history.

## 4. Public Interface and Error Contract

**Scope:** Hybrid — versioned CLI and JSON; no HTTP API in F0001.

- CLI input MUST use parsed arguments and explicit commands; arbitrary command strings are forbidden.
- Machine output MUST include `contract_version` and conform to the schemas in `planning-mds/schemas/`.
- Human tables and the TUI MUST be projections of the same application response records.
- Errors MUST include a stable code, user-safe message, remediation category, and documented exit-code class.
- Provider-specific flags MUST NOT leak into the common CLI contract.

## 5. Runtime Persistence

**Scope:** Stack-Specific — owner-only local JSON/JSONL files.

- Current run state MUST be an atomic JSON snapshot with a monotonic `revision` and `created_at`/`updated_at` audit fields.
- Mutation MUST hold a per-run lock, verify expected revision when supplied, write a same-directory temporary file, flush and `fsync`, then atomically replace.
- A corrupt snapshot MUST be preserved, not overwritten. Recovery uses the last valid snapshot and event stream.
- Runtime directories MUST default to `0700`; state, policy, launch-descriptor, and transcript files MUST default to `0600`.
- Paths MUST be validated using canonical resolved ancestry. String-prefix containment is forbidden.
- F0001 has no soft delete. Record deletion/retention automation is out of scope.

## 6. Workflow

**Scope:** Universal.

- Session, gate, and transcript workflows MUST use explicit enumerated states and transition tables.
- Unknown state MUST fail closed and require reconciliation.
- Gate approvals MUST require current evidence and validator eligibility plus explicit authorized user action.
- Gate decisions and audit events are immutable; later results create new events rather than rewriting history.
- Idempotent repeats SHOULD return the existing result; conflicting duplicate identities MUST fail with `CONFLICT`.

## 7. Provider and Process Execution

**Scope:** Stack-Specific — native Codex/Claude CLIs inside tmux.

- Provider adapters MUST return validated argv arrays and capability/readiness results.
- Application code MUST NOT invoke `shell=True` or concatenate user input into a command.
- Because tmux accepts a shell command, the only allowed shell seam is a constant session-entry helper plus a validated descriptor path; the helper revalidates the descriptor and calls `execvpe` with argv.
- Launch descriptors MUST be owner-only, schema-validated, and deleted when no longer required.
- Attach MUST target the existing tmux session and MUST NOT start a provider process.
- Provider authentication remains provider-owned. F0001 MUST NOT read credential files or environment secret values.

## 8. Transcript and Secret Handling

**Scope:** Hybrid.

- Transcript capture MUST default to disabled and require explicit enablement per run.
- Output MUST pass through a streaming redaction filter before the first disk write. Redaction failure MUST stop writes.
- Raw transcript content MUST NOT be retained as a fallback artifact.
- TUI preview MUST be bounded by bytes and lines and MUST render only redacted content.
- Command templates, audit payloads, validator summaries, and errors MUST use the same secret-pattern policy.

## 9. Watchers and Caching

**Scope:** Stack-Specific — local polling baseline.

- The portable MVP watcher SHOULD poll every 500 ms and debounce duplicate changes; a native-notification adapter MAY replace it.
- Watchers MUST treat missing, moved, malformed, and unreadable artifacts as explicit observations rather than process failures.
- An in-memory read projection MAY cache snapshots and observations, but mutation guards MUST re-read the current revision and re-probe volatile tmux/gate conditions.
- No external cache is used.

## 10. Testing and Verification

**Scope:** Universal.

- Unit tests MUST cover state transitions, authorization policy, schema validation, path containment, redaction across chunk boundaries, argv construction, and exit-code mapping.
- Integration tests MUST use real tmux when available and deterministic fake provider executables; they MUST prove launch, detach, attach reuse, exit reconciliation, transcript failure isolation, and restart recovery.
- Contract tests MUST validate every JSON example against its schema and confirm human and JSON output derive from the same records.
- Security tests MUST prove no credential contents or unredacted sentinel values reach snapshots, events, command logs, errors, or transcripts.

## 11. Terminal UI

**Scope:** Stack-Specific — POSIX terminal UI.

- The TUI MUST be keyboard-operable, handle terminal resize without losing state, and pair color with text/symbol status.
- The narrow target is 80x24. Rendering MUST remain a pure projection and cannot authorize or persist directly.
- Provider UI stays inside the attached tmux session; Nebula MUST NOT screen-scrape it to infer approval or lifecycle state.

## Pattern Update Process

1. Propose a change in an ADR or feature architecture review.
2. Review runtime, security, testing, and F0002/F0003 compatibility impact.
3. Update this file and its consuming contracts together.
4. Run plan or feature validation before implementation continues.

## Change Log

- 2026-07-13: Initial project-specific pattern set for F0001 Phase B.

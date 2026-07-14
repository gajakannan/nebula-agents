# F0001 Threat Model

Status: Reviewed
Date: 2026-07-13
Scope: F0001 tmux-native agent cockpit

## System and deployment scope

F0001 is a single-host Python CLI/TUI for starting and governing native Codex or Claude Code processes inside tmux. It has no HTTP listener, database, remote identity provider, cookie, or application-managed credential store. The local OS account is the authentication boundary; provider authentication remains inside the provider CLI.

Security-relevant components are the CLI/TUI, application authorization and lifecycle services, the owner-only runtime store, allowlisted process/tmux adapters, the transcript filter, local policy, evidence watcher, and schema-validated planning artifacts. The architecture sources are `planning-mds/architecture/c4-context.md`, `c4-container.md`, ADR-001 through ADR-004, and the F0001 assembly plan.

## Assets, actors, and entry points

| Kind | Items | Security objective |
|---|---|---|
| Assets | provider session, prompt contract, runtime snapshot, gate state, evidence, policy, event stream, transcript | confidentiality, integrity, availability |
| LocalOperator | owning OS UID that launches and mutates a run | authorized lifecycle control |
| Reviewer | OS identity with read and validator access plus optional named grants | least-privilege review |
| System | internal recovery/reconciliation actor | bounded automated transitions |
| External processes | tmux, provider executable, validators | direct-argv execution of allowlisted operations |
| Entry points | CLI arguments, TUI keys, policy JSON, run descriptor, evidence files, provider output, transcript bytes | validate, contain, authorize, and bound |

Provider output and evidence are untrusted data. A reviewer display label is presentation metadata, never identity. A process already running as the owning UID is inside the accepted local trust boundary and can access that user's files; it is not treated as an isolated tenant.

## Trust boundaries and data flows

1. The caller crosses the presentation boundary through schema-shaped CLI/TUI input; application services resolve the current OS identity and enforce policy.
2. Launch crosses the process boundary through a private, validated run descriptor. The session entry point revalidates ownership, containment, file type, mode, executable, argv, cwd, environment allowlist, and freshness before `execvpe`.
3. Runtime mutations cross the persistence boundary under a per-run lock with revision checks, immutable identity checks, atomic snapshot publication, and an append-only JSONL event.
4. Gate approval crosses the evidence boundary only after contained no-follow reads, stable metadata checks, semantic readiness, a digest, and a validator result bound to the gate and current revision. The final check runs under the same repository lock as commit.
5. Optional transcript data crosses from tmux to durable storage only through streaming redaction. Files are contained under the run, opened without symlink following, and owner-only.
6. Read views cross the reviewer boundary through an authorized projection that removes workspace, prompt, evidence, audit, tmux, validator-artifact, and transcript details unless the corresponding grant exists.

## STRIDE analysis

| Category | Concrete threat | Implemented control | Residual assessment |
|---|---|---|---|
| Spoofing | A display label or ambiguous UID/group bindings impersonate an operator. | Identity comes from `getuid`; labels are non-authoritative; exact UID takes precedence; duplicate bindings are rejected and conflicting roles fail closed. | Low within the same-UID trust boundary. |
| Tampering | Evidence changes after validation, a stale approval is replayed, or a symlink redirects a sensitive file. | Evidence digest is bound to gate ID and revision and rechecked under the commit lock; canonical containment, `O_NOFOLLOW`, stable `fstat`, CAS, and schema checks reject changes. | Same-UID filesystem tampering remains detectable by validation but is not cryptographically prevented. |
| Repudiation | A caller denies a gate, launch, transcript, or authorization action. | Sequenced runtime events record actor UID, correlation context, event type, and sanitized metadata; denied mutations are also audited when a run exists. | JSONL is append-only by application convention, not cryptographically tamper-evident against the owning UID. |
| Information disclosure | Reviewer output exposes internal paths/session names, or provider output persists a credential. | Least-privilege projections and capability-gated UI hide internal guidance; bounded streaming redaction precedes transcript writes and process output capture; owner-only permissions protect runtime files. | Pattern-based redaction cannot prove recognition of every future credential format. |
| Denial of service | Oversized evidence/output, an unclosed private-key block, or a hanging validator consumes resources. | Evidence file size caps, bounded capture, terminal truncation, bounded private-key redactor state, validator timeouts, and lock timeouts constrain work. | A process running as the owning UID can still exhaust host resources outside this application's boundary. |
| Elevation of privilege | Reviewer read paths persist mutations, optional grants broaden unrelated actions, or policy order elevates a role. | Default-deny action checks, named grants, owner/resource checks, read-only reviewer reconciliation, reauthorization under the commit lock, duplicate rejection, and conflict-deny role resolution prevent elevation. | Local OS account compromise grants that account's accepted authority. |

## Abuse cases and security invariants

- Shell metacharacters in names, paths, prompts, or evidence must remain inert data. Commands use typed argv; the two tmux shell-string boundaries are constructed with `shlex.join` from validated argv.
- A successful validator from an earlier gate, revision, or evidence digest must never approve a current gate.
- `READ_STATE` must not be a mutation capability. Reviewer refresh, reconcile, and evidence observation return a projection without committing state.
- Transcript redaction failure must stop durable disclosure rather than fall back to raw bytes.
- Policy load, initialization, or identity ambiguity must deny protected operations.
- Files leaving the run or workspace containment boundary, including symlinks, must be denied.

## Residual risk and disposition

No Critical, High, or Medium threat remains open. Accepted MVP risk is concentrated in the declared single-user OS boundary, the non-cryptographic local event log, and finite redaction signatures. These are documented as Low recommendations in the dated review.

Threat-model result: PASS WITH RECOMMENDATIONS.

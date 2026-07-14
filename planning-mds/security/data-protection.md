# F0001 Data Protection Review

Status: Reviewed
Date: 2026-07-13
Assessment: PASS WITH RECOMMENDATIONS

## Data classification

| Data | Classification | Persistence |
|---|---|---|
| Run IDs, feature/story IDs, lifecycle status | Internal | owner-only run snapshot and event stream |
| Workspace, evidence, audit, and transcript paths | Sensitive internal metadata | owner view only; removed from default reviewer projection |
| Prompts and provider terminal output | Potentially sensitive | prompt contract in owner-only runtime; output durable only when redacted capture is opted in |
| Gate reasons and validator summaries | Potentially sensitive | redacted and terminal-sanitized before state/audit use |
| Provider credentials and tokens | Secret | not read or stored by F0001 |
| Policy bindings and owner UID | Security-sensitive | owner-only local policy/runtime state |

## Storage and filesystem controls

Runtime directories are created owner-only and sensitive files use mode `0600`. State publication is atomic and guarded by a per-run lock and revision checks. Sensitive readers canonicalize paths, require containment, reject symlinks with `O_NOFOLLOW` where supported, require regular files owned by the current UID, and bound file size.

F0001 provides no application-layer encryption at rest. This is intentional for the declared single-host, single-OS-account boundary; host filesystem encryption and account controls remain deployment responsibilities. No database, object store, browser cache, or network transport is introduced.

## Data minimization and disclosure controls

Reviewer responses use `RunProjection`, not the raw runtime record. Internal workspace, evidence, prompt, audit, tmux, validator-artifact, and transcript details are withheld unless ownership or the corresponding action grant requires them.

Errors use stable categories and recovery guidance without raw environments, credentials, captured output, or unsafe paths. Process output and terminal text are size- and line-bounded before display. TUI controls are capability-aware so denied operations do not leak actionable session guidance.

## Transcript and output protection

Transcript capture is disabled by default and requires authorization plus confirmation. When enabled, tmux pipes bytes to a dedicated filter that applies streaming credential redaction before the first durable write. The filter recognizes bearer/API tokens, common provider tokens, AWS access-key identifiers, credential assignments, database URLs, and private-key blocks.

Private-key content is never emitted after a begin marker; the filter retains only enough bytes to recognize a split end marker, preventing unbounded buffering. Transcript targets must be the contained owner-only regular file for the run. A source, redaction, open, permission, or write failure terminates capture safely and does not fall back to raw storage. A timeout/error/malformed liveness probe is not evidence of inactivity. If possibly-live capture cannot be stopped and a truthful durable `Active` fact cannot be established, the application terminates the owning tmux session and verifies absence before returning a stable state-I/O error.

Preview is available only for a safely completed transcript, revalidates containment and permissions, and returns bounded sanitized content. Reviewer path/preview access is withheld without the transcript grant.

## Integrity, retention, and recovery

Snapshots carry monotonic revisions and event sequences. Immutable run identity, canonical audit location, and event/run correspondence are checked on commit. Recovery selects schema-valid contained snapshots and rejects corrupt identity.

The application does not implement remote backup or centralized retention. Local run artifacts and optional transcripts remain under the owning account until that account follows workspace retention policy. Deletion/archival automation is outside F0001 and must preserve evidence obligations.

## Residual risk and result

Pattern-based redaction is defense in depth, not a proof that every novel secret syntax is recognized. The strongest controls are avoiding credential access, disabling capture by default, owner-only storage, and fail-closed capture. Same-UID processes remain within the accepted trust boundary.

Data-protection result: PASS WITH RECOMMENDATIONS.

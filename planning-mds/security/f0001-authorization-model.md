# F0001 Local Authorization Model

## Trust Boundary

F0001 is a single-host tool. Authentication is the local OS identity of the process invoking `nebula-agents`; provider authentication is separate and remains inside Codex or Claude Code. A username or reviewer label entered in the TUI is never an authentication credential.

## Policy Request

```text
authorize(subject, resource, action, context) -> Allow | Deny
```

| Attribute class | Fields |
|-----------------|--------|
| Subject | OS UID, resolved username, group IDs, configured role, optional display label |
| Resource | run ID, owner UID, workspace root, session state, gate state, evidence eligibility, transcript state |
| Action | `Probe`, `Launch`, `Attach`, `ReadState`, `RunValidator`, `DecideGate`, `ConfigureTranscript` |
| Context | decision kind, validator key, expected revision, runtime path, correlation ID |

Default is deny. Policy or identity errors deny mutations and emit a sanitized `AuthorizationDenied` event when a run context exists.

## Roles and Grants

| Action | LocalOperator on owned run | Reviewer default | Optional reviewer grant |
|--------|----------------------------|------------------|-------------------------|
| Probe | Allow | Allow | Not needed |
| Launch | Allow | Deny | `reviewer_can_launch` (off by default) |
| ReadState | Allow | Allow | Not needed |
| Attach | Allow | Deny; guidance hidden | `reviewer_can_attach` |
| RunValidator | Allow for allowlisted validator | Allow for allowlisted validator | Not needed |
| DecideGate: Hold | Allow | Deny | `reviewer_can_hold` |
| DecideGate: Approve | Allow only when gate eligible | Deny | `reviewer_can_approve` plus eligibility |
| ConfigureTranscript | Allow | Deny | `reviewer_can_configure_transcript` |

The run creator's OS UID becomes `owner_uid`. Root/sudo does not receive an application-level bypass; any override must be an explicit policy grant and remains audited.

## Enforcement Points

1. Presentation validates shape only and passes the caller identity context.
2. Application reloads the current record and policy under the run lock.
3. Authorization evaluates subject/resource/action attributes.
4. Domain guards evaluate lifecycle, evidence, and revision invariants.
5. Infrastructure executes the approved side effect.
6. The result and sanitized authorization metadata are appended to the event stream.

The TUI is not an enforcement point. Hiding a control is usability only; every application mutation rechecks policy.

## Local Policy Storage

- Path: `.nebula-agents/runtime/policy.json` unless runtime root is overridden.
- Mode: `0600`; parent mode `0700`.
- Schema: `planning-mds/schemas/f0001-local-policy.schema.json`.
- Writes: locked, validated, and atomic.
- No dynamic role downloads or remote identity provider in F0001.

## Provider Credentials

- F0001 may resolve the provider executable and invoke version/help or documented login-status commands.
- It must not read `~/.codex/auth.json`, OS credential stores, Claude credential files, API-key environment values, or shell history.
- Provider login prompts remain inside the native provider CLI in tmux.
- Runtime snapshots store only a readiness category such as `ready` or `authentication_attention_needed`.

## Transcript and Evidence Visibility

- Full local paths, tmux session names, and transcript artifacts are internal-only.
- Reviewer output is sanitized; attach guidance and transcript path are withheld unless policy grants those actions.
- Redaction occurs before transcript display or write. A failed redaction status blocks display.
- Authorization and validator logs use stable keys and redacted summaries, never raw command environments.

## Required Tests

- Default deny for unknown role/action and malformed policy.
- Owner/operator allow for each intended mutation.
- Reviewer read and validator allow; launch, attach, approve, and transcript denial by default.
- Optional grants enable only their named action.
- Stale revision and ineligible gate still fail after authorization allows the subject.
- TUI control visibility cannot bypass application enforcement.
- Provider credential fixtures and redaction sentinels never appear in outputs or runtime files.

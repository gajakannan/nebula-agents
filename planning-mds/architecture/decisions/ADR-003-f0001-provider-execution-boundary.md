# ADR-003: Provider Execution Uses Typed Adapters and an Isolated Tmux Entry Helper

## Status

- [ ] Proposed
- [x] Accepted
- [ ] Superseded
- [ ] Rejected

**Accepted:** 2026-07-13T21:39:29-04:00 by explicit operator approval.

## Context

Codex and Claude Code have provider-specific interactive invocation and readiness behavior. Tmux creates sessions from a shell-command boundary, while F0001 accepts feature IDs, prompt selections, paths, and labels from users. Concatenating those values into shell text would create quoting, injection, portability, and redaction problems. Hard-coding provider flags in the application layer would also make CLI changes expensive and leak provider details into common state.

## Decision Drivers

- No arbitrary shell execution from user or policy input.
- Provider-specific change isolation.
- Exact one-provider-process-per-run behavior.
- Existing provider authentication and UI remain untouched.
- Commands and audit records remain sanitized and testable.

## Decision

Application code depends on `ProviderAdapter`, `TmuxPort`, and `ProcessRunner` interfaces. A provider adapter returns a validated argv tuple and non-secret readiness result. The common application layer never branches on provider flags.

Tmux receives only a constant `nebula-agents session-entry --descriptor <validated-path>` command. The descriptor is owner-only, schema-validated, and contained under the run directory. Inside the pane, `session-entry` revalidates it, changes to the canonical workspace, constructs an allowlisted environment, and uses `os.execvpe` with the provider argv. No user text is concatenated into the tmux command.

Attach resolves the recorded tmux session and calls the tmux client; it cannot invoke a provider adapter. Preflight may run executable discovery, version/help, and documented non-secret login-status probes. It never reads credential files, environment secret values, or starts a model turn.

## Options Considered

1. **Typed adapters + entry helper:** Selected.
2. **Direct shell command string passed to tmux:** Rejected due to injection and quoting risk.
3. **Send keystrokes into a blank pane:** Rejected; UI timing, escaping, and screen-state dependent.
4. **Managed provider API:** Rejected for F0001 and owned by F0002.

## Pros / Cons

**Entry helper**
- Pro: shell seam is constant and narrow.
- Pro: prompt and provider flags remain typed through application code.
- Pro: adapter tests can snapshot argv without running providers.
- Con: requires transient descriptor lifecycle and an extra executable subcommand.
- Con: prompt argv may be visible to same-user process inspection, so prompt contracts cannot contain secrets.

## Consequences

- Provider adapters need contract tests against deterministic fake binaries and installed CLI help during implementation.
- Descriptor creation, permission, validation, cleanup, and early-exit signaling are part of launch atomicity.
- Stored `launch_command` is a redacted template, never a dump of argv/environment.
- F0002 can add managed adapters behind a different execution boundary without altering F0001 tmux records.

## Security & Compliance Notes

- `shell=True` is forbidden in application and adapter code.
- Executable paths, working directories, descriptor paths, feature/story IDs, and prompt paths are validated before launch.
- Only named environment variables may be inherited; values are never logged.

## References

- [CLI contract](../f0001-cli-contract.md)
- [Authorization model](../../security/f0001-authorization-model.md)
- [Codex CLI command documentation](https://learn.chatgpt.com/docs/developer-commands.md?surface=cli)

## Follow-up Actions

- [ ] At feature G0, specify adapter interfaces and descriptor schema/file paths.
- [ ] Add command-injection, metacharacter, and process-list redaction tests.
- [x] Accepted through the Phase B operator approval gate.

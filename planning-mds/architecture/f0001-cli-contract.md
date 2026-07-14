# F0001 CLI and JSON Contract

## Contract Identity

- Command: `nebula-agents`
- Contract version: `1.0`
- Scope: local POSIX/WSL operation
- Transport: process argv, stdout/stderr, exit status, and local JSON/JSONL files
- HTTP/OpenAPI: not applicable; F0001 does not run a server

All commands accept `--format table|json` where output is data-bearing. `table` is the human default. JSON responses include `contract_version`, `command`, `generated_at`, and either `data` or `error`.

## Commands

| Command | Required input | Mutation | Authorization | Success result |
|---------|----------------|----------|---------------|----------------|
| `doctor` | none; optional `--provider codex|claude` | May create runtime directory; otherwise diagnostic only | `Probe` | Preflight result for tmux, provider, workspace, prompt, and runtime paths |
| `tui` | none; optional `--run-id` | Only through explicit TUI actions | Per action | Session list or selected session detail |
| `launch` | `--feature`, `--provider`, `--action`; optional `--story`, `--run-id`, `--transcript` | Creates run, event stream, launch descriptor, tmux session | `Launch` | Run summary with attach guidance |
| `attach` | `--run-id` | Appends attach event; never creates a session | `Attach` | Delegates terminal to recorded tmux session |
| `recover` | `--run-id`; optional `--expected-revision` | Restores the latest validated state image and appends recovery events; never creates a provider | Owning `LocalOperator` + `Attach` | Recovered run summary with attach/transcript/remediation guidance |
| `sessions` | optional `--status` | None | `ReadState` | Bounded list of run summaries |
| `status` | `--run-id` | None | `ReadState` | Current run/gate/validator/transcript projection |
| `evidence` | `--run-id` | None | `ReadState` | Artifact observations and expected paths |
| `validate` | `--run-id`, `--validator` | Records result and audit events | `RunValidator` | Validator key, exit code, duration, summary, artifact path |

Gate decisions and transcript toggles are application operations exposed through the TUI in F0001. Corrupt-state recovery is also exposed through the CLI because a corrupt current snapshot may be intentionally absent from ordinary read projections; recovery remains an explicit, owner-only mutation and never launches or attaches automatically.

## Input Rules

- `run_id`: `YYYY-MM-DD-8hex`.
- `feature`: `F####` and must resolve to one feature folder.
- `story`: `F####-S####`; feature prefix must match `--feature`.
- `provider`: exactly `codex` or `claude`.
- `action`: `plan`, `feature`, `build`, `review`, or `validate` and must resolve to an existing evidence-contract prompt.
- `validator`: committed allowlist key, initially `stories`, `trackers`, or `templates`; callers cannot supply executable paths or command fragments. The selected script and governed input roots are opened no-follow and inherited as stable descriptors for execution.
- User-supplied labels are display-only, bounded to 80 Unicode scalar values, and stripped of control characters.

## Exit Codes

| Exit | Class | Examples |
|------|-------|----------|
| 0 | Success | Query completed, launch active, validator passed |
| 2 | Usage/validation | Unknown option, invalid ID, schema violation |
| 3 | Preflight blocked | Missing tmux/provider/workspace or authentication attention required |
| 4 | Not found | Run, tmux session, evidence path, or prompt not found |
| 5 | Forbidden | Default-deny local policy rejected the action |
| 6 | Conflict | Duplicate run/tmux ID, stale revision, invalid state transition |
| 7 | Gate blocked | Missing evidence, failed/absent validator, unknown gate |
| 8 | Command failed | Provider, tmux, or validator returned a failure |
| 9 | State I/O | Permission denied, corrupt state, atomic write/recovery failure |
| 10 | Timeout | Probe, provider start, validator, or watcher operation timed out |
| 130 | Interrupted | User cancellation or SIGINT where cleanup completed safely |

When a validator runs, the process returns the validator exit code only when it is in `1..125`; runtime contract failures use the classes above and the JSON body distinguishes them.

## Error Shape

```json
{
  "contract_version": "1.0",
  "command": "launch",
  "generated_at": "2026-07-13T18:00:00Z",
  "error": {
    "code": "PREFLIGHT_BLOCKED",
    "message": "The selected provider is not ready.",
    "category": "authentication_attention",
    "details": [{"check": "provider_auth", "status": "attention_needed"}],
    "remediation": "Complete login in the native provider CLI, then rerun doctor.",
    "correlation_id": "6fddeba4-7f25-4bf1-a298-70c095235f4f"
  }
}
```

Errors never include environment values, credential-file contents, raw transcript text, or unredacted subprocess output.

## Provider Port

```text
ProviderAdapter
  key() -> codex | claude
  probe(context) -> PreflightResult
  build_interactive_argv(workspace_root, prompt_text) -> tuple[str, ...]
  classify_early_exit(exit_code, redacted_output) -> ProviderStartResult
```

- The common application layer never branches on provider command flags.
- Codex may receive the workspace and optional initial prompt through documented interactive CLI arguments; existing cached login remains provider-owned.
- Claude invocation details are likewise isolated in its adapter and verified against the installed CLI help during implementation.
- A probe may invoke version/help and a provider-supported non-secret login-status command. It cannot read auth files, print tokens, start a model turn, or perform login.

## Tmux Launch Boundary

Tmux receives only a constant `session-entry` helper command and a validated descriptor path. The owner-only descriptor contains the provider argv, canonical working directory, approved environment-variable names, and correlation ID. `session-entry` validates the descriptor again and replaces itself using `os.execvpe`. User text is never concatenated into tmux's shell command.

The initial evidence-contract prompt may be a single provider argv value. Prompt contracts must not contain secrets because local process listings may expose argv to the same OS user.

## JSON Schemas

- Preflight output: `planning-mds/schemas/f0001-preflight-result.schema.json`
- Run/status output: `planning-mds/schemas/f0001-run-record.schema.json`
- Audit events: `planning-mds/schemas/f0001-runtime-event.schema.json`
- Local policy: `planning-mds/schemas/f0001-local-policy.schema.json`
- Native provider launch descriptor: `planning-mds/schemas/f0001-launch-descriptor.schema.json`

## Compatibility

Readers must reject unknown major versions and may ignore unknown additive fields only when the relevant schema permits them. F0001 schemas set `additionalProperties: false`; additive evolution therefore requires a new schema version and explicit dual-read support.

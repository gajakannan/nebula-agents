# Configuring an MCP host for Nebula Agents

`nebula-agents mcp serve` exposes six **read-only** tools over stdio. There is
deliberately **no `mcp install` subcommand** — see *Why configuration is manual* below.

## Add the server to your host

The server is a stdio child process. Point your host at the installed console script and
run it from the workspace you want to inspect.

```jsonc
{
  "mcpServers": {
    "nebula-agents": {
      "command": "nebula-agents",
      "args": ["mcp", "serve"],
      "cwd": "/absolute/path/to/your/workspace"
    }
  }
}
```

`cwd` matters: the workspace root determines which runtime directory, evidence root, and
feature tree the tools read. Set `NEBULA_AGENTS_RUNTIME_DIR` in the host's environment
block if your runtime directory is not `<workspace>/.nebula-agents/runtime`.

If `nebula-agents` is not on the host's `PATH` — hosts frequently do not inherit a login
shell — use the absolute path from `which nebula-agents`, or the interpreter form:

```jsonc
{ "command": "/path/to/venv/bin/python", "args": ["-m", "nebula_agents", "mcp", "serve"] }
```

## The six tools

| Tool | Input | Returns |
|------|-------|---------|
| `nebula_session_list` | optional `status`, `limit` | Run IDs with sanitized status |
| `nebula_session_status` | `run_id` | Provider, action, feature, gate, validator, evidence summary |
| `nebula_gate_status` | `run_id` | Gate state and decision records |
| `nebula_validator_status` | `run_id` | Latest validator results |
| `nebula_evidence_list` | `run_id`; optional `kind`, `cursor` | Artifact IDs, kinds, summaries, freshness |
| `nebula_evidence_show` | `artifact_id` | Redacted summary and retrieval metadata — never raw bytes |

Tool names are a public contract. Renaming one breaks host configuration, so they do not
change without a contract version bump.

List responses are paged: a response carrying `next_cursor` has more, and you pass that
value back as `cursor`.

## What the surface cannot do

Every tool is read-only, and that is **structural rather than promised**. The server is
constructed with a query-only application facade, so the services that launch sessions,
index evidence, write summaries, or decide proposals are not reachable from it. Adding a
mutating tool would require changing the facade the adapter is constructed with — a
visible architectural edit, not a new handler (ADR-007).

Every call additionally evaluates the default-deny authorization contract with action
`ReadState`. Both mechanisms are kept: a policy misconfiguration alone must not widen the
surface, and a wiring mistake alone must not either.

`nebula_evidence_show` refuses content whenever an artifact's redaction status is not
`Pass`, returning a structured `REDACTION_FAILED` error rather than a partial body.

## Why configuration is manual

Nebula does not write your host's configuration file. Doing so would put it inside a
trust boundary it does not own — the file governs which processes that host will spawn,
it frequently sits alongside credentials for other servers, and its format is the host
vendor's to change. An `install` command would have to locate that file by guesswork,
merge into it without clobbering unrelated entries, and keep pace with each host's
schema. Getting any of that subtly wrong is worse than a documented paste.

This was recorded as open question **M1** during F0003 planning and resolved on
2026-08-29: hosts are configured manually from this document.

## Troubleshooting

**The host shows no tools.** Run the server by hand and send it one line:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | nebula-agents mcp serve
```

You should get a JSON line listing six tools. If the command is not found, the host's
`PATH` is the problem, not the server.

**Tools return `WORKSPACE_NOT_CONFIGURED`.** The `cwd` is not a Nebula workspace. It needs
a `planning-mds/` tree with `features/` and `schemas/` beneath it.

Note that `nebula-agents doctor` run outside a workspace reports `SCHEMA_INVALID`
("Schema cannot be loaded") rather than a setup error — an F0001 diagnostic quirk recorded
as finding S9-F2. Nothing is corrupt; you are in the wrong directory. Check the `cwd` in
your host configuration first.

**Tools return `NOT_FOUND` for a run you can see.** The host is reading a different
runtime directory. Check `NEBULA_AGENTS_RUNTIME_DIR` in the host's environment block
against the one your shell uses.

**A response says `REDACTION_FAILED`.** That artifact has not been summarized, or its
redaction did not complete. Run `nebula-agents evidence summarize --run-id <id>`.

The server exits with its host; nothing is supervised. Closing the host closes it.

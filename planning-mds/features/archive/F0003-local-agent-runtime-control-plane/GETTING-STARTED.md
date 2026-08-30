# F0003 - Local Agent Runtime Control Plane - Getting Started

## Prerequisites

- [ ] F0001 session registry shape is accepted or available as an implementation dependency.
- [ ] Local runtime directory convention is selected.
- [ ] At least one supported native provider CLI can be probed in development.
- [ ] Redaction rules are agreed before transcript or command-log summaries are published.

## Services to Run

F0003 should remain local-only. Early commands should follow this shape:

```bash
nebula-agents doctor
nebula-agents wrap codex --action feature --feature F0001
nebula-agents sessions
nebula-agents status --run <RUN_ID>
nebula-agents evidence list --run <RUN_ID>
nebula-agents evidence show <ARTIFACT_ID>
nebula-agents metrics --run <RUN_ID>
nebula-agents learn review --run <RUN_ID>
```

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `NEBULA_AGENTS_RUNTIME_DIR` | Local runtime state, summaries, and indexes. | `.nebula-agents/runtime` |
| `NEBULA_AGENTS_PROVIDER` | Optional provider selection for wrap launch. | unset |
| `NEBULA_AGENTS_MCP_READONLY` | Keeps MCP tools read-only unless explicitly overridden. | `true` |
| `NEBULA_AGENTS_REDACTION_STRICT` | Enables strict secret redaction for summaries. | `true` |
| `NEBULA_AGENTS_LEARNING_PROPOSALS` | Enables failed-run proposal generation. | `false` |

## Seed Data

Use captured F0001-style run metadata, transcripts, command logs, validator outputs, and evidence manifests. Synthetic fixtures should include successful runs, blocked launches, failed validators, missing transcripts, stale evidence, and rejected learning proposals.

## How to Verify

1. Run provider capability probes and confirm launch guards block unsupported modes.
2. Start a wrapped native session and verify run metadata is persisted.
3. Query status through CLI and MCP surfaces.
4. Add transcript, command log, validator output, and manifest artifacts.
5. Generate summaries and confirm each summary links to a full artifact.
6. Inspect metrics for duration, gate wait time, validator status, transcript health, and evidence freshness.
7. Generate failure-learning proposals and confirm they require review before any instruction changes.

## Key Files

| Layer | Path | Purpose |
|-------|------|---------|
| Planning | `planning-mds/features/F0003-local-agent-runtime-control-plane/PRD.md` | Runtime control plane requirements |
| Planning | `planning-mds/features/F0003-local-agent-runtime-control-plane/F0003-S*.md` | Implementation stories |
| Runtime | `agents/runtime/**` | Proposed local runtime modules |
| CLI | `agents/runtime/cli.py` | Proposed command entry point |
| MCP | `agents/runtime/mcp_server.py` | Proposed read-only tool server |
| Templates | `agents/templates/prompts/evidence-contract/` | Prompt contracts referenced by runtime state |

## Dev User Credentials

Provider credentials stay outside Nebula-owned files. Capability probes may execute provider CLIs, but runtime state must not include credential bodies, API keys, auth cache contents, or subscription account secrets.

## Notes

- The local runtime should treat full artifacts as the source of truth and summaries as navigational aids.
- Any future managed orchestration should consume F0003 contracts instead of scraping terminal output.
- Learning proposals should require explicit reviewer acceptance before instruction files or process docs change.

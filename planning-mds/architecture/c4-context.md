# Nebula Agents System Context

```mermaid
C4Context
    title F0001 Tmux-Native Agent Cockpit - System Context
    Person(operator, "Local Operator", "Launches, attaches to, validates, and governs native agent runs")
    Person(reviewer, "Local Reviewer", "Inspects sanitized state and evidence; runs allowed validators")
    System(cockpit, "Nebula Agents Cockpit", "Local CLI/TUI that wraps native tmux sessions with governed state, evidence visibility, and recovery")
    System_Ext(tmux, "tmux", "Owns the durable local terminal session")
    System_Ext(codex, "Codex CLI", "Native interactive coding agent")
    System_Ext(claude, "Claude Code CLI", "Native interactive coding agent")
    System_Ext(workspace, "Product Workspace", "Planning documents, prompts, validators, and evidence artifacts")
    System_Ext(os, "Local OS Identity and Filesystem", "User/group identity, process execution, and owner-only runtime state")

    Rel(operator, cockpit, "Operates", "Terminal")
    Rel(reviewer, cockpit, "Reviews", "Terminal")
    Rel(cockpit, tmux, "Creates, probes, and attaches to sessions", "Local process")
    Rel(tmux, codex, "Hosts one selected provider")
    Rel(tmux, claude, "Hosts one selected provider")
    Rel(cockpit, workspace, "Reads planning/evidence and invokes allowlisted validators", "Filesystem + argv")
    Rel(cockpit, os, "Resolves identity and stores atomic state", "Local APIs")
```

## Boundary Notes

- Provider login and provider tool approvals stay inside the native CLI.
- Lifecycle gate approval is a separate explicit Nebula action and cannot be inferred from provider screen output.
- No network service, cloud data store, remote collaborator, or managed provider adapter exists in F0001.
- F0003 and F0002 may add surfaces around this system but must preserve direct tmux attach as fallback until parity is proven.

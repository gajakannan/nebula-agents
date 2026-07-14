# Nebula Agents Container View

```mermaid
C4Container
    title F0001 Tmux-Native Agent Cockpit - Container View
    Person(operator, "Local Operator", "Operates native agent runs")
    Person(reviewer, "Local Reviewer", "Reads state and validates evidence")

    System_Boundary(nebula, "Nebula Agents Cockpit") {
        Container(ui, "CLI and TUI", "Python terminal application", "Parses commands, captures explicit decisions, and renders sanitized projections")
        Container(app, "Application and Domain", "Python modules", "Enforces run, gate, transcript, authorization, and recovery invariants")
        Container(adapters, "Runtime Adapters", "Python modules", "Tmux/provider execution, filesystem persistence, polling, OS identity, clock")
        ContainerDb(store, "Local Runtime Store", "JSON snapshots + JSONL events", "Owner-only, locked, atomic current state and immutable audit")
    }

    System_Ext(tmux, "tmux", "Durable terminal session")
    System_Ext(provider, "Native Provider CLI", "Codex or Claude interactive UI")
    System_Ext(workspace, "Workspace Planning and Evidence", "PRDs, stories, prompts, gate logs, reports, validators")

    Rel(operator, ui, "Launches, attaches, decides gates", "Terminal")
    Rel(reviewer, ui, "Queries and validates", "Terminal")
    Rel(ui, app, "Invokes typed use cases")
    Rel(app, adapters, "Uses ports")
    Rel(adapters, store, "Locks, validates, appends, atomically replaces")
    Rel(adapters, tmux, "Creates/probes/attaches", "argv + isolated helper")
    Rel(tmux, provider, "Hosts one process")
    Rel(adapters, workspace, "Reads/watches and runs allowlisted validators", "Filesystem + argv")
```

## Deployment Topology

All containers in the diagram are logical boundaries inside one local executable except the filesystem store and external processes. There is no Docker or server deployment requirement for F0001. A TUI exit must leave tmux and its provider child alive.

## Dependency Direction

```text
CLI/TUI -> Application -> Domain
             ^
             |
          Adapters
```

Adapters implement application-owned ports. Presentation cannot call adapters directly.

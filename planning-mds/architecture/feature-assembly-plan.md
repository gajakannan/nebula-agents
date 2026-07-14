# Feature Assembly Plan Index

## Purpose

This file is the cross-feature sequencing view. Implementation-level detail remains in each feature-local plan so it archives with the feature.

## Active Plans

| Feature | Status | Execution Plan | Dependency Position |
|---------|--------|----------------|---------------------|
| F0001 — Tmux-Native Agent Cockpit | G0 validated; implementation next | [`../features/F0001-tmux-native-agent-cockpit/feature-assembly-plan.md`](../features/F0001-tmux-native-agent-cockpit/feature-assembly-plan.md) | First runtime delivery; establishes the native-session identity and read contracts consumed by F0003 and later F0002. |

## Sequencing Constraints

1. F0001 ships the native tmux fallback and local run identity first.
2. F0003 may index and summarize F0001 records but cannot redefine their identity, audit, or redaction meaning.
3. F0002 cannot remove the native path until closeout evidence demonstrates equivalent interactive approvals, terminal visibility, validation gates, and recovery.
4. Shared contract drift found during implementation returns to Architect ownership before the affected implementation checkpoint advances.


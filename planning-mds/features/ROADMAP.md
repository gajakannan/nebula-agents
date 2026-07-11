# Feature Roadmap (Now / Next / Later)

**Last Reviewed:** 2026-07-06

## Purpose

This roadmap sequences Nebula Agents work so the team can validate one delivery step before starting the next. It is intentionally conservative: tmux-native session orchestration comes first because it preserves the current interactive quality of Codex and Claude Code. Managed SDK/provider orchestration comes later only after parity is proven.

## Update Rules

- Move a feature between `Now`, `Next`, `Later`, and `Completed` when its execution state changes.
- Keep links aligned with `REGISTRY.md`, `STORY-INDEX.md`, and `BLUEPRINT.md`.
- Do not place F0002 in `Now` until F0001 validates provider auth reuse, interactive approval preservation, gate visibility, transcript recovery, and validator integration.

## Now

| Feature | Status | Why Now | Validation Gate |
|---------|--------|---------|-----------------|
| [F0006 - Compiled KG Projection and Governed Integration](./F0006-compiled-kg-projection-and-integration/) | Done | Seven open contributor PRs in the reference product repo (`nebula-insurance-crm`) were blocked on hand-merging knowledge-graph/tracker YAML with no sanctioned integration owner — every future multi-contributor merge hit the same wall. Phase A (semantic merge tool + integrator role) drained the queue; Phase B (compiled projection) removed the problem class structurally. | Phase A (2026-07-06): all 7 `nebula-insurance-crm` PRs merged via integrator, promoted to `main`. **Phase B complete 2026-07-11** (all 9 stories, feature-review PASS): decompiler cutover landed (`kg-source/` is authoring truth); `compile(decompile(graph)) == graph` + tracker round trip byte-identical; blocking `reproducibility` CI on `main`; contract docs reconciled (audit clean). Branch promotion to `main` pending. |
| [F0001 - Tmux-Native Agent Cockpit](./F0001-tmux-native-agent-cockpit/) | Planned | Establish the first usable terminal cockpit without losing native agent interactivity or subscription auth. | Operator can launch, attach, monitor, validate, and recover a native Codex or Claude Code session from the TUI. |

## Next

| Feature | Status | Why Next | Entry Criteria |
|---------|--------|----------|----------------|
| [F0003 - Local Agent Runtime Control Plane](./F0003-local-agent-runtime-control-plane/) | Planned | Add concrete local commands, status tools, evidence retrieval, summaries, metrics, and reviewed learning before managed orchestration becomes default. | F0001 session registry and transcript model are accepted or available as implementation dependencies. |
| [F0002 - Managed Agent Orchestration](./F0002-managed-agent-orchestration/) | Planned | Add provider adapters and richer orchestration once tmux behavior and runtime control-plane contracts are understood and testable. | F0001 is implemented, F0003 runtime contracts are validated, and evidence shows native interactivity can be preserved or matched. |

## Later

| Feature | Status | Notes |
|---------|--------|-------|
| [F0004 - Reflective Learning Loop and Strategy Playbook](./F0004-reflective-learning-loop/) | Planned | Closes the context-engineering loop (learn -> Write -> Select). Needs run evidence/telemetry from F0003 evidence store before reflection has useful input. Ships behind a default-off flag, candidate-only at first. |

## Completed

| Feature | Completed Date | Evidence |
|---------|----------------|----------|

## Notes

- F0001 is a subscription-first implementation path. It should call authenticated local CLIs, not API-key-only SDK flows.
- F0003 is the local runtime hardening layer that turns launch, status, evidence, summaries, metrics, and learning review into concrete implementation contracts.
- F0002 may support SDK and exec-based providers, but it must keep a tmux fallback until managed orchestration proves equivalent engineering quality.
- F0004 is a context-engineering layer, not a runtime path. It depends on F0003 evidence/telemetry being available to reflect from, and it never mutates `SKILL.md` or applies an unapproved change.
- F0005 was superseded by F0006 on 2026-07-04 (see `REGISTRY.md` Retired Features): its logical doc-ref design is fully absorbed as the compiled-projection compiler's reference format.
- F0006 is independent of the F0001 → F0003 → F0002 runtime line and does not displace F0001; it is in `Now` because it unblocked the reference product repo's contributor PRs. Its Phase-A merge train completed and promoted to `main` on 2026-07-06 (S0001–S0003 done); Phase B (shard migration) may now proceed.

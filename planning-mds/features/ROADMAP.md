# Feature Roadmap (Now / Next / Later)

**Last Reviewed:** 2026-07-13

## Purpose

This roadmap sequences Nebula Agents work so the team can validate one delivery step before starting the next. It is intentionally conservative: tmux-native session orchestration comes first because it preserves the current interactive quality of Codex and Claude Code. Managed SDK/provider orchestration comes later only after parity is proven.

## Update Rules

- Move a feature between `Now`, `Next`, `Later`, and `Completed` when its execution state changes.
- Keep links aligned with `REGISTRY.md`, `STORY-INDEX.md`, and `BLUEPRINT.md`.
- Do not place F0002 in `Now` until F0001 validates provider auth reuse, interactive approval preservation, gate visibility, transcript recovery, and validator integration.

## Now

| Feature | Status | Why Now | Validation Gate |
|---------|--------|---------|-----------------|
| [F0007 - Spec-Driven Orchestration and Prompt Compilation](./F0007-spec-driven-orchestration-and-prompt-compilation/) | Planned | The fixed orchestration contract is paraphrased across actions, 24 evidence prompts, skills, validators, and prose linters. F0007 makes versioned policy authoritative, compiles prompts, executes typed procedure, and preserves historical evidence semantics. | Historical policy fixtures retain baseline verdicts; typed runtime has no shell path; generated prompts pass drift plus independent semantic checks; one governed pilot reaches closeout. |
| [F0001 - Tmux-Native Agent Cockpit](./F0001-tmux-native-agent-cockpit/) | In Progress | Establish the first usable terminal cockpit without losing native agent interactivity or subscription auth. G0 assembly planning passed in run `2026-07-13-1cfbc5a0`. | Operator can launch, attach, monitor, validate, and recover a native Codex or Claude Code session from the TUI. |

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
| [F0006 - Compiled KG Projection and Governed Integration](./archive/F0006-compiled-kg-projection-and-integration/) | 2026-07-11 | All 9 stories Done; feature-review PASS; framework Phase-B PRs #42-#46 and product PR #59 landed on `main`; compiled-projection and reproducibility gates green; recovery G8 archive completed 2026-07-12. |

## Notes

- F0001 is a subscription-first implementation path. It should call authenticated local CLIs, not API-key-only SDK flows.
- F0003 is the local runtime hardening layer that turns launch, status, evidence, summaries, metrics, and learning review into concrete implementation contracts.
- F0002 may support SDK and exec-based providers, but it must keep a tmux fallback until managed orchestration proves equivalent engineering quality.
- F0004 is a context-engineering layer, not a runtime path. It depends on F0003 evidence/telemetry being available to reflect from, and it never mutates `SKILL.md` or applies an unapproved change.
- F0005 was superseded by F0006 on 2026-07-04 (see `REGISTRY.md` Retired Features): its logical doc-ref design is fully absorbed as the compiled-projection compiler's reference format.
- F0006 is independent of the F0001 → F0003 → F0002 runtime line and does not displace F0001. Phase A promoted on 2026-07-06; Phase B completed and promoted on 2026-07-11; recovery G8 closeout archived it on 2026-07-12.
- F0007 is framework hardening and may proceed alongside F0001 because it reduces prompt/contract maintenance risk without changing the runtime product sequence.

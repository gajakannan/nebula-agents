# G0 Assembly Plan Validation — F0001 remediation run 2026-07-14-b885d64c

## Run Identity

- Feature: F0001 — Tmux-Native Agent Cockpit
- Gate: G0
- Reviewer: Architect Agent
- Reviewed on: 2026-07-14
- Plan: `planning-mds/features/F0001-tmux-native-agent-cockpit/feature-assembly-plan.md`
- Prior blocked run: `2026-07-13-1cfbc5a0`

## Scope Review

The remediation is limited to eight blocking code-review findings plus two directly observed operator-flow gaps. It preserves the local tmux/native-provider architecture, six approved stories, local authorization model, persistence model, and public CLI/TUI separation.

## Architecture Reconciliation

- Absolute preflight paths follow S0001's machine-readable path rule.
- Atomic launch and transcript compensation follow ADR-002 persistence ordering and fail-closed terminal-state requirements.
- Descriptor-bound script/input access strengthens the approved ADR-003 execution boundary without introducing a new service or API.
- Last-valid evidence preservation and YAML/Markdown categorization follow S0003.
- Reachable corrupt-state recovery and complete recovery projection follow S0005/S0006.
- Product-root environment resolution and post-launch next-step guidance reconcile implementation with the documented setup contract without changing launch into attach.
- The critical-path 100% branch targets remain unchanged. The initial G0 dependency range was `pytest>=8,<9`; the post-G1 security reconciliation below supersedes that range without changing runtime code or product scope.

## Dependency And Ownership Review

Backend owns domain/application/infrastructure changes; Presentation owns CLI/TUI/formatting; QE owns tests and official branch evidence. Shared contracts remain Architect-owned. Code and Security Review remain independent at G3. The live operator demo session is excluded from every automated lane.

## Mutation And Audit Review

The highest-risk mutations have explicit compensation/recovery proof: tmux creation before durable launch commit, transcript piping before/after terminal commits, worker sidecar failure, corrupt snapshot repair, and validator path replacement. Pure rendering changes do not replace application enforcement.

## Integration And Test Review

G2 requires a full compatible-environment suite, real tmux/fake-provider lifecycle, failure injection for each crash seam, table/JSON parity, non-repository-cwd product-root probes, and branch-enabled XML. No prior test or review verdict is carried forward as passing evidence.

## Knowledge-Graph Prediction

The existing six predicted capabilities remain sufficient. The repository still lacks lookup/hint/compiler tooling and a self-hosted KG source, so the prior G7 governance limitation is preserved exactly.

## Findings

No blocking G0 plan finding. The remediation must stop if G1 fails or if any fresh G3 Critical/High finding remains.

## Post-G1 Security Reconciliation

The clean pytest-8 verification resolved pytest 8.4.2 and the required dependency audit reported `CVE-2025-71176 / GHSA-6w46-j5rx-g56g`. The reviewed advisory affects pytest through 9.0.2 on UNIX and upstream pytest 9.0.3 records the fix. Architect therefore reconciled the assembly plan and package metadata to `pytest>=9.0.3,<10` before the final G2 suite. This resolves the prior review's plan/metadata mismatch while refusing a known-vulnerable test toolchain.

## Result

PASS

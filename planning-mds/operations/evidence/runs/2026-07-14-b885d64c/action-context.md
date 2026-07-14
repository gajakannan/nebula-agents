# Action Context — F0001 remediation run 2026-07-14-b885d64c

## Run Identity

- Action: `feature`
- Feature: `F0001`
- Feature slug: `tmux-native-agent-cockpit`
- Run ID: `2026-07-14-b885d64c`
- Rerun of: `2026-07-13-1cfbc5a0`
- Product root: `/home/gajap/uSandbox/repos/nebula/nebula-agents`
- Branch: `feat/F0001-tmux-native-agent-cockpit`
- Started: `2026-07-14T15:43:28-04:00`
- Current owner: Architect Agent

## Inputs

- Explicit operator instruction: `start the F0001 G3 remediation run`.
- F0001 PRD, six story contracts, approved Phase B architecture, and existing assembly plan.
- Blocking `code-review-report.md` and passing-with-recommendations `security-review-report.md` from run `2026-07-13-1cfbc5a0`.
- Operator demo observations: product-root discovery failed outside the repository and successful launch did not itself enter or explain the TUI.
- `agents/actions/feature.md`, Architect role contract, Agent Ops evidence contract, and manual orchestration runbook.

## Assumptions

- This is remediation of the same approved F0001 scope on the existing feature branch, not a new feature or a waiver request.
- The existing demo run and tmux session are user-owned live state and remain untouched.
- The branch-coverage contract remains binding. Dependency ranges remain binding unless a current audit proves them unsafe; R8 was reconciled from pytest `<9` to the upstream fixed `>=9.0.3,<10` line after CVE-2025-71176 was reproduced in the clean environment.
- Prior G2/G3 evidence is triage input only; the new run must produce its own G1-G3 evidence.

## Scope Boundaries

In scope: the eight blocking review findings, `NEBULA_AGENTS_PRODUCT_ROOT` wiring, launch next-step guidance, corresponding tests/docs, new evidence, and fresh reviews.

Out of scope: automatic TUI entry, automatic tmux attachment, managed-provider orchestration, HTTP/remote operation, new provider SDKs, G4 approval, and any G5-G8 closeout action before that approval.

The formal failure-triage request authorizes exact reads from cold archive run `2026-07-13-1cfbc5a0`. No unrelated evidence runs were read. The repository has no `.agentignore` and no self-hosted KG lookup/hint/compiler tools, so raw feature, architecture, source, and review artifacts remain authoritative.

## Lifecycle Stage

Current stage: `G6 passed; G7 blocked because the product has not adopted the mandatory KG source/compiler/validator contract; G8 is closed pending explicit governance resolution`.

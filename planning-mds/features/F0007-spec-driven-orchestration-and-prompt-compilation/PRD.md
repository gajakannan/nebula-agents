# F0007 - Spec-Driven Orchestration and Prompt Compilation PRD

## Feature Header

**Feature ID:** F0007
**Feature Name:** Spec-Driven Orchestration and Prompt Compilation
**Priority:** Critical
**Phase:** Framework Hardening
**Status:** Draft

## Feature Statement

**As a** framework maintainer evolving governed agent workflows
**I want** fixed orchestration policy declared once and executed by deterministic scripts
**So that** prompts focus on judgment, contract changes are reviewable, and historical evidence
remains valid without maintaining paraphrased rules across dozens of files.

## Business Objective

- **Goal:** Move fixed paths, artifacts, ordering, thresholds, gate arithmetic, and command
  procedure from hand-maintained prompt prose into versioned specifications and scripts.
- **Baseline:** The contract is repeated across action documents, 24 evidence prompts, role skills,
  validators, and regex-based alignment checks.
- **Target:** One active action policy plus immutable historical bundles feeds prompt generation,
  gate execution, configuration consumers, and version-aware validation.
- **Primary metric:** A representative contract change is declared once and produces a behavioral
  diff plus deterministic updates without manual policy edits across prompt pairs.
- **Safety metric:** Every archived evidence fixture retains its pre-migration validator verdict.
- **Context metric:** Generated action prompts and affected role skills reduce fixed procedural prose
  by at least 40% without losing accepted judgment guidance.

## Problem Statement

The framework treats English as executable configuration. Identical session setup, command logging,
gate ordering, severity arithmetic, and evidence requirements are paraphrased across many files.
The paraphrases do not diff cleanly, prompt context is spent on deterministic procedure, and the
framework needs regexes to detect obsolete sentences.

Moving all policy into one mutable file would remove drift but create two new risks: a common-mode
policy regression could make prompts and validators consistently wrong, and a new matrix could
retroactively reinterpret old evidence. F0007 therefore combines single declaration with immutable
history, independent conformance fixtures, and explicit behavioral diffs.

## Scope and Boundaries

### In Scope

- Versioned action specifications, shared constants, immutable historical policy bundles, and JSON
  Schema plus semantic validation.
- `contract_version` stamping for new manifests and date-based compatibility for legacy manifests.
- Independent historical fixtures, semantic invariants, and a behavioral contract-diff command.
- Deterministic run initialization, product scaffolding, and concurrency-safe state creation.
- A shared typed-operation runtime used by action gates and the existing lifecycle runner.
- Complete command telemetry through `run-gate.py` for gate operations and `exec-and-log.py` for
  other commands.
- Durable manual checkpoints with evidence attestations, hashes, locking, and atomic state writes.
- Central severity arithmetic and vague-language linting.
- Generation of operator-friendly and automation-safe evidence prompts with committed output and a
  CI drift gate.
- Version-aware evidence-validator convergence through a dual-read migration.
- Consolidation of coverage thresholds and other policy literals across action docs, skills,
  `agent-map.yaml`, and coverage scripts.
- Prose thinning that retains review criteria, classification, clarification, architectural judgment,
  teaching examples, and writing voice.

### Out of Scope

- Product-specific KG implementations or vendoring `{PRODUCT_ROOT}/scripts/kg/**` into the framework.
- Automatic migration or mutation of in-flight product evidence runs.
- Replacing human severity classification or architectural/review judgment with scripts.
- A hosted orchestration service, database-backed workflow engine, or provider SDK migration.
- Rewriting editorial actions such as `blog` and `document` beyond shared run initialization.
- Removing the readable generated prompts from version control.

## Acceptance Criteria Overview

- [ ] Every action spec passes structural and semantic validation; executable operations are typed
  argv arrays with declared cwd, timeout, outputs, and mutations.
- [ ] New evidence manifests carry `contract_version` and `contract_effective_date`; legacy manifests
  resolve deterministically by date without being rewritten.
- [ ] Historical fixtures for all existing effective-date cutovers retain their baseline verdicts.
- [ ] A contract diff reports added, removed, or changed gates, artifacts, operations, thresholds,
  stop conditions, and compatibility dates.
- [ ] `init-run.py` cannot create two active runs for the same feature under concurrent invocation.
- [ ] Neither the action gate driver nor arbitrary-command wrapper invokes spec content through a shell.
- [ ] An unattested manual checkpoint cannot be skipped with resume flags.
- [ ] Both prompt variants regenerate byte-identically; drift and independent semantic violations fail CI.
- [ ] Validator dual-read reports zero disagreement before private constants are removed.
- [ ] `coverage_min_pct` has one policy owner and all runtime/configuration consumers resolve it.
- [ ] A governed pilot completes closeout with complete JSONL command telemetry and no historical
  fixture regression.

## Architecture

```text
 agents/actions/spec/
   _contract.yaml -------- active version + shared values
   history/*.yaml -------- immutable, fully resolved policy bundles
   <action>.yaml ---------- active action policy
   schema/*.json ---------- structural contract
          |
          +--> validate_action_specs.py --contract-diff
          +--> render-prompts.py --> committed prompt variants
          +--> init-run.py / scaffold-product.py
          +--> run-gate.py --> gate_runtime.py --> subprocess(argv)
          +--> version-aware validators
          +--> contract-value.py --> symbolic consumers
          |
 independent fixtures + semantic invariants (not generated from policy)
```

## Policy and Compatibility Model

### Active Policy

`_contract.yaml` names the active contract version and owns shared values such as run-ID format,
base evidence files, command-log fields, coverage minimum, and context preamble. Each action spec
declares its scope, inputs, ownership, gates, typed operations, stop conditions, and judgment notes.

### Historical Policy

Each published version under `history/` is fully resolved and immutable. It contains the shared
values and action matrices needed to interpret evidence produced under that version; it never
inherits a mutable value from the active contract.

### Manifest Resolution

1. A new run receives both `contract_version` and `contract_effective_date`.
2. A validator loads the exact policy named by `contract_version`.
3. A legacy manifest without a version maps to the newest historical policy whose `effective_from`
   is not later than the manifest date.
4. An unknown version or a date older than the first supported policy fails with a named rule.
5. Historical manifests are read-only; compatibility never backfills them in place.

## Typed Operation Model

```yaml
- run:
    argv: [python3, agents/scripts/validate_templates.py]
    cwd: framework
    timeout_seconds: 300
    expected_artifacts: []
    mutates: []
- checkpoint:
    id: archive-move
    requires: [pm-closeout.md, signoff-ledger.md]
    produces: [archived-feature-folder]
- write:
    artifact: latest-run.json
    after: prior-manifest-patched
```

The schema rejects string-form executable commands, unknown placeholders, undeclared mutation
classes, duplicate operation IDs, and checkpoints without pre/postconditions. The runtime passes
argv directly to `subprocess.run`, applies timeouts, and records normalized telemetry.

## Command Telemetry Boundary

| Command Class | Supported Entry Point | Required Record |
|---------------|-----------------------|-----------------|
| Gate operation from an action spec | `run-gate.py` | `commands.log`, `lifecycle-gates.log`, gate-state journal |
| Framework lifecycle gate | `run-lifecycle-gates.py` via shared runtime | Lifecycle result plus command record when a run folder is supplied |
| Implementation, investigation, or manual-checkpoint command | `exec-and-log.py -- ...` | `commands.log` JSONL entry |
| Human judgment without a command | Checkpoint attestation | Gate-state record with evidence paths and hashes |

## Independent Correctness Controls

- Golden historical evidence fixtures are not generated from action specs.
- Semantic invariants remain explicit: canonical package scope, run-ID restrictions, required
  gate/artifact relationships, monotonic policy dates, and no shell-form execution.
- Prompt snapshots exercise every action scope and variant branch.
- Dual-read validator tests compare the legacy constants and policy-derived decisions.
- A policy-changing pull request includes the behavioral diff as review evidence.

## Roles and Authorization

| Role | Responsibility | Mutation Boundary |
|------|----------------|-------------------|
| Product Manager | Action scope, artifacts, trackers, rollout, and prompt-equivalence acceptance | May edit planning/action policy fields; cannot weaken historical fixtures silently |
| Architect | Policy schema, versioning, operation model, checkpoint semantics | Approves schema and compatibility changes |
| Backend Developer | Python runners, generators, validators, and locking | Writes framework scripts within declared interfaces |
| Quality Engineer | Historical fixtures, concurrency/failure tests, pilot evidence | Does not modify expected verdicts merely to make a change pass |
| Code Reviewer | Common-mode regression, subprocess safety, compatibility review | Blocks untyped execution or unreviewed policy weakening |
| DevOps | CI drift/conformance gates and generated-file workflow | Owns lifecycle and CI integration |
| Security Reviewer | Command injection, path escape, redaction, and lock/state integrity | Required for execution-boundary stories |

## Non-Functional Requirements

- **Determinism:** Prompt generation and contract-diff output are byte-stable for identical input.
- **Safety:** No `shell=True`; resolved paths stay within framework/product roots; secret scanning and
  redaction semantics remain intact.
- **Compatibility:** Historical verdicts do not change after an active-policy update.
- **Concurrency:** Run initialization and gate-state/log writes are serialized per feature/run.
- **Performance:** Spec load plus validation adds less than 250 ms before command execution on the
  repository fixture set; prompt regeneration completes in under 10 seconds locally.
- **Portability:** Python behavior is platform-aware; unsupported locking behavior fails closed with
  a clear diagnostic rather than proceeding unlocked.
- **Observability:** Every scripted operation emits structured status, failure step, and log references.

## Rollout Strategy

1. Establish versioned policy, schema, fixtures, and contract diff.
2. Introduce deterministic run setup and typed execution without thinning existing prose.
3. Generate the `feature` prompt pair first and compare semantics against current files.
4. Roll out remaining actions; keep independent prompt invariants.
5. Put evidence validation in dual-read mode and resolve every disagreement.
6. Thin prose only after generated prompts and validators are accepted.
7. Pilot on one new governed feature run; do not convert an in-flight run between gates.
8. Remove duplicate constants only after the pilot and historical suite are green.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Mutable policy changes old evidence | Immutable bundles and manifest version selection |
| Generator, runner, and validator agree on a bad edit | Independent fixtures, invariants, and behavioral diff |
| Placeholder or quoting becomes command injection | Typed argv, allowlisted placeholders, no shell |
| Resume skips the archive/manual step | Durable attestation with required outputs and hashes |
| Concurrent agents corrupt logs or state | Per-feature/per-run locks and atomic replacement |
| Prompt generation drops nuance | Human semantic-equivalence review and free-text judgment fields |
| Threshold remains duplicated | Symbolic consumer references and a validation gate for private literals |
| Rollout splits one run across contracts | No in-flight conversion; version fixed at initialization |

## Success Criteria

- One policy edit updates all derived surfaces and produces a reviewed behavioral diff.
- Historical evidence fixtures retain identical results before and after convergence.
- The feature prompt pair is at least 40% shorter in fixed procedure while preserving judgment
  sections identified in the source proposal.
- One pilot feature closes successfully with gate operations and arbitrary commands recorded through
  the supported entry points.
- Lifecycle CI fails on generated drift, schema errors, semantic-invariant violations, historical
  regression, and unresolved validator dual-read disagreement.

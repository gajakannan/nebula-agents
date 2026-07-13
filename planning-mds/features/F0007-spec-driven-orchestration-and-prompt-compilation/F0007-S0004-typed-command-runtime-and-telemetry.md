# F0007-S0004 - Typed Command Runtime and Complete Telemetry

## Story Header

**Story ID:** F0007-S0004
**Feature:** F0007 - Spec-Driven Orchestration and Prompt Compilation
**Title:** Typed command runtime and complete telemetry
**Priority:** Critical
**Phase:** Framework Hardening

## User Story

**As a** framework operator
**I want** all scripted commands executed as typed argv through one runtime with normalized telemetry
**So that** quoting, injection, timeout, and logging behavior is consistent across lifecycle and action gates.

## Context & Background

This slice extracts `gate_runtime.py` from the existing lifecycle runner and adds `exec-and-log.py`
for arbitrary non-gate commands. It preserves the current lifecycle CLI while establishing the only
supported shell-free subprocess path for later action gates.

## Acceptance Criteria

**Happy Path:**
- **Given** a validated typed operation
- **When** the shared runtime executes it
- **Then** argv is passed directly without a shell, cwd and timeout are enforced, and exit status plus
  durable artifacts are appended through `append-command-log.py`
- **Then** `run-lifecycle-gates.py` retains its current list/run behavior and result codes

**Edge Cases / Rejected Inputs:**
- Metacharacters, spaces, and placeholder values remain single argv elements and never trigger shell expansion.
- Path escape, unknown cwd label, missing executable, timeout, signal, and logging failure return named errors.
- A command requesting undeclared mutation or artifact outside the product root is rejected.
- Secret-bearing command content is redacted or forbidden according to the existing telemetry policy.

## Data Requirements

- Operation input: argv, cwd label, timeout, expected artifacts, mutation classes, redactions.
- Result: operation ID, start/end time, exit code, timeout/signal state, artifact references.
- JSONL command schema remains compatible with existing validation.

## Role-Based Visibility

- Spec-authorized gate runners and explicit operators may execute commands.
- Callers cannot authorize path escape by supplying a different cwd string.
- Security Reviewer approves execution and redaction boundaries.
- Logs are readable by evidence reviewers but must not contain raw secrets.

## Non-Functional Expectations

- No reachable `shell=True` or equivalent evaluation.
- Signal forwarding and timeout cleanup leave no orphaned child process in tests.
- Caller-level per-run locking prevents interleaved journal/log corruption.
- Runtime functions are unit-testable without invoking real product tools.

## Dependencies

**Depends On:** F0007-S0001.

**Related Stories:** S0005 builds the action driver; S0009 adopts lifecycle gates.

## Business Rules

1. Gate operations use the shared runtime.
2. Non-gate commands use `exec-and-log.py` when run evidence is active.
3. `append-command-log.py` remains the single normalization path.

## Out of Scope

- Gate ordering, checkpoint state, severity decisions, or prompt generation.
- Supporting arbitrary shell pipelines as one operation; callers express pipelines as explicit processes or scripts.

## Questions & Assumptions

**Open Questions:**
- [ ] Define whether lifecycle runs without a run folder emit only console output or an optional framework-local log.

**Assumptions:**
- Existing JSONL schema remains version 1 unless signal/timeout fields require an additive schema revision.

## Definition of Done

- [ ] Shared runtime and arbitrary-command wrapper implemented.
- [ ] Lifecycle runner regression suite passes unchanged behavior expectations.
- [ ] Injection, argv preservation, timeout, signal, path, artifact, and redaction tests pass.
- [ ] Audit telemetry proves every executed test command's normalized result.
- [ ] No spec content reaches a shell interpreter.

## Review Provenance

Story-level signoff is recorded in the parent `STATUS.md`.

# F0007-S0003 - Run Initialization and Product Scaffolding

## Story Header

**Story ID:** F0007-S0003
**Feature:** F0007 - Spec-Driven Orchestration and Prompt Compilation
**Title:** Run initialization and product scaffolding
**Priority:** High
**Phase:** Framework Hardening

## User Story

**As a** feature operator
**I want** one idempotent command to initialize a version-stamped evidence run and scaffold missing product files
**So that** session setup is consistent, concurrency-safe, and no longer reconstructed from prompt prose.

## Context & Background

`init-run.py` resolves product/feature paths, creates the evidence skeleton, stamps policy identity,
and detects competing active runs. `scaffold-product.py` performs the mechanical portion of `init.md`
using missing-only writes. User interviews and blueprint tailoring remain judgment work.

## Acceptance Criteria

**Happy Path:**
- **Given** a valid product root and feature ID
- **When** `init-run.py` initializes a new run
- **Then** exactly one run folder, manifest, base files, logs, artifact directories, and seeded action
  context are created with active contract version/date
- **Then** resolved variables are emitted as JSON and the mutation is represented in audit evidence

**Edge Cases / Rejected Inputs:**
- Two concurrent initializers for the same feature yield one success and one explicit conflict.
- Existing non-empty run folders are rejected unless authorized `--resume` is used.
- A product root outside the allowed boundary or a malformed feature ID is forbidden.
- A scaffold destination that already exists is preserved byte-for-byte; partial writes are rolled back.

## Data Requirements

- Inputs: action, feature, product root, mode, optional rerun/resume.
- Outputs: run ID, prior run ID, resolved paths, policy version/date, created/preserved file list.
- Lock identity: feature ID plus resolved product root.
- Scaffold map: template, destination, required/optional classification.

## Role-Based Visibility

- Operators and PM may initialize runs under an authorized product root.
- `scaffold-product.py` writes only missing product files; existing content requires explicit manual edit.
- Other role agents consume emitted variables but cannot bypass the concurrent-run policy.

## Non-Functional Expectations

- Atomic manifest and pointer writes; no partial skeleton on failure.
- Cross-platform locking fails closed when a safe primitive is unavailable.
- Idempotent `--check` produces no mutation and a deterministic report.
- Run IDs use cryptographic randomness without shell evaluation.

## Dependencies

**Depends On:** F0007-S0001.

**Related Stories:** S0005 consumes initialized gate state; S0009 uses initialization in the pilot.

## Business Rules

1. A run's contract version is fixed at creation.
2. One active draft/in-progress run per feature unless the policy explicitly permits otherwise.
3. Scaffolding never overwrites a product-owned file.

## Out of Scope

- Executing feature gates or deciding product blueprint content.
- Migrating an in-flight prose-created run.

## Questions & Assumptions

**Open Questions:**
- [x] Select the portable lock-file/advisory-lock implementation and stale-lock recovery contract.
  **Resolved:** atomic `os.open(O_CREAT|O_EXCL)` lock file (identity = feature id + resolved product
  root), held only around the scan-and-create critical section and released in `finally`; fails
  closed on `OSError` (never proceeds unlocked). The durable "one active run per feature" guard is
  the manifest scan, not the lock, so stale locks are rare; a stale lock is cleared with
  `--force-unlock`. Portable across POSIX/Windows without `fcntl`.

**Assumptions:**
- `_product_root.py` remains the canonical root resolver.

## Definition of Done

- [x] Run initialization and scaffold check/write modes implemented. (`init-run.py`;
  `scaffold-product.py` with `--check`)
- [x] Contract stamping and legacy rerun linkage tested. (manifest `contract_version` +
  `contract_effective_date` from active policy; `rerun_of`; `test_init_run.py`)
- [x] Concurrent creator, resume, malformed input, path escape, and rollback tests pass.
  (`test_init_run.py` — 2 concurrent initializers → one success + one conflict; `--resume`
  idempotency; F#### / slug traversal rejection; rollback leaves no partial skeleton)
- [x] Audit output lists all created and preserved artifacts. (JSON report `created`/`preserved`)
- [x] `init.md` mechanical inventory is represented in the scaffold spec. (`agents/scripts/scaffold-map.yaml`)

## Review Provenance

Story-level signoff is recorded in the parent `STATUS.md`.

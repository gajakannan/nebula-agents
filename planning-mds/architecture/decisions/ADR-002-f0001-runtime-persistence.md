# ADR-002: Atomic JSON Snapshots Plus Append-Only JSONL Runtime Events

## Status

- [ ] Proposed
- [x] Accepted
- [ ] Superseded
- [ ] Rejected

**Accepted:** 2026-07-13T21:39:29-04:00 by explicit operator approval.

## Context

The cockpit needs fast current-state reads after restart and immutable evidence of launch, validation, gate, transcript, and recovery actions. It is single-host and local-only. A database would add installation, migration, backup, and failure modes before F0001 needs cross-run queries or multi-user coordination. A single mutable JSON file would lose history and be vulnerable to concurrent command corruption. Pure event sourcing would make basic status recovery needlessly complex.

## Decision Drivers

- Human-inspectable and machine-validated local state.
- Crash-safe writes and deterministic recovery.
- Append-only audit evidence for every mutation.
- No server/database prerequisite.
- Stable handoff to F0003 indexing and metrics.

## Decision

Each run uses:

- one owner-only atomic `run.json` snapshot with `schema_version`, monotonic `revision`, `created_at`, and `updated_at`;
- one owner-only append-only `events.jsonl` stream with contiguous per-run `sequence` values;
- one per-run advisory lock for all mutations.

Mutation validates the current snapshot and expected revision under lock, appends and syncs the event, writes the next snapshot through a same-directory temporary file, syncs it, atomically replaces the target, and syncs the directory. If the snapshot commit fails after event append, recovery deterministically replays unapplied events.

Snapshots and events follow committed JSON Schemas. Corrupt files are preserved for diagnosis. F0001 does not implement deletion, soft delete, automated retention, cross-run transactions, or analytics.

## Options Considered

1. **Atomic JSON + JSONL:** Selected.
2. **SQLite:** Rejected for MVP; strong local option later, but adds schema migrations and does not remove the need for exportable event evidence.
3. **One JSON document containing audit arrays:** Rejected; unbounded rewrites and poor append durability.
4. **JSONL event sourcing only:** Rejected; slower and more complex for ordinary status/list projections.
5. **Markdown state:** Rejected as authoritative persistence; weak validation and unsafe concurrent mutation.

## Pros / Cons

**Atomic JSON + JSONL**
- Pro: simple local operations and recovery.
- Pro: current reads are bounded while history stays immutable.
- Pro: easy schema validation and F0003 ingestion.
- Con: requires careful two-file commit/replay logic.
- Con: cross-run queries scan snapshots until F0003 adds an index.

**SQLite**
- Pro: transactions and queries.
- Con: premature migration and operational surface for the F0001 scale target.

## Consequences

- Every event reducer must be deterministic and idempotent by `(run_id, sequence)`.
- Integration tests must terminate writers at each commit seam and prove recovery.
- File permissions and path containment are part of the persistence contract.
- F0003 may index these records but cannot silently redefine their meaning.

## Security & Compliance Notes

- Runtime directory defaults to `0700`; files default to `0600`.
- Payloads are bounded and sanitized before append.
- Credential contents and raw transcript chunks are prohibited from both files.

## References

- [Data model](../data-model.md)
- [Runtime-event schema](../../schemas/f0001-runtime-event.schema.json)
- [Run-record schema](../../schemas/f0001-run-record.schema.json)

## Follow-up Actions

- [x] Define the schemas and recovery workflow.
- [ ] At feature G0, specify lock implementation and failure-injection tests.
- [x] Accepted through the Phase B operator approval gate.

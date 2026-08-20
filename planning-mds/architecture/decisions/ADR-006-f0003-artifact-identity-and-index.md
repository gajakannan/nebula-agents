# ADR-006: Run-Scoped Artifact IDs With Content Hashing in an Atomic Index

## Status

- [x] Proposed
- [ ] Accepted
- [ ] Superseded
- [ ] Rejected

## Context

F0003-S0004 requires every evidence artifact — transcript, command log, validator output,
manifest, status, metric, learning proposal — to receive an identifier that is *stable
across reloads*, unique within a run, and usable as the join key from summaries
(S0005), MCP responses (S0003), and learning proposals (S0006) back to full local
evidence.

Two properties are in tension. Stability across reloads argues for deriving the ID from
something intrinsic, so re-indexing the same artifact yields the same ID. Uniqueness
argues against pure content derivation, because S0004 explicitly requires that
"duplicate artifact content is indexed twice; IDs remain unique while content hash links
duplicates" — two distinct artifacts may legitimately hold identical bytes.

## Decision Drivers

- Stable across re-index, restart, and machine.
- Unique even when content collides.
- Traceable back to a local path without embedding one.
- Cheap enough to compute during indexing.
- No central allocator or database.

## Decision

An artifact ID is `{run_id}/{artifact_kind}/{path_digest12}`, where `path_digest12` is the
first 12 hex characters of SHA-256 over the artifact's **canonical path relative to the
run root**. Identity is therefore derived from *location within the run*, which is what
actually stays constant across reloads.

Content hashing is kept but serves a different purpose: `content_hash` is a full SHA-256
of the bytes, recorded as an attribute. It powers duplicate detection and staleness
checks. It does not participate in identity, which is what lets two artifacts with equal
bytes keep distinct IDs.

The index is one atomic JSON document per run at `{runtime_dir}/{run_id}/artifacts.json`,
written with the same discipline ADR-002 established for `run.json`: per-run lock,
monotonic `revision`, same-directory temporary file, `fsync`, atomic replace, corrupt
files preserved. It is a projection — losing it costs a re-index, never evidence.

Path containment is validated before an entry is admitted: the resolved canonical path
must be inside the run's workspace, runtime, or evidence root. Symlinks are resolved
before the check, never after.

## Options Considered

1. **Run-scoped path digest + separate content hash:** Selected.
2. **Content hash as the identity:** Rejected. Violates the S0004 duplicate requirement,
   and an artifact that is still being written changes identity as it grows.
3. **Sequential integers per run:** Rejected. Stable only if the index survives and the
   discovery order never changes; re-indexing after a partial loss renumbers everything,
   which breaks every summary and proposal reference.
4. **Random UUID per entry:** Rejected. Unique but not stable — re-indexing mints new IDs
   for the same artifact, so references rot silently.
5. **Full relative path as the ID:** Rejected. Stable and unique, but leaks local
   directory structure into MCP responses and proposal records, and paths exceed
   comfortable identifier length.
6. **SQLite index:** Rejected for the same reasons as ADR-002 — migrations and an
   operational surface F0003's scale does not need.

## Pros / Cons

**Path digest + content hash**
- Pro: re-indexing is idempotent; the same artifact keeps its ID.
- Pro: duplicates stay distinct while remaining linkable by `content_hash`.
- Pro: the ID reveals run and kind for debugging without exposing a filesystem layout.
- Con: moving an artifact within a run changes its ID; moves must be treated as
  delete-plus-add, and the index records the prior ID in `superseded_by`.
- Con: 12 hex characters is a truncation; collision within one run and kind is possible
  in principle and must fail loudly rather than silently overwrite.

## Consequences

- Indexing is idempotent and safe to re-run; this is the recovery path when the index is
  lost or corrupt.
- A truncated-digest collision within a run+kind must raise a conflict, not overwrite.
- `retrieval_policy` (`LocalOnly`, `SummaryOnly`, `Blocked`, `Missing`) and
  `redaction_status` are index attributes, so exposure decisions do not require reading
  the artifact.
- An artifact that disappears after indexing keeps its entry with
  `freshness_status: missing` — references stay resolvable and explain themselves.
- F0002 can adopt the same scheme for managed runs because nothing in it assumes tmux.

## Security & Compliance Notes

- The index is owner-only (`0600`) in a `0700` directory.
- Entries store paths but the index is never exposed wholesale through MCP; responses
  project a bounded subset (ADR-007).
- Path containment uses resolved canonical ancestry, never string prefixes
  (SOLUTION-PATTERNS §5).
- A failed redaction sets `redaction_status: Fail` and forces `retrieval_policy: Blocked`;
  summary exposure is refused until it is resolved.

## References

- [ADR-002: runtime persistence](./ADR-002-f0001-runtime-persistence.md)
- [ADR-008: deterministic summaries](./ADR-008-f0003-deterministic-summaries.md)
- [Data model](../data-model.md)
- [F0003 runtime contract](../f0003-runtime-contract.md)

## Follow-up Actions

- [ ] At feature G0, fix the digest length after estimating artifact counts per run.
- [ ] Specify the `superseded_by` transition for artifacts moved within a run.

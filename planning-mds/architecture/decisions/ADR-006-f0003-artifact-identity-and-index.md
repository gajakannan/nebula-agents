# ADR-006: Run-Scoped Artifact IDs With Content Hashing in an Atomic Index

## Status

- [ ] Proposed
- [x] Accepted
- [ ] Superseded
- [ ] Rejected

**Accepted:** 2026-08-29T11:15:45-04:00 by explicit operator approval.

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

An artifact ID is `{run_id}/{artifact_kind}/{root_key}-{path_digest12}`:

- `root_key` is `ws`, `rt`, or `ev` — the approved root that owns the artifact
  (workspace, runtime, or evidence).
- `path_digest12` is the first 12 hex characters of SHA-256 over the artifact's canonical
  path **relative to that owning root**, in POSIX form.

Identity is therefore derived from *location within a named root*, which is what actually
stays constant across reloads.

### Root selection

S0004 admits three approved roots, and they nest in practice: the evidence root and the
default runtime directory both sit inside the workspace, while `NEBULA_AGENTS_RUNTIME_DIR`
can move the runtime root outside it entirely. A fixed root order would therefore give
different answers under different configurations, and "relative to the run root" has no
value at all for an artifact outside the run directory.

The owning root is resolved deterministically:

1. Resolve all three roots to canonical absolute paths, with symlinks resolved.
2. The owning root is the **longest** resolved root that is an ancestor of the artifact's
   canonical path. Longest-match makes the result independent of configuration order and
   correct under any nesting.
3. If two roots resolve to the same path, break the tie in the fixed order
   runtime > evidence > workspace.
4. If no root is an ancestor, indexing fails and records a policy violation. This is the
   existing S0004 requirement and is unchanged.

The chosen root is recorded on the entry as `source_root`, so an entry is self-describing:
a reader can interpret an ID without holding the configuration that produced it.

### Content hashing

Content hashing is kept but serves a different purpose: `content_hash` is a full SHA-256
of the bytes, recorded as an attribute. It powers duplicate detection and staleness
checks. It does not participate in identity, which is what lets two artifacts with equal
bytes keep distinct IDs.

### Index storage

The index is one atomic JSON document per run at `{runtime_dir}/{run_id}/artifacts.json`,
written with the same discipline ADR-002 established for `run.json`: per-run lock,
monotonic `revision`, same-directory temporary file, `fsync`, atomic replace, corrupt
files preserved. It is a projection — losing it costs a re-index, never evidence.

Path containment is validated before an entry is admitted, as part of step 4 above.
Symlinks are resolved before the check, never after.

### Digest length

12 hex characters, fixed here rather than deferred. Collision handling does not depend on
the length being generous: a digest collision within the same run, kind, and root raises a
conflict rather than overwriting (see Consequences), so a collision is a loud failure, not
silent corruption.

## Options Considered

1. **Root-scoped path digest + root discriminator + separate content hash:** Selected.
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

Root-selection alternatives, considered separately:

7. **Digest relative to the run root only:** Rejected — this was the original decision and
   the defect C1 identified. It has no defined value for an artifact outside the run
   directory, which includes the evidence-package `manifest` and `validator-output` kinds
   S0004 names explicitly.
8. **Digest relative to the workspace root always:** Rejected. One base for every
   artifact, but the runtime root can be relocated outside the workspace by
   `NEBULA_AGENTS_RUNTIME_DIR`, so the ambiguity returns for exactly the artifacts most
   likely to be indexed.
9. **Digest the absolute canonical path:** Rejected. Unambiguous on one machine, but the
   ID becomes machine-specific — two checkouts of the same evidence package compute
   different IDs, so evidence stops being portable.
10. **Fixed root precedence rather than longest-match:** Rejected. Correct only for the
    default layout; a relocated runtime root or a nested evidence root silently changes
    which root wins, and therefore changes every ID.

## Pros / Cons

**Root-scoped path digest + discriminator**
- Pro: defined for every artifact in every approved root, under any nesting.
- Pro: re-indexing is idempotent; the same artifact keeps its ID.
- Pro: duplicates stay distinct while remaining linkable by `content_hash`.
- Pro: the ID reveals run, kind, and root for debugging without exposing a filesystem
  layout; `source_root` makes the entry readable without the producing configuration.
- Pro: portable — the same evidence package computes the same IDs on another machine.
- Con: the ID is three characters longer, and callers must treat `root_key` as opaque
  rather than parsing it for a path.
- Con: relocating an approved root re-homes every artifact under it and changes those IDs;
  this is a configuration change, and re-indexing is the migration.
- Con: moving an artifact within a root changes its ID; moves are delete-plus-add, with
  the prior ID recorded in `superseded_by`.
- Con: 12 hex characters is a truncation; collision within one run, kind, and root is
  possible in principle and must fail loudly rather than silently overwrite.

## Consequences

- Indexing is idempotent and safe to re-run; this is the recovery path when the index is
  lost or corrupt.
- Root resolution runs once per artifact at index time, and `source_root` is persisted, so
  reads never re-derive it.
- A truncated-digest collision within a run, kind, and root must raise a conflict, not
  overwrite.
- Relocating an approved root is a migration: IDs under it change, and the remedy is a
  re-index. Implementations must not attempt to rewrite existing IDs in place.
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

- [x] Fix the digest length. Resolved in this revision: 12 hex, decided here rather than
      deferred to G0. The earlier "decide at G0" follow-up contradicted the committed
      schema, which already pinned 12 (plan-review finding M2).
- [ ] Specify the `superseded_by` transition for artifacts moved within a root.
- [ ] At feature G0, decide whether `source_root` values are also surfaced through MCP
      responses or remain index-internal.
- [x] Accepted through the Phase B operator approval gate.

## Revision History

- **2026-08-19 — initial draft.** Identity derived from the path "relative to the run
  root".
- **2026-08-21 — root discriminator added.** Plan-review run `2026-08-19-ec0a97ce` raised
  C1: the original rule had no defined value for artifacts outside the run directory,
  while S0004 admits three approved roots. Identity is now root-scoped with an explicit
  `root_key`, and root selection is longest-match with a fixed tiebreak. M2 resolved in
  the same pass. The ADR remains `Proposed`; this revision precedes any approval.
- **2026-08-29 — accepted.** The root-scoped identity rule above is the approved one; the
  Phase B operator approval was recorded against plan-review run `2026-08-22-5ed12b9c`.

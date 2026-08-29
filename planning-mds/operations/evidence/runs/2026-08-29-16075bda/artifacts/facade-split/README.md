# Checkpoint A evidence — audit-stream invariance across the S0007 split

F0003-S0007 requires the audit stream to be **byte-identical for an identical operation
sequence** across the query/command split: every mutating operation appends the same
runtime event type and payload shape as before, and query-facade operations append **no**
event at all.

## Method

`audit_harness.py` builds an `Application` against a temporary workspace, performs one
authorized `launch` with a fake provider and tmux adapter, then calls two query-facade
methods (`sessions`, `recovery_candidates`). It dumps every `events.jsonl` line with keys
sorted.

It was run against two trees:

| Stream | Tree |
|--------|------|
| `audit-stream-pre-split.txt` | `main` before the split, via `git worktree --detach` |
| `audit-stream-post-split.txt` | this branch, after the split |

Four fields are inherently per-run random and are normalised, not compared:
`occurred_at` (`<TS>`), `run_id` (`<RUNID>`), `correlation_id` (`<UUID>`), and the
run-derived tmux session suffix (`<SESSION>`). Everything that carries meaning — event
type, ordering, `sequence`, payload keys and values, actor, `schema_version` — is compared
verbatim.

An earlier run of this comparison *did* differ, on exactly those four fields and nothing
else. That is recorded here rather than hidden: it is what established the normalisation
is isolating randomness and not masking a behavioral change.

## Result

`diff` is empty — **byte-identical**.

The stream contains exactly two events, `LaunchRequested` then `RunLaunched`. The two
query calls contributed nothing, which is the second half of the criterion.

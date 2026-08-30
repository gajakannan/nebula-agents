# Acceptance-Criteria Coverage Audit — F0003, run 2026-08-29-16075bda

Produced at Step 8. Maps every story's acceptance criteria to the test that closes it, and
states plainly what is **not** covered.

**192 F0003 tests** within a suite of **709**, green on Python 3.11, 3.12, and 3.14.

## S0001 — Runtime command surface and wrap launch

| Criterion | Test |
|-----------|------|
| `wrap` runs preflight, creates a run, records provider/workspace/action/feature/runtime dir/session ref | `test_wrap_launch.py::test_wrap_probes_guards_and_then_launches` |
| Delegates to the native launcher without storing provider credentials | `test_wrap_launch.py::test_wrap_calls_f0001_launch_unchanged` + `test_f0003_boundaries.py` sentinel sweep |
| `sessions` lists the run | `test_f0003_lifecycle.py` |
| `status` returns human- and machine-readable output | `test_f0003_lifecycle.py` (`--format json`), F0001 `test_cli.py` (table) |
| Launch audit entries are written | `test_artifact_index.py`, `test_learning_proposals.py` event assertions |
| Missing required capability blocks launch and points at the report | `test_wrap_launch.py::test_a_blocked_wrap_creates_no_run_and_starts_no_session` |
| Blocked launch is exit 3, distinct from 5 and 8 | `test_capability_matrix.py::test_the_guard_raises_exit_3_naming_the_failing_capability` |

**Inherited from F0001, unchanged and still covered by its tests:** run-ID collision
rejection, runtime-directory creation denial, launch-metadata write failure, and stale
session-reference reconciliation. `wrap` calls `RunService.launch` unmodified — asserted —
so these paths are not re-tested here rather than being untested.

## S0002 — Provider capability matrix and launch guards

Fully covered. `test_capability_matrix.py` (19 tests) covers the four requirement levels
against the four probe results, missing provider, probe timeout, missing tmux,
authentication-attention, stale-report re-probe, fresh-report reuse, and redaction of
secret-bearing version output. `test_wrap_launch.py` covers the guard in place.

## S0003 — MCP status and evidence tools

**NOT COVERED — not implemented.** Step 7 is deferred pending **M1** (`nebula-agents mcp
install` versus documented manual host configuration). No test in this suite asserts
anything about the six MCP tools, and no partial implementation exists to mislead a
reader.

What *is* already in place for it: the query-only facade the adapter must be constructed
with (`test_facade_split.py`), and the `f0003-mcp-response` schema, which
`test_f0003_record_schemas.py` explicitly records as unexercised with the reason.

## S0004 — Evidence artifact store and retrieval index

Fully covered. `test_artifact_identity.py` (14) covers identity, longest-match root
selection under all three nesting configurations, the tiebreak, containment, duplicate
content, and digest collision. `test_artifact_index.py` (10) covers atomic publish,
idempotent re-index, optimistic concurrency, corrupt-index recovery, missing artifacts,
symlink escape, and the audit event.

## S0005 — Deterministic transcript, log, and validator summaries

Fully covered. `test_summary_determinism.py` (14) proves determinism across repeated
calls, separate processes, and three interpreter versions, against a corpus authored
before the extractors. `test_evidence_summarize.py` (7) covers persistence, index update,
unsupported kinds, missing sources, and the audit event.

## S0006 — Runtime metrics and failure-learning review

Fully covered. `test_metrics_derivation.py` (13) covers the closed metric set,
`derived_from` pinning, inapplicable-versus-zero, and worst-entry freshness.
`test_learning_proposals.py` (11) covers clean runs, stale-evidence blocking, sticky
rejection in both directions, target-document authorization, append-only decisions, and
inertness on disk.

## S0007 — Application query/command service split

Fully covered. `test_facade_split.py` (8) plus the 514 pre-existing F0001 tests passing
unmodified, plus the audit-stream invariance evidence in `artifacts/facade-split/`.

## Cross-cutting, added at Step 8

| Concern | Test |
|---------|------|
| Inward dependency rule | `test_layering.py` — added at Step 5 after a real violation |
| No model call reachable from a summarizer | `test_layering.py` — import-level, structural |
| Owner-only modes on every F0003 store | `test_f0003_boundaries.py` |
| Symlink resolved before containment | `test_f0003_boundaries.py` |
| End-to-end credential sentinel sweep | `test_f0003_boundaries.py` |
| Proposal target allowlist, including schema and policy paths | `test_f0003_boundaries.py` |
| No new required dependency (ADR-005/007) | `test_package_contract.py` + verified clean install |
| Full operator lifecycle through the CLI | `test_f0003_lifecycle.py` |

## Known gaps, stated rather than implied

1. **S0003 is entirely unimplemented and untested.** Blocked on M1.
2. **The lifecycle test patches the provider and tmux seams.** A real provider process is
   exercised only by F0001's `test_real_tmux_lifecycle.py`, which runs and does not skip.
   F0003 adds no new subprocess path — `wrap` calls F0001's `launch` unchanged — so this
   is a deliberate boundary, not an omission.
3. **`metrics` `gate_wait_seconds` uses the gate's `updated_at`.** Where a gate has none,
   the run's is used. That is an approximation; a dedicated gate-transition timestamp
   would be exact and belongs to whoever revisits gate state.

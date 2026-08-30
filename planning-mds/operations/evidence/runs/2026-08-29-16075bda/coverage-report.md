# Coverage Report — F0003

**Run:** `2026-08-29-16075bda` · **Gate:** G2 · **Owner:** Quality Engineer · **Date:** 2026-08-29
**Result: PASS**

## Totals

| Measure | Value | Floor |
|---------|-------|-------|
| Line | **92.30%** (5484 / 5942) | `coverage_min_pct` (`_contract.yaml`) |
| Branch | **82.71%** (1439 / 1740) | not separately floored |

Machine-readable: `artifacts/test-results/coverage.xml`.

Branch coverage is reported because the first evidence run recorded `branch-rate 0` — the
`--cov-branch` flag was absent, not the branches. Recorded so the zero is not read as a
result.

## F0003 modules

| Module | Line |
|--------|------|
| `domain/enums.py` | 100% |
| `infrastructure/schema_registry.py` | 100% |
| `application/commands.py` | 100% |
| `domain/summaries.py` | 98% |
| `domain/proposals.py` | 98% |
| `application/learning.py` | 97% |
| `domain/artifacts.py` | 97% |
| `domain/capabilities.py` | 96% |
| `application/capabilities.py` | 95% |
| `infrastructure/artifact_index.py` | 95% |
| `infrastructure/proposal_store.py` | 95% |
| `application/evidence.py` | 95% |
| `infrastructure/summarizers.py` | 94% |
| `application/metrics.py` | 93% |
| `presentation/mcp_server.py` | 92% |
| `infrastructure/capability_probe.py` | 88% |
| `infrastructure/atomic.py` | 84% |

## What the uncovered lines are

`infrastructure/atomic.py` at 84% is the lowest, and deliberately so: the uncovered lines
are `OSError` branches on `flock`, `fsync`, and `os.replace` — filesystem failures that
cannot be provoked without a fault-injecting filesystem. They are defensive paths that
convert an OS error into a typed `NebulaError`; the conversion is uniform and the
alternative to leaving them uncovered is a mock that asserts the mock.

`capability_probe.py` at 88% is the same shape: unreadable-report and malformed-JSON
branches that return `None` so a missing report reads as "re-probe".

This is stated rather than left for a reviewer to infer, because a coverage number without
an account of its gap is a number, not evidence.

## Risk modules

The modules carrying security-relevant logic are all above the total: `domain/artifacts.py`
(containment, identity) 97%, `domain/proposals.py` (target allowlist) 98%,
`infrastructure/schema_registry.py` (schema allowlist) 100%. `test_f0003_boundaries.py`
exercises each against attack-shaped input in addition to the line coverage above.

## Verdict

**PASS** — line coverage exceeds the contract floor with margin, and the shortfall is
accounted for rather than averaged away.

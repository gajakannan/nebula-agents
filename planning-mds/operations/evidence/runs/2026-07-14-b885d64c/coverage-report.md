# F0001 Remediation Coverage Report — run 2026-07-14-b885d64c

## Summary

| Metric | Covered | Valid | Rate | Gate |
|--------|---------|-------|------|------|
| Lines | 4,189 | 4,620 | 90.67% | PASS (minimum 85%) |
| Aggregate branches | 1,197 | 1,472 | 81.32% | Informational; no aggregate branch threshold |

## Mandatory Risk Modules

| Module | Covered branches | Valid branches | Rate | Gate |
|--------|------------------|----------------|------|------|
| `application/authorization.py` | 42 | 42 | 100% | PASS |
| `domain/transitions.py` | 24 | 24 | 100% | PASS |
| `domain/redaction.py` | 26 | 26 | 100% | PASS |
| `presentation/session_entry.py` | 60 | 60 | 100% | PASS |

## Method

Coverage was collected by the exact acceptance command in `test-execution-report.md` with `--cov-branch`, the committed `engine/pyproject.toml` coverage configuration, the official Cobertura XML reporter, and `--cov-fail-under=85`. The command exited 0. The XML contains branch data and reports branch-rate `1` for each mandatory risk module.

## Raw Artifact

- Path: `artifacts/test-results/coverage.xml`
- Size: 212,114 bytes
- SHA-256: `aa55e2cdb15495bb1c573703922a20cf13e716fb141c3dd53f669bafe9bc906f`

## Waiver

No line or risk-module branch coverage waiver applies.

## Result

PASS

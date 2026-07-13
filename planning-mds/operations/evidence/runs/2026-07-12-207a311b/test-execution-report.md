# F0006 Recovery Test Execution Report

## Framework Results

198 tests passed across `agents/product-manager/scripts/tests` and `agents/scripts/tests`.
Contract audit, agent-map validation, and prompt-template validation passed.

## Reference Product Results

182 KG tests passed. Four assertions are stale post-F0006 expectations (story/node counts, tracker
placement/order, lookup source-doc order); one MCP workstate test could not write into the sandboxed
reference checkout. The shipped F0006 implementation commits remain on `main` in both repositories.

## Disposition

The current failures are not regressions introduced by the archive recovery. They remain explicit
maintenance follow-ups; the recovery does not rewrite historical test results.

Result: PASS

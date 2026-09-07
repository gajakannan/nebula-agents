# F0009 — Project-owned instructions and required checks

**Status:** Planned — candidate implementation under review; not released or approved.

This tooling work adds an optional product manifest, instruction loader, strict Python check executor, PR2/PR4 enforcement, and durable evidence. Product requirements never enter the generic framework. It builds on F0007's gate runtime and prompt compiler without replacing their core operations or existing renderer changes.

Contract and usage: [Project extensions](../../../agents/docs/PROJECT-EXTENSIONS.md).

Acceptance: product isolation, explicit root binding, strict result handling, preserved framework failures, unchanged-input resume, stale-result rejection, and no-write preview operations are regression tested. Native host adapter support is not included. Framework publication and downstream pin coordination remain required.

This reserved tracker entry does not assert completion of a plan/feature lifecycle or signoff. PRD, story decomposition, and delivery evidence remain subject to the normal review process.

## Stories

| ID | Title | Status |
|----|-------|--------|

**Total Stories:** 0

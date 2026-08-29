# ADR-005: F0003 Extends the Existing Local Package Rather Than Adding a Service

## Status

- [ ] Proposed
- [x] Accepted
- [ ] Superseded
- [ ] Rejected

**Accepted:** 2026-08-29T11:15:45-04:00 by explicit operator approval.

## Context

F0001 delivered a single local Python executable under `engine/` with Presentation,
Application, Domain, and Infrastructure layers, and it deliberately excluded an MCP
surface, artifact index, metrics store, and learning loop (BLUEPRINT §4.8). F0003 adds
exactly those four surfaces plus a provider capability matrix.

The question is where they live. F0003 must serve two consumers with different process
models: an operator at a terminal running commands, and an MCP host that speaks stdio to
a child process. It must also leave stable contracts behind for F0002 without becoming a
daemon, because a background service would reintroduce the lifecycle, port, and
multi-user concerns F0001 was scoped to avoid.

## Decision Drivers

- Reuse F0001's layering rather than growing a parallel one.
- No always-on process, port, or installation step beyond the existing package.
- The MCP surface must be a child process the host owns, not a server Nebula manages.
- Read paths must be usable when no run is active.
- F0002 needs importable contracts, not scraped output.

## Decision

F0003 extends the existing `engine/` package. It adds application services and
infrastructure adapters beside F0001's, and two new presentation entry points:

- new `nebula-agents` subcommands (`wrap`, `providers doctor`, `evidence *`, `metrics`,
  `learn review`) on the existing console script;
- a `nebula-agents mcp serve` subcommand that speaks MCP over stdio on the process the
  host spawns, and exits with it.

No new distributable, no daemon, no port, no database. The MCP surface is a presentation
adapter over the same application services the CLI calls — it never reaches into the
filesystem or registry directly, so a read-only guarantee proven at the application layer
holds for both surfaces at once.

F0003 owns the artifact index, capability reports, summaries, metrics, and learning
proposals. It does not modify F0001's `RunRecord`/`RuntimeEvent` semantics; it reads them
and writes its own records alongside (ADR-002: "F0003 may index these records but cannot
silently redefine their meaning").

## Options Considered

1. **Extend `engine/`:** Selected.
2. **Separate `control-plane/` package:** Rejected. Both packages would need F0001's
   domain models, ports, path-containment, and redaction; the seam would be duplicated
   code or a circular dependency, and the operator would install two things.
3. **Long-running local daemon with a socket:** Rejected. Adds lifecycle, stale-socket,
   permission, and single-instance concerns for no benefit — every F0003 read is a
   filesystem read that a short-lived process does equally well.
4. **HTTP service on localhost:** Rejected. A port is a multi-user surface on a shared
   host, and it contradicts F0001's local trust boundary.
5. **Fold the MCP tools into the existing `scripts/kg/mcp_server.py`:** Rejected. That
   server projects the knowledge graph, which is planning-time data; runtime state is a
   separate concern with a separate lifetime and different redaction rules.

## Pros / Cons

**Extend `engine/`**
- Pro: one install, one layering, one redaction and path-containment implementation.
- Pro: the read-only MCP guarantee is enforced once, at the application boundary.
- Pro: F0002 imports the same services rather than parsing CLI output.
- Con: `engine/` grows; module ownership must stay legible as F0003 lands.
- Con: CLI and MCP entry points share a process model that suits neither perfectly.

**Separate package**
- Pro: crisp ownership boundary per feature.
- Con: duplicated domain and security primitives, or a dependency cycle.

## Consequences

- New F0003 modules follow F0001's inward dependency rule; the domain stays free of
  subprocess, filesystem, and transport imports.
- `engine/pyproject.toml` gains no required runtime dependency for the MCP surface
  (see ADR-007).
- Module-level ownership must be documented as F0003 lands so `engine/` stays navigable.
- Coverage thresholds apply to the whole package, so F0003 code carries F0001's bar.

## Security & Compliance Notes

- The MCP child process inherits the spawning host's OS identity; authorization still
  evaluates the default-deny subject/resource/action contract per call.
- No new listening socket, port, or credential store is introduced.

## References

- [ADR-002: runtime persistence](./ADR-002-f0001-runtime-persistence.md)
- [ADR-007: read-only MCP surface](./ADR-007-f0003-readonly-mcp-surface.md)
- [Solution patterns](../SOLUTION-PATTERNS.md)
- [F0003 runtime contract](../f0003-runtime-contract.md)

## Follow-up Actions

- [ ] At feature G0, fix the module map for the new application/infrastructure units.
- [ ] Confirm the `mcp serve` subcommand name against host configuration conventions.
- [x] Accepted through the Phase B operator approval gate.

# G0 Assembly Plan Validation — F0003 run 2026-08-29-16075bda

## Run Identity

- Feature: F0003 — Local Agent Runtime Control Plane
- Gate: G0
- Reviewer: Architect Agent
- Reviewed on: 2026-08-29
- Plan: `planning-mds/features/F0003-local-agent-runtime-control-plane/feature-assembly-plan.md`
- Phase B approval: `2026-08-29T11:15:45-04:00` (BLUEPRINT §5.9); ADR-005…009 `Accepted`
- Plan-review verdict this run builds on: `2026-08-22-5ed12b9c` — READY,
  `requires_justification: false`

## Scope Review

The plan covers all seven stories through the existing local Python package. It includes the
query/command facade split, domain records and artifact identity, the per-run artifact index,
provider capability probing with the wrapped launch guard, deterministic summarizers, metrics
derivation, the learning-proposal workflow, the stdio MCP adapter, and the test/evidence
closure.

Excluded and confirmed excluded in the plan: HTTP service, database, daemon, listening port,
managed provider SDK, automatic document mutation, and any terminal-UI surface. The CLI-only
boundary is carried from PRD *UX / Surfaces* and BLUEPRINT §5.8 into the plan's Scope
Breakdown, which states "no UI framework, no screens" against the presentation row rather
than leaving it implicit.

Story-to-step coverage is total and non-overlapping:

| Story | Steps |
|-------|-------|
| S0001 | 4 |
| S0002 | 2, 4 |
| S0003 | 7 |
| S0004 | 2, 3 |
| S0005 | 2, 5 |
| S0006 | 2, 6 |
| S0007 | 1 |

## Architecture Reconciliation

- Package extension, no service or daemon, no new required dependency — matches ADR-005 and
  BLUEPRINT §5.1. The plan's DI section keeps domain and application free of infrastructure
  and presentation imports.
- Artifact identity, longest-match root selection, the `runtime > evidence > workspace`
  tiebreak, the fixed 12-hex digest, and `content_hash` as attribute-not-identity all match
  ADR-006. The plan reproduces the rule as executable code rather than restating it in prose.
- The MCP adapter constructed with a query-only facade, plus a second `ReadState` check as
  defense in depth, matches ADR-007. The plan names the failure mode ADR-007 targets: passing
  `app.commands` to `McpServer` is the visible architectural edit.
- Rule-based extraction with no model call, `rule_set_version` stamping, and the rule that
  failure markers are never dropped for size (`Partial`, not `Pass`) match ADR-008.
- Inert proposals, generation-time allowlist enforcement, append-only attributed decisions,
  sticky rejection pinned to source `content_hash`, and `accept` never opening the target
  document all match ADR-009.
- The three added actions, `RunValidator` keeping its F0001 meaning, and `DecideProposal`
  resolving against the target document match BLUEPRINT §5.4 and
  `security/f0001-authorization-model.md` § *F0003 Action Extensions*.
- Commands, MCP tool names, exit-code mappings, input rules, and record contracts match
  `architecture/f0003-runtime-contract.md` at version `1.1`.
- All six committed schemas are consumed; no record in the plan carries a field absent from
  its schema, and every schema-required field appears.

## Dependency And Ownership Review

Step ordering is a genuine dependency chain, not a preference. Two orderings are hard
constraints and the plan states both: S0007 must land before S0003, because the MCP adapter
cannot be constructed with a query-only facade that does not exist; and domain identity
(Step 2) precedes the index (Step 3), which precedes everything that reads it.

Ownership is unambiguous. Backend owns runtime and presentation modules — correctly assigned
to one role here rather than split, because F0003 adds no UI and the "presentation" layer is
argparse plus a stdio adapter. QE owns executable evidence, Security owns the security
verdict, Architect owns shared contracts and G7 reconciliation, PM alone owns G8 closeout. No
two roles hold conflicting ownership of the same canonical semantics.

The plan correctly assigns **no** AI-scope work: rule-based extraction and MCP transport are
not LLM workflows, and ADR-008 excludes model-generated summaries by decision.

## Mutation And Audit Review

All seven mutating entry points name their service method, record, authorization action,
concurrency guard, failure class, runtime event, and restart proof. The read surfaces —
`evidence list|show`, `metrics`, `learn list|show`, and all six MCP tools — are listed with
audit "none", which matches BLUEPRINT §5.3's rule that read-only queries create no runtime
events.

Two review points worth recording:

- The plan makes the read/write boundary **testable rather than asserted**: Checkpoint A
  requires the runtime tree to be byte-identical after executing every query method, which is
  what catches a query that lazily initializes state. That is S0007's named edge case, and
  the plan closes it with a check rather than a promise.
- `DecideProposal`'s traceability row states the resource is the target document and gives
  the test expectation — a run owner lacking the target role is denied. This is the rule a
  Security Reviewer needs to verify, and it is present at the point of enforcement rather
  than only in the ADR.

## Integration And Test Review

Five checkpoints (A–E) sit at real risk boundaries rather than at step counts. Each carries
falsifiable criteria: byte-identical audit streams, ID stability across a moved runtime root,
the three-root nesting configurations with a deliberate tie, byte-identical summaries across
two interpreter versions, and structural unreachability of mutating services from
`McpServer`.

The acceptance-criteria test matrix maps every story to named test files. The regression
boundary for the highest-risk step is explicit and external: the 514 existing engine tests
pass **unmodified**, with no test rewritten to accommodate the new structure.

Determinism is verified across the CI matrix (3.11 / 3.12 / 3.14), which is appropriate here
— two Python-version-specific pathlib bugs were found in this repo by exactly that matrix.

## Knowledge-Graph Prediction

The six capabilities, four entities, and two workflows are already declared in
`planning-mds/kg-source/features/F0003.yaml`; G7 binds as-built source to them. The plan
states the binding is authored as shards under `kg-source/` and compiled, and that the
generated files must never be hand-edited — which `validate.py --check-reproducible`
enforces. The shard's feature status moves `planned → in-progress` at G0.

## Findings

No blocking plan finding.

Three items are carried forward, all recorded in the plan's Risks table:

| Item | Severity | Carried to |
|------|----------|------------|
| M1 — `nebula-agents mcp install` versus documented manual host configuration | Medium | **Must be answered before Step 7 (S0003)**; does not block Steps 1-6 |
| Hand-rolled MCP protocol revision and its conformance fixtures not yet pinned | Medium | Pin during Step 7 authoring; ADR-007's adapter boundary keeps an SDK swap local |
| L1 — S0001's open question unreconciled against ADR-005 | Low | Reconcile during Step 4 authoring |

M1 is the only one with a gating effect, and it gates a step rather than the gate. The plan
sequences S0003 last, which means M1 has six steps' worth of runway before it blocks
anything — that sequencing is deliberate and is the reason M1 was accepted open at the Phase
B approval.

## Result

PASS

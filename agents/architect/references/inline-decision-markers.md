# Inline Decision Markers

Inline decision markers capture local implementation rationale that is too
small for an ADR and too code-specific for canonical-node rationale. They are
retrieval aids only. Raw source, ADRs, canonical nodes, schemas, and feature
docs remain authoritative under `solution-ontology.yaml.authority.precedence`.

Use them sparingly. A marker should explain why a non-obvious choice exists,
not narrate what the next line of code does.

---

## Marker Syntax

Use uppercase tags in ordinary comments:

```csharp
// WHY: Customer cancellation is idempotent because outbox replay is at-least-once.
public Task CancelAsync(Guid customerId, CancellationToken ct) { ... }

// DECISION: Keep order totals calculated in the aggregate to preserve invariants.
order.RecalculateTotals();

// TRADEOFF: Batch size is fixed to bound lock time during nightly order sync.
const int BatchSize = 250;

// SUPERSEDES: ADR-014 local retry note; retry policy now lives in ADR-022.
```

```typescript
// WHY: Keep this filter client-side because the order list is already fully scoped by the API.
const visibleOrders = orders.filter(matchesSelectedCustomer)

/**
 * @why Customer badges are precomputed so the grid does not recompute labels on every hover.
 */
export function CustomerBadge(...) { ... }
```

```python
# WHY: The prompt checksum includes tool schema versions so cached outputs expire after contract changes.
cache_key = build_cache_key(prompt, tool_schema_version)
```

Supported marker kinds:

| Kind | Use |
|---|---|
| `WHY` | Non-obvious local rationale, workaround, invariant, or contract-shaped logic. |
| `DECISION` | Explicit local design choice with a stable alternative. |
| `TRADEOFF` | Accepted compromise such as latency vs. accuracy or simplicity vs. flexibility. |
| `SUPERSEDES` | Inline rationale that replaces a prior ADR note or older local decision. |

---

## When to Use

Add a marker when future maintainers would otherwise need to rediscover the
reasoning by reading tickets, PR discussion, or commit history:

- A workaround for a dependency or platform limitation.
- A performance choice that looks arbitrary without context.
- Contract-shaped logic that mirrors an API, schema, or workflow invariant.
- A local compromise accepted by the architect or feature owner.

Do not add a marker for:

- Obvious mechanics, such as "loop through customers".
- Names that already explain the intent.
- General architecture decisions that belong in an ADR.
- Shared semantic rules that belong in `canonical-nodes.yaml.rationale`.

---

## Supersession Rules

`SUPERSEDES` markers must name the superseded ADR or canonical ADR node.
Accepted forms:

```text
// SUPERSEDES: ADR-014 local retry note; retry policy now lives in ADR-022.
// SUPERSEDES: adr:014 local timeout rationale.
```

Validation should fail when the referenced ADR is unknown. This keeps local
comments from silently replacing authority that the knowledge graph cannot
resolve.

Use the same mental model as `workstate.py` supersession: one active rationale
should remain for a topic. If two active `WHY` markers on the same symbol say
opposite things, validation should warn and an architect should reconcile them.

---

## Promotion Rules

During feature close:

1. Run `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/decisions.py`.
2. Review new entries in `{NEBULA_PRODUCT_ROOT}/planning-mds/knowledge-graph/decisions-index.yaml`.
3. Promote reasoning into `canonical-nodes.yaml.rationale` when it describes
   shared semantics for an entity, workflow, capability, role, or policy.
4. Keep reasoning inline when it only explains a local implementation detail.
5. Create or update an ADR when the rationale changes architecture, data
   contracts, security posture, or cross-feature behavior.
6. Validate with `python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/validate.py --check-decisions`.

Examples:

| Marker | Destination |
|---|---|
| `WHY: Customer cancellation is idempotent because outbox replay is at-least-once.` | Promote if this is the customer aggregate contract. |
| `TRADEOFF: Batch size is fixed to bound lock time during nightly order sync.` | Keep inline if only this job uses it. |
| `DECISION: Order totals are aggregate-owned, not API-computed.` | Promote to canonical rationale or ADR if it affects multiple components. |

---

## Generated Index

`decisions.py` scans files declared in `code-index.yaml` and emits:

```yaml
decisions:
  - id: decision:backend-src-customers-customer-service-l42-why
    file: backend/src/Customers/CustomerService.cs
    line: 42
    kind: WHY
    text: Customer cancellation is idempotent because outbox replay is at-least-once.
    resolved_node: entity:customer
    resolved_symbol: symbol:entity-customer:customer-service.cancel-async
```

`lookup.py --file <path>` joins decisions for that file. `lookup.py --symbol
<name>` joins decisions for matching symbols when `symbol-index.yaml` exists.

---

## Review Gate

Reviewers should block non-obvious changes that lack a marker. The blocker is
about missing rationale, not comment volume. A clean, self-explanatory change
should remain uncommented.

When markers changed, reviewers should require:

```bash
python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/validate.py --regenerate-decisions --check-decisions
```

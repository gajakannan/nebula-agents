# Data Contract Patterns

> **Examples in this guide use `customers` and `orders` as illustrative entities.
> These are not prescriptive — substitute your own domain entities when applying
> these patterns. See `BOUNDARY-POLICY.md` → "Standard Example Entities" for
> the full convention and field mapping.

---

Guide for choosing the right contract format when data crosses a system boundary. Most architects default to "API contract" (OpenAPI + JSON Schema + Pact) for every boundary, but request/response APIs are only one of three legitimate contract surfaces. Choosing the wrong one produces brittle integrations, missing freshness/quality semantics, or contracts that drift silently.

---

## 1. The Three Contract Surfaces

### 1.1 API Contracts — synchronous request/response

**When to use:** UI talking to backend. Service-to-service synchronous calls. Anywhere a consumer expects an immediate response and the boundary is per-request, not per-dataset.

**Tooling:**
- **OpenAPI 3.x** — endpoint, method, status codes, request/response shapes
- **JSON Schema** — request/response validation rules, shared between frontend and backend
- **Pact** — consumer-driven contract testing to prevent provider/consumer drift

**Strengths:** Mature ecosystem, strong tooling, granular per-endpoint versioning, good fit for transactional CRUD.

**Weaknesses:** No native semantics for freshness, dataset-level quality, lineage, batch volume, or access terms. Versioning is per-endpoint, not per-data-product. Bad fit when the consumer wants "the customers dataset as of yesterday" rather than "GET /customers/{id}".

---

### 1.2 Dataset Contracts — files, tables, batch feeds, snapshots

**When to use:** Imports from external systems. Exports to analytics warehouses, finance/billing systems, regulatory reporting. Partner batch reports. Periodic snapshots. ETL/ELT pipeline boundaries. Migration files. Anywhere the unit of exchange is a *dataset* (rows, files, tables, partitions) rather than a single entity request.

**Tooling:**
- **Open Data Contract Standard (ODCS) v3.x** — the live standard, governed by Bitol / LF AI & Data
- **Data Contract CLI** — open-source linting and validation tooling that supports ODCS
- **datacontract.com** — vendor site that hosts the CLI

**What ODCS adds beyond JSON Schema:**
- Freshness expectations (e.g. updated daily by 06:00 UTC)
- Quality rules (row counts, null-rate ceilings, referential integrity, business invariants)
- Lineage and provenance (upstream sources, downstream consumers)
- Server / location / access-terms (where the dataset lives, who can read it, retention)
- Data classification (PII, regulated, public)
- Ownership (data product owner, on-call, escalation)
- Versioning at the *data product* level, not per-field

**Critical caveat:** the older "Data Contract Specification" (datacontract-specification.com) is **deprecated**. Author against ODCS v3.x. The Data Contract CLI continues to support ODCS as tooling.

---

### 1.3 Event Contracts — streams, topics, outbox events

**When to use:** Asynchronous event publication. Outbox-style reliable delivery. Pub/sub topics. Webhooks consumed at scale. Anywhere the unit of exchange is a *message* on a stream rather than a request or a dataset.

**Tooling:**
- **AsyncAPI** — analogous to OpenAPI but for event-driven APIs. Defines channels, message schemas, bindings (Kafka, AMQP, MQTT, webhooks).
- Message payloads typically defined with **JSON Schema** or Avro.

**Strengths:** Native semantics for channels, message ordering, delivery guarantees, transport bindings. Good fit for outbox events and stream processing.

**Weaknesses:** Tooling less mature than OpenAPI. Versioning of message shapes is its own discipline.

---

## 2. Decision Matrix

| Question | API Contract | Dataset Contract | Event Contract |
|----------|:------------:|:----------------:|:--------------:|
| Sync request/response? | ✅ | | |
| Per-record retrieval? | ✅ | | |
| File / table / partition exchange? | | ✅ | |
| Periodic snapshot or batch feed? | | ✅ | |
| Quality / freshness / lineage SLAs needed? | | ✅ | partial |
| Async fire-and-forget? | | | ✅ |
| Stream / topic / outbox? | | | ✅ |
| Multiple unknown consumers? | partial | ✅ | ✅ |
| External party (regulator, carrier, vendor)? | partial | ✅ | partial |
| PII classification / access terms required? | | ✅ | partial |

A boundary can require **more than one** contract. A `customers-export-v1` dataset contract and a `customer.created.v1` event contract often coexist for the same domain entity, serving different consumers.

---

## 3. Composition, Not Replacement

Data contracts **compose with** API contracts; they don't replace them. A typical layering for a non-trivial integration boundary:

```
Internal domain model (entities, EF/ORM)
        ↓
Application API (OpenAPI + JSON Schema + Pact)
   for transactional UI/service calls
        ↓
Canonical integration model (anti-corruption layer)
        ↓
Outbound boundary
   ├─ Dataset contracts (ODCS) for batch/file/feed consumers
   └─ Event contracts (AsyncAPI) for stream/outbox consumers
        ↓
External consumers
   carriers, finance, analytics warehouse, regulators, partners
```

**What stays where:**

- Domain entities and EF migrations are not data contracts.
- JSON Schemas in `{NEBULA_PRODUCT_ROOT}/planning-mds/schemas/` remain the validation source for application API DTOs.
- Pact remains the consumer/provider behavioral check for application APIs.
- ODCS does **not** replace OpenAPI. ODCS does **not** replace JSON Schema for in-process validation.
- Server blocks in ODCS contracts must not contain real secrets — they describe location and access pattern, not credentials.

---

## 4. When Each Contract Format Earns Its Keep

### 4.1 Adopt API contracts (OpenAPI + JSON Schema + Pact)

Always, as soon as a service exposes more than one endpoint or has more than one consumer. This is baseline; not a choice.

### 4.2 Adopt dataset contracts (ODCS)

Strong signals:
- An import pipeline (customer onboarding, migration, partner data load) needs to validate inbound files before promotion.
- An outbound export feeds a system you don't control (analytics warehouse, regulatory reporting, billing).
- A consumer asks "when was this last updated?" or "what's the row-count expectation?" and the answer doesn't live anywhere queryable.
- A connector acceptance gate needs a versioned, machine-readable definition of what it produces or consumes.
- Multiple downstream consumers depend on the same dataset and drift between them is becoming costly.

Weak signals (probably don't adopt yet):
- Single consumer, single producer, internal only.
- Boundary is request/response, not dataset.
- The data is exposed *only* via the application API and no batch/file/feed extract exists.

### 4.3 Adopt event contracts (AsyncAPI)

Strong signals:
- An outbox pattern is publishing canonical events to multiple consumers.
- A pub/sub topic or stream exists and consumers need to know message shapes.
- Webhook payloads are consumed by parties outside your team.

---

## 5. Adoption Pattern: Lint-Only First

Data contracts are most often introduced *before* the runtime that produces or consumes them is built. This is fine — and arguably correct — but only with the right discipline.

**Phase 1 — Lint-only (recommended starting point):**
- Place ODCS / AsyncAPI files in a versioned location (e.g. `{NEBULA_PRODUCT_ROOT}/planning-mds/data-contracts/`).
- CI validates syntax and cross-references (e.g. referenced schemas exist).
- No runtime enforcement.
- Cost: minimal. Value: forces explicit thinking about freshness, quality, ownership before code locks in assumptions.

**Phase 2 — Producer-side validation:**
- The producer service / pipeline validates its output against the contract before publishing.
- Failures block publication or route to dead-letter.

**Phase 3 — Consumer-side validation:**
- Consumers validate inbound data against the contract version they declare.
- Mismatches surface as connector health alarms, not silent corruption.

Adopting Phase 1 alone is a legitimate and useful state. Skipping straight to Phase 3 without Phases 1–2 produces brittle integrations and contract files that have already drifted from reality.

---

## 6. Versioning

Data contract versioning is **not** the same as API versioning.

- **API versioning** is per-endpoint or per-resource, with semver and URL/header conventions.
- **Data contract versioning** is per-data-product. A `customers-export-v1` dataset contract is a stable promise to consumers; `v2` is a *new* dataset that may run in parallel during migration.

A breaking change to a dataset contract typically means publishing both `v1` and `v2` for a defined deprecation window so downstream consumers can migrate. This is closer to product lifecycle management than to typical software versioning.

The same principle applies to event contracts: a new message version is a new channel or a new schema reference, not a silent overwrite.

---

## 7. Common Anti-Patterns

**Treating every boundary as an API contract.** Forcing batch/file integrations through synthetic REST endpoints. Loses freshness, quality, and lineage semantics. Produces fragile import flows.

**Treating every boundary as a data contract.** Defining ODCS contracts for transactional UI calls. Adds ceremony without value; OpenAPI + JSON Schema already covers this.

**Storing secrets in ODCS server blocks.** Server blocks describe location and access pattern. Credentials belong in a secrets manager, referenced by name from the contract.

**Letting the domain model leak into the data contract.** Outbound dataset contracts should be expressed in the canonical integration model, not the internal entity shape. An ODCS file that is a 1:1 mirror of an EF entity is a maintenance trap — it couples external consumers to internal refactors.

**Authoring against the deprecated Data Contract Specification.** Tooling still works, but the spec is no longer the standard. Use ODCS v3.x.

**Writing contracts after the integration ships.** Contract files become drift-detection only when they precede or accompany the runtime they describe. Retroactive contracts tend to document the bug, not the intent.

---

## 8. Architect Responsibilities

When evaluating an integration boundary in a feature design:

1. Identify the **shape** of the boundary: request/response, dataset, or event.
2. Choose the contract format(s) that match — possibly more than one.
3. If a dataset or event contract is appropriate, decide adoption phase (lint-only is usually the right starting point).
4. Confirm contracts compose with the existing API contract stack rather than replacing it.
5. Document the choice in an ADR if a new contract format is being introduced for the first time, or if the boundary justifies an explicit decision record.

---

## 9. References

- Open Data Contract Standard (ODCS): https://bitol-io.github.io/open-data-contract-standard/latest/
- Data Contract CLI: https://cli.datacontract.com/
- Data Contract Specification (deprecated, do not author against): https://datacontract-specification.com/
- AsyncAPI: https://www.asyncapi.com/
- OpenAPI: https://www.openapis.org/

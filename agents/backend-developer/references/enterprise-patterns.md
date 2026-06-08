# Enterprise Microservice Patterns

Use this reference when architecture specifies microservices, event-driven
integration, CQRS, sagas, gRPC, Kafka, resilience, or observability. The guidance
is stack-agnostic unless a Python or .NET note is called out.

## 1. Domain-Driven Implementation

- Keep behavior in domain entities and value objects.
- Use immutable value objects.
- Let aggregates emit domain events during state changes.
- Persist aggregate changes and outbox rows together.
- Define repository protocols/interfaces in the domain or application boundary.
- Implement repositories in infrastructure.

Python:

```python
class OrderRepository(Protocol):
    async def get(self, order_id: UUID) -> Order | None:
        ...
```

.NET:

```csharp
public interface IOrderRepository
{
    Task<Order?> GetByIdAsync(Guid id, CancellationToken ct = default);
}
```

## 2. CQRS

- Use command handlers for writes.
- Use query handlers for reads.
- Keep write models rich and invariant-protecting.
- Keep read models flat and projection-friendly.
- Introduce a bus only when shared pipeline behavior is valuable.

## 3. Event Sourcing

Apply only when the architect specifies event sourcing.

- Store events append-only.
- Use aggregate version for optimistic concurrency.
- Reconstitute aggregate state from events.
- Snapshot every N events when rehydration becomes expensive.
- Build projections asynchronously and make them rebuildable.

## 4. Transactional Outbox

- Create `outbox_messages` with `event_id`, `event_type`, `aggregate_id`,
  `aggregate_type`, `occurred_at`, `payload`, `published_at`, and retry fields.
- Stage outbox rows in the same transaction as aggregate changes.
- Relay workers publish from the outbox to Kafka.
- Mark rows as published after message broker acknowledgement.
- Use retry count and next-attempt timestamp for transient failures.
- Move poison events to a dead-letter topic or dead-letter table after the
  configured threshold.

Python relay workers usually run as an async process using SQLAlchemy and
`confluent-kafka`. .NET relay workers usually run as `BackgroundService` with
EF Core and `Confluent.Kafka`.

## 5. Saga Activities

- Use Temporal when workflows cross service boundaries and require
  compensation.
- Make each activity idempotent.
- Add explicit timeout and retry policy to every activity.
- Add compensation activities for each irreversible step where possible.
- Store idempotency keys or workflow IDs to safely handle retries.

Python:

```python
@activity.defn
async def reserve_products(command: ReserveProducts) -> ReservationResult:
    return await handler.execute(command)
```

.NET:

```csharp
[Activity]
public Task<ReservationResult> ReserveProductsAsync(ReserveProducts command)
    => _handler.Handle(command, CancellationToken.None);
```

## 6. gRPC

- Keep `.proto` files in `shared/proto/` or the owning service `proto/`
  directory.
- Generate clients and servers from protobuf.
- Propagate deadlines, auth metadata, trace context, and request IDs.
- Add circuit breakers and retries to clients.
- Do not expose internal database shapes through protobuf contracts.

## 7. Kafka

- Use schema registry for event schemas when architecture requires Avro.
- Events include envelope fields: `event_id`, `event_type`, `aggregate_id`,
  `aggregate_type`, `occurred_at`, and `payload`.
- Producers publish only from outbox relays.
- Consumers deduplicate by `event_id`.
- Use consumer groups per service responsibility.
- Send invalid or repeatedly failing messages to a dead-letter topic.
- Keep handlers idempotent and side effects transactionally recorded.

## 8. Resilience

Every external dependency needs:

- Timeout: never rely on client defaults.
- Retry: transient failures only, exponential backoff with jitter.
- Circuit breaker: fail fast while a dependency is unhealthy.
- Bulkhead: cap concurrent calls to preserve service health.
- Fallback: cached response, default response, or queue-for-later behavior when
  approved by architecture.

Python: use `httpx`, `tenacity`, `circuitbreaker`, async semaphores, and
dependency-specific timeout settings.

.NET: use `Microsoft.Extensions.Http.Resilience` for HTTP and
`Microsoft.Extensions.Resilience` for non-HTTP pipelines.

## 9. Observability

- Initialize OpenTelemetry during service startup.
- Auto-instrument HTTP, database, Kafka, gRPC, and outbound HTTP clients.
- Expose Prometheus metrics at `/metrics`.
- Include request count, latency, error count, dependency latency, and
  business metrics.
- Log structured JSON.
- Include trace ID, span ID, subject, tenant, request ID, and service name where
  available.
- Do not log secrets or sensitive payload fields.

Python: use `structlog`, `opentelemetry-instrumentation-fastapi`,
`opentelemetry-instrumentation-sqlalchemy`, and `prometheus-client`.

.NET: use Serilog, OpenTelemetry packages, and `prometheus-net` or the approved
metrics exporter from `SOLUTION-PATTERNS.md`.

## 10. Security

- Validate OIDC/JWT tokens at the service boundary.
- Enforce ABAC using PyCasbin or Casbin before sensitive reads and all
  mutations.
- Use service-to-service auth: internal JWT, mTLS, or mesh identity as specified
  by architecture.
- Keep request-scoped user context immutable.
- Validate all inbound payloads.
- Use parameterized queries only.
- Keep secrets in environment or approved secret storage.

## 11. Health and Readiness

- `/health/live` proves the process is running.
- `/health/ready` verifies critical dependencies.
- Readiness checks should be fast and bounded by timeout.
- Include dependency names and status in readiness responses.
- Kubernetes should use readiness for traffic routing and liveness for restart
  decisions.

## 12. Data Ownership

- Each service owns its database.
- Other services access data through APIs or events.
- Do not share internal tables.
- Publish domain events for state changes that other services need.
- Keep migrations scoped to the owning service.

## 13. Schema Evolution

- Add optional fields for backward-compatible event changes.
- Do not remove or rename event fields without a migration plan.
- Version API and event contracts deliberately.
- Register schemas before deployment when schema registry is in use.
- Keep consumers tolerant of unknown optional fields.

## 14. Deployment Readiness

- Build multi-stage Docker images.
- Expose health and metrics endpoints.
- Configure via environment variables.
- Run migrations through the approved deployment path.
- Include resource requests, limits, probes, and graceful shutdown settings in
  Kubernetes or Helm artifacts when DevOps owns those files.

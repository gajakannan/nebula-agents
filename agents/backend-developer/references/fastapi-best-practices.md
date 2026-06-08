# FastAPI Best Practices

Use this reference when `SOLUTION-PATTERNS.md` assigns a backend service to
Python or FastAPI. Keep the domain layer free of FastAPI, SQLAlchemy, Pydantic,
and infrastructure imports.

## App Factory

- Expose `create_app(settings: Settings) -> FastAPI` from `api/main.py`.
- Use `lifespan` for startup and shutdown work.
- Initialize logging, tracing, metrics, database engines, cache clients, and
  message clients during startup.
- Close async clients and drain background work during shutdown.
- Keep module import side effects small so tests can build apps with overrides.

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings)
    setup_tracing(app, settings.service_name)
    app.state.db = create_engine(settings.database_url)
    yield
    await app.state.db.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(lifespan=lifespan, title="Backend Service")
    app.include_router(order_router)
    app.include_router(health_router)
    return app
```

## Router Organization

- Use one router per aggregate or bounded service area.
- Prefix externally visible routes with `/api/v1`.
- Keep route handlers thin: parse request, authorize, call handler, map response.
- Put request and response models near the router when they are API-specific.
- Put application DTOs in `application/dtos.py` when shared by handlers.

## Dependency Injection

- Dependency flow: `Settings -> Engine -> Session -> Repository -> Handler`.
- Prefer `Depends()` factories for request-scoped dependencies.
- Use a DI container only when dependency graphs become too large for simple
  factories.
- Override dependencies in tests with `app.dependency_overrides`.
- Never construct database sessions inside route handlers.

```python
async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


def get_create_order_handler(
    session: AsyncSession = Depends(get_session),
) -> CreateOrderHandler:
    return CreateOrderHandler(
        unit_of_work=SqlAlchemyUnitOfWork(session),
        outbox=OutboxPublisher(),
    )
```

## Async Rules

- Use `async def` for I/O paths.
- Use sync functions for CPU-only domain logic.
- Do not call blocking libraries from async endpoints.
- Use `asyncio.TaskGroup` for bounded concurrent calls.
- Always set explicit timeouts on `httpx.AsyncClient`, Redis, Kafka, and gRPC.

## Middleware

Recommended order:

1. Tracing and request context.
2. Request ID propagation.
3. Authentication.
4. Rate limiting.
5. Error handling and problem response mapping.

Propagate `X-Request-ID` to downstream HTTP and gRPC calls. Include it in
structured logs and response headers.

## Error Handling

- Map domain exceptions to RFC 9457 problem responses.
- Return validation failures in a stable shape.
- Do not leak stack traces or internal dependency names in API responses.
- Log unexpected errors once at the boundary with correlation metadata.

```python
@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "type": "about:blank",
            "title": "Domain rule violation",
            "status": 400,
            "detail": str(exc),
        },
        media_type="application/problem+json",
    )
```

## Configuration

- Use `pydantic-settings`.
- Validate configuration at startup.
- Read secrets from environment or a secret provider.
- Keep `.env` local-only and never required in production.
- Use typed URLs, durations, and feature flags.

## Auth

- Validate OIDC/JWT tokens in middleware or a shared dependency.
- Build a request-scoped `AuthUser` object with subject, tenant, and roles.
- Enforce PyCasbin before mutation and before sensitive reads.
- Do not rely on frontend permissions.

## Validation

- Use Pydantic v2 models for API input and output.
- Set `extra="forbid"` on request models unless the contract says otherwise.
- Export JSON Schema when the frontend or contract tests need it.
- Keep domain invariants in domain entities, not only Pydantic models.

## Pagination

- Prefer keyset or cursor pagination for large tables.
- Include `items`, `next_cursor`, and `has_more` in list responses.
- Validate `limit` with a service-approved maximum.
- Keep sorting stable by including a unique tiebreaker column.

## Background Work

- Use FastAPI `BackgroundTasks` only for best-effort, non-critical work.
- Use Temporal activities for reliable workflows and compensations.
- Use Kafka consumers or outbox relays for durable asynchronous integration.

## File Uploads

- Stream large files to object storage.
- Prefer pre-signed upload URLs when clients can upload directly.
- Validate content type, size, and ownership before accepting metadata.
- Store only metadata in the service database.

## WebSockets

- Keep WebSocket state in a connection manager.
- Authenticate before accepting long-lived connections.
- Bound message size and connection count.
- Use durable event streams for replayable events.

## gRPC Alongside FastAPI

- Share application handlers between REST and gRPC adapters.
- Keep generated protobuf code outside the domain layer.
- Propagate deadlines and request IDs.
- Add client interceptors for auth, tracing, retry, and timeout.

## Rate Limiting

- Apply rate limits at the gateway when possible.
- Add service-level Redis token bucket limits for high-risk endpoints.
- Return clear 429 problem responses.
- Include request ID in rate-limit logs.

## OpenAPI

- Group routes with tags.
- Define security schemes in app metadata.
- Include problem response schemas.
- Keep examples generic and contract-aligned.

## Health

- `/health/live` returns 200 when the process can serve.
- `/health/ready` checks critical dependencies: database, cache, message broker, and
  required external services.
- Readiness failures return 503 and a dependency status map.

## Graceful Shutdown

- Stop accepting new work on SIGTERM.
- Drain in-flight requests for the platform grace period.
- Close database, Redis, HTTP, Kafka, and gRPC clients.
- Stop outbox relays and consumers cleanly.

## Type Hints

- Run `mypy --strict`.
- Do not use `Any` without a short justification.
- Use `Protocol` for application ports.
- Use dataclasses or Pydantic models for structured data.
- Avoid `setattr` and `getattr` for normal attribute access.

## Testing

- Use `pytest` and `pytest-asyncio`.
- Use `httpx.AsyncClient` for API tests.
- Override dependencies for unit-style API tests.
- Use testcontainers for PostgreSQL and message broker integration tests.
- Test authorization, validation, error mapping, and happy paths.

```python
@pytest.mark.asyncio
async def test_create_order_returns_created(app: FastAPI) -> None:
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/orders", json=valid_order_payload())

    assert response.status_code == 201
```

## Bulk Operations

- Use batch endpoints only when the API contract requires them.
- Define partial success semantics up front.
- Return per-item status for mixed outcomes.
- Use database bulk APIs carefully; do not bypass invariants.

## Idempotency

- Support `Idempotency-Key` for client-retried mutations when specified.
- Store request fingerprint, response body, status code, and expiry.
- Reject key reuse with a different request fingerprint.
- Use Redis or a database table depending on durability requirements.

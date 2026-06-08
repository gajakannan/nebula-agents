# Code Patterns (Dual-Stack Reference)

Use these examples as implementation shapes, not as requirements. The active
stack comes from `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`.
Keep domain examples generic: customers, orders, and products only.

## 1. Domain Entity

### Python

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4


class DomainError(Exception):
    pass


@dataclass(frozen=True)
class OrderSubmitted:
    aggregate_id: UUID
    total: Decimal
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Order:
    """Aggregate root. Domain code has no FastAPI or SQLAlchemy imports."""

    customer_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: str = "draft"
    total: Decimal = Decimal("0.00")
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = None
    version: int = 0

    def add_item(self, product_id: UUID, quantity: int, unit_price: Decimal) -> None:
        if quantity <= 0:
            raise DomainError("Quantity must be positive")
        self.total += unit_price * quantity
        self.updated_at = datetime.now(timezone.utc)

    def submit(self) -> list[OrderSubmitted]:
        if self.status != "draft":
            raise DomainError("Only draft orders can be submitted")
        if self.total <= Decimal("0.00"):
            raise DomainError("Cannot submit empty order")
        self.status = "submitted"
        self.updated_at = datetime.now(timezone.utc)
        self.version += 1
        return [OrderSubmitted(aggregate_id=self.id, total=self.total)]
```

### .NET

```csharp
public sealed class Order : BaseEntity
{
    private readonly List<LineItem> _lineItems = new();

    public Guid CustomerId { get; private set; }
    public OrderStatus Status { get; private set; } = OrderStatus.Draft;
    public decimal Total { get; private set; }
    public int Version { get; private set; }
    public IReadOnlyList<LineItem> LineItems => _lineItems.AsReadOnly();

    private Order() { }

    public Order(Guid customerId)
    {
        CustomerId = customerId;
    }

    public void AddItem(Guid productId, int quantity, decimal unitPrice)
    {
        if (quantity <= 0)
            throw new DomainException("Quantity must be positive");

        _lineItems.Add(new LineItem(productId, quantity, unitPrice));
        Total += quantity * unitPrice;
    }

    public IReadOnlyList<DomainEvent> Submit()
    {
        if (Status != OrderStatus.Draft)
            throw new DomainException("Only draft orders can be submitted");
        if (Total <= 0)
            throw new DomainException("Cannot submit empty order");

        Status = OrderStatus.Submitted;
        Version += 1;
        return new[] { new OrderSubmitted(Id, Total) };
    }
}
```

## 2. Command Handler

### Python

```python
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class CreateOrderCommand:
    customer_id: UUID
    items: list[LineItemInput]


@dataclass(frozen=True)
class LineItemInput:
    product_id: UUID
    quantity: int
    unit_price: Decimal


class CreateOrderHandler:
    def __init__(self, unit_of_work: UnitOfWork, outbox: OutboxPublisher):
        self._unit_of_work = unit_of_work
        self._outbox = outbox

    async def execute(self, command: CreateOrderCommand) -> UUID:
        order = Order(customer_id=command.customer_id)
        for item in command.items:
            order.add_item(item.product_id, item.quantity, item.unit_price)

        events = order.submit()
        async with self._unit_of_work as uow:
            await uow.orders.save(order)
            await self._outbox.stage(uow.session, events)
            await uow.commit()
        return order.id
```

### .NET

```csharp
public sealed record CreateOrderCommand(Guid CustomerId, IReadOnlyList<LineItemDto> Items);

public sealed class CreateOrderHandler : IRequestHandler<CreateOrderCommand, Guid>
{
    private readonly IOrderRepository _orders;
    private readonly IOutboxPublisher _outbox;
    private readonly IUnitOfWork _unitOfWork;

    public CreateOrderHandler(
        IOrderRepository orders,
        IOutboxPublisher outbox,
        IUnitOfWork unitOfWork)
    {
        _orders = orders;
        _outbox = outbox;
        _unitOfWork = unitOfWork;
    }

    public async Task<Guid> Handle(CreateOrderCommand command, CancellationToken ct)
    {
        var order = new Order(command.CustomerId);
        foreach (var item in command.Items)
            order.AddItem(item.ProductId, item.Quantity, item.UnitPrice);

        var events = order.Submit();
        await _orders.SaveAsync(order, ct);
        await _outbox.StageAsync(events, ct);
        await _unitOfWork.CommitAsync(ct);
        return order.Id;
    }
}
```

## 3. Repository

### Python

```python
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class OrderRepository(Protocol):
    async def get(self, order_id: UUID) -> Order | None:
        ...

    async def save(self, order: Order) -> None:
        ...


class SqlAlchemyOrderRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, order_id: UUID) -> Order | None:
        result = await self._session.execute(
            select(OrderModel).where(OrderModel.id == order_id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model is not None else None

    async def save(self, order: Order) -> None:
        model = OrderModel.from_domain(order)
        await self._session.merge(model)
        await self._session.flush()
```

### .NET

```csharp
public interface IOrderRepository
{
    Task<Order?> GetByIdAsync(Guid id, CancellationToken ct = default);
    Task SaveAsync(Order order, CancellationToken ct = default);
}

public sealed class OrderRepository : IOrderRepository
{
    private readonly AppDbContext _context;

    public OrderRepository(AppDbContext context)
    {
        _context = context;
    }

    public Task<Order?> GetByIdAsync(Guid id, CancellationToken ct = default)
        => _context.Orders
            .Include(order => order.LineItems)
            .FirstOrDefaultAsync(order => order.Id == id, ct);

    public async Task SaveAsync(Order order, CancellationToken ct = default)
    {
        _context.Orders.Update(order);
        await _context.SaveChangesAsync(ct);
    }
}
```

## 4. API Endpoint

### Python

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


class LineItemDto(BaseModel):
    product_id: UUID
    quantity: int
    unit_price: str


class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UUID
    items: list[LineItemDto]


class CreateOrderResponse(BaseModel):
    id: UUID
    status: str


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreateOrderResponse)
async def create_order(
    request: CreateOrderRequest,
    handler: CreateOrderHandler = Depends(get_create_order_handler),
    user: AuthUser = Depends(get_current_user),
    enforcer: CasbinEnforcer = Depends(get_enforcer),
) -> CreateOrderResponse:
    allowed = enforcer.enforce(user.subject, "orders", "create", {"tenant": user.tenant_id})
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    command = CreateOrderCommand(
        customer_id=request.customer_id,
        items=[
            LineItemInput(item.product_id, item.quantity, Decimal(item.unit_price))
            for item in request.items
        ],
    )
    order_id = await handler.execute(command)
    return CreateOrderResponse(id=order_id, status="submitted")
```

### .NET

```csharp
public static class OrderEndpoints
{
    public static IEndpointRouteBuilder MapOrderEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapPost("/api/v1/orders", CreateOrder)
            .RequireAuthorization();
        return app;
    }

    private static async Task<IResult> CreateOrder(
        CreateOrderRequest request,
        IRequestHandler<CreateOrderCommand, Guid> handler,
        ICasbinEnforcer enforcer,
        HttpContext context,
        CancellationToken ct)
    {
        var subject = context.User.FindFirst("sub")?.Value ?? string.Empty;
        if (!enforcer.Enforce(subject, "orders", "create"))
            return Results.Forbid();

        var orderId = await handler.Handle(
            new CreateOrderCommand(request.CustomerId, request.Items),
            ct);

        return Results.Created($"/api/v1/orders/{orderId}", new { id = orderId });
    }
}
```

## 5. Transactional Outbox

### Python

```python
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUuid
from sqlalchemy.orm import Mapped, mapped_column


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"

    id: Mapped[UUID] = mapped_column(PgUuid(as_uuid=True), primary_key=True, default=uuid4)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class OutboxPublisher:
    async def stage(self, session: AsyncSession, events: list[DomainEvent]) -> None:
        for event in events:
            session.add(
                OutboxMessage(
                    aggregate_type=event.aggregate_type,
                    aggregate_id=str(event.aggregate_id),
                    event_type=event.event_type,
                    payload=event.to_json(),
                )
            )
```

### .NET

```csharp
public sealed class OutboxMessage
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string AggregateType { get; set; } = string.Empty;
    public string AggregateId { get; set; } = string.Empty;
    public string EventType { get; set; } = string.Empty;
    public string Payload { get; set; } = string.Empty;
    public DateTime OccurredAt { get; set; } = DateTime.UtcNow;
    public bool Published { get; set; }
}

public sealed class OutboxPublisher : IOutboxPublisher
{
    private readonly AppDbContext _context;

    public OutboxPublisher(AppDbContext context)
    {
        _context = context;
    }

    public Task StageAsync(IEnumerable<DomainEvent> events, CancellationToken ct)
    {
        foreach (var evt in events)
        {
            _context.OutboxMessages.Add(new OutboxMessage
            {
                AggregateType = evt.AggregateType,
                AggregateId = evt.AggregateId.ToString(),
                EventType = evt.EventType,
                Payload = JsonSerializer.Serialize(evt),
            });
        }

        return Task.CompletedTask;
    }
}
```

## 6. Resilient External Call

### Python

```python
import httpx
from circuitbreaker import circuit
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter


class ProductClient:
    def __init__(self, base_url: str):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=5.0)

    @circuit(failure_threshold=5, recovery_timeout=30)
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.2, max=5),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def get_product(self, product_id: str) -> dict[str, object]:
        response = await self._client.get(f"/api/v1/products/{product_id}")
        response.raise_for_status()
        return response.json()
```

### .NET

```csharp
builder.Services.AddHttpClient<IProductClient, ProductClient>(client =>
{
    client.BaseAddress = new Uri("http://product-service");
    client.Timeout = TimeSpan.FromSeconds(5);
})
.AddResilienceHandler("product-service", resilience =>
{
    resilience.AddRetry(new HttpRetryStrategyOptions
    {
        MaxRetryAttempts = 3,
        BackoffType = DelayBackoffType.Exponential,
        UseJitter = true,
    });
    resilience.AddCircuitBreaker(new HttpCircuitBreakerStrategyOptions
    {
        FailureRatio = 0.5,
        SamplingDuration = TimeSpan.FromSeconds(10),
        BreakDuration = TimeSpan.FromSeconds(30),
    });
    resilience.AddTimeout(TimeSpan.FromSeconds(5));
});
```

## 7. OpenTelemetry Setup

### Python

```python
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup_tracing(app: FastAPI, service_name: str) -> None:
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
```

### .NET

```csharp
builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource.AddService("order-service"))
    .WithTracing(tracing => tracing
        .AddAspNetCoreInstrumentation()
        .AddEntityFrameworkCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddOtlpExporter())
    .WithMetrics(metrics => metrics
        .AddAspNetCoreInstrumentation()
        .AddPrometheusExporter());
```

## 8. Health Checks

### Python

```python
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["health"])


@router.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> JSONResponse:
    checks = {}
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "failed"

    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "failed"

    all_ok = all(value == "ok" for value in checks.values())
    return JSONResponse(content=checks, status_code=200 if all_ok else 503)
```

### .NET

```csharp
builder.Services.AddHealthChecks()
    .AddNpgSql(connectionString, name: "database")
    .AddRedis(redisConnection, name: "redis");

app.MapHealthChecks("/health/live", new HealthCheckOptions
{
    Predicate = _ => false
});
app.MapHealthChecks("/health/ready");
```

## 9. Idempotent Event Consumer

### Python

```python
import json
from collections.abc import Awaitable, Callable

from confluent_kafka import Consumer

EventHandler = Callable[[dict[str, object]], Awaitable[None]]


class EventConsumer:
    def __init__(
        self,
        consumer: Consumer,
        handlers: dict[str, EventHandler],
        processed: ProcessedEventStore,
    ):
        self._consumer = consumer
        self._handlers = handlers
        self._processed = processed

    async def run(self, topics: list[str]) -> None:
        self._consumer.subscribe(topics)
        while True:
            message = self._consumer.poll(1.0)
            if message is None or message.error():
                continue

            event = json.loads(message.value().decode("utf-8"))
            event_id = str(event["event_id"])
            if await self._processed.contains(event_id):
                self._consumer.commit(message)
                continue

            handler = self._handlers.get(str(event["event_type"]))
            if handler is not None:
                await handler(event)

            await self._processed.add(event_id)
            self._consumer.commit(message)
```

### .NET

```csharp
public sealed class EventConsumerService : BackgroundService
{
    private readonly IConsumer<string, string> _consumer;
    private readonly IServiceProvider _services;

    protected override async Task ExecuteAsync(CancellationToken ct)
    {
        _consumer.Subscribe(new[] { "events.orders" });

        while (!ct.IsCancellationRequested)
        {
            var result = _consumer.Consume(ct);
            var envelope = JsonSerializer.Deserialize<EventEnvelope>(result.Message.Value);
            if (envelope is null)
                continue;

            using var scope = _services.CreateScope();
            var processed = scope.ServiceProvider.GetRequiredService<IProcessedEvents>();
            if (await processed.ContainsAsync(envelope.EventId, ct))
            {
                _consumer.Commit(result);
                continue;
            }

            var handler = scope.ServiceProvider.GetRequiredKeyedService<IEventHandler>(envelope.EventType);
            await handler.HandleAsync(envelope, ct);
            await processed.AddAsync(envelope.EventId, ct);
            _consumer.Commit(result);
        }
    }
}
```

## 10. Unit Test

### Python

```python
from decimal import Decimal
from uuid import uuid4

import pytest


def test_submit_draft_order_succeeds() -> None:
    order = Order(customer_id=uuid4())
    order.add_item(product_id=uuid4(), quantity=2, unit_price=Decimal("10.00"))

    events = order.submit()

    assert order.status == "submitted"
    assert len(events) == 1
    assert events[0].aggregate_id == order.id


def test_submit_empty_order_raises() -> None:
    order = Order(customer_id=uuid4())

    with pytest.raises(DomainError, match="Cannot submit empty order"):
        order.submit()
```

### .NET

```csharp
public sealed class OrderTests
{
    [Fact]
    public void Submit_DraftOrderWithItems_ShouldSucceed()
    {
        var order = new Order(Guid.NewGuid());
        order.AddItem(Guid.NewGuid(), 2, 10.00m);

        var events = order.Submit();

        order.Status.ShouldBe(OrderStatus.Submitted);
        events.ShouldHaveSingleItem();
        events[0].ShouldBeOfType<OrderSubmitted>();
    }

    [Fact]
    public void Submit_EmptyOrder_ShouldThrow()
    {
        var order = new Order(Guid.NewGuid());

        Should.Throw<DomainException>(() => order.Submit());
    }
}
```

## Checklist

- Domain layer stays framework-free in both stacks.
- Application handlers own orchestration, transaction boundaries, and outbox staging.
- Infrastructure adapters implement repository protocols or interfaces.
- API endpoints validate input, authorize before mutation, and map domain errors to problem responses.
- External calls have explicit timeout, retry, and circuit breaker behavior.
- Event consumers deduplicate by `event_id`.

# Service Architecture Patterns

Comprehensive guide for designing service architecture, module boundaries, and integration patterns. This guide covers modular monolith architecture, Clean Architecture layers, Domain-Driven Design patterns, CQRS considerations, and integration strategies.

---

## 1. Modular Monolith Architecture

### 1.1 What is a Modular Monolith?

**Modular Monolith** is a single deployable application organized into logical modules with clear boundaries.

**Key Characteristics:**
- **Single Deployment**: One executable, one Docker container
- **Logical Modules**: Organized by domain (Customer, Order, Notification)
- **Clear Boundaries**: Each module has well-defined interfaces
- **Shared Database**: All modules share one PostgreSQL database
- **In-Process Communication**: Modules call each other via interfaces (no network calls)

**Why Modular Monolith:**
- Simpler deployment (single container vs managing many services)
- Easier transactions (ACID across modules, single database)
- Faster development (no inter-service communication overhead)
- Lower operational complexity (one database, one deployment, simpler monitoring)
- Appropriate scale (50-500 users, not Netflix scale)
- Future microservices path (modules can be extracted later if needed)

---

### 1.2 Module Boundaries

**Modules:**

1. **Customer Module**
   - Entities: Customer, Address, CustomerHierarchy
   - Responsibilities: Customer CRUD, customer hierarchy, customer addresses
   - APIs: `/api/customers/*`

2. **Order Module**
   - Entities: Order, OrderDocument, Invoice
   - Responsibilities: Order intake, workflow, document management, invoicing
   - APIs: `/api/orders/*`

3. **Subscription Module**
   - Entities: Subscription, SubscriptionFollowUp
   - Responsibilities: Subscription pipeline, reminders, expiration status tracking
   - APIs: `/api/subscriptions/*`

4. **Timeline Module (Shared)**
   - Entities: ActivityTimelineEvent, WorkflowTransition
   - Responsibilities: Audit trail, activity timeline, workflow history
   - APIs: `/api/timeline/*`

5. **Identity Module**
   - Entities: UserProfile, UserPreference
   - Responsibilities: User profiles, preferences, Keycloak integration
   - APIs: `/api/users/*`, `/api/profile/*`

---

### 1.3 Module Communication (In-Process)

**Modules communicate via interfaces, not direct dependencies:**

```csharp
// Order Module depends on Customer Module interface
public interface ICustomerService
{
    Task<Customer?> GetByIdAsync(Guid customerId);
    Task<bool> IsActiveAsync(Guid customerId);
}

// Order Module uses interface
public class OrderService
{
    private readonly ICustomerService _customerService;

    public async Task<Order> CreateAsync(CreateOrderRequest request)
    {
        // Validate customer exists and is active
        var customerExists = await _customerService.IsActiveAsync(request.CustomerId);
        if (!customerExists)
            throw new ValidationException("Customer not found or inactive");

        // ... create order
    }
}
```

**Benefits:**
- Clear module boundaries
- Testable (can mock interfaces)
- Future-proof (can replace in-process call with HTTP call if extracted to microservice)

---

### 1.4 Shared Kernel

**Shared Kernel**: Common types and utilities used by all modules.

**What Goes in Shared Kernel:**
- `BaseEntity` (common base class for all entities)
- `Result<T>` (standardized result pattern)
- `ErrorResponse` (standardized error format)
- `IRepository<T>` (generic repository interface)
- Common value objects (Money, EmailAddress, PhoneNumber)

**What Doesn't Go in Shared Kernel:**
- Domain entities (Customer, Order) - belong to specific modules
- Business logic - belongs to modules

**Project Structure:**
```
App.SharedKernel/
  ├── BaseEntity.cs
  ├── Result.cs
  ├── ErrorResponse.cs
  ├── ValueObjects/
  │   ├── Money.cs
  │   ├── EmailAddress.cs
  │   └── PhoneNumber.cs
  └── Interfaces/
      └── IRepository.cs
```

---

### 1.5 Benefits of Modular Monolith

**Simplicity:**
- One codebase to navigate
- One deployment to manage
- One database to backup

**Transactions:**
- ACID transactions across modules
- No distributed transactions (sagas)
- Easier to maintain data consistency

**Development Velocity:**
- Faster feedback loop (no inter-service coordination)
- Easier debugging (single process)
- Easier testing (no mock services)

**Cost:**
- Lower infrastructure costs (one database, one app server)
- Simpler monitoring (one application to monitor)

---

## 2. Clean Architecture Layers

### 2.1 Overview

**Clean Architecture** separates concerns into concentric layers with dependency rules.

**Layers (innermost to outermost):**
1. **Domain Layer**: Entities, value objects, domain events (no dependencies)
2. **Application Layer**: Use cases, interfaces, DTOs (depends on Domain)
3. **Infrastructure Layer**: EF Core, repositories, external services (depends on Application)
4. **API Layer**: Controllers, middleware, OpenAPI (depends on Application)

**Dependency Rule**: Dependencies point inward (API → Application → Domain ← Infrastructure).

---

### 2.2 Domain Layer

**Contains:**
- Entities (Customer, Order)
- Value Objects (Address, Money, EmailAddress)
- Domain Events (CustomerCreated, OrderTransitioned)
- Domain Exceptions (CustomerNotFoundException, InvalidStatusTransitionException)
- Interfaces (IRepository is defined here, implemented in Infrastructure)

**No Dependencies:**
- No EF Core references
- No external library dependencies (except maybe FluentValidation)
- Pure C# domain logic

**Example:**

```csharp
// Domain Layer: App.Domain/Entities/Customer.cs
public class Customer : BaseEntity
{
    public string Name { get; private set; }
    public string Email { get; private set; }
    public string Status { get; private set; }

    // Domain methods (business logic)
    public void Activate()
    {
        if (Status == "Suspended")
            throw new InvalidOperationException("Cannot activate suspended customer");

        Status = "Active";
        DomainEvents.Raise(new CustomerActivated(Id));
    }

    public void Suspend(string reason)
    {
        Status = "Suspended";
        DomainEvents.Raise(new CustomerSuspended(Id, reason));
    }
}
```

---

### 2.3 Application Layer

**Contains:**
- Use Cases / Application Services (CreateCustomerUseCase, GetCustomerUseCase)
- DTOs (CreateCustomerRequest, CustomerResponse)
- Interfaces (ICustomerService, IOrderService)
- Validation (FluentValidation validators)
- Mapping (AutoMapper profiles)

**Depends On:** Domain Layer only

**Example:**

```csharp
// Application Layer: App.Application/Customers/CreateCustomerUseCase.cs
public class CreateCustomerUseCase
{
    private readonly IRepository<Customer> _repository;
    private readonly IUnitOfWork _unitOfWork;

    public async Task<Result<CustomerResponse>> ExecuteAsync(CreateCustomerRequest request)
    {
        // Validate
        var validator = new CreateCustomerRequestValidator();
        var validation = await validator.ValidateAsync(request);
        if (!validation.IsValid)
            return Result<CustomerResponse>.Failure(validation.Errors);

        // Create entity
        var customer = new Customer
        {
            Name = request.Name,
            Email = request.Email,
            Region = request.Region
        };

        // Save
        await _repository.AddAsync(customer);
        await _unitOfWork.CommitAsync();

        // Map to DTO
        var response = new CustomerResponse
        {
            Id = customer.Id,
            Name = customer.Name,
            Status = customer.Status
        };

        return Result<CustomerResponse>.Success(response);
    }
}
```

---

### 2.4 Infrastructure Layer

**Contains:**
- EF Core DbContext
- Repository implementations
- External API clients (Temporal, Keycloak, SendGrid)
- File storage (S3, Azure Blob)
- Caching (Redis)

**Depends On:** Application Layer (implements interfaces defined there)

**Example:**

```csharp
// Infrastructure Layer: App.Infrastructure/Persistence/AppDbContext.cs
public class AppDbContext : DbContext
{
    public DbSet<Customer> Customers { get; set; }
    public DbSet<Order> Orders { get; set; }

    protected override void OnModelCreating(ModelBuilder builder)
    {
        builder.ApplyConfigurationsFromAssembly(typeof(AppDbContext).Assembly);
    }
}

// Infrastructure Layer: App.Infrastructure/Persistence/CustomerRepository.cs
public class CustomerRepository : IRepository<Customer>
{
    private readonly AppDbContext _context;

    public async Task<Customer?> GetByIdAsync(Guid id)
    {
        return await _context.Customers.FindAsync(id);
    }

    public async Task AddAsync(Customer customer)
    {
        await _context.Customers.AddAsync(customer);
    }
}
```

---

### 2.5 API Layer

**Contains:**
- Minimal API endpoints
- Middleware (authentication, authorization, error handling)
- OpenAPI configuration
- Dependency injection setup

**Depends On:** Application Layer only (not Infrastructure directly)

**Example:**

```csharp
// API Layer: App.API/Program.cs
var builder = WebApplication.CreateBuilder(args);

// Register dependencies
builder.Services.AddApplication(); // Application Layer DI
builder.Services.AddInfrastructure(builder.Configuration); // Infrastructure Layer DI

var app = builder.Build();

// Minimal API endpoints
app.MapPost("/api/customers", async (
    CreateCustomerRequest request,
    CreateCustomerUseCase useCase) =>
{
    var result = await useCase.ExecuteAsync(request);
    return result.IsSuccess
        ? Results.Created($"/api/customers/{result.Value.Id}", result.Value)
        : Results.BadRequest(result.Error);
})
.WithName("CreateCustomer")
.WithTags("Customers");

app.Run();
```

---

### 2.6 Dependency Flow

**Correct:**
```
API Layer
  ↓ (depends on)
Application Layer
  ↓ (depends on)
Domain Layer
  ↑ (implemented by)
Infrastructure Layer
```

**Infrastructure depends on Application (implements interfaces), but Application doesn't depend on Infrastructure.**

**Dependency Inversion Principle:**
- Application defines `IRepository<T>` interface
- Infrastructure implements `CustomerRepository : IRepository<Customer>`
- API layer wires them together via DI

---

## 3. Domain-Driven Design Patterns

### 3.1 Aggregates

**Aggregate** is a cluster of entities and value objects with a clear boundary and a root entity.

**Aggregate Root:**
- Entry point for all operations on the aggregate
- Enforces invariants (business rules)
- Controls lifecycle of contained entities

**Example: Customer Aggregate**

```csharp
public class Customer : BaseEntity // Aggregate Root
{
    public string Name { get; private set; }
    public ICollection<Address> Addresses { get; private set; } // Contained entities

    // Aggregate root enforces business rules
    public void AddAddress(Address address)
    {
        if (Addresses.Count >= 10)
            throw new DomainException("Customer cannot have more than 10 addresses");

        Addresses.Add(address);
    }

    public void RemoveAddress(Guid addressId)
    {
        var address = Addresses.FirstOrDefault(a => a.Id == addressId);
        if (address == null)
            throw new DomainException("Address not found");

        Addresses.Remove(address);
    }
}

// Repository works at aggregate root level
public interface ICustomerRepository
{
    Task<Customer?> GetByIdAsync(Guid id); // Returns entire aggregate
    Task AddAsync(Customer customer); // Saves entire aggregate
}
```

**Design Principle:** Don't access Address directly. Always go through Customer aggregate root.

---

### 3.2 Value Objects

**Value Object** is an immutable object defined by its properties, not identity.

**Example: Money Value Object**

```csharp
public class Money : ValueObject
{
    public decimal Amount { get; }
    public string Currency { get; }

    public Money(decimal amount, string currency)
    {
        if (amount < 0)
            throw new ArgumentException("Amount cannot be negative");
        if (string.IsNullOrEmpty(currency) || currency.Length != 3)
            throw new ArgumentException("Currency must be 3-letter ISO code");

        Amount = amount;
        Currency = currency;
    }

    // Value equality (two Money objects with same amount and currency are equal)
    protected override IEnumerable<object> GetEqualityComponents()
    {
        yield return Amount;
        yield return Currency;
    }

    // Immutable operations return new instance
    public Money Add(Money other)
    {
        if (Currency != other.Currency)
            throw new InvalidOperationException("Cannot add different currencies");

        return new Money(Amount + other.Amount, Currency);
    }
}
```

---

### 3.3 Domain Events

**Domain Event** represents something that happened in the domain.

**Example: OrderTransitioned Event**

```csharp
public record OrderTransitioned : DomainEvent
{
    public Guid OrderId { get; init; }
    public string FromStatus { get; init; }
    public string ToStatus { get; init; }
    public DateTime TransitionedAt { get; init; }
}

// Raised by domain entity
public class Order : BaseEntity
{
    public void Transition(string toStatus)
    {
        var fromStatus = Status;
        Status = toStatus;

        // Raise domain event
        DomainEvents.Raise(new OrderTransitioned
        {
            OrderId = Id,
            FromStatus = fromStatus,
            ToStatus = toStatus,
            TransitionedAt = DateTime.UtcNow
        });
    }
}

// Handled by application layer
public class OrderTransitionedHandler : IDomainEventHandler<OrderTransitioned>
{
    public async Task Handle(OrderTransitioned @event)
    {
        // Create timeline event
        await _timelineService.LogEventAsync(new ActivityTimelineEvent
        {
            EntityType = "Order",
            EntityId = @event.OrderId,
            EventType = "OrderTransitioned",
            Payload = JsonSerializer.Serialize(@event)
        });

        // Send email notification
        await _emailService.SendStatusChangeEmailAsync(@event.OrderId, @event.ToStatus);
    }
}
```

---

### 3.4 Repositories

**Repository** abstracts data access for aggregate roots.

**Interface (defined in Domain Layer):**

```csharp
public interface IRepository<T> where T : BaseEntity
{
    Task<T?> GetByIdAsync(Guid id);
    Task<List<T>> GetAllAsync();
    Task AddAsync(T entity);
    Task UpdateAsync(T entity);
    Task DeleteAsync(T entity);
}
```

**Implementation (in Infrastructure Layer):**

```csharp
public class Repository<T> : IRepository<T> where T : BaseEntity
{
    private readonly AppDbContext _context;

    public async Task<T?> GetByIdAsync(Guid id)
    {
        return await _context.Set<T>().FindAsync(id);
    }

    public async Task AddAsync(T entity)
    {
        await _context.Set<T>().AddAsync(entity);
    }
}
```

---

### 3.5 Domain Services

**Domain Service** contains business logic that doesn't belong to a single entity.

**Example: Pricing Calculation Service**

```csharp
public class PricingCalculationService
{
    public async Task<List<PricingTier>> CalculatePricingAsync(Order order)
    {
        // Business logic spanning multiple aggregates
        var customer = await _customerRepository.GetByIdAsync(order.CustomerId);
        var schedule = await _pricingScheduleRepository.GetByRegionAndCategoryAsync(
            customer.Region, order.Category);

        var totalDiscount = order.Amount * (schedule.DiscountRate / 100);

        // Calculate pricing tiers across customer hierarchy
        var tiers = new List<PricingTier>();
        // ... calculation logic
        return tiers;
    }
}
```

---

## 4. CQRS Considerations

### 4.1 What is CQRS?

**CQRS** (Command Query Responsibility Segregation) separates read and write models.

**Command Side (Writes):**
- Create, Update, Delete operations
- Uses domain entities
- Enforces business rules
- Transactional

**Query Side (Reads):**
- Read-only queries
- Optimized for specific views
- Denormalized data
- No business logic

---

### 4.2 When to Use CQRS

**Use CQRS When:**
- Read and write patterns are very different
- Complex queries require denormalized data
- High read volume, low write volume
- Need to scale reads independently

**MVP: NOT Using CQRS**
- Simple CRUD operations
- Reads and writes use same data model
- No extreme performance requirements
- Avoid complexity for MVP

**Future Consideration:**
- If 360 views become slow, create read-side projections
- If reporting becomes complex, use separate read database

---

### 4.3 Read Models (Without Full CQRS)

**Use projections for complex queries:**

```csharp
// Write model: Full Customer entity
public class Customer : BaseEntity { /* all fields */ }

// Read model: Optimized for list view
public class CustomerListItem
{
    public Guid Id { get; set; }
    public string Name { get; set; }
    public string Status { get; set; }
}

// Query projects to read model
var customers = await context.Customers
    .Select(c => new CustomerListItem
    {
        Id = c.Id,
        Name = c.Name,
        Status = c.Status
    })
    .ToListAsync();
```

---

### 4.4 When NOT to Use CQRS

**Avoid CQRS for MVP:**
- Adds significant complexity (two models to maintain)
- Eventual consistency between read/write sides
- More infrastructure (separate databases or projections)
- Not needed for 50-500 users with simple queries

**Keep It Simple:** Use same model for reads and writes, optimize queries as needed.

---

## 5. Integration Patterns

### 5.1 Temporal Workflow Integration

**Use Temporal for long-running workflows:**

```csharp
// Workflow definition
[Workflow]
public class SubscriptionExpirationWorkflow
{
    [WorkflowRun]
    public async Task RunAsync(ExpirationWorkflowInput input)
    {
        // Schedule reminder 120 days before expiration
        await Workflow.DelayAsync(input.Subscription.ExpirationDate.AddDays(-120) - DateTime.UtcNow);
        await Workflow.ExecuteActivityAsync<SendExpirationReminderActivity>(
            new ReminderInput { SubscriptionId = input.SubscriptionId, DaysOut = 120 });

        // ... more reminders
    }
}

// Triggered from application layer
public class SubscriptionService
{
    private readonly ITemporalClient _temporalClient;

    public async Task CreateSubscriptionAsync(Subscription subscription)
    {
        // Save subscription
        await _repository.AddAsync(subscription);

        // Start Temporal workflow
        await _temporalClient.StartWorkflowAsync<SubscriptionExpirationWorkflow>(
            new ExpirationWorkflowInput { SubscriptionId = subscription.Id, Subscription = subscription });
    }
}
```

---

### 5.2 Keycloak Integration (Authentication)

**Delegate authentication to Keycloak:**

```csharp
// User logs in via Keycloak (OIDC redirect)
// Keycloak returns JWT token
// API validates JWT and extracts token attributes

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.Authority = "https://keycloak.example.com/realms/app";
        options.Audience = "app-api";
    });
```

**On first login, sync user to UserProfile table:**

```csharp
public async Task OnFirstLoginAsync(ClaimsPrincipal user)
{
    var userId = Guid.Parse(user.FindFirstValue(ClaimTypes.NameIdentifier));
    var existingProfile = await _context.UserProfiles.FindAsync(userId);

    if (existingProfile == null)
    {
        var profile = new UserProfile
        {
            Id = userId,
            Email = user.FindFirstValue(ClaimTypes.Email),
            FullName = user.FindFirstValue("name"),
            Roles = user.FindAll(ClaimTypes.Role).Select(c => c.Value).ToArray()
        };
        await _context.UserProfiles.AddAsync(profile);
        await _context.SaveChangesAsync();
    }
}
```

---

### 5.3 External Partner APIs (Order Pricing)

**Call partner APIs for pricing orders:**

```csharp
public interface IPartnerPricingClient
{
    Task<PricingResponse> GetPriceAsync(PricingRequest request);
}

public class PartnerPricingClient : IPartnerPricingClient
{
    private readonly HttpClient _httpClient;

    public async Task<PricingResponse> GetPriceAsync(PricingRequest request)
    {
        var response = await _httpClient.PostAsJsonAsync("/api/price", request);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<PricingResponse>();
    }
}

// Resilience with Polly
builder.Services.AddHttpClient<IPartnerPricingClient, PartnerPricingClient>()
    .AddTransientHttpErrorPolicy(policy => policy.WaitAndRetryAsync(3, _ => TimeSpan.FromSeconds(2)))
    .AddTransientHttpErrorPolicy(policy => policy.CircuitBreakerAsync(5, TimeSpan.FromSeconds(30)));
```

---

### 5.4 Email Service Integration (SendGrid/SMTP)

**Send emails via SendGrid:**

```csharp
public interface IEmailService
{
    Task SendExpirationReminderAsync(Guid subscriptionId, int daysOut);
}

public class SendGridEmailService : IEmailService
{
    private readonly ISendGridClient _sendGridClient;

    public async Task SendExpirationReminderAsync(Guid subscriptionId, int daysOut)
    {
        var subscription = await _subscriptionRepository.GetByIdAsync(subscriptionId);

        var message = new SendGridMessage
        {
            From = new EmailAddress("noreply@example.com", "App Notifications"),
            Subject = $"Expiration Reminder - {daysOut} Days",
            PlainTextContent = $"Your subscription {subscription.SubscriptionNumber} expires in {daysOut} days.",
            HtmlContent = $"<p>Your subscription <strong>{subscription.SubscriptionNumber}</strong> expires in {daysOut} days.</p>"
        };

        message.AddTo(new EmailAddress(subscription.CustomerEmail));

        await _sendGridClient.SendEmailAsync(message);
    }
}
```

---

### 5.5 Document Storage (S3/Azure Blob)

**Store documents in blob storage:**

```csharp
public interface IDocumentStorageService
{
    Task<string> UploadAsync(Stream fileStream, string fileName, string contentType);
    Task<Stream> DownloadAsync(string blobKey);
    Task DeleteAsync(string blobKey);
}

public class S3DocumentStorageService : IDocumentStorageService
{
    private readonly IAmazonS3 _s3Client;
    private readonly string _bucketName;

    public async Task<string> UploadAsync(Stream fileStream, string fileName, string contentType)
    {
        var key = $"orders/{Guid.NewGuid()}/{fileName}";

        var request = new PutObjectRequest
        {
            BucketName = _bucketName,
            Key = key,
            InputStream = fileStream,
            ContentType = contentType
        };

        await _s3Client.PutObjectAsync(request);
        return key;
    }
}
```

---

### 5.6 Webhook Patterns (Event Notifications)

**Notify external systems of events:**

```csharp
public class WebhookNotificationService
{
    public async Task NotifyOrderCompletedAsync(Order order)
    {
        var webhook = new
        {
            eventType = "order.completed",
            orderId = order.Id,
            orderNumber = order.OrderNumber,
            timestamp = DateTime.UtcNow
        };

        var subscribedWebhooks = await _webhookRepository.GetActiveWebhooksAsync("order.completed");

        foreach (var webhookUrl in subscribedWebhooks)
        {
            await _httpClient.PostAsJsonAsync(webhookUrl, webhook);
        }
    }
}
```

---

## Version History

**Version 1.0** - 2026-01-31 - Initial service architecture patterns guide (450 lines)

# Architecture Best Practices

> **Examples in this guide use `customers` and `orders` as illustrative entities.
> These are not prescriptive — substitute your own domain entities when applying
> these patterns. See `BOUNDARY-POLICY.md` → "Standard Example Entities" for
> the full convention and field mapping.

---

Comprehensive guide for designing robust, maintainable architecture for enterprise applications.

## Table of Contents

1. [Clean Architecture Principles](#clean-architecture-principles)
2. [SOLID Principles](#solid-principles)
3. [Domain-Driven Design (DDD)](#domain-driven-design)
4. [Layering and Dependencies](#layering-and-dependencies)
5. [API Design Principles](#api-design-principles)
6. [Data Modeling Principles](#data-modeling-principles)
7. [Security Architecture](#security-architecture)
8. [Performance and Scalability](#performance-and-scalability)
9. [Observability](#observability)
10. [Common Anti-Patterns](#common-anti-patterns)

---

## Clean Architecture Principles

### Core Concepts

**Goal:** Create systems that are:
- Independent of frameworks
- Testable
- Independent of UI
- Independent of Database
- Independent of external agencies

### Layer Structure

```
┌─────────────────────────────────────┐
│         API / Presentation          │  ← Controllers, DTOs, Middleware
│    (ASP.NET Core, React)            │
└──────────────┬──────────────────────┘
               │ depends on ↓
┌──────────────┴──────────────────────┐
│          Application Layer          │  ← Use Cases, Interfaces, Application Services
│    (Business Workflows)             │
└──────────────┬──────────────────────┘
               │ depends on ↓
┌──────────────┴──────────────────────┐
│           Domain Layer              │  ← Entities, Value Objects, Domain Events
│    (Business Logic, Core)           │
└─────────────────────────────────────┘
               ↑ depended on by
┌──────────────┴──────────────────────┐
│       Infrastructure Layer          │  ← EF Core, External Services, File System
│    (Implementation Details)         │
└─────────────────────────────────────┘
```

**Key Rule:** Dependencies flow inward. Inner layers know nothing about outer layers.

### Domain Layer (Core)

**Contains:**
- Entities (Customer, Order, Product)
- Value Objects (Money, Address, EmailAddress)
- Domain Events (CustomerCreated, OrderPlaced)
- Domain Services (complex business logic that doesn't belong to a single entity)
- Repository Interfaces (but NOT implementations)

**Does NOT Contain:**
- Database code (no EF Core)
- External service calls
- HTTP/API concerns
- UI logic

**Example Entity:**
```csharp
public class Customer
{
    public Guid Id { get; private set; }
    public string Name { get; private set; }
    public string Email { get; private set; }
    public CustomerStatus Status { get; private set; }

    // Domain logic
    public void Activate()
    {
        if (Status == CustomerStatus.Suspended)
            throw new DomainException("Cannot activate a suspended customer");

        Status = CustomerStatus.Active;
        AddDomainEvent(new CustomerActivated(Id));
    }

    // Factory method
    public static Customer Create(string name, string email)
    {
        // Validation
        if (string.IsNullOrEmpty(name))
            throw new ArgumentException("Name is required");

        var customer = new Customer
        {
            Id = Guid.NewGuid(),
            Name = name,
            Email = email,
            Status = CustomerStatus.Active
        };

        customer.AddDomainEvent(new CustomerCreated(customer.Id, customer.Name));
        return customer;
    }
}
```

### Application Layer

**Contains:**
- Use Cases / Application Services (CreateCustomerUseCase, GetCustomerQuery)
- Commands and Queries (CQRS pattern)
- DTOs / Request/Response Models
- Application Interfaces (IEmailService, INotificationService)
- Validators
- Mappers (Entity → DTO)

**Does NOT Contain:**
- Database implementation details
- HTTP concerns (that's API layer)
- Domain logic (that's Domain layer)

**Example Use Case:**
```csharp
public class CreateCustomerUseCase
{
    private readonly ICustomerRepository _repository;
    private readonly IAuthorizationService _authz;
    private readonly ITimelineService _timeline;

    public async Task<CustomerDto> Execute(CreateCustomerCommand command, User user)
    {
        // Authorization check
        await _authz.CheckPermission(user, "CreateCustomer");

        // Create domain entity
        var customer = Customer.Create(
            command.Name,
            command.Email
        );

        // Persist
        await _repository.Add(customer);
        await _repository.SaveChanges();

        // Timeline event
        await _timeline.LogEvent(new CustomerCreatedEvent(customer.Id, user.Id));

        // Return DTO
        return MapToDto(customer);
    }
}
```

### Infrastructure Layer

**Contains:**
- EF Core DbContext and Configurations
- Repository Implementations
- External Service Implementations (Email, SMS, etc.)
- File System Access
- Caching Implementation

**Example Repository:**
```csharp
public class CustomerRepository : ICustomerRepository
{
    private readonly AppDbContext _context;

    public async Task<Customer> GetById(Guid id)
    {
        return await _context.Customers
            .Include(c => c.Orders)
            .FirstOrDefaultAsync(c => c.Id == id);
    }

    public async Task Add(Customer customer)
    {
        await _context.Customers.AddAsync(customer);
    }

    public async Task SaveChanges()
    {
        await _context.SaveChangesAsync();
    }
}
```

### API Layer

**Contains:**
- Controllers
- API DTOs (distinct from Application DTOs if needed)
- Middleware (auth, error handling, logging)
- API Versioning
- Swagger/OpenAPI configuration

**Example Controller:**
```csharp
[ApiController]
[Route("api/customers")]
[Authorize]
public class CustomersController : ControllerBase
{
    private readonly CreateCustomerUseCase _createCustomer;

    [HttpPost]
    [ProducesResponseType(typeof(CustomerResponse), 201)]
    [ProducesResponseType(typeof(ErrorResponse), 400)]
    public async Task<IActionResult> Create([FromBody] CreateCustomerRequest request)
    {
        var command = MapToCommand(request);
        var result = await _createCustomer.Execute(command, User);

        return CreatedAtAction(
            nameof(GetById),
            new { id = result.Id },
            result
        );
    }
}
```

---

## SOLID Principles

### Single Responsibility Principle (SRP)

**Definition:** A class should have only one reason to change.

**Bad Example:**
```csharp
public class CustomerService
{
    public void CreateCustomer() { /* creates customer */ }
    public void SendEmail() { /* sends email */ }
    public void LogActivity() { /* logs to database */ }
    public void ValidateData() { /* validates */ }
}
// This class has 4 reasons to change!
```

**Good Example:**
```csharp
public class CustomerService
{
    private readonly ICustomerRepository _repository;
    private readonly IEmailService _email;
    private readonly ITimelineService _timeline;
    private readonly IValidator<Customer> _validator;

    public void CreateCustomer()
    {
        // Orchestrates, delegates to specialized services
    }
}
```

### Open/Closed Principle (OCP)

**Definition:** Software entities should be open for extension, closed for modification.

**Use Strategy Pattern for Varying Behavior:**
```csharp
public interface IShippingCalculator
{
    decimal Calculate(Order order);
}

public class StandardShippingCalculator : IShippingCalculator
{
    public decimal Calculate(Order order) { /* standard shipping logic */ }
}

public class ExpressShippingCalculator : IShippingCalculator
{
    public decimal Calculate(Order order) { /* express shipping logic */ }
}

// Add new shipping strategies without modifying existing code
```

### Liskov Substitution Principle (LSP)

**Definition:** Subtypes must be substitutable for their base types.

**Avoid violating LSP:**
```csharp
// Bad: Square violates LSP if it inherits from Rectangle
public class Rectangle
{
    public virtual int Width { get; set; }
    public virtual int Height { get; set; }
}

public class Square : Rectangle
{
    // Violates LSP: SetWidth changes Height too
    public override int Width
    {
        set { base.Width = base.Height = value; }
    }
}

// Good: Use composition or separate hierarchies
public interface IShape
{
    int Area();
}

public class Rectangle : IShape { }
public class Square : IShape { }
```

### Interface Segregation Principle (ISP)

**Definition:** Clients should not be forced to depend on interfaces they don't use.

**Bad Example:**
```csharp
public interface ICustomerRepository
{
    Task<Customer> GetById(Guid id);
    Task Add(Customer customer);
    Task Update(Customer customer);
    Task Delete(Guid id);
    Task<List<Customer>> Search(string term);
    Task<CustomerStatistics> GetStatistics(Guid id);
    Task<List<Order>> GetOrders(Guid id);
}
// Too many responsibilities!
```

**Good Example:**
```csharp
public interface ICustomerRepository
{
    Task<Customer> GetById(Guid id);
    Task Add(Customer customer);
    Task SaveChanges();
}

public interface ICustomerQueryService
{
    Task<List<Customer>> Search(string term);
    Task<CustomerStatistics> GetStatistics(Guid id);
}

public interface ICustomerOrdersService
{
    Task<List<Order>> GetOrders(Guid id);
}
```

### Dependency Inversion Principle (DIP)

**Definition:** High-level modules should not depend on low-level modules. Both should depend on abstractions.

**Bad Example:**
```csharp
public class CustomerService
{
    private SqlCustomerRepository _repository; // Concrete dependency!

    public CustomerService()
    {
        _repository = new SqlCustomerRepository(); // Tightly coupled!
    }
}
```

**Good Example:**
```csharp
public class CustomerService
{
    private readonly ICustomerRepository _repository; // Abstract dependency

    public CustomerService(ICustomerRepository repository) // Injected
    {
        _repository = repository;
    }
}

// Configured in Startup.cs:
services.AddScoped<ICustomerRepository, SqlCustomerRepository>();
```

---

## Domain-Driven Design (DDD)

### Bounded Contexts

**Definition:** Explicit boundaries within which a domain model is defined.

**Example Bounded Contexts:**
- **Customer Management Context:** Customer, Address, ContactInfo
- **Order Processing Context:** Order, OrderItem, Payment
- **Inventory Context:** Product, Stock, Warehouse
- **Identity Context:** User, Role, Permission

**Context Mapping:**
- Contexts communicate through well-defined interfaces
- Shared Kernel: Common types (Money, Address)
- Anti-Corruption Layer: Translate between contexts

### Aggregates

**Definition:** Cluster of domain objects treated as a single unit.

**Rules:**
- One entity is the Aggregate Root (e.g., Order)
- External objects can only reference the root
- Aggregates are transactional boundaries

**Example:**
```csharp
public class Order // Aggregate Root
{
    private readonly List<OrderItem> _items; // Part of aggregate
    public IReadOnlyList<OrderItem> Items => _items.AsReadOnly();

    public void AddItem(OrderItem item)
    {
        // Business rule enforced at aggregate level
        if (_items.Count >= 50)
            throw new DomainException("Cannot exceed 50 items per order");

        _items.Add(item);
    }
}

// OrderItem is only accessible through Order
```

### Value Objects

**Definition:** Objects defined by their attributes, not identity.

**Characteristics:**
- Immutable
- No identity
- Replaceable

**Example:**
```csharp
public class Money : ValueObject
{
    public decimal Amount { get; }
    public string Currency { get; }

    public Money(decimal amount, string currency)
    {
        if (amount < 0) throw new ArgumentException("Amount cannot be negative");
        Amount = amount;
        Currency = currency;
    }

    // Value objects are compared by value, not reference
    protected override IEnumerable<object> GetEqualityComponents()
    {
        yield return Amount;
        yield return Currency;
    }

    // Immutable operations return new instances
    public Money Add(Money other)
    {
        if (Currency != other.Currency)
            throw new InvalidOperationException("Cannot add different currencies");

        return new Money(Amount + other.Amount, Currency);
    }
}
```

### Domain Events

**Definition:** Something that happened in the domain that domain experts care about.

**Example:**
```csharp
public class CustomerCreated : DomainEvent
{
    public Guid CustomerId { get; }
    public string CustomerName { get; }
    public DateTime OccurredAt { get; }

    public CustomerCreated(Guid customerId, string customerName)
    {
        CustomerId = customerId;
        CustomerName = customerName;
        OccurredAt = DateTime.UtcNow;
    }
}

// Entity raises events
public class Customer
{
    private List<DomainEvent> _domainEvents = new();
    public IReadOnlyList<DomainEvent> DomainEvents => _domainEvents.AsReadOnly();

    protected void AddDomainEvent(DomainEvent domainEvent)
    {
        _domainEvents.Add(domainEvent);
    }

    public void ClearDomainEvents()
    {
        _domainEvents.Clear();
    }
}

// Events are dispatched after SaveChanges
public async Task SaveChanges()
{
    await _context.SaveChangesAsync();
    await DispatchDomainEvents();
}
```

---

## Layering and Dependencies

### Dependency Flow Rules

```
API Layer
   ↓ (depends on)
Application Layer
   ↓ (depends on)
Domain Layer
   ↑ (implemented by)
Infrastructure Layer
```

**Key Rules:**
1. Domain Layer has NO dependencies (pure C#)
2. Application Layer depends ONLY on Domain
3. Infrastructure implements interfaces from Domain/Application
4. API Layer orchestrates, delegates to Application

### Dependency Injection

**Configure in Program.cs / Startup.cs:**
```csharp
// Domain Services
services.AddScoped<ICustomerDomainService, CustomerDomainService>();

// Application Services
services.AddScoped<CreateCustomerUseCase>();
services.AddScoped<GetCustomerQuery>();

// Infrastructure
services.AddScoped<ICustomerRepository, CustomerRepository>();
services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(connectionString));

// External Services
services.AddScoped<IEmailService, SendGridEmailService>();
services.AddScoped<ITimelineService, TimelineService>();
```

---

## API Design Principles

### RESTful Conventions

- Use nouns for resources (`/api/customers`, not `/api/getCustomers`)
- Use HTTP verbs correctly (GET, POST, PUT, DELETE)
- Return appropriate status codes (200, 201, 400, 404, 500)
- Use plural nouns (`/customers`, not `/customer`)
- Use hierarchical URLs for relationships (`/customers/{id}/orders`)

### Versioning

**URL Versioning (Recommended):**
```
/api/v1/customers
/api/v2/customers
```

**Header Versioning (Alternative):**
```
GET /api/customers
Accept: application/vnd.yourapp.v1+json
```

### Error Handling

**Consistent Error Contract:**
```json
{
  "code": "VALIDATION_ERROR",
  "message": "Invalid request data",
  "details": [
    {
      "field": "name",
      "message": "Name is required"
    }
  ],
  "traceId": "550e8400-e29b-41d4-a716-446655440000"
}
```

See `agents/architect/references/api-design-guide.md` for comprehensive API design patterns.

---

## Data Modeling Principles

### Normalization

- **1NF:** Atomic values, no repeating groups
- **2NF:** No partial dependencies
- **3NF:** No transitive dependencies

**When to Denormalize:**
- Read-heavy queries with complex joins
- Performance requirements dictate it
- Always document why

### Indexes

**When to Add Index:**
- Foreign keys (EF Core doesn't auto-index FKs!)
- Columns used in WHERE clauses
- Columns used in ORDER BY
- Columns used in JOIN conditions

**When NOT to Add Index:**
- Small tables (< 1000 rows)
- Columns rarely queried
- Columns with low selectivity (e.g., boolean flags)

### Audit Fields

**Every entity should have:**
```csharp
public DateTime CreatedAt { get; set; }
public Guid CreatedBy { get; set; }
public DateTime UpdatedAt { get; set; }
public Guid UpdatedBy { get; set; }
public DateTime? DeletedAt { get; set; } // Soft delete
```

See `agents/architect/references/data-modeling-guide.md` for comprehensive data modeling patterns.

---

## Security Architecture

### Defense in Depth

**Multiple layers of security:**
1. **Network:** HTTPS, firewall
2. **Authentication:** OIDC Provider (JWT)
3. **Authorization:** Casbin (ABAC)
4. **Application:** Input validation, SQL injection prevention
5. **Data:** Encryption at rest, TDE
6. **Audit:** Comprehensive logging

### Authorization Layers

```
┌─────────────────────────┐
│   API Controller        │ ← [Authorize] attribute
└──────────┬──────────────┘
           │
           ↓
┌──────────┴──────────────┐
│   Authorization Service │ ← Casbin ABAC check
└──────────┬──────────────┘
           │
           ↓
┌──────────┴──────────────┐
│   Application Service   │ ← Business rule validation
└──────────┬──────────────┘
           │
           ↓
┌──────────┴──────────────┐
│   Domain Entity         │ ← Invariant enforcement
└─────────────────────────┘
```

### Principle of Least Privilege

- Users get ONLY permissions they need
- Default deny (explicit allow required)
- Separate read and write permissions
- Row-level security where applicable

See `agents/architect/references/authorization-patterns.md` for comprehensive authorization patterns.

---

## Performance and Scalability

### Database Performance

**Avoid N+1 Queries:**
```csharp
// Bad: N+1
var customers = await _context.Customers.ToListAsync();
foreach (var customer in customers)
{
    var orders = await _context.Orders.Where(o => o.CustomerId == customer.Id).ToListAsync();
}

// Good: Eager loading
var customers = await _context.Customers
    .Include(c => c.Orders)
    .ToListAsync();
```

**Use Projections:**
```csharp
// Bad: Load entire entity
var customers = await _context.Customers.ToListAsync();

// Good: Project to DTO
var customers = await _context.Customers
    .Select(c => new CustomerListDto
    {
        Id = c.Id,
        Name = c.Name,
        Status = c.Status
    })
    .ToListAsync();
```

### Caching Strategy

**Cache Layers:**
1. **Memory Cache:** Short-lived, high-speed (reference data)
2. **Distributed Cache:** Redis for shared state
3. **CDN:** Static assets

**What to Cache:**
- Reference data (regions, categories)
- Infrequently changing data (customer details)
- Expensive calculations (customer statistics)

**What NOT to Cache:**
- Sensitive data
- Rapidly changing data
- Large objects

### Pagination

**Always paginate list endpoints:**
```csharp
public async Task<PagedResult<CustomerDto>> GetCustomers(int page, int pageSize)
{
    var query = _context.Customers.AsQueryable();

    var totalCount = await query.CountAsync();
    var items = await query
        .Skip((page - 1) * pageSize)
        .Take(pageSize)
        .ToListAsync();

    return new PagedResult<CustomerDto>
    {
        Items = items,
        Page = page,
        PageSize = pageSize,
        TotalCount = totalCount,
        TotalPages = (int)Math.Ceiling(totalCount / (double)pageSize)
    };
}
```

---

## Observability

### Logging Levels

- **Trace:** Very detailed, disabled in production
- **Debug:** Diagnostic info, disabled in production
- **Information:** General flow (requests, key events)
- **Warning:** Unexpected but recoverable (retry logic, degraded performance)
- **Error:** Errors that require attention
- **Critical:** Application crash, data loss

### Structured Logging

```csharp
_logger.LogInformation(
    "Customer {CustomerId} created by user {UserId}",
    customerId,
    userId
);

// JSON output:
// {
//   "timestamp": "2024-01-15T10:30:00Z",
//   "level": "Information",
//   "message": "Customer 123... created by user 456...",
//   "customerId": "123e4567-e89b-12d3-a456-426614174000",
//   "userId": "987e6543-e21b-43a1-b789-123456789abc"
// }
```

### Correlation IDs

**Track requests across services:**
```csharp
public class CorrelationIdMiddleware
{
    public async Task Invoke(HttpContext context)
    {
        var correlationId = context.Request.Headers["X-Correlation-ID"].FirstOrDefault()
            ?? Guid.NewGuid().ToString();

        context.Items["CorrelationId"] = correlationId;
        context.Response.Headers.Add("X-Correlation-ID", correlationId);

        using (_logger.BeginScope(new Dictionary<string, object> { ["CorrelationId"] = correlationId }))
        {
            await _next(context);
        }
    }
}
```

---

## Common Anti-Patterns

### God Objects

**Anti-Pattern:** One class does everything
```csharp
public class CustomerManager
{
    public void CreateCustomer() { }
    public void UpdateCustomer() { }
    public void DeleteCustomer() { }
    public void SendEmail() { }
    public void GenerateReport() { }
    public void CalculateStatistics() { }
    // ... 50 more methods
}
```

**Solution:** Split into focused classes with single responsibilities

### Anemic Domain Model

**Anti-Pattern:** Entities with no behavior, all logic in services
```csharp
public class Customer
{
    public Guid Id { get; set; }
    public string Name { get; set; }
    public string Status { get; set; }
    // Just properties, no behavior
}

public class CustomerService
{
    public void ActivateCustomer(Customer customer)
    {
        customer.Status = "Active"; // Logic outside entity
    }
}
```

**Solution:** Move behavior into entities
```csharp
public class Customer
{
    public void Activate()
    {
        if (Status == CustomerStatus.Suspended)
            throw new DomainException("Cannot activate suspended customer");

        Status = CustomerStatus.Active;
    }
}
```

### Leaky Abstractions

**Anti-Pattern:** Implementation details leak through interfaces
```csharp
public interface ICustomerRepository
{
    Task<IQueryable<Customer>> GetQueryable(); // Leaks EF Core IQueryable!
}
```

**Solution:** Hide implementation details
```csharp
public interface ICustomerRepository
{
    Task<List<Customer>> Search(CustomerSearchCriteria criteria);
}
```

### Magic Strings/Numbers

**Anti-Pattern:**
```csharp
if (customer.Status == "Active") // Magic string
{
    // ...
}
```

**Solution:** Use enums or constants
```csharp
public enum CustomerStatus
{
    Active,
    Inactive,
    Suspended
}

if (customer.Status == CustomerStatus.Active)
{
    // ...
}
```

---

## Further Reading

- Clean Architecture by Robert C. Martin
- Domain-Driven Design by Eric Evans
- Implementing Domain-Driven Design by Vaughn Vernon
- Building Microservices by Sam Newman
- Microsoft .NET Architecture Guides: https://learn.microsoft.com/dotnet/architecture/

---

## Frontend UI Governance Addendum (Theme-Safe Architecture)

Architects should define frontend visual quality constraints as enforceable rules, not only preferences.

### Required Constraints for Theme-Aware UI

- Use semantic theme tokens/classes for UI text, surfaces, and borders (for example `text-text-primary`, `bg-surface-card`, `border-surface-border`).
- Prohibit raw palette utility classes for app UI (`zinc/slate/gray/neutral/stone`) unless an exception is explicitly documented for a visual effect.
- Require dark and light theme verification for styling changes in acceptance criteria, test plans, or assembly checkpoints.
- Require automated enforcement where possible (static guard for class usage plus visual/theme smoke tests for critical pages).

### Handoff Guidance to Frontend and QA

- Identify theme-sensitive screens/components (cards, forms, overlays, data-dense widgets).
- Define the minimum visual smoke scope per feature (for example dashboard + affected CRUD screens).
- Ensure CI includes fast style-policy checks and artifacted browser tests for regression diagnosis.

### Frontend Module Boundary Governance (Vertical Slices)

Architects should define frontend module boundaries early enough that implementation agents do not spread feature code across unrelated global folders.

**Required guidance for frontend-heavy features**
- Specify the feature slice name(s) in the assembly plan (for example `features/customers`, `features/orders`).
- State what code must remain feature-local vs what may be shared.
- Prefer co-location of feature components, hooks, API modules, feature DTO/types, and tests.
- Reserve shared/global folders for primitives, app shell, and truly cross-feature utilities.

**Handoff example (good)**
- `{PRODUCT_ROOT}/experience/src/features/orders/components/*` for list cards/status badges/popovers
- `{PRODUCT_ROOT}/experience/src/features/orders/hooks/*` for fetch/mutation query hooks
- `{PRODUCT_ROOT}/experience/src/features/orders/types/*` for feature DTOs not shared elsewhere
- `{PRODUCT_ROOT}/experience/src/components/ui/*` only for reusable primitives

**Anti-pattern to call out explicitly**
- Adding new feature-only hooks/types/components to global `src/hooks`, `src/types`, or `src/components` because it is faster in the moment. This increases cognitive drift and weakens ownership boundaries.

---

## Version History

**Version 2.0** - 2026-02-03 - Replaced all solution-specific entities with standard generic set (customers/orders). Replaced Nebula bounded contexts with generic examples. See `BOUNDARY-POLICY.md` → "Standard Example Entities" for the convention.
**Version 1.0** - 2026-01-26 - Initial architecture best practices guide

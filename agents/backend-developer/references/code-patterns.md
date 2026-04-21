# Backend Developer Code Patterns

Reference patterns extracted from the main SKILL.md for detailed implementation guidance.

## Best Practices

### Domain Entity with Audit Fields
```csharp
using System;

namespace MyApp.Domain.Entities;

public class Customer
{
    public Guid Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Email { get; set; } = string.Empty;
    public string Phone { get; set; } = string.Empty;
    public CustomerStatus Status { get; set; }

    // Audit fields (required on all entities)
    public DateTime CreatedAt { get; set; }
    public Guid CreatedBy { get; set; }
    public DateTime UpdatedAt { get; set; }
    public Guid UpdatedBy { get; set; }

    // Soft delete (required on all entities)
    public bool IsDeleted { get; set; }
    public DateTime? DeletedAt { get; set; }
    public Guid? DeletedBy { get; set; }

    // Business logic
    public void Activate()
    {
        if (IsDeleted)
            throw new InvalidOperationException("Cannot activate deleted customer");

        Status = CustomerStatus.Active;
    }
}

public enum CustomerStatus
{
    Active,
    Inactive
}
```

### JSON Schema Validation with NJsonSchema
```csharp
using NJsonSchema;
using NJsonSchema.Validation;
using Microsoft.AspNetCore.Mvc;

namespace MyApp.Api.Endpoints;

public static class CustomerEndpoints
{
    // Load schema from shared location
    private static readonly JsonSchema CustomerSchema =
        JsonSchema.FromFileAsync("../../planning-mds/schemas/customer.schema.json").Result;

    public static void MapCustomerEndpoints(this WebApplication app)
    {
        app.MapPost("/api/customers", CreateCustomer)
            .RequireAuthorization();
    }

    private static async Task<IResult> CreateCustomer(
        CreateCustomerDto dto,
        ICustomerService customerService,
        IAuthorizationService authz,
        HttpContext context)
    {
        // 1. Validate against JSON Schema
        var validator = new JsonSchemaValidator();
        var validationResult = validator.Validate(
            System.Text.Json.JsonSerializer.Serialize(dto),
            CustomerSchema);

        if (validationResult.Count > 0)
        {
            // Return RFC 7807 ProblemDetails
            var errors = validationResult
                .Select(e => new { Field = e.Path, Error = e.ToString() })
                .ToList();

            return Results.ValidationProblem(
                errors.ToDictionary(e => e.Field, e => new[] { e.Error }));
        }

        // 2. Authorize
        if (!await authz.CanCreate(context.User, "customer"))
        {
            return Results.Problem(
                statusCode: 403,
                title: "Forbidden",
                detail: "You do not have permission to create customers");
        }

        // 3. Create customer
        var customer = await customerService.CreateAsync(dto);

        // 4. Return 201 Created
        return Results.Created($"/api/customers/{customer.Id}", customer);
    }
}
```

### Alternative: Validation Attribute
```csharp
using NJsonSchema;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Filters;

// Custom validation attribute
public class ValidateJsonSchemaAttribute : ActionFilterAttribute
{
    private readonly string _schemaPath;

    public ValidateJsonSchemaAttribute(string schemaPath)
    {
        _schemaPath = schemaPath;
    }

    public override async Task OnActionExecutionAsync(
        ActionExecutingContext context,
        ActionExecutionDelegate next)
    {
        var schema = await JsonSchema.FromFileAsync(_schemaPath);
        var validator = new JsonSchemaValidator();

        // Get request body
        var body = context.ActionArguments.Values.FirstOrDefault();
        var json = System.Text.Json.JsonSerializer.Serialize(body);

        var errors = validator.Validate(json, schema);
        if (errors.Count > 0)
        {
            context.Result = new BadRequestObjectResult(new ProblemDetails
            {
                Status = 400,
                Title = "Validation failed",
                Detail = string.Join(", ", errors.Select(e => e.ToString()))
            });
            return;
        }

        await next();
    }
}

// Usage
[HttpPost]
[ValidateJsonSchema("schemas/customer.schema.json")]
public async Task<IActionResult> CreateCustomer(CreateCustomerDto dto)
{
    // Validation already done by attribute
    // ...
}
```

### EF Core Configuration with Audit Fields
```csharp
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using MyApp.Domain.Entities;

namespace MyApp.Infrastructure.Persistence.Configurations;

public class CustomerConfiguration : IEntityTypeConfiguration<Customer>
{
    public void Configure(EntityTypeBuilder<Customer> builder)
    {
        builder.ToTable("Customers");

        builder.HasKey(b => b.Id);

        builder.Property(b => b.Name)
            .IsRequired()
            .HasMaxLength(100);

        builder.Property(b => b.Email)
            .IsRequired()
            .HasMaxLength(255);

        builder.Property(b => b.Phone)
            .HasMaxLength(20);

        // Audit fields
        builder.Property(b => b.CreatedAt)
            .IsRequired();

        builder.Property(b => b.CreatedBy)
            .IsRequired();

        builder.Property(b => b.UpdatedAt)
            .IsRequired();

        builder.Property(b => b.UpdatedBy)
            .IsRequired();

        // Soft delete
        builder.Property(b => b.IsDeleted)
            .IsRequired()
            .HasDefaultValue(false);

        builder.HasQueryFilter(b => !b.IsDeleted); // Global query filter

        // Indexes
        builder.HasIndex(b => b.Email);
        builder.HasIndex(b => b.IsDeleted);
    }
}
```

## Repository Pattern
```csharp
// Application layer - Interface
namespace MyApp.Application.Interfaces;

public interface ICustomerRepository
{
    Task<Customer?> GetByIdAsync(Guid id, CancellationToken ct = default);
    Task<IEnumerable<Customer>> ListAsync(CancellationToken ct = default);
    Task<Customer> AddAsync(Customer customer, CancellationToken ct = default);
    Task UpdateAsync(Customer customer, CancellationToken ct = default);
    Task DeleteAsync(Guid id, CancellationToken ct = default);
}

// Infrastructure layer - Implementation
namespace MyApp.Infrastructure.Persistence.Repositories;

public class CustomerRepository : ICustomerRepository
{
    private readonly AppDbContext _context;

    public CustomerRepository(AppDbContext context)
    {
        _context = context;
    }

    public async Task<Customer?> GetByIdAsync(Guid id, CancellationToken ct = default)
    {
        return await _context.Customers
            .FirstOrDefaultAsync(b => b.Id == id, ct);
    }

    public async Task<IEnumerable<Customer>> ListAsync(CancellationToken ct = default)
    {
        return await _context.Customers
            .OrderBy(b => b.Name)
            .ToListAsync(ct);
    }

    public async Task<Customer> AddAsync(Customer customer, CancellationToken ct = default)
    {
        _context.Customers.Add(customer);
        await _context.SaveChangesAsync(ct);
        return customer;
    }

    public async Task UpdateAsync(Customer customer, CancellationToken ct = default)
    {
        _context.Customers.Update(customer);
        await _context.SaveChangesAsync(ct);
    }

    public async Task DeleteAsync(Guid id, CancellationToken ct = default)
    {
        var customer = await GetByIdAsync(id, ct);
        if (customer != null)
        {
            customer.IsDeleted = true;
            customer.DeletedAt = DateTime.UtcNow;
            // DeletedBy set by SaveChanges interceptor
            await _context.SaveChangesAsync(ct);
        }
    }
}
```

## Audit Interceptor (Auto-set Audit Fields)
```csharp
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Diagnostics;

namespace MyApp.Infrastructure.Persistence;

public class AuditInterceptor : SaveChangesInterceptor
{
    private readonly ICurrentUserService _currentUser;

    public AuditInterceptor(ICurrentUserService currentUser)
    {
        _currentUser = currentUser;
    }

    public override InterceptionResult<int> SavingChanges(
        DbContextEventData eventData,
        InterceptionResult<int> result)
    {
        UpdateAuditFields(eventData.Context);
        return base.SavingChanges(eventData, result);
    }

    public override ValueTask<InterceptionResult<int>> SavingChangesAsync(
        DbContextEventData eventData,
        InterceptionResult<int> result,
        CancellationToken ct = default)
    {
        UpdateAuditFields(eventData.Context);
        return base.SavingChangesAsync(eventData, result, ct);
    }

    private void UpdateAuditFields(DbContext? context)
    {
        if (context == null) return;

        var userId = _currentUser.UserId;
        var now = DateTime.UtcNow;

        foreach (var entry in context.ChangeTracker.Entries())
        {
            if (entry.State == EntityState.Added)
            {
                entry.Property("CreatedAt").CurrentValue = now;
                entry.Property("CreatedBy").CurrentValue = userId;
                entry.Property("UpdatedAt").CurrentValue = now;
                entry.Property("UpdatedBy").CurrentValue = userId;
            }
            else if (entry.State == EntityState.Modified)
            {
                entry.Property("UpdatedAt").CurrentValue = now;
                entry.Property("UpdatedBy").CurrentValue = userId;
            }
            else if (entry.State == EntityState.Deleted)
            {
                // Soft delete
                entry.State = EntityState.Modified;
                entry.Property("IsDeleted").CurrentValue = true;
                entry.Property("DeletedAt").CurrentValue = now;
                entry.Property("DeletedBy").CurrentValue = userId;
            }
        }
    }
}
```

## Timeline Service (Create Audit Events)
```csharp
namespace MyApp.Infrastructure.Services;

public class TimelineService : ITimelineService
{
    private readonly AppDbContext _context;
    private readonly ICurrentUserService _currentUser;

    public TimelineService(AppDbContext context, ICurrentUserService currentUser)
    {
        _context = context;
        _currentUser = currentUser;
    }

    public async Task CreateEventAsync(
        string entityType,
        Guid entityId,
        string eventType,
        string description,
        object? metadata = null,
        CancellationToken ct = default)
    {
        var timelineEvent = new ActivityTimelineEvent
        {
            Id = Guid.NewGuid(),
            EntityType = entityType,
            EntityId = entityId,
            EventType = eventType,
            Description = description,
            PerformedBy = _currentUser.UserId,
            PerformedAt = DateTime.UtcNow,
            Metadata = metadata != null
                ? System.Text.Json.JsonSerializer.Serialize(metadata)
                : null
        };

        _context.ActivityTimelineEvents.Add(timelineEvent);
        await _context.SaveChangesAsync(ct);
    }
}

// Usage in service
public async Task<Customer> UpdateCustomerAsync(Guid id, UpdateCustomerDto dto)
{
    var customer = await _repository.GetByIdAsync(id);
    if (customer == null)
        throw new NotFoundException("Customer not found");

    customer.Name = dto.Name;
    customer.Email = dto.Email;

    await _repository.UpdateAsync(customer);

    // Create timeline event (required!)
    await _timelineService.CreateEventAsync(
        entityType: "Customer",
        entityId: id,
        eventType: "CustomerUpdated",
        description: $"Customer {customer.Name} updated",
        metadata: new { Changes = dto });

    return customer;
}
```

## Authorization with Casbin
```csharp
using Casbin;
using Casbin.AspNetCore.Authorization;

namespace MyApp.Infrastructure.Services;

public class AuthorizationService : IAuthorizationService
{
    private readonly IEnforcer _enforcer;

    public AuthorizationService(IEnforcer enforcer)
    {
        _enforcer = enforcer;
    }

    public async Task<bool> CanCreate(ClaimsPrincipal user, string resource)
    {
        var userId = user.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        var roles = user.FindAll(ClaimTypes.Role).Select(c => c.Value);

        // Check ABAC policy
        foreach (var role in roles)
        {
            if (await _enforcer.EnforceAsync(role, resource, "create"))
                return true;
        }

        return false;
    }

    public async Task<bool> CanRead(ClaimsPrincipal user, object entity)
    {
        var userId = user.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        var roles = user.FindAll(ClaimTypes.Role).Select(c => c.Value);

        // Check attribute-based rules
        // Example: Can only read if entity is in user's region

        return true; // Implement based on ABAC rules
    }
}

// Casbin policy file (conf/policy.csv)
// p, admin, customer, create
// p, admin, customer, read
// p, admin, customer, update
// p, admin, customer, delete
// p, user, customer, read
```

## Common Patterns

### CRUD Service Pattern
```csharp
public class CustomerService : ICustomerService
{
    private readonly ICustomerRepository _repository;
    private readonly ITimelineService _timeline;
    private readonly IAuthorizationService _authz;

    public async Task<Customer> CreateAsync(CreateCustomerDto dto)
    {
        var customer = new Customer
        {
            Id = Guid.NewGuid(),
            Name = dto.Name,
            Email = dto.Email,
            Phone = dto.Phone,
            Status = CustomerStatus.Active
            // Audit fields set by interceptor
        };

        await _repository.AddAsync(customer);

        await _timeline.CreateEventAsync(
            "Customer", customer.Id, "CustomerCreated",
            $"Customer {customer.Name} created");

        return customer;
    }
}
```

### Error Handling with ProblemDetails
```csharp
// Custom exception
public class NotFoundException : Exception
{
    public NotFoundException(string message) : base(message) { }
}

// Global exception handler
app.UseExceptionHandler(exceptionHandlerApp =>
{
    exceptionHandlerApp.Run(async context =>
    {
        var exception = context.Features
            .Get<IExceptionHandlerFeature>()?.Error;

        var problemDetails = exception switch
        {
            NotFoundException => new ProblemDetails
            {
                Status = 404,
                Title = "Not Found",
                Detail = exception.Message
            },
            ValidationException => new ProblemDetails
            {
                Status = 400,
                Title = "Validation Error",
                Detail = exception.Message
            },
            _ => new ProblemDetails
            {
                Status = 500,
                Title = "Internal Server Error",
                Detail = "An unexpected error occurred"
            }
        };

        context.Response.StatusCode = problemDetails.Status ?? 500;
        await context.Response.WriteAsJsonAsync(problemDetails);
    });
});
```

## Security Considerations

### Input Validation
- **Always validate** with JSON Schema before processing
- **Never trust** client input
- **Sanitize** all inputs before database operations
- **Use parameterized queries** (EF Core does this automatically)

### Authorization
- **Check permissions** on every operation
- **Never rely** on client-side authorization
- **Log authorization failures** for audit
- **Use ABAC** for fine-grained control

### Secrets Management
- **Never hardcode** connection strings, API keys, passwords
- **Use configuration** (appsettings.json, environment variables)
- **Use secret management** (Azure Key Vault, AWS Secrets Manager)
- **Rotate secrets** regularly

### SQL Injection Prevention
```csharp
// GOOD - EF Core uses parameterized queries
var customer = await _context.Customers
    .Where(b => b.Email == email)
    .FirstOrDefaultAsync();

// BAD - Never use raw SQL with string interpolation
// var customer = await _context.Customers
//     .FromSqlRaw($"SELECT * FROM Customers WHERE Email = '{email}'")
//     .FirstOrDefaultAsync();
```

## Testing Strategy

### Unit Tests (Domain & Application)
```csharp
using Xunit;
using Shouldly;

public class CustomerTests
{
    [Fact]
    public void Activate_ShouldSetStatusToActive()
    {
        // Arrange
        var customer = new Customer { Status = CustomerStatus.Inactive };

        // Act
        customer.Activate();

        // Assert
        customer.Status.ShouldBe(CustomerStatus.Active);
    }

    [Fact]
    public void Activate_WhenDeleted_ShouldThrowException()
    {
        // Arrange
        var customer = new Customer { IsDeleted = true };

        // Act & Assert
        Should.Throw<InvalidOperationException>(() => customer.Activate());
    }
}
```

### Integration Tests (API)
```csharp
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;
using Shouldly;

public class CustomerEndpointTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;

    public CustomerEndpointTests(WebApplicationFactory<Program> factory)
    {
        _client = factory.CreateClient();
    }

    [Fact]
    public async Task CreateCustomer_WithValidData_ReturnsCreated()
    {
        // Arrange
        var dto = new CreateCustomerDto
        {
            Name = "Test Customer",
            Email = "test@example.com",
            Phone = "1234567890"
        };

        // Act
        var response = await _client.PostAsJsonAsync("/api/customers", dto);

        // Assert
        response.StatusCode.ShouldBe(HttpStatusCode.Created);
        var customer = await response.Content.ReadFromJsonAsync<Customer>();
        customer.ShouldNotBeNull();
        customer!.Name.ShouldBe("Test Customer");
    }

    [Fact]
    public async Task CreateCustomer_WithInvalidEmail_ReturnsBadRequest()
    {
        // Arrange
        var dto = new CreateCustomerDto
        {
            Name = "Test Customer",
            Email = "invalid-email",
            Phone = "1234567890"
        };

        // Act
        var response = await _client.PostAsJsonAsync("/api/customers", dto);

        // Assert
        response.StatusCode.ShouldBe(HttpStatusCode.BadRequest);
    }
}
```

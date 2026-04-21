# Data Modeling Guide

> **Examples in this guide use `customers` and `orders` as illustrative entities.
> These are not prescriptive — substitute your own domain entities when applying
> these patterns. See `BOUNDARY-POLICY.md` → "Standard Example Entities" for
> the full convention and field mapping.

---

Comprehensive guide for designing database schemas with Entity Framework Core 10, PostgreSQL, and Clean Architecture principles.

---

## 1. Entity Design Patterns

### 1.1 Base Entity Classes

All domain entities should inherit from a common base class to ensure consistency.

```csharp
public abstract class BaseEntity
{
    public Guid Id { get; set; } = Guid.NewGuid();

    // Audit fields (who and when)
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public Guid CreatedBy { get; set; }
    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
    public Guid UpdatedBy { get; set; }

    // Soft delete
    public DateTime? DeletedAt { get; set; }

    // Helper methods
    public bool IsDeleted => DeletedAt.HasValue;
    public void SoftDelete() => DeletedAt = DateTime.UtcNow;
    public void Restore() => DeletedAt = null;
}
```

**Benefits:**
- Consistent audit trail across all entities
- Automatic soft delete support
- Reduces boilerplate in entity classes
- Easy to add global conventions (e.g., RowVersion for concurrency)

**Convention:**
- All entities in Domain layer inherit from `BaseEntity`
- Infrastructure layer (EF Core) automatically sets audit fields via interceptors
- Global query filter applies `WHERE DeletedAt IS NULL` to all queries

---

### 1.2 Soft Delete Pattern

Soft delete marks records as deleted without removing them from the database, preserving audit trail and allowing restoration.

**Implementation:**

```csharp
// Entity with soft delete
public class Customer : BaseEntity
{
    public string Name { get; set; }
    public string TaxId { get; set; }
    // ... other fields
}

// EF Core configuration
public class CustomerConfiguration : IEntityTypeConfiguration<Customer>
{
    public void Configure(EntityTypeBuilder<Customer> builder)
    {
        // Global query filter - automatically excludes soft-deleted records
        builder.HasQueryFilter(c => c.DeletedAt == null);

        // Partial index for active records only (PostgreSQL)
        builder.HasIndex(c => c.DeletedAt)
            .HasFilter("DeletedAt IS NULL")
            .HasDatabaseName("IX_Customers_ActiveOnly");
    }
}

// Repository pattern
public class CustomerRepository
{
    private readonly ApplicationDbContext _context;

    // Get active customers (soft-deleted automatically excluded)
    public async Task<List<Customer>> GetAllAsync()
    {
        return await _context.Customers.ToListAsync();
    }

    // Include soft-deleted customers (bypass global filter)
    public async Task<List<Customer>> GetAllIncludingDeletedAsync()
    {
        return await _context.Customers
            .IgnoreQueryFilters()
            .ToListAsync();
    }

    // Soft delete
    public async Task DeleteAsync(Guid id)
    {
        var customer = await _context.Customers.FindAsync(id);
        customer.SoftDelete();
        await _context.SaveChangesAsync();
    }

    // Restore soft-deleted
    public async Task RestoreAsync(Guid id)
    {
        var customer = await _context.Customers
            .IgnoreQueryFilters()
            .FirstAsync(c => c.Id == id);
        customer.Restore();
        await _context.SaveChangesAsync();
    }
}
```

**Considerations:**
- Soft-deleted records still count against database size
- Unique constraints must account for soft-deleted records (e.g., tax ID can be reused after soft delete)
- Consider hard delete after retention period (e.g., 7 years)

---

### 1.3 Audit Fields (Who and When)

Every mutation should track who made the change and when.

**Automatic Audit via SaveChanges Interceptor:**

```csharp
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

    private void UpdateAuditFields(DbContext? context)
    {
        if (context == null) return;

        var userId = _currentUser.UserId;
        var timestamp = DateTime.UtcNow;

        foreach (var entry in context.ChangeTracker.Entries<BaseEntity>())
        {
            switch (entry.State)
            {
                case EntityState.Added:
                    entry.Entity.CreatedAt = timestamp;
                    entry.Entity.CreatedBy = userId;
                    entry.Entity.UpdatedAt = timestamp;
                    entry.Entity.UpdatedBy = userId;
                    break;

                case EntityState.Modified:
                    entry.Entity.UpdatedAt = timestamp;
                    entry.Entity.UpdatedBy = userId;
                    break;
            }
        }
    }
}
```

**Benefits:**
- No manual setting of audit fields in business logic
- Consistent across all entities
- Impossible to forget

---

### 1.4 Value Objects (Owned Entities)

Value objects are immutable objects without identity, defined by their properties.

**Example: Address Value Object:**

```csharp
public class Address
{
    public string Street { get; private set; }
    public string City { get; private set; }
    public string State { get; private set; }
    public string ZipCode { get; private set; }

    private Address() { } // EF Core constructor

    public Address(string street, string city, string state, string zipCode)
    {
        Street = street;
        City = city;
        State = state;
        ZipCode = zipCode;
    }

    // Value equality
    public override bool Equals(object? obj)
    {
        if (obj is not Address other) return false;
        return Street == other.Street && City == other.City &&
               State == other.State && ZipCode == other.ZipCode;
    }

    public override int GetHashCode() =>
        HashCode.Combine(Street, City, State, ZipCode);
}

// Entity using value object
public class Customer : BaseEntity
{
    public string Name { get; set; }
    public Address BillingAddress { get; set; } // Owned entity
    public Address ShippingAddress { get; set; }
}

// EF Core configuration
public class CustomerConfiguration : IEntityTypeConfiguration<Customer>
{
    public void Configure(EntityTypeBuilder<Customer> builder)
    {
        builder.OwnsOne(c => c.BillingAddress, address =>
        {
            address.Property(a => a.Street).HasColumnName("BillingStreet");
            address.Property(a => a.City).HasColumnName("BillingCity");
            address.Property(a => a.State).HasColumnName("BillingState");
            address.Property(a => a.ZipCode).HasColumnName("BillingZipCode");
        });

        builder.OwnsOne(c => c.ShippingAddress, address =>
        {
            address.Property(a => a.Street).HasColumnName("ShippingStreet");
            address.Property(a => a.City).HasColumnName("ShippingCity");
            address.Property(a => a.State).HasColumnName("ShippingState");
            address.Property(a => a.ZipCode).HasColumnName("ShippingZipCode");
        });
    }
}
```

**Result:** All address fields stored in Customers table (not separate table), value object enforces immutability and consistency.

---

### 1.5 Enumerations (String vs Int)

**String Enums (Recommended):**

```csharp
public class OrderStatus
{
    public const string Pending = nameof(Pending);
    public const string Processing = nameof(Processing);
    public const string Shipped = nameof(Shipped);
    public const string Delivered = nameof(Delivered);
    public const string Cancelled = nameof(Cancelled);
    public const string Returned = nameof(Returned);
}

public class Order : BaseEntity
{
    public string Status { get; set; } = OrderStatus.Pending;
}

// EF Core configuration
builder.Property(o => o.Status)
    .IsRequired()
    .HasMaxLength(50);
```

**Int Enums with Value Converter:**

```csharp
public enum OrderStatusEnum
{
    Pending = 1,
    Processing = 2,
    Shipped = 3,
    Delivered = 4,
    Cancelled = 5,
    Returned = 6
}

// EF Core configuration - store as string in database
builder.Property(o => o.Status)
    .HasConversion<string>()
    .IsRequired()
    .HasMaxLength(50);
```

**Recommendation:** Use string enums (self-documenting in database, easier to query, no magic numbers).

---

## 2. Relationship Patterns

### 2.1 One-to-Many Relationships

**Example: Customer → Addresses**

```csharp
public class Customer : BaseEntity
{
    public string Name { get; set; }

    // Navigation property (one customer has many addresses)
    public ICollection<AddressEntity> Addresses { get; set; } = new List<AddressEntity>();
}

public class AddressEntity : BaseEntity
{
    public string Street { get; set; }
    public string City { get; set; }

    // Foreign key
    public Guid CustomerId { get; set; }

    // Navigation property (many addresses belong to one customer)
    public Customer Customer { get; set; }
}

// EF Core configuration
public class AddressEntityConfiguration : IEntityTypeConfiguration<AddressEntity>
{
    public void Configure(EntityTypeBuilder<AddressEntity> builder)
    {
        builder.HasOne(a => a.Customer)
            .WithMany(c => c.Addresses)
            .HasForeignKey(a => a.CustomerId)
            .OnDelete(DeleteBehavior.Cascade); // When customer deleted, delete addresses
    }
}
```

**Cascade Behaviors:**
- `Cascade`: Delete children when parent deleted (use for owned relationships)
- `Restrict`: Prevent parent delete if children exist (use for critical relationships like Customer → Orders)
- `SetNull`: Set FK to null when parent deleted (use for optional relationships)

---

### 2.2 Many-to-Many Relationships

**Modern Approach (EF Core 5+):** Use explicit join entity for metadata.

**Example: Product → Categories (many products in many categories)**

```csharp
public class Product : BaseEntity
{
    public string Name { get; set; }
    public ICollection<ProductCategory> ProductCategories { get; set; } = new List<ProductCategory>();
}

public class Category : BaseEntity
{
    public string Name { get; set; }
    public ICollection<ProductCategory> ProductCategories { get; set; } = new List<ProductCategory>();
}

// Explicit join entity with metadata
public class ProductCategory : BaseEntity
{
    public Guid ProductId { get; set; }
    public Product Product { get; set; }

    public Guid CategoryId { get; set; }
    public Category Category { get; set; }

    // Additional metadata
    public int DisplayOrder { get; set; }
    public bool IsPrimary { get; set; } // Is this the primary category?
    public DateTime AssignedAt { get; set; }
}

// EF Core configuration
public class ProductCategoryConfiguration : IEntityTypeConfiguration<ProductCategory>
{
    public void Configure(EntityTypeBuilder<ProductCategory> builder)
    {
        builder.HasKey(pc => new { pc.ProductId, pc.CategoryId }); // Composite key

        builder.HasOne(pc => pc.Product)
            .WithMany(p => p.ProductCategories)
            .HasForeignKey(pc => pc.ProductId);

        builder.HasOne(pc => pc.Category)
            .WithMany(c => c.ProductCategories)
            .HasForeignKey(pc => pc.CategoryId);
    }
}
```

---

### 2.3 Self-Referencing Relationships

**Example: Organization Hierarchy (Parent → Subsidiaries)**

```csharp
public class Organization : BaseEntity
{
    public string Name { get; set; }

    // Self-referencing foreign key
    public Guid? ParentOrganizationId { get; set; }

    // Navigation properties
    public Organization? ParentOrganization { get; set; }
    public ICollection<Organization> Subsidiaries { get; set; } = new List<Organization>();
}

// EF Core configuration
public class OrganizationConfiguration : IEntityTypeConfiguration<Organization>
{
    public void Configure(EntityTypeBuilder<Organization> builder)
    {
        builder.HasOne(o => o.ParentOrganization)
            .WithMany(o => o.Subsidiaries)
            .HasForeignKey(o => o.ParentOrganizationId)
            .OnDelete(DeleteBehavior.Restrict); // Prevent cascade delete of entire tree
    }
}
```

---

### 2.4 Optional vs Required Relationships

**Required Relationship (FK cannot be null):**

```csharp
public class Order : BaseEntity
{
    // Required: Every order must have a customer
    public Guid CustomerId { get; set; }
    public Customer Customer { get; set; }
}

// EF Core knows it's required (non-nullable Guid)
```

**Optional Relationship (FK can be null):**

```csharp
public class Order : BaseEntity
{
    // Optional: Order may not have assigned processor yet
    public Guid? AssignedProcessorId { get; set; }
    public User? AssignedProcessor { get; set; }
}

// EF Core knows it's optional (nullable Guid?)
```

---

### 2.5 Navigation Properties (One-Way vs Two-Way)

**Two-Way Navigation (Recommended for most cases):**

```csharp
public class Customer : BaseEntity
{
    public ICollection<Order> Orders { get; set; }
}

public class Order : BaseEntity
{
    public Guid CustomerId { get; set; }
    public Customer Customer { get; set; } // Allows order.Customer.Name
}
```

**One-Way Navigation (When reverse navigation not needed):**

```csharp
public class ActivityTimelineEvent : BaseEntity
{
    public Guid UserId { get; set; }
    // No navigation property - don't need event.User typically
}
```

---

## 3. Migration Strategies

### 3.1 Code-First Migrations

**Create Migration:**

```bash
# Navigate to Infrastructure project
cd src/YourApp.Infrastructure

# Add migration
dotnet ef migrations add AddCustomerEntity --startup-project ../YourApp.API

# Review generated migration in Migrations/ folder
# Verify Up() and Down() methods

# Apply migration to database
dotnet ef database update --startup-project ../YourApp.API
```

**Generated Migration Example:**

```csharp
public partial class AddCustomerEntity : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.CreateTable(
            name: "Customers",
            columns: table => new
            {
                Id = table.Column<Guid>(nullable: false),
                Name = table.Column<string>(maxLength: 255, nullable: false),
                TaxId = table.Column<string>(maxLength: 50, nullable: false),
                CreatedAt = table.Column<DateTime>(nullable: false),
                // ... other columns
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_Customers", x => x.Id);
            });

        migrationBuilder.CreateIndex(
            name: "IX_Customers_TaxId",
            table: "Customers",
            column: "TaxId",
            unique: true);
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropTable("Customers");
    }
}
```

---

### 3.2 Seed Data Patterns

**Deterministic Seeding (Production Reference Data):**

```csharp
public class SeedDataConfiguration : IEntityTypeConfiguration<Region>
{
    public void Configure(EntityTypeBuilder<Region> builder)
    {
        // Seed reference data with deterministic GUIDs
        builder.HasData(
            new Region { Id = Guid.Parse("00000000-0000-0000-0000-000000000001"), Code = "NA", Name = "North America" },
            new Region { Id = Guid.Parse("00000000-0000-0000-0000-000000000002"), Code = "EU", Name = "Europe" },
            // ... other regions
        );
    }
}
```

**Idempotent Seeding (Development/Test Data):**

```csharp
public static class DatabaseSeeder
{
    public static async Task SeedDevelopmentDataAsync(ApplicationDbContext context)
    {
        // Seed only if no data exists
        if (await context.Customers.AnyAsync())
            return;

        var customers = new[]
        {
            new Customer { Id = Guid.NewGuid(), Name = "Acme Corp", TaxId = "12-3456789" },
            new Customer { Id = Guid.NewGuid(), Name = "Global Inc", TaxId = "98-7654321" }
        };

        await context.Customers.AddRangeAsync(customers);
        await context.SaveChangesAsync();
    }
}
```

---

### 3.3 Data Migration vs Schema Migration

**Schema Migration:** Changes table structure (add column, drop table, rename field).

**Data Migration:** Populates or transforms existing data.

**Example: Adding Status Field with Default Value**

```csharp
protected override void Up(MigrationBuilder migrationBuilder)
{
    // 1. Add column (nullable initially)
    migrationBuilder.AddColumn<string>(
        name: "Status",
        table: "Customers",
        maxLength: 20,
        nullable: true);

    // 2. Set default value for existing rows (data migration)
    migrationBuilder.Sql(
        "UPDATE Customers SET Status = 'Active' WHERE Status IS NULL");

    // 3. Make column required
    migrationBuilder.AlterColumn<string>(
        name: "Status",
        table: "Customers",
        maxLength: 20,
        nullable: false);
}
```

---

### 3.4 Handling Breaking Changes

**Renaming Column (with backward compatibility):**

```csharp
// Step 1: Add new column
migrationBuilder.AddColumn<string>(
    name: "CustomerName",
    table: "Customers");

// Step 2: Copy data from old column
migrationBuilder.Sql(
    "UPDATE Customers SET CustomerName = Name");

// Step 3: Drop old column (in next migration, after app updated)
migrationBuilder.DropColumn(
    name: "Name",
    table: "Customers");
```

---

### 3.5 Production Migration Checklist

- [ ] Test migration on development database
- [ ] Review generated SQL (`dotnet ef migrations script`)
- [ ] Backup production database before migration
- [ ] Run migration during maintenance window (if schema changes are breaking)
- [ ] Verify data integrity after migration
- [ ] Have rollback plan (migration's Down() method tested)

---

## 4. Query Optimization

### 4.1 Eager Loading (.Include, .ThenInclude)

**Problem: N+1 Queries**

```csharp
// BAD: N+1 queries (1 for customers + N for each customer's orders)
var customers = await context.Customers.ToListAsync(); // 1 query
foreach (var customer in customers)
{
    var orders = await context.Orders.Where(o => o.CustomerId == customer.Id).ToListAsync(); // N queries
}
```

**Solution: Eager Loading**

```csharp
// GOOD: Single query with JOIN
var customers = await context.Customers
    .Include(c => c.Orders)
    .ToListAsync();

// Multiple levels
var orders = await context.Orders
    .Include(o => o.Customer)
        .ThenInclude(c => c.ParentOrganization)
    .Include(o => o.Items)
        .ThenInclude(i => i.Product)
    .ToListAsync();
```

---

### 4.2 Projection (Select to DTOs)

**Problem: Loading Entire Entities**

```csharp
// BAD: Loads all 20 fields of Customer entity
var customers = await context.Customers.ToListAsync();
return customers.Select(c => new CustomerListItem { Id = c.Id, Name = c.Name });
```

**Solution: Project to DTO**

```csharp
// GOOD: SQL only selects Id, Name columns
var customers = await context.Customers
    .Select(c => new CustomerListItem
    {
        Id = c.Id,
        Name = c.Name,
        TaxId = c.TaxId
    })
    .ToListAsync();
```

---

### 4.3 Pagination (Skip/Take)

**Offset Pagination:**

```csharp
public async Task<PagedResult<Customer>> GetCustomersAsync(int page, int pageSize)
{
    var query = context.Customers.AsQueryable();

    var totalCount = await query.CountAsync();

    var customers = await query
        .OrderBy(c => c.Name)
        .Skip((page - 1) * pageSize)
        .Take(pageSize)
        .ToListAsync();

    return new PagedResult<Customer>
    {
        Data = customers,
        Page = page,
        PageSize = pageSize,
        TotalCount = totalCount,
        TotalPages = (int)Math.Ceiling(totalCount / (double)pageSize)
    };
}
```

**Keyset Pagination (for large datasets):**

```csharp
// More efficient than OFFSET for large datasets
var customers = await context.Customers
    .Where(c => c.Name.CompareTo(lastSeenName) > 0)
    .OrderBy(c => c.Name)
    .Take(pageSize)
    .ToListAsync();
```

---

### 4.4 Filtering Best Practices

**Use Indexed Columns in WHERE:**

```csharp
// GOOD: Status is indexed
var activeCustomers = await context.Customers
    .Where(c => c.Status == "Active")
    .ToListAsync();

// AVOID: String operations prevent index usage
var customers = await context.Customers
    .Where(c => c.Name.ToLower().Contains("acme")) // Can't use index
    .ToListAsync();

// BETTER: Use case-insensitive collation in database
var customers = await context.Customers
    .Where(c => EF.Functions.ILike(c.Name, "%acme%")) // Uses index with PostgreSQL ILIKE
    .ToListAsync();
```

---

### 4.5 Avoiding N+1 Queries (Batching)

**Use .Include() or Explicit Loading:**

```csharp
// Explicit loading (load related data separately)
var customer = await context.Customers.FindAsync(customerId);
await context.Entry(customer)
    .Collection(c => c.Orders)
    .LoadAsync();
```

---

## 5. PostgreSQL-Specific Patterns

### 5.1 JSONB Columns for Flexible Data

**Use Case:** User preferences, audit event payloads, flexible metadata.

```csharp
public class UserProfile : BaseEntity
{
    public Guid UserId { get; set; }

    // Store preferences as JSONB
    public Dictionary<string, object> Preferences { get; set; } = new();
}

// EF Core configuration
builder.Property(u => u.Preferences)
    .HasColumnType("jsonb");

// Query JSONB
var users = await context.UserProfiles
    .Where(u => EF.Functions.JsonContains(u.Preferences, @"{""theme"": ""dark""}"))
    .ToListAsync();
```

---

### 5.2 Full-Text Search

**Use tsvector and GIN Index:**

```csharp
// Migration: Add full-text search column
migrationBuilder.Sql(@"
    ALTER TABLE Customers ADD COLUMN SearchVector tsvector
    GENERATED ALWAYS AS (to_tsvector('english', coalesce(Name, '') || ' ' || coalesce(TaxId, ''))) STORED;

    CREATE INDEX IX_Customers_SearchVector ON Customers USING GIN(SearchVector);
");

// Query
var customers = await context.Customers
    .Where(c => EF.Functions.ToTsVector("english", c.Name + " " + c.TaxId)
        .Matches(EF.Functions.ToTsQuery("english", searchTerm)))
    .ToListAsync();
```

---

### 5.3 Array Columns

```csharp
public class Order : BaseEntity
{
    public string[] Tags { get; set; } // Stored as PostgreSQL array
}

// EF Core configuration
builder.Property(o => o.Tags)
    .HasColumnType("text[]");

// Query
var orders = await context.Orders
    .Where(o => o.Tags.Contains("urgent"))
    .ToListAsync();
```

---

### 5.4 GUID vs Serial Primary Keys

**Recommendation:** Use GUIDs for distributed systems, ease of merging data, security (non-sequential).

```csharp
// UUID v7 (time-ordered, better index performance than random UUIDs)
public Guid Id { get; set; } = Guid.CreateVersion7();
```

---

### 5.5 Index Types

- **B-tree** (default): General purpose, good for equality and range queries
- **GIN** (Generalized Inverted Index): Full-text search, JSONB, arrays
- **GiST** (Generalized Search Tree): Spatial data, full-text search
- **Hash**: Equality only (rarely needed)

---

## 6. Audit Trail Implementation

### 6.1 ActivityTimelineEvent Table

**Append-only audit log for all entity mutations.**

```csharp
public class ActivityTimelineEvent : BaseEntity
{
    public string EntityType { get; set; } // "Customer", "Order", etc.
    public Guid EntityId { get; set; } // No FK constraint (entity may be deleted)
    public string EventType { get; set; } // "CustomerCreated", "CustomerUpdated", etc.
    public Guid UserId { get; set; }
    public DateTime Timestamp { get; set; }
    public Dictionary<string, object> Payload { get; set; } // JSONB for flexibility
}

// EF Core configuration
public class ActivityTimelineEventConfiguration : IEntityTypeConfiguration<ActivityTimelineEvent>
{
    public void Configure(EntityTypeBuilder<ActivityTimelineEvent> builder)
    {
        builder.ToTable("ActivityTimelineEvents");

        builder.Property(e => e.Payload)
            .HasColumnType("jsonb");

        // Indexes for common queries
        builder.HasIndex(e => new { e.EntityType, e.EntityId });
        builder.HasIndex(e => e.Timestamp);

        // Prevent updates/deletes (append-only)
        // Note: This is convention-based; enforce in application layer
    }
}
```

---

### 6.2 WorkflowTransition Table

**Immutable log of all workflow state changes.**

```csharp
public class WorkflowTransition : BaseEntity
{
    public Guid OrderId { get; set; } // Or other entity with workflow
    public string FromStatus { get; set; }
    public string ToStatus { get; set; }
    public DateTime TransitionedAt { get; set; }
    public Guid TransitionedBy { get; set; }
    public string? Reason { get; set; } // Required for Cancelled/Returned
}

// EF Core configuration
public class WorkflowTransitionConfiguration : IEntityTypeConfiguration<WorkflowTransition>
{
    public void Configure(EntityTypeBuilder<WorkflowTransition> builder)
    {
        builder.ToTable("WorkflowTransitions");

        builder.HasIndex(w => w.OrderId);
        builder.HasIndex(w => w.TransitionedAt);
    }
}
```

---

### 6.3 Event Sourcing for Audit

**Rebuild entity state from event stream (advanced pattern).**

```csharp
// Consider for Phase 2 if needed
public async Task<Customer> RebuildCustomerFromEventsAsync(Guid customerId)
{
    var events = await context.ActivityTimelineEvents
        .Where(e => e.EntityType == "Customer" && e.EntityId == customerId)
        .OrderBy(e => e.Timestamp)
        .ToListAsync();

    var customer = new Customer();
    foreach (var evt in events)
    {
        switch (evt.EventType)
        {
            case "CustomerCreated":
                customer.Id = evt.EntityId;
                customer.Name = evt.Payload["name"]?.ToString();
                // ... apply event
                break;
            case "CustomerUpdated":
                // ... apply update
                break;
        }
    }

    return customer;
}
```

---

## Version History

**Version 3.0** - 2026-02-03 - Replaced all solution-specific entities with standard generic set (customers/orders). Changed many-to-many example to Product/Category. See `BOUNDARY-POLICY.md` → "Standard Example Entities" for the convention.
**Version 2.0** - 2026-01-31 - Comprehensive data modeling guide with EF Core 10 and PostgreSQL patterns (350 lines)
**Version 1.0** - 2026-01-26 - Initial data modeling guide (54 lines)

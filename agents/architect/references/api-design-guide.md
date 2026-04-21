# API Design Guide

> **Examples in this guide use `customers` and `orders` as illustrative entities.
> These are not prescriptive — substitute your own domain entities when applying
> these patterns. See `BOUNDARY-POLICY.md` → "Standard Example Entities" for
> the full convention and field mapping.

---

Comprehensive guide for designing RESTful APIs using .NET 10 Minimal APIs. This guide covers REST principles, request/response patterns, pagination, filtering, versioning, security, and OpenAPI documentation.

---

## 1. RESTful Principles

### 1.1 Resource Naming Conventions

**Use Nouns, Not Verbs:**
- ✅ Good: `GET /customers`, `POST /orders`
- ❌ Bad: `GET /getCustomers`, `POST /createOrder`

**Use Plural Nouns:**
- ✅ Good: `/customers`, `/orders`
- ❌ Bad: `/customer`, `/order`

**Hierarchical Resource URLs:**
- ✅ Good: `/customers/{id}/orders` (orders belong to customer)
- ✅ Good: `/orders/{id}/items` (items belong to order)
- ❌ Bad: `/customer-orders?customerId={id}` (flat structure)

**Lowercase with Hyphens (for multi-word resources):**
- ✅ Good: `/order-items`, `/timeline-events`
- ❌ Bad: `/OrderItems`, `/timeline_events`

**Avoid Deep Nesting (max 2 levels):**
- ✅ Good: `/customers/{id}/orders/{orderId}`
- ❌ Bad: `/customers/{id}/orders/{orderId}/items/{itemId}/details/{detailId}`
- Better: `/orders/{orderId}/items/{itemId}`

---

### 1.2 HTTP Methods (Verbs)

**GET - Retrieve Resources:**
- `GET /customers` - List all customers (with pagination)
- `GET /customers/{id}` - Get single customer by ID
- `GET /customers/{id}/orders` - Get customer's orders
- Idempotent: Multiple identical requests have same effect
- No side effects (no data mutations)
- Cacheable

**POST - Create New Resource:**
- `POST /customers` - Create new customer
- `POST /orders/{id}/transition` - Perform action (state change)
- Non-idempotent: Multiple requests create multiple resources
- Returns `201 Created` with `Location` header pointing to new resource
- Response body includes created resource

**PUT - Replace Entire Resource:**
- `PUT /customers/{id}` - Replace entire customer (all fields required)
- Idempotent: Multiple identical requests have same effect
- Returns `200 OK` with updated resource or `204 No Content`
- Rarely used in practice (PATCH preferred)

**PATCH - Partial Update:**
- `PATCH /customers/{id}` - Update specific fields
- Idempotent (if designed correctly)
- Returns `200 OK` with updated resource
- Preferred over PUT for updates

**DELETE - Remove Resource:**
- `DELETE /customers/{id}` - Soft delete customer
- Idempotent: Deleting already-deleted resource returns `204`
- Returns `204 No Content` (no response body)
- Consider soft delete (set DeletedAt timestamp) vs hard delete

---

### 1.3 HTTP Status Codes

**Success Codes:**
- **200 OK**: Successful GET, PUT, PATCH (with response body)
- **201 Created**: Successful POST (new resource created)
- **204 No Content**: Successful DELETE or PUT with no response body
- **202 Accepted**: Request accepted, processing asynchronously (long-running operations)

**Client Error Codes:**
- **400 Bad Request**: Validation error, malformed request
- **401 Unauthorized**: Missing or invalid authentication token
- **403 Forbidden**: User authenticated but lacks permission
- **404 Not Found**: Resource doesn't exist
- **409 Conflict**: Business rule violation (e.g., duplicate order number, invalid state transition)
- **422 Unprocessable Entity**: Request syntactically valid but semantically invalid

**Server Error Codes:**
- **500 Internal Server Error**: Unexpected server error
- **503 Service Unavailable**: Service temporarily down (maintenance, overload)

---

### 1.4 Idempotency

**Idempotent Methods** (safe to retry):
- GET, PUT, DELETE
- Multiple identical requests have the same effect as single request

**Non-Idempotent Methods** (not safe to retry):
- POST
- Multiple requests may create multiple resources

**Idempotency Keys for POST:**
```http
POST /orders
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json

{ "customerId": "...", "name": "Acme Inc" }
```

Server stores idempotency key; duplicate requests with same key return original response (don't create duplicate).

---

### 1.5 HATEOAS Considerations

**HATEOAS** (Hypermedia as the Engine of Application State): Include links to related resources in responses.

**Example:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Acme Inc",
  "status": "Active",
  "_links": {
    "self": { "href": "/customers/123e4567-e89b-12d3-a456-426614174000" },
    "orders": { "href": "/customers/123e4567-e89b-12d3-a456-426614174000/orders" },
    "addresses": { "href": "/customers/123e4567-e89b-12d3-a456-426614174000/addresses" }
  }
}
```

**General guidance:** For internal APIs, full HATEOAS adds complexity without clear benefit. Consider limiting it to pagination links only unless clients are highly decoupled and need self-describing responses.

---

## 2. Request/Response Patterns

### 2.1 Request Models (DTOs)

**Use Data Transfer Objects (DTOs) for Requests:**

```csharp
public record CreateCustomerRequest
{
    [Required]
    [MaxLength(255)]
    public string Name { get; init; }

    [Required]
    [MaxLength(50)]
    public string Region { get; init; }

    [EmailAddress]
    public string? Email { get; init; }

    [Phone]
    public string? Phone { get; init; }
}

// Minimal API endpoint
app.MapPost("/customers", async (
    CreateCustomerRequest request,
    ICustomerService customerService,
    IValidator<CreateCustomerRequest> validator) =>
{
    var validationResult = await validator.ValidateAsync(request);
    if (!validationResult.IsValid)
        return Results.ValidationProblem(validationResult.ToDictionary());

    var customer = await customerService.CreateAsync(request);
    return Results.Created($"/customers/{customer.Id}", customer);
})
.WithName("CreateCustomer")
.WithTags("Customers")
.Produces<CustomerResponse>(201)
.ProducesProblem(400)
.ProducesProblem(403)
.ProducesProblem(409);
```

**Validation Best Practices:**
- Use Data Annotations for simple validation (`[Required]`, `[MaxLength]`, `[EmailAddress]`)
- Use FluentValidation for complex validation (cross-field, business rules)
- Return detailed field-level errors

---

### 2.2 Response Models (DTOs)

**Separate Request and Response DTOs:**

```csharp
public record CustomerResponse
{
    public Guid Id { get; init; }
    public string Name { get; init; }
    public string Region { get; init; }
    public string? Email { get; init; }
    public string? Phone { get; init; }
    public string Status { get; init; }
    public DateTime CreatedAt { get; init; }
    public DateTime UpdatedAt { get; init; }

    // Internal-only fields (conditionally included based on user role)
    public string? InternalNotes { get; init; }
}
```

**Map Entities to DTOs (never expose entities directly):**

```csharp
var customer = await context.Customers.FindAsync(id);
var response = new CustomerResponse
{
    Id = customer.Id,
    Name = customer.Name,
    // ... map fields
};
```

---

### 2.3 Standard Error Contract

Use RFC Problem Details with media type `application/problem+json`.

Reference:
- `{PRODUCT_ROOT}/planning-mds/architecture/api-guidelines-profile.md`
- `{PRODUCT_ROOT}/planning-mds/architecture/error-codes.md`

**Example Error Response (403):**
```json
{
  "type": "https://api.example.com/problems/policy-denied",
  "title": "Forbidden",
  "status": 403,
  "code": "policy_denied",
  "traceId": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
}
```

---

### 2.4 Success Response Envelopes

**Simple Response (No Envelope):**
```json
GET /customers/123
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Acme Inc",
  "status": "Active"
}
```

**List Response (With Pagination Metadata):**
```json
GET /customers?page=1&pageSize=20
{
  "data": [
    { "id": "...", "name": "Acme Inc" },
    { "id": "...", "name": "Global Corp" }
  ],
  "page": 1,
  "pageSize": 20,
  "totalCount": 156,
  "totalPages": 8
}
```

**Recommendation:** Use envelope for lists (to include pagination metadata), no envelope for single resources.

---

## 3. Pagination Patterns

### 3.1 Offset Pagination (Page-Based)

**Query Parameters:**
- `page` (integer, default: 1)
- `pageSize` (integer, default: 20, max: 100)

**Request:**
```http
GET /customers?page=2&pageSize=20
```

**Response:**
```json
{
  "data": [
    { "id": "...", "name": "Customer 21" },
    { "id": "...", "name": "Customer 22" }
  ],
  "page": 2,
  "pageSize": 20,
  "totalCount": 156,
  "totalPages": 8
}
```

**Implementation:**
```csharp
app.MapGet("/customers", async (
    [FromQuery] int page = 1,
    [FromQuery] int pageSize = 20,
    ApplicationDbContext context) =>
{
    if (pageSize > 100) pageSize = 100;

    var query = context.Customers.AsQueryable();

    var totalCount = await query.CountAsync();

    var data = await query
        .OrderBy(c => c.Name)
        .Skip((page - 1) * pageSize)
        .Take(pageSize)
        .Select(c => new CustomerListItem { Id = c.Id, Name = c.Name })
        .ToListAsync();

    return Results.Ok(new
    {
        data,
        page,
        pageSize,
        totalCount,
        totalPages = (int)Math.Ceiling(totalCount / (double)pageSize)
    });
});
```

**Pros:** Simple, supports "jump to page N", shows total count
**Cons:** Slow for large offsets (OFFSET 10000 is slow), inconsistent if data changes between requests

---

### 3.2 Cursor-Based Pagination (Keyset)

**Better for Large Datasets:**

**Query Parameters:**
- `cursor` (string, opaque token pointing to last seen item)
- `limit` (integer, default: 20)

**Request:**
```http
GET /customers?limit=20&cursor=eyJuYW1lIjoiQWNtZSIsImlkIjoiMTIzIn0=
```

**Response:**
```json
{
  "data": [ ... ],
  "nextCursor": "eyJuYW1lIjoiWmVuaXRoIiwiaWQiOiI3ODkifQ==",
  "hasMore": true
}
```

**Implementation:**
```csharp
var (name, id) = DecodeCursor(cursor); // Base64 decode

var customers = await context.Customers
    .Where(c => c.Name.CompareTo(name) > 0 || (c.Name == name && c.Id.CompareTo(id) > 0))
    .OrderBy(c => c.Name)
    .ThenBy(c => c.Id)
    .Take(limit + 1)
    .ToListAsync();

var hasMore = customers.Count > limit;
if (hasMore) customers.RemoveAt(customers.Count - 1);

var nextCursor = hasMore ? EncodeCursor(customers.Last().Name, customers.Last().Id) : null;
```

**Pros:** Fast for large datasets, consistent results
**Cons:** Can't jump to arbitrary page, no total count

---

### 3.3 HATEOAS Pagination Links

**Include Navigation Links:**
```json
{
  "data": [ ... ],
  "page": 2,
  "pageSize": 20,
  "totalCount": 156,
  "totalPages": 8,
  "_links": {
    "first": { "href": "/customers?page=1&pageSize=20" },
    "prev": { "href": "/customers?page=1&pageSize=20" },
    "self": { "href": "/customers?page=2&pageSize=20" },
    "next": { "href": "/customers?page=3&pageSize=20" },
    "last": { "href": "/customers?page=8&pageSize=20" }
  }
}
```

---

## 4. Filtering & Sorting

### 4.1 Query String Parameters for Filtering

**Simple Filters:**
```http
GET /customers?status=Active&region=West
```

**Search (across multiple fields):**
```http
GET /customers?search=acme
```

**Filter Operators:**
```http
GET /orders?amount[gte]=500&orderDate[lte]=2026-12-31
```

**Implementation:**
```csharp
app.MapGet("/customers", async (
    [FromQuery] string? status,
    [FromQuery] string? region,
    [FromQuery] string? search,
    ApplicationDbContext context) =>
{
    var query = context.Customers.AsQueryable();

    if (!string.IsNullOrEmpty(status))
        query = query.Where(c => c.Status == status);

    if (!string.IsNullOrEmpty(region))
        query = query.Where(c => c.Region == region);

    if (!string.IsNullOrEmpty(search))
        query = query.Where(c => EF.Functions.ILike(c.Name, $"%{search}%") ||
                                 EF.Functions.ILike(c.Email, $"%{search}%"));

    return Results.Ok(await query.ToListAsync());
});
```

---

### 4.2 Multi-Field Sorting

**Query Parameter:**
```http
GET /customers?sort=name:asc,createdAt:desc
```

**Implementation:**
```csharp
public static IQueryable<T> ApplySorting<T>(this IQueryable<T> query, string? sortParam)
{
    if (string.IsNullOrEmpty(sortParam))
        return query;

    var sortFields = sortParam.Split(',');

    IOrderedQueryable<T>? orderedQuery = null;

    foreach (var field in sortFields)
    {
        var parts = field.Split(':');
        var fieldName = parts[0];
        var direction = parts.Length > 1 ? parts[1] : "asc";

        var parameter = Expression.Parameter(typeof(T), "x");
        var property = Expression.Property(parameter, fieldName);
        var lambda = Expression.Lambda(property, parameter);

        var methodName = orderedQuery == null
            ? (direction == "desc" ? "OrderByDescending" : "OrderBy")
            : (direction == "desc" ? "ThenByDescending" : "ThenBy");

        orderedQuery = (IOrderedQueryable<T>)typeof(Queryable)
            .GetMethods()
            .First(m => m.Name == methodName && m.GetParameters().Length == 2)
            .MakeGenericMethod(typeof(T), property.Type)
            .Invoke(null, new object[] { orderedQuery ?? query, lambda })!;
    }

    return orderedQuery ?? query;
}
```

---

### 4.3 Search Across Multiple Fields

**PostgreSQL Full-Text Search:**
```csharp
var customers = await context.Customers
    .Where(c => EF.Functions.ToTsVector("english", c.Name + " " + c.Email)
        .Matches(EF.Functions.ToTsQuery("english", searchTerm)))
    .ToListAsync();
```

---

## 5. Versioning Strategies

### 5.1 URI Versioning (Recommended)

**Include Version in URL Path:**
```http
GET /v1/customers
GET /v2/customers
```

**Pros:** Simple, explicit, easy to route
**Cons:** Multiple endpoints in code, URL changes

**Implementation:**
```csharp
var v1 = app.MapGroup("/v1").WithTags("V1");
v1.MapGet("/customers", GetCustomersV1);

var v2 = app.MapGroup("/v2").WithTags("V2");
v2.MapGet("/customers", GetCustomersV2);
```

---

### 5.2 Header Versioning

**Version in Custom Header:**
```http
GET /customers
API-Version: 2
```

**Pros:** Clean URLs
**Cons:** Less discoverable, harder to test

---

### 5.3 Query Parameter Versioning

**Version as Query Param:**
```http
GET /customers?version=2
```

**Pros:** Easy to test
**Cons:** Pollutes query string, easy to forget

---

### 5.4 Deprecation Policy

**Sunset Header (RFC 8594):**
```http
HTTP/1.1 200 OK
Sunset: Sat, 31 Dec 2026 23:59:59 GMT
Deprecation: true
Link: <https://api.example.com/v2/customers>; rel="successor-version"
```

**Recommendation:** Support previous version for 12 months after new version released.

---

## 6. API Security

### 6.1 Authentication (JWT via OIDC Provider)

**Require Bearer Token on All Endpoints:**
```csharp
app.MapGet("/customers", async () => { ... })
    .RequireAuthorization();
```

**Validate JWT Token:**
```csharp
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.Authority = "https://auth.example.com/realms/{your-realm}";
        options.Audience = "{your-app-id}";
        options.RequireHttpsMetadata = true;
    });
```

---

### 6.2 Authorization (Casbin ABAC)

**Enforce Authorization Middleware:**
```csharp
app.Use(async (context, next) =>
{
    var enforcer = context.RequestServices.GetRequiredService<IEnforcer>();
    var user = context.User;
    var resource = DetermineResource(context.Request.Path);
    var action = DetermineAction(context.Request.Method);

    if (!await enforcer.EnforceAsync(user, resource, action))
    {
        context.Response.StatusCode = 403;
        await context.Response.WriteAsJsonAsync(new ErrorResponse
        {
            Code = "INSUFFICIENT_PERMISSIONS",
            Message = $"User lacks {action} permission for {resource}"
        });
        return;
    }

    await next();
});
```

---

### 6.3 CORS Configuration

**Configure CORS for Frontend:**
```csharp
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowFrontend", policy =>
    {
        policy.WithOrigins("https://app.example.com")
              .AllowAnyMethod()
              .AllowAnyHeader()
              .AllowCredentials();
    });
});

app.UseCors("AllowFrontend");
```

---

### 6.4 Rate Limiting

**Prevent Abuse:**
```csharp
builder.Services.AddRateLimiter(options =>
{
    options.GlobalLimiter = PartitionedRateLimiter.Create<HttpContext, string>(context =>
        RateLimitPartition.GetFixedWindowLimiter(
            partitionKey: context.User.Identity?.Name ?? context.Connection.RemoteIpAddress?.ToString() ?? "anonymous",
            factory: _ => new FixedWindowRateLimiterOptions
            {
                PermitLimit = 100,
                Window = TimeSpan.FromMinutes(1)
            }));
});

app.UseRateLimiter();
```

---

### 6.5 Input Validation

**Never Trust Client Input:**
- Validate all request data (Data Annotations, FluentValidation)
- Sanitize strings (prevent SQL injection, XSS)
- Use parameterized queries (EF Core does this automatically)
- Validate file uploads (size, type, content)

---

## 7. OpenAPI Documentation

### 7.1 Swagger/OpenAPI 3.0 Best Practices

**Add Swagger to .NET 10:**
```csharp
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(options =>
{
    options.SwaggerDoc("v1", new OpenApiInfo
    {
        Title = "Your App API",
        Version = "v1",
        Description = "API for managing customers, orders, and products",
        Contact = new OpenApiContact
        {
            Name = "Your Team",
            Email = "support@example.com"
        }
    });

    // Add JWT authentication
    options.AddSecurityDefinition("Bearer", new OpenApiSecurityScheme
    {
        Type = SecuritySchemeType.Http,
        Scheme = "bearer",
        BearerFormat = "JWT",
        Description = "JWT Authorization header using the Bearer scheme"
    });

    options.AddSecurityRequirement(new OpenApiSecurityRequirement
    {
        {
            new OpenApiSecurityScheme
            {
                Reference = new OpenApiReference
                {
                    Type = ReferenceType.SecurityScheme,
                    Id = "Bearer"
                }
            },
            Array.Empty<string>()
        }
    });
});

app.UseSwagger();
app.UseSwaggerUI();
```

---

### 7.2 Schema Definitions (components/schemas)

**Define Reusable Schemas:**
```yaml
components:
  schemas:
    CustomerResponse:
      type: object
      properties:
        id:
          type: string
          format: uuid
        name:
          type: string
        status:
          type: string
          enum: [Active, Inactive, Suspended]

    ErrorResponse:
      type: object
      required: [code, message]
      properties:
        code:
          type: string
        message:
          type: string
        details:
          type: array
          items:
            $ref: '#/components/schemas/ErrorDetail'
```

---

### 7.3 Examples and Descriptions

**Add Examples to Endpoints:**
```csharp
app.MapPost("/customers", async (CreateCustomerRequest request) => { ... })
    .WithOpenApi(operation =>
    {
        operation.Summary = "Create a new customer";
        operation.Description = "Creates a new customer record. Requires CreateCustomer permission.";
        return operation;
    })
    .Produces<CustomerResponse>(201)
    .ProducesProblem(400)
    .ProducesProblem(403);
```

---

### 7.4 Generating Client SDKs

**Use OpenAPI Generator:**
```bash
# Generate TypeScript client for React frontend
openapi-generator-cli generate \
  -i https://api.example.com/swagger/v1/swagger.json \
  -g typescript-fetch \
  -o clients/typescript

# Generate C# client for integration tests
openapi-generator-cli generate \
  -i https://api.example.com/swagger/v1/swagger.json \
  -g csharp-netcore \
  -o clients/csharp
```

---

## Version History

**Version 3.0** - 2026-02-03 - Replaced all solution-specific entities with standard generic set (customers/orders). Removed Nebula-specific recommendations. See `BOUNDARY-POLICY.md` → "Standard Example Entities" for the convention.
**Version 2.0** - 2026-01-31 - Comprehensive API design guide with .NET 10 Minimal APIs (400 lines)
**Version 1.0** - 2026-01-26 - Initial API design guide (64 lines)

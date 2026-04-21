# Authorization Patterns

> **Examples in this guide use `customers` and `orders` as illustrative entities, with
> roles like `Sales` and `Support` demonstrating ABAC patterns. These are not
> prescriptive — substitute your own domain entities and roles when applying these
> patterns. See `BOUNDARY-POLICY.md` → "Standard Example Entities" for the convention.

---

Comprehensive guide for implementing Attribute-Based Access Control (ABAC) with Casbin. This guide covers ABAC fundamentals, Casbin architecture, OIDC integration, common patterns, testing, and pitfalls to avoid.

---

## 1. ABAC Fundamentals

### 1.1 What is ABAC?

**Attribute-Based Access Control (ABAC)** is a flexible authorization model that makes access decisions based on attributes of:
- **Subject** (user): roles, region, department, userId
- **Resource** (entity): type, status, owner, assignedTo
- **Action**: Create, Read, Update, Delete, Transition, Assign
- **Environment**: time, IP address, location (optional)

**Comparison with RBAC:**
- **RBAC (Role-Based)**: "Admin can do everything, Support can update orders"
- **ABAC (Attribute-Based)**: "Support can update orders assigned to them"

ABAC provides fine-grained control beyond simple role checks.

---

### 1.2 Subject Attributes

**Subject attributes** describe the user making the request.

**Common Attributes:**
```csharp
public class SubjectAttributes
{
    public Guid UserId { get; set; } // OIDC subject ID
    public string[] Roles { get; set; } // ["Sales", "Support", "Admin"]
    public string? Region { get; set; } // "West", "East", "Central"
    public string? Department { get; set; } // "Operations", "Sales"
    public Guid? CustomerId { get; set; } // For customer portal users
}
```

**Extracted From:**
- JWT token claims (roles, userId, region)
- UserProfile table in database (additional attributes)

**Example:**
```json
{
  "userId": "550e8400-e29b-41d4-a716-446655440000",
  "roles": ["Support"],
  "region": "West",
  "department": "Operations"
}
```

---

### 1.3 Resource Attributes

**Resource attributes** describe the entity being accessed.

**Common Attributes:**
```csharp
public class ResourceAttributes
{
    public string Type { get; set; } // "Customer", "Order", "Product"
    public Guid Id { get; set; } // Entity ID
    public string? Status { get; set; } // "Active", "Processing", "Shipped"
    public Guid? OwnerId { get; set; } // User who created/owns the resource
    public Guid? AssignedTo { get; set; } // User assigned to the resource
    public Guid? CustomerId { get; set; } // Associated customer
}
```

**Extracted From:**
- Entity being accessed (query database)
- Request path/body

**Example:**
```json
{
  "type": "Order",
  "id": "789e4567-e89b-12d3-a456-426614174000",
  "status": "Processing",
  "assignedTo": "550e8400-e29b-41d4-a716-446655440000",
  "customerId": "123e4567-e89b-12d3-a456-426614174000"
}
```

---

### 1.4 Action Types

**Actions** describe what operation the user wants to perform.

**Standard CRUD Actions:**
- `Create` - Create new entity
- `Read` - View entity
- `Update` - Modify entity
- `Delete` - Remove entity (soft delete)

**Domain-Specific Actions:**
- `Transition` - Change workflow status (e.g., Pending → Processing)
- `Assign` - Assign resource to user (e.g., assign order to support agent)
- `Restore` - Restore soft-deleted entity
- `ViewAuditLog` - View audit trail
- `Export` - Export data (reports, CSV)

---

### 1.5 Environment Attributes (Optional)

**Environment attributes** describe the context of the request.

**Examples:**
- Current time (business hours only)
- IP address (internal network only)
- Geographic location
- Device type (mobile, desktop)

**Recommendation:** Start without environment attributes (YAGNI). Add if specific requirements emerge.

---

### 1.6 Policy Evaluation

**Casbin evaluates policies and returns:**
- **Allow**: User is authorized
- **Deny**: User is explicitly denied (policy says "deny")
- **Not Applicable**: No matching policy (default deny)

**Default Behavior:** If no policy matches, deny access (secure by default).

---

## 2. Casbin Architecture

### 2.1 Casbin Model

**Casbin uses a model file to define how policies are structured and evaluated.**

**Model Components:**
- **Request Definition**: What input is provided (subject, object, action)
- **Policy Definition**: How policies are stored (subject, object, action, effect)
- **Matcher**: Expression to match request against policies
- **Effect**: How to combine multiple matching policies (allow-override, deny-override)

**Example Casbin Model (`casbin_model.conf`):**
```ini
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act, eft

[role_definition]
g = _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act || p.sub == "Admin"
```

**Explanation:**
- Request has subject (user role), object (resource type), action
- Policy has subject (role), object, action, effect (allow/deny)
- Matcher checks if user has role matching policy, object and action match, OR user is Admin
- Effect allows if any policy allows

---

### 2.2 Policy Storage

**Policies can be stored in:**
- **CSV File**: Simple, version-controlled, not dynamic
- **Database**: PostgreSQL table, dynamic policies
- **Remote API**: Centralized policy service (advanced)

**Recommended Approach: Database Storage**

**CasbinRule Table:**
```sql
CREATE TABLE casbin_rule (
    id SERIAL PRIMARY KEY,
    ptype VARCHAR(100),  -- 'p' for policy, 'g' for grouping
    v0 VARCHAR(100),     -- Subject (role)
    v1 VARCHAR(100),     -- Object (resource type)
    v2 VARCHAR(100),     -- Action
    v3 VARCHAR(100),     -- Effect (allow/deny)
    v4 VARCHAR(100),     -- Condition (optional)
    v5 VARCHAR(100)      -- Reserved (optional)
);
```

**Example Policies:**
```sql
INSERT INTO casbin_rule (ptype, v0, v1, v2, v3) VALUES
('p', 'Sales', 'Customer', 'Create', 'allow'),
('p', 'Sales', 'Customer', 'Read', 'allow'),
('p', 'Sales', 'Customer', 'Update', 'allow'),
('p', 'Support', 'Customer', 'Read', 'allow'),
('p', 'Admin', '*', '*', 'allow');
```

---

### 2.3 Policy Enforcement Point (Middleware)

**Enforce Authorization on Every Request:**

```csharp
public class CasbinAuthorizationMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<CasbinAuthorizationMiddleware> _logger;

    public CasbinAuthorizationMiddleware(RequestDelegate next, ILogger<CasbinAuthorizationMiddleware> logger)
    {
        _next = next;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context, IEnforcer enforcer, ICurrentUserService currentUser)
    {
        // Skip authorization for health checks, swagger
        if (context.Request.Path.StartsWithSegments("/health") ||
            context.Request.Path.StartsWithSegments("/swagger"))
        {
            await _next(context);
            return;
        }

        // Extract subject, object, action
        var subject = currentUser.Roles.FirstOrDefault() ?? "Anonymous";
        var (resourceType, action) = DetermineResourceAndAction(context.Request);

        // Enforce policy
        var allowed = await enforcer.EnforceAsync(subject, resourceType, action);

        if (!allowed)
        {
            _logger.LogWarning("Authorization denied: {Subject} cannot {Action} {Resource}",
                subject, action, resourceType);

            context.Response.StatusCode = 403;
            await context.Response.WriteAsJsonAsync(new ErrorResponse
            {
                Code = "INSUFFICIENT_PERMISSIONS",
                Message = $"User lacks {action} permission for {resourceType}"
            });
            return;
        }

        await _next(context);
    }

    private (string ResourceType, string Action) DetermineResourceAndAction(HttpRequest request)
    {
        var path = request.Path.Value;
        var method = request.Method;

        // Parse path: /api/customers/{id} -> "Customer"
        var pathSegments = path.Split('/', StringSplitOptions.RemoveEmptyEntries);
        var resourceType = pathSegments.Length > 1 ? pathSegments[1].TrimEnd('s') : "Unknown";

        // Map HTTP method to action
        var action = method switch
        {
            "GET" => "Read",
            "POST" => "Create",
            "PUT" => "Update",
            "PATCH" => "Update",
            "DELETE" => "Delete",
            _ => "Unknown"
        };

        return (resourceType, action);
    }
}
```

---

### 2.4 Subject Extraction (from JWT)

**Extract Subject Attributes from JWT Token:**

```csharp
public class CurrentUserService : ICurrentUserService
{
    private readonly IHttpContextAccessor _httpContextAccessor;

    public CurrentUserService(IHttpContextAccessor httpContextAccessor)
    {
        _httpContextAccessor = httpContextAccessor;
    }

    public Guid UserId =>
        Guid.Parse(_httpContextAccessor.HttpContext?.User.FindFirstValue(ClaimTypes.NameIdentifier) ?? Guid.Empty.ToString());

    public string[] Roles =>
        _httpContextAccessor.HttpContext?.User.FindAll(ClaimTypes.Role).Select(c => c.Value).ToArray() ?? Array.Empty<string>();

    public string? Region =>
        _httpContextAccessor.HttpContext?.User.FindFirstValue("region");
}
```

---

### 2.5 Resource Attribute Extraction

**Load Resource Attributes from Database:**

```csharp
public async Task<ResourceAttributes> GetOrderAttributesAsync(Guid orderId)
{
    var order = await _context.Orders
        .Where(o => o.Id == orderId)
        .Select(o => new ResourceAttributes
        {
            Type = "Order",
            Id = o.Id,
            Status = o.Status,
            AssignedTo = o.AssignedSupportId,
            CustomerId = o.CustomerId
        })
        .FirstOrDefaultAsync();

    return order ?? throw new NotFoundException("Order not found");
}
```

---

## 3. OIDC Provider Integration

### 3.1 JWT Token Structure

**OIDC provider issues JWT tokens with user attributes:**

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",
  "email": "sarah.chen@example.com",
  "name": "Sarah Chen",
  "preferred_username": "sarah.chen",
  "realm_access": {
    "roles": ["Sales", "User"]
  },
  "resource_access": {
    "your-api": {
      "roles": ["CreateCustomer", "UpdateOrder"]
    }
  },
  "region": "West",
  "iat": 1706745600,
  "exp": 1706749200
}
```

**Key Token Fields:**
- `sub`: Unique user ID (OIDC subject)
- `realm_access.roles`: Roles assigned to user
- `region`: Custom token attribute (configured in your identity provider)

---

### 3.2 UserProfile Mapping

**Map OIDC User to Application UserProfile:**

```csharp
public class UserProfile : BaseEntity
{
    public Guid Id { get; set; } // Same as OIDC subject ID
    public string Email { get; set; }
    public string FullName { get; set; }
    public string[] Roles { get; set; } // Synced from OIDC provider
    public string? Region { get; set; }
    public Guid? CustomerId { get; set; } // For customer portal users
}

// Sync on first login
public async Task SyncUserProfileAsync(ClaimsPrincipal user)
{
    var userId = Guid.Parse(user.FindFirstValue(ClaimTypes.NameIdentifier));

    var profile = await _context.UserProfiles.FindAsync(userId);
    if (profile == null)
    {
        profile = new UserProfile
        {
            Id = userId,
            Email = user.FindFirstValue(ClaimTypes.Email),
            FullName = user.FindFirstValue("name"),
            Roles = user.FindAll(ClaimTypes.Role).Select(c => c.Value).ToArray(),
            Region = user.FindFirstValue("region")
        };
        await _context.UserProfiles.AddAsync(profile);
    }
    else
    {
        // Update roles and region on each login (in case changed in identity provider)
        profile.Roles = user.FindAll(ClaimTypes.Role).Select(c => c.Value).ToArray();
        profile.Region = user.FindFirstValue("region");
    }

    await _context.SaveChangesAsync();
}
```

---

### 3.3 Role Synchronization

**OIDC Provider Roles → Casbin Subject Attributes:**

1. User logs in via OIDC provider
2. Provider returns JWT with roles in `realm_access.roles`
3. Application syncs roles to UserProfile table
4. Casbin policies use roles as subject (e.g., `Sales`, `Support`, `Admin`)

**No need to manually sync roles to Casbin** - roles are already in JWT, extracted by CurrentUserService.

---

### 3.4 Token Validation

**Validate JWT Signature and Expiration:**

```csharp
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.Authority = "https://auth.example.com/realms/{your-realm}";
        options.Audience = "your-api";
        options.RequireHttpsMetadata = true; // Enforce HTTPS

        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidIssuer = "https://auth.example.com/realms/{your-realm}",
            ValidateAudience = true,
            ValidAudience = "your-api",
            ValidateLifetime = true, // Check expiration
            ClockSkew = TimeSpan.FromMinutes(5) // Allow 5 min clock skew
        };
    });
```

---

## 4. Common Authorization Patterns

### 4.1 Role-Based Policies

**Simple role-based authorization:**

```csv
# Sales users can create/read/update customers
p, Sales, Customer, Create, allow
p, Sales, Customer, Read, allow
p, Sales, Customer, Update, allow

# Support can read customers but not modify
p, Support, Customer, Read, allow

# Admins can do everything
p, Admin, *, *, allow
```

---

### 4.2 Owner-Based Policies

**User can update resources they own:**

```csv
# Users can update their own profile
p, User, UserProfile, Update, allow, sub.userId == res.ownerId
```

**Casbin Model with Condition:**
```ini
[matchers]
m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act && eval(p.condition)
```

**Enforcement:**
```csharp
var allowed = await enforcer.EnforceAsync(
    currentUser.UserId,
    "UserProfile",
    "Update",
    new { userId = currentUser.UserId, ownerId = profile.Id }
);
```

---

### 4.3 Attribute-Based Policies

**Support can update orders assigned to them:**

```csv
p, Support, Order, Update, allow, sub.userId == res.assignedTo
```

**Enforcement:**
```csharp
var order = await _context.Orders.FindAsync(orderId);

var allowed = await enforcer.EnforceAsync(
    new { role = "Support", userId = currentUser.UserId },
    new { type = "Order", assignedTo = order.AssignedSupportId },
    "Update"
);
```

---

### 4.4 Hierarchical Policies

**Managers can view records of their team members:**

```csv
# Manager can read orders assigned to team members
p, Manager, Order, Read, allow, sub.teamMembers.contains(res.assignedTo)
```

---

### 4.5 Conditional Policies

**User can transition order only if in certain status:**

```csv
# Sales can transition orders in Pending status
p, Sales, Order, Transition, allow, res.status in ["Pending"]

# Support can transition orders in Processing or Shipped status
p, Support, Order, Transition, allow, sub.userId == res.assignedTo && res.status in ["Processing", "Shipped"]
```

---

## 5. Testing Authorization

### 5.1 Unit Testing Policies

**Test Policy Enforcement in Isolation:**

```csharp
[Fact]
public async Task Sales_CanCreateCustomer()
{
    // Arrange
    var enforcer = await GetEnforcerAsync();

    // Act
    var allowed = await enforcer.EnforceAsync("Sales", "Customer", "Create");

    // Assert
    Assert.True(allowed);
}

[Fact]
public async Task Support_CannotCreateCustomer()
{
    // Arrange
    var enforcer = await GetEnforcerAsync();

    // Act
    var allowed = await enforcer.EnforceAsync("Support", "Customer", "Create");

    // Assert
    Assert.False(allowed);
}

[Fact]
public async Task Support_CanUpdateAssignedOrder()
{
    // Arrange
    var enforcer = await GetEnforcerAsync();
    var supportUserId = Guid.NewGuid();

    // Act
    var allowed = await enforcer.EnforceAsync(
        new { role = "Support", userId = supportUserId },
        new { type = "Order", assignedTo = supportUserId },
        "Update"
    );

    // Assert
    Assert.True(allowed);
}
```

---

### 5.2 Integration Testing

**Test Full Request → Authorization → Response:**

```csharp
[Fact]
public async Task CreateCustomer_WithSalesRole_Returns201()
{
    // Arrange
    var client = _factory.CreateClient();
    var token = GenerateJwtToken(new[] { "Sales" });
    client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

    var request = new CreateCustomerRequest { Name = "Acme", Email = "contact@acme.com", Region = "West" };

    // Act
    var response = await client.PostAsJsonAsync("/api/customers", request);

    // Assert
    Assert.Equal(HttpStatusCode.Created, response.StatusCode);
}

[Fact]
public async Task CreateCustomer_WithSupportRole_Returns403()
{
    // Arrange
    var client = _factory.CreateClient();
    var token = GenerateJwtToken(new[] { "Support" });
    client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

    var request = new CreateCustomerRequest { Name = "Acme", Email = "contact@acme.com", Region = "West" };

    // Act
    var response = await client.PostAsJsonAsync("/api/customers", request);

    // Assert
    Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
}
```

---

### 5.3 Policy Validation

**Detect Conflicting or Redundant Policies:**

```csharp
[Fact]
public void ValidatePolicies_NoConflicts()
{
    var policies = GetAllPolicies();

    // Check for conflicts (same subject, object, action with different effects)
    var conflicts = policies
        .GroupBy(p => new { p.Subject, p.Object, p.Action })
        .Where(g => g.Select(p => p.Effect).Distinct().Count() > 1);

    Assert.Empty(conflicts);
}

[Fact]
public void ValidatePolicies_NoRedundant()
{
    var policies = GetAllPolicies();

    // Check for redundant policies (Admin already has *, *, allow)
    var adminPolicy = policies.First(p => p.Subject == "Admin" && p.Object == "*");
    var redundant = policies.Where(p => p.Subject == "Admin" && p.Object != "*");

    Assert.Empty(redundant);
}
```

---

### 5.4 Test Data Generation

**Generate Test User Contexts with Different Roles:**

```csharp
public sealed record TestUserContext(
    Guid UserId,
    string Email,
    string[] Roles,
    string Region
);

public static class TestUsers
{
    public static TestUserContext SalesUser(Guid? userId = null) =>
        new(
            userId ?? Guid.NewGuid(),
            "sales@example.com",
            new[] { "Sales" },
            "West"
        );

    public static TestUserContext SupportUser(Guid? userId = null) =>
        new(
            userId ?? Guid.NewGuid(),
            "support@example.com",
            new[] { "Support" },
            "West"
        );

    public static TestUserContext AdminUser(Guid? userId = null) =>
        new(
            userId ?? Guid.NewGuid(),
            "admin@example.com",
            new[] { "Admin" },
            "Central"
        );
}
```

---

## 6. Common Pitfalls

### 6.1 Missing Authorization Checks

**Anti-Pattern:** Only checking authorization in some endpoints, not all.

**Problem:**
- API can be called directly, bypassing UI authorization
- Security vulnerability

**Solution:**
- Use middleware to enforce authorization on ALL requests
- No endpoint should bypass authorization (except public endpoints like health checks)

```csharp
// WRONG: Authorization in endpoint logic (easy to forget)
app.MapPost("/api/customers", async (CreateCustomerRequest request, ICurrentUserService user) =>
{
    if (!user.Roles.Contains("Sales"))
        return Results.Forbid();

    // ... create customer
});

// RIGHT: Authorization in middleware (enforced globally)
app.Use<CasbinAuthorizationMiddleware>();
```

---

### 6.2 Client-Side Authorization Only

**Anti-Pattern:** Hiding UI elements based on role, but not enforcing authorization on API.

**Problem:**
- Malicious user can call API directly (bypass UI)
- Security vulnerability

**Solution:**
- Server-side authorization is MANDATORY
- Client-side authorization is UX optimization only (hide buttons user can't use)

---

### 6.3 Hard-Coded Role Checks

**Anti-Pattern:** Hard-coding role checks in business logic.

**Problem:**
```csharp
// WRONG: Hard-coded role check
if (user.Role == "Admin")
{
    // ... admin-only logic
}
```

- Scattered role checks across codebase
- Hard to audit all authorization logic
- Difficult to change policies

**Solution:** Use policy engine (Casbin) for all authorization.

---

### 6.4 Insufficient Logging

**Anti-Pattern:** Not logging authorization decisions.

**Problem:**
- Can't audit who accessed what
- Can't detect authorization bypasses
- Can't troubleshoot permission issues

**Solution:**
- Log all authorization checks (approved and denied)
- Include user, resource, action, result

```csharp
_logger.LogInformation("Authorization {Result}: {User} {Action} {Resource}",
    allowed ? "ALLOWED" : "DENIED",
    currentUser.UserId,
    action,
    resourceType);
```

---

### 6.5 Performance Issues

**Anti-Pattern:** Loading policies from database on every request.

**Problem:**
- Slow authorization checks
- Database overload

**Solution:**
- Cache policies in memory (Casbin does this automatically)
- Reload policies periodically or on-demand (when policies change)

```csharp
// Reload policies every 5 minutes
services.AddHostedService<CasbinPolicyRefreshService>();

public class CasbinPolicyRefreshService : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            await Task.Delay(TimeSpan.FromMinutes(5), stoppingToken);
            await _enforcer.LoadPolicyAsync();
        }
    }
}
```

---

## Version History

**Version 3.0** - 2026-02-03 - Replaced all solution-specific entities with standard generic set (customers/orders). Replaced domain-specific legacy role examples with generic roles (Sales/Support). See `BOUNDARY-POLICY.md` → "Standard Example Entities" for the convention.
**Version 2.0** - 2026-01-31 - Comprehensive authorization guide with ABAC, Casbin, and OIDC (500 lines)
**Version 1.0** - 2026-01-26 - Initial authorization patterns guide (55 lines)

# Performance Design Guide

Comprehensive guide for designing performant systems. This guide covers performance requirements, database optimization, caching strategies, API performance, and load testing & monitoring.

---

## 1. Performance Requirements

### 1.1 Response Time Targets

**API Response Times** (95th percentile):
- **Simple queries** (GET /api/customers/{id}): < 100ms
- **List queries** (GET /api/customers?page=1): < 300ms
- **Complex queries** (360 views with joins): < 500ms
- **Mutations** (POST, PUT, DELETE): < 300ms
- **Search queries**: < 1 second

**Frontend Load Times:**
- **Initial page load**: < 2 seconds
- **Subsequent navigation**: < 500ms (SPA transitions)
- **Time to Interactive (TTI)**: < 3 seconds

---

### 1.2 Throughput Targets

**Concurrent Users:**
- **MVP (Phase 0)**: 50 concurrent users
- **Phase 1**: 200 concurrent users
- **Phase 2**: 500 concurrent users

**Requests per Second:**
- **MVP**: 100 requests/sec
- **Phase 1**: 500 requests/sec
- **Phase 2**: 1000 requests/sec

---

### 1.3 Database Query Performance

**Query Execution Times:**
- **Simple SELECT** (by primary key): < 5ms
- **JOIN queries** (2-3 tables): < 50ms
- **Aggregation queries** (COUNT, SUM): < 100ms
- **Full-text search**: < 200ms

**Connection Pool:**
- **Min connections**: 10
- **Max connections**: 100 (EF Core default)

---

### 1.4 Page Load Performance

**Metrics:**
- **First Contentful Paint (FCP)**: < 1 second
- **Largest Contentful Paint (LCP)**: < 2.5 seconds
- **First Input Delay (FID)**: < 100ms
- **Cumulative Layout Shift (CLS)**: < 0.1

---

### 1.5 Service Level Objectives (SLOs)

**Availability:**
- **MVP**: 99.5% uptime (3.65 hours downtime/month)
- **Phase 1**: 99.9% uptime (43 minutes downtime/month)

**Error Rate:**
- **Target**: < 0.1% error rate (1 error per 1000 requests)

---

## 2. Database Optimization

### 2.1 Index Design

**Indexing Strategy:**

**Primary Keys:**
- Always indexed (clustered index on `Id` column)
- Use GUIDs for distributed systems, but consider sequential GUIDs (UUID v7) for better index performance

**Foreign Keys:**
- **Always index foreign keys** (EF Core doesn't auto-create FK indexes)

```csharp
builder.HasIndex(o => o.CustomerId)
    .HasDatabaseName("IX_Orders_CustomerId");

builder.HasIndex(o => o.AssignedUserId)
    .HasDatabaseName("IX_Orders_AssignedUserId");
```

**Query-Specific Indexes:**
- Index columns used in WHERE, ORDER BY, JOIN clauses

```csharp
// Frequently filtered by Status
builder.HasIndex(o => o.Status)
    .HasDatabaseName("IX_Orders_Status");

// Composite index for common query: status + order date
builder.HasIndex(o => new { o.Status, o.OrderDate })
    .HasDatabaseName("IX_Orders_Status_OrderDate");
```

**Covering Indexes:**
- Include all columns needed by query in index (avoid table lookup)

```csharp
// Query: SELECT Id, Name, Status FROM Customers WHERE Region = 'US-West'
builder.HasIndex(c => c.Region)
    .IncludeProperties(c => new { c.Id, c.Name, c.Status })
    .HasDatabaseName("IX_Customers_Region_Covering");
```

**Partial Indexes:**
- Index only subset of rows (PostgreSQL feature)

```csharp
// Index only active customers
builder.HasIndex(c => c.DeletedAt)
    .HasFilter("DeletedAt IS NULL")
    .HasDatabaseName("IX_Customers_Active");
```

---

### 2.2 Query Optimization

**Avoid SELECT \*:**

```csharp
// BAD: Loads all 20 fields
var customers = await _context.Customers.ToListAsync();

// GOOD: Project to DTO, load only needed fields
var customers = await _context.Customers
    .Select(c => new CustomerListItem
    {
        Id = c.Id,
        Name = c.Name,
        Status = c.Status
    })
    .ToListAsync();
```

---

### 2.3 N+1 Query Prevention

**Problem:**

```csharp
// BAD: N+1 queries (1 for customers + N for each customer's addresses)
var customers = await _context.Customers.ToListAsync(); // 1 query
foreach (var customer in customers)
{
    customer.Addresses = await _context.Addresses
        .Where(a => a.CustomerId == customer.Id)
        .ToListAsync(); // N queries
}
```

**Solution: Eager Loading**

```csharp
// GOOD: Single query with JOIN
var customers = await _context.Customers
    .Include(c => c.Addresses)
    .ToListAsync();
```

**Solution: Split Queries (for multiple collections)**

```csharp
// When including multiple collections, use AsSplitQuery to avoid cartesian explosion
var customers = await _context.Customers
    .Include(c => c.Addresses)
    .Include(c => c.Orders)
    .Include(c => c.Notes)
    .AsSplitQuery() // Executes 4 separate queries instead of 1 huge JOIN
    .ToListAsync();
```

---

### 2.4 Connection Pooling

**EF Core Connection Pooling** (enabled by default):

```csharp
builder.Services.AddDbContextPool<AppDbContext>(options =>
    options.UseNpgsql(connectionString, npgsqlOptions =>
    {
        npgsqlOptions.EnableRetryOnFailure(3); // Retry 3 times on transient failure
        npgsqlOptions.CommandTimeout(30); // 30 second command timeout
    }),
    poolSize: 128 // Connection pool size (default: 1024)
);
```

**Benefits:**
- Reuses connections (avoids overhead of opening new connection)
- Faster DbContext creation

---

### 2.5 Pagination Strategies

**Offset Pagination** (for small datasets):

```csharp
var customers = await _context.Customers
    .OrderBy(c => c.Name)
    .Skip((page - 1) * pageSize)
    .Take(pageSize)
    .ToListAsync();
```

**Keyset Pagination** (for large datasets, faster):

```csharp
// First page
var customers = await _context.Customers
    .OrderBy(c => c.Name)
    .ThenBy(c => c.Id)
    .Take(pageSize)
    .ToListAsync();

// Next page (using last seen name and id)
var nextPage = await _context.Customers
    .Where(c => c.Name.CompareTo(lastSeenName) > 0 ||
                (c.Name == lastSeenName && c.Id.CompareTo(lastSeenId) > 0))
    .OrderBy(c => c.Name)
    .ThenBy(c => c.Id)
    .Take(pageSize)
    .ToListAsync();
```

---

### 2.6 Denormalization (When Justified)

**Avoid premature denormalization**, but consider for:
- Frequently accessed aggregations (total order amount, order count)
- Complex calculations (discount tiers)

**Example: Customer Order Total YTD**

```csharp
// Normalized: Calculate on every query (slow)
var orderTotalYTD = customer.Orders
    .Where(o => o.OrderDate.Year == DateTime.UtcNow.Year)
    .Sum(o => o.Amount);

// Denormalized: Store in Customer table, update on order changes (fast)
public class Customer : BaseEntity
{
    public decimal OrderTotalYTD { get; set; } // Cached value
}

// Update on order create/update
public async Task CreateOrderAsync(Order order)
{
    await _context.Orders.AddAsync(order);

    var customer = await _context.Customers.FindAsync(order.CustomerId);
    customer.OrderTotalYTD += order.Amount;

    await _context.SaveChangesAsync();
}
```

**Tradeoff:** Consistency (must ensure cached value stays in sync).

---

## 3. Caching Strategies

### 3.1 Response Caching (HTTP Cache Headers)

**Cache GET responses at HTTP level:**

```csharp
builder.Services.AddResponseCaching();
app.UseResponseCaching();

// Endpoint with caching
app.MapGet("/api/customers", async (AppDbContext context) =>
{
    var customers = await context.Customers.ToListAsync();
    return Results.Ok(customers);
})
.CacheOutput(policy => policy.Expire(TimeSpan.FromMinutes(5))); // Cache for 5 minutes
```

**Cache-Control Headers:**
- `Cache-Control: public, max-age=300` (cache for 5 minutes)
- `Cache-Control: no-cache` (revalidate every time)
- `Cache-Control: no-store` (never cache, for sensitive data)

---

### 3.2 In-Memory Caching (Reference Data)

**Cache reference data** (regions, categories, statuses) in memory:

```csharp
public class RegionService
{
    private readonly IMemoryCache _cache;
    private readonly AppDbContext _context;

    public async Task<List<Region>> GetAllRegionsAsync()
    {
        return await _cache.GetOrCreateAsync("regions", async entry =>
        {
            entry.AbsoluteExpirationRelativeToNow = TimeSpan.FromHours(24); // Cache for 24 hours
            return await _context.Regions.ToListAsync();
        });
    }
}
```

**What to Cache:**
- Reference data (changes rarely)
- User profiles (changes infrequently)
- Authorization policies (changes infrequently)

**What NOT to Cache:**
- Transactional data (orders, payments)
- Real-time data (order status)

---

### 3.3 Distributed Caching (Redis)

**Use Redis for session data or frequently accessed data** across multiple app servers:

```csharp
builder.Services.AddStackExchangeRedisCache(options =>
{
    options.Configuration = "redis.example.com:6379";
    options.InstanceName = "App_";
});

public class CustomerService
{
    private readonly IDistributedCache _cache;

    public async Task<Customer?> GetCustomerByIdAsync(Guid customerId)
    {
        var cacheKey = $"customer:{customerId}";

        // Try cache first
        var cachedCustomer = await _cache.GetStringAsync(cacheKey);
        if (cachedCustomer != null)
            return JsonSerializer.Deserialize<Customer>(cachedCustomer);

        // Cache miss, query database
        var customer = await _context.Customers.FindAsync(customerId);

        // Store in cache for 10 minutes
        await _cache.SetStringAsync(cacheKey, JsonSerializer.Serialize(customer),
            new DistributedCacheEntryOptions { AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(10) });

        return customer;
    }
}
```

---

### 3.4 Cache Invalidation

**Invalidate cache on updates:**

```csharp
public async Task UpdateCustomerAsync(Guid customerId, UpdateCustomerRequest request)
{
    var customer = await _context.Customers.FindAsync(customerId);
    customer.Name = request.Name;
    await _context.SaveChangesAsync();

    // Invalidate cache
    await _cache.RemoveAsync($"customer:{customerId}");
}
```

**Strategies:**
- **Time-based**: Cache expires after N minutes (simple, eventually consistent)
- **Event-based**: Invalidate on update (complex, immediately consistent)

---

### 3.5 Cache-Aside Pattern

**Application manages cache** (load, populate, invalidate):

1. Check cache
2. If miss, query database
3. Store in cache
4. Return result

```csharp
public async Task<Customer?> GetCustomerAsync(Guid id)
{
    // 1. Check cache
    var cachedCustomer = await _cache.GetAsync<Customer>($"customer:{id}");
    if (cachedCustomer != null)
        return cachedCustomer;

    // 2. Cache miss, query database
    var customer = await _context.Customers.FindAsync(id);

    // 3. Store in cache
    if (customer != null)
        await _cache.SetAsync($"customer:{id}", customer, TimeSpan.FromMinutes(10));

    // 4. Return
    return customer;
}
```

---

## 4. API Performance

### 4.1 Compression (gzip, brotli)

**Enable response compression:**

```csharp
builder.Services.AddResponseCompression(options =>
{
    options.EnableForHttps = true; // Compress HTTPS responses
    options.Providers.Add<BrotliCompressionProvider>(); // Brotli (better compression)
    options.Providers.Add<GzipCompressionProvider>(); // Gzip (fallback)
});

app.UseResponseCompression();
```

**Reduces payload size by 70-90%** for JSON responses.

---

### 4.2 Response Pagination (Limit Payload Size)

**Always paginate list endpoints:**

```csharp
app.MapGet("/api/customers", async (
    [FromQuery] int page = 1,
    [FromQuery] int pageSize = 20) =>
{
    if (pageSize > 100) pageSize = 100; // Max 100 items per page

    var customers = await _context.Customers
        .Skip((page - 1) * pageSize)
        .Take(pageSize)
        .ToListAsync();

    return Results.Ok(new { data = customers, page, pageSize });
});
```

**Never return unlimited results** (risk of huge payloads, timeouts).

---

### 4.3 Partial Responses (Field Selection)

**Allow clients to request only needed fields:**

```csharp
// Request: GET /api/customers?fields=id,name,status
app.MapGet("/api/customers", async (
    [FromQuery] string? fields) =>
{
    var query = _context.Customers.AsQueryable();

    // Project based on requested fields
    if (!string.IsNullOrEmpty(fields))
    {
        var fieldList = fields.Split(',');
        // ... dynamic projection
    }

    return Results.Ok(await query.ToListAsync());
});
```

**Reduces payload size** for mobile clients.

---

### 4.4 Batch Endpoints (Avoid Chatty APIs)

**Provide batch endpoints for common operations:**

```csharp
// BAD: Client makes 10 separate requests
// GET /api/customers/1
// GET /api/customers/2
// ...

// GOOD: Batch endpoint
// POST /api/customers/batch
// { "ids": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] }
app.MapPost("/api/customers/batch", async (BatchRequest request) =>
{
    var customers = await _context.Customers
        .Where(c => request.Ids.Contains(c.Id))
        .ToListAsync();

    return Results.Ok(customers);
});
```

---

### 4.5 Async Processing (Long-Running Operations)

**For operations that take > 5 seconds, use async processing:**

```csharp
// Client initiates long-running operation
app.MapPost("/api/reports/generate", async (GenerateReportRequest request) =>
{
    // Start background job (Hangfire, Temporal)
    var jobId = await _backgroundJobClient.EnqueueAsync(() => GenerateReportAsync(request));

    // Return 202 Accepted with job ID
    return Results.Accepted($"/api/reports/jobs/{jobId}", new { jobId });
});

// Client polls for status
app.MapGet("/api/reports/jobs/{jobId}", async (string jobId) =>
{
    var status = await _jobService.GetStatusAsync(jobId);

    return status.IsComplete
        ? Results.Ok(new { status = "completed", result = status.Result })
        : Results.Ok(new { status = "processing" });
});
```

---

## 5. Load Testing & Monitoring

### 5.1 Load Testing Tools

**k6 (Recommended):**

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '1m', target: 50 },  // Ramp up to 50 users
    { duration: '3m', target: 50 },  // Stay at 50 users for 3 min
    { duration: '1m', target: 100 }, // Ramp up to 100 users
    { duration: '3m', target: 100 }, // Stay at 100 users for 3 min
    { duration: '1m', target: 0 },   // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% of requests < 500ms
    http_req_failed: ['rate<0.01'],   // < 1% errors
  },
};

export default function () {
  let res = http.get('https://api.example.com/api/customers');
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });
  sleep(1);
}
```

**JMeter:**
- GUI-based tool
- Good for complex scenarios
- Heavier than k6

---

### 5.2 Performance Baselines

**Establish baselines before optimization:**

**Metrics to Track:**
- Average response time
- 95th percentile response time
- Requests per second
- Error rate
- Database query time
- CPU/memory usage

**Baseline Tests:**
- Run load test with 50 concurrent users
- Record metrics
- Optimize
- Run load test again, compare

---

### 5.3 Application Performance Monitoring (APM)

**Tools:**
- **Application Insights** (Azure)
- **New Relic**
- **Datadog**
- **Elastic APM**

**Metrics to Monitor:**
- **Request duration**: Track slow endpoints
- **Dependency duration**: Track database query times, external API calls
- **Exception rate**: Track errors
- **Request rate**: Track throughput

**Example: Application Insights**

```csharp
builder.Services.AddApplicationInsightsTelemetry();

// Custom metrics
_telemetryClient.TrackMetric("OrderCreated", 1);
_telemetryClient.TrackDependency("PostgreSQL", "GetCustomer", startTime, duration, success);
```

---

### 5.4 Structured Logging (with Correlation IDs)

**Log requests with correlation IDs** for tracing:

```csharp
app.Use(async (context, next) =>
{
    var correlationId = context.Request.Headers["X-Correlation-ID"].FirstOrDefault()
        ?? Guid.NewGuid().ToString();

    context.Response.Headers.Add("X-Correlation-ID", correlationId);

    using (_logger.BeginScope(new Dictionary<string, object> { ["CorrelationId"] = correlationId }))
    {
        await next();
    }
});

// All logs within request include correlation ID
_logger.LogInformation("Processing request for customer {CustomerId}", customerId);
```

**Benefits:** Trace single request across multiple services/logs.

---

### 5.5 Metrics (Response Times, Error Rates, Throughput)

**Prometheus Metrics:**

```csharp
builder.Services.AddSingleton<IMetricsCollector, PrometheusMetricsCollector>();

public class PrometheusMetricsCollector
{
    private readonly Counter _requestCounter = Metrics.CreateCounter(
        "app_http_requests_total",
        "Total HTTP requests",
        new CounterConfiguration { LabelNames = new[] { "method", "endpoint", "status" } });

    private readonly Histogram _requestDuration = Metrics.CreateHistogram(
        "app_http_request_duration_seconds",
        "HTTP request duration in seconds",
        new HistogramConfiguration { LabelNames = new[] { "method", "endpoint" } });

    public void RecordRequest(string method, string endpoint, int statusCode, double duration)
    {
        _requestCounter.WithLabels(method, endpoint, statusCode.ToString()).Inc();
        _requestDuration.WithLabels(method, endpoint).Observe(duration);
    }
}

// Expose /metrics endpoint for Prometheus scraping
app.MapMetrics();
```

---

## Version History

**Version 1.0** - 2026-01-31 - Initial performance design guide (420 lines)

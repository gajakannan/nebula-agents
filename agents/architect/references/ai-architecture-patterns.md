# AI Architecture Patterns

> **Audience:** Software Architects designing AI features
> **Purpose:** Design guidance for integrating AI/LLM capabilities into applications
> **Related:** `agents/architect/references/ai-integration-patterns.md` (choose integration pattern first)

---

This guide provides architects with specific patterns, contracts, and design decisions for integrating AI features. Read `agents/architect/references/ai-integration-patterns.md` first to choose between AI-Optional, AI-Embedded, or AI-Centric patterns, then use this guide for detailed architecture design.

---

## 1. Architect Responsibilities for AI Features

When AI features are in scope, architects must define:

1. **Integration Pattern Selection** - Which AI pattern (Optional/Embedded/Centric) fits requirements?
2. **API Contracts** - Backend ↔ Neuron interfaces (request/response schemas)
3. **Data Access Patterns** - How AI agents access CRM data (direct, proxy, MCP)
4. **Authentication & Authorization** - Service-to-service auth, user permissions
5. **Error Handling & Fallbacks** - What happens when AI fails?
6. **Cost Controls** - Rate limiting, model selection, budget constraints
7. **Observability Requirements** - Logging, metrics, tracing for AI calls
8. **Security Boundaries** - PII protection, prompt injection prevention

---

## 2. Pattern Selection Decision Tree

### Step 1: Assess AI Complexity

**Simple AI (Pattern 1: AI-Optional)**
- Single LLM API call per feature
- No multi-step workflows
- No prompt management or versioning
- No dedicated AI engineering needed

**Moderate AI (Pattern 2: AI-Embedded)**
- Multi-step workflows (analyze → reason → recommend)
- Prompt management and versioning required
- Reusable AI logic across multiple features
- Dedicated AI Engineer on team

**Complex AI (Pattern 3: AI-Centric)**
- Real-time streaming (chat, live suggestions)
- MCP servers for external tool access
- Advanced patterns (RAG, multi-agent, vector search)
- AI is primary application value

### Step 2: Assess Team & Org Constraints

| Constraint | AI-Optional | AI-Embedded | AI-Centric |
|------------|-------------|-------------|------------|
| **Team Size** | 2-3 (no AI eng) | 3-5 (1 AI eng) | 5+ (2+ AI eng) |
| **AI Budget** | <$100/mo | $100-1000/mo | >$1000/mo |
| **Deployment Complexity** | Minimal | Moderate | High |
| **Time to Market** | Fastest | Moderate | Slowest |

### Step 3: Document Decision

Create ADR in `{PRODUCT_ROOT}/planning-mds/architecture/decisions/`:

**Example ADR:**
```markdown
# ADR: AI Integration Pattern for Customer Insights

## Status
Accepted

## Context
We need to implement AI-powered customer risk assessment and recommendations.
Requirements:
- Multi-step analysis workflow (fetch data → analyze → recommend)
- Reusable across multiple customer features
- AI Engineer available on team
- Budget: ~$500/month
- No need for real-time streaming

## Decision
Use **AI-Embedded (Pattern 2)** with {PRODUCT_ROOT}/neuron/ layer accessed via backend proxy.

## Consequences
✅ Clear separation of business logic ({PRODUCT_ROOT}/engine/) and AI logic ({PRODUCT_ROOT}/neuron/)
✅ AI logic testable independently
✅ Backend controls authorization and rate limiting
✅ Can scale {PRODUCT_ROOT}/neuron/ independently
❌ Added deployment complexity (2 services → 3 services)
❌ Extra latency from proxy hop (~50-100ms)
```

---

## 3. API Contract Patterns (Backend ↔ Neuron)

### 3.1 Request/Response Contract Template

All {PRODUCT_ROOT}/neuron/ API endpoints should follow this structure:

**Request:**
```json
{
  "entity_id": "uuid or string",
  "context": {
    "include_history": boolean,
    "lookback_period_days": number,
    "additional_params": "..."
  },
  "options": {
    "model_preference": "haiku" | "sonnet" | "opus",
    "max_latency_ms": number,
    "language": "en" | "es" | "..."
  }
}
```

**Response (Success):**
```json
{
  "result": {
    "classification": "High" | "Medium" | "Low",
    "confidence": 0.85,
    "details": ["detail1", "detail2"],
    "recommendations": [
      {
        "action": "string",
        "priority": "High" | "Medium" | "Low",
        "reasoning": "string"
      }
    ]
  },
  "metadata": {
    "model_used": "llm-model",
    "token_count": 450,
    "cost_usd": 0.0023,
    "latency_ms": 1234,
    "generated_at": "2026-02-07T10:30:00Z"
  }
}
```

**Response (Error):**
```json
{
  "error": "insufficient_data" | "ai_processing_failed" | "rate_limit_exceeded",
  "message": "Human-readable error message",
  "details": {
    "min_required": 10,
    "actual": 2
  },
  "retry_after_seconds": 60  // For rate limit errors
}
```

### 3.2 OpenAPI Specification

Document all {PRODUCT_ROOT}/neuron/ endpoints in `{PRODUCT_ROOT}/planning-mds/api/neuron-api.yaml`:

```yaml
openapi: 3.0.0
info:
  title: Neuron AI Service API
  version: 1.0.0
servers:
  - url: http://neuron:8000
    description: Internal neuron service

paths:
  /assess-customer-risk:
    post:
      summary: Assess customer risk level
      operationId: assessCustomerRisk
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/RiskAssessmentRequest'
      responses:
        '200':
          description: Risk assessment completed
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/RiskAssessmentResponse'
        '400':
          description: Invalid request or insufficient data
        '429':
          description: Rate limit exceeded
        '500':
          description: AI processing failed

components:
  schemas:
    RiskAssessmentRequest:
      type: object
      required: [customer_id]
      properties:
        customer_id:
          type: string
          format: uuid
        context:
          type: object
          properties:
            include_payment_history:
              type: boolean
              default: true
            lookback_months:
              type: integer
              default: 6

    RiskAssessmentResponse:
      type: object
      properties:
        result:
          type: object
          properties:
            risk_level:
              type: string
              enum: [Low, Medium, High]
            confidence:
              type: number
              minimum: 0.0
              maximum: 1.0
            key_indicators:
              type: array
              items:
                type: string
        metadata:
          $ref: '#/components/schemas/AiMetadata'
```

### 3.3 Backend Proxy Service Pattern

**File:** `{PRODUCT_ROOT}/engine/Services/AiProxyService.cs`

**Responsibilities:**
1. Authorization enforcement
2. Rate limiting
3. Request validation
4. Error handling with fallbacks
5. Audit logging
6. Timeout enforcement

**Example Implementation:**
```csharp
public class AiProxyService
{
    private readonly HttpClient _neuronClient;
    private readonly IAuthorizationService _authz;
    private readonly IRateLimiter _rateLimiter;
    private readonly ILogger<AiProxyService> _logger;

    public async Task<RiskAssessmentResult> AssessCustomerRiskAsync(
        Guid customerId,
        ClaimsPrincipal user)
    {
        // 1. Authorize
        if (!await _authz.HasPermissionAsync(user, "customer:analyze-risk"))
        {
            _logger.LogWarning("Unauthorized AI request: {UserId}", user.GetUserId());
            throw new UnauthorizedException("Insufficient permissions");
        }

        // 2. Rate limit
        if (!await _rateLimiter.AllowRequestAsync(user.GetUserId(), "ai-risk-assessment"))
        {
            _logger.LogWarning("Rate limit exceeded: {UserId}", user.GetUserId());
            throw new RateLimitExceededException("Too many AI requests");
        }

        // 3. Call {PRODUCT_ROOT}/neuron/ with timeout
        try
        {
            var request = new RiskAssessmentRequest
            {
                CustomerId = customerId,
                Context = new { IncludePaymentHistory = true, LookbackMonths = 6 }
            };

            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
            var response = await _neuronClient.PostAsJsonAsync(
                "/assess-customer-risk",
                request,
                cts.Token
            );

            if (!response.IsSuccessStatusCode)
            {
                _logger.LogError("Neuron API error: {StatusCode}", response.StatusCode);
                return CreateFallbackResponse();
            }

            var result = await response.Content.ReadFromJsonAsync<RiskAssessmentResponse>();

            // 4. Audit log
            await LogAiUsageAsync(user.GetUserId(), customerId, result.Metadata);

            return result.Result;
        }
        catch (TaskCanceledException)
        {
            _logger.LogError("Neuron API timeout for customer {CustomerId}", customerId);
            return CreateFallbackResponse();
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "Neuron API connection failed");
            return CreateFallbackResponse();
        }
    }

    private RiskAssessmentResult CreateFallbackResponse()
    {
        return new RiskAssessmentResult
        {
            Error = "AI analysis temporarily unavailable. Please try again later.",
            IsError = true
        };
    }
}
```

---

## 4. Data Access Patterns

### 4.1 Pattern: Backend Proxy (Recommended for AI-Embedded)

**Flow:**
```
AI Agent ({PRODUCT_ROOT}/neuron/) → HTTP call → Backend Internal API ({PRODUCT_ROOT}/engine/) → Database
```

**Advantages:**
- ✅ Backend enforces authorization
- ✅ Single source of truth for data access logic
- ✅ Consistent audit logging
- ✅ No direct database access from AI layer

**Implementation:**

**Backend Internal API** (`{PRODUCT_ROOT}/engine/Controllers/InternalController.cs`):
```csharp
[ApiController]
[Route("api/internal")]
[Authorize(AuthenticationSchemes = "ServiceAuth")] // Service-to-service auth
public class InternalController : ControllerBase
{
    [HttpGet("customers/{id}")]
    public async Task<CustomerDto> GetCustomer(Guid id)
    {
        // Validate service token
        if (!User.IsService())
            return Forbid();

        // Return customer data for AI analysis
        var customer = await _customerService.GetAsync(id);
        return MapToDto(customer);
    }

    [HttpGet("customers/{id}/payments")]
    public async Task<List<PaymentDto>> GetPayments(Guid id)
    {
        if (!User.IsService())
            return Forbid();

        return await _paymentService.GetPaymentHistoryAsync(id);
    }
}
```

**AI Agent** (`{PRODUCT_ROOT}/neuron/domain_agents/data_fetcher.py`):
```python
import httpx

class DataFetcher:
    def __init__(self, service_token: str):
        self.service_token = service_token
        self.base_url = "http://engine:5000/api/internal"

    async def fetch_customer_context(self, customer_id: str) -> dict:
        """Fetch customer data from backend internal API."""
        headers = {"Authorization": f"Bearer {self.service_token}"}

        async with httpx.AsyncClient() as client:
            # Fetch in parallel
            customer_task = client.get(
                f"{self.base_url}/customers/{customer_id}",
                headers=headers
            )
            payments_task = client.get(
                f"{self.base_url}/customers/{customer_id}/payments",
                headers=headers
            )

            customer_resp, payments_resp = await asyncio.gather(
                customer_task, payments_task
            )

            return {
                "customer": customer_resp.json(),
                "payments": payments_resp.json()
            }
```

### 4.2 Pattern: MCP Server (For AI-Centric)

**Flow:**
```
AI Agent ({PRODUCT_ROOT}/neuron/) → MCP Tool Call → MCP Server ({PRODUCT_ROOT}/neuron/mcp/) → Backend API ({PRODUCT_ROOT}/engine/)
```

**Use When:**
- AI-Centric pattern (Pattern 3)
- Multiple AI agents need data access
- Need standardized tool interface
- External AI systems need CRM data access

**MCP Server Specification:**

File: `{PRODUCT_ROOT}/planning-mds/api/mcp-servers.yaml`

```yaml
mcp_server:
  name: crm-data-mcp
  version: 1.0.0
  description: MCP server for CRM data access

tools:
  - name: get_customer
    description: Fetch customer by ID
    input_schema:
      type: object
      properties:
        customer_id:
          type: string
          format: uuid
          description: Customer UUID
      required: [customer_id]
    returns:
      type: object
      description: Customer details

  - name: search_customers
    description: Search customers by query
    input_schema:
      type: object
      properties:
        query:
          type: string
          description: Search query
        limit:
          type: integer
          default: 10
          maximum: 100
      required: [query]
    returns:
      type: array
      items:
        type: object
      description: List of matching customers

authentication:
  type: bearer_token
  token_source: service_token_provider
  scopes: [crm.read, crm.write]

rate_limiting:
  requests_per_minute: 100
  requests_per_hour: 1000
```

---

## 5. Authentication & Authorization Architecture

### 5.1 Service-to-Service Authentication

**Requirements:**
- Neuron/ must authenticate when calling {PRODUCT_ROOT}/engine/ internal APIs
- Token-based authentication (JWT)
- Short-lived tokens (1 hour expiry)
- Scoped permissions (crm.read, crm.write, etc.)

**Token Provisioning:**

**Option 1: Pre-provisioned Service Token**
```bash
# Generate service token at deployment time
export NEURON_SERVICE_TOKEN="eyJhbGciOiJSUzI1NiIs..."

# {PRODUCT_ROOT}/neuron/ uses this token for all backend calls
```

**Option 2: Token Exchange (Preferred)**
```csharp
// {PRODUCT_ROOT}/engine/Services/ServiceAuthService.cs
public class ServiceAuthService
{
    public async Task<string> GenerateServiceTokenAsync(string serviceName, string[] scopes)
    {
        // Generate JWT for service-to-service auth
        var serviceJwtAttributes = new[]
        {
            new Claim("sub", serviceName),
            new Claim("type", "service"),
            new Claim("scopes", string.Join(" ", scopes))
        };

        var token = _jwtGenerator.GenerateToken(serviceJwtAttributes, expiresIn: TimeSpan.FromHours(1));
        return token;
    }
}
```

### 5.2 User Permission Enforcement

**Backend MUST enforce user permissions before calling AI:**

```csharp
// ❌ BAD: No permission check before AI call
public async Task<RiskAssessment> GetRiskAsync(Guid customerId)
{
    return await _aiService.AssessRiskAsync(customerId); // Bypasses authz!
}

// ✅ GOOD: Check permission first
public async Task<RiskAssessment> GetRiskAsync(Guid customerId, ClaimsPrincipal user)
{
    // Enforce permission
    if (!await _authz.HasPermissionAsync(user, "customer:analyze-risk"))
        throw new UnauthorizedException();

    // Then call AI
    return await _aiService.AssessRiskAsync(customerId, user);
}
```

**Permission Mapping:**

| Feature | Permission Required | Scope |
|---------|---------------------|-------|
| Risk Assessment | `customer:analyze-risk` | Customer-specific |
| Batch Analysis | `customer:batch-analyze` | Organization-wide |
| Recommendation Generation | `customer:ai-recommendations` | Customer-specific |
| AI Chat | `ai:chat` | User-specific |

---

## 6. Error Handling & Fallback Patterns

### 6.1 Error Classification

**Transient Errors (Retry):**
- `503 Service Unavailable` - Neuron/ temporarily down
- `429 Rate Limit` - LLM provider API rate limit
- Network timeout - Connection issues

**Permanent Errors (No Retry):**
- `400 Bad Request` - Invalid input
- `401 Unauthorized` - Auth failed
- `403 Forbidden` - Permission denied
- `insufficient_data` - Not enough data for analysis

### 6.2 Fallback Strategy

**Level 1: Degraded AI Response**
```csharp
if (aiResponse.Confidence < 0.6)
{
    return new Result
    {
        Message = "AI analysis completed but confidence is low. Manual review recommended.",
        ShowWarning = true,
        Data = aiResponse
    };
}
```

**Level 2: Generic Fallback**
```csharp
catch (AiServiceException ex)
{
    _logger.LogError(ex, "AI service failed for customer {CustomerId}", customerId);

    return new Result
    {
        Message = "AI analysis is temporarily unavailable. Please try again in a few minutes.",
        IsError = true
    };
}
```

**Level 3: Feature Disabled**
```csharp
// Show UI without AI features
return new Result
{
    FeatureAvailable = false,
    Message = "AI features are currently unavailable."
};
```

### 6.3 Timeout Configuration

**Recommended Timeouts:**
```csharp
// Frontend → Backend: 15 seconds
// Backend → Neuron: 10 seconds
// Neuron → LLM: 8 seconds

var httpClient = new HttpClient
{
    BaseAddress = new Uri("http://neuron:8000"),
    Timeout = TimeSpan.FromSeconds(10)
};
```

---

## 7. Cost Control Architecture

### 7.1 Rate Limiting Strategy

**Per-User Rate Limits:**
```csharp
public class AiRateLimitConfig
{
    public int RequestsPerMinute { get; set; } = 10;
    public int RequestsPerHour { get; set; } = 100;
    public int RequestsPerDay { get; set; } = 500;
}
```

**Per-Organization Rate Limits:**
```csharp
// Prevent single org from consuming all AI budget
public int OrgRequestsPerHour { get; set; } = 1000;
public decimal OrgDailyCostLimit { get; set; } = 50.00m;
```

**Implementation:**
```csharp
public async Task<bool> AllowRequestAsync(string userId, string feature)
{
    var userKey = $"ai:ratelimit:user:{userId}:{feature}";
    var orgKey = $"ai:ratelimit:org:{user.OrgId}:{feature}";

    // Check user limit
    var userCount = await _redis.IncrementAsync(userKey, expiry: TimeSpan.FromMinutes(1));
    if (userCount > _config.RequestsPerMinute)
        return false;

    // Check org limit
    var orgCount = await _redis.IncrementAsync(orgKey, expiry: TimeSpan.FromHours(1));
    if (orgCount > _config.OrgRequestsPerHour)
        return false;

    return true;
}
```

### 7.2 Model Selection for Cost Optimization

**Cost Tiers (varies by provider):**
- Lightweight models: ~$0.0005-0.001 per request (fast, simple tasks)
- Balanced models: ~$0.003-0.005 per request (default choice)
- Advanced models: ~$0.015-0.02 per request (complex reasoning)

**Routing Logic:**
```python
def select_model(task_complexity: str, data_quality: str) -> str:
    """Route to appropriate model based on task."""
    if task_complexity == "simple" and data_quality == "good":
        return "llm-lightweight"  # 10-20x cheaper

    if task_complexity == "complex" or data_quality == "poor":
        return "llm-advanced"   # Best reasoning

    return "llm-balanced"     # Balanced default
```

---

## 8. Observability Requirements

### 8.1 Logging

**Required Log Fields:**
```json
{
  "timestamp": "2026-02-07T10:30:00Z",
  "level": "INFO",
  "event": "ai_request",
  "user_id": "uuid",
  "customer_id": "uuid",
  "feature": "risk-assessment",
  "model_used": "llm-balanced",
  "token_count": 450,
  "cost_usd": 0.0023,
  "latency_ms": 1234,
  "status": "success" | "error",
  "error_type": "rate_limit" | "timeout" | null
}
```

### 8.2 Metrics

**Track These Metrics:**
```csharp
// Request metrics
_metrics.Increment("ai.requests.total", tags: ["feature:risk", "model:sonnet"]);
_metrics.Histogram("ai.latency_ms", latency, tags: ["feature:risk"]);

// Cost metrics
_metrics.Increment("ai.tokens.total", tokenCount, tags: ["model:sonnet"]);
_metrics.Increment("ai.cost_usd", cost, tags: ["model:sonnet"]);

// Error metrics
_metrics.Increment("ai.errors.total", tags: ["error:timeout", "feature:risk"]);
```

**Alerts:**
- Error rate > 5% for 5 minutes
- P95 latency > 10 seconds for 10 minutes
- Daily cost > $50
- Rate limit hit > 100 times in 1 hour

### 8.3 Distributed Tracing

**Trace AI Request Flow:**
```
User Request (trace_id=abc123)
  → Backend API (span: api_request)
    → Auth Check (span: authz)
    → AI Proxy Service (span: ai_proxy)
      → Neuron API (span: neuron_request)
        → Data Fetch (span: data_fetch)
        → LLM Call (span: llm_call)
        → Response Parse (span: parse_response)
      ← Neuron Response
    ← AI Proxy Response
  ← Backend Response
```

---

## 9. Security Patterns

### 9.1 PII Protection

**Never Log Full PII to AI Logs:**
```csharp
// ❌ BAD: Logs full customer data
_logger.LogInfo("AI request for {Customer}", JsonSerializer.Serialize(customer));

// ✅ GOOD: Logs only IDs
_logger.LogInfo("AI request for customer {CustomerId}", customer.Id);
```

**Sanitize Before Sending to LLM:**
```python
def sanitize_customer_data(customer: dict) -> dict:
    """Remove PII before sending to LLM."""
    return {
        "profile": {
            "name": "<REDACTED>",  # Don't send real names to LLM logs
            "email": "<REDACTED>",
            "status": customer["status"],
            "account_age_days": customer["account_age_days"]
        },
        "metrics": customer["metrics"]  # Aggregated metrics OK
    }
```

### 9.2 Prompt Injection Prevention

**Validate User Inputs:**
```csharp
public async Task<string> AnalyzeWithUserInputAsync(string userQuery)
{
    // Validate input length
    if (userQuery.Length > 500)
        throw new ValidationException("Query too long");

    // Detect prompt injection attempts
    if (ContainsSuspiciousPatterns(userQuery))
    {
        _logger.LogWarning("Potential prompt injection detected: {Query}", userQuery);
        throw new ValidationException("Invalid input");
    }

    // Escape special characters
    var sanitized = EscapePromptSpecialChars(userQuery);

    return await _aiService.AnalyzeAsync(sanitized);
}

private bool ContainsSuspiciousPatterns(string input)
{
    var suspiciousPatterns = new[]
    {
        "ignore previous",
        "disregard instructions",
        "new instructions:",
        "system:",
        "</user>",
        "<system>"
    };

    return suspiciousPatterns.Any(p => input.Contains(p, StringComparison.OrdinalIgnoreCase));
}
```

### 9.3 Output Sanitization

**Never Trust LLM Outputs:**
```csharp
public async Task<RiskAssessment> GetRiskAsync(Guid customerId)
{
    var aiResult = await _aiService.AssessRiskAsync(customerId);

    // Validate AI output
    if (!IsValidRiskLevel(aiResult.RiskLevel))
    {
        _logger.LogError("Invalid AI output: {RiskLevel}", aiResult.RiskLevel);
        return CreateFallbackResponse();
    }

    // Sanitize recommendations (prevent XSS if displayed in UI)
    aiResult.Recommendations = aiResult.Recommendations
        .Select(r => HtmlEncoder.Default.Encode(r))
        .ToList();

    return aiResult;
}
```

---

## 10. Architect Deliverables Checklist

When designing AI features, architects must deliver:

- [ ] **ADR documenting pattern selection** (AI-Optional, Embedded, or Centric)
- [ ] **OpenAPI spec for {PRODUCT_ROOT}/neuron/ API** (`{PRODUCT_ROOT}/planning-mds/api/neuron-api.yaml`)
- [ ] **Data access pattern definition** (Backend proxy or MCP server)
- [ ] **Authentication design** (Service-to-service auth, user permissions)
- [ ] **Error handling strategy** (Fallbacks, timeouts, retries)
- [ ] **Rate limiting config** (Per-user, per-org limits)
- [ ] **Cost control strategy** (Model selection, budget limits)
- [ ] **Observability requirements** (Logs, metrics, traces, alerts)
- [ ] **Security review** (PII protection, prompt injection, output sanitization)
- [ ] **Non-functional requirements** (Latency SLAs, cost SLAs, availability)

---

## 11. Common Mistakes to Avoid

❌ **Skipping authorization checks** - Always enforce permissions before AI calls
❌ **No rate limiting** - AI features can be abused without limits
❌ **Logging PII** - Never log sensitive data to AI logs
❌ **No fallback strategy** - Application crashes when AI fails
❌ **Trusting LLM outputs** - Always validate AI responses
❌ **No cost tracking** - AI costs spiral without monitoring
❌ **Deep integration** - AI logic tightly coupled to business logic
❌ **No timeout handling** - Requests hang indefinitely

---

## 12. References

**Framework Documentation:**
- `agents/architect/references/ai-integration-patterns.md` - Choose AI pattern first
- `agents/ai-engineer/SKILL.md` - AI Engineer responsibilities
- `{PRODUCT_ROOT}/planning-mds/examples/stories/ai-story-example.md` - Example AI story

**External Resources:**
- [Model Context Protocol (MCP)](https://spec.modelcontextprotocol.io/)
- [OWASP LLM Security Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [LangChain Documentation](https://python.langchain.com/) (Multi-provider abstraction)
- Provider docs: See vendor selection guide in `ai-integration-patterns.md`

---

**Questions?** Consult with AI Engineer or Security Agent for implementation details.

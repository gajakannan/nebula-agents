# AI Engineer Code Patterns

Reference patterns extracted from the main SKILL.md for detailed implementation guidance.

## Best Practices

### Prompt Engineering
```python
# Good: Clear, structured prompt
system_prompt = """
You are a data processing assistant for customer records.

Your task: Analyze the record and generate a classification report.

Input format:
- Category: {category}
- Value: {value}
- Region: {region}
- History: {history}

Output format:
- Priority: Low/Medium/High
- Recommended action: Brief description
- Reasoning: 2-3 sentences

Rules:
- Flag high-value items for immediate review
- Consider region-specific factors
- Weight recent history heavily
"""
```

### Model Selection
```python
def route_request(task_complexity: str) -> str:
    """Route to appropriate model based on complexity."""
    if task_complexity == "simple":
        return "llm-lightweight"  # Fast, cheap
    elif task_complexity == "complex":
        return "llm-advanced"   # Deep reasoning
    else:
        return "llm-balanced" # Balanced
```

### Error Handling
```python
async def call_llm_with_retry(prompt: str, max_retries: int = 3):
    """Call LLM with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            response = await client.messages.create(...)
            return response
        except RateLimitError:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)
        except APIError as e:
            logger.error(f"LLM API error: {e}")
            raise
```

### Cost Tracking
```python
def track_usage(prompt_tokens: int, completion_tokens: int, model: str):
    """Track token usage and cost."""
    cost = calculate_cost(prompt_tokens, completion_tokens, model)
    metrics.increment("llm.tokens.prompt", prompt_tokens)
    metrics.increment("llm.tokens.completion", completion_tokens)
    metrics.increment("llm.cost", cost)
    logger.info(f"LLM call: {model}, tokens={prompt_tokens+completion_tokens}, cost=${cost:.4f}")
```

## Common Patterns

### Simple Agent (Single Prompt)
```python
async def analyze_record(record: dict) -> dict:
    """Analyze a data record with LLM."""
    prompt = format_record_prompt(record)
    response = await llm.generate(prompt)
    return parse_response(response)
```

### ReAct Agent (Reasoning + Acting)
```python
async def process_with_tools(query: str, tools: list):
    """Agent that reasons and uses tools."""
    while not done:
        # Reason about what to do
        thought = await llm.reason(query, context)

        # Act (use a tool or provide answer)
        if thought.action == "use_tool":
            result = await execute_tool(thought.tool, thought.args)
            context.append(result)
        else:
            return thought.answer
```

### Multi-Agent Collaboration
```python
async def processing_workflow(record: dict):
    """Multi-agent data processing workflow."""
    # Agent 1: Validation
    validation = await validation_agent.check(record)

    # Agent 2: Enrichment
    enriched = await enrichment_agent.process(record, validation)

    # Agent 3: Decision
    decision = await decision_agent.approve(record, enriched)

    return decision
```

## Integration Contracts

### Backend-Neuron Integration

When implementing AI features using **AI-Embedded (Pattern 2)** or **AI-Centric (Pattern 3)**, you must define clear contracts between {PRODUCT_ROOT}/neuron/ and {PRODUCT_ROOT}/engine/:

**Your Responsibilities:**
1. **Define API Endpoints** - RESTful endpoints for AI features
2. **Document Request/Response Schemas** - OpenAPI specs in `{PRODUCT_ROOT}/planning-mds/api/neuron-api.yaml`
3. **Implement Data Fetching** - Call {PRODUCT_ROOT}/engine/ internal APIs to get CRM data
4. **Handle Service Auth** - Use service tokens to authenticate with backend
5. **Return Structured Responses** - Include metadata (model, tokens, cost, latency)
6. **Implement Error Handling** - Graceful failures with error codes

**API Contract Template:**

Request:
```json
{
  "entity_id": "uuid",
  "context": { "include_history": true, "lookback_days": 180 },
  "options": { "model_preference": "sonnet", "max_latency_ms": 5000 }
}
```

Response (Success):
```json
{
  "result": { "classification": "High", "confidence": 0.85, "details": [...] },
  "metadata": {
    "model_used": "llm-balanced",
    "token_count": 450,
    "cost_usd": 0.0023,
    "latency_ms": 1234,
    "generated_at": "2026-02-07T10:30:00Z"
  }
}
```

Response (Error):
```json
{
  "error": "insufficient_data" | "ai_processing_failed" | "rate_limit_exceeded",
  "message": "Human-readable error",
  "details": {},
  "retry_after_seconds": 60
}
```

**Data Access Pattern:**

Neuron/ calls backend internal APIs to fetch CRM data:

```python
# {PRODUCT_ROOT}/neuron/services/data_service.py
import httpx
import os

class DataService:
    def __init__(self):
        self.base_url = "http://engine:5000/api/internal"
        self.service_token = os.getenv("NEURON_SERVICE_TOKEN")

    async def fetch_customer_data(self, customer_id: str) -> dict:
        """Fetch customer data from backend internal API."""
        headers = {"Authorization": f"Bearer {self.service_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/customers/{customer_id}",
                headers=headers,
                timeout=5.0
            )

            if response.status_code == 401:
                raise AuthenticationError("Service token invalid")
            if response.status_code == 404:
                raise NotFoundError(f"Customer {customer_id} not found")

            response.raise_for_status()
            return response.json()
```

### Frontend-Neuron Integration (AI-Centric Only)

For **AI-Centric (Pattern 3)** with real-time streaming:

**Your Responsibilities:**
1. **Implement WebSocket Endpoints** - For real-time chat/streaming
2. **Handle Connection Auth** - Validate user tokens on WebSocket connect
3. **Stream LLM Responses** - Use Anthropic streaming API
4. **Implement Backpressure** - Handle slow clients gracefully

**WebSocket Endpoint Example:**

```python
# {PRODUCT_ROOT}/neuron/api/streaming.py
from fastapi import WebSocket, WebSocketDisconnect
from anthropic import AsyncAnthropic

@router.websocket("/chat/stream")
async def chat_stream(websocket: WebSocket):
    await websocket.accept()

    try:
        # Authenticate connection
        auth_message = await websocket.receive_json()
        user = await validate_auth_token(auth_message["token"])

        if not user:
            await websocket.send_json({"error": "Unauthorized"})
            await websocket.close()
            return

        # Receive user message
        user_message = await websocket.receive_json()

        # Stream LLM response
        async with AsyncAnthropic() as client:
            async with client.messages.stream(
                model="claude-sonnet-4",
                max_tokens=1024,
                messages=[{"role": "user", "content": user_message["text"]}]
            ) as stream:
                async for text in stream.text_stream:
                    await websocket.send_json({"type": "text", "content": text})

                # Send final metadata
                final_message = await stream.get_final_message()
                await websocket.send_json({
                    "type": "metadata",
                    "tokens": final_message.usage.total_tokens,
                    "model": final_message.model
                })

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.send_json({"error": str(e)})
        await websocket.close()
```

### MCP Server Implementation (AI-Centric Only)

For **AI-Centric (Pattern 3)** with MCP servers:

**Your Responsibilities:**
1. **Implement MCP Tools** - Expose CRM data/operations as tools
2. **Define Tool Schemas** - Input/output schemas for each tool
3. **Handle Tool Authorization** - Verify scoped permissions
4. **Document MCP Server** - OpenAPI-style spec in `{PRODUCT_ROOT}/planning-mds/api/mcp-servers.yaml`

**MCP Server Example:**

```python
# {PRODUCT_ROOT}/neuron/mcp/crm_data_server.py
from mcp import Server, Tool

server = Server("crm-data-mcp")

@server.tool()
async def get_customer(customer_id: str) -> dict:
    """
    Fetch customer by ID.

    Args:
        customer_id: Customer UUID

    Returns:
        Customer object with profile and metadata
    """
    # Call backend internal API
    data_service = DataService()
    customer = await data_service.fetch_customer_data(customer_id)

    return {
        "id": customer["id"],
        "name": customer["name"],
        "status": customer["status"],
        "account_age_days": customer["account_age_days"]
    }

@server.tool()
async def search_customers(query: str, limit: int = 10) -> list[dict]:
    """
    Search customers by query.

    Args:
        query: Search query string
        limit: Max results (default 10, max 100)

    Returns:
        List of matching customers
    """
    if limit > 100:
        raise ValueError("Limit cannot exceed 100")

    data_service = DataService()
    results = await data_service.search_customers(query, limit)

    return results
```

## Observability Requirements

### Logging

**Required Log Fields for Every AI Request:**
```python
logger.info(
    "AI request completed",
    extra={
        "event": "ai_request",
        "user_id": user_id,
        "entity_id": entity_id,
        "feature": "risk-assessment",
        "model_used": "llm-balanced",
        "token_count": 450,
        "prompt_tokens": 200,
        "completion_tokens": 250,
        "cost_usd": 0.0023,
        "latency_ms": 1234,
        "status": "success",
        "confidence": 0.85
    }
)
```

**Error Logging:**
```python
logger.error(
    "AI request failed",
    extra={
        "event": "ai_error",
        "user_id": user_id,
        "entity_id": entity_id,
        "feature": "risk-assessment",
        "error_type": "rate_limit" | "timeout" | "api_error",
        "error_message": str(e),
        "retry_attempted": False
    },
    exc_info=True
)
```

**What NOT to Log:**
- Full prompts (may contain PII)
- Full LLM responses (may contain sensitive data)
- Customer PII (names, emails, SSN, etc.)

**What TO Log:**
- Request IDs, entity IDs, user IDs
- Model name, token counts, costs
- Latency, status, error types
- Confidence scores, classifications

### Metrics & Monitoring

**Implement These Metrics:**

```python
# {PRODUCT_ROOT}/neuron/services/metrics_service.py
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
ai_requests_total = Counter(
    'ai_requests_total',
    'Total AI requests',
    ['feature', 'model', 'status']
)

ai_latency_seconds = Histogram(
    'ai_latency_seconds',
    'AI request latency',
    ['feature', 'model']
)

# Cost metrics
ai_tokens_total = Counter(
    'ai_tokens_total',
    'Total tokens used',
    ['model', 'token_type']  # token_type: prompt or completion
)

ai_cost_usd_total = Counter(
    'ai_cost_usd_total',
    'Total AI cost in USD',
    ['model', 'feature']
)

# Error metrics
ai_errors_total = Counter(
    'ai_errors_total',
    'Total AI errors',
    ['feature', 'error_type']
)

# Usage example
with ai_latency_seconds.labels(feature='risk-assessment', model='claude-sonnet-4').time():
    result = await agent.assess_risk(customer_id)

ai_requests_total.labels(feature='risk-assessment', model='claude-sonnet-4', status='success').inc()
ai_tokens_total.labels(model='claude-sonnet-4', token_type='prompt').inc(result.prompt_tokens)
ai_tokens_total.labels(model='claude-sonnet-4', token_type='completion').inc(result.completion_tokens)
ai_cost_usd_total.labels(model='claude-sonnet-4', feature='risk-assessment').inc(result.cost_usd)
```

## Cost Tracking & Budgets

**Track Costs Per Feature:**

```python
# {PRODUCT_ROOT}/neuron/services/cost_tracker.py
import asyncio
from datetime import datetime
from decimal import Decimal

class CostTracker:
    def __init__(self):
        self.daily_costs = {}  # {date: {feature: cost}}

    async def track_request(
        self,
        feature: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> Decimal:
        """Track cost for AI request."""
        cost = self.calculate_cost(model, prompt_tokens, completion_tokens)

        # Update daily totals
        date = datetime.utcnow().date()
        if date not in self.daily_costs:
            self.daily_costs[date] = {}
        if feature not in self.daily_costs[date]:
            self.daily_costs[date][feature] = Decimal('0.0')

        self.daily_costs[date][feature] += cost

        # Check budget limits
        if self.daily_costs[date][feature] > Decimal('50.0'):
            logger.warning(
                f"Feature {feature} exceeded daily budget: ${self.daily_costs[date][feature]}"
            )

        return cost

    def calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
        """Calculate cost based on token usage."""
        # Pricing as of 2026 (update as needed)
        pricing = {
            "claude-haiku-4": {"prompt": 0.00025, "completion": 0.00125},
            "claude-sonnet-4": {"prompt": 0.003, "completion": 0.015},
            "claude-opus-4": {"prompt": 0.015, "completion": 0.075}
        }

        if model not in pricing:
            logger.error(f"Unknown model: {model}")
            return Decimal('0.0')

        cost = (
            Decimal(str(pricing[model]["prompt"])) * prompt_tokens / 1000 +
            Decimal(str(pricing[model]["completion"])) * completion_tokens / 1000
        )

        return cost.quantize(Decimal('0.0001'))
```

## Security Best Practices

### 1. PII Protection

**Never Log PII:**
```python
# BAD: Logs customer name
logger.info(f"Analyzing risk for {customer.name}")

# GOOD: Logs only ID
logger.info(f"Analyzing risk for customer {customer.id}")
```

**Sanitize Data Before LLM:**
```python
def sanitize_customer_data(customer: dict) -> dict:
    """Remove PII before sending to LLM."""
    return {
        "id": customer["id"],  # UUID is OK
        "status": customer["status"],
        "account_age_days": calculate_age(customer["created_at"]),
        "engagement_score": customer["engagement_score"],
        # DO NOT include: name, email, phone, SSN, address
    }
```

### 2. Prompt Injection Prevention

**Validate User Inputs:**
```python
def validate_user_query(query: str) -> str:
    """Validate and sanitize user query."""
    # Length check
    if len(query) > 500:
        raise ValidationError("Query too long (max 500 chars)")

    # Detect suspicious patterns
    suspicious = [
        "ignore previous", "disregard instructions",
        "new instructions:", "system:", "</user>", "<system>"
    ]

    query_lower = query.lower()
    if any(pattern in query_lower for pattern in suspicious):
        raise ValidationError("Invalid query detected")

    # Escape special characters
    return escape_prompt_chars(query)
```

### 3. Output Sanitization

**Validate LLM Outputs:**
```python
def validate_risk_assessment(result: dict) -> dict:
    """Validate AI output structure."""
    # Check required fields
    if "risk_level" not in result:
        raise ValueError("Missing risk_level in AI response")

    # Validate risk level is allowed value
    if result["risk_level"] not in ["Low", "Medium", "High"]:
        raise ValueError(f"Invalid risk_level: {result['risk_level']}")

    # Validate confidence range
    if not (0.0 <= result.get("confidence", 0.0) <= 1.0):
        raise ValueError("Confidence must be between 0.0 and 1.0")

    # Sanitize text fields (prevent XSS)
    if "recommendations" in result:
        result["recommendations"] = [
            sanitize_text(rec) for rec in result["recommendations"]
        ]

    return result
```

### 4. Rate Limiting

**Implement Rate Limits:**
```python
from fastapi import HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/assess-customer-risk")
@limiter.limit("10/minute")  # 10 requests per minute per IP
async def assess_risk(request: RiskAssessmentRequest):
    try:
        result = await agent.assess_risk(request.customer_id)
        return result
    except RateLimitExceeded:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again in 60 seconds.",
            headers={"Retry-After": "60"}
        )
```

## Example Agent Implementation

`{PRODUCT_ROOT}/neuron/domain_agents/` is the target location for agent implementations. Populate with:
- Agent definition
- Prompt templates
- Tool implementations
- Testing strategy
- Integration with main app

**Integration Checklist:**
- [ ] API endpoint defined in FastAPI
- [ ] Request/response schemas documented
- [ ] Data fetching from backend implemented
- [ ] Service-to-service auth configured
- [ ] Error handling with fallbacks
- [ ] Logging all requests with metadata
- [ ] Metrics tracking (latency, cost, errors)
- [ ] Cost tracking per feature
- [ ] Rate limiting implemented
- [ ] PII sanitization before LLM calls
- [ ] Output validation and sanitization
- [ ] Unit tests for agent logic
- [ ] Integration tests with mock backend
- [ ] Evaluation tests for accuracy

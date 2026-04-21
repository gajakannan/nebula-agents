# AI Integration Patterns

**Purpose:** This document defines integration patterns for AI features in applications built with the agentic builder framework. It helps Product Managers, Architects, and Developers choose the right AI integration strategy based on their requirements.

**Last Updated:** 2026-02-07

---

## Overview

The framework supports three distinct AI integration patterns, each suited for different use cases:

1. **AI-Optional** - LLM calls embedded in backend services (no {PRODUCT_ROOT}/neuron/ layer)
2. **AI-Embedded** - Dedicated {PRODUCT_ROOT}/neuron/ layer accessed via backend proxy
3. **AI-Centric** - Full {PRODUCT_ROOT}/neuron/ intelligence layer with parallel access patterns

Choose the pattern that matches your:
- AI complexity and sophistication needs
- Team structure and skillsets
- Scalability and isolation requirements
- Cost and latency constraints

---

## Pattern 1: AI-Optional

### When to Use

Use this pattern when:
- AI features are **simple and limited** (e.g., single LLM API calls)
- You have **no dedicated AI engineering team**
- AI is **not a core differentiator** of your application
- You want to **minimize architectural complexity**
- AI usage is **low volume** (cost is manageable within backend budget)

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend ({PRODUCT_ROOT}/experience/)                │
│                     React + TypeScript                       │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP/REST
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                        Backend ({PRODUCT_ROOT}/engine/)                     │
│                       .NET + C# API                          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Business Services                                     │  │
│  │                                                       │  │
│  │  CustomerService                                     │  │
│  │    ├─ GetCustomer()                                  │  │
│  │    ├─ UpdateCustomer()                               │  │
│  │    └─ SuggestNextAction() ← LLM API call here       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Infrastructure                                        │  │
│  │   • PostgreSQL (data)                                │  │
│  │   • Keycloak (auth)                                  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                             │
                             ↓
                   ┌─────────────────┐
                   │     LLM API     │
                   └─────────────────┘
```

### Implementation Details

**Backend Integration:**
```csharp
// {PRODUCT_ROOT}/engine/Services/CustomerService.cs
public class CustomerService
{
    private readonly IGenericLLMClient _genericLlmClient;
    private readonly ICustomerRepository _repository;

    public async Task<string> SuggestNextActionAsync(Guid customerId)
    {
        var customer = await _repository.GetAsync(customerId);

        // Simple LLM call embedded in service
        var prompt = $@"
            Based on this customer data:
            - Name: {customer.Name}
            - Last Contact: {customer.LastContactDate}
            - Status: {customer.Status}

            Suggest the next best action for account management.
            ";

        var response = await _genericLlmClient.Messages.CreateAsync(
            model: "llm-model-4",
            max_tokens: 200,
            messages: new[] {
                new Message { Role = "user", Content = prompt }
            }
        );

        return response.Content[0].Text;
    }
}
```

**Directory Structure:**
```
project/
├── {PRODUCT_ROOT}/engine/               # Backend only
│   ├── Controllers/
│   ├── Services/
│   │   └── CustomerService.cs  ← LLM calls here
│   ├── Domain/
│   └── Infrastructure/
│       └── LLM/
│           └── LLMClient.cs  ← SDK wrapper
├── {PRODUCT_ROOT}/experience/           # Frontend
└── {PRODUCT_ROOT}/planning-mds/
```

### Advantages

✅ **Simplicity** - No separate AI layer to manage
✅ **Minimal overhead** - Single codebase, single deployment
✅ **Quick to implement** - Backend developer can handle it
✅ **Easy debugging** - All logic in one place

### Disadvantages

❌ **Limited scalability** - AI logic coupled with business logic
❌ **Hard to test AI independently** - No isolation
❌ **No reusability** - AI logic duplicated across services
❌ **Cost tracking difficult** - Mixed with backend metrics
❌ **Not suitable for complex AI** - No room for agentic workflows, MCP servers, etc.

### Agent Involvement

- **Backend Developer** - Implements LLM integration
- **AI Engineer** - NOT NEEDED (Backend Dev handles simple LLM calls)
- **Architect** - Validates integration points and error handling

### When to Graduate to Pattern 2

Move to AI-Embedded when:
- AI features become more complex (multi-step workflows)
- You hire a dedicated AI Engineer
- You need to reuse AI logic across multiple backend services
- AI cost becomes significant and needs dedicated tracking
- You need to test AI behavior independently

---

## Pattern 2: AI-Embedded

### When to Use

Use this pattern when:
- AI features are **moderately complex** (multi-step workflows, prompt management)
- You have **dedicated AI engineering capability**
- AI is **a key feature** but not the primary application value
- You want **clear separation** between business logic and AI logic
- You need **independent scaling and testing** of AI components

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend ({PRODUCT_ROOT}/experience/)                │
│                     React + TypeScript                       │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP/REST
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                        Backend ({PRODUCT_ROOT}/engine/)                     │
│                       .NET + C# API                          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Business Services                                     │  │
│  │                                                       │  │
│  │  CustomerService                                     │  │
│  │    ├─ GetCustomer()                                  │  │
│  │    ├─ UpdateCustomer()                               │  │
│  │    └─ SuggestNextAction()                            │  │
│  │          ↓ HTTP (internal)                           │  │
│  └──────────┼───────────────────────────────────────────┘  │
│             │                                                │
│  ┌──────────▼───────────────────────────────────────────┐  │
│  │ AI Proxy Service                                      │  │
│  │   • Routes requests to {PRODUCT_ROOT}/neuron/                       │  │
│  │   • Handles auth/rate limiting                       │  │
│  │   • Aggregates AI responses                          │  │
│  └──────────┬───────────────────────────────────────────┘  │
└─────────────┼────────────────────────────────────────────────┘
              │ HTTP (internal service call)
              ↓
┌─────────────────────────────────────────────────────────────┐
│                     Intelligence ({PRODUCT_ROOT}/neuron/)                   │
│                        Python + FastAPI                      │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Domain Agents                                         │  │
│  │   • CustomerAnalysisAgent                            │  │
│  │   • RecommendationAgent                              │  │
│  │   • RiskAssessmentAgent                              │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Workflows                                             │  │
│  │   • Multi-step agent orchestration                   │  │
│  │   • Prompt management                                │  │
│  │   • Model routing logic                              │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ API Endpoints (FastAPI)                               │  │
│  │   POST /analyze-customer                             │  │
│  │   POST /suggest-next-action                          │  │
│  │   POST /assess-risk                                  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ↓
                   ┌──────────────────────┐
                   │       LLM API        │
                   └──────────────────────┘
```

### Implementation Details

**Backend Proxy ({PRODUCT_ROOT}/engine/):**
```csharp
// {PRODUCT_ROOT}/engine/Services/AiProxyService.cs
public class AiProxyService
{
    private readonly HttpClient _neuronClient;
    private readonly IAuthorizationService _authz;

    public async Task<NextActionSuggestion> SuggestNextActionAsync(
        Guid customerId,
        ClaimsPrincipal user)
    {
        // Authorize request
        if (!await _authz.CanAccessAiFeatures(user))
            throw new UnauthorizedException();

        // Forward to {PRODUCT_ROOT}/neuron/ with rate limiting
        var request = new { customer_id = customerId };
        var response = await _neuronClient.PostAsJsonAsync(
            "http://neuron:8000/suggest-next-action",
            request
        );

        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<NextActionSuggestion>();
    }
}
```

**AI Layer ({PRODUCT_ROOT}/neuron/):**
```python
# {PRODUCT_ROOT}/neuron/api/routes.py
from fastapi import APIRouter, HTTPException
from neuron.domain_agents.recommendation_agent import RecommendationAgent

router = APIRouter()
agent = RecommendationAgent()

@router.post("/suggest-next-action")
async def suggest_next_action(request: NextActionRequest):
    """Suggest next best action for a customer."""
    try:
        # Multi-step workflow
        customer_data = await fetch_customer_data(request.customer_id)
        analysis = await agent.analyze_customer(customer_data)
        suggestion = await agent.generate_recommendation(analysis)

        # Track usage
        await track_ai_usage(
            endpoint="suggest-next-action",
            model=agent.model_name,
            tokens=suggestion.token_count
        )

        return suggestion
    except Exception as e:
        logger.error(f"AI suggestion failed: {e}")
        raise HTTPException(status_code=500, detail="AI processing failed")
```

**Directory Structure:**
```
project/
├── {PRODUCT_ROOT}/engine/               # Backend (C# / .NET)
│   ├── Controllers/
│   ├── Services/
│   │   └── AiProxyService.cs  ← Proxy to {PRODUCT_ROOT}/neuron/
│   └── Infrastructure/
│       └── HttpClients/
│           └── NeuronClient.cs
├── {PRODUCT_ROOT}/neuron/               # AI Layer (Python)
│   ├── api/
│   │   └── routes.py     ← FastAPI endpoints
│   ├── domain_agents/
│   │   ├── recommendation_agent.py
│   │   └── risk_agent.py
│   ├── workflows/
│   ├── prompts/
│   ├── models/
│   └── config/
├── {PRODUCT_ROOT}/experience/           # Frontend
└── {PRODUCT_ROOT}/planning-mds/
```

### Advantages

✅ **Clear separation** - AI logic isolated from business logic
✅ **Independent scaling** - Scale {PRODUCT_ROOT}/neuron/ separately from {PRODUCT_ROOT}/engine/
✅ **Testability** - Test AI agents independently
✅ **Reusability** - AI agents can be called from multiple backend services
✅ **Cost tracking** - Dedicated AI metrics and monitoring
✅ **Technology flexibility** - Python AI stack, .NET backend stack
✅ **Security boundary** - Backend controls access to AI features

### Disadvantages

⚠️ **Added complexity** - Two services to deploy and manage
⚠️ **Latency overhead** - Extra HTTP hop ({PRODUCT_ROOT}/engine/ → {PRODUCT_ROOT}/neuron/)
⚠️ **Network dependency** - AI features fail if {PRODUCT_ROOT}/neuron/ is down
⚠️ **Authentication complexity** - Need service-to-service auth

### Agent Involvement

- **Architect** - Defines {PRODUCT_ROOT}/engine/↔{PRODUCT_ROOT}/neuron/ API contract
- **Backend Developer** - Implements proxy service and integration
- **AI Engineer** - Implements {PRODUCT_ROOT}/neuron/ agents, workflows, and API
- **DevOps** - Deploys and configures both services
- **Security** - Reviews service-to-service authentication

### API Contract Between {PRODUCT_ROOT}/engine/ and {PRODUCT_ROOT}/neuron/

**Contract Location:** `{PRODUCT_ROOT}/planning-mds/api/neuron-api.yaml` (OpenAPI spec)

**Example Contract:**
```yaml
POST /suggest-next-action
Request:
  customer_id: uuid
  context: object (optional)
Response:
  suggestion: string
  confidence: float (0-1)
  reasoning: string
  token_count: int
  cost_usd: float
```

**Error Handling:**
- Backend MUST handle {PRODUCT_ROOT}/neuron/ failures gracefully
- Provide fallback behavior if AI is unavailable
- Log failures for debugging
- Return user-friendly error messages

### When to Graduate to Pattern 3

Move to AI-Centric when:
- AI features become the **primary application value**
- You need **real-time LLM interactions** (streaming, chat)
- Frontend requires **direct AI access** (can't wait for backend proxy)
- You implement **MCP servers** for external tool integration
- You need **advanced AI patterns** (multi-agent collaboration, RAG)

---

## Pattern 3: AI-Centric

### When to Use

Use this pattern when:
- AI features are **complex and central** to application value
- You need **real-time LLM streaming** to frontend (chat, live suggestions)
- You implement **MCP (Model Context Protocol)** servers for external tool access
- You have **multiple AI integration points** (not just backend → AI)
- You need **maximum AI flexibility** and sophistication

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend ({PRODUCT_ROOT}/experience/)                │
│                     React + TypeScript                       │
│                                                              │
│  ┌───────────────────┐        ┌──────────────────────────┐ │
│  │ Business Features │        │ AI Features              │ │
│  │ (CRUD, workflows) │        │ (Chat, streaming)        │ │
│  └─────────┬─────────┘        └──────────┬───────────────┘ │
└────────────┼────────────────────────────┼──────────────────┘
             │                             │
             │ HTTP/REST                   │ WebSocket/SSE
             ↓                             ↓
┌────────────────────────┐    ┌───────────────────────────────┐
│   Backend ({PRODUCT_ROOT}/engine/)    │    │   Intelligence ({PRODUCT_ROOT}/neuron/)      │
│   .NET + C# API        │    │   Python + FastAPI            │
│                        │    │                               │
│  Business Services     │    │  ┌─────────────────────────┐ │
│  Data Access           │    │  │ MCP Servers             │ │
│  Workflows             │    │  │  • CRM Data Access      │ │
│  Authorization         │    │  │  • Document Retrieval   │ │
│                        │    │  │  • External Tools       │ │
│  ┌──────────────────┐ │    │  └─────────────────────────┘ │
│  │ Data API         │ │    │                               │
│  │ (for {PRODUCT_ROOT}/neuron/)    │ │    │  ┌─────────────────────────┐ │
│  └─────────┬────────┘ │    │  │ AI Agents               │ │
└────────────┼───────────┘    │  │  • Conversational UI    │ │
             │                │  │  • Recommendation       │ │
             │ HTTP (MCP)     │  │  • Analysis & Insights  │ │
             └────────────────┼──│  • RAG Pipelines        │ │
                              │  └─────────────────────────┘ │
                              │                               │
                              │  ┌─────────────────────────┐ │
                              │  │ Streaming API           │ │
                              │  │  • WebSocket endpoints  │ │
                              │  │  • SSE endpoints        │ │
                              │  └─────────────────────────┘ │
                              └───────────────┬───────────────┘
                                              │
                                              ↓
                                   ┌──────────────────────┐
                                   │      LLM API         │
                                   │  Vector DB (optional)│
                                   └──────────────────────┘
```

### Implementation Details

**Frontend Direct AI Access:**
```typescript
// {PRODUCT_ROOT}/experience/src/services/aiService.ts
export class AiService {
  private neuronWs: WebSocket;

  async streamChatResponse(message: string): Promise<AsyncIterable<string>> {
    // Direct WebSocket connection to {PRODUCT_ROOT}/neuron/
    this.neuronWs = new WebSocket('ws://neuron:8000/chat/stream');

    this.neuronWs.send(JSON.stringify({
      message,
      auth_token: this.authToken
    }));

    // Stream response chunks
    return this.streamResponses();
  }
}
```

**MCP Server ({PRODUCT_ROOT}/neuron/):**
```python
# {PRODUCT_ROOT}/neuron/mcp/crm_data_server.py
from mcp import Server, Tool, Resource

server = Server("crm-data-mcp")

@server.tool()
async def get_customer(customer_id: str) -> dict:
    """Fetch customer data from CRM backend."""
    # Call {PRODUCT_ROOT}/engine/ API to get customer data
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://engine:5000/api/internal/customers/{customer_id}",
            headers={"Authorization": f"Bearer {service_token}"}
        )
        return response.json()

@server.tool()
async def search_customers(query: str) -> list[dict]:
    """Search for customers matching query."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://engine:5000/api/internal/customers/search",
            params={"q": query},
            headers={"Authorization": f"Bearer {service_token}"}
        )
        return response.json()
```

**Streaming AI Chat ({PRODUCT_ROOT}/neuron/):**
```python
# {PRODUCT_ROOT}/neuron/api/streaming.py
from fastapi import WebSocket
from llmmodel import AsyncLlmModel

@router.websocket("/chat/stream")
async def chat_stream(websocket: WebSocket):
    await websocket.accept()

    # Authenticate connection
    auth_token = await websocket.receive_text()
    if not await validate_token(auth_token):
        await websocket.close()
        return

    # Stream LLM response
    async with AsyncLlmModel() as client:
        async with client.messages.stream(
            model="llm-model",
            max_tokens=1024,
            messages=[{"role": "user", "content": "..."}]
        ) as stream:
            async for text in stream.text_stream:
                await websocket.send_text(text)
```

**Directory Structure:**
```
project/
├── {PRODUCT_ROOT}/engine/               # Backend (C# / .NET)
│   ├── Controllers/
│   │   └── InternalController.cs  ← API for {PRODUCT_ROOT}/neuron/ MCP
│   ├── Services/
│   └── Authorization/
│       └── ServiceAuthHandler.cs  ← Service-to-service auth
├── {PRODUCT_ROOT}/neuron/               # AI Layer (Python)
│   ├── api/
│   │   ├── routes.py
│   │   └── streaming.py  ← WebSocket/SSE endpoints
│   ├── mcp/
│   │   ├── crm_data_server.py
│   │   └── document_server.py
│   ├── domain_agents/
│   │   ├── conversational_agent.py
│   │   ├── recommendation_agent.py
│   │   └── rag_agent.py
│   ├── workflows/
│   ├── prompts/
│   ├── models/
│   └── config/
├── {PRODUCT_ROOT}/experience/           # Frontend
│   └── src/
│       ├── services/
│       │   ├── apiService.ts      ← HTTP to {PRODUCT_ROOT}/engine/
│       │   └── aiService.ts       ← WebSocket to {PRODUCT_ROOT}/neuron/
│       └── components/
│           └── AiChat.tsx         ← Streaming AI chat UI
└── {PRODUCT_ROOT}/planning-mds/
```

### Advantages

✅ **Maximum AI sophistication** - Full agentic workflows, MCP, RAG
✅ **Real-time streaming** - Low-latency LLM responses to frontend
✅ **MCP tool integration** - AI agents can access CRM data via MCP
✅ **Parallel data access** - Frontend calls {PRODUCT_ROOT}/engine/ and {PRODUCT_ROOT}/neuron/ independently
✅ **Advanced patterns** - Multi-agent collaboration, vector search, etc.
✅ **AI-first UX** - Native chat interfaces, live suggestions

### Disadvantages

⚠️ **High complexity** - Three-tier architecture with multiple integration points
⚠️ **Security challenges** - Frontend-to-neuron auth, service-to-service auth
⚠️ **Increased latency** - MCP calls from {PRODUCT_ROOT}/neuron/ back to {PRODUCT_ROOT}/engine/
⚠️ **DevOps overhead** - WebSocket infrastructure, monitoring, scaling
⚠️ **Cost complexity** - AI usage from multiple sources

### Agent Involvement

- **Architect** - Defines all integration contracts ({PRODUCT_ROOT}/engine/↔{PRODUCT_ROOT}/neuron/, {PRODUCT_ROOT}/experience/↔{PRODUCT_ROOT}/neuron/, MCP)
- **Backend Developer** - Implements internal API for MCP server, service auth
- **Frontend Developer** - Implements WebSocket/SSE integration for streaming AI
- **AI Engineer** - Implements MCP servers, streaming endpoints, advanced agents
- **DevOps** - Deploys WebSocket infrastructure, manages service mesh
- **Security** - Reviews all authentication flows, rate limiting, abuse prevention

### MCP Integration Contract

**MCP Server Specification:** `{PRODUCT_ROOT}/planning-mds/api/mcp-servers.yaml`

**Example MCP Server:**
```yaml
server: crm-data-mcp
tools:
  - name: get_customer
    description: Fetch customer by ID
    parameters:
      customer_id: string (uuid)
    returns: Customer object

  - name: search_customers
    description: Search customers by query
    parameters:
      query: string
      limit: int (optional, default 10)
    returns: Customer[]

authentication:
  type: bearer_token
  token_endpoint: http://engine:5000/api/auth/service-token
  scopes: [crm.read, crm.write]
```

**Security:**
- MCP servers MUST authenticate with {PRODUCT_ROOT}/engine/ using service tokens
- Tokens scoped to specific permissions (crm.read, crm.write, etc.)
- Rate limiting on MCP endpoints
- Audit log of all MCP tool calls

---

## Decision Matrix

### Choose AI-Optional if:
- [ ] AI features are simple (single LLM API calls)
- [ ] No dedicated AI Engineer on team
- [ ] AI is not a differentiator
- [ ] Low AI usage volume
- [ ] Want minimal complexity

### Choose AI-Embedded if:
- [ ] AI features are moderately complex (workflows, prompt management)
- [ ] Have dedicated AI Engineer
- [ ] AI is a key feature
- [ ] Need independent testing and scaling
- [ ] Want clear separation of concerns

### Choose AI-Centric if:
- [ ] AI features are complex and central to value
- [ ] Need real-time streaming (chat, live suggestions)
- [ ] Implement MCP servers
- [ ] Multiple AI integration points
- [ ] Maximum AI flexibility required

---

## Migration Path

### AI-Optional → AI-Embedded

**Steps:**
1. Create `{PRODUCT_ROOT}/neuron/` directory with FastAPI structure
2. Extract LLM logic from backend services into {PRODUCT_ROOT}/neuron/ agents
3. Implement proxy service in {PRODUCT_ROOT}/engine/
4. Define API contract between {PRODUCT_ROOT}/engine/ and {PRODUCT_ROOT}/neuron/
5. Deploy {PRODUCT_ROOT}/neuron/ as separate service
6. Update {PRODUCT_ROOT}/engine/ to call {PRODUCT_ROOT}/neuron/ instead of LLM provider API directly

**Effort:** 1-2 weeks

---

### AI-Embedded → AI-Centric

**Steps:**
1. Add WebSocket/SSE endpoints to {PRODUCT_ROOT}/neuron/
2. Implement MCP servers in {PRODUCT_ROOT}/neuron/mcp/
3. Create internal API in {PRODUCT_ROOT}/engine/ for MCP server data access
4. Update frontend to call {PRODUCT_ROOT}/neuron/ directly for streaming features
5. Implement service-to-service authentication
6. Set up WebSocket infrastructure (load balancing, monitoring)

**Effort:** 2-4 weeks

---

## Pattern Comparison Table

| Aspect | AI-Optional | AI-Embedded | AI-Centric |
|--------|-------------|-------------|------------|
| **Complexity** | Low | Medium | High |
| **AI Sophistication** | Simple calls | Workflows | Advanced (MCP, RAG) |
| **Deployment Units** | 2 (engine + experience) | 3 (engine + neuron + experience) | 3 (with MCP/streaming) |
| **Team Size** | 2-3 (no AI Engineer) | 3-5 (1 AI Engineer) | 5+ (2+ AI Engineers) |
| **Latency** | Low | Medium (proxy hop) | Low-Medium (streaming) |
| **Testability** | Medium | High | High |
| **Cost Tracking** | Mixed with backend | Dedicated | Dedicated + granular |
| **Security Boundary** | Backend controls all | Backend proxies AI | Frontend + Backend + MCP |
| **Scalability** | Limited | Independent | Maximum |
| **Best For** | MVP, simple features | Production apps with AI | AI-native applications |

---

## Vendor Selection Guide

This framework is **vendor-agnostic** and works with any LLM provider. Below is guidance for adapting these patterns to specific providers.

### Supported Provider Types

**Cloud API Providers:**
- Anthropic (Claude)
- OpenAI (GPT-4, GPT-3.5)
- Azure OpenAI
- Google Vertex AI (Gemini)
- Cohere
- AI21 Labs

**Self-Hosted / Local:**
- Ollama (local inference)
- vLLM (high-throughput serving)
- Text Generation Inference (HuggingFace)
- LM Studio

**Framework Support:**
- LangChain (multi-provider abstraction)
- LlamaIndex (data framework)
- Haystack (NLP pipelines)

### Model Tier Mapping

The patterns reference generic model tiers. Map them to your provider:

| Generic Tier | Use Case | Anthropic | OpenAI | Azure OpenAI | Local (Ollama) |
|--------------|----------|-----------|--------|--------------|----------------|
| **llm-lightweight** | Fast, simple tasks | Claude 3.5 Haiku | GPT-4o Mini | gpt-4o-mini | llama3.2 (3B) |
| **llm-balanced** | Default choice | Claude 3.5 Sonnet | GPT-4o | gpt-4o | llama3.1 (8B) |
| **llm-advanced** | Complex reasoning | Claude Opus 4 | o1 | o1 | llama3.1 (70B) |

### Provider Adaptation Examples

#### Example 1: Anthropic (Cloud)

**SDK:** `anthropic` (Python), `@anthropic-ai/sdk` (TypeScript)

```python
# {PRODUCT_ROOT}/neuron/models/llm_client.py
from anthropic import AsyncAnthropic

class LLMClient:
    def __init__(self):
        self.client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    async def generate(self, prompt: str, model_tier: str = "balanced"):
        model_map = {
            "lightweight": "claude-3-5-haiku-20241022",
            "balanced": "claude-3-5-sonnet-20241022",
            "advanced": "claude-opus-4-20250514"
        }

        response = await self.client.messages.create(
            model=model_map[model_tier],
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text
```

**Streaming:**
```python
async with self.client.messages.stream(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[{"role": "user", "content": prompt}]
) as stream:
    async for text in stream.text_stream:
        yield text
```

---

#### Example 2: OpenAI (Cloud)

**SDK:** `openai` (Python), `openai` (TypeScript)

```python
# {PRODUCT_ROOT}/neuron/models/llm_client.py
from openai import AsyncOpenAI

class LLMClient:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def generate(self, prompt: str, model_tier: str = "balanced"):
        model_map = {
            "lightweight": "gpt-4o-mini",
            "balanced": "gpt-4o",
            "advanced": "o1"
        }

        response = await self.client.chat.completions.create(
            model=model_map[model_tier],
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content
```

**Streaming:**
```python
stream = await self.client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}],
    stream=True
)

async for chunk in stream:
    if chunk.choices[0].delta.content:
        yield chunk.choices[0].delta.content
```

---

#### Example 3: Azure OpenAI

**SDK:** `openai` with Azure configuration

```python
# {PRODUCT_ROOT}/neuron/models/llm_client.py
from openai import AsyncAzureOpenAI

class LLMClient:
    def __init__(self):
        self.client = AsyncAzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-02-15-preview",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )

    async def generate(self, prompt: str, model_tier: str = "balanced"):
        # Azure uses deployment names, not model names
        deployment_map = {
            "lightweight": "gpt-4o-mini-deployment",
            "balanced": "gpt-4o-deployment",
            "advanced": "o1-deployment"
        }

        response = await self.client.chat.completions.create(
            model=deployment_map[model_tier],  # deployment name
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content
```

---

#### Example 4: Ollama (Local)

**SDK:** `ollama` (Python), HTTP API

```python
# {PRODUCT_ROOT}/neuron/models/llm_client.py
import ollama

class LLMClient:
    def __init__(self):
        self.client = ollama.AsyncClient(host=os.getenv("OLLAMA_HOST", "http://localhost:11434"))

    async def generate(self, prompt: str, model_tier: str = "balanced"):
        model_map = {
            "lightweight": "llama3.2:3b",
            "balanced": "llama3.1:8b",
            "advanced": "llama3.1:70b"
        }

        response = await self.client.chat(
            model=model_map[model_tier],
            messages=[{"role": "user", "content": prompt}]
        )

        return response['message']['content']
```

**Streaming:**
```python
stream = await self.client.chat(
    model="llama3.1:8b",
    messages=[{"role": "user", "content": prompt}],
    stream=True
)

async for chunk in stream:
    if 'message' in chunk and 'content' in chunk['message']:
        yield chunk['message']['content']
```

---

#### Example 5: Multi-Provider Abstraction (LangChain)

**SDK:** `langchain`, `langchain-anthropic`, `langchain-openai`

```python
# {PRODUCT_ROOT}/neuron/models/llm_client.py
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

class LLMClient:
    def __init__(self, provider: str = "anthropic"):
        if provider == "anthropic":
            self.client = ChatAnthropic(model="claude-3-5-sonnet-20241022")
        elif provider == "openai":
            self.client = ChatOpenAI(model="gpt-4o")
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    async def generate(self, prompt: str):
        messages = [HumanMessage(content=prompt)]
        response = await self.client.ainvoke(messages)
        return response.content
```

---

### Cost Considerations by Provider

**Cloud Provider Pricing (Approximate, as of 2026):**

| Provider | Lightweight | Balanced | Advanced |
|----------|-------------|----------|----------|
| **Anthropic Claude** | ~$0.001/req | ~$0.005/req | ~$0.02/req |
| **OpenAI** | ~$0.0005/req | ~$0.003/req | ~$0.015/req |
| **Azure OpenAI** | Similar to OpenAI | Similar to OpenAI | Similar to OpenAI |
| **Google Vertex** | ~$0.0008/req | ~$0.004/req | ~$0.018/req |

**Local Hosting Costs:**
- **Ollama (lightweight)**: $0/req (hardware cost only)
- **Ollama (advanced)**: $0/req (requires GPU, higher hardware cost)
- **Tradeoff**: No per-request cost, but higher infrastructure cost

### Selecting Your Provider

**Choose Cloud (Anthropic/OpenAI/Azure) if:**
- ✅ You need best-in-class model quality
- ✅ You want zero infrastructure management
- ✅ Your usage is moderate (< 1M tokens/day)
- ✅ You need rapid iteration and experimentation

**Choose Local (Ollama/vLLM) if:**
- ✅ You have high-volume usage (> 10M tokens/day)
- ✅ You need data sovereignty / on-premise deployment
- ✅ You have GPU infrastructure available
- ✅ You can tolerate slightly lower quality for cost savings

**Choose Multi-Provider Abstraction (LangChain) if:**
- ✅ You want flexibility to switch providers
- ✅ You need to support multiple providers simultaneously
- ✅ You want to avoid vendor lock-in
- ✅ You're willing to accept abstraction overhead

---

### Configuration Pattern

**Recommended: Environment-Based Configuration**

```python
# {PRODUCT_ROOT}/neuron/config/llm_config.py
import os
from enum import Enum

class LLMProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    AZURE = "azure"
    OLLAMA = "ollama"

class LLMConfig:
    def __init__(self):
        self.provider = LLMProvider(os.getenv("LLM_PROVIDER", "anthropic"))
        self.api_key = os.getenv(f"{self.provider.upper()}_API_KEY")
        self.endpoint = os.getenv(f"{self.provider.upper()}_ENDPOINT")

        # Model tier mappings per provider
        self.model_tiers = {
            LLMProvider.ANTHROPIC: {
                "lightweight": "claude-3-5-haiku-20241022",
                "balanced": "claude-3-5-sonnet-20241022",
                "advanced": "claude-opus-4-20250514"
            },
            LLMProvider.OPENAI: {
                "lightweight": "gpt-4o-mini",
                "balanced": "gpt-4o",
                "advanced": "o1"
            },
            LLMProvider.OLLAMA: {
                "lightweight": "llama3.2:3b",
                "balanced": "llama3.1:8b",
                "advanced": "llama3.1:70b"
            }
        }

    def get_model(self, tier: str) -> str:
        return self.model_tiers[self.provider][tier]
```

**Usage:**
```python
# Set environment variables
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-...

config = LLMConfig()
model = config.get_model("balanced")  # Returns "claude-3-5-sonnet-20241022"
```

---

## References

### Related Documents
- `agents/ai-engineer/SKILL.md` - AI Engineer responsibilities
- `agents/architect/references/ai-architecture-patterns.md` - Architect AI patterns
- `{PRODUCT_ROOT}/planning-mds/examples/stories/ai-story-example.md` - Example AI feature story

### External Resources

**Framework Documentation:**
- [Model Context Protocol (MCP) Specification](https://spec.modelcontextprotocol.io/)
- [FastAPI WebSocket Guide](https://fastapi.tiangolo.com/advanced/websockets/)
- [LangChain Documentation](https://python.langchain.com/)
- [LlamaIndex Documentation](https://docs.llamaindex.ai/)

**Provider Documentation:**
- [Anthropic API Docs](https://docs.anthropic.com/)
- [OpenAI API Docs](https://platform.openai.com/docs/)
- [Azure OpenAI Docs](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [Google Vertex AI Docs](https://cloud.google.com/vertex-ai/docs)
- [Ollama Documentation](https://ollama.ai/docs)

**Open Source Tools:**
- [vLLM (High-Performance Inference)](https://github.com/vllm-project/vllm)
- [Text Generation Inference](https://github.com/huggingface/text-generation-inference)
- [LiteLLM (Provider Abstraction)](https://github.com/BerriAI/litellm)

---

**Questions?** Discuss with your Architect or reference the AI integration examples in `{PRODUCT_ROOT}/planning-mds/examples/`.

# Deployment Architecture

> **Template:** Use this template to document deployment architecture for your application.
> **Location:** Copy to `{PRODUCT_ROOT}/planning-mds/architecture/deployment-architecture.md`
> **Created by:** DevOps agent during Phase 3 of build action
> **Purpose:** Single source of truth for deployment configuration

---

## Architecture Pattern

**Pattern Type:** [Select: API-Only / 3-Tier / AI-Enabled 3-Tier / Microservices]

**Description:** [Brief description of the deployment architecture]

**Rationale:** [Why this pattern was chosen - reference code inspection findings]

**Reference:** `agents/devops/references/containerization-guide.md` - [Section X.X Pattern Name]

---

## Code Inspection Summary

### Services Detected

#### 1. Backend API ({PRODUCT_ROOT}/engine/)
- **Language:** [e.g., C# / .NET 10]
- **Framework:** [e.g., ASP.NET Core]
- **Database:** [e.g., PostgreSQL]
- **Authentication:** [e.g., Keycloak JWT]
- **Port:** [e.g., 5000]
- **Dependencies:** [List NuGet packages or key dependencies]
- **Configuration Files:** [e.g., appsettings.json, launchSettings.json]

#### 2. Frontend ({PRODUCT_ROOT}/experience/)
- **Language:** [e.g., TypeScript / React 18]
- **Build Tool:** [e.g., Vite]
- **Runtime:** [e.g., Static files served by Nginx]
- **Port:** [e.g., 3000 (dev), 80 (prod)]
- **API Endpoint:** [e.g., http://api:5000]
- **Configuration Files:** [e.g., vite.config.ts, .env]

#### 3. AI Layer ({PRODUCT_ROOT}/neuron/)
**[If {PRODUCT_ROOT}/neuron/ exists]**
- **Language:** [e.g., Python 3.11]
- **Framework:** [e.g., FastAPI]
- **Port:** [e.g., 8000]
- **LLM Provider:** [e.g., Detected from requirements.txt]
- **MCP Servers:** [Yes/No - list if yes]
- **Dependencies:** [List from requirements.txt]
- **Integration:** [Calls {PRODUCT_ROOT}/engine/ internal API]

---

### Infrastructure Requirements

**Database:**
- **Type:** [PostgreSQL / MySQL / MongoDB / SQLite]
- **Version:** [e.g., PostgreSQL 16]
- **Storage:** [Persistent volume required]
- **Port:** [e.g., 5432]

**Caching:** [Redis / Memcached / None]
**Message Queue:** [RabbitMQ / Kafka / None]
**Workflow Engine:** [Temporal / None]
**Additional Services:** [List any other detected services]

---

### Service Dependencies

```
[Draw ASCII diagram showing service dependencies]

Example:
┌──────────────┐
│   Frontend   │ :3000
│ ({PRODUCT_ROOT}/experience/)│
└──────┬───────┘
       │
       ↓
┌──────────────┐     ┌────────────┐
│ Backend API  │<────│ AI Layer   │ :8000
│  ({PRODUCT_ROOT}/engine/)   │     │  ({PRODUCT_ROOT}/neuron/) │
│    :5000     │     └────────────┘
└──────┬───────┘
       │
       ↓
┌──────────────┐
│  PostgreSQL  │ :5432
└──────────────┘
```

**Dependency List:**
- `{PRODUCT_ROOT}/experience/` → `{PRODUCT_ROOT}/engine/` (API calls)
- `{PRODUCT_ROOT}/neuron/` → `{PRODUCT_ROOT}/engine/` (internal API for data access)
- `{PRODUCT_ROOT}/engine/` → `postgres` (database connection)

---

## Service Specifications

### Database Service

```yaml
Service Name: postgres
Image: postgres:16
Persistent Storage: Required
  - Volume: postgres_data
  - Mount: /var/lib/postgresql/data

Ports:
  - Internal: 5432
  - External: 5432 (dev only, not exposed in production)

Environment Variables:
  - POSTGRES_DB: [Database name]
  - POSTGRES_USER: [Database user]
  - POSTGRES_PASSWORD: [Secret - from env or vault]

Health Check:
  - Command: pg_isready -U ${POSTGRES_USER}
  - Interval: 10s
  - Timeout: 5s
  - Retries: 5

Initialization:
  - Script: [If init scripts needed, specify location]
```

---

### Backend API Service ({PRODUCT_ROOT}/engine/)

```yaml
Service Name: api
Build:
  - Context: ./engine
  - Dockerfile: ./engine/Dockerfile (to be created)
  - Multi-stage: Yes (build + runtime)

Runtime:
  - Base Image: [e.g., mcr.microsoft.com/dotnet/aspnet:10.0]
  - Working Directory: /app

Ports:
  - Internal: 5000
  - External: 5000:5000

Dependencies:
  - postgres (wait for healthy)

Environment Variables:
  - DATABASE_URL: Connection string to postgres
  - ASPNETCORE_ENVIRONMENT: [Development / Staging / Production]
  - KEYCLOAK_URL: [Auth provider URL]
  - JWT_SECRET: [Secret - from env or vault]
  - [List all detected env vars]

Health Check:
  - Endpoint: /health or /api/health
  - Method: GET
  - Expected Status: 200
  - Interval: 30s

Restart Policy: unless-stopped

Resource Limits: [Optional]
  - CPU: [e.g., 1.0]
  - Memory: [e.g., 512M]
```

---

### Frontend Service ({PRODUCT_ROOT}/experience/)

```yaml
Service Name: web
Build:
  - Context: ./experience
  - Dockerfile: ./experience/Dockerfile (multi-stage: node + nginx)
  - Stage 1: Node 20 (build)
  - Stage 2: Nginx alpine (runtime)

Runtime:
  - Base Image: nginx:alpine
  - Static Files: /usr/share/nginx/html
  - Config: Custom nginx.conf for SPA routing

Ports:
  - Development: 3000:3000
  - Production: 80:80

Dependencies:
  - api (must be running for API calls)

Environment Variables:
  - API_URL: [URL to backend API]
  - [Build-time env vars from .env]

Health Check:
  - Endpoint: /
  - Method: GET
  - Expected Status: 200

Restart Policy: unless-stopped
```

---

### AI Layer Service ({PRODUCT_ROOT}/neuron/)

**[Only if {PRODUCT_ROOT}/neuron/ exists]**

```yaml
Service Name: neuron
Build:
  - Context: ./neuron
  - Dockerfile: ./neuron/Dockerfile
  - Base Image: python:3.11-slim

Runtime:
  - Python Version: 3.11
  - Framework: FastAPI + Uvicorn

Ports:
  - Internal: 8000
  - External: 8000:8000

Dependencies:
  - api (calls internal API for data)

Environment Variables:
  - LLM_PROVIDER: [anthropic / openai / azure / ollama]
  - LLM_API_KEY: [Secret - from env or vault]
  - ENGINE_INTERNAL_API_URL: http://api:5000/api/internal
  - [Additional LLM config vars]

Health Check:
  - Endpoint: /health
  - Method: GET
  - Expected Status: 200

Restart Policy: unless-stopped

Resource Limits: [Optional - AI workloads may need more]
  - CPU: [e.g., 2.0]
  - Memory: [e.g., 1G]
```

---

## Network Architecture

### Network Topology

```
┌────────────────────────────────────────────────┐
│             Docker Network (bridge)            │
│                                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │   web    │  │   api    │  │  neuron  │    │
│  │  :3000   │  │  :5000   │  │  :8000   │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │             │               │          │
│       └─────────────┴───────────────┘          │
│                     │                          │
│              ┌──────┴─────┐                   │
│              │  postgres  │                   │
│              │   :5432    │                   │
│              └────────────┘                   │
└────────────────────────────────────────────────┘
         │              │              │
         ↓              ↓              ↓
    [Host:3000]   [Host:5000]   [Host:8000]
```

### Communication Patterns

**External → Frontend:**
- Browser → http://localhost:3000 (dev) or https://app.domain.com (prod)

**Frontend → Backend:**
- HTTP requests from React app → http://api:5000 (container) or http://localhost:5000 (dev)

**Frontend → AI Layer (if AI-Centric pattern):**
- WebSocket for streaming → ws://neuron:8000/chat/stream

**Backend → Database:**
- TCP connection → postgres:5432

**AI Layer → Backend:**
- Internal API calls → http://api:5000/api/internal

---

## Environment Variables

### Database Variables
```bash
POSTGRES_DB=<database_name>
POSTGRES_USER=<db_user>
POSTGRES_PASSWORD=<secret>
DATABASE_URL=postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
```

### Application Variables
```bash
# Backend ({PRODUCT_ROOT}/engine/)
ASPNETCORE_ENVIRONMENT=Development|Staging|Production
ASPNETCORE_URLS=http://+:5000

# Frontend ({PRODUCT_ROOT}/experience/)
API_URL=http://localhost:5000  # Dev
# API_URL=https://api.domain.com  # Prod

# Node
NODE_ENV=development|production
```

### Authentication Variables
```bash
KEYCLOAK_URL=http://keycloak:8080
JWT_SECRET=<long_random_secret_string>
JWT_ISSUER=<issuer>
JWT_AUDIENCE=<audience>
```

### AI Variables (if {PRODUCT_ROOT}/neuron/ exists)
```bash
LLM_PROVIDER=anthropic|openai|azure|ollama
LLM_API_KEY=<secret>
ENGINE_INTERNAL_API_URL=http://api:5000/api/internal

# Provider-specific
ANTHROPIC_API_KEY=<secret>
OPENAI_API_KEY=<secret>
AZURE_OPENAI_ENDPOINT=<url>
OLLAMA_HOST=http://localhost:11434
```

### Secrets Management
**Development:**
- Store in `.env` file (gitignored)
- Copy from `.env.example` template

**Production:**
- Use secrets manager (Azure Key Vault / AWS Secrets Manager / HashiCorp Vault)
- Mount as environment variables at runtime
- Never commit secrets to git

---

## Deployment Targets

### Development (Local)

**Purpose:** Developer workstation, rapid iteration

**Configuration:**
```yaml
# docker-compose.yml
- Hot reload enabled
- Debug ports exposed
- All services in docker-compose
- Seed/test data loaded
- Verbose logging
```

**Start Command:**
```bash
docker-compose up --build
```

**Access:**
- Frontend: http://localhost:3000
- API: http://localhost:5000
- Neuron: http://localhost:8000
- Database: localhost:5432 (for DB tools)

---

### Staging

**Purpose:** Pre-production testing, QA validation

**Configuration:**
```yaml
# docker-compose.staging.yml
- Production builds (no hot reload)
- No debug ports
- Real Keycloak instance
- Staging database (separate from prod)
- Moderate logging
```

**Differences from Dev:**
- Uses production Docker images
- SSL/TLS enabled
- Connects to staging Keycloak
- Uses staging environment variables

---

### Production

**Purpose:** Live application serving real users

**Configuration:**
[Choose orchestration platform]

**Option A: Docker Compose (Single Node)**
- Suitable for: Small-scale, MVP, low traffic
- Limitations: No auto-scaling, single point of failure
- File: `docker-compose.prod.yml`

**Option B: Docker Swarm**
- Suitable for: Medium-scale, multi-node
- Features: Load balancing, auto-scaling, rolling updates
- Deployment: `docker stack deploy`

**Option C: Kubernetes**
- Suitable for: Large-scale, enterprise
- Features: Advanced orchestration, auto-scaling, self-healing
- Deployment: `kubectl apply -f k8s/`

**Requirements:**
- ✅ SSL/TLS termination (reverse proxy or load balancer)
- ✅ Secrets from vault (not .env files)
- ✅ Persistent volumes for database
- ✅ Health checks and monitoring
- ✅ Log aggregation (e.g., ELK stack)
- ✅ Backup strategy for database
- ✅ Disaster recovery plan

**Resource Requirements:**
- API: [CPU, Memory requirements]
- Web: [CPU, Memory requirements]
- Neuron: [CPU, Memory requirements - may need GPU]
- Database: [Storage requirements]

---

## Non-Functional Requirements

### Performance
- **API Response Time:** [e.g., p95 < 200ms]
- **Frontend Load Time:** [e.g., < 2 seconds]
- **AI Response Time:** [e.g., p95 < 5 seconds]
- **Database Query Time:** [e.g., < 100ms for common queries]

### Scalability
- **Concurrent Users:** [e.g., 1000 concurrent users]
- **Requests per Second:** [e.g., 500 req/s]
- **Horizontal Scaling:** [Yes/No - which services can scale horizontally]
- **Vertical Scaling:** [Limits - max CPU/memory per service]

### Availability
- **Uptime Target:** [e.g., 99.9% (3 nines)]
- **Planned Downtime:** [e.g., Sunday 2-4 AM for maintenance]
- **High Availability:** [Yes/No]
- **Failover Strategy:** [If HA, describe failover]

### Security
- **HTTPS:** Required in production
- **Secrets Management:** [Vault / Key Manager]
- **Network Isolation:** [Backend/DB not exposed externally]
- **Authentication:** [Keycloak / Auth0 / Custom]
- **API Rate Limiting:** [e.g., 100 req/min per user]

---

## Monitoring & Observability

### Health Checks
- **API:** `GET /health` → 200 OK
- **Frontend:** `GET /` → 200 OK
- **Neuron:** `GET /health` → 200 OK
- **Database:** `pg_isready` or `SELECT 1`

### Metrics Collection
**Recommended Tools:**
- Prometheus (metrics)
- Grafana (dashboards)
- Loki (logs)

**Key Metrics to Track:**
- Request rate (req/s)
- Response time (p50, p95, p99)
- Error rate (%)
- CPU usage per service
- Memory usage per service
- Database connections
- AI token usage and cost

### Logging
**Log Levels:**
- Development: Debug
- Staging: Info
- Production: Warning

**Log Aggregation:**
- Collect logs from all containers
- Centralized logging (e.g., ELK stack, Datadog)
- Retention: [e.g., 30 days]

### Alerting
**Alert On:**
- Service down (health check fails)
- Error rate > 5%
- Response time p95 > threshold
- Database connection pool exhausted
- Disk space < 10%
- Memory usage > 90%

---

## Backup & Recovery

### Database Backup
**Strategy:**
- **Frequency:** [e.g., Daily at 2 AM UTC]
- **Retention:** [e.g., 7 daily, 4 weekly, 12 monthly]
- **Method:** [pg_dump / managed backup service]
- **Location:** [S3 bucket / Azure Blob Storage / NAS]

**Recovery Time Objective (RTO):** [e.g., < 1 hour]
**Recovery Point Objective (RPO):** [e.g., < 24 hours]

### Disaster Recovery
**Scenarios:**
1. **Database corruption:** Restore from backup
2. **Service failure:** Restart container or fail over to replica
3. **Complete outage:** Restore from infrastructure-as-code + latest backup

---

## Deployment Procedures

### Initial Deployment
```bash
1. Clone repository
2. Copy .env.example to .env and configure secrets
3. Build images: docker-compose build
4. Start services: docker-compose up -d
5. Run migrations: docker exec api dotnet ef database update
6. Verify health: ./scripts/health-check.sh
7. Load seed data (if needed): ./scripts/seed-data.sh
```

### Rolling Updates
```bash
1. Pull latest code: git pull
2. Build new images: docker-compose build
3. Stop old containers: docker-compose down
4. Start new containers: docker-compose up -d
5. Verify health: ./scripts/health-check.sh
6. Rollback if issues: docker-compose down && git checkout <previous-commit> && docker-compose up -d
```

### Rollback Procedure
```bash
1. Identify previous working version
2. Stop current containers: docker-compose down
3. Checkout previous version: git checkout <commit>
4. Rebuild: docker-compose build
5. Start: docker-compose up -d
6. Verify: ./scripts/health-check.sh
```

---

## Cost Estimation

**Development:**
- Local resources only (developer workstation)
- No cloud costs

**Staging:**
- [List expected cloud resources and costs]

**Production:**
- Compute: [e.g., $X/month for VM/containers]
- Storage: [e.g., $Y/month for database storage]
- Networking: [e.g., $Z/month for bandwidth]
- LLM API: [e.g., $W/month based on usage]
- **Total Estimated:** $[Total]/month

---

## Architecture Decision Record (ADR)

**Decision:** [Deployment architecture pattern chosen]

**Status:** Accepted

**Context:**
- Code inspection revealed: [Summary of services detected]
- Architect specified: [NFRs, scalability requirements]
- Team capabilities: [Team size, skill levels]
- Timeline: [MVP / Phase 2 / Production]

**Decision:**
Implement [Pattern Name] deployment architecture with [orchestration choice].

**Consequences:**

**Positive:**
- ✅ [List benefits of this approach]

**Negative:**
- ⚠️ [List limitations or tradeoffs]

**Alternatives Considered:**
- [Alternative 1]: [Why not chosen]
- [Alternative 2]: [Why not chosen]

---

## Future Considerations

### Phase 2 Enhancements
- [ ] Add Redis for caching
- [ ] Implement message queue for async processing
- [ ] Add worker services for background jobs
- [ ] Implement auto-scaling
- [ ] Add CDN for static assets
- [ ] Implement blue-green deployments

### Observability Improvements
- [ ] Add distributed tracing (Jaeger)
- [ ] Implement custom metrics dashboards
- [ ] Set up APM (Application Performance Monitoring)
- [ ] Configure alerts for business metrics

### Security Enhancements
- [ ] Implement WAF (Web Application Firewall)
- [ ] Add DDoS protection
- [ ] Implement secrets rotation
- [ ] Add security scanning to CI/CD pipeline

---

## References

**Framework Documentation:**
- `agents/devops/references/containerization-guide.md` - Detailed containerization patterns
- `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md` - Solution-specific patterns
- `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` Section 4 - NFRs and architecture decisions

**External Resources:**
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Dockerfile Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [12-Factor App Methodology](https://12factor.net/)

---

**Document Version:** 1.0
**Created By:** DevOps Agent
**Created Date:** [Date]
**Last Updated:** [Date]
**Reviewed By:** [Architect / Team Lead]
**Approved By:** [User]

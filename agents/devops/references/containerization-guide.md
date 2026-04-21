# Containerization Guide

**Purpose:** Guide DevOps engineers through containerizing applications with Docker, from code inspection to deployment configuration generation.

**Audience:** DevOps agent, human DevOps engineers

---

## Overview

This guide follows a **three-phase workflow**:
1. **Discovery** - Inspect code to understand what needs to be deployed
2. **Design** - Create deployment architecture template
3. **Implementation** - Generate Docker configurations

---

## Phase 1: Code Inspection & Discovery

### Objective
Scan the codebase to detect languages, frameworks, dependencies, and deployment requirements.

---

### 1.1 Backend Service Detection ({PRODUCT_ROOT}/engine/)

**Scan for:**

#### .NET / C# API
```bash
# Detection signals
- *.csproj files
- appsettings.json, appsettings.Development.json
- Program.cs with WebApplication.CreateBuilder()
- Controllers/ directory

# Extract information
- Target framework: <TargetFramework>net10.0</TargetFramework>
- Database: Connection string in appsettings.json
- Port: applicationUrl in launchSettings.json or ASPNETCORE_URLS
- Auth: Keycloak integration (check for JWT bearer)
```

**Example detection:**
```
✓ {PRODUCT_ROOT}/engine/ detected
  - Language: C#
  - Framework: ASP.NET Core 10
  - Database: PostgreSQL (connection string: postgres://...)
  - Auth: Keycloak (JWT bearer authentication found)
  - Port: 5000 (from launchSettings.json)
  - Dependencies: EF Core, Casbin.NET
```

---

#### Java / Spring Boot API
```bash
# Detection signals
- pom.xml or build.gradle
- src/main/java/
- application.properties or application.yml
- @SpringBootApplication annotation

# Extract information
- Java version: <maven.compiler.target>
- Database: spring.datasource.url
- Port: server.port
- Auth: Spring Security configuration
```

---

#### Python / FastAPI
```bash
# Detection signals
- requirements.txt or pyproject.toml
- main.py or app.py with FastAPI()
- /app or /api directory structure

# Extract information
- Python version: python_requires in setup.py
- Database: SQLAlchemy connection strings
- Port: uvicorn run configuration (default 8000)
- Dependencies: requirements.txt
```

---

#### Node.js / Express API
```bash
# Detection signals
- package.json with "express" dependency
- server.js or app.js
- routes/ directory

# Extract information
- Node version: "engines" in package.json
- Database: Check for pg, mysql2, mongoose
- Port: process.env.PORT or hardcoded
- Auth: passport, jsonwebtoken dependencies
```

---

### 1.2 Frontend Service Detection ({PRODUCT_ROOT}/experience/)

#### React / Vite SPA
```bash
# Detection signals
- package.json with "react" and "vite"
- vite.config.ts
- src/main.tsx or src/index.tsx
- index.html

# Extract information
- React version: package.json dependencies
- Build tool: Vite (vite.config.ts)
- Port: vite.config.ts server.port (default 3000)
- API endpoint: Check .env files or constants for API_URL
- Runtime: Static files (needs nginx for production)
```

---

#### Vue / Vite SPA
```bash
# Detection signals
- package.json with "vue"
- vite.config.ts
- src/main.ts with createApp
- App.vue

# Extract information
- Vue version: package.json
- Build tool: Vite
- Port: 3000 (default)
- API endpoint: env variables or config
```

---

#### Angular SPA
```bash
# Detection signals
- angular.json
- package.json with "@angular/core"
- src/app/app.component.ts

# Extract information
- Angular version: package.json
- Build tool: Angular CLI
- Port: 4200 (default)
- API endpoint: environment.ts files
```

---

### 1.3 AI Layer Detection ({PRODUCT_ROOT}/neuron/)

#### Python / FastAPI (AI Layer)
```bash
# Detection signals
- {PRODUCT_ROOT}/neuron/ directory exists
- requirements.txt with fastapi, LLM provider SDKs
- mcp/ or domain_agents/ directories
- Presence of prompt templates

# Extract information
- LLM Provider: Check for anthropic, openai, ollama in requirements
- Port: 8000 (FastAPI default)
- MCP servers: Check {PRODUCT_ROOT}/neuron/mcp/ directory
- Dependencies on {PRODUCT_ROOT}/engine/: Look for httpx calls to internal API
```

---

### 1.4 Database Detection

**Scan configuration files for connection strings:**

```bash
# PostgreSQL
- appsettings.json: "Host=localhost;Database=..."
- DATABASE_URL environment variable
- docker-compose.yml with postgres service

# MySQL
- "Server=localhost;Database=..."
- MYSQL_URL environment variable

# MongoDB
- "mongodb://localhost:27017"
- MONGO_URL environment variable

# SQLite
- "Data Source=app.db"
- File-based, no container needed (dev only)
```

---

### 1.5 Additional Services Detection

#### Redis (Caching)
```bash
# Detection signals
- StackExchange.Redis NuGet package
- redis-client dependencies in package.json
- Configuration: "localhost:6379"
```

#### Message Queue (RabbitMQ, Kafka)
```bash
# Detection signals
- RabbitMQ.Client package
- kafka-node dependency
- Configuration for message broker
```

#### Workflow Engine (Temporal)
```bash
# Detection signals
- Temporal SDK dependencies
- Workflow definitions
- Worker processes
```

---

### 1.6 Environment Variables Inventory

**Scan for environment variables:**

```bash
# .NET
appsettings.json: Look for ${VAR_NAME} placeholders
launchSettings.json: Check environmentVariables section

# Node.js / React
.env files: .env, .env.example, .env.local
process.env.VAR_NAME references in code

# Python
.env files
os.getenv("VAR_NAME") in code
```

**Categorize variables:**
- **Database:** DATABASE_URL, DB_NAME, DB_USER, DB_PASSWORD
- **Auth:** KEYCLOAK_URL, JWT_SECRET, AUTH0_DOMAIN
- **External APIs:** LLM_API_KEY, LLM_PROVIDER
- **Application:** PORT, NODE_ENV, ASPNETCORE_ENVIRONMENT
- **Secrets:** API keys, passwords, tokens

---

### 1.7 Discovery Output

**Example discovery summary:**

```markdown
## Code Inspection Results

### Services Detected
1. **Backend API ({PRODUCT_ROOT}/engine/)**
   - Language: C# / .NET 10
   - Framework: ASP.NET Core
   - Database: PostgreSQL
   - Auth: Keycloak (JWT)
   - Port: 5000

2. **Frontend ({PRODUCT_ROOT}/experience/)**
   - Language: TypeScript / React 18
   - Build: Vite
   - Runtime: Static files (Nginx for prod)
   - Port: 3000 (dev), 80 (prod)

3. **AI Layer ({PRODUCT_ROOT}/neuron/)**
   - Language: Python 3.11
   - Framework: FastAPI
   - Port: 8000
   - Dependencies: {PRODUCT_ROOT}/engine/ internal API

### Infrastructure Requirements
- PostgreSQL 16 (persistent storage needed)
- No Redis detected
- No message queue detected
- No worker processes detected

### Service Dependencies
```
{PRODUCT_ROOT}/neuron/ ──┐
          ├──> {PRODUCT_ROOT}/engine/ ──> postgres
{PRODUCT_ROOT}/experience/ ┘
```

### Environment Variables Required
- DATABASE_URL (postgres connection)
- DB_NAME, DB_USER, DB_PASSWORD
- KEYCLOAK_URL, JWT_SECRET
- LLM_PROVIDER, LLM_API_KEY
- API_URL (for {PRODUCT_ROOT}/experience/)
```

---

## Phase 2: Deployment Architecture Design

### Objective
Based on code inspection, design the deployment architecture and create a solution-specific template.

---

### 2.1 Choose Deployment Pattern

#### Pattern 1: API-Only (Backend + Database)
**Use when:**
- No frontend detected ({PRODUCT_ROOT}/experience/ doesn't exist)
- Building pure API service
- Frontend hosted separately

**Architecture:**
```
┌──────────────┐
│ Backend API  │ :5000
└──────┬───────┘
       │
       ↓
┌──────────────┐
│   Database   │ :5432
└──────────────┘
```

**Services needed:**
- Database (postgres/mysql/mongodb)
- API ({PRODUCT_ROOT}/engine/)

---

#### Pattern 2: Traditional 3-Tier (API + SPA + Database)
**Use when:**
- Backend ({PRODUCT_ROOT}/engine/) + Frontend ({PRODUCT_ROOT}/experience/) both exist
- No AI layer ({PRODUCT_ROOT}/neuron/ doesn't exist)
- Standard web application

**Architecture:**
```
┌──────────────┐
│   Frontend   │ :3000
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ Backend API  │ :5000
└──────┬───────┘
       │
       ↓
┌──────────────┐
│   Database   │ :5432
└──────────────┘
```

**Services needed:**
- Database
- API ({PRODUCT_ROOT}/engine/)
- Web ({PRODUCT_ROOT}/experience/)

---

#### Pattern 3: AI-Enabled 3-Tier (API + SPA + AI + Database)
**Use when:**
- All three layers exist: {PRODUCT_ROOT}/engine/, {PRODUCT_ROOT}/experience/, {PRODUCT_ROOT}/neuron/
- AI features integrated
- Application uses LLM capabilities

**Architecture:**
```
┌──────────────┐
│   Frontend   │ :3000
└──────┬───────┘
       │
       ↓
┌──────────────┐     ┌────────────┐
│ Backend API  │<────│ AI Layer   │ :8000
│    :5000     │     │ ({PRODUCT_ROOT}/neuron/)  │
└──────┬───────┘     └────────────┘
       │
       ↓
┌──────────────┐
│   Database   │ :5432
└──────────────┘
```

**Services needed:**
- Database
- API ({PRODUCT_ROOT}/engine/)
- Web ({PRODUCT_ROOT}/experience/)
- Neuron ({PRODUCT_ROOT}/neuron/)

---

#### Pattern 4: Microservices (Multiple APIs + Database per service)
**Use when:**
- Multiple independent engine-* directories detected
- Service-oriented architecture
- Each service has its own database

**Architecture:**
```
┌────────────┐
│  Frontend  │
└─────┬──────┘
      │
      ├──> ┌──────────┐     ┌──────────┐
      │    │Service A │ --> │   DB A   │
      │    └──────────┘     └──────────┘
      │
      ├──> ┌──────────┐     ┌──────────┐
      │    │Service B │ --> │   DB B   │
      │    └──────────┘     └──────────┘
      │
      └──> ┌──────────┐     ┌──────────┐
           │Service C │ --> │   DB C   │
           └──────────┘     └──────────┘
```

**Services needed:**
- Multiple databases (one per service)
- Multiple APIs
- API Gateway (optional)
- Web ({PRODUCT_ROOT}/experience/)

---

### 2.2 Define Service Specifications

For each service, document:

#### Database Service
```yaml
Service: postgres
Image: postgres:16
Volumes: Persistent storage required
Ports: 5432 (internal), optionally expose for dev
Environment:
  - POSTGRES_DB
  - POSTGRES_USER
  - POSTGRES_PASSWORD
Health check: pg_isready
```

#### Backend API Service
```yaml
Service: api ({PRODUCT_ROOT}/engine/)
Build: ./engine/Dockerfile (to be created)
Runtime: .NET 10 / Java 17 / Python 3.11 / Node 20
Ports: 5000:5000 (or framework default)
Dependencies: [database]
Environment:
  - DATABASE_URL
  - Auth variables (KEYCLOAK_URL, JWT_SECRET)
Health check: HTTP GET /health or /api/health
```

#### Frontend Service
```yaml
Service: web ({PRODUCT_ROOT}/experience/)
Build: ./experience/Dockerfile (multi-stage with nginx)
Runtime: Nginx (production) or Vite dev server (dev)
Ports: 3000:3000 (dev), 80:80 (prod)
Dependencies: [api]
Environment:
  - API_URL
Health check: HTTP GET /
```

#### AI Layer Service
```yaml
Service: neuron ({PRODUCT_ROOT}/neuron/)
Build: ./neuron/Dockerfile
Runtime: Python 3.11 with FastAPI
Ports: 8000:8000
Dependencies: [api] (calls internal API)
Environment:
  - LLM_PROVIDER
  - LLM_API_KEY
  - ENGINE_INTERNAL_API_URL
Health check: HTTP GET /health
```

---

### 2.3 Consult Architect

**Read architectural decisions:**
- `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md` - Established patterns
- `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` Section 4 - NFRs (performance, scalability, availability)
- `{PRODUCT_ROOT}/planning-mds/architecture/decisions/*.md` - ADRs

**Questions to answer:**
1. **Scalability:** Does this need to scale horizontally? (Multiple replicas)
2. **High Availability:** Is HA required? (>99.9% uptime)
3. **Deployment Target:** Dev only? Staging? Production? All three?
4. **Networking:** Do services need to communicate externally?
5. **Secrets Management:** Env files? Vault? Cloud secrets manager?

**Example clarification:**
```
DevOps: "NFRs specify 'high availability' but no specifics.
         Should I design for Kubernetes (complex) or Docker Swarm (simpler)?"

Architect: "We're MVP phase. Single-node Docker Compose is sufficient.
            We'll add HA in phase 2 when we have real traffic."

DevOps: "Understood. Designing for single-node with easy migration path."
```

---

### 2.4 Create Deployment Architecture Template

**File:** `{PRODUCT_ROOT}/planning-mds/architecture/deployment-architecture.md`

**Use template:** `agents/templates/deployment-architecture-template.md`

**Fill in:**
- Architecture pattern (which pattern from 2.1)
- Service inventory (from code inspection)
- Dependency graph
- Port mappings
- Environment variables
- Network architecture diagram
- Deployment target specifications (dev/staging/prod)
- Reference to containerization patterns used

---

## Phase 3: Configuration Generation

### Objective
Generate Docker configurations based on the deployment architecture template.

---

### 3.1 Generate docker-compose.yml

**Structure:**
```yaml
version: '3.9'

services:
  # Database service
  database_service:
    image: <database-image>
    environment: <env-vars>
    volumes: <persistent-storage>
    ports: <port-mapping>
    healthcheck: <health-check>

  # Backend API service
  api_service:
    build:
      context: ./engine
      dockerfile: Dockerfile
    ports: <port-mapping>
    environment: <env-vars>
    depends_on:
      database_service:
        condition: service_healthy
    restart: unless-stopped

  # Frontend service (if exists)
  web_service:
    build:
      context: ./experience
      dockerfile: Dockerfile
    ports: <port-mapping>
    environment: <env-vars>
    depends_on: [api_service]
    restart: unless-stopped

  # AI layer service (if exists)
  neuron_service:
    build:
      context: ./neuron
      dockerfile: Dockerfile
    ports: <port-mapping>
    environment: <env-vars>
    depends_on: [api_service]
    restart: unless-stopped

volumes:
  <volume-definitions>

networks:
  default:
    driver: bridge
```

---

### 3.2 Generate Dockerfiles

#### .NET API Dockerfile
```dockerfile
# Multi-stage build for .NET
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

# Copy csproj and restore dependencies
COPY ["*.csproj", "./"]
RUN dotnet restore

# Copy source and build
COPY . .
RUN dotnet publish -c Release -o /app/publish

# Runtime stage
FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /app/publish .

# Expose port
EXPOSE 5000

# Set environment
ENV ASPNETCORE_URLS=http://+:5000

# Run application
ENTRYPOINT ["dotnet", "YourApp.dll"]
```

**Key considerations:**
- Use multi-stage builds (smaller image size)
- Restore dependencies in separate layer (better caching)
- Set ASPNETCORE_URLS to bind to all interfaces
- Replace "YourApp.dll" with actual assembly name from .csproj

---

#### Java Spring Boot Dockerfile
```dockerfile
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline
COPY src ./src
RUN mvn package -DskipTests

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /app/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

---

#### Python FastAPI Dockerfile
```dockerfile
FROM python:3.11-slim
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

#### React + Vite + Nginx Dockerfile
```dockerfile
# Build stage
FROM node:20-alpine AS build
WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Build application
COPY . .
RUN npm run build

# Production stage with Nginx
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom nginx config (if needed)
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**nginx.conf for SPA (handle client-side routing):**
```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy (optional)
    location /api {
        proxy_pass http://api:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

### 3.3 Generate .env.example

**Structure:**
```bash
# Database Configuration
DB_NAME=app_db
DB_USER=app_user
DB_PASSWORD=change_me_in_production

# Application Configuration
NODE_ENV=development
ASPNETCORE_ENVIRONMENT=Development

# Authentication
KEYCLOAK_URL=http://keycloak:8080
JWT_SECRET=change_me_in_production_use_long_random_string

# API Configuration
API_URL=http://localhost:5000

# AI Configuration (if {PRODUCT_ROOT}/neuron/ exists)
LLM_PROVIDER=anthropic
LLM_API_KEY=your_api_key_here

# Ports (for reference)
API_PORT=5000
WEB_PORT=3000
NEURON_PORT=8000
```

**Include comments:**
- Mark secrets that MUST be changed in production
- Provide examples of valid values
- Group related variables together

---

### 3.4 Generate Deployment Scripts

#### Development Start Script
```bash
#!/bin/bash
# scripts/dev-up.sh

echo "🚀 Starting development environment..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "✅ Created .env file. Please update with your credentials."
    exit 1
fi

# Build and start services
echo "🔨 Building and starting services..."
docker-compose up --build

echo "✅ Development environment is running!"
echo "   API: http://localhost:5000"
echo "   Web: http://localhost:3000"
echo "   Neuron: http://localhost:8000"
```

#### Development Stop Script
```bash
#!/bin/bash
# scripts/dev-down.sh

echo "🛑 Stopping development environment..."
docker-compose down
echo "✅ All services stopped"
```

#### Production Deploy Script
```bash
#!/bin/bash
# scripts/prod-deploy.sh

echo "🚀 Deploying to production..."

# Validate environment
if [ "$ENVIRONMENT" != "production" ]; then
    echo "❌ ENVIRONMENT must be set to 'production'"
    exit 1
fi

# Run security checks
echo "🔒 Running security checks..."
./scripts/check-secrets.sh

# Build production images
echo "🔨 Building production images..."
docker-compose -f docker-compose.prod.yml build

# Deploy
echo "🚀 Deploying..."
docker-compose -f docker-compose.prod.yml up -d

echo "✅ Deployment complete!"
```

---

### 3.5 Generate Health Check Scripts

```bash
#!/bin/bash
# scripts/health-check.sh

echo "🏥 Checking service health..."

# Check API
API_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health)
if [ "$API_HEALTH" = "200" ]; then
    echo "✅ API is healthy"
else
    echo "❌ API is unhealthy (status: $API_HEALTH)"
fi

# Check Web
WEB_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000)
if [ "$WEB_HEALTH" = "200" ]; then
    echo "✅ Web is healthy"
else
    echo "❌ Web is unhealthy (status: $WEB_HEALTH)"
fi

# Check Neuron (if exists)
if docker ps | grep -q neuron; then
    NEURON_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
    if [ "$NEURON_HEALTH" = "200" ]; then
        echo "✅ Neuron is healthy"
    else
        echo "❌ Neuron is unhealthy (status: $NEURON_HEALTH)"
    fi
fi
```

---

## Decision Trees

### Should I Add Redis?

```
┌─────────────────────────────────────┐
│ Is Redis referenced in code?       │
│ (connection strings, client libs)  │
└────────────┬────────────────────────┘
             │
      ┌──────┴──────┐
      YES           NO
      │             │
      ↓             ↓
  ┌───────┐    ┌─────────┐
  │ Add   │    │ Don't   │
  │ Redis │    │ add     │
  └───────┘    └─────────┘
```

### Should I Use Multi-Stage Builds?

```
┌─────────────────────────────────────┐
│ Is this a compiled language?       │
│ (.NET, Java, Go, TypeScript)       │
└────────────┬────────────────────────┘
             │
      ┌──────┴──────┐
      YES           NO (Python, PHP, Ruby)
      │             │
      ↓             ↓
  ┌───────┐    ┌─────────┐
  │ Use   │    │ Single  │
  │ multi │    │ stage   │
  │ stage │    │ is fine │
  └───────┘    └─────────┘
```

### Production vs Development Configuration

```
┌─────────────────────────────────────┐
│ Deployment target?                  │
└────────────┬────────────────────────┘
             │
      ┌──────┴──────────┐
   DEV/LOCAL       PRODUCTION
      │                 │
      ↓                 ↓
  Development:     Production:
  - Hot reload     - Optimized builds
  - Debug ports    - No debug ports
  - Local DBs      - Managed DBs
  - Seed data      - Real data
  - No secrets     - Vault/secrets manager
```

---

## Best Practices

### 1. Use Multi-Stage Builds
✅ Reduces final image size
✅ Separates build dependencies from runtime
✅ Improves security (no build tools in production)

### 2. Layer Optimization
```dockerfile
# ❌ BAD: Dependency changes invalidate all layers
COPY . .
RUN npm install

# ✅ GOOD: Dependencies cached separately
COPY package*.json ./
RUN npm install
COPY . .
```

### 3. Health Checks
✅ Always define health checks for services
✅ Use depends_on with condition: service_healthy
✅ Test health checks in development

### 4. Secrets Management
❌ Never commit secrets to .env files in git
✅ Use .env.example as template
✅ Add .env to .gitignore
✅ For production: Use vault, AWS Secrets Manager, or Azure Key Vault

### 5. Resource Limits
```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

### 6. Logging
```yaml
services:
  api:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 7. Restart Policies
```yaml
services:
  api:
    restart: unless-stopped  # Production
    # restart: "no"          # Development
```

---

## Common Patterns Library

### Pattern: Database with Init Scripts
```yaml
services:
  postgres:
    image: postgres:16
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init.sql
```

### Pattern: Service Wait for Database
```yaml
services:
  api:
    depends_on:
      postgres:
        condition: service_healthy
    # Alternative: use wait-for-it script
    command: ["./wait-for-it.sh", "postgres:5432", "--", "dotnet", "run"]
```

### Pattern: Development Hot Reload
```yaml
services:
  api:
    volumes:
      - ./engine:/app  # Mount source for hot reload
    environment:
      - ASPNETCORE_ENVIRONMENT=Development
```

### Pattern: Production with Separate Networks
```yaml
networks:
  frontend:
  backend:

services:
  web:
    networks: [frontend]

  api:
    networks: [frontend, backend]

  postgres:
    networks: [backend]  # Not exposed to frontend
```

---

## Troubleshooting

### Issue: Container won't start
**Check:**
1. View logs: `docker-compose logs <service>`
2. Verify health check: `docker ps` (should show "healthy")
3. Check environment variables: `docker-compose config`
4. Test build locally: `docker build -t test ./engine`

### Issue: Services can't communicate
**Check:**
1. Are services on same network? `docker network ls`
2. Use service names, not localhost: `http://api:5000` not `http://localhost:5000`
3. Check firewall rules on host
4. Verify depends_on is set correctly

### Issue: Database connection fails
**Check:**
1. Database is healthy: `docker-compose ps postgres`
2. Connection string uses service name: `postgres:5432` not `localhost:5432`
3. Wait for database to be ready (health check or wait script)
4. Credentials match between service and database

---

## References

**Docker Documentation:**
- [Dockerfile best practices](https://docs.docker.com/develop/dev-best-practices/)
- [Compose file reference](https://docs.docker.com/compose/compose-file/)
- [Multi-stage builds](https://docs.docker.com/build/building/multi-stage/)

**Framework Documentation:**
- `agents/templates/deployment-architecture-template.md` - Template structure
- `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md` - Solution-specific patterns

---

**Questions?** Consult with Architect agent for architectural decisions or Security agent for security best practices.

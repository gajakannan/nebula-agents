# DevOps - Code Patterns Reference

Detailed code examples for Docker, CI/CD, monitoring, and security configurations.

## Best Practices

### Multi-Stage Dockerfile (Backend - C# .NET)

```dockerfile
# Build stage
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

# Copy csproj and restore dependencies (cached layer)
COPY ["src/MyApp.Api/MyApp.Api.csproj", "src/MyApp.Api/"]
COPY ["src/MyApp.Application/MyApp.Application.csproj", "src/MyApp.Application/"]
COPY ["src/MyApp.Domain/MyApp.Domain.csproj", "src/MyApp.Domain/"]
COPY ["src/MyApp.Infrastructure/MyApp.Infrastructure.csproj", "src/MyApp.Infrastructure/"]
RUN dotnet restore "src/MyApp.Api/MyApp.Api.csproj"

# Copy everything else and build
COPY . .
WORKDIR "/src/src/MyApp.Api"
RUN dotnet build "MyApp.Api.csproj" -c Release -o /app/build

# Publish stage
FROM build AS publish
RUN dotnet publish "MyApp.Api.csproj" -c Release -o /app/publish /p:UseAppHost=false

# Runtime stage
FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS final
WORKDIR /app

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser /app
USER appuser

COPY --from=publish /app/publish .

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/health || exit 1

EXPOSE 5000
ENTRYPOINT ["dotnet", "MyApp.Api.dll"]
```

**Why multi-stage:**
- Build artifacts not in final image (smaller)
- SDK only in build stage (secure)
- Runtime image is minimal (~200MB vs 1GB)

### Dockerfile (Frontend - React + Vite)

```dockerfile
# Build stage
FROM node:20-alpine AS build
WORKDIR /app

# Copy package files (cached layer)
COPY package*.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# Runtime stage (Nginx)
FROM nginx:alpine AS final
WORKDIR /usr/share/nginx/html

# Copy custom nginx config
COPY docker/frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets
COPY --from=build /app/dist .

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD wget --quiet --tries=1 --spider http://localhost:80/health || exit 1

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Dockerfile (AI/Neuron - Python)

```dockerfile
FROM python:3.11-slim AS final
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["uvicorn", "neuron.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml (Local Development)

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    container_name: app-postgres
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: myapp
      POSTGRES_PASSWORD: dev_password_change_in_prod
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U myapp"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Keycloak (Authentication)
  keycloak:
    image: quay.io/keycloak/keycloak:23.0
    container_name: app-keycloak
    environment:
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: admin
      KC_DB: postgres
      KC_DB_URL: jdbc:postgresql://postgres:5432/keycloak
      KC_DB_USERNAME: myapp
      KC_DB_PASSWORD: dev_password_change_in_prod
    command: start-dev
    ports:
      - "8080:8080"
    depends_on:
      postgres:
        condition: service_healthy

  # Temporal (Workflow Engine)
  temporal:
    image: temporalio/auto-setup:1.22.0
    container_name: app-temporal
    environment:
      - DB=postgresql
      - DB_PORT=5432
      - POSTGRES_USER=myapp
      - POSTGRES_PWD=dev_password_change_in_prod
      - POSTGRES_SEEDS=postgres
    ports:
      - "7233:7233"
    depends_on:
      postgres:
        condition: service_healthy

  # Backend API (C# .NET)
  backend:
    build:
      context: .
      dockerfile: docker/backend/Dockerfile
    container_name: app-backend
    environment:
      - ASPNETCORE_ENVIRONMENT=Development
      - ConnectionStrings__DefaultConnection=Host=postgres;Database=myapp;Username=myapp;Password=dev_password_change_in_prod
      - Keycloak__Authority=http://keycloak:8080/realms/myapp
      - Temporal__HostPort=temporal:7233
    ports:
      - "5000:5000"
    depends_on:
      - postgres
      - keycloak
      - temporal
    volumes:
      - ./src:/app/src  # Hot reload for development

  # Frontend (React + Vite)
  frontend:
    build:
      context: .
      dockerfile: docker/frontend/Dockerfile
      target: dev  # Use dev stage with hot reload
    container_name: app-frontend
    environment:
      - VITE_API_URL=http://localhost:5000
      - VITE_KEYCLOAK_URL=http://localhost:8080
    ports:
      - "3000:3000"
    volumes:
      - ./experience:/app  # Hot reload
      - /app/node_modules  # Don't mount node_modules
    depends_on:
      - backend

  # AI/Neuron (Python)
  neuron:
    build:
      context: .
      dockerfile: docker/neuron/Dockerfile
    container_name: app-neuron
    environment:
      - DATABASE_URL=postgresql://myapp:dev_password_change_in_prod@postgres:5432/myapp
      - CLAUDE_API_KEY=${CLAUDE_API_KEY}
    ports:
      - "8000:8000"
    depends_on:
      - postgres
    volumes:
      - ./neuron:/app  # Hot reload

volumes:
  postgres_data:
```

### GitHub Actions CI/CD

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  # Run tests
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        component: [backend, frontend, neuron]
    steps:
      - uses: actions/checkout@v3

      - name: Run Backend Tests
        if: matrix.component == 'backend'
        run: |
          cd {PRODUCT_ROOT}/engine
          dotnet test --collect:"XPlat Code Coverage"

      - name: Run Frontend Tests
        if: matrix.component == 'frontend'
        run: |
          cd {PRODUCT_ROOT}/experience
          npm ci
          npm test

      - name: Run AI/Neuron Tests
        if: matrix.component == 'neuron'
        run: |
          cd {PRODUCT_ROOT}/neuron
          pip install -r requirements.txt
          pytest --cov=neuron

  # Build and push Docker images
  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push'
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v2
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push Backend
        uses: docker/build-push-action@v4
        with:
          context: .
          file: docker/backend/Dockerfile
          push: true
          tags: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}/backend:${{ github.sha }}

      - name: Build and push Frontend
        uses: docker/build-push-action@v4
        with:
          context: .
          file: docker/frontend/Dockerfile
          push: true
          tags: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}/frontend:${{ github.sha }}

  # Deploy to staging
  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop'
    environment:
      name: staging
      url: https://staging.your-app.com
    steps:
      - name: Deploy to Staging
        run: |
          # SSH to staging server and pull new images
          ssh deploy@staging.your-app.com "
            cd /opt/myapp &&
            docker-compose pull &&
            docker-compose up -d &&
            docker system prune -f
          "

  # Deploy to production (manual approval)
  deploy-production:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment:
      name: production
      url: https://your-app.com
    steps:
      - name: Deploy to Production
        run: |
          # Blue-green deployment
          ssh deploy@your-app.com "
            cd /opt/myapp &&
            ./scripts/deploy-blue-green.sh ${{ github.sha }}
          "
```

### Nginx Configuration (Reverse Proxy)

```nginx
# docker/nginx/nginx.conf
upstream backend {
    server backend:5000;
}

upstream frontend {
    server frontend:3000;
}

server {
    listen 80;
    server_name localhost;

    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support for hot reload
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Backend API
    location /api {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
```

## Common Patterns

### Environment Variable Management

**.env.example (Template):**
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/myapp

# Keycloak
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_REALM=myapp
KEYCLOAK_CLIENT_ID=myapp-api

# Temporal
TEMPORAL_HOST=localhost:7233

# AI/Neuron
CLAUDE_API_KEY=your-api-key-here

# Application
ASPNETCORE_ENVIRONMENT=Development
VITE_API_URL=http://localhost:5000
```

**Usage:**
```bash
# Copy template
cp .env.example .env

# Edit with real values
nano .env

# Load in docker-compose
docker-compose --env-file .env up
```

### Health Checks

**Backend (C# ASP.NET Core):**
```csharp
// Program.cs
app.MapGet("/health", () => Results.Ok(new
{
    Status = "healthy",
    Timestamp = DateTime.UtcNow,
    Version = "1.0.0"
}));

app.MapGet("/health/ready", async (AppDbContext db) =>
{
    try
    {
        await db.Database.CanConnectAsync();
        return Results.Ok(new { Status = "ready" });
    }
    catch
    {
        return Results.ServiceUnavailable();
    }
});
```

**Frontend (React):**
```typescript
// public/health endpoint
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'healthy' });
});
```

### Database Migrations

**Run migrations in Docker:**
```bash
# docker-compose.yml
services:
  backend:
    # ... other config
    command: >
      sh -c "
        dotnet ef database update &&
        dotnet MyApp.Api.dll
      "
```

**Separate migration job:**
```yaml
# GitHub Actions
- name: Run Migrations
  run: |
    docker run --rm \
      -e ConnectionStrings__DefaultConnection=${{ secrets.DB_CONNECTION }} \
      ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}/backend:${{ github.sha }} \
      dotnet ef database update
```

### Secrets Management (Production)

**HashiCorp Vault:**
```yaml
services:
  backend:
    environment:
      - VAULT_ADDR=http://vault:8200
      - VAULT_TOKEN=${VAULT_TOKEN}
    entrypoint: |
      sh -c "
        # Fetch secrets from Vault
        export DB_PASSWORD=$(vault kv get -field=password secret/database)
        export CLAUDE_API_KEY=$(vault kv get -field=api_key secret/claude)

        # Run application
        dotnet MyApp.Api.dll
      "
```

## Security Considerations

### Never Commit Secrets
```bash
# .gitignore
.env
.env.local
.env.*.local
*.key
*.pem
secrets/
```

### Use Non-Root Users in Containers
```dockerfile
# Create and use non-root user
RUN adduser --disabled-password --gecos '' appuser
USER appuser
```

### Scan Images for Vulnerabilities
```bash
# Trivy scan
trivy image ghcr.io/myapp/backend:latest

# In CI/CD
- name: Scan image
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ${{ env.IMAGE }}
    severity: CRITICAL,HIGH
```

### Limit Container Resources
```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

### Network Isolation
```yaml
networks:
  frontend-net:
    driver: bridge
  backend-net:
    driver: bridge
  database-net:
    driver: bridge
    internal: true  # No external access

services:
  postgres:
    networks:
      - database-net  # Only accessible internally

  backend:
    networks:
      - backend-net
      - database-net  # Can access database

  frontend:
    networks:
      - frontend-net
      - backend-net  # Can access backend API
```

## Monitoring Setup

### Prometheus Configuration

```yaml
# docker-compose.yml
services:
  prometheus:
    image: prom/prometheus:latest
    container_name: app-prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  grafana:
    image: grafana/grafana:latest
    container_name: app-grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    ports:
      - "3001:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/dashboards:/etc/grafana/provisioning/dashboards
    depends_on:
      - prometheus

volumes:
  prometheus_data:
  grafana_data:
```

**prometheus.yml:**
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'backend'
    static_configs:
      - targets: ['backend:5000']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'docker'
    static_configs:
      - targets: ['cadvisor:8080']
```

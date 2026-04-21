# DevOps Best Practices

Guidance for DevOps agent work. Keep this current as pipelines evolve.

## Principles
- Infrastructure as Code for all environments
- Environment parity (dev/test/stage/prod)
- Least privilege for all credentials and service accounts
- Automated build/test/deploy pipelines with approvals
- Observability by default (logs, metrics, traces)

## Container and Runtime Checklist
- **Use Multi-Stage Builds** — Smaller images, faster builds
- **Non-Root Users** — Security best practice
- **Health Checks** — Enable automatic restart on failure
- **Resource Limits** — Prevent one service from consuming all resources
- **Secrets Management** — Never commit secrets to git
- **Image Tagging** — Use specific versions, not `latest`
- **Logging** — Log to stdout, aggregate with Loki or the project-standard collector
- **Monitoring** — Prometheus + Grafana or the project-standard observability stack

## Baselines
- Use docker-compose for local dev
- CI runs on every PR and merge to main
- No secrets in repo; use .env or secrets manager
- Immutable build artifacts; deploy by version tag

## Checklists
- Pre-deploy: tests pass, scans pass, backups done
- Post-deploy: smoke tests, monitoring dashboards checked
- Rollback: documented and tested

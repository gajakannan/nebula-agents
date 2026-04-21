# Container Strategy

This framework uses a two-container model:

1. Builder runtime container (framework tooling)
2. Application runtime container(s) (generated solution services)

## 1) Builder Runtime Container

Purpose:
- Hosts agent role definitions, action docs, scripts, and templates used to orchestrate delivery.
- Provides a reproducible execution environment for running framework workflows.

Contains:
- `agents/`
- `blueprint-setup/`
- `scripts/`
- framework documentation

Does not contain:
- generated application source code in `{PRODUCT_ROOT}/engine/`, `{PRODUCT_ROOT}/experience/`, or `{PRODUCT_ROOT}/neuron/`
- project databases
- production secrets
- long-lived application runtime state

Usage:
- Build via root `Dockerfile`.
- Run interactively to execute planning/build workflows in a mounted workspace.

Execution boundary:
- The builder container is intentionally stack-agnostic and orchestration-focused.
- Do not treat the builder container as the place to install every app stack SDK/toolchain.
- Use the builder to coordinate workflows and collect artifacts, not to host production stack runtimes.

## 2) Application Runtime Container(s)

Purpose:
- Run the generated application stack (backend, frontend, database, and optional services).
- Host stack-specific compile/test/lint/security execution for the generated solution.

Produced by:
- `build` / `feature` actions and implementation agents (Backend, Frontend, AI Engineer, DevOps).

Typical services:
- API/backend service
- frontend service
- database service
- optional auth/cache/queue/worker services

Template:
- Start from `agents/templates/docker-compose.app-template.yml` and customize per project.
- Use `agents/devops/SKILL.md` for application Dockerfile, compose, and deployment guidance.

## Relationship

```text
Builder Container
  -> reads/writes planning and implementation artifacts
  -> coordinates agent workflows
  -> outputs app runtime configs
  -> records gate decisions and execution evidence locations

Application Containers
  -> run generated services
  -> execute stack-specific compile/test/security commands
  -> validated by QA/review/security gates
```

## Notes

- The builder and application runtimes are intentionally separate concerns.
- The builder runtime should not be treated as a production app deployment container.
- Stack-specific SDK/tooling belongs with the application runtime containers, not the builder base image.
- Application container strategy is project-specific and evolves with architecture decisions in `{PRODUCT_ROOT}/planning-mds/`.

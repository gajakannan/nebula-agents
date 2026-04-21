# Deployment Guide

This document is the operations-facing deployment guide for generated application runtimes.

## Scope

- Builder runtime orchestration is documented in `agents/docs/CONTAINER-STRATEGY.md`.
- This guide covers stack-specific application runtime deployment concerns.

## Required Inputs

- Deployment topology from `{PRODUCT_ROOT}/planning-mds/architecture/deployment-architecture.md`
- Runtime service definitions (`docker-compose*.yml`, Kubernetes manifests, or equivalent)
- Environment variable contract (`.env.example` and secret manager mappings)
- Validation evidence from lifecycle gates for the current stage

## Minimum Sections

1. Deployment environments (dev/staging/prod)
2. Build and release process
3. Configuration and secret handling
4. Health checks and rollback procedures
5. Observability (logs, metrics, traces)
6. Incident response contacts and escalation path

## Public-Safe Defaults

- Use immutable image tags (never `latest`)
- Avoid static credentials in committed manifests
- Bind admin/internal ports to private networks only
- Keep least-privilege runtime permissions

## Lifecycle Note

During `framework-bootstrap` and `planning` stages, this file may stay as a template.
Before `implementation`/`release-readiness`, it must be filled with environment-specific instructions.

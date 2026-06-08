# Product Context Map

Product repositories may define `planning-mds/context-map.yaml` to control
prompt context loading for agent runs. This is a product-local optimization
contract: it changes what agents load by default, not product behavior,
business logic, authorization, validation, evidence retention, or public
interfaces.

## Loading Order

When a product context map exists, agents should load context in this order:

1. Product `.agentignore`
2. Product `planning-mds/context-map.yaml`
3. Default layers named by the context map
4. Target feature files, if a feature is in scope
5. KG lookup/hint output, if available
6. Exact changed files and exact contracts needed by the task
7. On-demand layers only when their routing rule is satisfied

## Default Context

Default context should stay small. Typical defaults are:

- product `README.md`
- product `lifecycle-stage.yaml`
- product `.agentignore`
- `planning-mds/features/REGISTRY.md`
- `planning-mds/features/ROADMAP.md`
- target feature folder only
- KG lookup/hint output
- exact changed files

`planning-mds/BLUEPRINT.md` is loaded when planning, architecture, scope
reconciliation, or product-wide decisions require it.

## On-Demand Context

These classes should not be broad-loaded by default:

- feature archives
- historical evidence runs
- screenshots, visual artifacts, logs, HAR files, and generated reports
- full API/spec/schema directories
- full backend/frontend/neuron source trees
- full test trees
- examples and historical feature docs

Agents may load exact files from those areas for audits, validation, evidence
review, closeout, failure triage, security review, changed-path routing, KG
routing, exact contract checks, or explicit user requests.

## Agent Behavior

- Honor the product context map when it exists.
- If a context map conflicts with safety, authorization, validation, compliance,
  or an explicit user request, satisfy the safety/user requirement and record
  why on-demand context was needed.
- Prefer pointer files and manifests before raw evidence artifacts.
- Prefer KG command output before raw KG files.
- Prefer exact changed paths before broad source-tree reads.

## Validation

Products may provide a validator such as `scripts/validate-context-map.py`.
When present, run it during planning/tooling validation and report failures as
prompt-loading policy issues, not application behavior failures.

# Architect Scripts

Generic validation scripts.

## validate-architecture.py

```bash
python3 agents/architect/scripts/validate-architecture.py {PRODUCT_ROOT}/planning-mds/BLUEPRINT.md
```

## validate-api-contract.py

```bash
python3 agents/architect/scripts/validate-api-contract.py {PRODUCT_ROOT}/planning-mds/api/example-api.yaml
```

Validation scope includes:
- RFC 7807 `ProblemDetails` canonical error schema enforcement
- operation-level 4xx/5xx responses referencing `#/components/schemas/ProblemDetails`
- OpenAPI structure checks (required fields, response coverage, schema hygiene)

Dependency note: install framework script dependencies from `agents/scripts/requirements.txt`.

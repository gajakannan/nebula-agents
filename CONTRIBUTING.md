# Contributing

Thanks for contributing to this framework.

`nebula-agents` is the framework repo. Product planning and application code live in a sibling product repo resolved as `{PRODUCT_ROOT}` at session start — see `CONSUMER-CONTRACT.md` and `agents/docs/AGENT-USE.md`. Contributions here must stay framework-generic; product-specific changes belong in the product repo, not here.

## 1) Before You Start

1. Read `README.md`.
2. Read `BOUNDARY-POLICY.md`.
3. Read `CONSUMER-CONTRACT.md` so you understand what the framework exposes to downstream products.
4. Confirm your change is framework-generic (`agents/**`, framework root docs). If it is product/solution-specific, route it to the product repo under `{PRODUCT_ROOT}/planning-mds/` instead.

## 2) Contribution Flow

1. Open an issue describing the problem or proposal.
2. Create a branch for the change.
3. Submit a PR linked to the issue.
4. Ensure validations pass before requesting review.

## 3) Required Checks

Run at minimum:

```bash
python3 -m pip install -r agents/scripts/requirements.txt
python3 agents/scripts/run-lifecycle-gates.py
```

To inspect configured lifecycle stages and required gates:

```bash
python3 agents/scripts/run-lifecycle-gates.py --list
```

Lifecycle stage and gate definitions are declared in `lifecycle-stage.yaml`.

If your change touches scripts:

```bash
python3 -m py_compile $(rg --files agents | rg '\.py$')
```

Framework Python scripts live under `agents/` only. Product-owned scripts (for example `{PRODUCT_ROOT}/scripts/kg/`) are validated in the product repo, not here.

## 4) Boundary Rules

- Do not add solution-specific entities or terminology to `agents/`.
- Use standard example entities (`customers` and `orders`) in framework examples.
- Place project-specific requirements and examples in `{PRODUCT_ROOT}/planning-mds/`.

## 5) Vendor-Neutral Language Policy

- Core framework docs should use orchestrator-neutral language.
- Avoid making the framework dependent on a single runtime vendor.
- Vendor-specific integrations are acceptable when explicitly scoped (for example AI provider examples).

## 6) Proposing New Agents or Actions

For new agent roles:
1. Add `agents/<role>/SKILL.md`.
2. Add supporting `references/`, `scripts/`, or `assets/` as needed.
3. Add role references in role/action index docs.

For new actions:
1. Add `agents/actions/<action>.md`.
2. Define flow, prerequisites, inputs, outputs, and gates.
3. Update `agents/actions/README.md`.

## 7) Review Expectations

PRs should include:
- clear scope and rationale
- changed file list
- validation results
- any follow-up tasks

Keep changes focused and avoid unrelated edits in the same PR.

## 8) Branch and Commit Conventions

- Branch names should be descriptive and scoped (for example: `docs/vendor-neutral-language`, `fix/dockerignore-security`).
- Use small, focused commits by concern (docs, templates, actions, scripts).
- Prefer Conventional Commit style for clarity (for example: `docs: add orchestration I/O matrix`, `chore: tighten dockerignore exclusions`).

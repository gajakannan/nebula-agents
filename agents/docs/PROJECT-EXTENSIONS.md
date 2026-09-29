# Project instructions and required checks (v1)

A product can own local instructions and Python validation scripts without adding product rules to the framework. The optional `{NEBULA_PRODUCT_ROOT}/.nebula-project.yaml` declares them. This is a framework invocation convention, not a native hook API supplied by an agent host.

## Ownership and discovery

The framework owns discovery, schema validation, execution, and gate evidence. Products own the declared documents, scripts, and criteria. Instructions supplement the blueprint and do not override framework approvals or authorize additional scope. Resolve conflicts explicitly.

From the framework checkout, before action work and after every session resume:

```bash
python3 agents/scripts/project_context.py --product-root /absolute/product --action plan-review
```

Read the returned text, not only the listed filenames. The loader reads the product blueprint first and then applicable instruction files in declaration order. Explicit instruction loads are targeted reads even when `.agentignore` excludes those paths from broad discovery. It prints source paths and content hashes. `--json` returns the same context as structured data.

Both new commands require `--product-root` or `NEBULA_PRODUCT_ROOT`; the flag wins and there is no default product. Relative root inputs resolve against the invocation CWD; normalize once at session start and pass the absolute root thereafter. Product instruction/check paths resolve against that root. No manifest preserves the legacy action context procedure; `checks: []` enables instructions alone. A malformed manifest, missing instruction, unsupported version, or unsupported check point is an error. For `init`, a not-yet-created blueprint is allowed.

When upgrading existing products, update root placeholders in `.nebula-project.yaml`
checks and reusable prompts to `{NEBULA_PRODUCT_ROOT}`. Alternate root variable
names are rejected in executable configuration. Historical evidence remains readable
and does not need to be rewritten.

## Manifest

```yaml
version: 1
instructions:
  - path: docs/agent-instructions.md
  - path: docs/review-checklist.md
    actions: [plan-review]
checks:
  - id: plan-readiness
    action: plan-review
    stage: PR2
    event: before_stage_complete
    argv:
      - python3
      - "{NEBULA_PRODUCT_ROOT}/scripts/validation/check_plan.py"
      - --product-root
      - "{NEBULA_PRODUCT_ROOT}"
      - --plan-scope
      - "{PLAN_SCOPE}"
      - --target
      - "{TARGET}"
    cwd: product
    timeout_seconds: 60
    inputs:
      - planning-mds/features/**/*.md
      - scripts/validation/**/*.py
```

The schema is `agents/scripts/schemas/project.schema.json`. Fields are strict; check IDs must be unique. The only initial check point is `plan-review:PR2:before_stage_complete`, declared in the action spec. All declared checks are required. There are no replacement, optional-success, or arbitrary shell hooks.

`argv` is an argument array, never shell text. V1 accepts `python` or `python3` followed by a product-local `.py` script and uses the runner's Python interpreter. No inline `-c`, `-m`, shell executable, path traversal, or symlink escape is accepted. Timeouts are 1–300 seconds. Inputs are nonempty glob patterns; every pattern must match files. Declare all local dependencies and governing sources read by the check. Do not include its generated evidence directory in its inputs.

Supported placeholders are `{NEBULA_PRODUCT_ROOT}`, `{PLAN_SCOPE}`, and `{TARGET}`; feature scope also supplies `{FEATURE_ID}` and `{FEATURE_PATH}`. Unknown placeholders block execution. Features are resolved from `planning-mds/features/REGISTRY.md`, not arbitrary supplied directories. Feature-set targets are comma-separated IDs. Project scope requires target `project` and selects active or PRD-bearing, nonarchived registry entries; reserved IDs without plans are excluded. An active feature with a missing PRD is not silently excluded.

## Gate usage

Start or resume the normal action run and its base evidence package first. Use the same root, scope, target, and run ID throughout:

```bash
python3 agents/scripts/run-gate.py --product-root /absolute/product \
  --action plan-review --plan-scope feature --target F0001 --list
python3 agents/scripts/run-gate.py --product-root /absolute/product \
  --action plan-review --plan-scope feature --target F0001 \
  --run-id 2026-09-07-aabbccdd --stage PR2
```

The example run ID must be replaced with the actual action run ID. PR2 runs framework operations first, then required product checks. For opted-in feature-set/project scope, the runner expands story validation across the resolved features. A product failure cannot clear a framework failure. PR4 refuses to proceed without completed PR2 and current passing product-check evidence. Review roles still own the readiness judgment; neither a script pass nor a paused manual checkpoint is approval.

`--list` and `--dry-run` do not run checks or write state. Resume reuses only passing results with unchanged fingerprints and intact evidence. `--from` cannot skip an unfinished framework operation in a stage with required product checks. `--force` reruns checks but does not bypass prior required checks or approval checkpoints.

The run journal binds the product, action, scope, and manifest. Changing that identity—including deleting the manifest—requires a new run context. Fingerprints cover instruction contents, validator and declared inputs, the input file set, registry, relevant framework source files, and framework Git revision. Input changes during execution fail the check. Every attempt preserves separate stdout, stderr, and result metadata under the base run's `artifacts/project-checks/`, with hashes, command logs, and lifecycle logs. These are additive journal fields; historical evidence contracts remain unchanged. The optional project manifest/result contract is independently versioned at 1.

## Script result and CI

Scripts emit exactly one JSON object to stdout:

```json
{"schema_version":1,"check_id":"plan-readiness","status":"pass","findings":[]}
```

For failure, use `status: "fail"` and findings containing exactly `rule_id`, `message`, and product-relative `path`. Exit 0 means pass; 1 means validation failure; 2 means invocation/configuration error. Invalid JSON, inconsistent output/exit status, crashes, and timeouts block completion. Diagnostics belong on stderr.

CI uses the same resolver/executor without running an LLM or marking action stages complete:

```bash
python3 agents/scripts/project_checks.py --product-root /absolute/product \
  --action plan-review --plan-scope project --target project \
  --run-id 2026-09-07-aabbccdd
```

This writes `project-check-state.json` plus the same check evidence and logs; it does not imply reviewer approval. Pin a framework commit containing these commands before enabling them in consumer CI. Update the consumer blueprint and CI checkout pin together.

## Host boundary and limitations

Shell-capable hosts can invoke these same commands; no platform-specific hook translation is required. Generated operator and automation prompts both require explicit context loading on start/resume. This is not automatic enforcement of every command issued by a model.

The native launcher now reads `NEBULA_PRODUCT_ROOT` and binds its absolute workspace path into both the provider prompt and child environment, overriding stale tmux environment values. It still uses a single workspace for product and framework assets; separate sibling framework discovery is not supported by that adapter. For sibling consumption, use the documented framework-root shell session with explicit root arguments. Native host adapters have not been integration-tested for project extensions.

Local checks are trusted repository code, not sandboxed programs. Host permissions still govern execution. Structural validation checks artifacts and declared rules; semantic adequacy, security approval, and regulatory determinations remain human/reviewer responsibilities.

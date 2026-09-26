# Changelog

All notable changes to `nebula-agents` will be documented in this file. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows the policy in [CONSUMER-CONTRACT.md](CONSUMER-CONTRACT.md) §11.

---

## Unreleased

### Added — F0007 Spec-Driven Orchestration and Prompt Compilation

- Versioned action policy under `agents/actions/spec/` — active `_contract.yaml`, active action specs, and immutable, fully-resolved historical bundles (`history/<version>.yaml`) with JSON Schema and a semantic validator (`agents/scripts/validate_action_specs.py`), including manifest-version resolution.
- Independent conformance + historical baseline matrix (`agents/scripts/contract-conformance.py`) and a behavioral contract diff (`validate_action_specs.py --contract-diff`).
- Deterministic run initialization and product scaffolding (`agents/scripts/init-run.py`, `scaffold-product.py`).
- Shared shell-free typed-operation runtime and telemetry (`agents/scripts/gate_runtime.py`, `exec-and-log.py`); `run-lifecycle-gates.py` reuses the shared runtime.
- Durable gate driver with hashed manual-checkpoint attestations and the central severity state machine (`agents/scripts/run-gate.py`, `gate_policy.py`).
- Generated evidence-contract prompt pairs from the action policy with a drift gate (`agents/scripts/render-prompts.py`; `agents/templates/prompts/evidence-contract/generated/`).
- Shared-value resolver and vague-language linter (`agents/scripts/contract-value.py`, `lint-vague-language.py`).
- New framework lifecycle/CI gates: `action_spec_schema`, `contract_conformance`, `prompt_drift`.

### Changed

- **Consumer-visible:** newly initialized evidence runs carry `contract_version` in `evidence-manifest.json` (stamped by `init-run.py`) in addition to `contract_effective_date`. Legacy manifests without a version continue to resolve by effective date; published historical policy is immutable and an active-policy update never changes a historical run's verdict (`CONSUMER-CONTRACT.md`). Version/date contradictions fail closed.
- `validate-feature-evidence.py` is version-aware (new-field-guarded; existing rule IDs and behavior unchanged). Parity between the validator's date matrix and the versioned policy is proven by the dual-read diagnostic (`agents/product-manager/scripts/contract_compat.py --matrix`).

### Fixed — base-run tooling

- `run-gate.py`: checkpoint attestation hashes only file-like `requires` entries. Prose preconditions (validate V3, integrate I0, build, blog, document) are recorded as `acknowledged_preconditions` instead of being treated as missing files, so those checkpoints are no longer impossible to attest (`checkpoint_output_missing`). At least one hashed evidence file is still required; a prose-only checkpoint names its files with `--evidence`.
- `init-run.py`: `--feature` is required only for feature-bound actions (`FEATURE_ID` required in the action spec: `feature`, `plan`), which keep their run-scoped `evidence-manifest.json`. Every other action (for example `validate`, `blog`, `document`) now initializes base run files only, with no manifest and no feature index; `--feature` is optional scope. An unknown `--action` is rejected. Shared rule: `validate_action_specs.is_feature_bound`.
- `render-prompts.py`: the generated session-setup instruction matches what `init-run.py` creates. It no longer tells non-feature-bound actions to create `evidence-manifest.json`, names the `init-run.py` arguments, and says integrate-scheme ids are not minted by `init-run.py`. Operator prompts regenerated.
- `exec-and-log.py` / `gate_runtime.run_operation`: the command's stdout/stderr are passed through (or, with `--json`, kept out of the JSON). The new `--stdout` / `--stderr` options persist them inside the product root before the log entry is written, and record them as the entry's artifacts.
- `append-command-log.py`: the spec cwd labels `product` / `framework` (with optional subpath) map to `{PRODUCT_ROOT}` / `nebula-agents`, matching `gate_runtime`, instead of being recorded as `{PRODUCT_ROOT}/framework`.

### Deferred (human-gated)

- Cutover of the 24 hand-written evidence-contract prompts to generated output, and the 40% action/SKILL prose thinning, require role-owner semantic-equivalence approval.
- Removal of the validator's private date matrices follows a recorded zero-disagreement decision and the governed pilot.

## v0.1.0 — 2026-04-20

Initial standalone release, split from `gajakannan/nebula-crm` at commit `d2fa37c4216147b7a0be399e4133dac59ef75d9f` (the Section 9 Step 0 baseline hash recorded identically in `.split-baseline`).

### Added

- `README.md`, `CONSUMER-CONTRACT.md`, `lifecycle-stage.yaml`, `CHANGELOG.md` authored fresh for the framework repo
- `agents/docs/migration-from-nebula-crm.md` — migration note for consumers of the original mono-repo
- `{PRODUCT_ROOT}` path-indirection convention across every framework reference to product-owned paths
- `--product-root` / `NEBULA_PRODUCT_ROOT` resolution across framework Python scripts (shared `_product_root.py` helper)
- Embedded domain-term denylist in `agents/scripts/validate-genericness.py` so the validator runs with zero sibling-repo dependency in CI

### Changed

- Framework now ships as a standalone repo consumed as a sibling of the product repo, replacing the previous copy-in-place model
- `Dockerfile` builder image installs Python dependencies from `agents/scripts/requirements.txt` and no longer copies any product-owned `scripts/` content
- Framework docs, actions, and templates rewritten so every product-owned path is prefixed with `{PRODUCT_ROOT}`

### Removed

- Product-owned planning, implementation, and KG tooling (moved to `gajakannan/nebula-insurance-crm`)
- Old copy-in-place onboarding instructions
- Hardcoded product namespaces, API filenames, and layer directory names from framework prompts and references

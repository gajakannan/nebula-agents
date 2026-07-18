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

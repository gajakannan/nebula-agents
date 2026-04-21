# Changelog

All notable changes to `nebula-agents` will be documented in this file. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows the policy in [CONSUMER-CONTRACT.md](CONSUMER-CONTRACT.md) §11.

---

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

# Action Policy Specification (`agents/actions/spec/`)

Versioned, machine-readable orchestration policy — the source of truth F0007
migrates prose toward. Deterministic rules (gates, artifacts, ordering,
thresholds, typed command procedure) are declared here once; prompts, gate
execution, configuration consumers, and version-aware validators read this
policy instead of paraphrasing it.

> **S0001 scope.** This slice establishes policy identity, the active/historical
> layout, action/spec shapes, typed operations, placeholder rules, and
> manifest-version resolution — plus the validator that enforces them. It does
> **not** switch any live prompt or validator to this source; that is later
> stories (S0006 generation, S0007 validator convergence).

## Layout

| Path | Mutability | Purpose |
|------|-----------|---------|
| `_contract.yaml` | Editable (via review) | Active policy version + shared values consumed everywhere |
| `<action>.yaml` | Editable (via review) | Active action policy (gates, typed operations, ownership, stop conditions) |
| `history/<version>.yaml` | **Immutable after publication** | Fully-resolved policy bundle that interprets evidence produced under that version |
| `schema/*.schema.json` | Editable (via review) | JSON Schema structural contracts |

## Policy and compatibility model

- **Active policy** (`_contract.yaml`, `<action>.yaml`) is editable through
  review. `active_version` names the current version and **must equal the newest
  history bundle**; each active action spec's `contract.version` must equal
  `active_version`. The validator enforces both ties.
- **Historical policy** (`history/<version>.yaml`) is fully resolved and
  immutable: each bundle carries every shared value and action matrix needed to
  interpret evidence from its version, and never inherits a mutable value from
  the active contract. Versions are date-form (`YYYY-MM-DD`, optional `-rNN`
  suffix), monotonically increasing, and equal to the filename and
  `shared.contract_effective_date`.
- **Manifest resolution** (`validate_action_specs.py --resolve-manifest`):
  1. An explicit `contract_version` selects the exact bundle
     (`selection_source: explicit`).
  2. A legacy manifest (no version) with a date maps to the newest bundle whose
     `effective_from` is not later than the manifest date
     (`selection_source: legacy-date`); the manifest is never modified.
  3. An unknown version, or a date older than the first bundle, fails with a
     named rule (`manifest_unknown_version`, `manifest_date_before_first_policy`).

The five published bundles mirror the effective-date cutovers already encoded as
`*_EFFECTIVE_DATE` constants in
`agents/product-manager/scripts/validate-feature-evidence.py`:

| Version | Delta |
|---------|-------|
| `2026-05-19` | Base feature-completion contract |
| `2026-05-25` | Mandated security-scan classes for security-sensitive scope |
| `2026-06-01` | Architect G7 KG reconciliation package |
| `2026-07-05` | Proof of fresh generated-KG regeneration |
| `2026-07-11` | Compiled-projection contract (kg-source shards + `compile.py`) |

## Typed operation model

Executable policy is typed data, never shell text. A gate's `operations:` is an
ordered list; each item is exactly one of:

- `run` — `argv` array (no shell), `cwd` (`framework`|`product`),
  `timeout_seconds`, `expected_artifacts`, `mutates`.
- `checkpoint` — durable manual step; unique `id`, `description`, `requires`
  (preconditions), `produces` (postconditions).
- `write` — `artifact` produced `after` a named prior step.

The schema rejects string-form commands (a string is not an object). The
validator additionally rejects unknown placeholders, path escapes outside the
framework/product roots, duplicate gate/operation/checkpoint IDs, undeclared
mutation classes, and checkpoints missing pre/postconditions.

Free-text `judgment:` and `notes:` fields are the escape hatch: rendered into
prompts, never executed.

## Validate

```bash
python3 agents/scripts/validate_action_specs.py            # full report, exit 0/1
python3 agents/scripts/validate_action_specs.py --json     # machine-readable
python3 agents/scripts/validate_action_specs.py --resolve-manifest --version 2026-06-01
python3 agents/scripts/validate_action_specs.py --resolve-manifest --effective-date 2026-05-20
```

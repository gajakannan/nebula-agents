# Hotspot Review Guide

`{NEBULA_PRODUCT_ROOT}/planning-mds/knowledge-graph/coverage-report.yaml` rolls
behavioral signals (git activity, ownership, knowledge-silo risk) onto each
canonical node. These signals come from `{NEBULA_PRODUCT_ROOT}/scripts/kg/hotspots.py`
and feed reviewer, architect, and security workflows so risk decisions stop
being guesswork.

The hotspot layer is **not** authoritative. Per
`solution-ontology.yaml.authority.precedence`, raw artifacts win on conflict.
Hotspot signals are decision aids — they help pick reviewers, flag knowledge
silos, and concentrate threat-model effort, but they do not override design or
security judgment.

---

## Signals

`hotspots.py` walks git history (filtered through the significant-commit
predicate shared with `cochange.py`) and emits these fields per canonical node
into `coverage-report.yaml.freshness.canonical.<node-id>`:

| Field | Type | Meaning |
|---|---|---|
| `hotspot_rank` | integer | 1 = hottest node across the product. Rank is over nodes with bindings. |
| `hotspot_score` | float (0.0–1.0) | Normalized score: `Σ commits_per_bound_file × decay(180-day half-life) × file_count`. |
| `primary_owner` | string \| null | Top author across bound files (email or git identity). |
| `primary_owner_pct` | integer (0–100) | Percentage of touched lines attributed to `primary_owner`. |
| `bus_factor_flag` | boolean | `true` when `primary_owner_pct > 80`. Indicates knowledge-silo risk. |
| `last_modified` | YYYY-MM-DD | Latest commit timestamp across bound files. |

Merges, lints, dependency bumps, and other non-significant commits are filtered
out by the shared significant-commit predicate.

All fields are additive. Consumers may omit any of them; reviewers, architect,
and security only act on fields that are present.

---

## Thresholds

| Signal | Threshold | Action |
|---|---|---|
| `hotspot_rank ≤ 5` | Top-5 hottest node in product | Require explicit second-reviewer evidence on the PR. |
| `hotspot_score ≥ 0.80` | Score-band cutoff | Same as `hotspot_rank ≤ 5`; use when product has many nodes and rank alone is too coarse. |
| `bus_factor_flag: true` | One author owns >80% of touched lines | Tag `primary_owner` on the PR and require their acknowledgement. Architect proposes a knowledge-share follow-up at the next release-readiness checkpoint. |
| Hotspot ∩ `role:*` / `policy_rule:*` / auth boundary | Auth/policy hotspot | Security adds a targeted threat-model pass scoped to the bound files. |

Bands are framework defaults. A product may tighten or relax them in its own
overlay if telemetry justifies it — record the override in a product-local
ADR and reference it from `coverage-report.yaml`.

---

## When to use it

- **Code reviewer** — before assigning reviewers and before approving, consult
  `coverage-report.yaml` for the canonical nodes the PR touches. Route extra
  reviewer attention to hotspots; require owner acknowledgement on bus-factor
  nodes.
- **Architect** — at release-readiness checkpoints, walk the list of nodes
  with `bus_factor_flag: true` and propose knowledge-share follow-ups (pair
  programming, deliberate co-authoring, doc passes, rotation).
- **Security** — when triaging review scope, concentrate threat-model effort
  on hotspot files near auth and policy boundaries (`role:*`,
  `policy_rule:*`, authentication services, session/token handling).

---

## Examples (customers / orders)

```yaml
freshness:
  canonical:
    entity:customer:
      hotspot_rank: 3
      hotspot_score: 0.71
      primary_owner: alice@example.com
      primary_owner_pct: 62
      bus_factor_flag: false
      last_modified: '2026-05-08'
    entity:order:
      hotspot_rank: 1
      hotspot_score: 0.92
      primary_owner: bob@example.com
      primary_owner_pct: 84
      bus_factor_flag: true
      last_modified: '2026-05-12'
    role:order-approver:
      hotspot_rank: 7
      hotspot_score: 0.41
      primary_owner: carol@example.com
      primary_owner_pct: 58
      bus_factor_flag: false
      last_modified: '2026-05-01'
```

Reviewer interpretation:

- A PR touching `entity:order` trips both gates — require second-reviewer
  evidence AND `bob@example.com` acknowledgement (bus-factor).
- A PR touching `entity:customer` trips the second-reviewer gate only.
- A PR touching `role:order-approver` does not trip the hotspot threshold, but
  because the node lives in the `role:*` family, security still scopes a
  targeted threat-model pass when authorization logic changes.

---

## Regeneration

```bash
# Recompute hotspot/ownership signals into coverage-report.yaml
python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/hotspots.py

# Or as part of standard validation closeout
python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report
```

Cadence:

- After each feature close (alongside symbol-layer regeneration).
- At release-readiness checkpoints.
- On demand when reviewer or architect needs fresh signals.

---

## How signals compose

| Signal | Used by | Decision lever |
|---|---|---|
| `hotspot_rank` / `hotspot_score` | Code reviewer | Pick second reviewer; tighten review depth |
| `primary_owner` / `primary_owner_pct` | Code reviewer, Architect | Reviewer routing; knowledge-share planning |
| `bus_factor_flag` | Architect, Code reviewer | Knowledge-share follow-ups; PR acknowledgement |
| Hotspot ∩ `role:*` / `policy_rule:*` | Security | Targeted threat-model review |

Phase 4 (risk score) combines hotspot signals with blast, cochange, and
test-gap into a single 0–10 number — see `risk-scoring-guide.md` once Phase 4
lands.

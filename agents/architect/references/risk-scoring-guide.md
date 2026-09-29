# Risk Scoring Guide

`{NEBULA_PRODUCT_ROOT}/scripts/kg/risk.py` collapses the structural and behavioral KG
signals from Phases 1–3 into a single integer risk score (0–10) plus reviewer
recommendations. It is a **pre-flight check**, not a gate of record. Per
`solution-ontology.yaml.authority.precedence`, raw artifacts and human review
remain authoritative on conflict.

Use the score to:

- Decide whether a structural change needs an additional reviewer.
- Decide whether a build/merge needs an explicit `workstate.py decision`
  acknowledgement.
- Surface non-obvious coupling (co-change, bus-factor) before edits begin.

---

## Signals

Each signal is normalized to `[0.0, 1.0]`. Missing inputs degrade to `0.0`.

| Signal | Source | Normalization |
|---|---|---|
| `blast_count` | `blast.py` direct + one-hop neighbor count for the target | `min(1.0, (direct + neighbor) / 20)` |
| `hotspot_score` | Phase 3 `coverage-report.yaml.freshness.canonical.<node>.hotspot_score`; live `hotspots.py` fallback when missing | Already `[0, 1]` |
| `cochange_density` | `cochange.py` distinct co-change partners over the last 12 months (above `min-commits` threshold) | `min(1.0, distinct_partners / 40)` (saturates at 40 partners; products with tighter coupling baselines may override via a product-local ADR) |
| `ownership_concentration` | `primary_owner_pct` from Phase 3 | `primary_owner_pct / 100` |
| `test_gap` | `code-index.yaml` declared paths: counts files under `*tests*` buckets vs the rest | `0.0` when no impl files; `1.0` when impl > 0 and tests = 0; else `max(0, 1 − tests/impl)` |

`risk.py` reads `coverage-report.yaml` first to avoid re-running git history,
then falls back to live `compute_hotspots` for any node not yet covered.

---

## Weights

```
blast_count             × 2.0
hotspot_score           × 3.0
cochange_density        × 1.5
ownership_concentration × 1.5
test_gap                × 2.0
                        -----
                  total  10.0
```

Weights sum to 10 so the weighted sum lands in `[0, 10]`. The score is
`round(weighted_sum)`, clamped to `[0, 10]`.

`hotspot_score` carries the largest weight: a node concentrated at the top of
the change distribution is the strongest single predictor of regression risk.
`blast_count` and `test_gap` are next because they describe structural reach
and verification gap. `cochange_density` and `ownership_concentration` are
secondary correctives — they push the score up when coupling or knowledge silo
are present even though raw activity is low.

A product may tighten or relax these weights in a product-local overlay if
telemetry justifies it. Record the override in a product ADR and reference it
from `coverage-report.yaml`. Do not edit `risk.py` weights without that ADR.

---

## Score bands

| Band | Score | Meaning | Required action |
|---|---|---|---|
| `routine` | 0–3 | Edit is low-impact; standard review applies | None beyond default review |
| `elevated` | 4–6 | Concentrated risk on one or two signals | Reviewer notes the elevated signal; no extra reviewer required unless a Phase 3 gate trips |
| `high` | 7–8 | Multiple signals concentrated | **Reviewer gate**: require an additional reviewer (`kg.risk ≥ 7`) |
| `critical` | 9–10 | Severe concentration across signals | **Build gate**: require an explicit `workstate.py decision --topic risk-acknowledgement` entry before merge |

The reviewer gate is enforced by `agents/code-reviewer/SKILL.md` and
`agents/actions/review.md`. The build gate is enforced by
`agents/actions/build.md` and applies before the final merge step.

---

## When to call `risk.py`

| Role | Cadence |
|---|---|
| Backend / frontend / ai engineer | Before structural edits to a bound canonical node (file, method body, or symbol that resolves to a node) |
| Code reviewer | When triaging a PR — once per touched node, or once for the PR's primary node |
| Architect | At release-readiness checkpoints, scan for high/critical concentrations |
| Security | When triaging review scope on auth/policy nodes; pair with the hotspot review guide |

---

## Inputs and output shape

```bash
# By canonical node
python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/risk.py entity:customer

# By file (resolves to all bound nodes; primary node = highest score)
python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/risk.py --file backend/src/Application/Services/CustomerService.cs

# By symbol (requires symbol-index.yaml)
python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/risk.py --symbol CancelAsync --node entity:customer

# Narrative
python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/risk.py entity:customer --reason
```

JSON output (default):

```json
{
  "query": {"node": "entity:customer"},
  "mode": "node",
  "score": 7,
  "band": "high",
  "primary_node": "entity:customer",
  "signals": {
    "blast_count": 0.55,
    "hotspot_score": 0.71,
    "cochange_density": 0.30,
    "ownership_concentration": 0.62,
    "test_gap": 0.50
  },
  "raw": {
    "blast":     {"direct_node_count": 1, "neighbor_node_count": 10, "resolved_file_count": 18},
    "hotspot":   {"hotspot_rank": 3, "primary_owner": "alice@example.com", "primary_owner_pct": 62, "bus_factor_flag": false, "last_modified": "2026-05-08"},
    "cochange":  {"density": 0.30, "partner_count": 3, "partners": [{"node": "entity:order", "co_commits": 6}]},
    "test_gap":  {"test_files": 2, "impl_files": 4, "test_gap": 0.50}
  },
  "reviewer_recommendations": [
    "kg.risk ≥ 7 — additional reviewer required before merge.",
    "Test gap: 2 test file(s) vs 4 impl file(s) — add coverage before merge.",
    "Wide blast radius — run `blast.py` and walk downstream nodes before merging."
  ],
  "weights": {"blast_count": 2.0, "hotspot_score": 3.0, "cochange_density": 1.5, "ownership_concentration": 1.5, "test_gap": 2.0}
}
```

`per_node[]` carries the same shape for every bound node when the target was a
file or feature/story; `primary_node` is the node with the highest score and
its values are surfaced at the top level.

---

## Examples (customers / orders)

| Target | Score | Why |
|---|---|---|
| `entity:customer` after a routine field rename | 2 (`routine`) | Small blast, hotspot rank 14, tests present, no co-change partners — score is dominated by ownership only |
| `entity:order` after adding a state to its workflow | 7 (`high`) | hotspot_rank 1, primary_owner_pct 84 (bus-factor), wide blast across endpoints, test files lag impl files |
| `entity:order.SubmitAsync` after fixing a workaround | 8 (`high`) | Symbol-level edit reaches `entity:invoice` and `entity:fulfillment` via callees; blast_count and test_gap both ≥ 0.6 |
| `policy_rule:order-approver` after broadening approval scope | 9 (`critical`) | hotspot_score 0.91, primary owner is sole maintainer, no tests under `tests` bucket — build gate trips |

For the critical case the engineer must record an explicit decision before
merge, e.g.:

```bash
python3 {NEBULA_PRODUCT_ROOT}/scripts/kg/workstate.py \
  --state-file .kg-state/workstate.yaml \
  decision "Approved policy_rule:order-approver scope broadening" \
  --topic risk-acknowledgement \
  --rationale "kg.risk = 9; primary_owner acknowledged in PR; threat-model pass attached" \
  --files engine/src/Application/Policies/OrderApproverPolicy.cs
```

---

## Relationship to other gates

`risk.py` is a roll-up. The underlying gates remain authoritative:

- Phase 3 hotspot gates (`hotspot_rank ≤ 5`, `bus_factor_flag: true`) still
  apply on their own — even if the risk score is low, a touched hotspot needs
  second-reviewer evidence.
- Phase 4 build gate (`kg.risk ≥ 9`, critical) is additive to existing build
  protocol checks; it does not replace lifecycle or CI gates.
- The risk score does not consult planning-mds artifacts directly — only the
  derived KG signals. Authority on intent still lives in feature folders and
  ADRs.

---

## Failure modes and degradation

| Condition | Behavior |
|---|---|
| `coverage-report.yaml` missing | Live `compute_hotspots` is invoked; first call is slower |
| `symbol-index.yaml` missing | `--symbol` mode fails; node and file modes still work |
| No git history (`--months` window empty) | `cochange_density` = 0.0; signal contribution drops out |
| Target binds to no canonical node | `risk.py` exits non-zero with a clear message |
| Target resolves to many nodes (file/feature) | Score reported for the highest-risk node; full per-node breakdown under `per_node` |

The CLI never crashes silently; missing inputs degrade the score downward,
which biases toward false negatives (under-flagging) rather than false
positives. Reviewers should still apply Phase 1–3 gates independently.

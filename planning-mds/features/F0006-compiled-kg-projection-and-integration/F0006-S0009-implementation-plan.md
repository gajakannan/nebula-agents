# F0006-S0009 — Implementation Plan (Framework Contract, Roles & Docs Reconciliation)

> **Living tracker for the B6 build — the closing story of F0006.** Companion to
> [`F0006-S0009-framework-contract-reconciliation.md`](./F0006-S0009-framework-contract-reconciliation.md).
> Builds on S0001–S0008 (all shipped). Makes the written contract match the shipped compiled-projection
> + integrator behavior. Entirely in `nebula-agents`. Update §9 as work lands.

| Field | Value |
|-------|-------|
| Story | F0006-S0009 (PRD row **B6**) |
| Phase | B — Compiled projection (closes Phase B **and** F0006) |
| Status | **Done — 2026-07-11** (contract reconciled; audit clean; Architect + Code Reviewer PASS). Closes Phase B. Feature-level closeout is a separate maintainer step (D-closeout) |
| Created | 2026-07-11 |
| Branch | `feat/F0006-phase-B-compiled-projection` (nebula-agents; unpushed) |
| Signoff required | Architect (owns reconciliation) + Code Reviewer |
| Touches `main` | **No** — feature branch |

---

## 0. Scope

Update every action, prompt, ownership boundary, template, and doc so a strict agent obeying the
letter of the contract performs correctly at every gate — **no remaining description of hand-maintained
graph files, PM repoints, physical feature-doc refs in shards, trusting a clean merge of generated
files, or any path bypassing the integrator on graph/tracker files.** Docs ship **last** (after the
mechanism), so nothing describes unshipped behavior.

**Already landed (don't redo):** integrator persona/`integrate.md`/README+ROUTER routing + the runbook
integration section (S0003); `ci-gates-template.yml` job (S0008). **Remaining:** the items below.

---

## 1. The reconciliation surface

The audit grep (`grep -riE 'canonical-nodes|feature-mappings|code-index|regenerate-symbols|
regenerate-decisions' agents/`) hits **45 files** — most are legitimate mentions; S0009 edits the
subset that describes pre-compile behavior (the PRD "Framework Edit Inventory") and sweeps the rest for
uninventoried stale text. Concrete edit targets:

| Surface | Change |
|---------|--------|
| `agents/agent-map.yaml` | **Remove** every authoring write-scope to a now-generated file (§2) |
| `agents/actions/feature.md` | G7 = author shards + compile + validate; G8 archive = shard `path:`/`status:` edit + recompile; exit includes `--check-reproducible`; delete the off-book repoint narrative |
| `agents/actions/build.md`, `plan.md` | the 2026-07-05 KG-regeneration gate commands → the `compile.py`-driven flow; authored-file wording → shards |
| `templates/prompts/evidence-contract/{feature,build,plan}-{operator-friendly,automation-safe}.md` | same regeneration reconciliation (the "code paths only, stable across archive" claim becomes true) |
| `agents/product-manager/scripts/validate-feature-evidence.py` (+ tests) | matchers learn `compile.py`, gated on a new `contract_effective_date` (§3) |
| `agents/docs/KNOWLEDGE-GRAPH.md` | classification, shard schema, compile flow, logical refs, merge taxonomy, `depends_on` single-home; **F0005 gap closed in prose** (logical refs the only authoring form; off-book-repoint narrative gone) |
| `agents/docs/ORCHESTRATION-CONTRACT.md` | integrator role + mainline sole-writer rule + conflict routing |
| `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md` | add the Phase-B compile-flow steps to the maintainer procedure (integration section already landed S0003) |
| `templates/kg-reconciliation-template.md`, `feature-assembly-plan-template.md`, `tracker-governance-template.md`, `feature-registry-template.md` | shard-based reconciliation + logical-ref examples; generated-region markers on the trackers |
| `TRACKER-GOVERNANCE.md` (this repo's) | note which product-repo trackers became generated + that `nebula-agents` has not adopted the shard model (D-self-adoption) |

Each edited surface cites the story/PRD section that made the old text wrong (review traceability).

---

## 2. agent-map scope removal (the testable core)

Remove these authoring write-scopes (now `compile.py` outputs), **symmetrically**:
- **PM** (line 39): `knowledge-graph/feature-mappings.yaml`.
- **Architect** (lines 61–64): `canonical-nodes.yaml`, `feature-mappings.yaml`, `code-index.yaml`,
  `solution-ontology.yaml` (the ontology scope is already **relocated** to `kg-source/ontology/**`, added S0004 — so this is removal of the stale monolith line).
- **Keep** `coverage-report.yaml` (a `--write-coverage-report` regeneration, not a hand-edit).
- **Integrator** (lines 228–234): flip annotations — the curated trio from "via merge3 only" and
  REGISTRY/ROADMAP from "via tracker merge only" → "regenerated via `compile.py`".

**Invariant after:** no `knowledge-graph/*.yaml` (except `coverage-report.yaml`) in any authoring
role's write scope — only the integrator's generated-output scope and the compiler produce them. Every
"X owns Y" statement traces to exactly one primary `kg-source/**` scope (+ zero-or-more co-sign), and
the map matches S0004's ownership map exactly. The one documented sub-file split is REGISTRY/ROADMAP
(PM prose via `features/**`; integrator regenerates fenced regions — encoded by the `fenced-region`
marker in `generated_paths.yaml`, S0008, not two whole-file scopes). Verified by `validate_agent_map.py`
+ a new ownership-map assertion.

---

## 3. Regeneration-command reconciliation (evidence-matcher gate)

The 2026-07-05 "Enforce generated KG regeneration" surfaces tell agents to run
`validate.py --regenerate-symbols/--regenerate-decisions/--write-coverage-report` at G7. Post-cutover
the sanctioned entry is the **`compile.py`-driven flow** (compile emits the trio + drives the
generators). `validate-feature-evidence.py`'s matchers must **accept `compile.py`** as the regeneration
command — gated on a new `contract_effective_date` (as the 2026-07-05 rule was) so evidence from earlier
runs stays valid. Tests updated with a before/after `contract_effective_date` fixture.

---

## 4. Contract audit (grep-able, zero violations)

A re-runnable audit asserting **zero** framework files instruct/imply: hand-editing a generated file;
PM edits to architect-owned graph files; physical `planning-mds/features/…` refs in shard authoring
guidance; trusting a clean merge of generated files; any merge path bypassing the integrator on
graph/tracker files. Plus the uninventoried-mention sweep (§1 grep). Checklist stored with evidence.

---

## 5. What's explicitly out of scope

New behavior (all mechanisms shipped S0001–S0008); historical evidence runs (append-only); retroactive
edits to F0038/PR #47 records; `nebula-agents` adopting the shard model for its **own** planning graph
(D-self-adoption → follow-up).

---

## 6. Decisions (resolved 2026-07-11)

> **Confirmed:** **D-evidence-date** = gate the `compile.py` matcher on `contract_effective_date >=
> 2026-07-11` (earlier evidence keeps the `validate.py --regenerate-*` matchers). **D-self-adoption** =
> **defer** (S0009 only documents that nebula-agents hasn't adopted the shard model). **D-audit-form** =
> a re-runnable script (`agents/scripts/audit-contract.py`) + checklist in evidence. **D-closeout** =
> the F0006 feature-level closeout runs as a **separate maintainer-triggered step** after S0009. Details
> below.

- **D-evidence-date — the `contract_effective_date` gate.** `validate-feature-evidence.py` accepts
  `compile.py` as the regeneration command for runs whose contract date is on/after the cutover.
  **Recommendation:** gate on **2026-07-11** (Phase-B-complete); earlier evidence keeps the
  `validate.py --regenerate-*` matchers. Confirm the date.
- **D-self-adoption — does `nebula-agents` adopt the shard model for its own KG now?** **Recommendation:**
  **no — follow-up** (this repo has no populated KG; the story's own proposal). S0009 only *documents* in
  `TRACKER-GOVERNANCE.md` that the product repo's trackers are generated and this repo hasn't adopted.
  Confirm defer.
- **D-audit-form — how to deliver the contract audit.** **Recommendation:** a small re-runnable script
  (`agents/scripts/audit-contract.py` or documented grep assertions) + a completed checklist in the
  story evidence, so the "zero violations" claim is reproducible. Confirm script vs. checklist-only.
- **D-closeout — after S0009, close F0006?** S0009 is the last story. **Recommendation:** land S0009,
  then run the feature-level closeout (feature-review + signoff matrix) as a **separate step** you
  trigger; S0009's plan does not auto-close the feature. Confirm.

---

## 7. File inventory

**Framework repo `nebula-agents` only:** the §1 table's files, plus this plan + STATUS/README/STORY-INDEX
tracking, plus (D-audit-form) an audit script + its output. No product-repo changes.

---

## 8. Test plan (Code-Reviewer signed)

`validate_agent_map.py` green after scope removal + a new assertion that no `knowledge-graph/*.yaml`
(except `coverage-report.yaml`) is in an authoring write scope; `validate-feature-evidence.py` tests for
the `compile.py` matcher gated on `contract_effective_date` (before = old matcher, after = compile
accepted); the contract audit runs clean (zero violations) + the uninventoried-mention sweep; the
F0005-gap prose assertion (KNOWLEDGE-GRAPH.md documents logical refs as the only authoring form).

---

## 9. Progress checklist

- [x] Decisions D-evidence-date / D-self-adoption / D-audit-form / D-closeout resolved (2026-07-11)
- [x] `agent-map.yaml` authoring scopes removed (§2); integrator annotations flipped; `validate_agent_map.py` green + ownership assertion
- [x] `feature.md` G7/G8 reconciled (shards + recompile + `--check-reproducible`; off-book repoint narrative gone)
- [x] `build.md`/`plan.md` + the 6 prompt variants: regeneration commands → compile-driven flow
- [x] `validate-feature-evidence.py` learns `compile.py` (contract_effective_date gate) + tests
- [x] `KNOWLEDGE-GRAPH.md` / `ORCHESTRATION-CONTRACT.md` / `MANUAL-ORCHESTRATION-RUNBOOK.md` reconciled; F0005 gap closed in prose
- [x] Templates (`kg-reconciliation`, `feature-assembly-plan`, `tracker-governance`, `feature-registry`) → shards + logical refs
- [x] `TRACKER-GOVERNANCE.md` note (product trackers generated; nebula-agents unadopted)
- [x] Contract audit clean (zero violations) + uninventoried-mention sweep; checklist in evidence
- [x] STATUS provenance (Architect + Code Reviewer); story index updated
- [ ] (separate, pending) feature-level closeout for F0006 — maintainer-triggered (feature-review + final signoff matrix + any promotion to main). NOT part of S0009 per D-closeout.
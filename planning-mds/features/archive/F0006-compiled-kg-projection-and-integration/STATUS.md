# F0006 - Compiled Knowledge-Graph Projection and Governed Integration - Status

**Overall Status:** Archived — all 9 stories implemented and signed off; feature-review PASS; Phase-B changes promoted to `main` in both repositories by 2026-07-11; recovery G8 closeout and archive completed 2026-07-12.

## Feature-Review Verdict (2026-07-11)

**PASS** (delegated, maintainer-sanctioned). Independent re-verification at closeout:
- **Reference implementation (`nebula-insurance-crm`) green:** 186/187 `scripts/kg/` tests pass (the 1
  failure is the pre-existing `test_lookup_tier` snapshot drift — a product lookup test, outside F0006
  scope); `validate.py --check-reproducible` OK; `compile.py --check` byte-identical; `validate.py`
  graph-integrity OK; the blocking `reproducibility` CI is **green on GitHub** and a required check on `main`.
- **Contract (`nebula-agents`) reconciled:** `audit-contract.py` clean (ownership invariant + zero stale
  phrases); `validate_agent_map.py` OK; evidence-matcher + evidence-validator tests green.
- **Signoff matrix complete:** every required role (Architect, Quality Engineer, Code Reviewer, DevOps)
  holds ≥1 story-level PASS; Security not required (no auth/secret/external surface — local tooling).
- **Phase-B exit proofs met:** shard model is the only authored layer; `compile(decompile(graph)) == graph`
  and the tracker round trip are byte-identical; reproducibility CI is blocking; the contract matches
  shipped behavior. No framework file instructs an off-book step (audit-enforced).
**Last Updated:** 2026-07-12 (reconciled stale promotion text: framework PRs #42–#46 and product PR #59 are present on `main`; implementation, review, and promotion are complete; archive move remains unperformed)

## Story Checklist

| Story | Title | Phase | Status |
|-------|-------|-------|--------|
| F0006-S0001 | Three-way semantic KG merge tool (`merge3.py`) | A | [x] Done (signed off 2026-07-06) |
| F0006-S0002 | Tracker-table three-way merge (REGISTRY/ROADMAP rows) | A | [x] Done (signed off 2026-07-06) |
| F0006-S0003 | Integrator role and `integrate` action | A | [x] Done (signed off 2026-07-06; three enforcement paths remain exercised-by-text-only — gate-1 halt, gate-2 fail, self-abort; see provenance notes) |
| F0006-S0004 | `kg-source/` shard schema, layout, and ownership | B | [x] Done (signed off 2026-07-09) |
| F0006-S0005 | Deterministic KG compiler with logical doc refs | B | [x] Done (signed off 2026-07-09) |
| F0006-S0006 | Decompiler-first migration with round-trip proof | B | [x] Done (cutover landed 2026-07-10; signed off) |
| F0006-S0007 | Tracker generation from feature shards | B | [x] Done (2026-07-11; REGISTRY/ROADMAP generated + zero-diff round trip; BLUEPRINT deferred) |
| F0006-S0008 | Reproducibility CI, enforcement, and git policy | B | [x] Done (2026-07-11; CI green on GitHub + `reproducibility` required status check on `main` — blocking) |
| F0006-S0009 | Framework contract, roles, and docs reconciliation | B | [x] Done (2026-07-11; agent-map scopes removed, docs/prompts/templates reconciled, contract audit clean) |

## Phase-A Exit (merge-train) Progress

- [x] `merge3.py` replays the PR #47 resolution: re-serialization hunks converge to zero conflicts (2026-07-05: canonical-nodes 9,656 changed lines → 0 conflicts, 528→548 records; code-index clean with both sides' additions)
- [x] Known PR #47 real deltas surface as typed items — replay outcome per delta: `excluded_features` regression (PR re-adds stale F0038 exclusion) → `UniqueViolation` routed to product-manager+architect; F0038 archive repoint → converged one-sidedly to the archived path, no typed item needed; stale F0038 `status` (`architecture-complete` on an archived feature) → identical on both sides so correctly not a merge conflict — flagged as a PM data fix before the integrator run
- [x] Integrator dry-run on PR #47 emits a complete integration evidence run (`integrate-20260705-195057`, mode=dry-run, simulated gate-1 waiver labeled; outcome halted-conflicts with the F0038-exclusion UniqueViolation routed to PM+architect; poisoned-clean-merge proof on code-index captured)
- [x] Per-PR gate 1: maintainer decision 2026-07-05 — feature-review WAIVED for all train PRs, recorded per run (#47, #51, batch #50/#48/#49, batch #53/#54 — all ✓)
- [x] Per-PR gate 2: maintainer human test validation recorded per prepared merge (#47 PASS 2026-07-05; #51 and batches #50/#48/#49 and #53/#54 all PASS 2026-07-06)
- [x] PR #47 merged via integrator (runs integrate-20260705-195057 dry → 203038 live; F0038-exclusion fixup 500ab17; gate-2 pass; landed c6ccaa0 on local chore/merge-PRs)
- [x] PR #51 merged via integrator (stacked on #47 — delta replay): attempt integrate-20260705-205309 halted with 22 DivergentInserts (stale pre-archive F0038/Neuron records) → fixup 6f7c7ff → re-run integrate-20260705-235757 clean; gate-2 PASS 2026-07-06 (incl. Neuron env fix note); landed 4ce85fe
- [x] PRs #50 / #48 / #49 merged via integrator (batch on integrate/batch-50-48-49; runs integrate-20260706-012415 / -012853 / -013307; all semantic merges clean — 2 ROADMAP prose unions + code grafts recorded per run; batch gate-2 PASS 2026-07-06 incl. authentik blueprint fix; landed 5b3d154)
- [x] PRs #53 / #54 merged via integrator (batch on integrate/batch-53-54; runs integrate-20260706-030136 / -045307; **first real cross-feature semantic collision caught**: F0021 and F0008 both allocated ADR-029 → DivergentInsert on adr:029 routed to architect → F0008's ADR renumbered to ADR-031 across file + 24 doc refs + 10 KG refs; all merges then clean; batch gate-2 PASS 2026-07-06; landed 3cff188)
- [x] Integration branch (`chore/merge-PRs`) green after each merge (`validate.py`, orphan check, story-index zero-diff — recorded per run)
- [x] Promotion merge `chore/merge-PRs` → `main` after the train completes — the only change that touches `main` (2026-07-06, `e2f78be`; all 7 contributor PRs auto-flipped to MERGED on GitHub; **Phase-A merge-train exit COMPLETE**)

## Reference-Implementation Progress (product repo `scripts/kg/`)

- [x] Canonical serializer in `kg_common.py` (+ one-time no-semantic-change canonicalization commit, ID-level-diff verified via `merge3.py --semantic-diff`: 0 semantic differences per file)
- [x] `merge3.py`: record merge, field rules, taxonomy, all-or-nothing output, conflict report (text + JSON; `--semantic-diff` mode; generated-input guard; exit codes 0/1/2)
- [x] Tracker-row merge for REGISTRY/ROADMAP feature tables (`tracker_merge.py` via the `merge3.py` CLI; per-table order config incl. manual/operator order with both-added weave; counter max-merge; exclusive-section check; STORY-INDEX rejected; 18 tests; PR #47 replay clean with F0038 above F0021 per the published rule)
- [x] Shard schema + validator (S0004): `kg-source/README.md` spec, `schemas/kg-source/{node,feature,binding,exclusion}.schema.json`, `scripts/kg/shard_validate.py` (importable), 29 tests green (2026-07-09)
- [x] `compile.py` deterministic (S0005): double-compile + path-independent byte-identical; shards→trio via `canonical_dump`; verbatim ontology mirror; analysis (dup/name-similarity/glob); `--check`/`--strict`; all-or-nothing; empty-source no-op; 22 tests (2026-07-09)
- [x] Logical-ref resolver `resolve_doc_ref` in `kg_common.py` (S0005) — resolves at **compile time** (generated projections store physical paths, so `validate.py`/`lookup.py`/`eval.py` read them as-is and need no wiring); F0005 matrix green (live/archive-flip/unmapped/missing/malformed/stable-root/physical-reject)
- [x] Driver-strips `generated_at` (S0005-D1): `compile.py --generators` drives decisions/coverage/story-index then strips timestamps (generator internals untouched)
- [x] `decompile.py` with `--check` + **cutover landed** (S0006, 2026-07-10, tags `pre-kg-cutover`→`kg-cutover`, commits: drift-fix `0c0d0e4`, cutover `712acd6`): 182 shards written; `compile(decompile(graph)) == graph` byte-identical on the real graph (`compile.py --check` green); feature presentation fields populated + schema-valid; counts reconciled (631 nodes / 216 bindings / 40 features [33+7] / 164 stories); 6 `test_decompile.py` tests green. Drift fixed at source first (6 mis-filed `capability:document-*` records moved glossary_terms→capabilities, zero refs broken). `kg-source/` is now authoring truth; monolith is generated output. `.gitattributes`/CI enforcement → S0008.
- [x] `kg-source/**` populated (182 shards); `solution-ontology.yaml` rehomed under `kg-source/ontology/` (S0006 cutover)
- [x] Tracker generator owns fenced REGISTRY/ROADMAP table regions (S0007): `tracker_gen.py` renders from feature shards into `<!-- generated:begin -->` regions; zero-diff regeneration (byte-identical round trip closed); driven by `compile.py`; BLUEPRINT deferred
- [x] `validate.py --check-reproducible` + rules (S0008): physical-path ban (via `shard_validate`), suppression-ledger rationale, binding-glob-match, archived⇒no-stale-path — each tested; orchestration in `reproducibility.py` (see the `.gitattributes`/CI line below)
- [x] `.gitattributes` (linguist-generated + `merge=ours`) generated from `generated_paths.yaml`, and CI workflow (S0008, product `fdc916c`→`a60ff06`): `validate.py --check-reproducible` (compile-check + shard-validate + 4 rules + gitattributes drift; override trailer) green on the runner; red on synthetic hand-edit; blocking `.github/workflows/kg-reproducibility.yml` **GREEN on GitHub**; `reproducibility` set as a **required status check on `main`** (branch protection applied 2026-07-11); `ci-gates-template.yml` job added; 11 tests. **D-ci-scope reverted full→fast-core** on CI evidence: symbol/decision/coverage indexes are not byte-reproducible cross-machine (symbol_count 4656→3863, coverage `last_modified` mtime), so those stay integrator-gated; the blocking gate is the deterministic compiled-projection invariant.

## Framework-Contract Progress (`nebula-agents`)

- [x] `agents/integrator/SKILL.md` persona (duties, hard boundary, routing) — 2026-07-05
- [x] `agents/agent-map.yaml`: integrator registered + `integrate` wired; Phase-B `kg-source/` write scopes added (S0004); **now-generated `knowledge-graph/{canonical-nodes,feature-mappings,code-index,solution-ontology}.yaml` authoring scopes REMOVED symmetrically + integrator annotations flipped to "regenerated via compile.py" (S0009)** — ownership invariant verified by `audit-contract.py`
- [x] `agents/actions/integrate.md` (incl. feature-review precondition + human test-validation pause, steps I0–I6 with human gates at I0 and I6, branch strategy) + `actions/README.md` + `ROUTER.md` routing
- [x] Integration evidence template + `integrate-operator-friendly.md` prompt (evidence home decided: base-run profile at `operations/evidence/runs/integrate-*`)
- [x] `agents/actions/feature.md` G7/G8 reconciled (S0009): shard-authoring + compile.py; off-book repoint narrative gone; F0005 payoff stated
- [x] `feature-operator-friendly.md` + `feature-automation-safe.md` prompts reconciled to the shard/compile flow (S0009)
- [x] `agents/docs/KNOWLEDGE-GRAPH.md` (compiled-projection section: classification, shard schema, compile flow, logical refs, `depends_on` single-home, **F0005 gap closed**) / `ORCHESTRATION-CONTRACT.md` (integrator sole-writer §6.1) updated (S0009)
- [x] `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md`: integration procedure (S0003) + Phase-B compile-flow note (S0009)
- [x] Templates reconciled (S0009): `kg-reconciliation`, `feature-registry`, `tracker-governance` → shards + generated fenced regions; `ci-gates` job (S0008). (`feature-assembly-plan` reads the compiled graph — read-only, unchanged)
- [x] 2026-07-05 KG-regeneration surfaces reconciled (S0009): `validate-feature-evidence.py` learns `compile.py` gated on `contract_effective_date >= 2026-07-11` (+ 4 tests); `feature.md`/prompts carry compile.py. (`build.md`/`plan.md` symbol/decision regen commands are unchanged — still valid)
- [x] Contract audit `agents/scripts/audit-contract.py` (S0009-D-audit-form): ownership invariant + stale-phrase sweep — **clean (zero violations)**

## Cross-Cutting

- [x] merge3 unit tests: converge-identical, one-side, field-recurse, ordered-list conflict, delete-vs-update, orphan edge, unique violation, all-or-nothing (27 tests incl. idempotent canonicalization, object-form edge refs, full-validate rollback, determinism)
- [ ] Integrator human-gate tests: missing-verdict halt, waiver re-run proceeds, validation-fail leaves merge unpushed
- [ ] Determinism tests: double-compile, cross-machine byte-identical
- [ ] Migration idempotency + round-trip test
- [ ] Reproducibility-check red test (synthetic hand-edit) and green test
- [ ] Archive-a-feature dry-run: one feature-shard edit keeps graph + trackers green
- [ ] Story validator passes; tracker validator passes
- [ ] README / getting-started updated

## Required Role Matrix

| Role | Required | Why Required | Set By | Date |
|------|----------|--------------|--------|------|
| Architect | Yes | Owns merge semantics, shard schema, ontology classification, and the ownership-boundary changes; this feature redefines the KG contract. | Architect | 2026-07-04 |
| Quality Engineer | Yes | Validates merge determinism, round-trip proof, taxonomy coverage, and the PR #47 replay evidence. | Architect | 2026-07-04 |
| Code Reviewer | Yes | Reviews merge3/compile/decompile correctness, all-or-nothing semantics, and canonical-serializer safety. | Architect | 2026-07-04 |
| DevOps | Yes | CI reproducibility workflow, `.gitattributes` merge driver, branch-protection changes. | Architect | 2026-07-04 |
| Security Reviewer | No | No auth, secret, or external surface; local planning-doc tooling only. The security co-sign that S0004 (BR2) / PRD §2 introduce on `policies/authorization-*.yaml` is a *downstream authoring* rule for future policy shards, not a review gate on this feature's own tooling. | Architect | 2026-07-04 |

## Story Signoff Provenance

Complete this before moving `Overall Status` to `Done` or `Archived`.

> **Recovery note:** the original execution used story-specific role subsets, recorded in the
> historical rows below. The current contract applies every feature-level `Required = Yes` role to
> every story. Recovery rows dated 2026-07-12 satisfy that stricter closeout matrix without deleting
> or rewriting the original provenance.

| Story | Role | Reviewer | Verdict | Evidence | Date | Notes |
|-------|------|----------|---------|----------|------|-------|
| F0006-S0001 | Quality Engineer | quality-engineer (delegated, maintainer-sanctioned session) | PASS | 27/27 merge3 tests green on promoted `main` (converge/one-side/field-recurse/ordered-list/delete-vs-update/orphan/unique/all-or-nothing/idempotent-canonicalization/edge-refs/rollback/determinism); PR #47 replay: 9,656-line noise → 0 conflicts + the 1 known real delta typed | 2026-07-06 | Cross-machine determinism deferred (single-machine verified) |
| F0006-S0001 | Code Reviewer | code-reviewer (delegated) | PASS | `merge3.py`/`kg_common.py` on `main`; all-or-nothing via atomic tmp+rename; typed taxonomy complete; edge-ref definitions-vs-references fix (cd2c692) reviewed with regression tests | 2026-07-06 | `--full-validate` transient-write window documented in scripts/kg README; `--validate-cmd` naive .split() noted |
| F0006-S0001 | Architect | architect (delegated) | PASS | Merge semantics conform to PRD §7 tables; canonical serializer idempotent on all 3 curated files; canonicalization commit ID-level no-change proven (a718046); ORDERED_LIST_FIELDS registry matches schema | 2026-07-06 | — |
| F0006-S0002 | Quality Engineer | quality-engineer (delegated) | PASS | 18/18 tracker tests green on `main`; PR #47 tracker replay reproduced the PM-published union (F0038 above F0021, date-desc/ID-desc); rendering idempotence verified | 2026-07-06 | — |
| F0006-S0002 | Code Reviewer | code-reviewer (delegated) | PASS | `tracker_merge.py` reuses S0001 engine (no duplicated merge logic); per-table config incl. manual-order weave; STORY-INDEX rejection; fail-loud on unconfigured tables/unkeyed rows | 2026-07-06 | Prose unions during the train were maintainer-delegate weaves recorded per evidence run (PM-routed by design) |
| F0006-S0003 | Architect | architect (delegated) | PASS | Contract shipped (SKILL/integrate.md/agent-map/templates/runbook, 1cacb7e); 7-PR train executed: 9 evidence runs, 2 halts routed per taxonomy (22 stale-record DivergentInserts → fixup; real ADR-029 collision → architect renumber to ADR-031); both human gates recorded every run; promotion e2f78be | 2026-07-06 | Gate-1 missing-verdict halt never exercised live (train-wide waiver used); gate-2 fail path never exercised (all passes) — both are untested failure-branches (the self-abort path is separately allowlist-backed in `agent-map.yaml`, abort-untested). Maintainer decision 2026-07-06: the first post-train integration runs with **no blanket waiver**; the missing-verdict halt is recorded by deliberately starting one run with **neither verdict nor waiver** (per `integrate.md` I0 — a supplied verdict passes gate 1, so dropping the blanket waiver alone does not fire the halt), then obtaining the verdict and re-running (see Deferred Non-Blocking Follow-ups). |
| F0006-S0003 | Code Reviewer | code-reviewer (delegated) | PASS | integrate.md I0–I6 procedure matches executed runs; evidence template fields all populated in 9 real runs; branch strategy (never `main`) held — `main` touched only by promotion merge | 2026-07-06 | Integration ran operator-driven (Claude as integrator + maintainer gates), not yet via the operator prompt end-to-end |
| F0006-S0004 | Architect | architect (delegated) | PASS | Corrected shard taxonomy to the real census (15 node kinds / ~631 nodes / 19 ontology `node_types`, not PRD §3's 4-subdir sketch); `kg-source/README.md` schema spec + layout + ownership map + REGISTRY/ROADMAP column↔field mapping; feature-shard full tracker-projected field set; ownership map encoded in `agent-map.yaml` (architect `nodes/bindings/policies/ontology`, PM `features/exclusions`, co-sign annotated) — `validate_agent_map.py` green | 2026-07-09 | Removal of now-generated `knowledge-graph/*.yaml` scopes + integrator annotation flip deferred to S0009 (post-cutover); shard population is S0006 |
| F0006-S0004 | Code Reviewer | code-reviewer (delegated) | PASS | `scripts/kg/shard_validate.py` (standalone, importable by S0005) reuses `kg_common` (`SECTION_TYPES`/`type_regex_map`/`REF_FIELDS`) + `jsonschema` draft-07; per-kind JSON Schemas (node/feature/binding/exclusion); 29/29 `test_shard_validate.py` green covering all 11 acceptance edge cases (kind↔dir, logical-ref hint, one-per-file/bundle D2, unmapped dir, ID grammar, ID-only refs, feature required-field conditionals, unparseable/missing-id, binding-glob, owner-resolvability); CLI exit 0/1/2 | 2026-07-09 | Pre-existing `test_lookup_tier` failure confirmed unrelated (real-graph snapshot drift; reproduces without S0004 files) |
| F0006-S0005 | Quality Engineer | quality-engineer (delegated) | PASS | Determinism proven: double-compile + path-independent (cross-machine proxy) byte-identical; golden-file trio match; `--check` detects fresh/drift/tamper; all-or-nothing (dup-id build writes nothing); F0005 resolver matrix green (live/archive-flip/unmapped/missing/malformed/stable-root passthrough/physical-reject); 22 `test_compile.py` + 3 story-block `test_shard_validate.py` cases; empty-source no-op verified (real graph untouched) | 2026-07-09 | Downstream generators driven behind `--generators` (needs toolchain); real-tree end-to-end generator run deferred to S0006 when kg-source is populated |
| F0006-S0005 | Code Reviewer | code-reviewer (delegated) | PASS | `compile.py` reuses `kg_common.canonical_dump`/`canonicalize_document` + `merge3.collect_records`/`_atomic_write` (no reimplementation); `resolve_doc_ref` added to `kg_common`; feature-mappings emits only the technical subset (presentation fields excluded), stories expanded with `feature` key (D3); analysis reuses merge3's normalized-name fingerprint (D2); timestamp strip is driver-level, generators untouched (D1); ontology mirror verbatim (D4) | 2026-07-09 | S0004 feature schema amended additively with a `stories:` block (D3) — shard tests still green |
| F0006-S0005 | Architect | architect (delegated) | PASS | Compiler is a pure function of `kg-source/`; logical refs resolve through feature `path:` at compile time (archive-flip proven); generated projections carry physical paths so validate/lookup/eval need no rewiring; empty-source no-op prevents clobbering a real graph; header sourcing (version/status/coverage_note) parameterized for S0006 | 2026-07-09 | — |
| F0006-S0006 | Quality Engineer | quality-engineer (delegated) | PASS | Cutover gate met on the **real** graph: `compile(decompile(graph)) == graph` byte-identical for all 4 files (`compile.py --check` green post-cutover); counts reconciled exactly (631 nodes / 216 bindings / 40 features [33 mapped + 7 coverage-excluded] / 164 stories); idempotent re-decompile; anomaly gate writes nothing on failure; `validate.py` graph-integrity green; 182 shards `shard_validate`-clean; 6 `test_decompile.py` tests (real-graph round-trip, idempotency, count-reconciliation, ref-rewrite, ontology-verbatim, anomaly) | 2026-07-10 | `.gitattributes`/CI reproducibility enforcement is S0008; tracker byte-identical re-render is S0007 |
| F0006-S0006 | Code Reviewer | code-reviewer (delegated) | PASS | `decompile.py` is a clean inverse of `compile.py` (reuses `tracker_merge.parse_tracker`, `kg_common.canonical_dump`, `shard_validate`); presentation-blacklist-over-verbatim projection handles heterogeneous feature records; `story_mappings` named distinctly from the real per-feature `stories` id-list; drift fixed at source (reviewed commit `0c0d0e4`), never laundered into shards; schema relaxations (open technical fields, object-form refs, free `method`) justified by real data; tagged, single-revert rollback | 2026-07-10 | S0004/S0005 suites still green after the additive schema/projection changes |
| F0006-S0006 | Architect | architect (delegated) | PASS | Migration modeling sound: shard taxonomy covers all 15 node kinds at the D2 granularity; 40 features = 33 mapped + 7 `coverage_excluded`; logical-ref rewrite reversible (byte-identical round trip proves it); `projections-meta.yaml` sources the non-record headers; cutover keeps projections unchanged (shards added, `compile(source)` == committed) so rollback is a single revert to `pre-kg-cutover` | 2026-07-10 | — |
| F0006-S0007 | Quality Engineer | quality-engineer (delegated) | PASS | Byte-identical tracker round trip closed: `tracker_gen.py --check` zero-diff on the real trackers; REGISTRY content byte-identical (29 archived / 9 planned / 2 retired / 0 active reproduced exactly), ROADMAP diff = markers + 3 documented rows; every feature in exactly one REGISTRY table + one ROADMAP section; `compile.py --check` (KG trio) still byte-identical (roadmap_order blacklisted); 11 `test_tracker_gen.py` tests (zero-diff regen, region integrity, ordering, counter, count reconciliation, prose-untouched) | 2026-07-11 | Region *enforcement* (CI) is S0008 |
| F0006-S0007 | Code Reviewer | code-reviewer (delegated) | PASS | `tracker_gen.py` writes only between fenced markers (prose untouched, verified by test); REGISTRY placement/sort derived by documented rules (rule-first, D-registry-derivation) — no stored display field needed; ROADMAP order captured as an additive `roadmap_order` presentation field (does not leak to feature-mappings); distinct Abandoned rationale preserved (not lost to canonicalization); `Next Available` = max+1; wired into the compile driver | 2026-07-11 | S0002 tracker-merge → transition-only; TRACKER-GOVERNANCE update handed to S0009 |
| F0006-S0007 | Product Manager | product-manager (delegated) | PASS | One-time canonicalization diff reviewed + approved (D-canon): REGISTRY markers-only; ROADMAP markers + F0010/F0011 fuller Abandoned link names (matching REGISTRY) + F0014 PRD→README (README present). BLUEPRINT.md §3.3 generation **deferred** (bespoke prose + stale F0021/F0022 duplicates — not a clean projection) | 2026-07-11 | BLUEPRINT defer + duplicate cleanup tracked in Deferred Non-Blocking Follow-ups |
| F0006-S0008 | DevOps | devops (delegated) | PASS | `.gitattributes` generated from `generated_paths.yaml` (whole-file → `linguist-generated`+`merge=ours`; fenced-region trackers excluded); blocking `.github/workflows/kg-reproducibility.yml` **green on GitHub**; `reproducibility` applied as a required status check on `nebula-insurance-crm` `main`; `ci-gates-template.yml` job template added | 2026-07-11 | D-ci-scope reverted full→fast-core on a real CI run (symbol/decision/coverage indexes not byte-reproducible cross-machine); those stay integrator-gated |
| F0006-S0008 | Quality Engineer | quality-engineer (delegated) | PASS | Red (synthetic hand-edit of canonical-nodes → fail naming file + remediation) and green (compliant repo → pass) proven locally and on GitHub; each rule (archived-no-stale-path, suppression-rationale, binding-glob-match) + `.gitattributes` drift + override-trailer downgrade has a test; 11 `test_reproducibility.py` | 2026-07-11 | — |
| F0006-S0008 | Code Reviewer | code-reviewer (delegated) | PASS | `reproducibility.py` reuses `compile`/`tracker_gen`/`shard_validate`; `.gitattributes` generated from the single manifest (no second hand-maintained copy — drift-checked); `validate.py --check-reproducible` is a thin early-exit delegation; committed symbol/decision/unbound stripped of `generated_at` (S0005-D1) | 2026-07-11 | Physical-path ban is `shard_validate`'s (S0004), wired into the reproducibility path |
| F0006-S0009 | Architect | architect (delegated) | PASS | `agent-map.yaml` authoring scopes for the generated trio + ontology removed symmetrically (PM + architect); integrator annotations flipped to "regenerated via compile.py"; ownership invariant holds (only integrator writes generated files, + coverage-report). `feature.md` G7/G8 + role ownership reconciled to shard-authoring + compile.py (off-book repoint narrative gone; F0005 payoff stated). `KNOWLEDGE-GRAPH.md` compiled-projection section (source/generated classification, shard schema, compile flow, logical refs, `depends_on` single-home, F0005 gap closed) + `ORCHESTRATION-CONTRACT.md` integrator sole-writer §6.1 + `MANUAL-ORCHESTRATION-RUNBOOK.md` compile-flow note. Re-runnable `audit-contract.py` (D-audit-form) **clean**: ownership + zero stale authoring phrases | 2026-07-11 | nebula-agents self-adoption deferred (D-self-adoption); documented in TRACKER-GOVERNANCE |
| F0006-S0009 | Code Reviewer | code-reviewer (delegated) | PASS | `validate-feature-evidence.py` learns `compile.py` as the projection-regeneration command, gated on `KG_COMPILE_PROJECTION_EFFECTIVE_DATE = 2026-07-11` (earlier evidence keeps the `--regenerate-*` contract; symbols/decisions matchers unchanged); 4 new tests + existing 18 evidence tests green. Prompts (feature-operator-friendly/automation-safe) + templates (kg-reconciliation, feature-registry, tracker-governance) reconciled to shards; `validate_agent_map.py` green; genericness unchanged (pre-existing flags only) | 2026-07-11 | — |
| F0006-S0001 | Quality Engineer | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/test-execution-report.md | 2026-07-12 | Current recovery row; historical detail retained above |
| F0006-S0001 | Code Reviewer | recovery-closeout review | APPROVED | planning-mds/operations/evidence/runs/2026-07-12-207a311b/code-review-report.md | 2026-07-12 | Current recovery row |
| F0006-S0001 | DevOps | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/deployability-check.md | 2026-07-12 | Current recovery row |
| F0006-S0001 | Architect | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/g0-assembly-plan-validation.md | 2026-07-12 | Current recovery row |
| F0006-S0002 | Quality Engineer | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/test-execution-report.md | 2026-07-12 | Current recovery row |
| F0006-S0002 | Code Reviewer | recovery-closeout review | APPROVED | planning-mds/operations/evidence/runs/2026-07-12-207a311b/code-review-report.md | 2026-07-12 | Current recovery row |
| F0006-S0002 | DevOps | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/deployability-check.md | 2026-07-12 | Current recovery row |
| F0006-S0002 | Architect | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/g0-assembly-plan-validation.md | 2026-07-12 | Current recovery row |
| F0006-S0003 | Quality Engineer | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/test-execution-report.md | 2026-07-12 | Current recovery row |
| F0006-S0003 | Code Reviewer | recovery-closeout review | APPROVED | planning-mds/operations/evidence/runs/2026-07-12-207a311b/code-review-report.md | 2026-07-12 | Current recovery row |
| F0006-S0003 | DevOps | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/deployability-check.md | 2026-07-12 | Current recovery row |
| F0006-S0003 | Architect | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/g0-assembly-plan-validation.md | 2026-07-12 | Current recovery row |
| F0006-S0004 | Quality Engineer | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/test-execution-report.md | 2026-07-12 | Current recovery row |
| F0006-S0004 | Code Reviewer | recovery-closeout review | APPROVED | planning-mds/operations/evidence/runs/2026-07-12-207a311b/code-review-report.md | 2026-07-12 | Current recovery row |
| F0006-S0004 | DevOps | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/deployability-check.md | 2026-07-12 | Current recovery row |
| F0006-S0004 | Architect | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/g0-assembly-plan-validation.md | 2026-07-12 | Current recovery row |
| F0006-S0005 | Quality Engineer | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/test-execution-report.md | 2026-07-12 | Current recovery row |
| F0006-S0005 | Code Reviewer | recovery-closeout review | APPROVED | planning-mds/operations/evidence/runs/2026-07-12-207a311b/code-review-report.md | 2026-07-12 | Current recovery row |
| F0006-S0005 | DevOps | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/deployability-check.md | 2026-07-12 | Current recovery row |
| F0006-S0005 | Architect | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/g0-assembly-plan-validation.md | 2026-07-12 | Current recovery row |
| F0006-S0006 | Quality Engineer | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/test-execution-report.md | 2026-07-12 | Current recovery row |
| F0006-S0006 | Code Reviewer | recovery-closeout review | APPROVED | planning-mds/operations/evidence/runs/2026-07-12-207a311b/code-review-report.md | 2026-07-12 | Current recovery row |
| F0006-S0006 | DevOps | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/deployability-check.md | 2026-07-12 | Current recovery row |
| F0006-S0006 | Architect | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/g0-assembly-plan-validation.md | 2026-07-12 | Current recovery row |
| F0006-S0007 | Quality Engineer | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/test-execution-report.md | 2026-07-12 | Current recovery row |
| F0006-S0007 | Code Reviewer | recovery-closeout review | APPROVED | planning-mds/operations/evidence/runs/2026-07-12-207a311b/code-review-report.md | 2026-07-12 | Current recovery row |
| F0006-S0007 | DevOps | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/deployability-check.md | 2026-07-12 | Current recovery row |
| F0006-S0007 | Architect | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/g0-assembly-plan-validation.md | 2026-07-12 | Current recovery row |
| F0006-S0007 | Product Manager | recovery-closeout review | APPROVED | planning-mds/operations/evidence/runs/2026-07-12-207a311b/pm-closeout.md | 2026-07-12 | Supersedes the historical free-text PM evidence cell for validator resolution |
| F0006-S0008 | Quality Engineer | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/test-execution-report.md | 2026-07-12 | Current recovery row |
| F0006-S0008 | Code Reviewer | recovery-closeout review | APPROVED | planning-mds/operations/evidence/runs/2026-07-12-207a311b/code-review-report.md | 2026-07-12 | Current recovery row |
| F0006-S0008 | DevOps | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/deployability-check.md | 2026-07-12 | Current recovery row |
| F0006-S0008 | Architect | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/g0-assembly-plan-validation.md | 2026-07-12 | Current recovery row |
| F0006-S0009 | Quality Engineer | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/test-execution-report.md | 2026-07-12 | Current recovery row |
| F0006-S0009 | Code Reviewer | recovery-closeout review | APPROVED | planning-mds/operations/evidence/runs/2026-07-12-207a311b/code-review-report.md | 2026-07-12 | Current recovery row |
| F0006-S0009 | DevOps | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/deployability-check.md | 2026-07-12 | Current recovery row |
| F0006-S0009 | Architect | recovery-closeout review | PASS | planning-mds/operations/evidence/runs/2026-07-12-207a311b/g0-assembly-plan-validation.md | 2026-07-12 | Current recovery row |

## Deferred Non-Blocking Follow-ups

| Follow-up | Why deferred | Tracking link | Owner |
|-----------|--------------|---------------|-------|
| Roll compiler + shard migration to other product repos | Each repo adopts independently after the reference implementation is proven | TBD | Framework maintainer |
| Re-evaluate OmniGraph (or similar) if live multi-agent graph writes are ever needed | Out of scope; serial integrator suffices at current scale | TBD | Architect |
| Central `F####` reservation tooling for contributors | Process rule suffices now (REGISTRY reservation before branching) | TBD | PM |
| Generate BLUEPRINT.md §3.3 feature list from shards + clean its stale duplicates (F0021/F0022 appear twice with contradictory status) | S0007 D-blueprint decision (2026-07-11): §3.3 is a bespoke prose list, not a clean projection; generating it would drop per-feature descriptions. Not needed to close the REGISTRY/ROADMAP round trip (the story's gate). | TBD | PM |
| Exercise S0003's untested enforcement paths: gate-1 missing-verdict halt, gate-2 validation-fail-leaves-merge-unpushed, and the contract-violation self-abort (integrator would write a source file) | Train-wide feature-review waiver + all-pass validations + no attempted source write meant none fired live. Self-abort is already allowlist-backed (`agents/agent-map.yaml` integrator scope excludes feature docs + `kg-source/**`, "abort + self-report on violation"), so its gap is verifying the abort *fires*, not a missing guard; gate-1/gate-2 are untested failure-branches. | **First post-train integration** runs with **no blanket waiver** (maintainer decision 2026-07-06); to record the missing-verdict halt, one run is deliberately started with **neither verdict nor waiver** (per `integrate.md` I0), the halt fires and is captured in that run's evidence, then the verdict is obtained and the run re-run. (Merely supplying a real verdict passes gate 1 and leaves the halt untested — dropping the blanket waiver alone does not trigger it.) Gate-2-fail injection stays optional (catch on the first real validation failure). Self-abort scenario test folded into S0009 when integrator tooling is next touched. | Maintainer + Quality Engineer |

## Closeout Summary

| Field | Value |
|-------|-------|
| Implementation completed | Phase A: 2026-07-06 (S0001–S0003); Phase B (B1–B6): **complete 2026-07-11** (S0004/S0005 2026-07-09; S0006 cutover 2026-07-10; S0007/S0008/S0009 2026-07-11) |
| Closeout review date | 2026-07-11 (feature-review PASS — delegated, maintainer-sanctioned) |
| Total stories | 9 |
| Stories completed | 9 / 9 (all implemented + signed off; every required role holds ≥1 story-level PASS) |
| Test count (unit + integration) | Product `scripts/kg/`: **186 tests** green (merge3 27, tracker_merge 18, shard_validate 32, compile 24, decompile 6, tracker_gen 11, reproducibility 11, + existing lookup/eval/etc.) + 9 Phase-A integration evidence runs. Framework `nebula-agents`: evidence-matcher 4 + evidence-validator 18 + audit-contract + validate_agent_map. Reproducibility CI green on GitHub |
| Defects found during review | (1) S0006 source drift — 6 `capability:document-*` records mis-filed in `glossary_terms`; (2) S0008 — symbol/decision/coverage indexes not byte-reproducible cross-machine (surfaced by a real CI run); (3) pre-existing `test_lookup_tier` failure (product lookup-test snapshot drift, **outside F0006 scope**) |
| Defects fixed before closeout | (1) FIXED at source pre-cutover (`0c0d0e4`: moved the 6 records → `capabilities`, zero refs broken; byte-identical round trip proven); (2) RESOLVED by scoping the CI gate to the deterministic compiled-projection invariant (D-ci-scope fast-core), those indexes stay integrator-gated |
| Residual risks | Reference-product snapshot expectations require refresh after subsequent feature/tracker growth; the sandbox-blocked MCP workstate case requires a writable checkout. Symbol/decision/coverage cross-machine reproducibility remains integrator-gated. S0003's gate-1/gate-2/self-abort enforcement paths remain deferred. BLUEPRINT generation and `nebula-agents` shard self-adoption remain deferred. |
| Archive status | Archived by recovery G8 closeout on 2026-07-12; canonical recovery run `2026-07-12-207a311b`. |

## Tracker Sync Checklist

Re-aligned 2026-07-12 at recovery G8 closeout (F0006 → Archived, all 9 stories Done).

- [x] `planning-mds/features/REGISTRY.md` status/path aligned (F0006 → Archived; F0005 superseded record present)
- [x] `planning-mds/features/ROADMAP.md` section aligned (F0006 → Completed section)
- [x] `planning-mds/features/STORY-INDEX.md` (S0001–S0009 → Done)
- [x] `planning-mds/BLUEPRINT.md` feature/story status links aligned (F0006 Archived; S0001–S0009 Done)
- [x] Every required signoff role has story-level `PASS` entries with reviewer, date, and evidence (Architect, QE, Code Reviewer, DevOps — verified at closeout)

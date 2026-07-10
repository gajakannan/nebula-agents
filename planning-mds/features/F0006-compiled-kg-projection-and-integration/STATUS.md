# F0006 - Compiled Knowledge-Graph Projection and Governed Integration - Status

**Overall Status:** In Progress
**Last Updated:** 2026-07-09 (Phase B: **S0004 + S0005 done and signed off** — shard schema/validator + deterministic compiler; B1–B2 of B1–B6. Phase A complete 2026-07-06: all 7 contributor PRs integrated and promoted to `main`; S0001–S0003 signed off)

## Story Checklist

| Story | Title | Phase | Status |
|-------|-------|-------|--------|
| F0006-S0001 | Three-way semantic KG merge tool (`merge3.py`) | A | [x] Done (signed off 2026-07-06) |
| F0006-S0002 | Tracker-table three-way merge (REGISTRY/ROADMAP rows) | A | [x] Done (signed off 2026-07-06) |
| F0006-S0003 | Integrator role and `integrate` action | A | [x] Done (signed off 2026-07-06; three enforcement paths remain exercised-by-text-only — gate-1 halt, gate-2 fail, self-abort; see provenance notes) |
| F0006-S0004 | `kg-source/` shard schema, layout, and ownership | B | [x] Done (signed off 2026-07-09) |
| F0006-S0005 | Deterministic KG compiler with logical doc refs | B | [x] Done (signed off 2026-07-09) |
| F0006-S0006 | Decompiler-first migration with round-trip proof | B | [ ] Not Started |
| F0006-S0007 | Tracker generation from feature shards | B | [ ] Not Started |
| F0006-S0008 | Reproducibility CI, enforcement, and git policy | B | [ ] Not Started |
| F0006-S0009 | Framework contract, roles, and docs reconciliation | B | [ ] Not Started |

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
- [ ] `decompile.py` with `--check`; round-trip `compile(decompile(graph))` byte-identical; feature-table decompile populates feature-shard presentation fields (name/phase/section/rationale/gate/dates), schema-valid + count-reconciled (tracker round trip closes at S0007)
- [ ] `kg-source/**` populated; `solution-ontology.yaml` rehomed under `kg-source/ontology/`
- [ ] Tracker generator owns fenced REGISTRY/ROADMAP table regions (byte-identical round trip from decompiled shards)
- [ ] `validate.py --check-reproducible` + new rules (physical-path ban, alias ledger, glob overlap, archived⇒no-stale-path)
- [ ] `.gitattributes` (linguist-generated + merge driver) and CI workflow (warn → blocking)

## Framework-Contract Progress (`nebula-agents`)

- [x] `agents/integrator/SKILL.md` persona (duties, hard boundary, routing) — 2026-07-05
- [~] `agents/agent-map.yaml`: integrator registered (balanced tier) + `integrate` action wired with `review-verdict`/`approval` gates; **Phase-B `kg-source/` write scopes added (S0004, 2026-07-09)** — architect: `nodes/bindings/policies/ontology`, PM: `features/exclusions` (co-sign annotated); removal of the now-generated `knowledge-graph/*.yaml` scopes + integrator annotation flip deferred to S0009 (post-cutover)
- [x] `agents/actions/integrate.md` (incl. feature-review precondition + human test-validation pause, steps I0–I6 with human gates at I0 and I6, branch strategy) + `actions/README.md` + `ROUTER.md` routing
- [x] Integration evidence template + `integrate-operator-friendly.md` prompt (evidence home decided: base-run profile at `operations/evidence/runs/integrate-*`)
- [ ] `agents/actions/feature.md` G7/G8 reconciled (no off-book repoint narrative)
- [ ] `feature-operator-friendly.md` prompt reconciled
- [ ] `agents/docs/KNOWLEDGE-GRAPH.md` / `ORCHESTRATION-CONTRACT.md` updated (no integrator/shard content yet)
- [~] `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md`: integration procedure + both human gates landed in S0003; Phase-B compile-flow additions pending (S0009)
- [ ] Templates updated: `kg-reconciliation`, `feature-assembly-plan`, `tracker-governance`, `feature-registry`, `ci-gates`
- [ ] 2026-07-05 KG-regeneration enforcement surfaces reconciled for Phase B: `build.md`, `plan.md`, feature/build/plan prompt variants; `validate-feature-evidence.py` matchers learn `compile.py` (+ tests)

## Cross-Cutting

- [x] merge3 unit tests: converge-identical, one-side, field-recurse, ordered-list conflict, delete-vs-update, orphan edge, unique violation, all-or-nothing (27 tests incl. idempotent canonicalization, object-form edge refs, full-validate rollback, determinism)
- [ ] Integrator human-gate tests: missing-verdict halt, waiver re-run proceeds, validation-fail leaves merge unpushed
- [ ] Determinism tests: double-compile, cross-machine byte-identical
- [ ] Migration idempotency + round-trip test
- [ ] Reproducibility-check red test (synthetic hand-edit) and green test
- [ ] Archive-a-feature dry-run: one feature-shard edit keeps graph + trackers green
- [ ] Story validator passes; tracker validator passes
- [ ] README / getting-started updated

## Required Signoff Roles (Set in Planning)

| Role | Required | Why Required | Set By | Date |
|------|----------|--------------|--------|------|
| Architect | Yes | Owns merge semantics, shard schema, ontology classification, and the ownership-boundary changes; this feature redefines the KG contract. | Architect | 2026-07-04 |
| Quality Engineer | Yes | Validates merge determinism, round-trip proof, taxonomy coverage, and the PR #47 replay evidence. | Architect | 2026-07-04 |
| Code Reviewer | Yes | Reviews merge3/compile/decompile correctness, all-or-nothing semantics, and canonical-serializer safety. | Architect | 2026-07-04 |
| DevOps | Yes | CI reproducibility workflow, `.gitattributes` merge driver, branch-protection changes. | Architect | 2026-07-04 |
| Security Reviewer | No | No auth, secret, or external surface; local planning-doc tooling only. The security co-sign that S0004 (BR2) / PRD §2 introduce on `policies/authorization-*.yaml` is a *downstream authoring* rule for future policy shards, not a review gate on this feature's own tooling. | Architect | 2026-07-04 |

## Story Signoff Provenance

Complete this before moving `Overall Status` to `Done` or `Archived`.

> **Required roles per story:** the roles listed for a story below are exactly those required for
> that story — a role's absence means it is *not required* for that story, not that a signoff is
> missing. QE's required scope is the merge tooling and replay/round-trip evidence (S0001, S0002,
> S0005–S0008); the schema/spec story (S0004) and the role/contract stories (S0003, S0009) require
> Architect + Code Reviewer but no QE — S0004 defines the `kg-source/` shard schema and ownership,
> which is design + contract review rather than testable merge tooling. This is why S0002 has no
> Architect row (it inherits S0001's merge semantics) and S0003/S0004 have no QE row. S0008
> additionally carries a Code Reviewer row: it ships `validate.py` enforcement-rule code and the
> merge driver (code correctness), which DevOps's CI / `.gitattributes` / branch-protection scope
> does not cover. Every story that ships executable tooling carries a Code Reviewer row for code
> correctness — S0001, S0002, S0005, S0006, S0007, S0008 — so S0007 has one (its tracker generator,
> with fenced-region markers, cell escaping, deterministic ordering, and a byte-identical round
> trip, is as much code as S0002's table merge); S0009 (contract/docs) carries Code Reviewer for the
> `validate-feature-evidence.py` matcher change it ships. Feature-level closeout still requires every
> role in "Required Signoff Roles" to hold at least one story-level PASS.

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
| F0006-S0006 | Quality Engineer | TBD | TBD | TBD | TBD | Pending implementation |
| F0006-S0006 | Code Reviewer | TBD | TBD | TBD | TBD | Pending implementation |
| F0006-S0007 | Quality Engineer | TBD | TBD | TBD | TBD | Pending implementation |
| F0006-S0007 | Code Reviewer | TBD | TBD | TBD | TBD | Pending implementation (tracker-generator code: region markers, cell escaping, ordering, byte-identical round trip) |
| F0006-S0008 | DevOps | TBD | TBD | TBD | TBD | Pending implementation |
| F0006-S0008 | Quality Engineer | TBD | TBD | TBD | TBD | Pending implementation |
| F0006-S0008 | Code Reviewer | TBD | TBD | TBD | TBD | Pending implementation (validator rule code + merge driver) |
| F0006-S0009 | Architect | TBD | TBD | TBD | TBD | Pending implementation |
| F0006-S0009 | Code Reviewer | TBD | TBD | TBD | TBD | Pending implementation |

## Deferred Non-Blocking Follow-ups

| Follow-up | Why deferred | Tracking link | Owner |
|-----------|--------------|---------------|-------|
| Roll compiler + shard migration to other product repos | Each repo adopts independently after the reference implementation is proven | TBD | Framework maintainer |
| Re-evaluate OmniGraph (or similar) if live multi-agent graph writes are ever needed | Out of scope; serial integrator suffices at current scale | TBD | Architect |
| Central `F####` reservation tooling for contributors | Process rule suffices now (REGISTRY reservation before branching) | TBD | PM |
| Exercise S0003's untested enforcement paths: gate-1 missing-verdict halt, gate-2 validation-fail-leaves-merge-unpushed, and the contract-violation self-abort (integrator would write a source file) | Train-wide feature-review waiver + all-pass validations + no attempted source write meant none fired live. Self-abort is already allowlist-backed (`agents/agent-map.yaml` integrator scope excludes feature docs + `kg-source/**`, "abort + self-report on violation"), so its gap is verifying the abort *fires*, not a missing guard; gate-1/gate-2 are untested failure-branches. | **First post-train integration** runs with **no blanket waiver** (maintainer decision 2026-07-06); to record the missing-verdict halt, one run is deliberately started with **neither verdict nor waiver** (per `integrate.md` I0), the halt fires and is captured in that run's evidence, then the verdict is obtained and the run re-run. (Merely supplying a real verdict passes gate 1 and leaves the halt untested — dropping the blanket waiver alone does not trigger it.) Gate-2-fail injection stays optional (catch on the first real validation failure). Self-abort scenario test folded into S0009 when integrator tooling is next touched. | Maintainer + Quality Engineer |

## Closeout Summary

| Field | Value |
|-------|-------|
| Implementation completed | Phase A: 2026-07-06 (S0001–S0003); Phase B: in progress (B1/S0004 + B2/S0005 2026-07-09) |
| Closeout review date | TBD (feature closes after Phase B) |
| Total stories | 9 |
| Stories completed | 5 / 9 |
| Test count (unit + integration) | 45 unit (merge3 27 + tracker 18) + 9 integration evidence runs |
| Defects found during review | TBD |
| Defects fixed before closeout | TBD |
| Residual risks | TBD |

## Tracker Sync Checklist

Aligned 2026-07-06 to Phase-A completion (S0001–S0003 Done, F0006 In Progress); re-verify at closeout.

- [x] `planning-mds/features/REGISTRY.md` status/path aligned (F0006 → In Progress; F0005 superseded record present)
- [x] `planning-mds/features/ROADMAP.md` section aligned (F0006 → In Progress; PR count corrected 5 → 7; Phase-A-complete framing)
- [x] `planning-mds/features/STORY-INDEX.md` regenerated or updated (S0001–S0003 → Done)
- [x] `planning-mds/BLUEPRINT.md` feature/story status links aligned (F0006 In Progress; S0001–S0003 Done)
- [ ] Every required signoff role has story-level `PASS` entries with reviewer, date, and evidence (Phase-B roles pending)

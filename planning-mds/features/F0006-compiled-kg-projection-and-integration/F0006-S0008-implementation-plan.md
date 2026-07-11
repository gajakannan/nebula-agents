# F0006-S0008 — Implementation Plan (Reproducibility CI, Enforcement & Git Policy)

> **Living tracker for the B5 build.** Companion to
> [`F0006-S0008-reproducibility-ci-and-git-policy.md`](./F0006-S0008-reproducibility-ci-and-git-policy.md).
> Builds on S0004–S0007 (done; `kg-source/` is authoring truth, trackers generated). Turns the
> reproducibility invariant we've been proving by hand (`compile.py --check`, `tracker_gen.py --check`)
> into **enforced CI + git policy**. Update §9 as work lands.

| Field | Value |
|-------|-------|
| Story | F0006-S0008 (PRD row **B5**) |
| Phase | B — Compiled projection |
| Status | **Approved 2026-07-11 — ready to build** (all §4 decisions resolved) |
| Created | 2026-07-11 |
| Branch (both repos) | `feat/F0006-phase-B-compiled-projection` |
| Signoff required | **DevOps** + Quality Engineer + Code Reviewer |
| Touches `main` | **No** — feature branch (branch-protection flip is a separate maintainer action) |

---

## 0. Scope

**Delivers** the enforcement layer for the committed-projection policy:
- `scripts/kg/generated_paths.yaml` — the single authoritative manifest of every generated path with a
  `whole-file` / `fenced-region` granularity marker (PRD §2 is its content).
- `.gitattributes` generated **from** the manifest (never hand-listed): `linguist-generated` + a merge
  driver on `whole-file` paths only; the `fenced-region` trackers excluded from both.
- `validate.py --check-reproducible` — the single reproducibility entry point (CI + integrator use it).
- New validator rules: physical-feature-path ban (source), archived⇒no-stale-path (projections),
  alias-suppression-ledger-rationale-required, binding-glob-matches-≥1-file.
- `.github/workflows/kg-reproducibility.yml` — PR check (warn-only shake-out → blocking).
- `agents/templates/ci-gates-template.yml` (framework repo) — the reusable job template.
- Documented maintainer-override trailer (logged, emergencies only).

**Defers:** branch-protection flip to *blocking* (a maintainer GitHub setting — see D-ci-mode); the
contract/docs reconciliation (S0009); other product repos.

---

## 1. What S0008 enforces (already proven by hand)

Through S0005–S0007 we have been running these green manually:
- `compile.py --check` → committed trio + ontology mirror **+ REGISTRY/ROADMAP fenced regions** == `compile(source)`.
- `shard_validate.py` → all shards valid.
- `validate.py` → graph integrity.

S0008 makes them a **PR gate** so no branch can commit a hand-edited generated file (or a stale
projection) without CI failing with an actionable message. Same check the integrator already runs at
merge (S0003) — CI is the second location.

---

## 2. Reuse surface

| Need | Reuse |
|------|-------|
| Reproducibility check | `compile.py --check` (trio+ontology+trackers, S0005/S0007); `shard_validate.py` |
| Generated-path list content | PRD §2 "Generated projections" table (9 whole-file + 2 fenced-region) |
| Glob existence | `kg_common.expand_declared_pattern` / `has_wildcards` |
| Existing derived checks | `validate.py --check-symbols/--check-decisions/--check-drift` (d18909b) |
| Validator report/CLI | `validate.py`'s argparse + report.error plumbing |

New: the manifest + `.gitattributes` generator + drift check, `--check-reproducible` orchestration, the
four rules, the CI workflow + template.

---

## 3. The manifest (`generated_paths.yaml`)

```yaml
generated_paths:
  - {path: planning-mds/knowledge-graph/canonical-nodes.yaml, granularity: whole-file, by: compile.py}
  - {path: planning-mds/knowledge-graph/feature-mappings.yaml, granularity: whole-file, by: compile.py}
  - {path: planning-mds/knowledge-graph/code-index.yaml,       granularity: whole-file, by: compile.py}
  - {path: planning-mds/knowledge-graph/solution-ontology.yaml, granularity: whole-file, by: compile.py}
  - {path: planning-mds/knowledge-graph/symbol-index.yaml,      granularity: whole-file, by: symbols.py}
  - {path: planning-mds/knowledge-graph/unbound-but-referenced.yaml, granularity: whole-file, by: symbols.py}
  - {path: planning-mds/knowledge-graph/coverage-report.yaml,   granularity: whole-file, by: validate.py --write-coverage-report}
  - {path: planning-mds/knowledge-graph/decisions-index.yaml,   granularity: whole-file, by: decisions.py}
  - {path: planning-mds/features/STORY-INDEX.md,                granularity: whole-file, by: generate-story-index.py}
  - {path: planning-mds/features/REGISTRY.md, granularity: fenced-region, by: tracker_gen.py}
  - {path: planning-mds/features/ROADMAP.md,  granularity: fenced-region, by: tracker_gen.py}
```

One home, three consumers (CI, `.gitattributes` generation, integrator). A CI check fails if
`.gitattributes` drifts from the manifest.

---

## 4. Decisions (resolved 2026-07-11)

> **Confirmed:** **D-ci-scope = FULL** — the PR check builds the .NET/TS symbol extractors and
> verifies the *entire* generated surface (trio+ontology+trackers **and** symbol-index/
> unbound/decisions/coverage), not just the fast compiled-projection check. **D-ci-mode = BLOCKING
> immediately** — land the workflow blocking **and** add branch protection with the required status
> check on `nebula-insurance-crm` main in this story (changes the repo merge policy). **D-merge-driver
> = `merge=ours`.** **D-check-entry** (single `validate.py --check-reproducible`) and **D-override**
> (`KG-Reproducibility-Override:` trailer) = defaults. Scope implications below.

**Full-check scope implications (D-ci-scope):**
- `validate.py --check-reproducible` orchestrates: `compile.py --check` (trio+ontology+trackers) +
  `shard_validate.py` + `--check-symbols`/`--check-decisions` + coverage-report regen-and-diff + the 4
  new rules. Non-zero on any drift.
- The **committed** `symbol-index.yaml`/`decisions-index.yaml`/`coverage-report.yaml` carry
  `generated_at` today; S0008 regenerates + **strips `generated_at`** (S0005-D1) + commits them once so
  the full-surface diff is deterministic (a one-time content change, DevOps-reviewed).
- The CI workflow installs the toolchain: `setup-dotnet` (.NET 10, matches the Dockerfile sdk stage),
  `setup-node` + `pnpm install` (ts-symbols), `pip install pyyaml jsonschema`. Watch the poisoned
  `.kg-state/symbols-cache.json` trap (delete before regenerate). Runtime rises to a few minutes.
- **story-index** reproducibility needs the framework `generate-story-index.py` (in `nebula-agents`):
  the workflow checks out `nebula-agents` too (or that one file stays integrator-gated — decide at build).

**Blocking-now implications (D-ci-mode):** after the workflow runs green once, add it as a **required
status check** in `nebula-insurance-crm` branch protection (via `gh api`). This is an outward-facing
repo-config change — I'll confirm before applying it.

## 4b. Decision details (as planned)

- **D-check-entry — the single reproducibility command.** **Recommendation:** add
  `validate.py --check-reproducible` that orchestrates `compile.py --check` + `shard_validate.py` + the
  four new rules and exits non-zero on any drift/violation. CI and the integrator both call just this.
  Confirm (vs. CI invoking each tool separately).
- **D-ci-scope — what the PR check runs.** The trio+ontology+tracker reproducibility (`compile --check`)
  is **fast, no toolchain**. The symbol/decision/coverage indexes need the .NET/TS build (`--check-symbols`).
  **Recommendation:** the PR gate runs the **fast** compiled-projection check + shard validation + rules
  (low single-digit minutes); the heavier symbol/decision reproducibility stays integrator-gated (it
  already has `--check-symbols`/`--check-decisions`) and can be a separate optional CI job. Confirm.
- **D-ci-mode — warn-only → blocking.** **Recommendation:** land the workflow **warn-only**
  (`continue-on-error`) for a shake-out window; flipping to **blocking** = adding it as a required status
  check in `nebula-insurance-crm` branch protection (currently unprotected — a maintainer GitHub action,
  your call when ready). S0008 lands the workflow + the red/green proof; the flip is a one-line/one-setting
  follow-up. Confirm this staging.
- **D-merge-driver — `.gitattributes` driver for whole-file paths.** **Recommendation:** `merge=ours`
  (simple; the integrator's unconditional recompile is the real correctness — the driver only prevents
  local conflict-marker deadlocks; drivers don't run on GitHub server-side merges, which is fine). The
  `fenced-region` trackers get **neither** `linguist-generated` nor the driver. Confirm `merge=ours`
  vs. a custom "take-either-then-recompile" driver.
- **D-override — emergency override.** **Recommendation:** a commit trailer `KG-Reproducibility-Override:
  <reason>` that CI detects on the head commit and downgrades the failure to a logged warning
  (emergencies only; the integrator records it in evidence). Confirm the trailer name/behavior.

---

## 5. New validator rules (`validate.py`)

1. **Physical-feature-path ban (source):** already enforced on shards by `shard_validate` (S0004) — wired
   into the `--check-reproducible` path so CI covers it.
2. **Archived ⇒ no stale path (projections):** for each feature with `archived_date`, no generated
   projection may contain a non-`archive/` path to its folder (the F0038 postmortem rule). Safety net —
   `compile` already resolves via `feature.path`, so this should never fire post-cutover.
3. **Alias-suppression ledger rationale:** every entry in `kg-source/exclusions/suppressions.yaml` must
   carry a non-empty `rationale` (compile silently ignores rationale-less entries; here it's an error).
4. **Binding glob matches ≥1 file:** every `code-index` binding path resolves to ≥1 real file (via
   `expand_declared_pattern`) unless explicitly allowed.

---

## 6. Red / green proof

- **Red:** a synthetic hand-edit of `canonical-nodes.yaml` (no shard change compiles to it) → CI fails
  naming the file + remediation ("edit the shard / run compile.py"). A stale tracker region → same.
- **Green:** a PR whose shards compile to exactly its committed projections → CI passes.
- Recorded in the workflow run (the DoD's "red test + green test").

---

## 7. File inventory

**Product repo `nebula-insurance-crm`:**
- `scripts/kg/generated_paths.yaml` — the manifest
- `scripts/kg/gitattributes_gen.py` (or a `validate.py` mode) — generate/check `.gitattributes` from the manifest
- `.gitattributes` — generated
- `scripts/kg/validate.py` — **edit**: `--check-reproducible` + the four rules
- `.github/workflows/kg-reproducibility.yml` — the PR check
- `scripts/kg/tests/test_reproducibility.py` — red/green, manifest↔.gitattributes drift, each rule
- `scripts/kg/README.md` — **edit**: reproducibility/enforcement section

**Framework repo `nebula-agents`:**
- `agents/templates/ci-gates-template.yml` — the reusable job template
- STATUS/plan tracking

---

## 8. Test plan (QE + DevOps signed)

Red (hand-edit → fail with remediation) + green (compliant → pass); manifest↔`.gitattributes` drift
detection; each rule (archived-consistency, ledger-rationale, glob-match, physical-path-ban) has a
failing + passing case; `--check-reproducible` exits non-zero on any drift; override-trailer downgrades
correctly; workflow runs in low single-digit minutes.

---

## 9. Progress checklist

- [x] Decisions D-check-entry / D-ci-scope / D-ci-mode / D-merge-driver / D-override resolved (2026-07-11)
- [ ] `generated_paths.yaml` manifest (9 whole-file + 2 fenced-region, per PRD §2)
- [ ] `.gitattributes` generated from manifest (`merge=ours` + `linguist-generated` on whole-file only) + drift check
- [ ] `validate.py --check-reproducible` orchestration — **FULL**: compile-check + shard-validate + symbols/decisions/coverage + the 4 rules
- [ ] Regenerate + strip `generated_at` from committed symbol-index/decisions/coverage (one-time, DevOps-reviewed)
- [ ] `.github/workflows/kg-reproducibility.yml` — **blocking**, with .NET/Node/pnpm toolchain setup; red/green proof recorded
- [ ] `agents/templates/ci-gates-template.yml` (framework)
- [ ] Override-trailer convention documented + honored
- [ ] `test_reproducibility.py` green; `scripts/kg/README.md` updated
- [ ] **Branch protection**: add the required status check on `nebula-insurance-crm` main (via `gh api`, after first green run — I'll confirm before applying)
- [ ] STATUS provenance (DevOps + QE + Code Reviewer); story index updated
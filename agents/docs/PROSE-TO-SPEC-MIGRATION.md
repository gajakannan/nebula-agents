# Prose-to-Spec Migration: Making Scripts the Source of Truth

**Status:** Proposal
**Scope:** `agents/actions/**`, `agents/templates/prompts/evidence-contract/**`, `agents/*/SKILL.md`, shared and per-role scripts
**Author:** framework review, 2026-07-12

---

## 1. Executive Summary

Today the orchestration contract is encoded three times: once in prose (action files,
evidence-contract prompts, SKILL.md sections), once in validators
(`validate-feature-evidence.py` and friends), and once in prose-linters that try to keep
the first two in sync (`audit-contract.py`, hard-coded lists in `validate_templates.py`).
The prose is the *primary* encoding and the scripts are defense in depth — which is
backwards. Prose drifts silently (it is paraphrased, not copied, so no diff tool catches
divergence), it consumes LLM context on facts a script should own, and it forces every
contract change to be re-authored in up to 24 files.

This proposal inverts the direction:

1. **One machine-readable spec per action** (`agents/actions/spec/<action>.yaml`) becomes
   the single source of truth for gates, artifacts, commands, ordering, ownership, and
   stop conditions.
2. **Prompts become build artifacts** rendered from the spec (both operator-friendly and
   automation-safe variants), with a CI drift gate.
3. **Deterministic procedure moves into scripts** the agent invokes: session setup, gate
   running, severity gating, closeout sequencing, product scaffolding.
4. **Prose shrinks to what genuinely needs judgment**: review criteria, severity
   classification, clarification questions, KG binding decisions, writing voice.

The end state: action files and SKILL.md files roughly halve in size, the 24
evidence-contract prompts become generated output of ~13 small YAML records + 1 template,
and a contract change (e.g. a new gate artifact) is a one-file edit that propagates to
prompts, runner, and validator automatically.

---

## 2. Evidence: Why This Is Needed

Findings from a full review of the three surfaces (2026-07-12):

### 2.1 The repo already lints its own prose — the tell

- `agents/scripts/audit-contract.py` maintains `STALE_PATTERNS` — regexes that sweep
  `actions/*.md` and the evidence-contract prompts for sentences describing pre-compiled-
  projection behavior ("hand-edit canonical-nodes.yaml", "repoint archive doc refs").
- `agents/scripts/validate_templates.py:355-380` hard-codes content assertions about
  prompt files: which must mention `planning-mds/operations/evidence/`, which must not
  contain `uuid4`, which gate template names `feature.md` must reference.

When regexes are required to keep English consistent with validators, the English is
functioning as source code without a compiler. Every new invariant currently needs a new
regex.

### 2.2 The 24 evidence-contract prompts are ~80–90% one skeleton

- Every file repeats the same SESSION_SETUP (run-ID generation, evidence folder skeleton,
  manifest init, concurrent-run check), context-loading preamble
  (`ROUTER.md → agent-map.yaml → AGENT-USE.md → actions/<x>.md`), commands.log rules, and
  conflict-resolution blocks — parameterized only by an action prefix (`BLOG_RUN_ID`,
  `PLAN_RUN_ID`, …).
- Operator-friendly vs automation-safe pairs are ~90–100% semantically identical; only the
  encoding differs (prose paragraphs vs uppercase-header outline).
- Duplication is **paraphrased, not literal** (measured: only 2–19 shared lines >30 chars
  between files stating identical rules), so drift is invisible to diffs.
- Drift already exists: `append-command-log.py` is named in only **2 of 24** files that
  all state the same logging requirement; the contract effective date `2026-05-19` is
  hard-coded in all 24; `integrate` uses a different RUN_ID scheme with no structural
  marker saying so.

### 2.3 Action files embed one policy engine seven times

- The severity gate state machine (`IF critical>0: BLOCKED / ELIF high>0: WARNING +
  justification / ELSE: ACCEPTABLE`) plus its machine-readable JSON appears in
  `build.md`, `feature.md`, `review.md`, `validate.md`, `test.md`, `plan-review.md`,
  `feature-review.md` — each repeating "orchestrators must be able to programmatically
  determine gate state."
- Purely deterministic runbooks live as prose: per-gate validator command tables
  (`feature.md:166-176`, `build.md:77-84`), ordered exit validation with sequencing
  constraints an LLM is the wrong tool to remember ("run `--write-coverage-report`
  **after** the archive move", `feature.md:207`), and the supersession-and-publish
  sequence duplicated in `build.md:55-60` and `feature.md:154-160`.
- `init.md` is ~80% `mkdir` + copy-template-if-missing + file-existence validation.
- The banned-words linter (should/might/easy/fast/…) is spelled out in `plan.md`,
  `plan-review.md`, and `validate.md`.

### 2.4 SKILL.md files paraphrase the validators

- `validate-feature-evidence.py` (3,774 lines) owns the evidence contract with named rule
  IDs, yet six SKILL.md files carry "Feature Evidence Contract" sections re-narrating its
  rules per role (`product-manager/SKILL.md:369-403`, `code-reviewer/SKILL.md:441-465`,
  `quality-engineer/SKILL.md:505-534`, plus security, architect, devops).
- The ≥80% coverage threshold appears in ~15 prose locations; `validate-test-coverage.py`
  (`--min 80`) and `agent-map.yaml:440-442` already own it.
- `## Retrieval Guard` is verbatim-identical in 9 SKILL.md files with two already-drifted
  variants in 2 more.
- Four SKILL.md files exceed the 500-line ceiling enforced by `run-skill-regression.py`
  (quality-engineer 534, devops 530, architect 530, frontend-developer 508).
- Counter-example that proves the model: `integrator/SKILL.md` (134 lines) delegates to
  `agents/actions/integrate.md` with "follow it exactly" instead of restating it.

---

## 3. Design Principles

1. **Spec over prose.** Anything with a fixed answer (paths, commands, ordering, gate
   arithmetic, artifact lists, ID formats, thresholds) lives in YAML or a script. Prose
   never states a fact the spec owns; it points at it.
2. **Prompts are build artifacts.** Rendered from spec + template; humans edit the spec,
   never the rendered file. CI fails on drift.
3. **Scripts execute; agents decide.** The agent runs `run-gate.py G4` and reads its
   verdict; the agent does not recall which validator command belongs to G4.
4. **Validators and generators consume the same data.** The stage matrix that
   `validate-feature-evidence.py` enforces and the gate table the prompt shows must be
   the same object.
5. **Judgment stays in prose, and gets more room.** Review criteria, severity
   classification, clarification, KG binding decisions, and voice remain natural language
   — with more of the context window available to them.
6. **Boundary discipline is unchanged.** Framework scripts stay generic
   (`validate-genericness.py` still gates); product-repo scripts (`scripts/kg/*`) are
   referenced by the spec but never vendored into it.

---

## 4. Target Architecture

```
agents/actions/spec/
  _contract.yaml            # shared constants (one copy, consumed everywhere)
  _common.yaml              # shared blocks: session setup, forbidden, conflict rules
  feature.yaml              # per-action spec (gates, artifacts, commands, ownership)
  build.yaml
  plan.yaml
  ... (13 total)
        │
        ├──> agents/scripts/render-prompts.py
        │       renders BOTH variants per action into
        │       agents/templates/prompts/evidence-contract/*.md
        │       (committed, but CI regenerates and diffs — drift fails)
        │
        ├──> agents/scripts/run-gate.py <stage>
        │       runtime driver: executes the gate's commands in order,
        │       enforces sequencing constraints, appends to commands.log
        │       and lifecycle-gates.log, returns structured verdict
        │
        ├──> agents/scripts/init-run.py
        │       SESSION_SETUP as code: resolve vars, mint RUN_ID,
        │       create skeleton, init manifest, concurrent-run check
        │
        ├──> agents/scripts/gate_policy.py
        │       the severity state machine, imported by run-gate.py
        │       and by review-family actions
        │
        └──> validators (validate-feature-evidence.py, validate_templates.py)
                import the stage matrix / required-artifact lists from the
                same spec instead of private constants
```

The action `.md` files remain — but as the judgment layer: flow narrative, role
responsibilities, review criteria, examples. Their procedural sections become one-line
pointers ("Gate commands and ordering: `run-gate.py`; see `spec/feature.yaml`").

---

## 5. The Action Spec Schema

One YAML per action. Illustrative excerpt for `feature`:

```yaml
# agents/actions/spec/feature.yaml
action: feature
action_doc: agents/actions/feature.md
contract:
  name: Feature Evidence Contract
  scope: feature-completion          # feature-completion | base-run-only | read-only-audit | merge
run_id:
  scheme: contract                   # contract = YYYY-MM-DD-{secrets.token_hex(4)}
  var: RUN_ID
inputs:
  required:
    - {name: FEATURE_ID, format: "F####"}
  optional:
    - {name: MODE, enum: [clean, drift-reconcile], default: clean}
    - {name: SLICE_ORDER_SOURCE, enum: [assembly-plan, override], default: assembly-plan}
    - {name: SLICE_ORDER, required_when: "SLICE_ORDER_SOURCE=override"}
    - {name: PRODUCT_ROOT, default: sister-repo}
auto_resolved:                        # emitted by init-run.py; templates for docs only
  FEATURE_SLUG:  "kebab slug from REGISTRY.md"
  FEATURE_PATH:  "{PRODUCT_ROOT}/planning-mds/features/{FEATURE_ID}-{FEATURE_SLUG}"
  RUN_FOLDER:    "{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}"
  # ...
retrieval:
  tier_defaults: {clean: [1, 2], drift-reconcile: [3, 4]}   # retuned by eval.py
context_load:                         # beyond the shared 4-item preamble in _common.yaml
  - "python3 {PRODUCT_ROOT}/scripts/kg/lookup.py {FEATURE_ID} --tier {start_tier} ..."
  - "{FEATURE_PATH}/**"
ownership:
  product-manager: [pm-closeout.md, signoff-ledger.md, latest-run.json, "kg-source/features/*.yaml#path,status"]
  architect:       [feature-assembly-plan.md, g0-assembly-plan-validation.md, "kg-source/bindings/**", "kg-source/nodes/**"]
  quality-engineer: [test-plan.md, test-execution-report.md, coverage-report.md]
  # ...
gates:
  - id: G0
    title: Architect assembly plan authoring + validation
    role: architect
    artifacts: [g0-assembly-plan-validation.md]
    manifest_status_after: in-progress
    validate:
      - "python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G0"
    judgment: |                       # rendered as prose; NOT executed
      Author or reconcile the assembly plan; validate scope split, dependencies,
      checkpoints, ownership; initialize the Required Signoff Roles matrix.
  # ... G1..G6 similar ...
  - id: G7
    title: Architect KG reconciliation
    role: architect
    role_switch: agents/architect/SKILL.md
    artifacts: [kg-reconciliation.md]
    validate:
      - "python3 {PRODUCT_ROOT}/scripts/kg/compile.py"
      - "python3 {PRODUCT_ROOT}/scripts/kg/validate.py --regenerate-symbols --check-symbols --regenerate-decisions --check-decisions"
      - "python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift"
    constraints:
      - {forbid: "--write-coverage-report", reason: "path-sensitive; deferred to G8 after archive move"}
  - id: G8
    title: PM closeout
    role: product-manager
    role_switch: agents/product-manager/SKILL.md
    sequence:                         # strictly ordered; run-gate.py enforces
      - trackers-and-archive-move    # judgment step, prompt prose describes it
      - "python3 {PRODUCT_ROOT}/scripts/kg/compile.py"
      - "python3 agents/product-manager/scripts/patch-prior-manifest.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --new-run-id {RUN_ID}"
      - write: latest-run.json        # only after prior step exits 0
      - "python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report"
      - "python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift"
      - "python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout"
      - "python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID}"
severity_gate: standard               # -> gate_policy.py profile
forbidden:                            # merged with _common.yaml shared list
  - "Authoring kg-source shards during PM closeout (G7 owns shaping; G8 verifies)"
stop_conditions: [...]
conflict_resolution: [...]
notes:                                # irreducible action-specific prose blocks
  g2_scope_booleans: |
    Set frontend_in_scope=true if any changed_paths[] entry matches experience/** ...
```

Shared files:

```yaml
# agents/actions/spec/_contract.yaml — constants, single-sourced
contract_effective_date: 2026-05-19
run_id_format: "YYYY-MM-DD-[a-z0-9]{8}"
run_id_suffix_cmd: 'python3 -c "import secrets; print(secrets.token_hex(4))"'
run_id_forbidden: [uuid4]
base_run_files: [README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log]
artifacts_subdirs: [coverage, diffs, test-results, security, screenshots]
commands_log_schema: {fields: [schema_version, timestamp, cwd, command, exit_code, artifacts, redactions]}
coverage_min_pct: 80
banned_words: [should, might, probably, usually, easy, simple, fast, secure, ...]
context_preamble: [agents/ROUTER.md, agents/agent-map.yaml, agents/docs/AGENT-USE.md]
```

`_common.yaml` holds the shared FORBIDDEN entries (hint.py/blast.py preflight rules,
lookup-not-authoritative, gate-skipping), shared stop conditions, the runtime
preflight/triage block, and the conflict-resolution table — merged into every action that
declares `contract.scope: feature-completion`.

### Schema governance

- JSON Schema for the spec files, validated by a new
  `agents/scripts/validate_action_specs.py` (added to lifecycle gates).
- `severity_gate` values map to profiles in `gate_policy.py`
  (`standard`, `review-family`, `none`).
- `judgment:` and `notes:` fields are free text by design — the escape hatch that keeps
  the schema from fighting reality.

---

## 6. New Scripts

### 6.1 `agents/scripts/init-run.py` — SESSION_SETUP as code

```
python3 agents/scripts/init-run.py --action feature --feature F0038 \
    [--product-root PATH] [--mode clean] [--rerun-of RUN_ID]
```

Does everything the SESSION_SETUP prose currently asks the LLM to do:

1. Resolve `PRODUCT_ROOT` (reuse `_product_root.py`), `FEATURE_SLUG` from `REGISTRY.md`,
   and all derived paths.
2. Mint `RUN_ID` in contract format (or the integrate scheme when the spec says so).
3. Create `FEATURE_INDEX_ROOT`, `RUN_FOLDER`, and `artifacts/{...}` subdirs.
4. Initialize `evidence-manifest.json` from the template with all skeleton keys,
   `status: draft`, correct `contract_effective_date` (from `_contract.yaml`).
5. Create the base run files from templates; touch empty logs.
6. Run the concurrent-run check (scan sibling manifests for same-feature
   `draft`/`in-progress`); exit non-zero with a clear message on conflict.
7. Capture `RUN_ID_PRIOR` from `latest-run.json` if present.
8. **Emit all resolved variables as JSON to stdout** (and write
   `{RUN_FOLDER}/action-context.md` seed). The prompt shrinks to: "Run `init-run.py`;
   use its JSON output for every variable below."

Idempotency: refuses to re-init an existing non-empty RUN_FOLDER unless `--resume`.

### 6.2 `agents/scripts/run-gate.py` — the gate driver

```
python3 agents/scripts/run-gate.py --action feature --stage G4 \
    --product-root PATH --feature F0038 --run-id 2026-07-12-ab12cd34 [--dry-run]
```

1. Loads `spec/<action>.yaml`, finds the stage.
2. Runs the gate's `validate:`/`sequence:` commands **in order**; stops at first failure.
3. Enforces `constraints:` (e.g. refuses to run a forbidden flag at that stage; warns if
   a G8-only command is attempted at G7).
4. Appends every command to `commands.log` via `append-command-log.py` (closing the
   22-of-24-files gap where the helper is never mentioned) and gate results to
   `lifecycle-gates.log`.
5. Prints a structured verdict: `{stage, status: pass|fail, failed_step, log_refs}`.
6. `--list` mode prints the full ordered exit-validation runbook for the action —
   replacing the prose tables.

Judgment steps inside a `sequence:` (e.g. `trackers-and-archive-move`) are emitted as
"MANUAL: <description>" checkpoints — the driver pauses there (`--until`/`--from` flags)
so the agent performs the judgment work, then resumes the mechanical tail.

### 6.3 `agents/scripts/gate_policy.py` — the severity state machine (module + CLI)

```
python3 -m gate_policy --profile standard \
    --code-critical 0 --code-high 1 --security-critical 0 --security-high 0
→ {"status": "WARNING", "options": ["fix issues", "approve with justification", "reject"],
   "approve_enabled": true, "requires_justification": true}
```

One implementation of the 7×-duplicated policy. Review-family actions
(`plan-review`, `feature-review`) use the `review-family` profile (READY / CONDITIONALLY
READY / NOT READY, TRULY DONE / CONDITIONALLY DONE / NOT DONE). The agent still
*classifies* findings; the module owns the arithmetic and the allowed-options table, and
its JSON is what gets pasted into `gate-decisions.md`.

### 6.4 `agents/scripts/scaffold-product.py` — replaces ~80% of init.md

```
python3 agents/scripts/scaffold-product.py --product-root PATH [--dry-run] [--check]
```

- `mkdir -p` the planning-mds tree; copy each template to its target **iff missing**
  (table of `(template, destination)` pairs lives in `spec/init.yaml`).
- `--check` mode runs the existence-check validation criteria and reports.
- Never writes outside `PRODUCT_ROOT` (assert, don't trust).
- `init.md` keeps only: the user interview for BLUEPRINT sections 0–2, and judgment
  guidance for tailoring the blueprint.

### 6.5 `agents/scripts/render-prompts.py` — the prompt generator

```
python3 agents/scripts/render-prompts.py [--action feature] [--check]
```

- Renders `<action>-operator-friendly.md` and `<action>-automation-safe.md` from
  `spec/<action>.yaml` + `_contract.yaml` + `_common.yaml` using two templates
  (same data, two encodings). Jinja2 (already implied by `requirements.txt` additions)
  or plain `string.Template` if we want zero deps.
- `--check` re-renders to a temp dir and diffs against the committed files; non-zero on
  drift. Added to `lifecycle-stage.yaml` gates and CI.
- Header injected into every rendered file:
  `<!-- GENERATED from agents/actions/spec/feature.yaml — do not edit; run render-prompts.py -->`

### 6.6 `agents/scripts/lint-vague-language.py` — the banned-words linter

Extracts the plan/plan-review/validate word lists into `_contract.yaml:banned_words`,
scans given story/architecture files, reports per-line hits with the ❌→✅ replacement
suggestions. The three prose copies become "run the linter; fix hits or justify."

---

## 7. Changes to Existing Scripts

| Script | Change |
|---|---|
| `validate-feature-evidence.py` | Read the stage→required-artifact matrix from `spec/feature.yaml` (or a shared `stage-matrix.yaml` both import) instead of a private constant. Rule IDs unchanged. Behavior-identical refactor with the existing test suite as the harness. |
| `validate_templates.py` | Replace the hand-maintained `ACTIONS_THAT_MUST_REFERENCE_PACKAGE`, `PROMPTS_FORBIDDEN_UUID4`, `GATE_TEMPLATE_REFS` lists with a call to `render-prompts.py --check` (drift check subsumes them) plus spec-schema validation. |
| `audit-contract.py` | Keep the HARD ownership invariant (now checkable against `spec/*.yaml:ownership` too). The stale-phrase sweep shrinks as prose shrinks; long-term it audits only the hand-written judgment sections. |
| `append-command-log.py` | Unchanged; becomes the single logging path because `run-gate.py` calls it. |
| `run-skill-regression.py` | Add a check that SKILL.md files do **not** contain literal threshold numbers / rule paraphrases that `_contract.yaml` owns (grep for `≥80%`, rule-ID prose blocks) — the inverse of today's checks. |
| `run-lifecycle-gates.py` / `lifecycle-stage.yaml` | Add gates: `action_spec_schema`, `prompt_drift` (`render-prompts.py --check`). |

---

## 8. Thinning the Prose Surfaces

### 8.1 Action files (target shapes)

`feature.md` (1,113 lines today → ~450):

| Section today | Disposition |
|---|---|
| Retrieval Contract YAML (39-50) | Moves to spec (`retrieval:`); eval.py retunes the spec, not the doc |
| Context Files / On-Demand Paths | Spec (`context_load:`); doc keeps one paragraph of navigation philosophy |
| Ownership Contract | Spec (`ownership:`); doc keeps the *why* (2–3 sentences per role) |
| Forbidden | Spec + `_common.yaml`; doc drops the list |
| Gate Contract + Per-Gate Validation table (104-184) | Spec (`gates:`); doc shows the G0–G8 flow diagram only |
| Canonical Evidence Package list (116-151) | Already owned by the validator stage matrix → spec; doc links CONSUMER-CONTRACT.md |
| Closeout Supersession Sequence (153-160) | `run-gate.py G8` sequence; doc: one sentence + pointer |
| Exit Validation (195-210) | `run-gate.py --list`; delete the prose table |
| Runtime Preflight & Triage (219-236) | `_common.yaml` shared block (rendered into prompts); doc keeps the triage *reasoning* rules |
| Steps 0–9 execution instructions | **Keep** — role activation, responsibilities, review criteria are the judgment layer. Strip embedded command lines (point at run-gate) and the ASCII banners (move to templates or drop) |
| Vertical Slicing Best Practices, Examples | Keep (teaching content) |

Same treatment for `build.md` (1,178 → ~500), `review.md`/`validate.md`/`test.md`
(gate arithmetic + JSON blocks replaced by `gate_policy.py` reference), `plan.md`
(exit-validation table + banned-words → scripts), `init.md` (171 → ~60),
`integrate.md` (already tight; I2–I4 mechanical spine moves to spec/run-gate).

### 8.2 Evidence-contract prompts

All 24 become generated. Per-pair maintenance disappears; the irregular blocks
(feature G2 scope-boolean globs, integrate merge3 procedure, defect promotion flow)
live in `notes:` and render verbatim. The `defect-bugfix` and `integrate`
operator-only files simply have `variants: [operator-friendly]` in their spec.

### 8.3 SKILL.md files

1. Extract the verbatim `## Retrieval Guard` into `agents/docs/RETRIEVAL-GUARD.md`;
   each SKILL keeps a 2-line pointer. (Fixes the two drifted copies.)
2. Replace the six paraphrased `## Feature Evidence Contract` sections with a short
   role-scoped pointer: "Your `<report>.md` must pass these validator rules:
   `<rule-id list>` — see CONSUMER-CONTRACT.md §N. Run
   `validate-feature-evidence.py --stage <G>` before handing off." Rule IDs are stable
   identifiers; prose paraphrases are not.
3. Delete literal thresholds; reference `_contract.yaml` values by name
   ("coverage floor: `coverage_min_pct`").
4. Move the QE Quick-Reference command tables and the code-reviewer KG-threshold gates
   (`kg.risk ≥ 7 → extra reviewer`) into spec/config; SKILL keeps the judgment guidance.
5. Result: all 12 SKILLs comfortably under the 500-line regression ceiling.

---

## 9. Migration Plan

Each phase is independently shippable and gated by the existing test suites
(`agents/product-manager/scripts/tests/`, `agents/scripts/tests/`,
`run-skill-regression.py`, `run-lifecycle-gates.py`).

### Phase 1 — Foundations (low risk, ~2–3 days)

1. Add `agents/actions/spec/_contract.yaml` + JSON schema + `validate_action_specs.py`.
2. Build `init-run.py` (reuse `_product_root.py`; unit tests with a fixture product
   root; cover concurrent-run check and idempotency).
3. Build `gate_policy.py` with table-driven tests reproducing every IF/ELIF block from
   the seven action files (this is the regression proof that behavior is unchanged).
4. Extract `RETRIEVAL-GUARD.md`; fix the two drifted copies; update
   `run-skill-regression.py`.
5. **Acceptance:** all existing gates green; one feature-run smoke test using
   `init-run.py` produces a skeleton that `validate-feature-evidence.py --stage G0`
   accepts.

### Phase 2 — Prompt generation (~3–4 days)

1. Author `spec/feature.yaml` first (hardest case: 9 gates, closeout sequence, all the
   irregular notes). Render and **diff against the current hand-written pair** —
   iterate the template until the rendered output is semantically equivalent (this diff
   review is the main effort).
2. Roll out the remaining 12 specs (each far smaller than feature).
3. Wire `render-prompts.py --check` into `lifecycle-stage.yaml` and CI; add the
   GENERATED header; simplify `validate_templates.py` prompt lists.
4. **Acceptance:** `render-prompts.py --check` green in CI; `audit-contract.py` sweep
   count does not increase; a manual read of feature/build/plan pairs signs off
   semantic equivalence.

### Phase 3 — Gate driver + action thinning (~4–5 days)

1. Build `run-gate.py` against `spec/feature.yaml`; dry-run mode first.
2. Pilot on one real feature run in the product repo (pwb): agent uses
   `init-run.py` + `run-gate.py` end-to-end; compare evidence package to a
   prose-driven run.
3. Thin `feature.md` and `build.md` per §8.1; regenerate prompts (they now reference
   the driver); update `audit-contract.py` sweep list.
4. Extend to plan/review/test/validate/integrate; ship `scaffold-product.py` and
   `lint-vague-language.py`; thin `init.md`/`plan.md`.
5. **Acceptance:** a full governed feature run completes with every command routed
   through `run-gate.py`, `commands.log` fully populated via `append-command-log.py`,
   and `validate-feature-evidence.py --stage closeout` exit 0.

### Phase 4 — Validator convergence + SKILL cleanup (~3 days)

1. Refactor `validate-feature-evidence.py` to import the stage matrix from spec
   (behavior-identical; existing pytest suite is the harness).
2. SKILL.md thinning per §8.3; add the inverse checks to `run-skill-regression.py`.
3. Retire the now-redundant `STALE_PATTERNS` entries and `validate_templates.py`
   hard-coded lists.
4. **Acceptance:** all SKILLs < 500 lines; grep finds no literal `80%` thresholds or
   validator-rule paraphrases in SKILL prose; full lifecycle gates green.

Total: roughly 12–15 working days, parallelizable after Phase 1.

---

## 10. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| **Rendered prompts lose nuance** — a paraphrase in the hand-written file carried meaning the spec missed | Phase 2 requires a human semantic-equivalence review per action pair before switching; `notes:` free-text fields are the escape hatch, and anything that resists the schema stays prose |
| **Agents stop *understanding* the contract** because prompts say "run the script" without the why | Keep one-sentence rationales in the rendered output (spec `reason:` fields — e.g. why coverage regeneration is post-move). Understanding the *why* is judgment content; we keep it, we just stop restating the *what* |
| **run-gate.py becomes a second place gate logic lives** (vs the validators) | The driver only *sequences* commands from spec; it asserts nothing the validators don't. Pass/fail always comes from the invoked validator's exit code |
| **Generated-file merge conflicts** on concurrent branches | Files are regenerable; conflict resolution = re-run `render-prompts.py`. Document in CONTRIBUTING.md |
| **Product repos consuming CONSUMER-CONTRACT.md** see churn | The contract document and validator rule IDs are unchanged; only the framework's internal encoding moves. Note it in CHANGELOG.md and the consumer contract's effective-date mechanism |
| **Spec schema too rigid for the next new action** | `judgment:`/`notes:` free text plus per-action `extra_sections:`; the schema validates structure, not content |
| **LLM ignores the driver and hand-runs commands** | The rendered FORBIDDEN list includes "running gate validation commands directly instead of via run-gate.py"; `commands.log` review at signoff catches it; long-term, `validate-feature-evidence.py` can check that gate results in `lifecycle-gates.log` were driver-emitted |

---

## 11. What Deliberately Stays Prose

- Reviewer criteria checklists (feature-review 2a–2f, plan-review 1a–1c, code/security
  review guidance) — genuine reasoning.
- Severity *classification* of findings (the arithmetic after it is `gate_policy.py`).
- Plan clarification-question generation and story-writing guidance.
- Architect judgment at G7: deciding which directory glob constitutes one capability.
- Drift-reconcile repair reasoning; semantic-collision calls in integrate.
- blog.md and document.md almost entirely (voice, structure, editorial judgment) —
  they gain only `init-run.py` for their base evidence package.
- Teaching content: vertical-slicing best practices, examples, anti-patterns.

---

## 12. Open Questions

1. **Commit rendered prompts or render at use-time?** Proposal: commit + CI drift check
   (consumers without Python tooling can still read them; git history stays reviewable).
2. **Jinja2 dependency** — acceptable in `agents/scripts/requirements.txt`, or prefer
   stdlib templating? (Jinja2 recommended; the two-variant rendering wants real
   conditionals/loops.)
3. **Should `run-gate.py` live in the framework or be seeded into product repos** like
   `scripts/kg/*`? Proposal: framework (it's stack-agnostic orchestration), invoked with
   `--product-root`, consistent with the existing validator placement.
4. **Sequencing with in-flight work** — coordinate with any open feature runs in pwb so
   a run doesn't straddle prose-driven and driver-driven gates mid-flight.

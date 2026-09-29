# F0007-S0006 — Semantic-Equivalence Review of Generated Evidence Prompts

**Scope:** all 24 generated prompts under `agents/templates/prompts/evidence-contract/`
**Method:** requirement-level comparison of each prompt's last hand-written revision against
its current generated output, plus adversarial verification of the gates that guard the
cutover.
**Baseline:** commit `35237bf` — the last commit before the S0006 cutover began (#55).
**Reviewer:** automated analysis (Claude). **Date:** 2026-08-30.

> **This document is evidence, not acceptance.** It establishes what changed and what was
> lost. Role-owner signoff remains outstanding and is recorded in `STATUS.md`.
>
> **SE-1 was fixed on 2026-08-30** (§3, recommendation 1). SE-2 through SE-6 and GV-1/GV-2
> remain open. SE-3 is deliberately left unfixed pending the cross-repo pilot — see §8.

## 1. Method

All 24 prompts existed as hand-authored files at `35237bf`, so equivalence is checkable
rather than a matter of opinion. For each prompt, normative elements — artifact filenames,
gate IDs, placeholders, declared inputs, and commands — were extracted from both revisions.
Every element present in the baseline and absent from the generated output was then traced
into one of four recovery sites: the sibling variant, another generated prompt, the action
spec, or a pointer document (`CONSUMER-CONTRACT.md`, `AGENTIGNORE.md`, `AGENT-USE.md`).
Elements recovered nowhere were inspected by hand and either confirmed as losses or
dismissed as extraction noise.

Raw counts before triage: 192 dropped elements, 98 unrecovered. Most of the 98 were
artifacts of the extraction patterns, not real losses; the confirmed findings are below.

## 2. Direction of travel

The cutover made the prompts **stronger** on most measured axes. Presence counts across the
24 prompts, baseline versus generated:

| Normative behaviour | Baseline | Generated |
|---|---|---|
| `schema_version` in telemetry | 3 | 20 |
| Redaction / secret-leak rule | 3 | 20 |
| `lifecycle-gates.log` | 17 | 24 |
| `evidence-manifest.json` | 10 | 17 |
| Run-ID method (`secrets.token_hex`) | 23 | 23 |
| `commands.log` telemetry | 24 | 24 |
| Echo resolved `NEBULA_PRODUCT_ROOT` | 24 | 24 |
| `AGENT-USE.md` pointer | 24 | 24 |
| **`CONSUMER-CONTRACT.md` pointer** | **23** | **0** |

Only two measured behaviours regressed. Both are findings below (SE-3, SE-6).

## 3. Findings — prompt semantics

### SE-1 · High · Declared input constraints are silently dropped — **FIXED 2026-08-30**

`render-prompts.py` reads only `name`, `format`, and `default` from a spec's `inputs`
block. Two other declared keys are never emitted:

- **19 `enum` declarations** — the set of legal values for an input
- **15 `required_when` declarations** — conditional-requirement rules

**34 declarations across 12 of the 13 actions never reach any prompt.** Representative cases:

| Action | Input | Declared in spec | In prompt |
|---|---|---|---|
| `feature` | `MODE` | `[clean, drift-reconcile]` | `MODE — default clean` |
| `feature` | `SLICE_ORDER` | `required_when SLICE_ORDER_SOURCE=override` | bare name |
| `validate` | `STAGE` | `[G0,G1,G2,G3,G5,G6,G8,closeout]` | `STAGE — default closeout` |
| `integrate` | `MODE` | `[live, dry-run]` | not declared |
| `review` | `PATHS` | `required_when SCOPE=path-set` | bare name |
| `integrate` | `WAIVER` | `required_when no REVIEW_VERDICT_REF` | bare name |

The consequence is concrete: an agent reading `feature-operator-friendly.md` cannot learn
that `drift-reconcile` is a legal `MODE`; one reading `integrate-operator-friendly.md`
cannot learn that `dry-run` exists as a mode; one reading `review-*.md` is not told that
`PATHS` becomes required under `SCOPE=path-set`. The `integrate` `WAIVER` /
`REVIEW_VERDICT_REF` mutual-exclusion rule is invisible in the prompt.

The hand-written baseline carried these inline — `MODE={clean | drift-reconcile}`,
`SLICE_ORDER=` … `required only when SLICE_ORDER_SOURCE=override`. So this is a
**regression introduced by the cutover**, not a pre-existing gap.

**`prompt_drift` cannot detect this class of defect.** The gate compares committed output
against freshly rendered output; both come from the same renderer, so a constraint the
renderer never emits is equally absent from both sides and the comparison is green. This is
exactly the failure mode `contract-conformance.py`'s own docstring warns about — "prompts,
runners, and validators derived from one spec can all agree on a weakened … contract."

**Fix — applied.** `render-prompts.py` gained `_input_constraints()`, emitting both keys in
each variant's input block; all 24 prompts were regenerated. 22 files changed, 59 lines
modified 1:1 — every changed line is an input declaration, and no other prompt content
moved. The two `init` prompts declare no such constraints and were untouched, which is the
predicted result. Rendered form:

```
- `MODE` — one of `clean` | `drift-reconcile` — default `clean`      (operator-friendly)
- MODE enum:[clean|drift-reconcile] =default:clean                    (automation-safe)
- SLICE_ORDER required_when:[SLICE_ORDER_SOURCE=override]
```

Square brackets rather than braces: `PLACEHOLDER_RE` treats `{IDENT}` as a placeholder, and
a brace-wrapped single-value enum would trip `_semantic_check`'s unresolved-placeholder
guard. All 34 declarations were confirmed present in every variant after regeneration.

**Regression guard — verified by breaking it.** Since `prompt_drift` structurally cannot
catch this class, three tests were added to `test_render_prompts.py`: a renderer unit test,
a brace-collision test, and a per-spec sweep asserting every declared constraint appears in
the committed prompts. Reverting the renderer and regenerating reproduces the exact
regression shape — and confirms the diagnosis:

| | result |
|---|---|
| `render-prompts.py --check` (`prompt_drift`) | **exit 0 — blind** |
| `test_every_declared_constraint_reaches_the_committed_prompts` | **9 of 13 specs fail** |

That is the finding demonstrated rather than argued: the CI gate passes a prompt set that
has silently lost 34 declared constraints, and only the new test objects.

### SE-2 · Medium · The working-state protocol was dropped

The baseline `feature-*` prompts carried an explicit five-command protocol:

```
- workstate.py … init --role feature --scope {FEATURE_ID} …
- workstate.py decision --topic <slug>   after each gate pass
- workstate.py touch <path>              after significant file changes
- workstate.py dump --compact            after any compaction event
- workstate.py escalate <reason>         on INSUFFICIENT_CONTEXT
```

The generated prompts retain one incidental mention — `log via workstate.py decision
--topic plan-story-reconcile`, inside `CONFLICT_RESOLUTION`. Tracing each subcommand:

| Subcommand | In prompts | In specs | Recoverable elsewhere |
|---|---|---|---|
| `decision` | yes | yes | — |
| `escalate` | yes | yes | — |
| `init --role` | **no** (2→0) | no | `AGENT-USE.md`, `KNOWLEDGE-GRAPH.md` |
| `dump` | **no** (2→0) | no | `agents/actions/build.md`, `plan.md` |
| `touch` | **no** (2→0) | no | **nowhere** |

`touch` remains a live subcommand of `scripts/kg/workstate.py`, so this is documentation
loss rather than a stale reference. The surviving `decision` instruction now tells an agent
to record into a working-state file that no prompt tells it to `init`.

The practical cost falls on session resume and compaction (`resume-brief.py`,
`SESSION-SEGMENTATION.md`), which read the state these commands maintain.

### SE-3 · Medium · The `CONSUMER-CONTRACT.md` pointer is gone

23 of 24 baseline prompts opened by naming the authoritative contract document — e.g.
`CONTRACT: Feature Evidence Contract in CONSUMER-CONTRACT.md (effective 2026-05-19)`. **No
generated prompt references it.**

The document is not obsolete: it is 320 lines, still referenced by `README.md`,
`CONTRIBUTING.md`, `Dockerfile`, two role SKILLs, and two action docs, and it defines the
`{NEBULA_PRODUCT_ROOT}` path-indirection convention that every prompt depends on.

The specs do preserve the reference — but **only inside YAML comments** (`# … see
agents/actions/<action>.md and CONSUMER-CONTRACT.md`), which the parser discards and the
renderer therefore cannot emit. The link is structurally unable to survive compilation.

If dropping the pointer was deliberate — the spec, not the prose document, is now
authoritative — then the finding inverts: `CONSUMER-CONTRACT.md` is a live document that
nothing generated points to, and its relationship to the spec should be stated explicitly.
**This one needs a role-owner ruling rather than a code fix.**

### SE-4 · Low · Template provenance and the plan-overwrite rule

The baseline named the templates an agent authors from:

- `Initialize {RUN_FOLDER}/evidence-manifest.json from agents/templates/evidence-manifest-template.json`
- `Architect authors {FEATURE_PATH}/feature-assembly-plan.md from agents/templates/feature-assembly-plan-template.md … On drift-reconcile/rerun: reconcile the existing plan, do not overwrite`

The generated prompts say `Initialize evidence-manifest.json (status draft, contract version
stamped, …)` and list `feature-assembly-plan.md` as an architect artifact, without naming
either template. Both templates still exist under `agents/templates/`.

The clause **"reconcile the existing plan, do not overwrite"** went 1→0 across prompts and
is absent from the specs. The `CONFLICT_RESOLUTION` line that survives states which source
wins in a conflict; it does not state that an existing plan must not be overwritten on a
rerun.

### SE-5 · Low · Dropped retrieval targets

`{NEBULA_PRODUCT_ROOT}/planning-mds/security/authorization-matrix.md` appeared in 4 baseline
prompts (`plan-*`, `feature-*`) as an on-demand retrieval target and appears in none of the
generated prompts or specs. It is a product-owned path, absent from this repo, so the loss
is a retrieval hint rather than a broken reference.

### SE-6 · Low · `plan-operator-friendly.md` lost the `artifacts/` subdir convention

The only other measured presence regression. `plan-operator-friendly.md` no longer mentions
the `artifacts/` subdirectory convention its baseline carried; the sibling
`plan-automation-safe.md` still does.

## 4. Findings — gate verification

Per the working rule that a passing gate proves nothing until it has been made to fail,
each guard was tested by breaking what it guards. Restoration was verified after every test.

### Guards confirmed working

| Guard | Perturbation | Result |
|---|---|---|
| `prompt_drift` | append a line to a generated prompt | exit 1, diff reported |
| `prompt_drift` | change a gate title in the spec, do not regenerate | exit 1 (operator-friendly only — titles do not reach automation-safe) |
| `prompt_drift` | change a gate's artifact name in the spec | exit 1 (both variants) |
| `prompt_drift` | delete a generated prompt | exit 1, `missing` populated |
| `prompt_drift` | leak an undeclared variant for a known action | exit 1, `undeclared_extra` populated |
| `contract_compat --matrix` | shift `SECURITY_SCANS_EFFECTIVE_DATE` by one cutover | exit 1, 2 disagreeing cases |

**Reviewer error, recorded:** an earlier test dropped a file named `rogue-automation-safe.md`
into the generated directory and reported it as an undetected gap. That was wrong. The
check is scoped to known action names by design — its source comment says so — and it fires
correctly for the case it claims to cover, as the table shows. The residual behaviour (a
file named for a non-action is not flagged) is not a defect, since prompt lookup is by
action name.

### GV-1 · High · The conformance gate does not see a weakened working contract

`contract-conformance.py` is described in `lifecycle-stage.yaml` as catching "a weakened
contract even when generated output matches," and `rollout-report.md` §1 lists it as
blocking on a weakened contract.

Two weakening edits were made to the **active** `agents/actions/spec/_contract.yaml`:

| Edit | `prompt_drift` | `action_spec_schema` | `contract_conformance` |
|---|---|---|---|
| `coverage_min_pct: 80 → 10` | **exit 1** | exit 0 | exit 0 |
| drop `dast` from `required_security_scan_classes` | exit 0 | exit 0 | exit 0 |

With `dast` dropped, **the full six-gate CI suite passes.** `validate_action_specs.py` even
prints the weakened value in its summary without complaint.

The cause is structural. `check_baseline()` iterates `policy.bundles` — the frozen
`history/*.yaml` snapshots — and compares them to golden fixtures. Editing `_contract.yaml`
does not touch a published bundle, so the matrix is unaffected. **Nothing asserts that the
working contract still matches the published bundle for the active version.** The two are
currently identical, which is what makes the gap invisible.

The coverage weakening was caught only by `prompt_drift`, and only incidentally, because
`coverage_min_pct` happens to be interpolated into prompt text. That is an accidental guard
covering exactly the subset of contract values that reach prompt prose.

**Fix:** add an invariant asserting `_contract.yaml`'s shared block equals
`history/<active_version>.yaml`'s, and fail when they diverge without a version bump.

### GV-2 · High · `required_security_scan_classes` is enforced only by the private constant

This bears directly on the open S0007/S0008 decision and qualifies the parity evidence.

`validate-feature-evidence.py:39` hardcodes:

```python
REQUIRED_SECURITY_SCAN_CLASSES = ("dependency", "secrets", "sast", "dast")
```

It is a private constant, not read from policy. Tracing every consumer of the policy key:
`validate_action_specs.py` only sorts it for hashing; the rest are schema files and the
baseline fixtures. **No runtime consumer reads the policy value** — so the policy's copy is
decorative, and the private constant is the sole enforcement of DAST.

The dual-read parity matrix does not cover it. `contract_compat.py --matrix` compares
exactly four keys:

```
compile_projection_contract, kg_generated_regen_required,
kg_reconciliation_required, security_scans_required
```

All four are booleans. `required_security_scan_classes` (a tuple) and `coverage_min_pct`
are not compared. Verified by breaking both sides:

| Perturbation | Parity matrix |
|---|---|
| shift a date-gated boolean constant | **exit 1** — disagreement reported |
| drop `dast` from the private constant | exit 0 — zero disagreement |

So the value is unguarded on **both** sides: weakening it in the policy passes every gate
(GV-1), and weakening it in the private constant passes the parity check.

**Consequence for the removal decision:** "zero disagreement across all cutovers" is
accurate but narrower than it reads — it certifies four date-gated booleans, not the
constants generally. Removing the private constants as currently written would delete the
only enforcement of `required_security_scan_classes`, because nothing else reads it at
runtime. The parity evidence does not cover the constant that matters most here.

This is not an argument against removal. It is an argument that removal needs a policy
consumer wired first, and that GV-1 should be closed so the policy value cannot be weakened
unnoticed once it becomes load-bearing.

## 5. Verdict by prompt

Equivalence is assessed as **preserved** (no normative loss), **preserved with
qualification** (loss recovered in a sibling, spec, or pointer doc), or **regressed**.

| Prompt | Verdict | Findings |
|---|---|---|
| `feature-automation-safe.md` | Regressed | SE-1, SE-2, SE-3, SE-4 |
| `feature-operator-friendly.md` | Regressed | SE-1, SE-2, SE-3, SE-4, SE-5 |
| `plan-automation-safe.md` | Regressed | SE-1, SE-3, SE-5 |
| `plan-operator-friendly.md` | Regressed | SE-1, SE-3, SE-5, SE-6 |
| `review-automation-safe.md` | Regressed | SE-1, SE-3 |
| `review-operator-friendly.md` | Regressed | SE-1, SE-3 |
| `test-automation-safe.md` | Regressed | SE-1, SE-3 |
| `test-operator-friendly.md` | Regressed | SE-1, SE-3 |
| `validate-automation-safe.md` | Regressed | SE-1, SE-3 |
| `validate-operator-friendly.md` | Regressed | SE-1, SE-3 |
| `integrate-operator-friendly.md` | Regressed | SE-1, SE-3 |
| `feature-review-automation-safe.md` | Regressed | SE-1, SE-3 |
| `feature-review-operator-friendly.md` | Regressed | SE-1, SE-3 |
| `plan-review-automation-safe.md` | Regressed | SE-1, SE-3 |
| `plan-review-operator-friendly.md` | Regressed | SE-1, SE-3 |
| `build-automation-safe.md` | Regressed | SE-1, SE-3 |
| `build-operator-friendly.md` | Regressed | SE-1, SE-3 |
| `blog-automation-safe.md` | Regressed | SE-1, SE-3 |
| `blog-operator-friendly.md` | Regressed | SE-1, SE-3 |
| `document-automation-safe.md` | Regressed | SE-1, SE-3 |
| `document-operator-friendly.md` | Regressed | SE-1, SE-3 |
| `defect-bugfix-operator-friendly.md` | Regressed | SE-1, SE-3 |
| `init-automation-safe.md` | Preserved with qualification | SE-3 |
| `init-operator-friendly.md` | Preserved with qualification | SE-3 |

No prompt is assessed as fully preserved, because SE-3 touches 23 of 24 and SE-1 touched 22
of 24. The two `init` prompts declare no `enum` or `required_when` inputs, so SE-1 never
applied to them.

**SE-1 has since been fixed and the prompts regenerated**, so every "Regressed" verdict
above now rests on SE-2 through SE-6. On the SE-1 axis alone the current generated set is
equivalent to the hand-written baseline.

**This is not a verdict that the cutover was wrong.** Section 2 shows the generated prompts
carry materially more telemetry, redaction, and manifest discipline than the hand-written
originals. SE-1 is one renderer defect reproduced 34 times, and SE-3 is one structural
consequence of holding a pointer in a YAML comment. Both are narrow fixes.

## 6. Recommendation

Semantic equivalence is **not yet established**. Recommended before role-owner signoff:

1. ~~**SE-1** — emit `enum` and `required_when` from the renderer.~~ **Done 2026-08-30.**
   34 losses across 12 actions closed by one renderer change; regression tests added and
   verified by reverting the renderer. `prompt_drift`, the full six-gate suite, and 206
   script tests are green.
2. **GV-1** — add the working-contract-versus-published-bundle invariant to
   `contract-conformance.py`. Until this lands, no gate green is evidence about the
   contract's strength.
3. **GV-2** — settle before the S0007/S0008 removal decision, with the qualification above
   on record.
4. **SE-2** — restore the working-state protocol, or state that it now lives in
   `AGENT-USE.md` and drop `touch` from the tool if it is genuinely unused.
5. **SE-3** — role-owner ruling: restore the pointer via a rendered field, or record that
   the spec supersedes `CONSUMER-CONTRACT.md` and reconcile that document accordingly.
6. **SE-4 / SE-5 / SE-6** — low severity; fold into the SE-1 regeneration pass.

## 7. Reproduction

Every result above is reproducible from a clean tree. The guard tests each restore the
tree; `git status --short agents/` was confirmed clean after each.

```bash
# baseline corpus
git show 35237bf:agents/templates/prompts/evidence-contract/<name>.md

# SE-1: constraints declared but never rendered
.venv/bin/python - <<'PY'
import yaml, pathlib
for p in sorted(pathlib.Path("agents/actions/spec").glob("*.yaml")):
    if p.name == "_contract.yaml": continue
    inp = (yaml.safe_load(p.read_text()).get("inputs") or {})
    for kind in ("required", "optional"):
        for item in inp.get(kind) or []:
            for k in ("enum", "required_when"):
                if k in item: print(p.stem, item["name"], k, item[k])
PY

# GV-1: weaken the active contract, run the full CI suite
sed -i 's/\[dependency, secrets, sast, dast\]/[dependency, secrets, sast]/' agents/actions/spec/_contract.yaml
.venv/bin/python agents/scripts/run-lifecycle-gates.py   # passes
git checkout -- agents/actions/spec/_contract.yaml

# GV-2: parity does not cover the scan-class tuple
sed -i 's/^REQUIRED_SECURITY_SCAN_CLASSES = ("dependency", "secrets", "sast", "dast")/REQUIRED_SECURITY_SCAN_CLASSES = ("dependency", "secrets", "sast")/' \
  agents/product-manager/scripts/validate-feature-evidence.py
.venv/bin/python agents/product-manager/scripts/contract_compat.py --matrix   # ok: true
git checkout -- agents/product-manager/scripts/validate-feature-evidence.py
```

## 8. Scope limit of this review, and the cross-repo gap

This review compared text to text. That method establishes what the cutover dropped; it
cannot establish whether a generated prompt still *works*. Those are different questions,
and the second one has an unexercised gap behind it.

**The F0003 pilot never crossed a repo boundary.** Its `commands.log` for run
`2026-08-29-16075bda` records `--product-root` resolving to
`/home/gajap/uSandbox/repos/nebula/nebula-agents` in 14 invocations and `.` in 2, with zero
references to a sister product repo. The framework acted as its own product root for the
entire G0–G8 run.

So `{NEBULA_PRODUCT_ROOT}` path-indirection — the convention `CONSUMER-CONTRACT.md` §1 exists to
define, and the reason the framework is a separate repo at all — has never been exercised in
a governed run. `rollout-report.md` §2 asked for precisely this: "the LIVE governed pilot on
a real product feature (real `feature.yaml` operations + `{NEBULA_PRODUCT_ROOT}/scripts/kg/*` …)".
F0003 satisfied the "governed run reaches closeout" half of that sentence. It did not
satisfy the cross-repo half.

This bears directly on **SE-3**. In a self-rooted run every path resolves correctly whether
or not the agent understands the indirection convention, so a prompt that no longer points
at the document defining it looks harmless. Against a separate product repo it is the first
thing that matters.

**SE-3 is therefore deliberately left unfixed.** Whether the dropped pointer actually
degrades a run is genuinely unknown, and a cross-repo pilot is the experiment that settles
it. Fixing it first would destroy the signal. SE-1 was fixed ahead of any such pilot for the
opposite reason: a prompt that never names an input's legal values is a known defect with a
diagnosed cause, and leaving it in place would risk a run failure being misattributed to the
cross-repo path when the actual cause sits upstream of it.

**Recommended record correction, independent of any further run.** `STATUS.md` and the
`rollout-report.md` should state what F0003 proved — a governed run reaching closeout,
self-rooted — and what it did not. The current wording records the live governed pilot as
satisfied without that distinction, which reads as broader evidence than the run produced.

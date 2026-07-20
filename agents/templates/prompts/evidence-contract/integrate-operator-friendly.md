<!-- GENERATED from agents/actions/spec/integrate.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action integrate -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


This prompt encodes the **Feature Evidence Contract** (scope `merge`, policy `2026-07-11`).

Required inputs:
- `INTEGRATION_BRANCH` (format `target integration branch — never main; a maintainer-designated train or integrator-created integrate/<date>-train`)

Optional inputs (defaults apply when omitted):
- `PR_URL`
- `SOURCE`
- `REVIEW_VERDICT_REF`
- `WAIVER`
- `MODE` — default `live`
- `PRODUCT_ROOT` — default `sister-repo`

Auto-resolved (do not set; SESSION_SETUP / the orchestrator compute these):
- `MERGE_BASE` — git merge-base {INTEGRATION_BRANCH} {SOURCE}
- `RUN_FOLDER` — {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}

Generate `RUN_ID` once at session start in the contract format `integrate-YYYYMMDD-HHMMSS (UTC)` using `date -u +%Y%m%d-%H%M%S`. Do not use: uuid4.

Session setup: create the run under `planning-mds/operations/evidence/`, initialize `evidence-manifest.json` (status `draft`) with the active contract version stamped, create the base run files (README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log) and artifact subdirs (coverage, diffs, test-results, security, screenshots). Run `agents/scripts/init-run.py` to perform this.

Load context in this order, then navigate rather than eager-load:
1. `agents/ROUTER.md`
2. `agents/agent-map.yaml`
3. `agents/docs/AGENT-USE.md`
4. `agents/integrator/SKILL.md`
5. `agents/actions/integrate.md`
6. `agents/templates/integration-evidence-template.md`

Gates (run each stage through `agents/scripts/run-gate.py`, in order):
- **I0 — Gate 1 — feature-review verdict (maintainer)** (role: integrator; artifacts: none)
    - MANUAL checkpoint `review-verdict-gate`: Verify a passing REVIEW_VERDICT_REF, or record the maintainer's WAIVER + rationale in gate-decisions.md. Missing both -> halt; the evidence run records the missing gate; nothing is merged. (requires: REVIEW_VERDICT_REF (passing feature-review) or a maintainer WAIVER + rationale; produces: I0 authorization row in gate-decisions.md)
    - judgment: A waiver covers this run only. First post-train integration should run with NO blanket waiver — supply a
real REVIEW_VERDICT_REF (or deliberately omit both to exercise the halt).
- **I1 — Branch verification (bounce check)** (role: integrator; artifacts: none)
    - judgment: On {SOURCE}'s OWN content: regenerate its generated projections from its sources and compare to its
committed copies; scan for code-overlap with {INTEGRATION_BRANCH}. Committed != regenerated -> BOUNCE to
the contributor with the exact regeneration commands; the evidence run records the bounce and the run ends.
The integrator never fixes contributor branches.
- **I2 — Merge (git + semantic KG/tracker)** (role: integrator; artifacts: none)
    - judgment: In the worktree: `git merge --no-commit {SOURCE}` (code merges via git; code conflicts halt here as
ordinary git work — the integrator never resolves them). Then for each curated KG file changed on BOTH
sides since {MERGE_BASE}, and for REGISTRY.md and ROADMAP.md:
`python3 {PRODUCT_ROOT}/scripts/kg/merge3.py <file> --base {MERGE_BASE} --ours {INTEGRATION_BRANCH}
--theirs {SOURCE} --json {RUN_FOLDER}/artifacts/merge3-<name>.json`. Any typed conflict -> halt; the
conflict report (text + JSON) names the owning role per record kind (architect: nodes/bindings; PM:
features/trackers; co-sign: exclusions). Nothing is committed; the owner resolves on the contributor
branch and the maintainer re-invokes as a NEW run.
- **I3 — Unconditional regeneration** (role: integrator; artifacts: none)
    - judgment: Even (especially) when git reported a clean merge of generated files, regenerate from source:
`python3 {PRODUCT_ROOT}/scripts/kg/validate.py --regenerate-symbols --check-symbols --regenerate-decisions
--check-decisions`, then `--write-coverage-report`, then
`python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/`.
Never trust a textually clean git merge of a generated file.
- **I4 — Full validation** (role: integrator; artifacts: none)
    - judgment: All must exit 0: `python3 {PRODUCT_ROOT}/scripts/kg/validate.py`; `... --check-drift`; and
`python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT}
--skip-feature-evidence`. Story-index regeneration must be zero-diff on re-run. A failure after a clean
semantic merge -> halt with ConstraintViolation routed to the owning role.
- **I5 — Evidence + prepared merge** (role: integrator; artifacts: integration-report.json)
    - judgment: Complete the integration evidence run (template agents/templates/integration-evidence-template.md),
commit the merge on the worktree branch, and record the prepared-merge SHA in integration-report.json and
action-context.md (the run outcome in action-context.md must match integration-report.json). Do NOT push.
- **I6 — Gate 2 — human test validation (maintainer)** (role: integrator; artifacts: none)
    - MANUAL checkpoint `human-test-gate`: STOP. The maintainer exercises the feature on the prepared-merge worktree and records pass/fail in gate-decisions.md + integration-report.json. Pass -> the maintainer pushes to the integration branch. Fail -> treated as a bounce: nothing pushed, routed, any later re-run is a new run. (requires: integration-report.json; produces: I6 pass/fail verdict; on pass, the maintainer's push to the integration branch)

Severity gate profile: `none` (compute allowed outcomes with `agents/scripts/gate_policy.py`; coverage floor is 80%).

Ownership (strict):
- **integrator** owns: integration-report.json, per-file merge3 reports under {RUN_FOLDER}/artifacts, gate-decisions.md, the prepared merge commit on the integration-branch worktree

Forbidden:
- Generate RUN_ID with uuid4 (use the integrate-<UTC-timestamp> scheme).
- Operate on the operator's checkout — work in a dedicated worktree (git worktree add <tmp> {INTEGRATION_BRANCH}).
- Push, touch main, or run two integrations concurrently.
- Edit ANY source-authored file (feature docs, architecture, schemas, API contracts, code, Phase-B kg-source/**) — needing to is a semantic collision: abort and self-report in the evidence run.
- Trust a textually clean git merge of a generated file — regenerate regardless.
- Resolve code conflicts — surface them and halt.
- Edit a prior evidence run — a re-run is a NEW run with supersedes_run set.

Stop conditions:
- Gate I0 cannot be satisfied (no passing REVIEW_VERDICT_REF and no maintainer WAIVER).
- The I1 bounce check fails (committed generated files != regenerated on {SOURCE}).
- Any typed KG/tracker conflict (I2) or validation failure (I4) occurs.
- A source-authored file edit becomes necessary (semantic collision).
- INSUFFICIENT_CONTEXT occurs — escalate, open raw artifacts, do not proceed on weak matches.

Conflict resolution:
- curated KG file or REGISTRY.md/ROADMAP.md changed on both sides -> merge3.py typed 3-way merge; any typed conflict halts and routes to the owning role (architect: nodes/bindings; PM: features/trackers; co-sign: exclusions).
- code conflict in git merge -> surface and halt; integrate never resolves code conflicts.
- a source-authored file needs editing -> semantic collision; abort, self-report in the evidence run, route to the owner.
- re-integration of a bounced or updated branch -> a NEW run with supersedes_run set; never edit a prior evidence run.

Note (branch_strategy): Integration lands ONLY on {INTEGRATION_BRANCH}; main receives exactly one promotion merge from that branch
after the train completes, pushed by the maintainer. Stale main is not a valid merge base. In steady state
the integrator creates a dedicated integrate/<date>-train branch per train and the same promotion rule applies.

Note (evidence_outputs): In {RUN_FOLDER}: the six §8 base run files, integration-report.json (per
agents/templates/integration-evidence-template.md), and the per-file merge3/tracker JSON reports under
artifacts/. On success: a prepared merge commit on the integration-branch worktree awaiting I6 + maintainer
push. On bounce/halt: the bounce or conflict report addressed to the contributor or owning role; nothing merged.

Note (session_setup): Echo the resolved absolute {PRODUCT_ROOT} on the first turn. Mint RUN_ID as integrate-<UTC-timestamp>
(`integrate-$(date -u +%Y%m%d-%H%M%S)`); never uuid4. RUN_FOLDER is under planning-mds/operations/evidence/runs/.
Work in a dedicated worktree (`git worktree add <tmp> {INTEGRATION_BRANCH}`); never operate on the operator's
checkout; never push; never merge to main. MODE=dry-run prepares nothing for push and labels simulated inputs.

Note (source_resolution): PR_URL is the usual source: `gh pr checkout <PR#>` materializes the contributor branch locally, then
`gh pr view <PR_URL> --json headRefName,baseRefName,state` -> SOURCE=<headRefName>. Explicit SOURCE always
overrides anything derived from PR_URL.

Note (telemetry): Append every shell command to {RUN_FOLDER}/commands.log per the §13 JSONL schema (schema_version, timestamp
with timezone, cwd, command, exit_code, artifacts[], redactions[]).

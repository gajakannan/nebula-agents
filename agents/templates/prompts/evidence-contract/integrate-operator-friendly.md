This prompt runs the integrate action (`agents/actions/integrate.md`): merge ONE contributor branch into the integration branch with semantic KG/tracker merging, unconditional regeneration, validation, and an append-only integration evidence run — bracketed by two maintainer gates.

REQUIRED INPUTS (you must set):
- `SOURCE={branch or PR number}`
- `INTEGRATION_BRANCH={branch}` — never `main`; current train: the maintainer-designated branch (e.g. `chore/merge-PRs`); steady state: create `integrate/<date>-train`
- ONE OF: `REVIEW_VERDICT_REF={feature-review run reference}` or `WAIVER="{rationale}"` (maintainer-authorized, this run only)

OPTIONAL INPUTS (defaults apply when omitted):
- `PRODUCT_ROOT=` — default: sister-repo per `agents/docs/AGENT-USE.md` → Session Setup
- `MODE={live | dry-run}` — default `live`; `dry-run` prepares nothing for push and labels simulated inputs

AUTO-RESOLVED:
- `RUN_ID` — `integrate-$(date -u +%Y%m%d-%H%M%S)`
- `RUN_FOLDER` — `{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{RUN_ID}`
- `MERGE_BASE` — `git merge-base {INTEGRATION_BRANCH} {SOURCE}`

Echo the resolved absolute `{PRODUCT_ROOT}` on your first turn. Load context in this order: `agents/ROUTER.md` → `agents/agent-map.yaml` → `agents/integrator/SKILL.md` → `agents/actions/integrate.md` → `agents/templates/integration-evidence-template.md`.

Work in a dedicated worktree: `git worktree add <tmp> {INTEGRATION_BRANCH}`. Never operate on the operator's checkout. Never push. Never merge to `main`.

Follow gates I0–I6 from `integrate.md` exactly:
- `I0` — verify `REVIEW_VERDICT_REF` or record the waiver in `gate-decisions.md`; missing both → halt with the evidence run recording the missing gate
- `I1` — branch verification on {SOURCE}'s own content; stale generated files → BOUNCE (exact regeneration commands in the report); do not fix their branch
- `I2` — `git merge --no-commit {SOURCE}`; then `python3 {PRODUCT_ROOT}/scripts/kg/merge3.py <file> --base {MERGE_BASE} --ours {INTEGRATION_BRANCH} --theirs {SOURCE} --json {RUN_FOLDER}/artifacts/merge3-<name>.json` for each both-sides-changed curated KG file and for `REGISTRY.md`/`ROADMAP.md`; any typed conflict → halt, report routed to the owning role
- `I3` — regenerate unconditionally: `validate.py --regenerate-symbols --check-symbols --regenerate-decisions --check-decisions`, then `--write-coverage-report`, then `generate-story-index.py`
- `I4` — `validate.py` + `--check-drift` + `validate-trackers.py --skip-feature-evidence`, all exit 0
- `I5` — complete the evidence run (`integration-report.json` per template), commit the prepared merge in the worktree, record its SHA
- `I6` — STOP. The maintainer exercises the feature on the prepared worktree and records pass/fail in `gate-decisions.md` + `integration-report.json`. Pass → maintainer pushes. Fail → treated as a bounce.

Don'ts:
- Don't edit ANY source-authored file (feature docs, architecture, schemas, code, Phase-B `kg-source/**`) — needing to is a semantic collision: abort, self-report in the evidence run, route to the owner
- Don't trust a textually clean git merge of a generated file — regenerate regardless
- Don't resolve code conflicts — surface them and halt
- Don't edit a prior evidence run — re-runs are new runs with `supersedes_run` set
- Don't push, don't touch `main`, don't run two integrations concurrently

Append every shell command to `commands.log` per the §13 JSONL schema.

Stop immediately if: gate I0 cannot be satisfied, the bounce check fails, any typed conflict or validation failure occurs, a source-file edit becomes necessary, or `INSUFFICIENT_CONTEXT`.

Close the run: confirm the base files + `integration-report.json` + per-file merge reports exist and are non-empty; the run outcome in `action-context.md` matches `integration-report.json`.

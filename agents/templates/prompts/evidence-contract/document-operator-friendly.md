<!-- GENERATED from agents/actions/spec/document.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action document -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


This prompt encodes the **Feature Evidence Contract** (scope `base-run-only`, policy `2026-07-11`).

Before setup, discovery, or resume, bind the product root once. NEBULA_PRODUCT_ROOT is the canonical input in both a pasted prompt and the shell environment. An explicit operator value wins over the environment; stop for clarification if explicit selections disagree. Use only NEBULA_PRODUCT_ROOT for the input and all root placeholders. A value supplied in this prompt is valid even when the shell environment is empty; pass it explicitly to the resolver. Resolve relative paths (including ../) against the session's starting directory, normally nebula-agents, before changing directories: run `python3 agents/scripts/_product_root.py --product-root "<supplied path>"` from that directory, or omit the flag to read the environment. Replace the input value with the returned absolute NEBULA_PRODUCT_ROOT and echo it with its source. Pass that same absolute path as --product-root to every product-aware script, including init-run.py and resume-brief.py, and include it in every agent handoff. Do not rely on an export persisting between shell calls. On resume, reuse the recorded absolute root and reject a conflicting selection. If no value is supplied, ask for the product path; never infer it from a feature ID, scan siblings to choose a product, or default to a particular repository.

Required inputs:
- `DOC_SCOPE` — one of `api` | `readme` | `runbook` | `developer-guide` | `release-notes` | `mixed`
- `TARGETS` (format `[path, ...] destination doc files`)

Optional inputs (defaults apply when omitted):
- `SOURCE_CODE`
- `FEATURE_REF`
- `NEBULA_PRODUCT_ROOT` — default `environment; required if unset`

Auto-resolved (do not set; SESSION_SETUP / the orchestrator compute these):
- `DOC_RUN_FOLDER` — {NEBULA_PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{DOC_RUN_ID}
- `FEATURE_REF_PATH` — {NEBULA_PRODUCT_ROOT}/planning-mds/features/{FEATURE_REF}-{FEATURE_REF_SLUG} (only when FEATURE_REF is set)
- `FEATURE_REF_SLUG` — kebab-case slug for {FEATURE_REF} from REGISTRY.md (only when FEATURE_REF is set)

Generate `DOC_RUN_ID` once per run — not per session — in the contract format `YYYY-MM-DD-[a-z0-9]{8}` using `python3 -c import secrets; print(secrets.token_hex(4))`. Do not use: uuid4.

Resuming an in-flight run in a new session: do NOT generate a new `DOC_RUN_ID` and do NOT re-create the run. Run `python3 agents/scripts/resume-brief.py --product-root {NEBULA_PRODUCT_ROOT} --run-id <DOC_RUN_ID>` first — it reports position, next gate, recorded decisions, current story, and scope in one read, so the session does not re-derive them. `init-run.py --resume` reuses the existing run folder.

Session setup (first session of the run only): create the run under `planning-mds/operations/evidence/`, initialize `evidence-manifest.json` (status `draft`) with the active contract version stamped, create the base run files (README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log) and artifact subdirs (coverage, diffs, test-results, security, screenshots). Run `agents/scripts/init-run.py --product-root {NEBULA_PRODUCT_ROOT}` to perform this.

Load context in this order, then navigate rather than eager-load:
First resolve NEBULA_PRODUCT_ROOT explicitly. Run `python3 agents/scripts/project_context.py --product-root {NEBULA_PRODUCT_ROOT} --action document` and read the returned product instructions before action work, including after resume. A context error blocks the action; an absent project manifest preserves the existing context procedure.
1. `agents/ROUTER.md`
2. `agents/agent-map.yaml`
3. `agents/docs/AGENT-USE.md`
4. `agents/docs/PROJECT-EXTENSIONS.md`
5. `agents/actions/document.md`
6. `agents/technical-writer/SKILL.md`
7. `SOURCE_CODE paths (read-only)`
8. `for FEATURE_REF (read-only context): {FEATURE_REF_PATH}/README.md, PRD.md, feature-assembly-plan.md`

Gates (run each stage through `agents/scripts/run-gate.py`, in order):
- **D0 — Scope lock** (role: technical-writer; artifacts: gate-decisions.md)
    - judgment: Confirm DOC_SCOPE, TARGETS, and SOURCE_CODE and record the row in gate-decisions.md.
- **D1 — Draft** (role: technical-writer; artifacts: none)
    - judgment: Produce or update the TARGETS from the source code (and any FEATURE_REF context). Format and headings
depend on the doc type. Runtime verifications (API examples, CLI commands, health checks) run inside
runtime containers when feasible, with artifact paths recorded — never run compile/lint/runtime commands
outside runtime containers.
- **D2 — Self-review gate** (role: technical-writer; artifacts: none)
    - judgment: The author validates documentation quality and accuracy against the source code. Stop if self-review finds
factual errors that cannot be resolved against the source, or a runtime verification fails such that the
doc would mislead users.
- **D3 — Approval gate** (role: technical-writer; artifacts: none)
    - MANUAL checkpoint `doc-approval`: The user reviews the documentation and approves or requests changes. (requires: the TARGETS drafted at D1; produces: doc approval recorded in gate-decisions.md)
    - run `python3 agents/scripts/validate_templates.py` (cwd: framework, timeout: 300s)
    - judgment: After approval, run validate_templates.py (exit 0). Run `{NEBULA_PRODUCT_ROOT}/scripts/kg/validate.py --check-drift`
ONLY when KG references changed. DO NOT call validate-feature-evidence.py — there is no feature evidence
package for this run.

Severity gate profile: `none` (compute allowed outcomes with `agents/scripts/gate_policy.py`; coverage floor is 80%).

Ownership (strict):
- **technical-writer** owns: every produced doc file (the TARGETS)

Forbidden:
- Generate DOC_RUN_ID with uuid4.
- Write into any feature evidence package (####-*/).
- Cite documentation as a substitute for required feature evidence reports (e.g. test-execution-report.md, code-review-report.md).
- Execute compile/lint/runtime commands outside runtime containers.
- Skip the SELF-REVIEW or APPROVAL gates.

Stop conditions:
- Self-review identifies factual errors that cannot be resolved against source code.
- Runtime verification fails and the doc would mislead users.
- The user refuses the approval gate.

Conflict resolution:
- doc disagrees with code -> code wins; update the doc, not the code.
- doc disagrees with an API contract -> the contract wins; route to plan/architect if the contract itself is wrong.
- doc cites a runtime example that does not work -> fix or remove the example; do not ship docs that mislead.

Note (evidence_outputs): In {DOC_RUN_FOLDER}: README.md (Run Summary = "Documentation run", Status, Evidence Index pointing to
TARGETS, Validation Summary, Open Follow-ups); action-context.md (Scope Boundaries = "Documentation only; not
feature evidence", Lifecycle Stage = "Document"); artifact-trace.md (which TARGETS were created/updated +
SOURCE_CODE pointers); gate-decisions.md (D0..D3); commands.log; lifecycle-gates.log. The documentation files
themselves land at the TARGETS.

Note (session_setup): Echo the resolved absolute {NEBULA_PRODUCT_ROOT} on the first turn. Mint DOC_RUN_ID once in contract format (an ISO
YYYY-MM-DD date plus a secrets.token_hex(4) suffix); never uuid4. Create {DOC_RUN_FOLDER} and initialize the
six §8 base run files.

Note (telemetry): Append every shell command to {DOC_RUN_FOLDER}/commands.log per the §13 JSONL schema (schema_version,
timestamp with timezone, cwd, command, exit_code, artifacts[], redactions[]).

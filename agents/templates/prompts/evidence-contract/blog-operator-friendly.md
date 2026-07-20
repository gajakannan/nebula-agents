<!-- GENERATED from agents/actions/spec/blog.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action blog -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


This prompt encodes the **Feature Evidence Contract** (scope `base-run-only`, policy `2026-07-11`).

Required inputs:
- `POST_TYPE`
- `TARGET_PATH` (format `path to where the post will be written`)

Optional inputs (defaults apply when omitted):
- `AMPLIFICATION` — default `none`
- `FEATURE_REF`
- `PRODUCT_ROOT` — default `sister-repo`

Auto-resolved (do not set; SESSION_SETUP / the orchestrator compute these):
- `BLOG_RUN_FOLDER` — {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{BLOG_RUN_ID}
- `FEATURE_REF_PATH` — {PRODUCT_ROOT}/planning-mds/features/{FEATURE_REF}-{FEATURE_REF_SLUG} (only when FEATURE_REF is set)
- `FEATURE_REF_SLUG` — kebab-case slug for {FEATURE_REF} from REGISTRY.md (only when FEATURE_REF is set)

Generate `BLOG_RUN_ID` once at session start in the contract format `YYYY-MM-DD-[a-z0-9]{8}` using `python3 -c import secrets; print(secrets.token_hex(4))`. Do not use: uuid4.

Session setup: create the run under `planning-mds/operations/evidence/`, initialize `evidence-manifest.json` (status `draft`) with the active contract version stamped, create the base run files (README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log) and artifact subdirs (coverage, diffs, test-results, security, screenshots). Run `agents/scripts/init-run.py` to perform this.

Load context in this order, then navigate rather than eager-load:
1. `agents/ROUTER.md`
2. `agents/agent-map.yaml`
3. `agents/docs/AGENT-USE.md`
4. `agents/actions/blog.md`
5. `agents/blogger/SKILL.md`
6. `for FEATURE_REF (read-only context): {FEATURE_REF_PATH}/README.md, PRD.md, feature-assembly-plan.md; if archived, that feature's pm-closeout.md`

Gates (run each stage through `agents/scripts/run-gate.py`, in order):
- **B0 — Discovery** (role: blogger; artifacts: none)
    - judgment: Conversational: the agent asks, recommends, and aligns with the user on subject, angle, and audience
before any brief.
- **B1 — Editorial brief** (role: blogger; artifacts: none)
    - MANUAL checkpoint `editorial-brief`: The user approves the editorial brief before any drafting begins. (requires: subject context and the proposed angle/audience from B0; produces: approved editorial brief (gate-decisions.md))
    - judgment: Do not draft before this brief is approved.
- **B2 — Draft** (role: blogger; artifacts: none)
    - judgment: Write the primary post into TARGET_PATH.
- **B3 — Self-review gate** (role: blogger; artifacts: none)
    - judgment: Accuracy and quality check. When FEATURE_REF is set, cross-check feature status, dates, and decisions
against REGISTRY.md and the feature's pm-closeout.md — never misrepresent them. Stop if self-review finds
factual errors that cannot be resolved against the source artifacts.
- **B4 — Editorial gate** (role: blogger; artifacts: none)
    - MANUAL checkpoint `editorial-gate`: The user reviews and approves the post. Do not publish or amplify before this gate passes. (requires: the drafted post at TARGET_PATH; produces: editorial approval (gate-decisions.md))
- **B5 — Amplification (optional Phase 2)** (role: blogger; artifacts: none)
    - judgment: Only when AMPLIFICATION=phase-2: produce the channel derivatives. Skip this gate when AMPLIFICATION=none
(gate-decisions.md then records B0..B4).

Severity gate profile: `none` (compute allowed outcomes with `agents/scripts/gate_policy.py`; coverage floor is 80%).

Ownership (strict):
- **blogger** owns: the post and its channel derivatives (the user owns approval)

Forbidden:
- Generate BLOG_RUN_ID with uuid4.
- Write into any feature evidence package (####-*/).
- Cite a blog post as evidence for a completed terminal feature.
- Draft before the EDITORIAL BRIEF gate (B1).
- Publish or amplify before the EDITORIAL GATE (B4).
- Misrepresent feature status, dates, or decisions (cross-check REGISTRY.md and pm-closeout.md when FEATURE_REF is set).

Stop conditions:
- The user refuses the EDITORIAL BRIEF.
- Self-review identifies factual errors that cannot be resolved against source artifacts.
- The user refuses the EDITORIAL GATE.

Conflict resolution:
- a blog assertion disagrees with REGISTRY.md/STATUS.md/pm-closeout.md -> the registry/closeout wins; fix the post.
- a blog assertion disagrees with code -> code wins; do not publish content that misleads.

Note (evidence_outputs): In {BLOG_RUN_FOLDER}: README.md (Run Summary = "Blog run", Status, Evidence Index pointing to TARGET_PATH
and any amplification artifacts, Validation Summary, Open Follow-ups); action-context.md (Scope Boundaries =
"Editorial content; not feature evidence", Lifecycle Stage = "Blog"); artifact-trace.md (TARGET_PATH + any
channel derivative paths); gate-decisions.md (B0..B5, or B0..B4 when AMPLIFICATION=none); commands.log. The
post and its derivatives land at TARGET_PATH and the amplification destinations.

Note (exit_validation): No validators are required — blog content is not gated by feature evidence validators. Confirm
gate-decisions.md records all B0..B5 (or B0..B4 when AMPLIFICATION=none).

Note (session_setup): Echo the resolved absolute {PRODUCT_ROOT} on the first turn. Mint BLOG_RUN_ID once in contract format (an
ISO YYYY-MM-DD date plus a secrets.token_hex(4) suffix); never uuid4. Create {BLOG_RUN_FOLDER} and
initialize the six §8 base run files.

Note (telemetry): Append every shell command to {BLOG_RUN_FOLDER}/commands.log per the §13 JSONL schema (schema_version,
timestamp with timezone, cwd, command, exit_code, artifacts[], redactions[]).

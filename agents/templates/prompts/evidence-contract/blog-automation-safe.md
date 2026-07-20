<!-- GENERATED from agents/actions/spec/blog.yaml + _contract.yaml — do not edit; run: python3 agents/scripts/render-prompts.py --action blog -->
<!-- policy_version: 2026-07-11 | renderer_version: 1 -->


CONTRACT: Feature Evidence Contract | SCOPE: base-run-only | POLICY: 2026-07-11

REQUIRED_INPUTS:
- POST_TYPE
- TARGET_PATH [path to where the post will be written]
OPTIONAL_INPUTS:
- AMPLIFICATION =default:none
- FEATURE_REF
- PRODUCT_ROOT =default:sister-repo
AUTO_RESOLVED:
- BLOG_RUN_FOLDER = {PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{BLOG_RUN_ID}
- FEATURE_REF_PATH = {PRODUCT_ROOT}/planning-mds/features/{FEATURE_REF}-{FEATURE_REF_SLUG} (only when FEATURE_REF is set)
- FEATURE_REF_SLUG = kebab-case slug for {FEATURE_REF} from REGISTRY.md (only when FEATURE_REF is set)

RUN_ID: var=BLOG_RUN_ID format=YYYY-MM-DD-[a-z0-9]{8} method=python3 -c import secrets; print(secrets.token_hex(4)) forbidden=uuid4
SESSION_SETUP: init-run.py -> planning-mds/operations/evidence/... manifest=draft base_files=[README.md, action-context.md, artifact-trace.md, gate-decisions.md, commands.log, lifecycle-gates.log] artifacts=[coverage, diffs, test-results, security, screenshots]
CONTEXT: agents/ROUTER.md -> agents/agent-map.yaml -> agents/docs/AGENT-USE.md -> agents/actions/blog.md -> agents/blogger/SKILL.md -> for FEATURE_REF (read-only context): {FEATURE_REF_PATH}/README.md, PRD.md, feature-assembly-plan.md; if archived, that feature's pm-closeout.md

GATES:
- B0 role=blogger artifacts=[]
- B1 role=blogger artifacts=[]
    - MANUAL checkpoint `editorial-brief`: The user approves the editorial brief before any drafting begins. (requires: subject context and the proposed angle/audience from B0; produces: approved editorial brief (gate-decisions.md))
- B2 role=blogger artifacts=[]
- B3 role=blogger artifacts=[]
- B4 role=blogger artifacts=[]
    - MANUAL checkpoint `editorial-gate`: The user reviews and approves the post. Do not publish or amplify before this gate passes. (requires: the drafted post at TARGET_PATH; produces: editorial approval (gate-decisions.md))
- B5 role=blogger artifacts=[]

SEVERITY_GATE: profile=none tool=gate_policy.py coverage_min_pct=80
OWNERSHIP:
- blogger: the post and its channel derivatives (the user owns approval)
FORBIDDEN:
- Generate BLOG_RUN_ID with uuid4.
- Write into any feature evidence package (####-*/).
- Cite a blog post as evidence for a completed terminal feature.
- Draft before the EDITORIAL BRIEF gate (B1).
- Publish or amplify before the EDITORIAL GATE (B4).
- Misrepresent feature status, dates, or decisions (cross-check REGISTRY.md and pm-closeout.md when FEATURE_REF is set).
STOP_CONDITIONS:
- The user refuses the EDITORIAL BRIEF.
- Self-review identifies factual errors that cannot be resolved against source artifacts.
- The user refuses the EDITORIAL GATE.
CONFLICT_RESOLUTION:
- a blog assertion disagrees with REGISTRY.md/STATUS.md/pm-closeout.md -> the registry/closeout wins; fix the post.
- a blog assertion disagrees with code -> code wins; do not publish content that misleads.
NOTE[evidence_outputs]: In {BLOG_RUN_FOLDER}: README.md (Run Summary = "Blog run", Status, Evidence Index pointing to TARGET_PATH
and any amplification artifacts, Validation Summary, Open Follow-ups); action-context.md (Scope Boundaries =
"Editorial content; not feature evidence", Lifecycle Stage = "Blog"); artifact-trace.md (TARGET_PATH + any
channel derivative paths); gate-decisions.md (B0..B5, or B0..B4 when AMPLIFICATION=none); commands.log. The
post and its derivatives land at TARGET_PATH and the amplification destinations.
NOTE[exit_validation]: No validators are required — blog content is not gated by feature evidence validators. Confirm
gate-decisions.md records all B0..B5 (or B0..B4 when AMPLIFICATION=none).
NOTE[session_setup]: Echo the resolved absolute {PRODUCT_ROOT} on the first turn. Mint BLOG_RUN_ID once in contract format (an
ISO YYYY-MM-DD date plus a secrets.token_hex(4) suffix); never uuid4. Create {BLOG_RUN_FOLDER} and
initialize the six §8 base run files.
NOTE[telemetry]: Append every shell command to {BLOG_RUN_FOLDER}/commands.log per the §13 JSONL schema (schema_version,
timestamp with timezone, cwd, command, exit_code, artifacts[], redactions[]).

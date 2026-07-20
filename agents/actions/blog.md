# Action: Blog

## User Intent

Write development logs, technical articles, blog posts, and channel amplification content about project progress, decisions, lessons learned, and interesting technical challenges. This action is **conversational** — the agent asks questions, makes recommendations, and reaches alignment with the user before writing anything.

## Agent Flow

```
B0  Discovery         (conversational — ask, recommend, align)
  ↓
B1  Editorial brief   (user approves before drafting)
  ↓
B2  Draft             (write primary post into TARGET_PATH)
  ↓
B3  Self-review gate  (accuracy and quality)
  ↓
B4  Editorial gate    (user reviews and approves)
  ↓
B5  Amplification     (optional Phase 2 — channel derivatives)
Blog Complete
```

**Flow Type:** Single agent, discovery-first, with two editorial gates (B1, B4).

---

## Contract (generated — the spec is the source of truth)

The fixed procedure for this action — the `B0`–`B5` gates, inputs (`POST_TYPE`, `TARGET_PATH`,
`AMPLIFICATION`, `FEATURE_REF`), forbidden actions, stop conditions, and conflict resolution — is declared
once in [`agents/actions/spec/blog.yaml`](spec/blog.yaml) and compiled into the operator/automation prompt
pair at `agents/templates/prompts/evidence-contract/blog-operator-friendly.md` and `blog-automation-safe.md`.
Regenerate with `python3 agents/scripts/render-prompts.py`; the `prompt_drift` lifecycle gate fails if the
committed prompts drift from the spec. **Edit the spec, not this doc or the generated prompts.**

- **Scope** — `base-run-only`, and **outside the feature evidence contract**: editorial content is never
  evidence for a completed feature. `POST_TYPE ∈ {devlog | technical-article | release-post | retrospective |
  other}`; the run writes a base run package under
  `{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/{BLOG_RUN_ID}/` and the post at `TARGET_PATH`.
- **Gates** — B1 and B4 are user checkpoints: never draft before B1, never publish/amplify before B4. No
  validators are required. Never misrepresent feature status/dates/decisions — cross-check `REGISTRY.md` and
  the feature's `pm-closeout.md` when `FEATURE_REF` is set.

Drive the gates with `python3 agents/scripts/run-gate.py --action blog --stage <B0..B5> ...` (`--list` prints
the ordered runbook; it pauses at the B1/B4 editorial checkpoints).

---

## Runtime Execution Boundary

- Runs entirely in the builder runtime. No application containers required.
- Code examples must be verified against the actual codebase — the Blogger reads code but does not execute it.

## Required Reads Before Starting

1. `agents/blogger/SKILL.md` — agent capabilities, two-phase model, quality gates
2. `../nebula-blog/publication-profile.md` — voice, domain, audience, channel config (optional product override)
3. `../nebula-blog/SERIES-PLAN.md` — series roadmap, published + planned posts
4. `agents/blogger/references/blogging-best-practices.md` — craft reference

---

## Blogger craft (not encoded in the spec)

The spec owns the gate structure; the craft below is the Blogger's method (keep aligned with
`agents/blogger/SKILL.md` and `publication-profile.md`).

### B0 Discovery — the most important step

Ask questions conversationally (not a numbered list, not all at once); start with the most open question and follow the thread; make recommendations and push back when something doesn't feel right. The goal is a story worth telling, not just a topic. Core threads to work through:

- What did you build/decide/learn/observe that's worth writing about? What's the one takeaway for the reader?
- Where's the moment of surprise, mistake, or shaping constraint? That's usually the real hook.
- Does it fit a series in `SERIES-PLAN.md`, and where in that arc? What post type fits (devlog / deep dive / tutorial / case study / retrospective)?
- Is there an opening hook? What source material exists (commits, ADRs, feature artifacts, benchmarks, tests)? Which amplification channels after publishing?

Offer interpretations back ("the mistake you mentioned feels like the real hook, not the feature itself — what do you think?"). When done, summarize the angle + series placement + hook in 2–3 sentences and get explicit confirmation before B1.

### B1 Editorial brief

Present a brief and get explicit approval before drafting. Fields: Topic; The story (one sentence — the real angle); Hook; Post type; Series (name + number, or standalone); Target audience (specific); Estimated length; Source material; 3–5 Key points; Amplification channels; Output file `../nebula-blog/posts/YYYY-MM-DD-slug.md`.

### B2 Draft — voice

First-person builder's voice; the agreed hook pattern; emoji anchors on section headers (sparingly); insurance-domain grounding (name the application explicitly); series continuity (open with a recap if part of a series, close with a specific preview). Reference source material directly (repo-relative paths, real snippets, actual decision records) — no invented metrics.

### B3 Self-review checklist

- **Technical accuracy:** every assertion traces to source material; code snippets match the codebase; architecture descriptions consistent with planning artifacts; no secrets/credentials/internal hostnames/customer data.
- **Voice & craft:** hook matches the agreed pattern (not generic background); first-person throughout; insurance application named; register = experienced practitioner (not novice, not authority); series recap + forward preview.
- **Readability:** scannable headings; excerpted + annotated code (not raw dumps); a concrete takeaway (not a vague close); length within the post-type target.

### B5 Amplification — channel rules

Only when `AMPLIFICATION=phase-2`, and only after the primary post is approved. Translate for each channel (don't copy the primary), save to `../nebula-blog/amplification/YYYY-MM-DD-slug-[channel].md`, and honor the per-channel rule:

- **LinkedIn** — link in the first comment, not the post body
- **X/Twitter** — Substack link in a reply to the final tweet
- **Bluesky** — link can go directly in the final post
- **Reddit** — lead with value, not "I wrote a post"
- **dev.to** — set the canonical URL to the Substack post

After completion, remind the user to update `../nebula-blog/SERIES-PLAN.md` with the post status and Substack URL.

---

## Anti-Patterns to Avoid

- Jumping to drafting before discovery is complete, or producing a brief the user didn't approve.
- A post that could belong to any blog — no insurance grounding, no personal voice.
- Amplification that copies the primary instead of translating for the channel.
- Marking a post complete without flagging the `SERIES-PLAN.md` update.

## Related Files

- `agents/blogger/SKILL.md` · `../nebula-blog/publication-profile.md` · `agents/blogger/references/blogging-best-practices.md` · `../nebula-blog/SERIES-PLAN.md`

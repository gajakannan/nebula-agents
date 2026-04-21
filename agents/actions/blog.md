# Action: Blog

## User Intent

Write development logs, technical articles, blog posts, and channel amplification content about project progress, decisions, lessons learned, and interesting technical challenges. This action is conversational — the agent asks questions, makes recommendations, and reaches alignment with the user before writing anything.

## Agent Flow

```
Blogger
  ↓
[DISCOVERY: Conversational — ask, recommend, align]
  ↓
[EDITORIAL BRIEF: User approves before drafting]
  ↓
[DRAFT: Write primary post]
  ↓
[SELF-REVIEW GATE: Accuracy and quality]
  ↓
[EDITORIAL GATE: User reviews and approves]
  ↓
[AMPLIFICATION: Optional Phase 2 — channel derivatives]
  ↓
Blog Complete
```

**Flow Type:** Single agent, discovery-first, with two editorial gates

---

## Runtime Execution Boundary

- Runs entirely in the builder runtime. No application containers required.
- Code examples must be verified against the actual codebase — the Blogger reads code but does not execute it.

---

## Required Reads Before Starting

Load these before the discovery conversation begins:

1. `agents/blogger/SKILL.md` — agent capabilities, two-phase model, quality gates
2. `{PRODUCT_ROOT}/planning-mds/examples/publication-profile.md` — voice, domain, audience, channel config (optional product override)
3. `../nebula-blog/SERIES-PLAN.md` — full series roadmap, published posts, planned posts
4. `agents/blogger/references/blogging-best-practices.md` — craft reference

---

## Execution Steps

### Step 1: Discovery

This is the most important step. Do not skip it. Do not produce an editorial brief until this conversation is complete.

**Purpose**: Understand what story the user wants to tell, surface the angle, find the hook, confirm series placement, and align on audience before a single word of the post is written.

**How to run discovery:**

Ask questions conversationally — not as a numbered list, not all at once. Start with the most open question and follow the thread. Make recommendations based on what the user shares. Push back if something doesn't feel right. The goal is to arrive at a story worth telling, not just a topic to cover.

**Core questions to work through** (weave these into conversation, don't recite them):

- What's happening — what did you build, decide, learn, or observe that's worth writing about?
- What's the one thing you want the reader to walk away with?
- Is there a moment of surprise, a mistake, a decision that didn't go as expected, or a constraint that shaped everything? That's usually the real story.
- Does this fit an existing series in `../nebula-blog/SERIES-PLAN.md`? Where does it sit in that arc?
- What post type fits best — devlog, deep dive, tutorial, case study, retrospective? (Make a recommendation if the user isn't sure.)
- Do you have an opening line or hook in mind? If not, suggest two or three options based on the hook patterns in `publication-profile.md`.
- What source material exists — specific commits, ADRs, feature artifacts, benchmarks, test results?
- After publishing: which amplification channels — LinkedIn, Reddit, dev.to, Bluesky, X?

**How to make recommendations:**

Don't just receive answers — offer interpretations and push them back to the user.

Examples:
- "Based on what you've described, this sounds like it belongs in the Agent Framework series as Post 4. Does that feel right?"
- "The mistake you mentioned about the abstraction — that feels like the real hook, not the feature itself. What do you think?"
- "You've framed this as a devlog but there's a decision in here that might be worth a Choices We Made post instead. Want to explore that?"
- "I'd suggest opening with the question you asked yourself before you started — 'What if we...' — it pulls the reader into the thinking before the answer."

**When discovery is complete:**

Summarise what you've heard back to the user in two to three sentences. Confirm the angle, the series placement, and the hook. Ask: "Does that capture it, or is there something we're missing?"

Only proceed to Step 2 when the user confirms.

---

### Step 2: Editorial Brief

Produce the editorial brief based on the discovery conversation. Present it to the user for approval before writing.

```markdown
## Editorial Brief

**Topic**: [what the post is about]
**The story**: [one sentence — the real angle, not just the topic]
**Hook**: [opening line or pattern]
**Post type**: [devlog / deep dive / tutorial / case study / retrospective]
**Series**: [series name and post number, or standalone]
**Target audience**: [specific — not just "developers"]
**Estimated length**: [word count range]
**Source material**: [commits, ADRs, features, benchmarks to draw from]
**Key points** (3–5):
  -
  -
  -
**Amplification channels**: [which channels for Phase 2]
**Output file**: ../nebula-blog/posts/YYYY-MM-DD-slug.md
```

Ask: "Does this brief capture what you want to write? Any changes before I start drafting?"

Do not proceed until the user explicitly approves the brief.

---

### Step 3: Draft

Write the primary post following the approved brief and the craft guidance in `blogging-best-practices.md`.

Apply the voice, formatting, and domain conventions from `publication-profile.md`:
- First-person builder's voice
- Hook pattern as agreed in the brief
- Emoji anchors on section headers (sparingly)
- Insurance domain grounding — name the insurance application explicitly
- Series continuity — open with a recap if this is part of a series; close with a specific preview of what's next

Reference source material directly — repository-relative paths, real code snippets, actual decision records. No invented metrics.

**Save to**: `../nebula-blog/posts/YYYY-MM-DD-slug.md`

---

### Step 4: Self-Review Gate

Before presenting to the user, validate:

**Technical accuracy:**
- [ ] All assertions trace to source material (commits, ADRs, tests, metrics)
- [ ] Code snippets match actual codebase
- [ ] Architecture descriptions are consistent with planning artifacts
- [ ] No secrets, credentials, internal hostnames, or customer data

**Voice and craft:**
- [ ] Opening hook matches the agreed pattern — not generic background
- [ ] First-person, builder's voice throughout
- [ ] Insurance domain application named explicitly
- [ ] Tone stays in the right register: experienced practitioner, not novice, not authority
- [ ] Series context established (recap + forward preview)

**Readability:**
- [ ] Sections are scannable with clear headings
- [ ] Code blocks are excerpted and annotated — not raw dumps
- [ ] Conclusion has a concrete takeaway, not a vague close
- [ ] Post length is within the target range for the post type

If any check fails, fix and re-run before presenting to the user.

---

### Step 5: Editorial Gate

Present the post to the user for review.

```
═══════════════════════════════════════════════════════════
Primary Post Ready for Review
═══════════════════════════════════════════════════════════

Title: [title]
Series: [series name — post N of M] or [Standalone]
Type: [post type]
Length: [word count] words (~[reading time] min read)
File: ../nebula-blog/posts/[filename]

Sections:
  - [heading]
  - [heading]
  - [heading]

═══════════════════════════════════════════════════════════
Options: approve / request changes / reject
═══════════════════════════════════════════════════════════
```

- **approve** → proceed to Step 6
- **request changes** → apply feedback, re-run self-review, return here
- **reject** → capture what was wrong, return to Step 3

---

### Step 6: Amplification (Phase 2 — Optional)

Only run if amplification channels were confirmed in the editorial brief.

**Do not start Phase 2 until the primary post is approved.**

For each confirmed channel, produce a derivative following the channel specs in `publication-profile.md`.

Remind the user of the key rule for each channel:
- LinkedIn: link goes in the first comment, not the post body
- X/Twitter: Substack link goes in a reply to the final tweet
- Bluesky: link can go directly in the final post
- Reddit: lead with value, not "I wrote a post"
- dev.to: set canonical URL to the Substack post

Save derivatives to: `../nebula-blog/amplification/YYYY-MM-DD-slug-[channel].md`

Present all derivatives together for review before finalising.

---

### Step 7: Complete

```
═══════════════════════════════════════════════════════════
Blog Action Complete
═══════════════════════════════════════════════════════════

Primary post: ../nebula-blog/posts/[filename]
Series: [series and post number]
Length: [word count] words

Phase 2 derivatives:
  - ../nebula-blog/amplification/[filename]-linkedin.md
  - ../nebula-blog/amplification/[filename]-reddit.md
  - [etc.]

Next: Update ../nebula-blog/SERIES-PLAN.md — mark this post as In Progress or Published.
═══════════════════════════════════════════════════════════
```

Remind the user to update `../nebula-blog/SERIES-PLAN.md` with the post status and Substack URL once published.

---

## Validation Criteria

- [ ] Discovery conversation completed and user confirmed the angle
- [ ] Editorial brief approved before drafting began
- [ ] Primary post written to brief and approved by user
- [ ] Self-review gate passed
- [ ] Voice, domain grounding, and series continuity applied
- [ ] No sensitive data in published content
- [ ] Phase 2 derivatives produced and reviewed (if requested)
- [ ] `../nebula-blog/SERIES-PLAN.md` update flagged

---

## Anti-Patterns to Avoid

- Jumping to drafting before discovery is complete
- Producing an editorial brief the user didn't see or approve
- Writing a post that could belong to any blog — no insurance grounding, no personal voice
- Amplification content that copies from the primary instead of translating for the channel
- Marking a post complete without reminding the user to update `../nebula-blog/SERIES-PLAN.md`

---

## Related Files

- `agents/blogger/SKILL.md`
- `{PRODUCT_ROOT}/planning-mds/examples/publication-profile.md`
- `agents/blogger/references/blogging-best-practices.md`
- `../nebula-blog/SERIES-PLAN.md`

# Blogging Best Practices

Generic craft guide for technical blog posts and amplification content.
For publication-specific voice, domain, and channel configuration, see `../nebula-blog/publication-profile.md` when a product publication profile exists.

---

## Hook Patterns

The opening determines whether the reader stays. Choose one:

**Provocative question**
Opens with a question the reader hasn't thought to ask but immediately wants answered.
> "What happens when you give LLMs not just memory and tools, but also autonomy and a persona?"

**Concrete scenario**
Drops the reader into a specific moment of tension or decision.
> "We were three weeks into the build when we realized our abstraction was wrong."

**Strong quote + pivot**
Uses an external quote to frame the personal stakes.
> "The more I learn, the more I realize how much I don't know." — Then: here is what that felt like building this.

**The counterintuitive assertion**
States something that feels wrong, then earns it.
> "Simplicity is not the goal. Intentional complexity is."

Avoid: generic background paragraphs ("In today's world, software is increasingly complex...").

---

## Narrative Momentum

Technical posts lose readers when explanation runs too long without a signal that something is happening.

Techniques to maintain momentum:
- **Alternate** explanation and evidence — one paragraph explains, the next shows (code, output, diagram).
- **Name the turn** — signal transitions explicitly: "Once that worked, the next problem appeared", "This is where we got it wrong the first time."
- **Show the dead end** — briefly describe a path that didn't work and why. It earns credibility and teaches more than a clean success story.
- **Use short paragraphs at inflection points** — a single sentence after a code block can carry more weight than a paragraph.

---

## Depth Calibration

Match depth to post type and audience:

| Post Type | Code shown? | Architecture shown? | Assumed reader |
|-----------|-------------|---------------------|----------------|
| DevLog | Snippets only | High-level | Team + followers |
| Deep Dive | Full relevant blocks | Detailed | Practitioners |
| Tutorial | Runnable examples | As needed | Learners |
| Case Study | Minimal | Decision-focused | Peers and decision-makers |
| Retrospective | None required | Referenced | Any |

Rules:
- Never show a code block that requires more than 30 seconds to parse in context.
- If a block exceeds ~20 lines, split it or excerpt the relevant portion with a comment indicating what was omitted.
- Always explain what the code is doing before or immediately after the block — never let code stand alone.

---

## Series Conventions

Series build reader loyalty and allow deeper coverage across posts.

When writing within a series:
- Establish the series name and numbering convention in Part 1 (e.g., "Security Foundations – 101", "Choices We Made: Architecture – Part 1").
- Open each subsequent part with a one-paragraph recap of the series so far — assume some readers are joining mid-series.
- Close each part with a concrete preview of the next installment, not a vague "stay tuned."
- Use consistent section headings and formatting across parts so returning readers orient quickly.

When starting a series:
- Confirm upfront that more than one part exists (or is planned) before calling it Part 1.
- Define the series arc in the editorial brief: what does the complete series cover, and why does it take multiple parts?

---

## Technical Accuracy Standards

- Every assertion must trace to evidence: a commit, a test result, a measured metric, a decision record.
- If you cannot point to evidence, frame the statement as an observation or hypothesis, not a fact.
- Keep terminology consistent with the project's own planning artifacts and ADRs.
- When referencing code: use repository-relative paths, not absolute paths.
- When referencing metrics: state the measurement method and context, not just the number.

---

## Structural Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| Timeline summary without lessons | Readers already lived through it | Add what you'd do differently |
| Marketing copy without evidence | Destroys credibility | Add specific commits, benchmarks, or quotes |
| Overly long code blocks | Reader skips them | Excerpt and annotate |
| Generic conclusion | Wastes the ending | End with a concrete takeaway or decision |
| Vague "next steps" | Leaves reader with nothing | Name the next thing specifically |
| Apologetic hedging | Undermines the post | State what happened honestly; hedging is different from honesty |

---

## Amplification Craft

Channel derivatives are not summaries. They are translations.

**LinkedIn**: The professional reader skims. Lead with the human story or tension, not the technical detail. The link is the payoff, not the post itself.

**Reddit**: Redditors are allergic to promotion. The post should feel like sharing, not marketing. If the insight is genuinely useful, the community will ask for more. Never lead with "I wrote a post."

**dev.to**: Technical depth is welcome. This is the closest to the primary post in tone. Always set the canonical URL to the primary to avoid duplicate content issues with search engines.

**Bluesky / X / Twitter thread**: Each post must stand alone. If post 3 requires post 2 to make sense, split or rewrite. The hook post is the most important — it determines whether anyone reads the thread. Platform-specific tone, link placement, and hashtag rules are defined in `../nebula-blog/publication-profile.md` when a product publication profile exists.

---

## Checklist Before Delivery

- [ ] Hook does not start with generic background
- [ ] Every major assertion has supporting evidence
- [ ] Code blocks are excerpted, annotated, and not overlong
- [ ] Series context is established if this is part of a series
- [ ] Safety review complete (no secrets, credentials, or internal-only details)
- [ ] Conclusion has a concrete takeaway, not a vague closing
- [ ] Phase 2 derivatives each link to the primary and are adapted (not copied) for their channel

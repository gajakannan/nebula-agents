# Context Engineering

The framework-level reference for how agents keep their working context lean
and relevant: what gets loaded, when, in what form, and how it survives a long
session. This doc names the **strategy**; the mechanisms live in the docs it
links and are not restated here.

Most of the framework's retrieval machinery — the knowledge graph, role
scoping, `.agentignore`, the evidence cold-archive — exists to serve context
engineering. Naming the strategy makes those pieces legible as one discipline
instead of unrelated tools.

## The Four Moves

Context engineering here is organized around four moves. Every retrieval tool
in the framework serves at least one of them.

| Move | Goal | Primary mechanisms |
|------|------|--------------------|
| **Select** | Load only what is relevant | KG query layer, ROUTER, `.agentignore` |
| **Compress** | Fewest tokens per unit of context | tiered lookup, field projection, symbol granularity |
| **Write** | Persist context outside the window | `workstate.py`, KG-DECISION markers, STATUS.md |
| **Isolate** | Partition context by responsibility | per-role scopes, `{PRODUCT_ROOT}` split, sub-agents |

## Select — retrieve only what is relevant

The core discipline: **query an index, do not read the repo.**

| Practice | Tool / contract | Reference |
|----------|-----------------|-----------|
| Route before any code search | `hint.py <path>` (replaces blind grep) | KNOWLEDGE-GRAPH.md |
| Materialize a feature/file slice | `lookup.py` / `blast.py` — joins at query time; **raw yamls never enter context** | KNOWLEDGE-GRAPH.md |
| Follow the load order | `retrieval_contract` in `solution-ontology.yaml`: ontology → canonical-nodes → only the matching feature entry → one hop → raw files only when linked/changed/needed | KNOWLEDGE-GRAPH.md |
| Load only task-matched references | consult `ROUTER.md` before opening any `agents/<role>/references/` file | ROUTER.md |
| Skip cold archives | honor `{PRODUCT_ROOT}/.agentignore`; treat `planning-mds/operations/**` as cold — start from the evidence README + `latest-run.json` | AGENTIGNORE.md |

## Compress — fewest tokens per unit of context

| Practice | Tool / contract | Reference |
|----------|-----------------|-----------|
| Pull the minimum, expand on demand | `lookup.py F#### --tier 1/2/3/4` depth, `--fields ids/summaries/full` verbosity | KNOWLEDGE-GRAPH.md |
| Honor the minimal context contract | `minimum_prompt_block` in `solution-ontology.yaml` | KNOWLEDGE-GRAPH.md |
| Point at spans, not whole files | symbol + line-range results from `blast.py` / `lookup.py`; `diff-impact.py` maps a diff to symbols | KNOWLEDGE-GRAPH.md |
| Treat the KG as starting context | KG is a retrieval aid, not the answer — open raw artifacts only on conflict or verification (source precedence: raw wins) | KNOWLEDGE-GRAPH.md |

**Cache tiers (read:write discipline).** Order what's loaded by volatility so the model
pays cache *reads* (≈0.1× input) for stable material instead of *writes* (≈1.25×). Stratify
into three tiers, most-stable first:

| Tier | Changes | Contents | Caching |
|------|---------|----------|---------|
| **0** | never within a session | system prompt, tool defs, active `SKILL.md`, `ROUTER`, framework docs, `SOLUTION-PATTERNS.md` | large cached prefix |
| **1** | per feature/session | feature folder, linked ADRs, KG slice | ephemeral cache breakpoint |
| **2** | per turn | current instruction, latest retrieval/tool result, current diff | never cached — always the tail |

Rules: **volatile never above stable** — KG `hint`/`lookup`/`blast` results, file reads, and
tool output land in the Tier-2 tail, never interleaved into the preamble (otherwise every
retrieval busts the docs' cache); **keep the Tier-0 prefix byte-identical** across turns — no
timestamps, `--run-id`, per-turn counters, or varying system-reminders in the cached region
(the telemetry `--run-id` stamp lives in the tail); **don't cache one-shot content** — a file
read once is plain 1.0× input, not a 1.25× write. A cache write only pays off when re-read
before it expires (prefix change, 5-min TTL, or context reset), so cache the re-read preamble
and reset context at task boundaries (the Phase A→B / between-feature checkpoints in
`plan.md` / `build.md`) so the prefix doesn't grow unbounded — per-turn cost scales with
context size.

`eval.py` surfaces the result: a **cache-write spike** with high `write_share` is the
signature of a busted prefix; `kg_usage.py budget` flags when the loaded prefix exceeds the
§13.3 70% input budget (see Known gaps).

## Write — persist context outside the window

The long-horizon resilience layer: externalize state so a session can recover
after compaction instead of re-deriving it.

| Practice | Tool / contract | Reference |
|----------|-----------------|-----------|
| Externalize session state | `workstate.py init` (role, scope, run-id); `dump --compact` to recover after compaction | KNOWLEDGE-GRAPH.md |
| Filter stale context | record decisions with `--supersedes`; read `dump --current-view` | KNOWLEDGE-GRAPH.md |
| Make context climbs explicit | `workstate.py escalate` records *why* raw artifacts were opened — governed expansion, not silent ballooning | KNOWLEDGE-GRAPH.md |
| Persist rationale at the edit site | inline `// KG-DECISION:` markers, harvested into `decisions-index.yaml` | KNOWLEDGE-GRAPH.md |
| Query current state, not history | `STATUS.md` rows are append-only audit; resolve "current" via the documented semantics | AGENT-USE.md |

## Isolate — partition context by responsibility

| Practice | Tool / contract | Reference |
|----------|-----------------|-----------|
| Scope each role's reads/writes | per-role read/write surfaces (backend → `engine/**`, frontend → `experience/**`, …) | AGENT-USE.md |
| Separate framework from product | `{PRODUCT_ROOT}` placeholder keeps `agents/**` context out of product context | AGENT-USE.md |
| Exclude outright | `{PRODUCT_ROOT}/.agentignore` removes paths from agent attention | AGENTIGNORE.md |
| Delegate to bounded sub-tasks | action orchestration runs agents within their declared scope | actions/README.md |
| Partition a long run across sessions | bound each session to one story or gate; resume from evidence with `resume-brief.py --run-id` instead of re-deriving | SESSION-SEGMENTATION.md |

Isolate applies across **time** as well as responsibility. A run left in one
session grows until the window fills and compaction truncates it at an arbitrary
point, recovered from a generated summary. Segmenting at a story or gate
boundary moves that cut to a place you choose and recovers it from validated
evidence — the same move, applied to the session axis.

## Measurement — what makes it managed, not vibes

Context efficiency is observed, not assumed.

- `kg_common.estimate_tokens()` + `emit_telemetry()` stamp token estimates and a
  `--run-id` on every retrieval.
- `eval.py --since <ref>` scores retrieval quality against historical telemetry.
- Run/command telemetry is captured per the evidence contract in `AGENT-OPS.md`.
- `capture-run-telemetry.py` writes `token-usage.json` at closeout from the
  agent CLI's own session transcript: whole-run and per-gate `context_tokens`,
  `avg_context_tokens`, the cached/uncached split, and `compactions`. This is
  measured cost, not an estimate — it is what shows whether a context change
  actually paid. A null token field means the CLI does not report it, which is
  deliberately distinct from a measured zero.

If a retrieval pattern starts costing more tokens or returning worse slices, the
telemetry shows it before it becomes habit. Rising `avg_context_tokens` or a
non-zero `compactions` count is the signal that a run needs segmenting.

## Known gaps — discipline, not enforcement

These are deliberate honesty about where the strategy relies on agents
following it rather than being forced:

- **No *in-window* context budget.** `kg_usage.py budget` checks loaded context against
  the §13.3 70/30 budget at gate time (exit 1 when over the 70% input budget), but nothing
  *forces* the agent to run it or to load tier-1-first — it's an advisory gate, not a
  hard in-window ceiling.
- **The write layer depends on the agent calling `workstate.py`.** Skip it and
  post-compaction recovery degrades to re-derivation — and so does session
  segmentation, which reads the same state through `resume-brief.py`. A run that
  never called `workstate.py` can still be segmented, but each session resumes
  with its position and none of its reasoning, so decisions get re-litigated.
  Nothing enforces the call; `init-run.py` does not seed a workstate file.
- **Session boundaries are an instruction, not a control.** "Stop when …" in the
  kickoff is the only thing that ends a session at a chosen point; without it the
  window ends it instead. See SESSION-SEGMENTATION.md.
- **Quality gating is partial.** Low-confidence / `ambiguous` edges *halt*
  action (good), but there is no automatic "you have loaded too much, compress"
  trigger.

A planned KG-retrieval MCP server strengthens **select + compress** by moving
the joins server-side, so only the compact structured slice ever reaches the
model — but it changes the delivery channel, not this strategy.

## Cross-References

- `agents/docs/KNOWLEDGE-GRAPH.md` — the KG query layer, `workstate.py`,
  retrieval contract, and tiering that serve Select / Compress / Write.
- `agents/docs/AGENT-USE.md` — session setup, per-role scopes, and prompt
  clauses that serve Isolate.
- `agents/docs/AGENTIGNORE.md` — `.agentignore` and cold-archive retrieval
  semantics.
- `agents/docs/AGENT-OPS.md` — the telemetry/evidence contract behind
  Measurement.
- `agents/docs/SESSION-SEGMENTATION.md` — Isolate across sessions: session
  kickoff templates, boundary selection, and the `resume-brief.py` read surface.
- `agents/ROUTER.md` — task-to-reference routing (Select for the reference
  corpus).

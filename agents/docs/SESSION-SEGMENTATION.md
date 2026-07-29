# Session Segmentation

How to run one evidence run across several sessions on purpose, instead of
letting the context window end sessions for you.

This is the **Isolate** move applied to time rather than to roles: partition a
long run into bounded sessions, each starting from durable state on disk. See
`agents/docs/CONTEXT-ENGINEERING.md` for how it fits the four moves.

## Why

A long run's context grows until the window fills, then compaction truncates it
at whatever point that happens to be — an arbitrary boundary, recovered from a
model-written summary. Segmentation moves the boundary to a place you choose
(a story, a gate) and recovers from validated evidence artifacts instead.

The mechanics already exist. What segmentation adds is **choosing when to stop**
and **writing down what the next session needs**.

| | Compaction | Segmentation |
|---|---|---|
| Boundary chosen by | the window ceiling | you |
| Recovery source | a generated summary | `gate-state.json`, `workstate.json`, STATUS.md, the artifacts |
| Fidelity | lossy, unpredictable | whatever was recorded |
| Cost of resuming | re-derivation | one `resume-brief.py` read |

## The loop

Each session writes durable state as it works; the next session reads it back
through one command.

```
SESSION N                             SESSION N+1
  resume-brief.py  ──▶ ~1K brief        resume-brief.py  ──▶ ~1K brief
  read the named files                  read the named files
  work                                  work
    workstate.py decision  ─┐
    run-gate.py --stage ────┼─▶ run folder ──┘
    STATUS.md updates     ──┘   (durable)
  stop at the declared line
```

Nothing carries across the boundary except what reached disk. That is the point:
it makes the handoff auditable instead of implicit.

## Choosing boundaries

Split where the run already strains, not on a fixed cadence.

- **Per story** for the implementation gate — the phase carrying the highest
  turn count, and the first to exceed a single window.
- **Per role** where a gate runs two independent reviews (for example code
  review and security review) — they share no working context.
- **Group the short gates.** Planning, validation, signoff, and closeout gates
  are typically tens of turns; separate sessions for each cost more in
  re-establishment than they save.

A useful check: if a phase's turn count multiplied by its context growth rate
exceeds the model's window, it cannot fit one session regardless of discipline
and must be split.

## Session kickoff template

```
Resume <FEATURE_ID>, run <RUN_ID>.

First run: python3 agents/scripts/resume-brief.py --run-id <RUN_ID>
Follow its "Read these, in order" and obey "Do not re-read".

Scope this session: <the one slice>
Stop when: <the boundary>

Before you stop: <what the next session needs written down>
```

Four lines do the work:

- **`resume-brief.py` first.** Establishes position, next gate, recorded
  decisions, current story, and scope in one read. Without it the session
  rebuilds that by exploration, which is the cost segmentation exists to avoid.
- **Scope this session.** One slice. Ambiguity here is what makes a session run
  past its boundary.
- **Stop when.** Nothing in the framework enforces a session boundary — it is
  an instruction, and omitting it returns you to ceiling-driven compaction.
- **Before you stop.** The write half. Skip it and the next brief reports that
  no working state was recorded, so the next session re-derives decisions this
  one already made.

## Worked shapes

**Opening session** — the run does not exist yet, so there is no brief to read.

```
Start the feature action for <FEATURE_ID>, mode clean.

Scope this session: the planning and preflight gates only.
Stop when: preflight passes. Do not start implementation.

Before you stop:
- workstate.py init --role architect --scope <FEATURE_ID> --run-id <RUN_ID>
- record every scope decision with workstate.py decision
- report the RUN_ID back to me
```

**Implementation session, one per story** — only the story id changes between
these.

```
Resume <FEATURE_ID>, run <RUN_ID>.
First run: python3 agents/scripts/resume-brief.py --run-id <RUN_ID>

Scope this session: implement story <FEATURE_ID>-S#### only, through the
implementation gate.
Stop when: that gate passes for this story. Do not start the next story.

Before you stop:
- workstate.py decision for anything you chose that is not in the plan
- workstate.py question for anything unresolved
- flip this story's cells in the STATUS.md Story x Role matrix
```

**Paired review sessions** — the second names the first's output so it is read,
not redone.

```
Scope this session: the code review lane only. Not security review.
Stop when: the code-review report is written and its findings are recorded.
```

```
Scope this session: the security review lane only. Code review is already
done — read its report, do not redo it.
Stop when: the security report is written and the review gate passes.
```

**Closeout session** — checkpoints declared in the action spec still require a
maintainer decision.

```
Scope this session: the closeout gate.
The archive-move checkpoint needs my approval — stop and ask before moving
the feature folder.
```

## Invariants

- **One RUN_ID for the whole run.** Sessions resume a run; they do not start
  new ones. `gate-state.json` and the evidence manifest accumulate across all
  of them. Minting a fresh RUN_ID per session fragments the evidence package.
- **`init-run.py --resume`** is the mechanical counterpart: it reuses an
  existing run folder instead of failing. Segmentation is the operator
  discipline around it, not a replacement for it.
- **Checkpoints are unaffected.** A checkpoint declared in an action spec is a
  maintainer decision and still halts the session that reaches it.
- **The brief is a read surface, not a write.** `resume-brief.py` only reads
  evidence; running it never mutates a run.

## Measuring whether it worked

`token-usage.json` (written at closeout by `capture-run-telemetry.py`) records
per-gate `context_tokens`, `avg_context_tokens`, and `compactions`. Comparing a
segmented run against an unsegmented one on the same action shows the effect
directly: a segmented run records a lower `avg_context_tokens`, and
`compactions` is 0 when no session reached the window ceiling. See
`agents/docs/AGENT-OPS.md` for the evidence contract.

## Cross-References

- `agents/docs/CONTEXT-ENGINEERING.md` — the four moves; segmentation is
  Isolate applied across sessions.
- `agents/docs/KNOWLEDGE-GRAPH.md` — `workstate.py` subcommands that make the
  write half work.
- `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md` — the operator procedure for a
  run end to end.
- `agents/ROUTER.md` — routes resuming a run to `resume-brief.py`.

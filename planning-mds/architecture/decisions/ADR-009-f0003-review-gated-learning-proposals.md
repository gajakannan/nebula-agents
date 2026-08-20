# ADR-009: Learning Proposals Are Inert Artifacts With Allowlisted Targets

## Status

- [x] Proposed
- [ ] Accepted
- [ ] Superseded
- [ ] Rejected

## Context

F0003-S0006 adds `nebula-agents learn review`, which reads failed-run evidence and drafts
proposed corrections to process documents. This is the one place in F0003 where the
runtime forms an opinion about how the framework itself changes, so its safety model
deserves an explicit decision rather than an implementation habit.

The feature README states the constraint plainly: "Failure learning must produce proposed
corrections for review, not automatic instruction edits." The PRD names the matching risk:
"Learning proposals overfit one failed run."

F0004 later builds a full reflective learning loop. F0003 must not prejudge that design,
but it also must not create a path F0004 has to undo.

## Decision Drivers

- A proposal must never mutate a document as a side effect of being generated.
- Instruction files govern agent behavior; a bad edit propagates to every future run.
- Proposals must be traceable to the evidence that produced them.
- One failed run is weak evidence for a process change.
- F0004 must be able to build on this without reversing it.

## Decision

**Proposals are inert.** `learn review` writes proposal artifacts in `Draft` and changes
no other file. Generation and application are separate operations with separate
authorization; there is no flag on `learn review` that applies a proposal. Applying an
accepted proposal is a distinct, explicitly invoked action that takes a decided proposal
as input.

**Targets are allowlisted.** A proposal names a `target_document` that must appear in a
committed allowlist of framework and product instruction paths. A proposal targeting
anything else is refused at generation, with the blocked path recorded. The allowlist is
config, reviewed like any other contract.

**Decisions are append-only and attributed.** `Draft → Accepted | Edited | Rejected |
Archived`. Each decision appends a record carrying proposal ID, reviewer role, decision,
source artifact IDs, reason, and timestamp. Rejection is sticky: a rejected proposal is
not regenerated unless its source evidence changes, which is tracked by the
`content_hash` of the source artifacts (ADR-006). This directly answers the overfit risk —
a proposal the reviewer has already declined does not reappear each run.

**Role authorization follows the target.** The reviewer role must be authorized for the
document being changed: Security Reviewer for security guidance, Architect for
architecture and process, Product Manager for planning process. Authorization is evaluated
against the target, not the proposal.

**Evidence is required and must be current.** A proposal needs at least one source
artifact ID. Generation is blocked when evidence is stale or missing rather than proceeding
on partial input.

## Options Considered

1. **Inert proposals, allowlisted targets, append-only decisions:** Selected.
2. **Auto-apply with git revert as the safety net:** Rejected. Revert is a recovery
   mechanism, not a control; an unnoticed instruction edit changes agent behavior in the
   window before anyone reads the diff, and the diff is not reviewed against the evidence
   that motivated it.
3. **Auto-apply behind a default-off flag:** Rejected. The flag becomes the default in
   any automated pipeline, and the safety model then rests on configuration nobody
   revisits.
4. **Proposals as free-form prose only:** Rejected. Untraceable to evidence, so a
   reviewer cannot check the reasoning, and the overfit risk is unmanageable.
5. **Defer all learning to F0004:** Rejected as a whole, but partially honored — F0003
   captures *proposals from run evidence* and stops there. Curation lifecycle, decay,
   counters, and strategy selection are F0004's.

## Pros / Cons

**Inert proposals**
- Pro: generation is safe to run at any time, including automatically.
- Pro: the reviewer sees evidence and proposal together before anything changes.
- Pro: sticky rejection keeps the overfit failure mode bounded.
- Pro: F0004 can consume these records without unwinding a mutation path.
- Con: a real improvement waits for a human, so the loop is slow by construction.
- Con: proposal artifacts accumulate and need their own retention story.

## Consequences

- `learn review` is a read-plus-write-own-artifacts operation; it never opens a target
  document for writing.
- The target allowlist is a reviewed contract; adding a path is a deliberate change.
- Applying an accepted proposal is out of F0003's automated scope — the decision record
  and patch plan are the deliverable.
- Proposal retention needs a policy before the artifact set grows unbounded.
- F0004 inherits proposal records, decision history, and the allowlist.

## Security & Compliance Notes

- No proposal path may write outside the allowlist, and the allowlist excludes secrets,
  credentials, CI configuration, and `.github/` workflow definitions.
- Proposals targeting security guidance require Security Reviewer acceptance.
- Proposal text passes the same redaction policy as summaries (ADR-008); evidence excerpts
  are redacted before they enter a proposal.
- Decision records are append-only and attributed, so review history is auditable.

## References

- [ADR-006: artifact identity](./ADR-006-f0003-artifact-identity-and-index.md)
- [ADR-008: deterministic summaries](./ADR-008-f0003-deterministic-summaries.md)
- [F0004 reflective learning loop](../../features/F0004-reflective-learning-loop/README.md)
- [F0003 runtime contract](../f0003-runtime-contract.md)

## Follow-up Actions

- [ ] At feature G0, author the initial target allowlist and its review process.
- [ ] Define proposal retention and archival policy.
- [ ] Confirm the F0004 handoff shape for proposal and decision records.

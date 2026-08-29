# ADR-008: Rule-Based Deterministic Summaries, Never Model-Generated

## Status

- [ ] Proposed
- [x] Accepted
- [ ] Superseded
- [ ] Rejected

**Accepted:** 2026-08-29T11:15:45-04:00 by explicit operator approval.

## Context

F0003-S0005 requires summaries of transcripts, command logs, validator output, and
manifests, and states two constraints that together decide the design: summaries must be
"deterministic for the same input fixture", and they are "navigation aids, not
authoritative evidence" (F0003 README) — every summary must link back to the full local
artifact.

The tempting implementation, in a product whose whole subject is agent runs, is to
summarize with a model. That would be wrong here, and it is worth recording why rather
than leaving it to be re-litigated.

## Decision Drivers

- Determinism is a stated acceptance criterion and a test requirement.
- Summaries are consumed by reviewers deciding whether evidence is adequate.
- Redaction must complete before exposure, with a provable boundary.
- Summarization must work with no network, no provider auth, and no cost.
- A summary that silently omits a failure is worse than no summary.

## Decision

Summaries are produced by **rule-based extraction only**. No model call participates in
generating a summary artifact. Each artifact kind has a dedicated extractor with an
explicit, ordered rule set:

| Kind | Preserved by rule |
|------|-------------------|
| Transcript | User prompts, approval moments, tool-call attention points, recovery markers |
| Command log | Command order, duration when available, exit code, every failed command |
| Validator output | Command, exit code, pass/fail, failed rule names, remediation hints |
| Manifest | Gate decisions, evidence paths, declared artifacts |

Extraction is **failure-preserving and lossy only toward passing noise**: a passing block
may be collapsed to a count (`truncation_count`), but a failure marker is never dropped
to satisfy a size bound. When bounds would force dropping a failure, `summary_status`
becomes `Partial` and `last_observed_marker` records where extraction stopped — the
summary says it is incomplete rather than appearing complete.

Redaction runs **before** extraction writes anything, on the same streaming filter F0001
uses for transcripts (ADR-004). If redaction fails, no summary artifact is written and
`redaction_status: Fail` blocks exposure through both CLI and MCP.

Every summary carries `artifact_id` and `source_reference`, so the full artifact is always
one step away. This is what makes lossiness acceptable: the summary is an index into
evidence, never a replacement for it.

## Options Considered

1. **Rule-based extraction:** Selected.
2. **Model-generated summaries:** Rejected. Non-deterministic, so the story's fixture
   requirement cannot be met; introduces network, auth, cost, and latency into a local
   read path; and a hallucinated or omitted failure marker in a *review* artifact is a
   correctness problem, not a quality one. F0003 summaries decide whether humans look
   closer — they must not be probabilistic.
3. **Model summaries with a deterministic cache:** Rejected. The cache makes repeat reads
   reproducible but the first generation still varies, so two operators can hold different
   summaries of the same artifact.
4. **Rule-based extraction with an optional model-generated prose layer:** Rejected for
   this feature and left open for F0004. It splits the artifact into a trustworthy half
   and a non-trustworthy half with no visible boundary for the reader.
5. **No summaries; always show full artifacts:** Rejected. It is the current state, and
   the review loop it produces is exactly what F0003 exists to fix.

## Pros / Cons

**Rule-based extraction**
- Pro: byte-identical output for identical input, so fixtures test it.
- Pro: no network, auth, cost, or latency in a local read path.
- Pro: a reviewer can reason about what the summary can and cannot omit.
- Pro: redaction boundary is provable by test.
- Con: extractors need per-kind maintenance as formats drift.
- Con: unstructured provider transcripts extract less cleanly than structured logs, so
  transcript summaries carry the most rule risk.
- Con: no natural-language synthesis; the summary reads as structured markers.

## Consequences

- Every extractor ships with fixtures asserting byte-identical output.
- An unrecognized artifact kind yields `summary_status: Unsupported` plus retrieval
  metadata — never a best-effort guess.
- Transcript extraction rules are the most likely to need revision; they are versioned
  with the summary so an old summary is re-derivable.
- Summaries are regenerable at any time from source, so they are a cache, not evidence,
  and may be discarded safely.
- F0004's reflective learning loop may layer model reasoning *on top of* these summaries;
  it must not replace them.

## Security & Compliance Notes

- Redaction precedes any summary write; failure blocks exposure through every surface.
- Summary size bounds are configured, not unbounded, so a hostile artifact cannot exhaust
  local storage.
- Extraction never executes artifact content; command logs are parsed as data.
- Summaries never include environment values or credential-file contents.

## References

- [ADR-004: transcript redaction](./ADR-004-f0001-transcript-redaction.md)
- [ADR-006: artifact identity](./ADR-006-f0003-artifact-identity-and-index.md)
- [F0004 reflective learning loop](../../features/F0004-reflective-learning-loop/README.md)
- [F0003 runtime contract](../f0003-runtime-contract.md)

## Follow-up Actions

- [ ] At feature G0, fix the per-kind rule sets and their fixture corpus.
- [ ] Define the summary rule-set version field and its compatibility policy.
- [x] Accepted through the Phase B operator approval gate.

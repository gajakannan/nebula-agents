# Test Plan — F0003 Local Agent Runtime Control Plane

**Run:** `2026-08-29-16075bda` · **Gate:** G2 · **Owner:** Quality Engineer · **Date:** 2026-08-29

## Scope

Seven stories, delivered across eight build steps. F0003 extends the F0001 package; the
514 F0001 tests are part of this feature's regression boundary and must pass **unmodified**
— that is S0007's acceptance criterion, not a convention.

## Strategy

Four layers, each answering a different question. The split matters because a defect has
twice been found in the *seam* between two correctly-tested layers, so seam coverage is a
first-class lane rather than an afterthought.

| Lane | Question it answers | Location |
|------|--------------------|----------|
| Unit | Is the rule right? | `tests/unit/` |
| Contract | Does the published surface match what is committed? | `tests/contract/` |
| Integration | Does it behave against a real filesystem? | `tests/integration/` |
| Security | Do the stated boundaries hold under attack-shaped input? | `tests/security/` |

## Test matrix by story

| Story | Lane coverage | Key risks the tests target |
|-------|---------------|----------------------------|
| S0001 | integration, contract | Guard runs **before** launch; a blocked launch creates no run and starts no session |
| S0002 | unit, integration | A timeout is not a pass; a stale report re-probes rather than warns; probe output is redacted before persistence |
| S0003 | contract | Read-only is structural at instance **and** import level; every envelope is schema-conformant; `evidence_show` refuses unredacted content |
| S0004 | unit, integration, security | Identity survives a moved runtime root; longest-match under all three nestings; symlink resolved before containment; digest collision is loud |
| S0005 | contract, integration | Byte-identical across processes and interpreter versions; failure markers never dropped for size |
| S0006 | unit, integration | Metrics recompute from pinned revisions; inapplicable ≠ zero; sticky rejection in both directions; target-document authorization |
| S0007 | contract | 514 F0001 tests unmodified; audit stream byte-identical; query facade mutation-free by construction |

## Determinism

S0005 requires byte-identical summaries. Asserted three ways, because two of them can pass
while the third fails:

1. Repeated calls in one process.
2. **Separate processes** — Python randomises string hashing per process, so an extractor
   iterating a set anywhere passes (1) and fails this.
3. **Three interpreter versions** — 3.11, 3.12, 3.14, compared by corpus digest.

The fixture corpus was authored **before** the extractors, so the rules were not shaped
around their own inputs.

## Regression boundaries

| Boundary | How it is held |
|----------|----------------|
| 514 F0001 tests | Run unmodified in every suite execution |
| Audit stream | Captured from `main` pre-split and diffed against every subsequent step |
| Summary output | Corpus digest compared across steps and interpreters |
| Inward dependency rule | `test_layering.py`, added after a real violation |
| No new required dependency | `test_package_contract.py` plus a clean-install check |

## Environments

Python 3.11.15, 3.12.13, 3.14.4 — the CI matrix. Two Python-version-specific `pathlib`
bugs were previously found in this repository by exactly that matrix, which is why
single-version execution is not accepted here.

Real tmux 3.6 exercises F0001's session path. F0003 adds no new subprocess path, so
provider and tmux seams are faked in F0003's own tests and the real-process assertion is
left to F0001's `test_real_tmux_lifecycle.py`, which runs and does not skip.

## Coverage target

Floor is `coverage_min_pct` from `agents/actions/spec/_contract.yaml`. Branch coverage is
reported alongside lines; the first G2 evidence run recorded `branch-rate 0` because the
flag was absent, which is why it is stated explicitly here.

## Explicitly out of scope

- Hosted or multi-user operation, provider credential storage, automatic gate approval —
  all outside F0003 (PRD *Out of Scope*).
- Third-party MCP host conformance. The surface is exercised in-process and as a real
  subprocess against the protocol shape this repository already serves; no published
  conformance suite is run.
- Applying an accepted learning proposal. Outside F0003's automated scope (ADR-009).

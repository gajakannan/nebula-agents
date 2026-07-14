# F0001 Test Plan — run 2026-07-13-1cfbc5a0

## Scope

The acceptance lane covers the complete local Python CLI/TUI vertical slice under `engine/`:

- S0001: Python/tmux/provider/workspace preflight, exact planning-document and missing-path diagnostics, prompt-leaf containment, stable classifications, and credential-boundary tests.
- S0002: descriptor validation, bounded colliding-session failures, feature/story symlink containment, exactly-once fake-provider launch, real tmux attach, recovery, and session freshness.
- S0003: owner-only durable registry, atomic/CAS writes, recovery invariants, canonical evidence-run discovery, semantic deduplication, persisted last-valid gate state through malformed observations, and restoration reconciliation.
- S0004: validator allowlist and feature-root containment, terminal results, evidence symlink rejection, reviewer summary path/secret suppression, evidence eligibility, hold/resume/approve guards, stale revisions, and ABAC.
- S0005: opt-in transcript lifecycle, redact-before-write streaming boundaries, durable ongoing/post-disable failures, delayed terminal completion, attach-after-failure availability, symlink/permission containment, safe preview, and recovery context.
- S0006: bounded/sanitized CLI JSON and table output, read-only session/status/evidence commands, keyboard TUI actions, resize/timeout behavior, and explicit confirmation.

## Test Levels

- Unit: domain transitions, authorization, services, adapters, config/identity/policy, watcher/validator, and TUI behavior.
- Contract: CLI grammar/envelopes, JSON schemas, formatter projection, committed prompts, and architecture boundary files.
- Integration: bootstrap/composition, filesystem recovery, subprocess/provider adapters, transcript pipe/filter, and real tmux lifecycle with a fake provider.
- Security: descriptor containment and modes, no-shell/provider boundary checks, streaming secret redaction, unsafe-path rejection, default deny, and no raw secret persistence.
- Smoke: installed package import, console help, JSON doctor, empty session list, and stable not-found error.

## Pass Criteria

- All tests pass with zero failures, errors, skips, or expected failures.
- Line coverage for `nebula_agents` is at least 85%; no coverage waiver is permitted.
- The real-tmux test launches one fake provider, attaches to the same recorded session, and does not launch a second process.
- Compile, whitespace/diff, story, tracker, architecture, schema, and template checks pass.
- Critical/high defects discovered by code or security review are fixed and regression-tested before G3 can pass.

## Environment

- Python 3.14.4 in `/tmp/f0001-venv`; package installed editable from `engine[test]`.
- pytest 9.1.1, pytest-cov 6.3.0, jsonschema 4.26.0.
- tmux 3.6 on the approved host-runtime lane.
- No real provider model turn or provider credential inspection is part of the suite.

## Result

PASS — 424 tests passed with zero failures, errors, skips, or expected failures; coverage passed at 90.03%.

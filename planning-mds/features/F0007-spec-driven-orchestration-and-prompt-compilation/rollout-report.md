# F0007 Rollout and Rollback Report (S0009)

**Status:** Rollout **HOLD** — awaiting required role signoffs and a live governed
product pilot. Framework adoption of the spec-driven gates is in place; the
destructive cutovers remain human-gated.

## 1. Lifecycle / CI gates enforced

Added to `lifecycle-stage.yaml` (run by `run-lifecycle-gates.py`, invoked from CI
via `agents/templates/ci-gates-template.yml`):

| Gate | Command | Blocks on |
|------|---------|-----------|
| `action_spec_schema` | `validate_action_specs.py` | Schema / semantic-invariant / version-resolution failure |
| `contract_conformance` | `contract-conformance.py` | Independent-invariant or historical-baseline-matrix failure (weakened contract) |
| `prompt_drift` | `render-prompts.py --check` | Generated prompt drift or a hand edit to a generated file |

Pre-existing framework gates (`boundary_genericness`, `skill_regression`,
`agent_map_schema`) are unchanged. The dual-read parity matrix
(`contract_compat.py --matrix`) and the inverse-literal audit
(`contract-value.py --audit`) are available as diagnostics; wiring them as blocking
CI gates is deferred with the constant-removal decision below.

**Remediation:** each gate prints a machine-readable failure; fix the policy (never
the generated file) and re-run the named command.

## 2. Governed pilot — rehearsal evidence

`agents/scripts/tests/test_pilot_end_to_end.py` drives a full run end-to-end against
a scaffolded fixture product root:

- `init-run.py` creates the run and stamps `contract_version` (fixed at creation).
- `run-gate.py` sequences typed operations through the shared shell-free runtime,
  pauses at the manual checkpoint, verifies a **hashed** evidence attestation, and
  resumes to completion.
- Telemetry is complete and durable: `commands.log` (JSONL v1), `lifecycle-gates.log`
  blocks per stage, and a `gate-state.json` journal with the attestation + hashes.
- An in-flight run cannot change its contract version between gates.

**Not yet done (human-gated):** the LIVE governed pilot on a real product feature
(real `feature.yaml` operations + `{PRODUCT_ROOT}/scripts/kg/*` + independent feature
review with all required roles) and its closeout signoffs. The rehearsal proves the
toolchain; it does not substitute for the role-owner review the PRD requires.

## 3. Rollback rehearsal

Rollback is **configuration / generated-output based** and never edits published
history (proven by `test_rollback_preserves_immutable_history`: regeneration and
validation do not mutate any `history/<version>.yaml`).

Procedure:

1. Revert the policy change commit (`git revert` / `git checkout <prev> -- agents/actions/spec/_contract.yaml agents/actions/spec/<action>.yaml`). This restores the previous `active_version` and removes the not-yet-relied-upon new bundle addition; it never edits a published bundle in place.
2. Regenerate prompts: `python3 agents/scripts/render-prompts.py`.
3. Re-run the gates: `action_spec_schema`, `contract_conformance`, `prompt_drift`.
4. Never roll back by editing `contract_version` in an existing evidence manifest — historical runs keep the version selected at creation.

## 4. Residual risks

- The 24 hand-written evidence-contract prompts are **not** yet replaced by generated
  output; only the `feature` pilot pair exists under `generated/`. Cutover needs
  role-owner semantic-equivalence approval (S0006).
- The validator's private date matrices are **still active** (parity proven, removal
  deferred to a recorded decision after the live pilot — S0007/S0008).
- The 40% action/SKILL prose thinning is not done (role-owner-gated — S0008).

## 5. Rollout decision

**HOLD.** Framework gate adoption and the toolchain are ready and green. Promotion of
the spec-driven path to authoritative (prompt cutover, constant removal, prose
thinning) requires: (a) a live governed product pilot reaching closeout, and (b) the
required role signoffs in `STATUS.md` (Architect, QE, Code Reviewer, DevOps, Security).
Recorded by: automated implementation (Claude), 2026-07-18. Owner for promotion: maintainer.

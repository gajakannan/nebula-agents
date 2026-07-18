# Generated evidence-contract prompts

**Do not edit these files by hand.** Every `*.md` in this directory is compiled
from the action policy (`agents/actions/spec/<action>.yaml` + `_contract.yaml`)
by `agents/scripts/render-prompts.py`. Each file carries a `GENERATED` header.

## Workflow

1. Edit the policy (`agents/actions/spec/<action>.yaml` or `_contract.yaml`), never
   the generated file.
2. Regenerate:
   ```bash
   python3 agents/scripts/render-prompts.py            # all actions
   python3 agents/scripts/render-prompts.py --action feature
   ```
3. Commit the regenerated output alongside the policy change.

## Drift gate

`render-prompts.py --check` regenerates to memory and fails on any difference
between committed and regenerated output — a hand edit, a stale file, or a policy
change that was not regenerated. It runs as the `prompt_drift` lifecycle gate
(`lifecycle-stage.yaml`). Resolution for a conflict or a drift failure is always
"re-run `render-prompts.py`", never a manual edit.

Both variants — `<action>-operator-friendly.md` (prose) and
`<action>-automation-safe.md` (uppercase outline) — encode the **same** policy
(scope, inputs, run-id rules, session setup, gates, operations, artifacts,
constraints, severity gate, stop conditions, and judgment notes). An action may
declare a subset in its spec's `variants` field (e.g. operator-only actions).

## Status (F0007-S0006)

The `feature` pair is generated here as the pilot. Cutover of the hand-written
prompts in the parent directory to these generated files is a human-gated rollout
step (PM + affected role owners approve semantic equivalence per the story's
Role-Based Visibility) and is intentionally **not** automatic.

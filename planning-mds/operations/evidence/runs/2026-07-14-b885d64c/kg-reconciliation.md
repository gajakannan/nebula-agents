# KG Reconciliation — F0001-tmux-native-agent-cockpit run 2026-07-14-b885d64c

## G7 Re-entry Decision

The operator selected remediation option 1 on 2026-07-14: adopt the compiled knowledge-graph
toolchain and establish initial product shards. The Architect used the completed F0006 implementation
in `nebula-insurance-crm` as the governed reference, adapted its tracker projection to this product,
and completed substantive G7 validation on 2026-07-15.

## Binding Delta

The as-built source confirms the six capabilities predicted at G0. All six now have canonical IDs and
validated implementation bindings; the adopted compiler/toolchain is represented by a seventh
capability.

| Canonical capability | Bound implementation surface | G0-declared? | Result |
|----------------------|------------------------------|--------------|--------|
| `capability:native-session-preflight` | preflight application service, provider/process/config adapters, and focused tests | yes | PASS |
| `capability:tmux-session-lifecycle` | run service, ports, tmux adapter, session entry, bootstrap, and real-tmux/reconciliation tests | yes | PASS |
| `capability:local-run-registry` | authorization, domain records/transitions, filesystem/identity/policy/schema stores, and focused tests | yes | PASS |
| `capability:evidence-and-gate-control` | gate service, evidence watcher, descriptor boundary, and focused tests | yes | PASS |
| `capability:redacted-transcript-recovery` | transcript service/adapters/filter, redaction domain, security and integration tests | yes | PASS |
| `capability:read-only-run-queries` | query service, CLI/formatters/interop/TUI, contract/security/TUI tests | yes | PASS |
| `capability:compiled-kg-projection` | `scripts/kg/**`, authored shards, shard schemas, and generated projections | adopted prerequisite | PASS |

Binding globs were narrowed to authored source and test paths so ignored C# `bin/` and `obj/`
outputs cannot enter the symbol projection. Every declared binding pattern resolves to at least one
repository path.

## Canonical Nodes

The authored source under `planning-mds/kg-source/**` contains:

- 7 capabilities;
- 2 entities;
- 3 workflows;
- 4 ADR records;
- 5 schema records;
- 2 roles;
- 4 policy rules;
- feature shards for F0001-F0007.

The compiled projection contains 27 canonical nodes, 2 mapped features (F0001 and F0006), 15 mapped
stories, 5 explicit coverage exclusions for planned/superseded scope, and 7 code bindings. F0001 owns
six story mappings. F0006 owns the nine adopted toolchain story mappings. REGISTRY and ROADMAP fenced
regions now compile from the feature shards, and `TRACKER-GOVERNANCE.md` records the adopted model.

## Validator Results

| Check | Command | Result |
|-------|---------|--------|
| Shard schema and ownership | `python3 scripts/kg/shard_validate.py` | PASS |
| Deterministic compile | `python3 scripts/kg/compile.py` and `python3 scripts/kg/compile.py --check` | PASS — projection trio, ontology mirror, and tracker regions are current |
| Symbol/decision regeneration | `python3 scripts/kg/validate.py --regenerate-symbols --check-symbols --regenerate-decisions --check-decisions` | PASS — 1,608 bound Python symbols; 0 decision markers |
| Reproducibility and git policy | `python3 scripts/kg/validate.py --check-reproducible` | PASS |
| Semantic drift | `python3 scripts/kg/validate.py --check-drift` | PASS |
| Toolchain tests | `/tmp/f0001-kg-venv/bin/pytest -q -ra scripts/kg/tests` | PASS — 186 passed, 1 fixture-path skip |
| Existing runtime regression | engine suite without host-tmux case, plus isolated host-tmux test | PASS — 513 + 1 = 514 |
| Scoped F0001 story validation | `validate-stories.py ... planning-mds/features/F0001-tmux-native-agent-cockpit` | PASS |
| Tracker validation | `validate-trackers.py ... --skip-feature-evidence` | PASS — 0 errors, 0 warnings |

The ontology still declares `validated_by` and `supersedes` edge types that this initial product
graph does not yet use; drift validation reports those as non-blocking warnings. The Casbin
`policy.csv` drift check is correctly skipped because this local product uses its own JSON policy
contract rather than that optional artifact.

`coverage-report.yaml` was intentionally not regenerated at G7. Per the lifecycle contract, coverage
regeneration occurs after the G8 archive move so timestamps and feature paths represent the final
closeout state.

Result: **PASS**

## Handoff To Closeout

The prior bootstrap blocker is closed. The semantic graph, compiled outputs, symbol/decision indexes,
reproducibility policy, and drift checks are green. G8 Product Manager closeout is authorized; it must
archive F0001, update its feature shard path/status, recompile, regenerate post-move coverage and story
indexes, validate trackers/evidence, disposition recommendations, and publish closeout state.

# F0007 - Feature Assembly Plan

## 1. Plan Identity

| Field | Value |
|-------|-------|
| Feature | F0007 - Spec-Driven Orchestration and Prompt Compilation |
| Status | Proposed |
| Phase | Framework Hardening |
| Source design | `agents/docs/PROSE-TO-SPEC-MIGRATION.md` |
| Build strategy | Four gated phases; preserve old behavior until dual-read parity and pilot acceptance |

## 2. Scope Split

| Layer | Owns | Does Not Own |
|-------|------|--------------|
| Versioned policy | Fixed gates, artifacts, operations, ordering, thresholds, stop conditions | Review judgment or product-specific implementation |
| Runtime scripts | Resolution, execution, locking, checkpoint state, logging, rendering | Policy meaning not declared in the spec |
| Validators | Evidence acceptance under the stamped policy version | Runtime sequencing side effects |
| Generated prompts | Operator/automation presentation of policy and retained rationale | Independent correctness proof |
| Hand-written prose | Judgment criteria, classification, clarification, teaching, voice | Duplicated fixed procedure |
| Independent fixtures | Historical and semantic expectations | Generated restatement of policy |

## 3. Story Assembly Order

```text
S0001 versioned policy/schema
   +--> S0002 conformance + behavioral diff
   +--> S0003 init/scaffold
   +--> S0004 typed runtime + telemetry
             +--> S0005 gate/checkpoint/severity
S0001+S0002+S0005 --> S0006 prompt generation
S0001+S0002+S0005 --> S0007 validator convergence
S0006+S0007       --> S0008 policy consumers + prose thinning
all accepted      --> S0009 governed pilot and rollout
```

S0003 and S0004 may run in parallel after S0001. S0006 may begin template prototyping after S0002,
but generated prompts do not become authoritative until S0005 defines their runtime calls.

## 4. Planned File Inventory

| Path | Change | Story |
|------|--------|-------|
| `agents/actions/spec/schema/action-spec.schema.json` | Add structural action-policy schema | S0001 |
| `agents/actions/spec/_contract.yaml` | Add active version and shared values | S0001 |
| `agents/actions/spec/history/*.yaml` | Add immutable resolved historical bundles | S0001 |
| `agents/actions/spec/<action>.yaml` | Add active action specifications | S0001/S0006 |
| `agents/scripts/validate_action_specs.py` | Structural/semantic validation and policy selection | S0001 |
| `agents/scripts/tests/fixtures/action-specs/**` | Valid, invalid, and historical fixtures | S0001/S0002 |
| `agents/scripts/contract-conformance.py` | Independent invariants and baseline matrix | S0002 |
| `agents/scripts/init-run.py` | Versioned, locked run initialization | S0003 |
| `agents/scripts/scaffold-product.py` | Idempotent product scaffolding/check | S0003 |
| `agents/scripts/gate_runtime.py` | Shared shell-free typed execution | S0004 |
| `agents/scripts/exec-and-log.py` | Arbitrary argv execution with normalized telemetry | S0004 |
| `agents/scripts/run-lifecycle-gates.py` | Reuse shared runtime without interface regression | S0004 |
| `agents/scripts/run-gate.py` | Stage sequencing and durable checkpoint journal | S0005 |
| `agents/scripts/gate_policy.py` | Central severity state machine | S0005 |
| `agents/scripts/render-prompts.py` | Compile both prompt variants and check drift | S0006 |
| `agents/templates/prompts/evidence-contract/*.md` | Generated committed outputs | S0006 |
| `agents/scripts/validate_templates.py` | Add drift while retaining semantic invariants | S0006 |
| `agents/product-manager/scripts/validate-feature-evidence.py` | Version-aware dual-read convergence | S0007 |
| `agents/templates/evidence-manifest-template.json` | Require version for new runs | S0007 |
| `CONSUMER-CONTRACT.md` | Document version and legacy resolution | S0007/S0009 |
| `agents/scripts/contract-value.py` | Resolve shared policy values for consumers | S0008 |
| `agents/scripts/lint-vague-language.py` | Central vague-language checks | S0008 |
| `agents/agent-map.yaml`, coverage scripts | Replace private coverage literals | S0008 |
| `agents/actions/*.md`, `agents/*/SKILL.md` | Remove duplicated fixed procedure | S0008 |
| `lifecycle-stage.yaml`, CI templates, CHANGELOG | Adopt conformance and drift gates | S0009 |

## 5. Contract Data Model

| Object | Required Fields | Invariants |
|--------|-----------------|------------|
| Policy bundle | `version`, `effective_from`, `shared`, `actions` | Immutable after publication; dates monotonic; fully resolved |
| Action spec | `action`, `contract`, `inputs`, `ownership`, `gates`, `stop_conditions` | Action/version matches active bundle; scope is known |
| Run operation | `argv`, `cwd`, `timeout_seconds`, `expected_artifacts`, `mutates` | No shell form; placeholders allowlisted; roots contained |
| Checkpoint | `id`, `description`, `requires`, `produces` | Unique ID; cannot resume without attestation |
| Gate state | `schema_version`, `run_id`, `stage`, `completed`, `pending`, `attestations` | Atomic writes; append-only completion; hashes recorded |
| Contract diff | base/head versions and changed policy paths | Deterministic order; classifies compatibility impact |

## 6. Mutation Traceability

| Mutation | Entry Point | Authorization | Concurrency | Failure Behavior | Audit Evidence | Story |
|----------|-------------|---------------|-------------|------------------|----------------|-------|
| Publish active policy | Reviewed spec change | Maintainer + Architect review | Git merge serialization | Schema/conformance blocks merge | Behavioral diff + CI | S0001/S0002 |
| Initialize run | `init-run.py` | Action caller within product root | Per-feature lock | No partial folder; conflict exits non-zero | Seed context + manifest | S0003 |
| Scaffold product | `scaffold-product.py` | Explicit product-root caller | Idempotent missing-only writes | Temp cleanup; existing files preserved | Scaffold report | S0003 |
| Execute operation | `gate_runtime.py` | Spec-declared gate or lifecycle config | Per-run lock around state/log | Timeout/failure stops sequence | JSONL + structured verdict | S0004/S0005 |
| Attest checkpoint | `run-gate.py --attest-checkpoint` | Role/operator named by action | Per-run lock | Missing outputs or hash failure rejected | Gate-state attestation | S0005 |
| Regenerate prompts | `render-prompts.py` | Maintainer edits policy/template | CI serialization | Drift exits non-zero; no partial publish | Generated header + diff | S0006 |
| Validate old evidence | Evidence validator | Read-only | Parallel safe | Unknown policy fails named rule | Version selection in result | S0007 |

## 7. Integration Checkpoints

| Checkpoint | Testable Criterion | Owner |
|------------|--------------------|-------|
| C1 Policy | Valid active and historical bundles pass; malformed versions/operations fail | S0001 |
| C2 Meaning | Historical baseline matrix unchanged; weakening fixture fails independently | S0002 |
| C3 Initialization | Two simultaneous creators yield one run; resume is idempotent | S0003 |
| C4 Execution | argv with spaces/metacharacters stays one argument; no shell invocation path exists | S0004 |
| C5 Checkpoint | Resume across unattested manual step fails; valid attestation records hashes | S0005 |
| C6 Prompts | Two generations are byte-identical; manual semantic review accepts feature pair | S0006 |
| C7 Validator | Dual-read result matrix reports zero disagreement across all stages/cutovers | S0007 |
| C8 Consolidation | Private threshold-literal audit is clean; target prose shrinks at least 40% | S0008 |
| C9 Pilot | New governed feature reaches closeout with complete logs and no historical regression | S0009 |

## 8. Architecture Decisions

### ADR F0007-001 - Versioned policy with immutable resolved history

**Status:** Proposed

**Decision:** Active policy is editable through review; every published historical bundle is fully
resolved and immutable. New manifests carry a version. Legacy manifests map by effective date.

**Rationale:** A mutable shared matrix cannot preserve archived evidence semantics. Fully resolved
history avoids accidental inheritance from current constants.

**Rejected alternatives:** One mutable spec (retroactive interpretation); copying policy into each
manifest (large, hard to validate); migrating archived manifests in place (destroys historical truth).

### ADR F0007-002 - Typed operations and shared runtime

**Status:** Proposed

**Decision:** Executable policy uses argv arrays. `gate_runtime.py` is shared by action and lifecycle
runners and never invokes a shell.

**Rationale:** String commands create quoting, injection, and platform ambiguity. Reusing one runtime
prevents two execution semantics.

### ADR F0007-003 - Generated consistency plus independent correctness

**Status:** Proposed

**Decision:** Prompts, runners, and validators consume the policy, while independent fixtures and
semantic invariants remain separately authored.

**Rationale:** Generation eliminates drift but cannot prove the shared input still encodes the right
contract.

### ADR F0007-004 - Durable manual checkpoint attestations

**Status:** Proposed

**Decision:** Manual steps pause the gate journal and require evidence-bearing attestation before
resume. Resume flags cannot jump an unattested checkpoint.

**Rationale:** The archive/publish seam is too consequential to represent as an unaudited CLI offset.

## 9. Test Strategy

- Unit: schema validation, placeholder resolution, policy selection, diff ordering, gate arithmetic.
- Property/fuzz: argv preservation, invalid YAML shapes, path traversal, duplicate IDs.
- Concurrency: simultaneous initialization and log/state appends.
- Snapshot: both prompt variants for every action scope.
- Historical: fixture verdicts at each effective-date cutover.
- Integration: lifecycle runner regression and feature G0/G8 sequences in a disposable product root.
- Pilot: one real governed feature run with closeout and rollback rehearsal.

## 10. Handoffs and Stop Conditions

- Stop if any historical fixture changes verdict without an explicitly approved new contract version.
- Stop if an executable string or shell invocation remains reachable from spec content.
- Stop if prompt equivalence requires moving judgment into opaque schema fields with no readable output.
- Stop if dual-read disagreement cannot be classified and fixed before removing private constants.
- Stop rollout if an in-flight run would change execution paths or contract version between gates.
- Route policy/schema questions to Architect, expected-verdict changes to QE + PM, execution safety to
  Security + Code Reviewer, and CI/generated artifact workflow to DevOps.

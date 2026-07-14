---
template: security-review
version: 2.0
feature_id: F0001
run_id: 2026-07-13-1cfbc5a0
---

# Security Review Report — F0001-tmux-native-agent-cockpit run 2026-07-13-1cfbc5a0

## Scope

- Feature ID: F0001
- Run ID: 2026-07-13-1cfbc5a0
- Date: 2026-07-13
- Reviewer: Security Reviewer (`agents/security`)
- Assessment: `PASS WITH RECOMMENDATIONS`
- Deployment boundary: local Python CLI/TUI and native tmux/provider processes; no HTTP listener, database, remote API, or application credential store

## Reviewed Surfaces

- OS-derived identity, local policy parsing, role/binding resolution, action authorization, ownership checks, and reviewer grants.
- Reviewer state projections, capability-controlled TUI/CLI guidance, validator summaries, reconciliation, and evidence observation.
- Gate evidence discovery, semantic verdicts, validator binding, digest/revision freshness, symlink rejection, and commit-lock authorization.
- Governed prompt, feature, story, validator, runtime, descriptor, transcript, and evidence filesystem boundaries.
- Provider/tmux execution through typed argv, `shell=False`, `shlex.join` at intentional tmux seams, and validated `execvpe` descriptors.
- Optional transcript lifecycle, streaming redact-before-write behavior, durable worker status, preview containment, and failure safety.
- Runtime snapshots, sequenced JSONL audit events, error/output sanitization, owner-only permissions, recovery, and CAS.
- Python dependencies, hardcoded-secret exposure, Bandit SAST results, and DAST applicability.

The broader design artifacts are `planning-mds/security/threat-model.md`, `authorization-review.md`, `data-protection.md`, `secrets-management.md`, `owasp-top-10-results.md`, and `reviews/security-review-2026-07-13.md`.

## Threat Boundary

| Subject | Resource | Operation | Enforced boundary |
|---|---|---|---|
| LocalOperator | owned run, tmux session, evidence, transcript | launch, attach, reconcile, validate, decide gate, recover, configure transcript | OS UID, owner UID, action policy, lifecycle invariants, expected revision |
| Reviewer | non-owned run projection | read state, observe evidence, run allowlisted validator | explicit binding, deny-by-default policy, sanitized projection, no read-path persistence |
| Reviewer with named grant | attach, hold/approve, launch, transcript control | only the granted action | named boolean grant plus normal ownership/resource and lifecycle checks; no implicit role elevation |
| System actor | owned internal projection | probe/read for recovery | system role cannot be locally assigned; foreign-owner and mutation access denied |
| tmux/provider process | private launch descriptor and workspace | direct native provider execution | canonical executable/cwd, owner-only no-follow descriptor, bounded schema, fixed environment-name allowlist, typed argv |
| Evidence watcher/validator | governed feature and evidence trees | inspect evidence and run a fixed validator | canonical ancestry, no symlink components, stable bounded reads, semantic gate verdicts, fixed command allowlist |
| Transcript worker | tmux bytes and run transcript | redact and append; publish terminal status | exact owner-only target, streaming redaction before write, bounded state, durable completed/failed status |

The owning OS UID is the accepted local trust boundary. A process already acting as that UID can access that user's files; F0001 does not claim hostile same-UID or remote multi-tenant isolation.

## Auth / Authz

F0001 uses the policy surface documented in `planning-mds/security/f0001-authorization-model.md`. The authoritative identity is the current OS UID and supplementary groups; display labels are never credentials. The default effect is deny.

- LocalOperator mutations require an owned resource.
- Reviewer probe/read and fixed validator access require an explicit Reviewer binding.
- Reviewer launch, attach, hold, approve, and transcript configuration remain denied unless their specific grant is true.
- Exact UID bindings take precedence over group bindings; duplicate subjects and conflicting effective roles fail closed.
- Protected mutations reload and reauthorize the current policy/run under the repository lock before commit.
- Non-owner projections hide workspace, prompt, evidence, audit, tmux, transcript, validator artifact, and untrusted validator-summary details.
- Gate approval requires confirmation plus evidence and validator results freshly bound to the same gate ID, current revision, and evidence digest under the commit lock.

No new remote permission, tenant, service account, token, password, or root bypass is introduced.

## Validation

Input controls include fixed enums/regexes for provider, action, feature/story/run/gate/session identifiers; schema validation for descriptors, run state, policy, events, and output; canonical ancestry; no-follow file opens; owner/mode/type checks; file/output size bounds; environment-name and validator command allowlists; stable `fstat` checks; and CAS revisions.

Final focused security regression command:

```text
/tmp/f0001-venv/bin/pytest -q tests/security tests/unit/test_authorization.py tests/unit/test_runtime_config_identity_policy.py tests/unit/test_transitions.py tests/unit/test_watcher_validator.py tests/unit/test_tmux_adapter.py tests/unit/test_application_services.py tests/unit/test_tui_behavioral_coverage.py tests/integration/test_transcript_filter.py tests/integration/test_transcript_adapter.py tests/integration/test_process_and_providers.py
```

Result: `307 passed in 0.72s`. This set covers gate deletion/replacement/revision races; reviewer projection and non-persistence; duplicate/conflicting policy bindings; evidence/prompt/feature/story/validator symlinks; command seams; transcript chunk redaction and terminal worker failure; authorization; and presentation capability controls. A direct bearer-token hold-reason probe persisted only `[REDACTED]`.

The frozen QE baseline independently records `424 passed`, zero failures/errors/skips/xfails, `90.03%` line coverage, and `1 passed` for the real tmux lifecycle.

## Audit / Logging

Runtime events cover launch, attach/recovery, validators, gates, transcript lifecycle, reconciliation, and authorization denials. Events are schema-validated, sequenced, append-only through the application repository, and stored in owner-only JSONL beside revisioned state images.

Audit payloads use stable identifiers, exit codes, durations, relative artifact names, categories, and counts. Process output, validator output, gate reasons, and transcript content are redacted/sanitized and bounded; raw environments and credentials are not logged. A non-owner never receives the raw validator summary or internal artifact path.

The local JSONL stream is not cryptographically tamper-evident against another process already acting as the owning UID. That limitation is a Low recommendation within the accepted MVP trust boundary.

## Secrets / Config

Provider authentication remains native to Codex or Claude Code. F0001 does not read provider auth files, keychains, shell history, API-key environment variables, or credential-store contents, and it does not persist a provider credential. The launch descriptor forwards only approved environment names; provider login prompts remain inside native tmux.

Runtime/policy/run/transcript directories and files are owner-only and reject unsafe symlinks, types, owners, or modes. Transcript capture is disabled by default and uses bounded streaming redaction before the first durable byte. Redaction or worker failure publishes `Failed` and blocks safe preview.

`detect-secrets 1.5.0` found no committed secret in application source or `engine/pyproject.toml`. Credential rotation and revocation remain the provider's responsibility because the application owns no secret or encryption key.

## Scan Disposition

| Class | Ran | Result / Finding summary | Artifact or waiver reason |
|---|---:|---|---|
| dependency | yes | Clean; `pip-audit` exit 0, no known vulnerabilities in the resolved dependency set | `artifacts/security/dependency-audit.json` |
| secrets | yes | Clean; `detect-secrets 1.5.0` exit 0 with `results: {}` | `artifacts/security/secrets-scan.json` |
| sast | yes | Findings reviewed; Bandit 1.9.4 scanned 5,572 source lines with 17 Low, 0 Medium, 0 High, no skipped files, and no `nosec` suppressions | `artifacts/security/bandit-sast.txt` |
| dast | no | Not applicable to the approved local CLI/TUI architecture | Waiver: no network listener or HTTP target; owner Security Reviewer; approved 2026-07-13 |

Final scan commands/results:

- `/tmp/f0001-venv/bin/pip-audit --requirement /tmp/f0001-audit-requirements.txt --cache-dir /tmp/pip-audit-cache --progress-spinner off --strict` — exit 0, no known vulnerabilities.
- `/tmp/f0001-venv/bin/detect-secrets -c 1 scan engine/src/nebula_agents engine/pyproject.toml` — exit 0, empty results.
- `/tmp/f0001-venv/bin/bandit -r engine/src/nebula_agents -f txt` — exit 1 because Low findings exist; 17 Low, 0 Medium, 0 High across 5,572 lines.

Bandit's findings are reviewed B110 best-effort audit/compensation handlers, B404/B603 intentional direct `shell=False` subprocess boundaries, B101 an internal post-`Popen` invariant, and B606 validated `execvpe`. They do not create an injection path, grant access, or suppress a primary authorization failure.

## OWASP Top 10 Coverage

| Category | Status | Notes |
|---|---|---|
| A01 Broken Access Control | OK | OS identity, explicit binding, deny-by-default action policy, resource ownership, named reviewer grants, minimized projections, and lock-time reauthorization. |
| A02 Cryptographic Failures | OK / limited applicability | No application credential or network transport; owner-only local storage and optional host disk encryption. No custom cryptography claimed. |
| A03 Injection | OK | Typed argv, `shell=False`, quoted intentional tmux seams, canonical descriptors, fixed validators, and bounded validated identifiers/paths. |
| A04 Insecure Design | OK | Explicit OS trust boundary, STRIDE model, fresh gate evidence binding, fail-closed policy, and opt-in redact-before-write transcript. |
| A05 Security Misconfiguration | OK | No listener/root bypass/remote policy; owner-only defaults, fixed environment names, schema validation, and unauthorized UI controls hidden without becoming enforcement. |
| A06 Vulnerable / Outdated Components | OK with Low recommendation | Dependency audit is clean; deterministic hash locking is recommended for release reproducibility. |
| A07 Identification & Authentication | OK / limited applicability | Caller identity is OS-derived; ambiguous roles fail closed; provider authentication/MFA/session revocation remain provider-native. |
| A08 Software & Data Integrity | OK with Low recommendation | Canonical no-follow paths, schemas, revisions, sequences, atomic state, and evidence digests; local audit is not cryptographically tamper-evident against the owning UID. |
| A09 Security Logging & Monitoring | OK with Low recommendation | Sanitized sequenced events cover security-sensitive actions and denials; centralized monitoring is outside the local MVP. |
| A10 Server-Side Request Forgery | N/A | No HTTP client, URL fetch, webhook, or server-side request surface exists. |

## Findings

Open findings by severity: Critical 0; High 0; Medium 0; Low 3.

- [low] Compatible dependency ranges can resolve different builds after the reviewed audit; publish a reviewed hash-locked constraints or lock artifact for packaged/CI releases — owner: DevOps; follow-up: deferred-no-followup
- [low] An already-compromised process acting as the owning UID can rewrite the local JSONL event stream without cryptographic evidence; add hash chaining, signed export, or an OS-protected audit sink if stronger accountability enters scope — owner: Security Reviewer; follow-up: deferred-no-followup
- [low] A future credential syntax may not match the finite transcript redaction patterns; maintain provider-format and adversarial split-chunk/private-key regression cases while preserving fail-closed capture — owner: Security Reviewer; follow-up: deferred-no-followup

All previously reproduced High/Medium findings are closed: stale gate approval, unredacted hold reasons, reviewer internal-path/validator-summary disclosure, reviewer read mutation, ambiguous policy bindings, governed-path symlink escapes, and transcript terminal-state races.

## Recommendation Disposition

| Recommendation | Disposition | Release impact |
|---|---|---|
| Deterministic hash-locked release dependencies | Deferred; current resolved set is audited clean and compatible ranges are bounded | Accepted Low residual; non-blocking |
| Optional cryptographic/external audit tamper evidence | Deferred until accountability extends beyond the owning-UID trust boundary | Accepted Low residual; non-blocking |
| Redaction format/corpus maintenance | Ongoing security maintenance; current formats and chunk/private-key boundary cases pass | Accepted Low residual; non-blocking |

Any future network listener, remote multi-user deployment, application-managed credential, plugin download, database, or URL-fetch capability invalidates the limited-applicability conclusions and requires a new threat model and DAST target.

## Result

`PASS WITH RECOMMENDATIONS`

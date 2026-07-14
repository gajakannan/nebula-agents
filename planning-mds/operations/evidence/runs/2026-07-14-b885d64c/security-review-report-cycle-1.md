---
template: security-review
version: 2.0
feature_id: F0001
run_id: 2026-07-14-b885d64c
---

# Security Review Report — F0001-tmux-native-agent-cockpit run 2026-07-14-b885d64c

## Scope

- Feature ID: F0001
- Run ID: 2026-07-14-b885d64c
- Date: 2026-07-14
- Reviewer: Security Reviewer (`agents/security`), independent of the current remediation implementation
- Assessment: `REQUEST CHANGES`
- Deployment boundary: local Python CLI/TUI and native tmux/provider processes; no HTTP listener, database, remote API, URL-fetch service, or application credential store

This fresh G3 pass reviewed the exact current worktree, the changed-path inventory, the prior review and remediation recommendations, the F0001 architecture/security/contracts, and every raw test/security artifact in this run. The security boundary remains the owning OS UID. F0001 does not claim isolation from a process already acting as that UID, but it does claim fail-closed lifecycle, authorization, governed-path, validator, and audit behavior inside that boundary.

The required cold evidence index `planning-mds/operations/evidence/README.md` and an F0001 `latest-run.json` pointer were absent. Because this review was explicitly assigned run `2026-07-14-b885d64c`, the exact run manifest was read directly. This evidence-governance limitation does not alter the source findings or expand review scope.

## Reviewed Surfaces

- OS-derived identity, local policy parsing, role/binding resolution, named reviewer grants, owner checks, and lock-time reauthorization.
- Launch, attach, recovery, gate, validator, evidence watcher, transcript, and state/audit failure paths.
- Run snapshot/event crash consistency, revision sequencing, backup recovery, authorization before corrupt-state access, and sanitized projections.
- Governed prompt, feature, story, validator, descriptor, runtime, transcript, and evidence filesystem boundaries, including symlink/replacement races.
- Provider/tmux execution through typed argument vectors, intentional tmux shell-string quoting, and descriptor-validated `execvpe` entry.
- Transcript redact-before-write behavior, worker-status sidecars, completion/failure reconciliation, preview containment, and sanitized failure reasons.
- Dependency resolution, hardcoded-secret exposure, Bandit results, branch-enabled coverage, and DAST applicability.

## Threat Boundary

| Subject / trigger | Resource | Operation | Required security property | Current result |
|---|---|---|---|---|
| LocalOperator | owned run and tmux session | launch, attach, recover, reconcile | owner/action authorization and durable fail-closed state | Issue: H-01 |
| Reviewer | non-owned run | read, probe, validate | explicit binding, minimized projection, no read-path mutation | Pass |
| Reviewer with named grant | attach, gate, launch, transcript | only the specifically granted mutation | grant plus normal owner/resource/lifecycle controls | Pass except effects of H-01/H-02/H-03 |
| Evidence watcher/validator | governed feature/evidence trees | observe and validate fixed content | descriptor-bound, no-follow, stable content; verdict bound to current digest | Issue: H-02 |
| Transcript worker | tmux stream and owner-only transcript | redact, append, publish terminal state | no plaintext-before-redaction; crash-safe completed/failed state | Issue: H-03 |
| Filesystem/power fault | snapshot and JSONL event | interrupt commit after publication | reconcile ambiguous commit outcome and terminalize safely | Issue: H-01 |
| tmux/provider process | private launch descriptor/workspace | execute native provider | fixed executable/cwd/environment names; no credential ingestion | Pass |

STRIDE emphasis for this local design is tampering and elevation through false lifecycle/gate state, information disclosure through projections/transcripts, repudiation through incomplete audit compensation, and denial of service through process/filesystem faults. H-01 affects tampering, repudiation, and fail-safe availability. H-02 affects tampering and gate-authority integrity. H-03 affects information disclosure, tampering, and repudiation because capture can continue behind a terminal durable state. No direct spoofing, remote code execution, SSRF, or cross-UID credential path was found.

## Auth / Authz

The current policy remains deny by default. The caller identity is derived from the OS UID and supplementary groups; display labels are not credentials. Exact-UID bindings take precedence, ambiguous or duplicate effective roles fail closed, LocalOperator mutations require ownership, and Reviewer mutations require their named grant as well as the normal resource and lifecycle checks. Foreign-owner projections suppress workspace, prompt, audit, tmux, transcript, evidence, validator artifact, and untrusted summary details.

Corrupt-state recovery authorizes a current-UID LocalOperator before repository recovery and then checks the recovered immutable owner again. Reviewer and foreign-owner recovery attempts are rejected before corrupt content is exposed. This closes the prior corrupt-state discovery/recovery authorization seam.

The authorization policy itself is sound, but H-01 can leave an authoritative `Active` record after the session was killed, H-02 can create a false successful validator fact, and H-03 can leave capture active after an authorized completion produced a durable `Completed` record. Downstream checks cannot safely authorize against state whose production was not fail closed.

## Validation

The implementation has strong fixed-enum/regex/schema validation, canonical ancestry, no-follow descriptor opens, owner/mode/type checks, bounded reads/output, environment and command allowlists, stable `fstat` checks, and compare-and-swap revisions. Evidence observation preserves the last valid durable projection when a later JSON, YAML, Markdown, lifecycle, gate, or story read is malformed or denied. Attach rejects failed/exited runs and checks tmux liveness.

Three boundary gaps remain:

1. Launch does not reconcile whether a repository commit became visible before raising, so its compensation can target a stale revision and then be silently discarded (H-01).
2. The stories validator receives a pinned feature-directory descriptor but enumerates and later reads descendant story pathnames. Those leaf reads are not descriptor/no-follow bound (H-02).
3. Transcript completion assumes every repository exception means the `Completed` transition was not published. It can restart the pipe from the stale `Active` record after `Completed` is already durable (H-03).

Fresh read-only validation performed during this review:

- `PYTHONDONTWRITEBYTECODE=1 /tmp/f0001-remediation-venv/bin/pytest -q -p no:cacheprovider engine/tests/security engine/tests/unit/test_authorization.py engine/tests/unit/test_watcher_validator.py engine/tests/unit/test_application_services.py engine/tests/integration/test_filesystem_store.py engine/tests/integration/test_transcript_adapter.py engine/tests/integration/test_transcript_filter.py` — `276 passed in 1.34s`.
- `/tmp/f0001-remediation-venv/bin/pip-audit -r /tmp/f0001-remediation-audit-requirements.txt -f json --progress-spinner off` — exit 0, no known vulnerabilities.
- Expanded `detect-secrets` scan over current source, tests, `engine/pyproject.toml`, F0001 planning/architecture/schema/security surfaces — exit 0, `results: {}`.
- `python3 agents/security/scripts/security-audit.py planning-mds/security` — pass.
- G2 evidence validator rerun — pass for the in-progress run state.

The green suite is relevant but does not inject an actual after-`os.replace` directory-fsync failure into launch or transcript completion, nor swap a descendant story between enumeration and `read_text`; it therefore does not close H-01, H-02, or H-03.

Raw JUnit and Cobertura were parsed independently. JUnit records 476 tests, 476 passed, and zero failures, errors, skips, or expected failures. Its SHA-256 is `988f4a1d239a19e20aa6b097ffe84e72c6a718385cfe1690c99a1f20d4a16c1f`. Coverage records 4,019/4,482 lines (89.67%) and 1,146/1,418 branches (80.82%); authorization (42/42), transitions (24/24), redaction (26/26), and session entry (60/60) each have 100% branch coverage. Its SHA-256 is `bb248602f5a7e082bcee7bb41a64ce32d096e1a18ded975c1729604749237b44`.

## Audit / Logging

Runtime events are schema-validated, sequenced, bounded, sanitized, and persisted in owner-only JSONL next to revisioned snapshots. Authorization denials, launch/attach, validator, gate, transcript, and reconciliation actions are represented. Hold reasons, process output, validator summaries, transcript failures, and non-owner projections are redacted or minimized; no raw environment or provider credential is logged.

Transcript completion/failure uses atomic terminal sidecars. On ordinary paths, the application waits for terminal worker status, records a bounded failure reason, blocks preview when capture/redaction failed, and can reconcile a completed or failed sidecar after an application commit or compensation failure. Combined output/status failure is converted to a durable failure through pipe liveness and reconciliation. H-03 shows that the ordinary sidecar design does not cover an ambiguous post-publication repository error: the compensation itself can restart capture behind a terminal snapshot.

H-01 is an audit-integrity exception: `RunLaunched` and `Active` can be visible even after launch compensation kills tmux, while the stale `LaunchFailed` commit is swallowed. The local JSONL stream also remains non-cryptographic against the accepted owning-UID boundary; that pre-existing limitation remains Low.

H-03 is a transcript audit/privacy exception: `TranscriptCompleted` and a `Completed` snapshot can be visible while the exception fallback re-enables the pipe. Reconciliation only probes capture status for an `Active` durable transcript, so the mismatch is not self-healing from the published record.

## Secrets / Config

Provider authentication remains native to Codex or Claude Code. F0001 does not read provider auth files, keychains, shell history, API-key environment variables, or credential-store contents, and this review did not inspect any such files. Only approved environment names are forwarded through the private launch descriptor. Transcript capture remains disabled by default and applies bounded streaming redaction before the first durable byte. H-03 does not bypass the redactor, but it can extend the collection period beyond an authorized completion and expose a mutating file through the completed-preview path; that is a material privacy and data-lifecycle failure.

The raw secret scan is clean, and the broader fresh scan is also clean. Redaction covers the current tested bearer, key, token, password, private-key, and split-chunk cases. A future credential syntax can exceed a finite pattern set, so corpus maintenance remains a Low recommendation.

## Scan Disposition

| Class | Ran | Result / finding summary | Artifact or waiver reason |
|---|---:|---|---|
| dependency | yes | Clean: 11 resolved dependencies, zero known vulnerabilities; fresh rerun also clean | `artifacts/security/dependency-audit.json` |
| secrets | yes | Clean: `results: {}`; expanded fresh scan over source/tests/contracts also clean | `artifacts/security/secrets-scan.json` |
| sast | yes | 6,348 LOC; 18 Low scanner findings, 0 Medium, 0 High; 17 High-confidence and 1 Medium-confidence; no errors, skips, or `nosec` suppressions. Manual review escalates the security context around B110 handlers into H-01 and H-03 | `artifacts/security/bandit-sast.json` |
| dast | no | Waiver approved: the local CLI/TUI architecture exposes no listener, HTTP route, server, URL-fetch, or remote dynamic target | Architect waiver in `evidence-manifest.json`, approved 2026-07-14; independently confirmed by Security Reviewer |

### CVE-2025-71176 reconciliation

The initial pytest 8 environment was correctly rejected. [NVD CVE-2025-71176](https://nvd.nist.gov/vuln/detail/CVE-2025-71176) identifies pytest through 9.0.2 on Unix as affected by insecure temporary-directory creation. The [pytest 9.0.3 release](https://github.com/pytest-dev/pytest/releases/tag/9.0.3) records the fix. `engine/pyproject.toml` now requires `pytest>=9.0.3,<10`; the audited and tested clean environment resolves pytest 9.1.1. R8 is closed.

### All Bandit findings

| # | Location | ID | Security disposition |
|---:|---|---|---|
| 1 | `application/gates.py:172` | B110 | Best-effort terminal audit fallback preserves the primary gate failure; no grant on audit failure. Accepted scanner Low. |
| 2 | `application/queries.py:65` | B110 | Denial-audit failure does not expose the denied projection or grant access. Accepted scanner Low. |
| 3 | `application/runs.py:85` | B110 | Denial-audit failure preserves the authorization denial. Accepted scanner Low. |
| 4 | `application/runs.py:331` | B110 | Not benign in context: it suppresses the stale compensation commit after a partially visible launch commit. Escalated to H-01. |
| 5 | `application/runs.py:381` | B110 | Transcript-pipe cleanup is secondary; failed transcript state blocks preview and is reconcilable. Accepted scanner Low. |
| 6 | `application/transcripts.py:65` | B110 | Best-effort disable compensation preserves primary transcript failure and safe state. Accepted scanner Low. |
| 7 | `application/transcripts.py:83` | B110 | Related to H-03: an ambiguous enable commit can be published before cleanup runs, so blindly disabling from the stale record can also desynchronize durable and external state. |
| 8 | `application/transcripts.py:111` | B110 | Related to H-03: suppressing a disable failure before persisting `Failed` relies on an unproven external capture state. |
| 9 | `application/transcripts.py:203` | B110 | H-03 context: this suppresses reconfiguration failure, but the more dangerous branch is successful reconfiguration after a partially published `Completed` commit. |
| 10 | `application/transcripts.py:224` | B110 | Same H-03 flaw in the compatibility completion branch without `capture_status`. |
| 11 | `infrastructure/process.py:6` | B404 | Intentional subprocess boundary; callers supply typed argument vectors and `shell=False`. Accepted scanner Low. |
| 12 | `infrastructure/process.py:71` | B603 | `Popen` uses the validated typed argv seam, bounded environment names, and no shell. Accepted scanner Low. |
| 13 | `infrastructure/process.py:80` | B101 | Internal post-`Popen` pipe invariant; optimized-mode removal causes safe failure rather than command or access expansion. Accepted scanner Low. |
| 14 | `infrastructure/tmux.py:7` | B404 | Intentional native tmux subprocess adapter. Accepted scanner Low. |
| 15 | `infrastructure/tmux.py:86` | B603 | Fixed tmux argv and `shell=False`; intentional shell text inside tmux is constructed with quoting at the governed seam. Accepted scanner Low. |
| 16 | `infrastructure/transcript.py:241` | B110 | Worker terminal-status cleanup is best effort; pipe liveness makes loss fail closed. Accepted scanner Low. |
| 17 | `infrastructure/transcript.py:267` | B110 | Secondary sidecar cleanup cannot authorize transcript preview. Accepted scanner Low. |
| 18 | `presentation/session_entry.py:132` | B606 | `execvpe` occurs only after executable/cwd/descriptor validation and fixed environment filtering. Accepted scanner Low. |

Thirteen scanner findings have no independently actionable injection, disclosure, or authorization path in the current design. Finding 4 is part of H-01. Findings 7-10 expose or surround the unsafe transcript compensation assumptions in H-03. Bandit's uniform Low labels do not account for the authoritative lifecycle and privacy context.

## R1-R10 Security Reassessment

| Item | Security disposition | Evidence / remaining risk |
|---|---|---|
| R1 doctor/path diagnostics | Closed | Absolute missing paths and the full path table are emitted without adding a credential or traversal surface. |
| R2 attach/launch fail closed | Reopened — H-01 | Attach rejects terminal state and absent tmux, but launch can persist `Active`, kill tmux, then swallow stale compensation after a partial repository commit. |
| R3 last-valid evidence | Closed | Malformed/denied JSON, YAML, Markdown, gate, lifecycle, feature, and story observations preserve the last valid durable projection. |
| R4 descriptor-bound validators | Reopened — H-02 | Script/workspace/feature-root descriptors are pinned; descendant story content is still enumerated and read by mutable pathname. |
| R5 transcript crash consistency | Reopened — H-03 | Terminal sidecars cover worker failures, but a post-publication repository exception can persist `Completed` and then re-enable capture from the stale `Active` record. |
| R6 corrupt-state recovery | Closed | LocalOperator/current-UID authorization occurs before recovery; immutable recovered owner is rechecked; Reviewer/foreign-owner paths deny. |
| R7 branch-enabled coverage | Closed | Cobertura contains branch data; four mandated risk modules are each 100%. H-01/H-02/H-03 demonstrate that thresholds do not replace adversarial boundary tests. |
| R8 pytest vulnerability | Closed | Contract is `>=9.0.3,<10`, resolved pytest is 9.1.1, and the fresh dependency audit is clean. |
| R9 product-root precedence | Closed | Explicit option → environment → cwd precedence is deterministic, tested, and does not broaden governed ancestry. |
| R10 launch next steps | Closed | TUI and explicit tmux attach guidance are separate; no implicit attach or privilege expansion was introduced. |

## Prior Finding and Recommendation Closure

| Prior item | Current disposition |
|---|---|
| Stale gate approval after evidence/revision change | Closed: fresh gate ID/revision/digest binding and lock-time reauthorization remain present. |
| Secret-bearing hold reason | Closed: persisted and displayed reasons are redacted/sanitized. |
| Reviewer internal paths/raw validator summary | Closed: minimized foreign-owner projection remains enforced. |
| Reviewer read-path mutation | Closed: reviewer observation/probe remains non-persistent. |
| Duplicate/conflicting policy bindings | Closed: ambiguous identity/role resolution fails closed. |
| Governed-path symlink escape | Partially reopened as H-02: initial ancestry/root checks close static escape, but not a descendant post-enumeration swap inside the stories validator. |
| Transcript terminal-state race | Reopened as H-03: worker terminal sidecars are sound, but application commit-outcome ambiguity can restart the pipe after `Completed` is published. |
| Hash-locked dependency recommendation | Open Low: compatible ranges and a temporary audit requirements file are not a durable reviewed hash lock. |
| Cryptographic audit-tamper recommendation | Open Low within the accepted same-UID boundary. |
| Redaction corpus/format maintenance | Open Low; current tests/scans are clean. |

## OWASP Top 10 Coverage

| Category | Status | Notes |
|---|---|---|
| A01 Broken Access Control | Issue | Policy checks are sound, but H-01/H-02 can manufacture unsafe authoritative lifecycle or validator facts consumed by protected workflows; H-03 defeats an authorized capture-completion boundary. |
| A02 Cryptographic Failures | OK / limited applicability | No application credential or network transport; owner-only local storage. Stronger same-UID audit evidence remains Low. |
| A03 Injection | OK | Typed argv, `shell=False`, bounded identifiers, fixed validators, and validated `execvpe`; no command/SQL/template injection path found. |
| A04 Insecure Design | Issue | Ambiguous launch/transcript commit outcomes and descendant validator TOCTOU violate the stated fail-closed design. |
| A05 Security Misconfiguration | OK | No listener/root bypass/remote policy; owner-only defaults and fixed environment-name forwarding. |
| A06 Vulnerable / Outdated Components | OK with Low recommendation | Resolved audit is clean and pytest CVE is reconciled; release dependency hash locking remains open. |
| A07 Identification & Authentication | OK / limited applicability | OS-derived identity and fail-closed role resolution; provider authentication remains provider-native. |
| A08 Software & Data Integrity | Issue | H-01 and H-03 break state/event/external-effect agreement; H-02 validates mutable descendant content outside the governed root. |
| A09 Security Logging & Monitoring | Issue | H-01 can omit the compensating launch fact; H-03 can record completion while capture has restarted. |
| A10 Server-Side Request Forgery | N/A | No HTTP client, URL-fetch, webhook, or server-side request surface exists. |

## Findings

Open findings by severity: Critical 0; High 3; Medium 0; Low 3.

### High — H-01: launch partial commit can leave false Active authority and incomplete audit

- Evidence: `engine/src/nebula_agents/application/runs.py:301-335`; `engine/src/nebula_agents/infrastructure/filesystem_store.py:258-271`, `292-299`, and `318-336`.
- Behavior: repository commit appends `RunLaunched`, replaces `run.json` with revision 1 `Active`, and only then fsyncs the directory. A failure after replacement raises to launch even though the new state/event are visible. Launch kills the created tmux session, attempts `LaunchFailed` at stale revision 0, and suppresses the resulting failure at `runs.py:331-332`.
- Security impact: durable authority and audit claim an active run/session after the external session is gone. Attach's live probe limits direct attachment, but state-based evidence, validator, gate, transcript, operator, and audit workflows can consume a false active lifecycle fact. The missing compensating event also undermines incident reconstruction.
- Exploit/fault scenario: an after-publication directory-fsync error or equivalent storage interruption triggers the ambiguous outcome. This is classified High—not Critical—because no direct remote, cross-UID, credential, or arbitrary-code path was found; the impact to the cockpit's authoritative integrity boundary is nevertheless substantial and realistic.
- Required remediation: reconcile commit outcome under the repository lock. On any ambiguous commit exception, reload/recover the current revision and event sequence; if `RunLaunched` became visible, terminalize from that current revision with an explicit compensation/failure event. Do not suppress inability to establish a durable terminal fact. Add an integration fault-injection test at the real repository boundary after snapshot replacement/before directory-fsync completion and assert no durable `Active`+absent-session result.
- Owner: Backend Engineer with Architect review.
- Target: before the next G3 rerun, no later than 2026-07-15.
- Follow-up: `F0001-G3-H01`.

### High — H-02: descriptor-bound stories validation does not bind descendant content

- Evidence: `engine/src/nebula_agents/infrastructure/watcher.py:410-465`; `agents/product-manager/scripts/validate-stories.py:42-55`, `314-344`, and `385-390`.
- Behavior: the runner pins the validator script, workspace, and feature root descriptors, then passes `/proc/self/fd/<feature-fd>`. The validator uses `Path.rglob` to collect story pathnames and later `Path.read_text` to reopen each leaf. A story can be replaced after enumeration by a symlink to a valid out-of-feature story, and the child can report success.
- Security impact: a mutable pathname can substitute content outside the governed feature boundary and produce a false successful validator result. The gate can then treat that result as fresh for the current digest/revision even though the validated bytes were not the governed bytes. This violates path containment and gate-integrity claims.
- Exploit scenario: a local workspace writer swaps a story leaf between enumeration and load. This is classified High—not Critical—because it requires local write/race capability and does not itself execute the substituted content; successful substitution can still bypass a required governance validator.
- Required remediation: validate bytes from stable no-follow leaf descriptors. Either walk/open every component relative to the pinned feature directory with `dir_fd`/`O_NOFOLLOW`, require regular current-owner safe-mode files and stable `fstat`, then parse those open bytes, or preopen and pass an immutable descriptor list to the child. Add an actual subprocess race test that replaces a story after enumeration and requires fail-closed nonzero validation.
- Owner: Backend Engineer and Product Manager validator owner, with Architect review.
- Target: before the next G3 rerun, no later than 2026-07-15.
- Follow-up: `F0001-G3-H02`.

### High — H-03: transcript completion can publish Completed and then restart capture

- Evidence: `engine/src/nebula_agents/application/transcripts.py:186-205` and `208-226`; the shared post-publication repository failure point is `engine/src/nebula_agents/infrastructure/filesystem_store.py:258-271` and `318-336`. Related enable/failure compensation assumptions occur at `transcripts.py:68-85` and `108-129`.
- Behavior: completion first disables the tmux pipe and observes terminal status, then commits `TranscriptCompleted`. The repository can replace the snapshot and append the event before directory fsync raises. Both exception fallbacks assume the durable snapshot is still `Active` and call `configure` using the stale record, restarting capture even when `Completed` is already authoritative.
- Security impact: the user-visible state enables completed transcript preview and represents capture as stopped, while the redact-before-write worker continues appending terminal output. Redaction reduces plaintext exposure but does not authorize continued collection, make a concurrently mutating preview stable, or preserve truthful audit. Because reconciliation probes capture status only when the durable transcript is `Active`, the mismatch can persist.
- Exploit/fault scenario: an after-publication directory-fsync error during transcript completion triggers successful fallback reconfiguration. Later credentials or sensitive terminal text can be collected after the user completed capture. This is classified High—not Critical—because content still passes through the redactor and no direct remote/cross-UID path was found; the consent, confidentiality, and audit impact is substantial.
- Required remediation: after any transcript commit exception, reload/recover the current revision/event under lock before choosing external compensation. If `Completed` or `Failed` published, keep/force the pipe disabled and verify it; only restore capture when the authoritative state is provably still `Active`. Apply the same commit-outcome protocol to enable/failure paths. Add real-repository fault tests after snapshot replacement/before directory-fsync completion and assert a terminal durable transcript never coexists with a live pipe or mutating completed preview.
- Owner: Backend Engineer with Security Reviewer and Architect review.
- Target: before the next G3 rerun, no later than 2026-07-15.
- Follow-up: `F0001-G3-H03`.

### Low recommendations

- [low] Compatible dependency ranges can resolve different builds after the reviewed audit; publish a reviewed hash-locked constraints or lock artifact for packaged/CI releases — owner: DevOps; follow-up: deferred-no-followup
- [low] An already-compromised process acting as the owning UID can rewrite the local JSONL event stream without cryptographic evidence; add hash chaining, signed export, or an OS-protected audit sink if stronger accountability enters scope — owner: Security Reviewer; follow-up: deferred-no-followup
- [low] A future credential syntax may not match the finite transcript redaction patterns; maintain provider-format and adversarial split-chunk/private-key regression cases while preserving fail-closed capture — owner: Security Reviewer; follow-up: deferred-no-followup

No independent Critical or Medium finding was identified. The three High findings are release/gate blockers and are not waivers or deferred recommendations.

## Recommendation Disposition

| Item | Disposition | Release impact |
|---|---|---|
| H-01 commit-outcome reconciliation | Must remediate and independently retest | Blocks G3 |
| H-02 descriptor-bound descendant validation | Must remediate and independently retest | Blocks G3 |
| H-03 transcript completion/pipe reconciliation | Must remediate and independently retest | Blocks G3 |
| Deterministic hash-locked release dependencies | Retain as Low recommendation; current resolved set is audited clean | Non-blocking after blockers close |
| Optional cryptographic/external audit tamper evidence | Retain until accountability extends beyond owning UID | Non-blocking after blockers close |
| Redaction format/corpus maintenance | Ongoing maintenance; current corpus and scans pass | Non-blocking after blockers close |
| Architect DAST no-target waiver | Approved by Security Reviewer for this exact local architecture | Non-blocking; invalidated by any future listener/network target |

Any future network listener, remote multi-user deployment, application-managed credential, plugin download, database, URL-fetch capability, or cross-UID service invalidates the current limited-applicability conclusions and DAST waiver.

## Result

`REQUEST CHANGES`

G3 Security does not pass. Remediate H-01, H-02, and H-03, add boundary-level regression tests, refresh affected raw test/coverage/SAST evidence, and request a new independent Security Reviewer pass.

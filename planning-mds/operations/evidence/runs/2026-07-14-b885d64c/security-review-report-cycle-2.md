---
template: security-review
version: 2.0
feature_id: F0001
run_id: 2026-07-14-b885d64c
review_cycle: 2
---

# Security Review Report — F0001-tmux-native-agent-cockpit run 2026-07-14-b885d64c, cycle 2

## Scope

- Feature ID: F0001
- Run ID: 2026-07-14-b885d64c
- Review cycle: 2
- Date: 2026-07-14
- Reviewer: Security Reviewer (`agents/security`), independent of both remediation cycles
- Assessment: `REQUEST CHANGES`
- Deployment boundary: local Python CLI/TUI plus native tmux/provider processes; no HTTP listener, database, remote API, URL fetcher, or application credential store

This is a fresh review of the source and evidence refreshed after G3 cycle 1. The immutable archive `security-review-report-cycle-1.md` was used only as a finding ledger and remains unchanged at SHA-256 `9ed763cd55549ced503697ff9fa25e1a94f923b4bfd2a6c83daec3ff43b3c6f2`. The current manifest, exact changed-file inventory, raw scans, JUnit, Cobertura, new boundary tests, and current source were reassessed directly.

The owning OS UID remains the accepted local trust boundary. A process already acting as that UID can access or alter that user's files; F0001 does not claim hostile same-UID isolation. It does claim that lifecycle, authorization, governed validator input, transcript collection state, and audit facts remain fail closed when a bounded application or adapter operation fails.

The reviewed diff inventory is `artifacts/diffs/changed-files.txt`, SHA-256 `054d38de01633e9dd6a0272bb1db6e9505b513cd6f66c9f2ff1efbef43eac0ff`. The implementation remains an uncommitted/untracked worktree, so that artifact and the source hashes observed during this pass—not the named Git head—define the review boundary.

## Reviewed Surfaces

- H-01 launch publication, recovery-image/event reconciliation, tmux compensation, terminal audit, attach safety, and authorization.
- H-02 inherited validator descriptors, descendant enumeration, no-follow opens, metadata/type/owner/mode/size checks, stable byte reads, subprocess descriptor passing, and gate-result integrity.
- H-03 transcript completion publication, terminal sidecars, pipe compensation, preview gating, and recovery.
- Adjacent transcript enable, launch-with-transcript, observed-failure, disable-failure, and nested compensation paths.
- OS identity, deny-by-default role policy, named reviewer grants, resource ownership, minimized projections, corrupt-state recovery authorization, and lock-time reauthorization.
- Provider/tmux command construction, bounded subprocess output, descriptor-based `execvpe`, error sanitization, transcript redaction, and local audit storage.
- Refreshed dependency, secret, Bandit, JUnit, branch coverage, and DAST-waiver evidence.

## Threat Boundary

| Subject / trigger | Asset and operation | Required security property | Cycle-2 disposition |
|---|---|---|---|
| LocalOperator | owned run; launch/attach/recover/gate/transcript | OS-derived identity, ownership, named action authorization, current revision | Pass |
| Reviewer | non-owned run; read/probe/validator and explicit grants | deny by default, minimized projection, no implicit mutation | Pass |
| Filesystem/power fault | event, state image, latest snapshot | reconcile ambiguous publication before external compensation | H-01 closed |
| Workspace/validator content | feature root and story bytes | fixed script/root descriptors, no symlink following, stable bounded bytes | H-02 closed for the stated boundary |
| Transcript worker/tmux | redacted terminal stream and pipe | durable state must truthfully represent whether collection is active | Issue: H-04 |
| Provider/tmux executable | launch descriptor and workspace | fixed validated executable/cwd/env names and safe argv | Pass |

STRIDE coverage:

- Spoofing: identity is OS-derived; ambiguous bindings and unbound roles deny.
- Tampering: state/event recovery and descriptor-bound story reads close H-01/H-02; H-04 still permits external pipe state to diverge from durable transcript state.
- Repudiation: sequenced owner-only events record security mutations and denials, but H-04 can make a terminal transcript event untruthful about continuing collection.
- Information disclosure: projections and logs are minimized/redacted; H-04 can extend collection after the durable/UI state says capture is inactive.
- Denial of service: file, output, descriptor-tree depth/entry, subprocess, and lock bounds exist; owning-UID host exhaustion remains outside the claimed boundary.
- Elevation of privilege: ownership, named reviewer grants, allowlisted validators, and lock-time authorization remain enforced; no new bypass was found.

## Auth / Authz

The policy remains deny by default. Identity comes from the OS UID and supplementary groups; labels are display metadata. Exact UID bindings take precedence over group bindings, ambiguous or duplicate effective roles fail closed, LocalOperator operations require ownership, and Reviewer mutations require the corresponding named grant. Foreign-owner projections suppress workspace, prompt, audit, tmux, transcript, evidence, validator artifact, and raw summary details.

Protected commits use lock-time reauthorization where the repository supports it. Launch failure compensation intentionally terminalizes an already-authorized operation even if the original operation reports a persistence error; this is a fail-safe internal transition rather than a new caller grant. Corrupt-state recovery still rejects non-LocalOperator/foreign-UID callers before repository recovery and checks the recovered immutable owner again.

No authorization bypass was found in H-01/H-02/H-03 remediation. H-04 is a data-lifecycle truthfulness failure after an authorized transcript operation, not a missing grant.

## Validation and Independent Results

### Refreshed official evidence

- JUnit: 488 tests, 488 passed, zero failures/errors/skips; SHA-256 `0dfdb5a419b759ed9f77d78d810b7d68cd62ae126545d4888a154cb7b58b7369`.
- Cobertura: 4,064/4,519 lines (89.93%) and 1,162/1,434 branches (81.03%); SHA-256 `c85cffadbc74edb1cd09b16bc7f6861f7191e0b8772217ee2a52d1071306a07e`.
- Required risk modules remain 100% branch covered: authorization, transitions, redaction, and session entry each report branch rate `1`.

### Fresh commands

- Exact new boundary files: `12 passed in 0.34s` for `test_commit_reconciliation.py` plus `test_story_validator_descriptor_boundary.py`.
- Broader security/failure set: `288 passed in 1.67s` across security, authorization, watcher/validator, application services, filesystem, transcript, and both new boundary files.
- Strict planning-security audit: pass.
- `pip check`: no broken requirements; pytest runtime independently reports 9.1.1.
- Fresh resolved `pip-audit`: exit 0, 11 reported dependencies, zero known vulnerabilities.
- Fresh expanded `detect-secrets 1.5.0` scan over source, tests, changed story validator, package metadata, F0001 planning, architecture, schemas, and security: exit 0, `results: {}`.
- Fresh Bandit rerun over engine source plus the changed story validator reproduced 16 Low, 0 Medium, 0 High, no errors/skips/`nosec`.

### Bounded probes

The exact pre-/post-publication launch and transcript tests, and the symlink-swap/metadata/FIFO validator tests, all pass. A separate compensation probe then exercised a case absent from those tests:

```text
Transcript pipe configure: succeeded
TranscriptEnabled commit: failed before publication
Compensating pipe disable: raised
durable transcript status: Disabled
pipe active: True
```

This follows the current `enable` exception path and establishes H-04. The exception still reaches the caller, but durable/UI state no longer truthfully represents collection.

A hard-link alias probe replaced the story entry after the parent opened the feature root and was accepted as a regular in-root file with link count 2. This does not reopen H-02 under the documented owning-UID boundary: unlike a symlink, the opened inode has a real link below the governed root and no unowned/cross-UID content is followed. Requiring single-link story inodes is retained as Low provenance hardening.

## H-01/H-02/H-03 Closure Matrix

| Cycle-1 finding | Cycle-2 result | Independent basis |
|---|---|---|
| H-01 launch can publish `Active`, kill tmux, and lose terminal audit | **Closed** | `application/runs.py:131-154, 325-393` recovers the state image matching the contiguous event suffix before compensation, kills the session, and commits `LaunchFailed` from the authoritative revision. Real pre-publication and post-`os.replace`/pre-directory-`fsync` tests leave `Failed`, no tmux session, and the correct two- or three-event sequence. |
| H-02 child validator follows a descendant replacement outside the feature | **Closed for stated symlink/TOCTOU boundary** | `infrastructure/watcher.py:410-470` passes the inherited feature FD explicitly. `validate-stories.py:44-104, 383-450` walks relative to open descriptors, uses `O_NOFOLLOW|O_NONBLOCK`, rejects unsafe owner/mode/type, caps depth/entries/file size, and validates stable double-read bytes. The exact real-subprocess symlink swap now fails nonzero. |
| H-03 `Completed` publication can restart capture from stale `Active` | **Closed** | `application/transcripts.py:45-104, 162-282` recovers authoritative state before pipe action. It restores only a provably `Active` pre-publication state and never restarts a recovered `Completed`/`Failed` state. Exact pre-/post-publication completion tests prove the pipe remains stopped for published `Completed`. |
| Adjacent transcript enable/failure compensation | **Open — H-04 High** | Terminal/non-Active recovery calls `disable` but suppresses its failure; the probe above leaves `Disabled` plus an active pipe. The same assumption exists in launch-with-transcript and observed-failure completion paths. |

## Audit / Logging

Events remain schema-validated, sequenced, bounded, sanitized, and owner-only. Authorization denials, launch/attach, validators, gates, transcript lifecycle, and recovery are represented. Process output, validator summaries, gate reasons, transcript failure categories, and foreign-owner views are redacted or minimized.

H-01 now records whether `RunLaunched` was published and adds `LaunchFailed` from the recovered revision, including the compensated event when applicable. H-03 no longer records completion while restarting capture.

H-04 still permits `Disabled` or `TranscriptFailed` to remain authoritative while the tmux pipe is active after a swallowed disable failure. The caller receives an exception, but later status and audit consumers cannot determine that collection continued. The JSONL stream also remains non-cryptographic against another process already acting as the owning UID; that accepted limitation remains Low.

## Secrets / Config

Provider authentication remains native to Codex or Claude Code. F0001 does not inspect or persist provider auth files, keychains, API-key variables, shell history, tokens, passwords, or an application encryption key. This review did not inspect credential files. Launch forwards only approved environment names through an owner-only descriptor.

Transcript capture remains opt-in and redacts before durable transcript bytes. H-04 does not bypass redaction, but redaction does not authorize continued collection after durable status says capture is inactive. The raw and independently expanded secret scans are clean. The finite redaction format corpus remains a Low maintenance recommendation.

## Scan Disposition

| Class | Ran | Result / finding summary | Artifact or waiver |
|---|---:|---|---|
| dependency | yes | Clean resolved set recorded 2026-07-14; pytest 9.1.1; zero known vulnerabilities; fresh rerun agrees | `artifacts/security/dependency-audit.json`, SHA-256 `8498dee8525ab7f7ca2090e1d7c8ad027e203d89955a29f70178a68377f856f6` |
| secrets | yes | Generated 2026-07-14T21:03:22Z; clean expanded scope, `results: {}`; fresh broader rerun agrees | `artifacts/security/secrets-scan.json`, SHA-256 `074a3b727d06fc514aca0bf1934c71b44ea622d6596f78456316bada9d7fcaa2` |
| sast | yes | Generated 2026-07-14T21:03:22Z; 6,925 LOC; 16 Low scanner findings, 0 Medium/High; 15 High-confidence and 1 Medium-confidence; manual review escalates compensation context to H-04 | `artifacts/security/bandit-sast.json`, SHA-256 `425bd68ec37545bc44d56ba524ca196a6087f951f6c8387668ac95caca09d80a` |
| dast | no | **Waiver approved for this exact cycle-2 architecture:** no listener, HTTP route/client, URL fetcher, daemon, or remote dynamic target exists | Architect waiver in `evidence-manifest.json`, approved 2026-07-14; independently confirmed by Security Reviewer |

Any future listener, remote multi-user service, URL fetcher, webhook, database, plugin download, application-managed credential, or cross-UID daemon invalidates the DAST waiver and requires a new threat model.

### CVE-2025-71176

[NVD CVE-2025-71176](https://nvd.nist.gov/vuln/detail/CVE-2025-71176) identifies insecure pytest temporary-directory creation through version 9.0.2 on Unix. The [pytest 9.0.3 release](https://github.com/pytest-dev/pytest/releases/tag/9.0.3) records the fix. The package and assembly contracts require `pytest>=9.0.3,<10`; both the refreshed suite and audit resolve 9.1.1. The initial pytest 8 environment remains correctly rejected, and the CVE reconciliation is closed.

### All 16 Bandit findings

| # | Location | ID | Security disposition |
|---:|---|---|---|
| 1 | `application/gates.py:172` | B110 | Best-effort validator-cancellation audit; the primary validator failure remains raised and no successful validator fact is granted. Accepted scanner Low. |
| 2 | `application/queries.py:65` | B110 | Denial-audit failure does not expose the denied projection. Accepted scanner Low. |
| 3 | `application/runs.py:85` | B110 | Denial-audit failure preserves authorization denial. Accepted scanner Low. |
| 4 | `application/runs.py:440` | B110 | H-04 context: launch-with-transcript can suppress failed pipe disable after a non-Active authoritative outcome. |
| 5 | `application/transcripts.py:65` | B110 | Failed restoration leaves durable `Active` with preview blocked; later status reconciliation fails closed. Accepted scanner Low. |
| 6 | `application/transcripts.py:73` | B110 | H-04 root: failed disable is suppressed for a terminal/non-Active recovered state. |
| 7 | `application/transcripts.py:141` | B110 | H-04 context: failed cleanup after an ambiguous failed-enable audit can leave external state unverified. |
| 8 | `application/transcripts.py:186` | B110 | H-04 context: observed `Failed` can be committed after pipe disable failed. |
| 9 | `infrastructure/process.py:6` | B404 | Intentional subprocess boundary. Accepted scanner Low. |
| 10 | `infrastructure/process.py:71` | B603 | Typed NUL-free argv, bounded approved environment names, `shell=False`, timeout/output limits. Accepted scanner Low. |
| 11 | `infrastructure/process.py:80` | B101 | Internal post-`Popen` pipe invariant; optimized-mode removal fails rather than expanding command/access authority. Accepted scanner Low. |
| 12 | `infrastructure/tmux.py:7` | B404 | Intentional native tmux adapter. Accepted scanner Low. |
| 13 | `infrastructure/tmux.py:86` | B603 | Fixed validated session argv and `shell=False`; no injection path. Accepted scanner Low. |
| 14 | `infrastructure/transcript.py:241` | B110 | Pipe configuration failure remains raised; secondary status-write failure cannot create a success fact. Accepted scanner Low. |
| 15 | `infrastructure/transcript.py:267` | B110 | Related H-04 context: adapter disable raises, but failure to restore its sidecar is secondary; application callers must not suppress the primary disable failure. |
| 16 | `presentation/session_entry.py:132` | B606 | `execvpe` follows descriptor schema/owner/mode/run/executable/cwd validation and fixed environment filtering. Accepted scanner Low. |

Eleven scanner findings are benign in the current design. Findings 4, 6-8, and 15 expose or surround H-04; Bandit's uniform Low rating does not account for transcript collection consent and durable-state authority.

## Security Dimensions

| Dimension | Result | Notes |
|---|---|---|
| Injection resistance | Pass | Typed argv, `shell=False`, quoted intentional tmux command seam, fixed validators, bounded identifiers and output. |
| Authentication robustness | Pass / local applicability | OS UID is the authentication boundary; provider authentication remains provider-native. |
| Access control | Pass | Ownership, explicit binding/grants, lock-time checks, minimized projection, owner-only recovery. |
| Sensitive-data exposure | **Issue** | H-04 can continue redacted collection after durable state says inactive. |
| Security configuration | Pass | Owner-only defaults; no CORS/cookie/TLS/listener target. |
| Component risk | Pass with Low hardening | Clean resolved audit; release dependency hash lock remains recommended. |
| Observability/auditability | **Issue** | H-04 can make a terminal transcript event/state incomplete or misleading. |
| Secrets/key management | Pass | No application credential store or committed secret found. |
| Abuse/resilience | Pass with residual | File/output/tree/time/lock bounds; owning-UID host exhaustion outside boundary. |
| Error/failure safety | **Issue** | H-01/H-03 ambiguity fixed, but failed transcript disable is still silently tolerated. |

## OWASP Top 10 Coverage

| Category | Status | Notes |
|---|---|---|
| A01 Broken Access Control | OK | OS identity, ownership, deny-by-default bindings, named grants, lock-time authorization, minimized projections. |
| A02 Cryptographic Failures | OK / limited applicability | No network credential/transport or custom crypto; owner-only local storage. |
| A03 Injection | OK | Typed argv and descriptor execution; no SQL/template/command injection path found. |
| A04 Insecure Design | Issue | H-04 violates the declared transcript terminal-state/privacy invariant under compensation failure. |
| A05 Security Misconfiguration | OK | No listener/root bypass/remote policy; owner-only defaults and fixed environment forwarding. |
| A06 Vulnerable / Outdated Components | OK with Low recommendation | Resolved audit clean and pytest CVE closed; deterministic hash locking remains open. |
| A07 Identification & Authentication | OK / limited applicability | OS identity is authoritative; ambiguous roles deny; provider auth remains native. |
| A08 Software & Data Integrity | Issue | H-04 permits external pipe state to diverge from durable transcript state. |
| A09 Security Logging & Monitoring | Issue | Terminal transcript state may not disclose continued collection after disable failure. |
| A10 Server-Side Request Forgery | N/A | No outbound URL request or server-side fetch surface. |

## Findings

Open findings: Critical 0; High 1; Medium 0; Low 4.

### High — H-04: failed transcript compensation can leave capture active behind Disabled/Failed state

- Severity: High.
- Location: `engine/src/nebula_agents/application/transcripts.py:45-75, 135-142, 183-201`; `engine/src/nebula_agents/application/runs.py:425-442`; adapter behavior at `engine/src/nebula_agents/infrastructure/transcript.py:245-269`.
- What: after recovering a non-Active/terminal durable state, transcript compensation calls `disable` and suppresses any failure. Launch-with-transcript and observed-failure completion contain the same assumption.
- Why it matters: tmux can continue sending later terminal output through the redact-before-write worker while the registry, UI, and audit say collection is `Disabled` or `Failed`. Redaction lowers plaintext exposure but does not authorize invisible continued collection.
- Exploit/fault scenario: configure capture successfully; fail the `TranscriptEnabled` commit before publication; then fail tmux pipe disable. The independent probe produced `durable Disabled pipe_active True`. A later command or credential prompt can therefore be collected after the operator believes capture never enabled. The required compound local failure and continued redaction keep this below Critical; the confidentiality/consent and audit impact remains High.
- Remediation: never swallow a disable failure when the authoritative state is non-Active. Verify pipe liveness after compensation. If it cannot be stopped, persist a truthful `Active`/explicit unresolved-compensation state from the authoritative revision, or fail safely by terminating the owning tmux session; do not expose a terminal transcript fact until capture is verified inactive. Cover TranscriptService enable, observed-failure completion, and RunService launch-with-transcript with exact commit-failure plus disable-failure/liveness tests.
- Owner: Backend Engineer with Architect and Security Reviewer review.
- Target: before the next G3 Security rerun, no later than 2026-07-15.
- Follow-up: `F0001-G3-H04`.

### Low recommendations

- [low] Compatible dependency ranges and a temporary resolved audit file are not a durable reviewed hash lock; publish hash-locked release/CI constraints — owner: DevOps; follow-up: deferred-no-followup
- [low] An already-compromised owning-UID process can rewrite local JSONL without cryptographic evidence; add hash chaining, signed export, or an OS-protected sink if accountability expands — owner: Security Reviewer; follow-up: deferred-no-followup
- [low] A future credential format can exceed finite redaction patterns; maintain provider-format, split-chunk, and private-key regression corpora — owner: Security Reviewer; follow-up: deferred-no-followup
- [low] Descriptor story validation accepts current-UID safe-mode multi-link regular files; require `st_nlink == 1` if provenance must exclude hard-link aliases across the governed root — owner: Product Manager validator owner; follow-up: deferred-no-followup

No new Critical or Medium finding was established. H-01, H-02, and H-03 are closed; H-04 is a new blocking adjacent failure-safety finding.

## Recommendation Disposition

| Item | Disposition | G3 impact |
|---|---|---|
| H-01 launch publication reconciliation | Mitigated and independently verified | Closed |
| H-02 descriptor-bound story validation | Mitigated for the stated symlink/TOCTOU boundary and independently verified | Closed |
| H-03 terminal completion publication | Mitigated and independently verified | Closed |
| H-04 failed pipe compensation | Must remediate and independently retest | **Blocks G3** |
| Deterministic dependency lock | Retain as Low release hardening | Non-blocking after H-04 |
| Cryptographic/external audit evidence | Retain within accepted owning-UID residual | Non-blocking after H-04 |
| Redaction-corpus maintenance | Ongoing | Non-blocking after H-04 |
| Single-link story provenance | Optional within current same-UID boundary | Non-blocking after H-04 |
| Architect DAST no-target waiver | Approved for exact current architecture | Non-blocking; invalidate on any network target |

## Result

`REQUEST CHANGES`

G3 Security cycle 2 does not pass. Remediate H-04, add the compound compensation/liveness regressions, refresh affected test/coverage/SAST evidence, and request another independent Security Reviewer pass.

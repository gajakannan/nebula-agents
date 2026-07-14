---
template: security-review
version: 2.0
feature_id: F0001
run_id: 2026-07-14-b885d64c
review_cycle: 3
---

# Security Review Report — F0001-tmux-native-agent-cockpit run 2026-07-14-b885d64c, final H-04 follow-up (archived cycle 3)

## Result

**REQUEST CHANGES**

Open findings: Critical 0; High 2; Medium 0; Low 4.

H-01, H-02, and H-03 remain closed. The ordinary H-04 remediation paths are materially improved and the 14-case compound reconciliation lane passes, but the claimed invariant is not complete. A pre-publication failure of the compensating `Active` commit leaves durable `Disabled` with live capture, and the production tmux liveness adapter converts timeout/error into `False`. Either condition can leave a durable terminal/non-active transcript projection while capture is possibly active. Both High findings block G3 and release.

## Scope and Boundary

- Feature ID: F0001
- Run ID: `2026-07-14-b885d64c`
- Review cycle: 3, independent final Security follow-up
- Date: 2026-07-14
- Deployment: local Python CLI/TUI plus native tmux/provider processes; no HTTP listener, database, remote API, URL fetcher, daemon, or application credential store
- Accepted trust boundary: the owning OS UID. F0001 does not claim hostile same-UID isolation, but it does claim fail-closed lifecycle, authorization, validator, transcript-consent, and audit behavior when bounded repository/tmux operations fail.

The exact final changed-file inventory is `artifacts/diffs/changed-files.txt`, SHA-256 `8245ce5896827bb9fc84559d8d9752ec8b075372211dd650e7626c645376ec1b`. The worktree is not represented by a single immutable Git commit; the inventory, raw evidence, and source hashes below define this review boundary.

The cycle archives were treated as finding ledgers only and were not edited:

| Archive | SHA-256 |
|---|---|
| `security-review-report-cycle-1.md` | `9ed763cd55549ced503697ff9fa25e1a94f923b4bfd2a6c83daec3ff43b3c6f2` |
| `security-review-report-cycle-2.md` | `f41fb619f6af4e976c389f72b03257ce74c27631c5d4e0ae68ecdf74779c1e57` |

Final reviewed source/test hashes:

| Path | SHA-256 |
|---|---|
| `application/runs.py` | `c2e5442b60c64aa18156bff43f19ce67cfd11224e3b9a0642078e18648ee1083` |
| `application/transcripts.py` | `acffd4897d86b61aaa5416819cb72b0c5ae7e18217f38ba422b9c3544def26a2` |
| `application/ports.py` | `4aff885553a4bba4c6ee344bbd0695642b384d516371e93645b5cb4c8cf1f19a` |
| `infrastructure/tmux.py` | `7a86a6e67473727318001918469914802fa70977270451984ccb5826e72a332f` |
| `infrastructure/transcript.py` | `eb56447bf1936e5fcb9512d49e20153349bda276544ed3bb776bb9c7a749e807` |
| `test_commit_reconciliation.py` | `45d90cd4663f76a1617689bdbfe4e7271127ea4f1b0190b5a832a5776613657f` |
| `test_story_validator_descriptor_boundary.py` | `28f416957e0a8f05735ff220b5a40b9c795d2c2aa9d8228ad94ee777dfd48634` |
| `test_application_services.py` | `4f46529c622961f7f72944ab3bc75e44d0f56dc206cf625b2438ccc3d95ad1c3` |

## Threat Model

| Subject / trigger | Asset / operation | Required property | Final disposition |
|---|---|---|---|
| LocalOperator | owned run and transcript lifecycle | OS identity, ownership, named authorization, current revision | Pass |
| Reviewer | foreign run read/probe/validator | deny by default, minimized projection, explicit grants | Pass |
| Filesystem/power fault | event/state publication and recovery | authoritative recovery before external compensation | H-01/H-03 pass; H-04R open |
| Workspace content | feature/story validator input | pinned descriptor, no-follow, bounded stable bytes | H-02 pass |
| tmux/worker fault | transcript pipe and terminal facts | terminal state only after proven inactive capture | H-05 open |
| Provider/tmux command input | executable, descriptor, cwd, argv/env | validated fixed boundary, no shell injection | Pass |

STRIDE disposition:

- Spoofing: OS-derived UID/group identity and ambiguous-role denial remain effective.
- Tampering: event/state recovery and descriptor-bound validation remain sound for H-01/H-02/H-03; H-04R can leave the durable transcript fact stale when the truthful compensation cannot publish.
- Repudiation: sequenced owner-only events remain present, but H-04R can omit `TranscriptEnabled` while capture is live and H-05 can permit an untruthful terminal event.
- Information disclosure: projections and logs are minimized/redacted, but continued transcript collection behind `Disabled`/`Failed`/`Completed` is a consent and exposure failure even when redaction remains active.
- Denial of service: subprocess, output, file, tree, lock, and timeout bounds remain; owning-UID host exhaustion is outside the accepted boundary.
- Elevation of privilege: ownership, grants, allowlisted validators, and lock-time authorization remain enforced; no new privilege bypass was found.

## Auth / Authz

Policy remains deny by default. Identity is OS-derived; display labels are not authority. Exact UID bindings take precedence, ambiguous effective roles fail closed, LocalOperator mutations require ownership, and Reviewer mutations require named grants. Foreign-owner projections suppress workspace, prompt, audit, tmux, transcript, evidence, validator artifact, and raw summary detail.

The compensating `TranscriptEnabled` path correctly uses `commit_authorized(... Action.CONFIGURE_TRANSCRIPT)` and emits only sanitized path/operation metadata. Its post-publication ambiguity recovery is authorized and truthful. H-04R is not an authorization bypass: it is the failure-safety case where that authorized compensating commit fails before publication and no verified external stop follows.

## Independent Validation

### Official raw evidence

- JUnit: 496 tests, 496 passed, zero failures/errors/skips/xfails; 73,899 bytes; SHA-256 `fc99c11dcf9a8e6af089050e9d9ff1a4761bf8cc8431203e282ffb494eb2c3f4`.
- Cobertura: 4,126/4,572 lines (90.24%) and 1,180/1,454 branches (81.16%); 209,925 bytes; SHA-256 `c23f2747d9fd23fd7631ad3b758e5725089f9abfd00e46c39620c2533d66b99e`.
- Authorization, transitions, redaction, and session-entry risk modules each retain 100% branch coverage.

### Fresh independent commands

- Full suite: `496 passed in 2.54s`.
- Exact commit-reconciliation plus descriptor-bound story files: `20 passed in 0.51s`; the commit file represents 14 compound H-01/H-03/H-04 cases and the descriptor file represents six H-02 cases.
- Strict planning-security audit: pass.
- Fresh resolved `pip-audit`: exit 0; 11 dependencies; zero known vulnerabilities.
- Fresh Bandit: reproduced 13 Low, 0 Medium, 0 High; 7,093 LOC; no errors, skips, or `nosec`; 12 High-confidence and one Medium-confidence finding.
- Refreshed expanded `detect-secrets 1.5.0` artifact: `results: {}`.

### H-04 adjacent-path matrix

| Required path | Independent result | Disposition |
|---|---|---|
| `TranscriptService.enable`: pre-publication commit failure + disable failure | Ordinary fallback writes authorized conservative `Active`, emits `TranscriptEnabled` with `disable-unverified`/`possibly-active`, and raises `STATE_IO` | Pass only while compensation commit publishes |
| Partial configure failure + disable failure | Conservative `Active`; no false `Failed` publication; `STATE_IO` | Pass only while compensation commit publishes |
| `RunService` launch-with-transcript equivalents | Provider run remains `Active`; transcript becomes conservative `Active`; `STATE_IO`; no false terminal transcript fact | Pass only while compensation commit publishes |
| Observed-`Failed` completion | Failed disable leaves original durable `Active`; no `TranscriptFailed` event | Pass |
| Owner status reconciliation | Failed disable leaves original durable `Active`; no terminal event | Pass |
| Adapter absent liveness method | Treated as unverified; conservative `Active` + `STATE_IO` | Pass |
| Fake liveness method raises | `stop_and_verify_capture` treats the exception as unverified | Application helper passes |
| Production tmux liveness command times out/errors | `TmuxAdapter.pipe_active` returns `False` | **Fail — H-05** |
| Compensating `Active` commit faults after publication | Recovery finds durable `Active`; event is present; caller receives stable `STATE_IO` | Pass |
| Compensating `Active` commit faults before publication | Recovery remains `Disabled` while pipe is live; no `TranscriptEnabled` event | **Fail — H-04R** |
| Original `TranscriptEnabled` faults after publication | Recovered `Active` is authoritative; no disable attempted | Pass |

### Exact independent probes

The cycle-2 original shape now succeeds when the compensating event publishes: configure activates the pipe, the original enable commit fails before publication, disable fails, the fallback commits `Active`, and the caller receives `STATE_IO`.

The nested pre-publication probe used the real `FilesystemRunRepository` and production `TranscriptService` behind a two-stage fault wrapper:

```text
original TranscriptEnabled commit: failed before publication
disable: failed; pipe remained active
compensating Active commit: failed before publication
error: STATE_IO
operation: transcript-enable-commit-active-compensation
durable transcript: Disabled
pipe active: True
events: LaunchRequested, RunLaunched
```

The after-publication control produced durable `Active`, a `TranscriptEnabled` event, live pipe, and stable `STATE_IO`; that ambiguity reconciliation is correct.

A separate production `TmuxAdapter` probe supplied bounded command results directly:

```text
display-message timeout (exit 124, timed_out=True) -> pipe_active False
display-message generic error (exit 1)             -> pipe_active False
```

`stop_and_verify_capture` interprets those values as a successful liveness proof when `disable` returned normally. The real adapter therefore does not preserve the helper's intended distinction between inactive and probe unavailable.

## Prior Finding Closure

| Finding | Final result | Basis |
|---|---|---|
| H-01: published `Active` launch can be followed by tmux kill without terminal audit | **Closed** | Authoritative recovery precedes session compensation; real pre-/post-publication tests leave `Failed`, no tmux session, and correct `LaunchFailed` sequencing. |
| H-02: child validator follows descendant replacement outside governed feature | **Closed for stated symlink/TOCTOU boundary** | Inherited root FD, descriptor-relative `O_NOFOLLOW` walk, stable metadata/double-read bytes, owner/mode/type/size/depth/entry limits; real swap tests fail closed. |
| H-03: published `Completed` can restart capture from stale `Active` | **Closed** | Completion ambiguity recovery restores only a recovered `Active`; published `Completed`/`Failed` never restarts the pipe. |
| H-04: failed disable hidden behind non-Active transcript state | **Partially remediated; H-04R open** | Ordinary and post-publication compensation cases are correct. A pre-publication failure of the compensating `Active` commit reproduces `Disabled` plus live pipe. |
| H-05: production liveness failure is reported as inactive | **Open — High** | `TmuxAdapter.pipe_active` reduces all nonzero/timeout outcomes to `False`, allowing terminal publication without proof. |

## Findings

### High — H-04R: pre-publication failure of compensating `Active` recreates hidden capture

- Location: `engine/src/nebula_agents/application/runs.py:201-256`; `engine/src/nebula_agents/application/transcripts.py:76-93, 175-194`; analogous launch paths at `application/runs.py:552-569`.
- What: after original enable publication fails and capture cannot be verified stopped, `persist_truthful_capture_active` attempts an authorized compensating `TranscriptEnabled`. If that commit fails before publication, recovery proves the current durable fact is still non-Active and raises `STATE_IO`, but no further external stop/kill is attempted.
- Impact: durable/UI/audit state can remain `Disabled` (or another recovered non-Active state) while tmux continues transcript collection. Later consumers do not have the conservative `Active` fact or event that the remediation relies on.
- Reproduction: exact output is recorded above. The condition is plausible during persistent state I/O failure because both the original and fallback writes share the same repository while tmux compensation can fail independently.
- Required fix: after a compensating `Active` fact is proven not published, force and verify capture inactivity through a bounded independent fallback (for example, retry disable and/or terminate the owned session and verify absence). Do not return with a durable non-Active fact and possibly-live capture. Add direct and launch tests for pre-publication fallback-commit failure, authorization denial at the fallback lock, and unavailable persistence recovery.
- Owner: Backend Developer. Release blocking.

### High — H-05: tmux liveness timeout/error is a false inactive proof

- Location: `engine/src/nebula_agents/infrastructure/tmux.py:98-107`; consumed by `infrastructure/transcript.py:280-282`; terminal gates at `application/runs.py:183-198`, `application/transcripts.py:137-151, 218-245`, and `application/runs.py:520-569, 649-654`.
- What: `pipe_active` returns `result.exit_code == 0 and stdout == "1"`. Timeout, missing target, malformed output, and generic command error all collapse to `False` instead of a probe error/unavailable result.
- Impact: after `disable` returns, a failed liveness command satisfies `verified_stopped`; services may publish `Failed`/`Completed` even though inactivity was never observed. This affects direct enable/complete, launch-with-transcript, and owner status reconciliation through the real adapter.
- Reproduction: bounded fake-runner calls produced `False` for exit 124 with `timed_out=True` and for exit 1.
- Required fix: make the adapter distinguish inactive (`exit 0` and exact `0`) from active (`exit 0` and exact `1`) and unavailable/error (timeout, nonzero, empty/malformed output). Propagate unavailable as an exception or typed tri-state so `stop_and_verify_capture` persists/retains conservative `Active` and raises `STATE_IO`. If a missing session is accepted as inactive, prove session absence separately. Add adapter tests and real-service tests for timeout, generic nonzero, malformed output, and inactive/active controls.
- Owner: Backend Developer. Release blocking.

### Low — deterministic release dependency locking

The resolved environment is clean, but compatible ranges do not provide a reproducible hash-locked release graph. Generate and verify a release lock with hashes while preserving supported Python/platform variants.

### Low — cryptographic audit tamper evidence

Runtime events are sequenced, owner-only, schema-validated, and recoverable, but another process already acting as the owning UID can rewrite history. If audit non-repudiation beyond the accepted UID boundary becomes required, add chained signatures or ship to an append-only sink.

### Low — maintained redaction adversarial corpus

Streaming redaction covers the current tested formats and split-chunk cases. Maintain a versioned adversarial corpus as provider output formats evolve.

### Low — single-link story provenance hardening

Descriptor-bound story reads reject symlink replacement and unsafe metadata but permit a regular hard-linked inode with an additional alias. Under the owning-UID boundary the opened inode is genuinely below the governed root; rejecting `st_nlink != 1` remains defense-in-depth provenance hardening.

## Audit / Logging

Events remain schema-validated, sequenced, bounded, sanitized, and owner-only. Authorization denials, launch/attach, validators, gates, transcripts, and recovery are represented. Process output, validator summaries, transcript failure categories, and foreign projections remain minimized.

Ordinary H-04 fallback emits an authorized `TranscriptEnabled` with `compensation=disable-unverified`, `commit_outcome=compensating-active`, `external_capture=possibly-active`, and a bounded operation name. H-04R demonstrates why that event cannot be the sole fail-safe: if it cannot publish, the caller alone receives `STATE_IO` and later durable consumers remain misled. H-05 can additionally permit a terminal event based on a false-negative probe.

## Secrets / Config

Provider authentication remains native to Codex/Claude. F0001 does not inspect or persist provider credential files, API-key variables, shell history, tokens, passwords, or an application encryption key. Launch forwards only allowlisted environment names through an owner-only descriptor. Transcript capture remains opt-in and redacts before durable transcript bytes; redaction does not authorize collection after status says inactive.

The raw expanded secret scan is clean. No CORS, cookie, TLS, database, web listener, or remote service configuration is applicable to this local architecture.

## Scan Accountability

| Class | Ran | Result | Artifact / waiver |
|---|---:|---|---|
| Dependency | yes | Clean; 11 resolved dependencies; zero known vulnerabilities; fresh rerun agrees | `artifacts/security/dependency-audit.json`, SHA-256 `8498dee8525ab7f7ca2090e1d7c8ad027e203d89955a29f70178a68377f856f6` |
| Secrets | yes | `detect-secrets 1.5.0`; expanded scope; `results: {}` | `artifacts/security/secrets-scan.json`, SHA-256 `d71aba4912403c83f9180f4aea6fc9d0bf7a042eba924bbe8048a9d1c2af42ad` |
| SAST | yes | 13 Low, 0 Medium, 0 High; 7,093 LOC; fresh rerun agrees; manual review found H-04R/H-05 | `artifacts/security/bandit-sast.json`, SHA-256 `301150a19ec88ad4edd8614583548d4a9c0a2b91443cdca541af0b8fe493b8af` |
| DAST | no | **Waiver confirmed for this snapshot:** no listener, HTTP route/client, URL fetcher, daemon, or remote target exists | Architect waiver in `evidence-manifest.json`, approved 2026-07-14; independently confirmed in cycle 3 |

Any future listener, remote multi-user service, webhook, URL fetcher, database, plugin download, application-managed credential, or cross-UID daemon invalidates the DAST waiver.

### CVE-2025-71176

[NVD CVE-2025-71176](https://nvd.nist.gov/vuln/detail/CVE-2025-71176) identifies pytest through 9.0.2 on Unix as affected by insecure temporary-directory creation. The [pytest 9.0.3 release](https://github.com/pytest-dev/pytest/releases/tag/9.0.3) records the fix. `engine/pyproject.toml` requires `pytest>=9.0.3,<10`; the final suite and audit resolve pytest 9.1.1. This CVE is closed.

### All final Bandit findings

| # | Location | ID | Disposition |
|---:|---|---|---|
| 1 | `application/gates.py:172` | B110 | Best-effort cancellation audit; primary validator failure remains raised. Accepted Low. |
| 2 | `application/queries.py:65` | B110 | Denial-audit failure never grants the denied projection. Accepted Low. |
| 3 | `application/runs.py:85` | B110 | Denial-audit failure preserves denial. Accepted Low. |
| 4 | `application/transcripts.py:71` | B110 | Failed pipe restoration leaves durable `Active`; no false terminal state. Accepted Low. |
| 5 | `application/transcripts.py:169` | B110 | Preserves original configure failure after terminal ambiguity reconciliation; pipe was verified stopped at the application seam, subject to H-05. Accepted scanner Low; H-05 is separately High. |
| 6 | `infrastructure/process.py:6` | B404 | Intentional bounded subprocess boundary. Accepted Low. |
| 7 | `infrastructure/process.py:71` | B603 | Typed NUL-free argv, approved env names, `shell=False`, timeout/output limits. Accepted Low. |
| 8 | `infrastructure/process.py:80` | B101 | Internal post-`Popen` pipe invariant; removal cannot expand authority. Accepted Low. |
| 9 | `infrastructure/tmux.py:7` | B404 | Intentional native tmux adapter. Accepted Low. |
| 10 | `infrastructure/tmux.py:86` | B603 | Validated fixed attach argv, filtered environment, `shell=False`. Accepted Low. |
| 11 | `infrastructure/transcript.py:241` | B110 | Primary configure failure remains raised; status-write failure cannot create success. Accepted Low. |
| 12 | `infrastructure/transcript.py:267` | B110 | Primary disable failure remains raised; secondary sidecar restoration failure cannot create success. Accepted Low. |
| 13 | `presentation/session_entry.py:132` | B606 | Descriptor schema/owner/mode/executable/cwd checks plus fixed env filtering precede `execvpe`. Accepted Low. |

## Security Dimensions

| Dimension | Result | Notes |
|---|---|---|
| Injection resistance | Pass | Typed argv, `shell=False`, quoted intentional tmux seam, fixed validators, bounded identifiers/output. |
| Authentication robustness | Pass / local applicability | OS UID is authoritative; provider authentication is provider-native. |
| Access control | Pass | Ownership, explicit bindings/grants, lock-time checks, minimized projections, owner-only recovery. |
| Sensitive-data exposure | **Fail** | H-04R/H-05 can continue capture behind a non-Active durable fact. |
| Security configuration | Pass | Owner-only defaults; no listener/CORS/cookie/TLS target. |
| Component risk | Pass with Low hardening | Resolved audit clean; hash locking recommended. |
| Observability/auditability | **Fail** | Missing compensation event or false terminal event can misrepresent live collection. |
| Secrets/key management | Pass | No application secret store or detected committed secret. |
| Abuse/resilience | Pass with residual | File/output/tree/time/lock bounds; owning-UID host exhaustion outside boundary. |
| Error/failure safety | **Fail** | H-04R and H-05 violate the transcript terminal-state invariant. |

## OWASP Top 10

| Category | Status | Notes |
|---|---|---|
| A01 Broken Access Control | OK | OS identity, ownership, deny-by-default bindings, grants, lock-time authorization, minimized projections. |
| A02 Cryptographic Failures | OK / limited applicability | No network credential/transport or custom crypto; local owner-only storage. |
| A03 Injection | OK | Typed argv, descriptor execution, no SQL/template/request injection path found. |
| A04 Insecure Design | **Issue** | Terminal transcript truth still depends on fallible persistence and a false-negative liveness adapter. |
| A05 Security Misconfiguration | OK | No listener/root bypass/remote policy; owner-only defaults and fixed environment forwarding. |
| A06 Vulnerable Components | OK with Low recommendation | Clean resolved audit and fixed pytest floor; deterministic lock remains recommended. |
| A07 Identification & Authentication | OK / limited applicability | OS identity authoritative; ambiguous roles deny; provider auth remains native. |
| A08 Software & Data Integrity | **Issue** | External pipe state can diverge from durable transcript state in H-04R/H-05. |
| A09 Logging & Monitoring | **Issue** | Durable event stream can omit active collection or assert a false terminal state. |
| A10 SSRF | N/A | No outbound URL fetch surface. |

## Required Closure

Security must independently rerun before G3 can pass. Closure requires:

1. H-04R tests proving that failure/denial/unavailability of the compensating `Active` commit cannot return with non-Active durable state and possibly-live capture, for direct enable, partial configure, and launch-with-transcript.
2. H-05 typed/exceptional liveness behavior for timeout, generic nonzero, malformed/empty output, inactive `0`, active `1`, and a separately proven missing-session case.
3. End-to-end service tests through the production tmux adapter boundary proving no `Disabled`, `Failed`, or `Completed` fact/event is published without verified inactivity.
4. Refreshed JUnit/Cobertura, Bandit, dependency, and secrets evidence with manifest hashes/counts reconciled.

No Critical finding is open. Both High findings block approval; therefore `PASS` and `PASS WITH RECOMMENDATIONS` are not available for this snapshot.

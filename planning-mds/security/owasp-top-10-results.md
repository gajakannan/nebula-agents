# F0001 OWASP Top 10 Results

Status: Reviewed
Date: 2026-07-13
Assessment: PASS WITH RECOMMENDATIONS
Baseline: OWASP Top 10 (2021)

## Applicability

F0001 is a local Python CLI/TUI with no HTTP listener, browser origin, cookie, remote API, database, or outbound URL-fetch feature. Web-only controls such as CORS, security headers, cookie flags, TLS termination, SSRF allowlists, and dynamic web scanning have no execution target. Categories are still assessed against analogous local trust boundaries.

## Category results

| OWASP category | Result | F0001 evidence and disposition |
|---|---|---|
| A01 Broken Access Control | PASS | OS-derived identity, deny-by-default action policy, owner/resource checks, named reviewer grants, safe projections, and reauthorization under the commit lock. Reviewer reads cannot persist mutations. |
| A02 Cryptographic Failures | PASS / limited applicability | F0001 stores no credential and transmits no application network data. Owner-only files and optional host disk encryption protect local data; no custom cryptography is claimed. |
| A03 Injection | PASS | Commands use typed argv with `shell=False`; tmux command strings use `shlex.join`; descriptor, identifier, path, executable, schema, and environment inputs are validated and bounded. |
| A04 Insecure Design | PASS | Architecture declares the OS trust boundary, default-deny policy, opt-in redact-before-write transcript, fresh gate evidence binding, CAS, and STRIDE abuse cases. |
| A05 Security Misconfiguration | PASS | Owner-only defaults, no listener, no root bypass, explicit runtime override, allowlisted environment, schema validation, fail-closed policy, and hidden unauthorized UI controls. |
| A06 Vulnerable and Outdated Components | PASS WITH RECOMMENDATION | `pip-audit` found no known vulnerability in the resolved set. Release reproducibility would improve with hash-locked dependencies. |
| A07 Identification and Authentication Failures | PASS / limited applicability | Caller identity is the OS UID; provider authentication remains provider-native. Ambiguous local role resolution fails closed and display labels are non-authoritative. No app password/session token exists. |
| A08 Software and Data Integrity Failures | PASS WITH RECOMMENDATION | Schemas, immutable identity, sequence/revision checks, atomic publication, contained no-follow reads, and gate evidence digests protect state. Local JSONL is not cryptographically tamper-evident against the owning UID. |
| A09 Security Logging and Monitoring Failures | PASS WITH RECOMMENDATION | Sequenced sanitized events cover lifecycle, gates, validators, transcript state, and authorization denial. Same-UID tamper evidence and centralized monitoring are outside the MVP. |
| A10 Server-Side Request Forgery | NOT APPLICABLE | No server-side URL retrieval, webhook, HTTP client, or remote fetch path exists in F0001. |

## Automated and manual evidence

- Dependency audit: `pip-audit`, exit 0, no known vulnerabilities.
- Secrets scan: `detect-secrets`, exit 0, no findings.
- SAST: Bandit 1.9.4, 5,572 source lines, 0 High, 0 Medium, and 17 reviewed Low heuristic findings.
- DAST: waived because the approved architecture has no network listener or HTTP target; waiver owner Security Reviewer, approved 2026-07-13.
- Focused manual/regression run: 307 passed, covering authorization, gate freshness, policy identity, governed path containment, execution boundaries, transcript redaction/failure state, projection, reconciliation, and TUI controls.
- Full QE baseline: 424 passed with zero failures, errors, skips, or xfails; 90.03% coverage; and one successful real tmux smoke test.

## Finding summary

No Critical, High, or Medium OWASP finding remains open. Low recommendations cover deterministic dependency locking, stronger optional audit tamper evidence, and continued redaction-corpus maintenance. All 17 Bandit Low results were manually dispositioned as intentional direct-argv/direct-exec boundaries or fail-safe best-effort compensation/audit paths.

## Release result

The local F0001 scope satisfies the OWASP review baseline. Any future network service, remote multi-user mode, database, plugin download, or URL-fetch behavior invalidates the limited-applicability decisions above and requires a new threat model and DAST target.

OWASP result: PASS WITH RECOMMENDATIONS.

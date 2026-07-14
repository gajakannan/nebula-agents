# F0001 Secrets Management Review

Status: Reviewed
Date: 2026-07-13
Assessment: PASS WITH RECOMMENDATIONS

## Credential ownership model

F0001 does not provision, retrieve, refresh, rotate, or persist provider credentials. Codex and Claude Code retain their native authentication and prompt behavior inside the tmux session. Readiness probes record only a category such as ready or authentication-attention-needed.

The cockpit must not read provider auth files, OS keychains, shell history, API-key environment values, or credential-store contents. An operator username or reviewer display label is not a credential.

## Process and environment boundary

Provider execution uses a canonical executable validated as a regular executable file and a typed argv vector. The private launch descriptor contains only approved fields and is owner-only, no-follow, size-bounded, run-bound, and deleted before `execvpe`.

The forwarded environment is an allowlist of non-secret execution context such as `PATH`, home/config directory locations, terminal values, locale, and provider configuration-directory locations. Arbitrary `*_TOKEN`, `*_KEY`, password, and credential values are not copied into descriptors or logs. F0001 does not print the raw launch environment.

## Redaction and failure safety

Credential-like content from provider output, transcript bytes, gate reasons, and captured process output is handled by the shared streaming redactor before durable or user-visible output. Supported classes include bearer values, common GitHub/Slack/provider token prefixes, AWS access-key IDs, key/value credential assignments, database URLs, and PEM private-key blocks.

Chunk overlap prevents credentials split across reads from leaking. Open private-key blocks never emit their contents and use bounded state. Terminal control characters and oversized output are sanitized or truncated after redaction. Redaction/capture failure stops transcript persistence instead of writing raw content.

## Repository and dependency scans

The F0001 evidence package records a `detect-secrets 1.5.0` scan of application source and `engine/pyproject.toml` with exit code 0 and an empty result set. Manual review found no hardcoded credential, private key, auth token, or connection string in runtime source.

`pip-audit` separately reports no known vulnerabilities in the resolved Python dependency set. Bandit reports no Medium or High issue; its 17 Low findings are reviewed subprocess, direct-exec, assertion, or best-effort audit/compensation patterns rather than embedded secrets.

## Rotation and incident handling

Because provider credentials remain provider-owned, rotation and revocation use the provider's native logout/login or credential-management workflow. If a redaction finding indicates possible disclosure, the operator must treat the underlying provider credential as exposed, rotate it through that provider, stop/replace the affected session, and handle the owner-only transcript under incident policy.

F0001 stores no encryption key and therefore has no application key-rotation schedule. Host disk encryption, OS account lifecycle, and provider credential rotation remain environmental controls.

## Residual risk and result

New credential formats can outpace a finite redaction signature set. Maintain adversarial split-chunk and private-key regression cases as formats evolve, while preserving the primary rule that F0001 never intentionally reads credentials.

Secrets-management result: PASS WITH RECOMMENDATIONS.

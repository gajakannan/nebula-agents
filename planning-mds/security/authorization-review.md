# F0001 Authorization Review

Status: Reviewed
Date: 2026-07-13
Assessment: PASS WITH RECOMMENDATIONS

## Authorization contract

F0001 authenticates the caller with the local OS UID and supplementary groups. Authorization is deny-by-default over subject, resource, action, and context attributes as defined in `planning-mds/security/f0001-authorization-model.md` and the local-policy schema.

The LocalOperator can mutate owned runs. A Reviewer can probe, read a sanitized projection, and run allowlisted validators; launch, attach, gate decisions, recovery, and transcript configuration require explicit policy. Root does not receive an application bypass. The System role cannot be assigned by local policy.

## Enforcement and policy integrity

- Presentation controls are usability hints only. Every protected application service invokes authorization independently.
- Mutations reauthorize against the current persisted policy and current run while holding the repository lock, then enforce the expected revision.
- Policy files are schema-validated, owner-only, locked, and atomically written. Duplicate `(subject_type, subject_id)` bindings are rejected.
- UID bindings take precedence over group bindings. Multiple matching roles at the effective precedence level fail closed.
- Authorization denials use stable public errors and append a sanitized `AuthorizationDenied` event when a run context exists.
- Optional reviewer grants map to one named action and do not confer ownership or bypass lifecycle guards.

## Resource and projection controls

The authorization resource binds workspace root, run ID, and owner UID. `safe_run_projection` is the only externally authorized run view. By default it removes workspace root, prompt contract, evidence root, audit path, tmux session name, validator artifact path, transcript path, and transcript preview for a non-owner.

The projection exposes boolean capabilities such as `can_attach`, `can_recover`, `can_decide_gate`, and `can_configure_transcript`. CLI formatters and the TUI use those booleans before showing action guidance. Application checks remain authoritative if a caller invokes an action directly.

Reviewer `READ_STATE` reconciliation and evidence observation are computed in memory and not committed. Only the owning LocalOperator can persist these lifecycle/evidence observations.

## Gate authorization and freshness

Gate approval requires explicit confirmation and an authorization context for `Approve`. A successful decision also requires all of the following at commit time:

- the requested gate is still pending;
- required evidence is semantically ready;
- contained evidence can be read without following symlinks and is stable across the read;
- the validator exited successfully for the same gate ID;
- `validated_revision` equals the current run revision;
- the validator's evidence digest equals a freshly computed digest.

The final freshness callback executes within the per-run repository lock. Deleted, replaced, stale, cross-gate, or concurrently changed evidence therefore blocks approval.

## Former findings and regression evidence

| Former issue | Current disposition | Regression evidence |
|---|---|---|
| HIGH: cached validator/evidence could approve without a fresh bound check | Fixed | gate tests cover deleted evidence, mismatched gate/revision/digest, semantic readiness, and revision change under lock |
| MEDIUM: reviewer projection exposed internal execution/transcript details | Fixed | projection tests assert hidden session, paths, prompt, evidence, validator path, transcript path/preview, and false capabilities |
| MEDIUM: reviewer read reconciliation persisted state | Fixed | query/service tests assert non-owner reads do not change repository revision |
| MEDIUM: duplicate or contradictory bindings could elevate by order | Fixed | policy and identity tests reject duplicates and conflicting effective roles |
| MEDIUM: validator summary bypassed reviewer path minimization | Fixed | non-owner projection replaces untrusted validator output with a stable generic summary; path and bearer sentinels are absent |
| MEDIUM: governed feature/story/validator paths followed symlinks | Fixed | launch and validator tests reject symlinked feature directories and story files before authorization or execution |
| MEDIUM: evidence root and prompt selection could escape their governed roots | Fixed | canonical evidence-run, prompt leaf, and ancestry checks reject symlinks; launch reopens prompts through no-follow directory descriptors |
| MEDIUM: transcript completion could race the filter's terminal failure | Fixed | completion waits for a bounded durable terminal status and persists `Failed` unless the worker reports valid `Completed` state |

The final focused authorization, security, gate, policy, containment, transcript, and presentation suite completed with 307 passed on 2026-07-13. No authorization bypass or governed-path escape was reproduced.

## Residual authorization risk

The owning OS UID is an explicit trust boundary, not a tenant. Another process already acting as that UID can read or alter owner files outside the guarantees of this application. This is acceptable for the local MVP and must be reconsidered before any multi-user daemon or remote service is introduced.

Authorization result: PASS WITH RECOMMENDATIONS.

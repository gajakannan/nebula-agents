# F0001 Deployability Check — run 2026-07-13-1cfbc5a0

## Scope

F0001 is a local Python package and tmux process, not a hosted deployment. This check covers package composition, console entry, runtime directory safety, host dependencies, and clean shutdown/cleanup behavior. Docker, CI/CD, database migrations, network services, and remote environment promotion are not in scope and no deployment configuration changed.

## Checks

| Check | Result | Evidence |
|-------|--------|----------|
| Editable install with test extras | PASS | `/tmp/f0001-venv/bin/pip install -e 'engine[test]'` |
| Installed import/version | PASS | `import nebula_agents` -> `0.1.0` |
| Console help | PASS | `nebula-agents --help` lists the approved public commands |
| Runtime doctor | PASS | JSON result `overall_status=ready`; tmux 3.6 and Codex CLI 0.144.3 ready |
| Owner-only runtime | PASS | doctor and containment tests validate private runtime directories/files |
| Full acceptance suite | PASS | 424 passed; 0 failures/errors/skips/xfails; 90.03% coverage against the 85% gate |
| Real tmux launch/attach | PASS | focused host-runtime test passed in 0.47 seconds; fake provider starts once, attach reuses the exact session, and cleanup succeeds |
| Failure/rollback | PASS | descriptor, bounded collision, tmux, validator, evidence, transcript, CAS, and persistence failures produce stable terminal/audit behavior |
| Containment and suppression | PASS | feature/story/evidence/prompt/validator symlinks are rejected; reviewer summaries suppress paths and secret-like content |
| Dependency audit | PASS | resolved runtime/test constraints have no known vulnerabilities |
| Compile and diff hygiene | PASS | compileall and `git diff --check` exit 0 |

## Operational Requirements

- POSIX/WSL environment with Python 3.11+, tmux, curses, and fcntl.
- At least one supported native provider CLI installed; provider login remains provider-owned.
- The workspace must contain committed feature, schema, and prompt contracts.
- Custom runtime roots must be absolute, owner-only, and non-symlinked.

## Rollback

Uninstall the Python package and remove only the operator-owned `.nebula-agents/runtime` directory after terminating recorded tmux sessions. F0001 creates no database, remote resource, system service, or migration requiring a separate rollback plane.

## Result

PASS

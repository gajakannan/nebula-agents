# Nebula Agents Runtime Glossary

## F0001 Entities

### Run Record

**Type:** Entity

The current, revisioned snapshot for one native provider run, including tmux identity, feature/story focus, lifecycle state, current gate, evidence observations, transcript state, and audit pointer.

### Runtime Event

**Type:** Entity

An immutable, sequenced, sanitized audit record for a run mutation, denial, validator execution, watcher error, or recovery action.

### Local Policy

**Type:** Entity

The versioned owner-only mapping from OS identity attributes and local roles to allowed runtime actions.

### Gate Snapshot

**Type:** Value Object

The current gate identifier, status, evidence eligibility, and latest decision projection within a run.

### Validator Result

**Type:** Value Object

A bounded, redacted result for one allowlisted validator execution, including stable key, exit code, duration, timestamp, summary, and optional artifact path.

### Artifact Observation

**Type:** Value Object

The last known availability, freshness, parse status, and relative path for one watched evidence artifact.

### Transcript State

**Type:** Value Object

The capture, redaction, path, preview, and failure state for an explicitly enabled redacted transcript.

### Provider Probe

**Type:** Value Object

A non-secret readiness observation for tmux or a supported provider executable.

## F0001 Roles

### Local Operator

**Type:** Role

The OS-authenticated creator/owner of a local run who may launch, attach, validate, decide eligible gates, and configure transcripts under default policy.

### Reviewer

**Type:** Role

A local user who may inspect sanitized run state and execute allowlisted validators; all mutation capabilities require explicit grants.

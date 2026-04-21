# Prioritization Examples

Use these as formatting patterns. Replace sample values with project data.

## Example 1: Now/Next/Later

### Context
Need a 1-quarter view for workflow and platform improvements.

### Output
- **Now**
  - API authorization hardening
  - Core lifecycle reliability fixes
- **Next**
  - At-risk entity queue
  - Bulk operations with guardrails
- **Later**
  - Predictive transition risk signals
  - Team benchmarking dashboards

### Notes
- Assumption: security/reliability are preconditions for scale features.
- Risk: bulk actions may require additional permission granularity.

## Example 2: RICE

### Context
Rank three candidate initiatives for next increment.

| Initiative | Reach | Impact | Confidence | Effort | RICE |
|---|---:|---:|---:|---:|---:|
| At-risk entity queue | 600 | 2.0 | 0.75 | 6 | 150 |
| Bulk edit workflows | 350 | 1.5 | 0.80 | 4 | 105 |
| Dashboard theming refresh | 1000 | 0.5 | 0.60 | 5 | 60 |

### Notes
- Rank: At-risk queue > Bulk edits > Theming refresh.
- Assumption: impact measured on weekly active operator productivity.

## Example 3: WSJF

### Context
Three platform initiatives compete for one release window.

| Initiative | Business Value | Time Criticality | Risk Reduction | Cost of Delay | Job Size | WSJF |
|---|---:|---:|---:|---:|---:|---:|
| Access policy enforcement | 9 | 10 | 8 | 27 | 5 | 5.4 |
| Data export tooling | 6 | 5 | 4 | 15 | 3 | 5.0 |
| UI navigation redesign | 5 | 3 | 2 | 10 | 4 | 2.5 |

### Notes
- Rank: Access policy enforcement first due to urgency and risk profile.

## Example 4: MoSCoW

### Context
Need a cut line for a fixed-date release.

- **Must**
  - Role-based authorization checks on all protected APIs
  - Lifecycle restore endpoint and audit events
- **Should**
  - Assigned-to display name in task summaries
  - List input guardrails (paging/status validation)
- **Could**
  - Additional timeline filtering UX
- **Won't (this release)**
  - Advanced predictive nudges

### Notes
- Assumption: Must items are release-blocking risk controls.

## Example 5: Kano

### Context
Classify features before final roadmap sequencing.

- **Must-be**
  - Correct permissions per role
  - Clear validation and error responses
- **Performance**
  - Faster search and filtering
  - Better work queue visibility
- **Delighter**
  - Proactive risk nudges
  - Smart next-best-action suggestions
- **Indifferent**
  - Non-essential cosmetic effects

### Notes
- Use Kano output to inform, not replace, RICE/WSJF scoring.

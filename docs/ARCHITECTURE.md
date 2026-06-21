# Driftwatch Architecture

## Oversight-Safety Runtime

```mermaid
flowchart LR
  UI[React control panel] -->|SSE request| API[FastAPI Driftwatch route]
  API --> D[Pluggable domain oracle]
  D --> C[Case + ground truth]
  C --> M[Caseworker degradation profile]
  M --> O[Oversight update]
  A[Strategic adversaries] --> O
  N[Citizen social graph] --> O
  I[Spot checks / confidence review / audits] --> O
  O --> E[Event log]
  E --> K[Debt / half-life / silent errors / skill / drift detection]
  E --> P[Early-warning predictor]
  K --> UI
  P -->|live risk score| UI
```

The domain oracle supports benefits eligibility, MSME microfinance, rural
healthcare triage, and gig-platform dispatch. The caseworker layer exposes
closed, open-source API, and local FP16/INT8/INT4 conditions. Population runs
use reproducible degradation profiles around oracle ground truth, so they work
without provider credentials; optional live provider adapters remain available
for direct model calls.

Each citizen independently tracks review probability and review skill. Language
mismatch and explanation quality affect effective skill, latency and trust are
logged as separate skip causes, healthcare applies a structural reviewer-capacity
ceiling, and network influence uses observable neighbor complaint rates. The
event log drives both aggregate metrics and the timestep-10 early-warning model.

## Legacy Population Engine

The original tiered Tier 1/2/3 population engine remains available through the
general simulation routes. It is separate from the Driftwatch oversight runtime
and continues to be covered by the existing engine/API test suite.

## Reproducibility and Limits

- Requests accept a seed and bounded population/horizon parameters.
- Simulation profiles are research assumptions, not empirical measurements of
  named production models.
- Prompt-injection rates are deterministic simulated susceptibility probes.
- State, result storage, caching, and rate limits are process-local.
- Multimodal decisions are not modeled.

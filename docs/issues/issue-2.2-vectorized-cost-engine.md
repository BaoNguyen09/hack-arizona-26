# Issue 2.2: Build Vectorized Cost Scoring Engine

## Scope

- Implement LCOE calculation matrix
- Implement temporal revenue projection matrix
- Implement carbon value matrix
- Implement final user-weighted composite score and expose it via FastAPI `/heatmap`

## Acceptance Criteria

- NumPy-based scoring runs over the pre-computed grid without Python loops on the hot path
- Composite score exposes weight controls for cost, revenue, and carbon value
- Backend response is stable and benchmarked against the 200ms target

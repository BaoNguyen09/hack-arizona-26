# Issue 2.1: Implement Physics-Based Generation Models

## Scope

- Write a PVWatts-style solar generation function
- Write an IEC wind power curve lookup model
- Validate solar generation against NREL PVWatts for at least 3 distinct coordinates

## Acceptance Criteria

- Solar model accounts for irradiance, ambient temperature, tilt, azimuth, losses, and AC conversion
- Wind model extrapolates 10m wind to hub height and maps to a turbine curve
- Tests verify modeled generation stays within 10% of benchmark values

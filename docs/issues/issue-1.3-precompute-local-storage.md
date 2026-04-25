# Issue 1.3: Implement Pre-Computation & Local-First Storage Pipeline

## Scope

- Map roughly 3,500 CONUS grid cells to nearest EIA price hub and Electricity Maps zone
- Compute base unweighted solar and wind capacity factors per cell
- Export joined data to Parquet or SQLite GeoPackage for fast hydration

## Acceptance Criteria

- Pre-computation job can run end to end from normalized inputs
- Output schema includes `lat`, `lon`, `solar_cf`, `wind_cf`, `avg_price`, `carbon_intensity`, and `nearest_transmission_km`
- The processed artifact loads fast enough to support sub-200ms score recalculation

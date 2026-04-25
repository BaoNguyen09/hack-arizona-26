# Issue 1.1: Build Weather & Physical Data Ingestion Hooks

## Scope

- Fetch 30 days of NOAA GFS weather data for CONUS at 0.25 degree resolution
- Include DSWRF, wind speed and direction at 10m, 80m, and 100m, plus temperature
- Download and parse NREL ATB static CSVs for CAPEX and OPEX assumptions
- Download HIFLD transmission line GeoJSON and EIA-860 power plant CSVs

## Acceptance Criteria

- Repeatable scripts exist for each source
- Raw outputs are stored under `data/raw/`
- Parsers normalize column names and data types
- Source metadata and refresh assumptions are documented

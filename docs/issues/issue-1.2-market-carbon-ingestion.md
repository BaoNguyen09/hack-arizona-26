# Issue 1.2: Build Market & Carbon Data Ingestion Hooks

## Scope

- Integrate the EIA Open Data API for hourly wholesale electricity prices by hub or node
- Pull historical or real-time carbon intensity from Electricity Maps
- Fetch annual baseline grid emission factors via EPA eGRID CSVs

## Acceptance Criteria

- API credentials are read from environment variables
- Rate limits and retry behavior are handled
- Parsed outputs can be joined by time and region
- A sample normalized dataset is committed or reproducible via script

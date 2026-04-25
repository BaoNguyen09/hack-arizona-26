# Epic 1: Data Infrastructure & Pre-Computation Pipeline

## Goal

Fetch disparate raw datasets and compile them into a highly optimized local-first structure that enables sub-200ms map rendering.

## Deliverables

- NOAA GFS ingestion hooks for 30 days of weather data over CONUS
- Static data ingestion for NREL ATB, HIFLD transmission lines, and EIA-860 plants
- Market and carbon data ingestion for EIA, Electricity Maps, and EPA eGRID
- Cell-level joined artifact exported as Parquet and/or SQLite GeoPackage

## Suggested Child Issues

- 1.1 Build weather and physical data ingestion hooks
- 1.2 Build market and carbon data ingestion hooks
- 1.3 Implement pre-computation and local-first storage pipeline

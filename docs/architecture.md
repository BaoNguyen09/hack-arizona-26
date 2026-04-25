# Architecture Notes

## Principles

- Local-first data products for fast iteration and demo resilience
- Pre-computation over raw hourly feeds to keep API latency comfortably below 200ms
- Clear separation between ingestion, modeling, optimization, and presentation
- Extensible interfaces so solar, wind, and future storage logic can share the same scoring surface

## Planned Runtime Flow

1. Offline jobs ingest and normalize raw weather, price, carbon, and infrastructure data
2. A preprocessing job materializes a joined cell-level analytics dataset
3. FastAPI loads the processed artifact into memory or DuckDB-backed access patterns
4. The `/heatmap` API applies scenario weights and returns score-enriched cells
5. The `/site` API returns per-cell diagnostics plus an optional AI-generated summary

## Priority Implementation Order

1. Data ingestion contracts
2. Pre-computation pipeline
3. Physics models
4. Vectorized scoring engine
5. Frontend interaction loop
6. LLM assistance features

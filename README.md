# Lumen

Lumen is a renewable energy cost optimization intelligence platform that turns weather, power prices, carbon intensity, and infrastructure constraints into an interactive decision surface for siting and scenario analysis.

## What This Repo Contains

- `backend/`: FastAPI application for scenario scoring, site detail APIs, and AI-generated briefs
- `frontend/`: React 18 + TypeScript + Deck.gl + MapLibre client
- `data/`: local-first storage for raw ingests, processed outputs, and reference datasets
- `scripts/`: ingestion, preprocessing, validation, and export jobs
- `docs/`: architecture notes and GitHub-ready backlog artifacts
- `.github/`: issue templates and pull request hygiene

## Product Goals

- Render a composite renewable cost heatmap over CONUS in under 200ms after scenario changes
- Pre-compute weather, price, carbon, and infrastructure joins into a local analytics-ready dataset
- Support Solar PV and Onshore Wind scenario analysis
- Produce human-readable site assessment briefs from structured model outputs

## Initial Architecture

### Data pipeline

1. Ingest NOAA GFS, NREL ATB, HIFLD, EIA Open Data, EIA-860, EPA eGRID, and Electricity Maps inputs
2. Normalize weather, market, carbon, and infrastructure data to a shared spatial grid
3. Pre-compute capacity factors, nearest price hubs, grid zones, and transmission proximity
4. Export a local Parquet or SQLite/GeoPackage artifact for fast backend hydration

### Backend

- FastAPI service for `/health`, `/heatmap`, `/site`, and future `/brief` and `/query` routes
- NumPy vectorized optimization engine for LCOE, revenue, carbon value, and composite scoring
- Physics models for PVWatts-style solar and IEC-style wind generation

### Frontend

- React 18 + Vite
- MapLibre GL + Deck.gl for the primary spatial experience
- Recharts for site-level diagnostics
- Minimalist scenario controls with sub-second feedback

## Repo Layout

```text
Lumen/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE.md
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/
│   └── tests/
├── data/
│   ├── processed/
│   ├── raw/
│   └── reference/
├── docs/
│   ├── architecture.md
│   ├── backlog.md
│   └── issues/
├── frontend/
│   ├── public/
│   └── src/
├── infra/
├── notebooks/
├── scripts/
├── .env.example
├── .gitignore
├── Makefile
└── requirements.txt
```

## Getting Started

### Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Environment

Copy `.env.example` into `.env` and fill in any API keys you intend to use.

- `EIA_API_KEY`
- `ELECTRICITY_MAPS_API_KEY`
- `OPENAI_API_KEY`
- `MAPTILER_API_KEY`

## Suggested Near-Term Milestones

1. Land data ingestion hooks for all external sources
2. Build the pre-computation artifact for ~3,500 CONUS grid cells
3. Validate solar and wind generation models against trusted benchmarks
4. Expose a fast composite scoring API
5. Connect the map layer and site investigation panel end to end

## Backlog

The issue-ready implementation plan is documented in [docs/backlog.md](/Users/shanejanney/Desktop/Lumen/docs/backlog.md) and split into individual GitHub-ready issue drafts under [docs/issues](/Users/shanejanney/Desktop/Lumen/docs/issues).

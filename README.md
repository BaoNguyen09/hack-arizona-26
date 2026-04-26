# Lumen — Renewable Energy Cost Optimization Intelligence Platform

Lumen is a map-based intelligence platform that visualizes renewable energy cost optimization across geography and time. It fuses weather-dependent generation models, wholesale electricity prices, grid carbon intensity, and infrastructure constraints into a single interactive decision surface.

Users explore a live choropleth map showing where energy is cheapest, click any county to see a detailed site assessment with LCOE breakdowns, revenue projections, carbon displacement metrics, and an AI-generated brief — all in seconds.

---

## Features

| Feature | Status |
|---|---|
| **County-level choropleth map** — 3,100+ US counties colored by carbon intensity using real EIA state-level energy data | ✅ Shipped |
| **Scenario configurator** — Technology toggle (Solar/Wind), CAPEX slider, carbon price slider | ✅ Shipped |
| **Site investigation panel** — Click any county for LCOE, capacity factor, revenue, carbon displacement, generation charts, and AI brief | ✅ Shipped |
| **Time-series animation** — Floating playback slider to animate data across hours | ✅ Shipped |
| **Analytics sidebar** — National overview with carbon intensity, electricity mix, price, and load charts | ✅ Shipped |
| **Backend API** — FastAPI with deterministic county scoring engine and AI brief generation | ✅ Shipped |
| **Natural language query** — NL scenario query bar (UI shell + backend stub) | 🔜 Planned |
| **Comparison mode** — Pin 2–3 candidate sites for side-by-side analysis | 🔜 Planned |
| **Real data ingestion** — NOAA GFS, EIA, NASA POWER, Electricity Maps | 🔜 Planned |

---

## Architecture

```
Frontend (React + TypeScript + Vite)
  ├── MapLibre GL JS — vector choropleth map (county-level)
  ├── Recharts — site-level diagnostic charts
  ├── Zustand — state management
  └── Framer Motion — animations

Backend (FastAPI + Python)
  ├── /county/{fips} — deterministic site metrics (LCOE, CF, revenue, carbon)
  ├── /brief — AI-generated site assessment text
  ├── /query — NL query parser (stub)
  └── NumPy scoring engine (LCOE, CRF, carbon value calculations)

Data Layer
  ├── State-level energy profiles (EIA 2026-02 data for all 50 states)
  ├── Deterministic county-level LCG engine (FIPS-seeded)
  └── US Counties + States GeoJSON (Census Bureau)
```

---

## Tech Stack

| Layer | Technology | Cost |
|---|---|---|
| **Frontend** | React 18, TypeScript, Vite, MapLibre GL JS, Recharts, Zustand, Framer Motion, Tailwind CSS | $0 |
| **Map tiles** | MapTiler free tier | $0 |
| **Backend** | Python 3.11+, FastAPI, uvicorn, NumPy, pandas | $0 |
| **Data** | EIA Open Data, EPA eGRID, Census GeoJSON | $0 |
| **LLM** (planned) | GPT-4o-mini or Groq (Llama 3) | ~$0–1 |

---

## Quickstart

### Prerequisites

- Node.js 18+
- Python 3.11+

### Backend

```bash
pip install fastapi uvicorn pandas pydantic_settings numpy
python -m uvicorn backend.app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173` (or the next available port).

---

## API

Full API documentation is available at [docs/api.md](docs/api.md).

When the backend is running, interactive Swagger docs are at `http://localhost:8000/docs`.

### Key endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/county/{fips_code}` | Site metrics for a US county |
| `POST` | `/brief` | AI-generated site assessment |
| `POST` | `/query` | Natural language query (stub) |
| `GET` | `/health` | Health check |

---

## Data Sources

| Source | Data | Used For |
|---|---|---|
| **EIA Open Data** (2026-02) | State-level electricity prices, generation mix (solar, wind, hydro, fossil %) | County-level energy profile baselines |
| **US Census Bureau** | County and state GeoJSON boundaries | Map rendering |
| **NREL ATB** | Reference CAPEX, OPEX, LCOE assumptions | Scoring engine defaults |
| **NOAA GFS** (planned) | Solar irradiance, wind speed forecasts | Weather-to-generation model |
| **NASA POWER** (planned) | Solar climatology | Validation/gap-fill |
| **EPA eGRID** (planned) | Annual grid emission factors | Carbon intensity baselines |
| **HIFLD** (planned) | Transmission line routes | Infrastructure overlay |

---

## Project Structure

```
Lumen/
├── backend/
│   └── app/
│       ├── api/routes.py        # API endpoints
│       ├── core/config.py       # Settings
│       ├── data/
│       │   ├── county_store.py  # Deterministic county data generator
│       │   ├── state_data.py    # EIA state energy profiles
│       │   └── processed_store.py
│       ├── engine/scoring.py    # LCOE/revenue/carbon scoring
│       ├── schemas/scenario.py  # Pydantic models
│       ├── services/            # Business logic
│       └── main.py              # FastAPI app
├── frontend/
│   └── src/
│       ├── components/          # React UI components
│       ├── data/                # Client-side data (zones, mockData, stateData)
│       ├── lib/api.ts           # Backend API client
│       ├── store/               # Zustand state management
│       └── App.tsx              # Root component
├── docs/
│   └── api.md                   # REST API reference
├── .env.example
├── requirements.txt
└── README.md
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in API keys as needed:

```
EIA_API_KEY=          # EIA Open Data API key (future)
OPENAI_API_KEY=       # For LLM-powered briefs (future)
MAPTILER_API_KEY=     # Map tile rendering
```

---

## License

MIT — see [LICENSE](LICENSE).

# Lumen API Reference

> Base URL: `http://localhost:8000`

Lumen exposes a RESTful API built with FastAPI. Interactive Swagger docs are available at `/docs` when the server is running.

---

## Endpoints

### `GET /health`

Health check endpoint. Returns service status and data store information.

**Response** `200 OK`

```json
{
  "status": "ok",
  "store_loaded": false,
  "store_row_count": 0
}
```

---

### `GET /county/{fips_code}`

**Primary endpoint.** Returns comprehensive site metrics for a US county identified by its 5-digit FIPS code. Metrics are deterministically generated from the FIPS code and real state-level energy data (EIA 2026-02).

#### Path Parameters

| Parameter | Type | Description |
|---|---|---|
| `fips_code` | `string` | 5-digit county FIPS code (e.g., `06037` for Los Angeles County, CA) |

#### Query Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `technology` | `string` | `solar` | Technology type: `solar` or `wind` |
| `capacity_mw` | `float` | `50.0` | Installed capacity in MW |
| `capex_usd_per_kw` | `float` | `1200.0` | Capital expenditure in USD per kW |
| `opex_usd_per_kw_year` | `float` | `35.0` | Operating expenditure in USD per kW per year |
| `discount_rate` | `float` | `0.06` | Discount rate for LCOE calculation |
| `project_lifetime_years` | `int` | `25` | Project lifetime in years |
| `carbon_price_usd_per_ton` | `float` | `50.0` | Social cost of carbon in USD per ton |
| `cost_weight` | `float` | `1.0` | Weight for cost minimization in composite score |
| `revenue_weight` | `float` | `1.0` | Weight for revenue maximization in composite score |
| `carbon_weight` | `float` | `1.0` | Weight for carbon value in composite score |

#### Example

```bash
curl "http://localhost:8000/county/48201?technology=solar&capacity_mw=100&capex_usd_per_kw=1000&carbon_price_usd_per_ton=50"
```

#### Response `200 OK`

```json
{
  "site": {
    "cell_id": "county_48201",
    "lat": 30.12,
    "lon": -95.47,
    "solar_cf_mean": 0.26,
    "wind_cf_mean": 0.31,
    "selected_technology": "solar",
    "selected_cf_mean": 0.26,
    "estimated_annual_generation_gwh": 113.88,
    "lcoe_usd_per_mwh": 32.4,
    "lcoe_components": {
      "capex_share": 22.1,
      "opex_share": 4.0,
      "financing_share": 6.3
    },
    "capex_total_usd_millions": 100.0,
    "price_hub_id": "HUB_TX",
    "avg_wholesale_price_usd_per_mwh": 38.2,
    "estimated_annual_revenue_usd_millions": 4.35,
    "revenue_per_mwh_usd": 38.2,
    "grid_carbon_intensity_g_per_kwh": 432.0,
    "annual_carbon_displacement_tons": 49195.0,
    "carbon_value_usd_per_year": 2459750.0,
    "carbon_value_usd_per_mwh": 21.6,
    "nearest_transmission_km": 18.3,
    "grid_zone_id": "ZONE_TX"
  },
  "scenario": {
    "technology": "solar",
    "capacity_mw": 100.0,
    "capex_usd_per_kw": 1000.0,
    "opex_usd_per_kw_year": 35.0,
    "discount_rate": 0.06,
    "project_lifetime_years": 25,
    "carbon_price_usd_per_ton": 50.0,
    "cost_weight": 1.0,
    "revenue_weight": 1.0,
    "carbon_weight": 1.0
  },
  "score_rank": 1,
  "total_cells": 3143
}
```

---

### `POST /brief`

Generates a natural-language AI site assessment brief from computed site metrics.

#### Request Body

```json
{
  "site": { "...SiteMetrics object from /county response..." },
  "scenario": { "...ScenarioRequest object from /county response..." }
}
```

#### Example

```bash
curl -X POST "http://localhost:8000/brief" \
  -H "Content-Type: application/json" \
  -d '{"site": {"selected_cf_mean": 0.26, "lcoe_usd_per_mwh": 32.4, "avg_wholesale_price_usd_per_mwh": 38.2, "grid_carbon_intensity_g_per_kwh": 432, "nearest_transmission_km": 18.3}, "scenario": {}}'
```

#### Response `200 OK`

```json
{
  "status": "success",
  "text": "Site Assessment: This county location offers a capacity factor of 26.0%, yielding an estimated LCOE of $32.4/MWh. Wholesale prices at the nearest hub average $38.2/MWh, creating positive margin. Grid carbon intensity here is 432.0 gCO₂/kWh, meaning each MWh displaces 0.43 tCO₂. Nearest 345kV transmission line is 18.3 km away. Key risk: curtailment during spring months when supply exceeds demand."
}
```

> **Note:** This endpoint currently uses template-based generation. Future versions will integrate Claude 3.5 or GPT-4o-mini for richer, context-aware briefs.

---

### `POST /query`

Natural language scenario query parser. **Stub — not yet implemented.**

Will parse queries like *"Show me the cheapest places to build 50MW of wind in ERCOT where carbon intensity is above 400 gCO₂/kWh"* into structured scenario parameters.

#### Response `200 OK`

```json
{
  "status": "not_implemented",
  "message": "NL query parsing coming soon"
}
```

---

### `GET /site`

Legacy grid-cell site lookup. Requires the pre-computed dataset (`lumen_cells.gpkg`) to be loaded.

> **Note:** This endpoint is superseded by `GET /county/{fips_code}` for the current county-based architecture.

---

### `POST /heatmap`

Legacy heatmap scoring endpoint. Requires the pre-computed dataset to be loaded.

> **Note:** The frontend now uses county-level choropleth rendering with client-side data generation. This endpoint is preserved for future use with real ingested data.

---

## Data Model

### SiteMetrics

| Field | Type | Description |
|---|---|---|
| `cell_id` | `string` | Unique identifier (e.g., `county_48201`) |
| `lat` | `float` | Latitude |
| `lon` | `float` | Longitude |
| `solar_cf_mean` | `float` | Mean solar capacity factor (0–1) |
| `wind_cf_mean` | `float` | Mean wind capacity factor (0–1) |
| `selected_technology` | `string` | `solar` or `wind` |
| `selected_cf_mean` | `float` | Capacity factor for selected technology |
| `estimated_annual_generation_gwh` | `float` | Estimated annual generation in GWh |
| `lcoe_usd_per_mwh` | `float` | Levelized Cost of Energy in $/MWh |
| `lcoe_components` | `object` | Breakdown: `capex_share`, `opex_share`, `financing_share` |
| `capex_total_usd_millions` | `float` | Total CAPEX in $M |
| `avg_wholesale_price_usd_per_mwh` | `float` | Average wholesale electricity price |
| `estimated_annual_revenue_usd_millions` | `float` | Estimated annual revenue in $M |
| `grid_carbon_intensity_g_per_kwh` | `float` | Grid carbon intensity (gCO₂eq/kWh) |
| `annual_carbon_displacement_tons` | `float` | Annual carbon displacement in metric tons |
| `nearest_transmission_km` | `float` | Distance to nearest transmission line in km |
| `grid_zone_id` | `string` | Grid zone identifier |

### ScenarioRequest

| Field | Type | Default | Description |
|---|---|---|---|
| `technology` | `string` | `solar` | `solar` or `wind` |
| `capacity_mw` | `float` | `50.0` | Installed capacity |
| `capex_usd_per_kw` | `float` | `1200.0` | Capital expenditure |
| `opex_usd_per_kw_year` | `float` | `35.0` | Operating expenditure |
| `discount_rate` | `float` | `0.06` | Discount rate |
| `project_lifetime_years` | `int` | `25` | Project lifetime |
| `carbon_price_usd_per_ton` | `float` | `50.0` | Carbon price |
| `cost_weight` | `float` | `1.0` | Cost minimization weight |
| `revenue_weight` | `float` | `1.0` | Revenue maximization weight |
| `carbon_weight` | `float` | `1.0` | Carbon value weight |

---

## CORS

The API allows requests from the following origins during development:

- `http://localhost:5173`
- `http://localhost:5174`
- `http://localhost:5175`
- `http://localhost:3000`

---

## Error Handling

| Status | Meaning |
|---|---|
| `200` | Success |
| `404` | County/cell not found |
| `422` | Validation error (invalid parameters) |
| `500` | Internal server error |
| `503` | Data store not loaded (for legacy endpoints) |

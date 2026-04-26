# State + Electricity Maps Energy Data Pipeline

This document explains how Lumen should fetch state electricity cost/mix data, map it to Electricity Maps zones, store it in SQLite, and transform it into processed tables/views for the backend scoring engine.

## Goal

Build a processed SQLite view with one row per state and Electricity Maps zone:

```text
state_code
state_name
electricity_maps_zone_id
month
avg_electricity_cost_cents_per_kwh
pct_solar_state
pct_wind_state
pct_hydro_state
pct_fossil_state
carbon_g_per_kwh_zone
renewable_pct_zone
carbon_free_pct_zone
```

This gives Lumen:

- State-level electricity cost proxy
- State-level generation mix
- Electricity Maps zone-level carbon/grid signals
- Joinable features for cell scoring and site briefs

Primary storage is SQLite. CSV files are optional seed/export artifacts for sharing, debugging, or bootstrapping static mappings.

## Storage Model

Use this flow:

```text
API fetch -> raw SQLite tables -> normalized SQLite tables -> processed SQLite views/tables -> backend scoring
```

Recommended database path:

```text
data/processed/lumen_energy.sqlite
```

Keep raw responses for reproducibility:

```sql
CREATE TABLE IF NOT EXISTS raw_api_responses (
  source TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  request_url TEXT NOT NULL,
  request_params_json TEXT,
  response_json TEXT NOT NULL,
  fetched_at_utc TEXT NOT NULL,
  PRIMARY KEY (source, endpoint, request_url, fetched_at_utc)
);
```

## Source 1: EIA Retail Electricity Cost

Use EIA retail sales for average electricity price by state.

Endpoint:

```text
GET https://api.eia.gov/v2/electricity/retail-sales/data/
```

Query shape:

```text
?api_key=<EIA_API_KEY>
&frequency=monthly
&data[0]=price
&facets[sectorid][]=ALL
&facets[stateid][]=AZ
&start=2026-02
&end=2026-02
```

Important fields:

```text
period      -> month
stateid     -> state_code
stateName   -> state_name
sectorid    -> ALL
price       -> avg electricity cost, cents/kWh
price-units -> cents per kilowatthour
```

Normalized SQLite table:

```sql
CREATE TABLE IF NOT EXISTS state_retail_price_monthly (
  state_code TEXT NOT NULL,
  state_name TEXT NOT NULL,
  month TEXT NOT NULL,
  avg_electricity_cost_cents_per_kwh REAL NOT NULL,
  source TEXT NOT NULL DEFAULT 'EIA retail-sales',
  updated_at_utc TEXT NOT NULL,
  PRIMARY KEY (state_code, month)
);
```

Formula:

```text
avg_electricity_cost_usd_per_mwh =
  avg_electricity_cost_cents_per_kwh * 10
```

Reason: `1 cent/kWh = $10/MWh`.

## Source 2: EIA State Generation Mix

Use EIA electric power operational data for monthly generation by state, sector, and energy source.

Endpoint:

```text
GET https://api.eia.gov/v2/electricity/electric-power-operational-data/data/
```

Query shape:

```text
?api_key=<EIA_API_KEY>
&frequency=monthly
&data[0]=generation
&facets[sectorid][]=99
&facets[location][]=AZ
&start=2026-02
&end=2026-02
```

Use `sectorid=99` for total electric power industry.

Important fields:

```text
period       -> month
location     -> state_code
fueltypeid   -> fuel/source code
sectorid     -> 99
generation   -> generation, usually thousand MWh in the API
generation-units
```

Fuel grouping:

```text
solar  = SUN
wind   = WND
hydro  = WAT / conventional hydro, depending on returned fuel code
fossil = COL + NG + PEL + PC + OOG
total  = total generation for same state/month
```

When using the EIA workbook fallback, source names are:

```text
solar  = Solar Thermal and Photovoltaic
wind   = Wind
hydro  = Hydroelectric Conventional
fossil = Coal + Natural Gas + Petroleum + Other Gases + Petroleum Coke
total  = Total
```

Normalized SQLite table:

```sql
CREATE TABLE IF NOT EXISTS state_generation_mix_monthly (
  state_code TEXT NOT NULL,
  state_name TEXT NOT NULL,
  month TEXT NOT NULL,
  solar_generation_mwh REAL NOT NULL,
  wind_generation_mwh REAL NOT NULL,
  hydro_generation_mwh REAL NOT NULL,
  fossil_generation_mwh REAL NOT NULL,
  total_generation_mwh REAL NOT NULL,
  pct_solar REAL NOT NULL,
  pct_wind REAL NOT NULL,
  pct_hydro REAL NOT NULL,
  pct_fossil REAL NOT NULL,
  source TEXT NOT NULL DEFAULT 'EIA electric-power-operational-data',
  updated_at_utc TEXT NOT NULL,
  PRIMARY KEY (state_code, month)
);
```

Formulas:

```text
pct_solar  = solar_generation_mwh / total_generation_mwh * 100
pct_wind   = wind_generation_mwh / total_generation_mwh * 100
pct_hydro  = hydro_generation_mwh / total_generation_mwh * 100
pct_fossil = fossil_generation_mwh / total_generation_mwh * 100
```

Keep source percentages independent. They do not need to sum to 100 because nuclear, biomass, geothermal, imports/exports, storage, and unknown categories may exist outside these four columns.

## Source 3: Electricity Maps Zones

Use Electricity Maps for grid-zone carbon and clean energy signals.

Auth:

```text
auth-token: <ELECTRICITY_MAPS_API_KEY>
```

List zones:

```text
GET https://api.electricitymap.org/v4/zones
```

Map a coordinate to a zone:

```text
GET https://api.electricitymap.org/v4/zone?lat=33.4484&lon=-112.0740
```

Use this later to improve state-zone mapping with actual sample points inside each state.

## Source 4: Electricity Maps Carbon Intensity

Endpoint:

```text
GET https://api.electricitymap.org/v4/carbon-intensity/past-range
```

Query shape:

```text
?zone=US-SW-AZPS
&start=2026-02-01T00:00:00Z
&end=2026-03-01T00:00:00Z
&temporalGranularity=monthly
&emissionFactorType=lifecycle
```

Notes:

- Unit is `gCO2eq/kWh`.
- `lifecycle` is the default emission factor type, but pass it explicitly.
- Store `isEstimated` and `estimationMethod`.
- Use `disableEstimations=true` only for strict validation; default should keep estimated data for better coverage.

Normalized SQLite table:

```sql
CREATE TABLE IF NOT EXISTS zone_carbon_monthly (
  electricity_maps_zone_id TEXT NOT NULL,
  month TEXT NOT NULL,
  carbon_g_per_kwh REAL NOT NULL,
  emission_factor_type TEXT NOT NULL DEFAULT 'lifecycle',
  is_estimated INTEGER,
  estimation_method TEXT,
  source TEXT NOT NULL DEFAULT 'Electricity Maps carbon-intensity',
  updated_at_utc TEXT NOT NULL,
  PRIMARY KEY (electricity_maps_zone_id, month, emission_factor_type)
);
```

Scoring formula:

```text
carbon_value_usd_per_mwh =
  carbon_g_per_kwh / 1000 * carbon_price_usd_per_ton
```

Reason:

```text
1 MWh = 1000 kWh
gCO2/kWh * 1000 kWh = gCO2/MWh
1 metric ton = 1,000,000 g
tonsCO2/MWh = carbon_g_per_kwh / 1000
```

Example:

```text
400 gCO2/kWh / 1000 * $50/ton = $20/MWh
```

## Source 5: Electricity Maps Electricity Mix

Endpoint:

```text
GET https://api.electricitymap.org/v4/electricity-mix/past-range
```

Query shape:

```text
?zone=US-SW-AZPS
&start=2026-02-01T00:00:00Z
&end=2026-03-01T00:00:00Z
&temporalGranularity=monthly
&breakdownType=flow-traced
```

Use `flow-traced` for consumer-side electricity available in the zone. Use `normal` when we want local generation mix only.

Normalized SQLite table:

```sql
CREATE TABLE IF NOT EXISTS zone_electricity_mix_monthly (
  electricity_maps_zone_id TEXT NOT NULL,
  month TEXT NOT NULL,
  solar_mwh REAL,
  wind_mwh REAL,
  hydro_mwh REAL,
  coal_mwh REAL,
  gas_mwh REAL,
  oil_mwh REAL,
  nuclear_mwh REAL,
  biomass_mwh REAL,
  geothermal_mwh REAL,
  unknown_mwh REAL,
  breakdown_type TEXT NOT NULL DEFAULT 'flow-traced',
  is_estimated INTEGER,
  source TEXT NOT NULL DEFAULT 'Electricity Maps electricity-mix',
  updated_at_utc TEXT NOT NULL,
  PRIMARY KEY (electricity_maps_zone_id, month, breakdown_type)
);
```

## Source 6: Electricity Maps Renewable And Carbon-Free Percent

Renewable percent:

```text
GET https://api.electricitymap.org/v4/renewable-energy/past-range
  ?zone=US-SW-AZPS
  &start=2026-02-01T00:00:00Z
  &end=2026-03-01T00:00:00Z
  &temporalGranularity=monthly
```

Carbon-free percent:

```text
GET https://api.electricitymap.org/v4/carbon-free-energy/past-range
  ?zone=US-SW-AZPS
  &start=2026-02-01T00:00:00Z
  &end=2026-03-01T00:00:00Z
  &temporalGranularity=monthly
```

Normalized SQLite table:

```sql
CREATE TABLE IF NOT EXISTS zone_clean_energy_monthly (
  electricity_maps_zone_id TEXT NOT NULL,
  month TEXT NOT NULL,
  renewable_pct REAL,
  carbon_free_pct REAL,
  is_estimated INTEGER,
  source TEXT NOT NULL DEFAULT 'Electricity Maps clean-energy',
  updated_at_utc TEXT NOT NULL,
  PRIMARY KEY (electricity_maps_zone_id, month)
);
```

## State-Zone Bridge Table

SQLite should own the bridge:

```sql
CREATE TABLE IF NOT EXISTS state_electricity_maps_zones (
  state_code TEXT NOT NULL,
  state_name TEXT NOT NULL,
  electricity_maps_zone_id TEXT NOT NULL,
  weight REAL NOT NULL DEFAULT 1.0,
  mapping_method TEXT NOT NULL DEFAULT 'manual_mvp',
  updated_at_utc TEXT NOT NULL,
  PRIMARY KEY (state_code, electricity_maps_zone_id)
);
```

We also have a CSV seed file:

```text
data/processed/state_electricity_maps_zones.csv
```

Use it to seed SQLite once, then treat the database table as canonical.

Current mapping is manual/heuristic. Good enough for MVP. Improve later by sampling points inside each state and calling:

```text
GET /v4/zone?lat=<lat>&lon=<lon>
```

Initial MVP rule:

```text
weight = 1 / number_of_zones_for_state
```

Better later:

```text
weight = sampled_points_in_zone / total_sampled_points_in_state
```

## Final Processed View

Join path:

```text
state_retail_price_monthly.state_code
  -> state_generation_mix_monthly.state_code
  -> state_electricity_maps_zones.state_code
  -> zone_carbon_monthly.electricity_maps_zone_id
  -> zone_clean_energy_monthly.electricity_maps_zone_id
```

Create the processed view in SQLite:

```sql
CREATE VIEW IF NOT EXISTS state_zone_energy_profile_monthly AS
SELECT
  p.state_code,
  p.state_name,
  b.electricity_maps_zone_id,
  p.month,
  p.avg_electricity_cost_cents_per_kwh,
  p.avg_electricity_cost_cents_per_kwh * 10 AS avg_electricity_cost_usd_per_mwh,
  g.pct_solar AS pct_solar_state,
  g.pct_wind AS pct_wind_state,
  g.pct_hydro AS pct_hydro_state,
  g.pct_fossil AS pct_fossil_state,
  z.carbon_g_per_kwh AS carbon_g_per_kwh_zone,
  c.renewable_pct AS renewable_pct_zone,
  c.carbon_free_pct AS carbon_free_pct_zone,
  b.weight AS mapping_weight
FROM state_retail_price_monthly p
JOIN state_generation_mix_monthly g
  ON g.state_code = p.state_code
 AND g.month = p.month
JOIN state_electricity_maps_zones b
  ON b.state_code = p.state_code
LEFT JOIN zone_carbon_monthly z
  ON z.electricity_maps_zone_id = b.electricity_maps_zone_id
 AND z.month = p.month
 AND z.emission_factor_type = 'lifecycle'
LEFT JOIN zone_clean_energy_monthly c
  ON c.electricity_maps_zone_id = b.electricity_maps_zone_id
 AND c.month = p.month;
```

Use a view while data volume is small. If queries become slow, materialize this as a table after each ingestion run.

## Backend Scoring Integration

Each grid cell should have:

```text
cell_id
lat
lon
state_code
electricity_maps_zone_id
```

Hydrate scoring fields:

```text
price_usd_per_mwh_mean = avg_electricity_cost_cents_per_kwh * 10
carbon_g_per_kwh_mean = carbon_g_per_kwh_zone
```

Current Lumen scoring formula:

```text
LCOE = (CAPEX * CRF + OPEX) / (CF * 8760)
Revenue = price_usd_per_mwh_mean
Carbon_Value = carbon_g_per_kwh_mean / 1000 * carbon_price_usd_per_ton
Composite_Score = cost_weight * LCOE
                - revenue_weight * Revenue
                - carbon_weight * Carbon_Value
```

Caveat:

```text
avg_electricity_cost_cents_per_kwh is retail electricity price.
It is a regional cost/value proxy, not wholesale generator revenue.
```

Later, replace revenue with ISO/LMP or wholesale price data where available. Keep retail price as a useful affordability/context feature.

## Ingestion Order

1. Fetch EIA retail price by state/month.
2. Fetch EIA generation by state/source/month.
3. Seed or update `state_electricity_maps_zones` in SQLite.
4. Fetch Electricity Maps carbon for each zone/month.
5. Fetch Electricity Maps mix and clean-energy percentages for each zone/month.
6. Save raw API responses into `raw_api_responses`.
7. Normalize raw responses into SQLite tables.
8. Query `state_zone_energy_profile_monthly`.
9. Join cells to `state_code` and `electricity_maps_zone_id`.
10. Feed processed features to backend scoring.

## Recommended Storage Layout

```text
data/processed/lumen_energy.sqlite

Optional exports:
data/processed/state_energy_profile.csv
data/processed/state_electricity_maps_zones.csv
data/processed/state_zone_energy_profile_monthly.csv
```

SQLite is canonical. CSV is for sharing/debugging only.

## Sources

- [EIA API documentation](https://www.eia.gov/opendata/documentation.php)
- [EIA retail sales data browser](https://www.eia.gov/opendata/index.php/browser/electricity/retail-sales)
- [EIA electric power operational data browser](https://www.eia.gov/opendata/index.php/browser/electricity/electric-power-operational-data)
- [EIA state generation workbook](https://www.eia.gov/electricity/data/state/)
- [Electricity Maps API reference](https://app.electricitymaps.com/developer-hub/api/reference)
- [Electricity Maps API docs](https://app.electricitymaps.com/docs)
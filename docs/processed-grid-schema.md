# Processed Grid Cell Dataset Schema

## Purpose

This dataset is the engine and API fixture for precomputed CONUS grid-cell analytics.
Each row represents one grid cell with the baseline attributes needed for score
calculation and endpoint development before the full data pipeline is ready.

## What "Schema" Means Here

In this repo, the processed dataset schema is the contract for the fixture data.
It defines:

- which columns must exist
- what each column means
- what type of value each column should contain
- what units those values use

This is a data schema, not a SQL database schema. It describes the shape of the
processed grid-cell dataset that the engine and API load into Python.

## Canonical Fixture

- File: `data/processed/lumen_cells.csv`
- Loader: `backend/app/data/processed_dataset.py`
- Generator: `scripts/create_demo_grid_fixture.py`

## Row Definition

Each row is a single processed grid cell in WGS84 (`EPSG:4326`) coordinates.

| Column | Type | Units | Description |
| --- | --- | --- | --- |
| `cell_id` | string | none | Stable unique identifier for the grid cell fixture row |
| `lat` | float64 | decimal degrees | Cell centroid latitude |
| `lon` | float64 | decimal degrees | Cell centroid longitude |
| `region` | string | none | Human-readable US region label for filtering and demos |
| `solar_cf` | float64 | fraction | Baseline solar capacity factor on a 0-1 scale |
| `wind_cf` | float64 | fraction | Baseline wind capacity factor on a 0-1 scale |
| `avg_price_per_mwh` | float64 | USD/MWh | Baseline average wholesale power price |
| `carbon_intensity_g_per_kwh` | float64 | g/kWh | Baseline grid carbon intensity |
| `nearest_transmission_km` | float64 | km | Distance to nearest transmission asset |

## Constraints

- `cell_id` must be unique.
- `lat` must be within CONUS-friendly latitude bounds for the fixture.
- `lon` must be within CONUS-friendly longitude bounds for the fixture.
- `solar_cf` and `wind_cf` must be in the inclusive range `[0.0, 1.0]`.
- `avg_price_per_mwh`, `carbon_intensity_g_per_kwh`, and
  `nearest_transmission_km` must be non-negative.
- The demo fixture must include at least 25 rows across varied US regions.

## Example Row

```csv
cell_id,lat,lon,region,solar_cf,wind_cf,avg_price_per_mwh,carbon_intensity_g_per_kwh,nearest_transmission_km
tx_001,31.9686,-99.9018,Texas,0.27,0.39,34.0,390.0,3.8
```

Interpretation:

- `tx_001` is the stable identifier for one grid cell
- `31.9686, -99.9018` is the cell centroid in latitude/longitude
- `Texas` is the region label
- `solar_cf=0.27` means a baseline solar capacity factor of 27%
- `wind_cf=0.39` means a baseline wind capacity factor of 39%
- `avg_price_per_mwh=34.0` means a baseline price of 34 USD/MWh
- `carbon_intensity_g_per_kwh=390.0` means 390 grams of CO2 per kWh
- `nearest_transmission_km=3.8` means the nearest transmission asset is 3.8 km away

## How To Use It

### 1. Read the raw fixture file

The checked-in fixture lives at:

- `data/processed/lumen_cells.csv`

You can open it directly with pandas:

```python
import pandas as pd

df = pd.read_csv("data/processed/lumen_cells.csv")
print(df.head())
```

### 2. Load it through the repo loader

Use the shared loader when backend or engine code needs the fixture:

```python
from backend.app.data.processed_dataset import load_processed_cells_frame

df = load_processed_cells_frame()
print(df.head())
```

This returns a pandas DataFrame with the required dataset columns.

### 3. Load typed records instead of a DataFrame

If you want plain Python objects without pandas logic in the caller:

```python
from backend.app.data.processed_dataset import load_processed_cell_records

records = load_processed_cell_records()
print(records[0])
```

This returns a list of `ProcessedCellRecord` objects.

### 4. Regenerate the demo fixture

If the demo fixture needs to be rebuilt deterministically:

```powershell
python scripts\create_demo_grid_fixture.py
```

That command:

- rewrites `data/processed/lumen_cells.csv`
- prints the fixture table to the terminal

## Typical Use Cases

- Backend/API development: load the fixture and build endpoint responses
- Engine development: run scoring logic over the grid cells
- Frontend integration: use backend responses built from stable fixture rows
- Testing: validate feature behavior without waiting for the full pipeline

## Demo Fixture Notes

- The checked-in dataset is deterministic and synthetic.
- Values are intentionally plausible but are not sourced from production-grade
  pipeline outputs.
- The fixture exists to unblock endpoint, scoring, and UI development while the
  real preprocessing jobs are still in progress.

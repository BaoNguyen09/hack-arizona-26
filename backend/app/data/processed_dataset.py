from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

DATASET_COLUMNS = [
    "cell_id",
    "lat",
    "lon",
    "state_code",
    "state_name",
    "electricity_maps_zone_id",
    "month",
    "solar_cf",
    "wind_cf",
    "avg_electricity_cost_cents_per_kwh",
    "pct_solar_state",
    "pct_wind_state",
    "pct_hydro_state",
    "pct_fossil_state",
    "carbon_g_per_kwh_zone",
    "renewable_pct_zone",
    "carbon_free_pct_zone",
]
DEFAULT_DATASET_PATH = Path("data/processed/lumen_cells.csv")


@dataclass(frozen=True)
class ProcessedCellRecord:
    cell_id: str
    lat: float
    lon: float
    state_code: str
    state_name: str
    electricity_maps_zone_id: str
    month: str
    solar_cf: float
    wind_cf: float
    avg_electricity_cost_cents_per_kwh: float
    pct_solar_state: float
    pct_wind_state: float
    pct_hydro_state: float
    pct_fossil_state: float
    carbon_g_per_kwh_zone: float
    renewable_pct_zone: float
    carbon_free_pct_zone: float


def _parse_row(row: dict[str, str]) -> ProcessedCellRecord:
    missing = [column for column in DATASET_COLUMNS if column not in row]
    if missing:
        raise ValueError(f"Processed dataset is missing required columns: {missing}")

    return ProcessedCellRecord(
        cell_id=row["cell_id"],
        lat=float(row["lat"]),
        lon=float(row["lon"]),
        state_code=row["state_code"],
        state_name=row["state_name"],
        electricity_maps_zone_id=row["electricity_maps_zone_id"],
        month=row["month"],
        solar_cf=float(row["solar_cf"]),
        wind_cf=float(row["wind_cf"]),
        avg_electricity_cost_cents_per_kwh=float(row["avg_electricity_cost_cents_per_kwh"]),
        pct_solar_state=float(row["pct_solar_state"]),
        pct_wind_state=float(row["pct_wind_state"]),
        pct_hydro_state=float(row["pct_hydro_state"]),
        pct_fossil_state=float(row["pct_fossil_state"]),
        carbon_g_per_kwh_zone=float(row["carbon_g_per_kwh_zone"]),
        renewable_pct_zone=float(row["renewable_pct_zone"]),
        carbon_free_pct_zone=float(row["carbon_free_pct_zone"]),
    )


def load_as_scoring_dataframe(dataset_path: Path | str = DEFAULT_DATASET_PATH):
    """Load the CSV and return a DataFrame compatible with the scoring engine.

    Maps CSV columns to the standard column names expected by ``score_all_cells``:
    - solar_cf_mean, wind_cf_mean
    - price_usd_per_mwh_mean (converted from cents/kWh * 10)
    - carbon_g_per_kwh_mean
    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("pandas is required") from exc

    raw = pd.read_csv(Path(dataset_path))

    # Newer pipelines may export a scoring-ready CSV directly (already using the
    # processed store column names). Detect and pass-through in that case.
    scoring_cols = {
        "cell_id",
        "lat",
        "lon",
        "solar_cf_mean",
        "wind_cf_mean",
        "price_usd_per_mwh_mean",
        "carbon_g_per_kwh_mean",
    }
    if scoring_cols.issubset(set(raw.columns)):
        keep = [
            "cell_id",
            "lat",
            "lon",
            "solar_cf_mean",
            "wind_cf_mean",
            "price_usd_per_mwh_mean",
            "carbon_g_per_kwh_mean",
        ]
        for optional in ("nearest_transmission_km", "price_hub_id", "grid_zone_id"):
            if optional in raw.columns:
                keep.append(optional)
        result = raw.loc[:, keep].copy()
        # Ensure optional columns exist for the scoring/services layer.
        for optional in ("nearest_transmission_km", "price_hub_id", "grid_zone_id"):
            if optional not in result.columns:
                result[optional] = None
        return result

    # Legacy demo CSV format (client-side dataset contract).
    frame = load_processed_cells_frame(dataset_path)
    return pd.DataFrame(
        {
            "cell_id": frame["cell_id"],
            "lat": frame["lat"],
            "lon": frame["lon"],
            "solar_cf_mean": frame["solar_cf"],
            "wind_cf_mean": frame["wind_cf"],
            # cents/kWh → $/MWh: multiply by 10
            "price_usd_per_mwh_mean": frame["avg_electricity_cost_cents_per_kwh"] * 10,
            "carbon_g_per_kwh_mean": frame["carbon_g_per_kwh_zone"],
            "nearest_transmission_km": None,
            "price_hub_id": frame["electricity_maps_zone_id"],
            "grid_zone_id": frame["electricity_maps_zone_id"],
        }
    )


def load_processed_cells_frame(dataset_path: Path | str = DEFAULT_DATASET_PATH):
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("pandas is required to load the processed dataset as a DataFrame") from exc

    path = Path(dataset_path)
    frame = pd.read_csv(path)
    missing = [column for column in DATASET_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Processed dataset is missing required columns: {missing}")
    return frame.loc[:, DATASET_COLUMNS]


def load_processed_cell_records(
    dataset_path: Path | str = DEFAULT_DATASET_PATH,
) -> list[ProcessedCellRecord]:
    path = Path(dataset_path)
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [_parse_row(row) for row in reader]

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

DATASET_COLUMNS = [
    "cell_id",
    "lat",
    "lon",
    "region",
    "solar_cf",
    "wind_cf",
    "avg_price_per_mwh",
    "carbon_intensity_g_per_kwh",
    "nearest_transmission_km",
]
DEFAULT_DATASET_PATH = Path("data/processed/lumen_cells.csv")


@dataclass(frozen=True)
class ProcessedCellRecord:
    cell_id: str
    lat: float
    lon: float
    region: str
    solar_cf: float
    wind_cf: float
    avg_price_per_mwh: float
    carbon_intensity_g_per_kwh: float
    nearest_transmission_km: float


def _parse_row(row: dict[str, str]) -> ProcessedCellRecord:
    missing = [column for column in DATASET_COLUMNS if column not in row]
    if missing:
        raise ValueError(f"Processed dataset is missing required columns: {missing}")

    return ProcessedCellRecord(
        cell_id=row["cell_id"],
        lat=float(row["lat"]),
        lon=float(row["lon"]),
        region=row["region"],
        solar_cf=float(row["solar_cf"]),
        wind_cf=float(row["wind_cf"]),
        avg_price_per_mwh=float(row["avg_price_per_mwh"]),
        carbon_intensity_g_per_kwh=float(row["carbon_intensity_g_per_kwh"]),
        nearest_transmission_km=float(row["nearest_transmission_km"]),
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

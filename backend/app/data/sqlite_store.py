"""SQLite-backed processed store.

Loads the latest (or specified) feature snapshot from the Lumen SQLite DB into
memory and provides the same interface as `ProcessedStore` for scoring.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from shapely import STRtree


class SqliteProcessedStore:
    """In-memory cache backed by SQLite tables."""

    _instance: "SqliteProcessedStore | None" = None

    def __init__(self) -> None:
        self._is_loaded = False
        self._df: pd.DataFrame | None = None
        self._cell_id_index: dict[str, int] | None = None
        self._spatial_index: STRtree | None = None  # type: ignore[name-defined]
        self._geometry_to_index: dict[int, int] | None = None
        self._db_path: Path | None = None
        self._snapshot_id: str | None = None

    @classmethod
    def get_instance(cls) -> "SqliteProcessedStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def row_count(self) -> int:
        return 0 if self._df is None else len(self._df)

    def load(self, db_path: str | Path, snapshot_id: str | None = None) -> None:
        """Load features from SQLite into a DataFrame and build indices."""
        self._db_path = Path(db_path)
        if not self._db_path.exists():
            raise FileNotFoundError(f"SQLite DB not found: {self._db_path}")

        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            snap = snapshot_id or _latest_snapshot_id(conn)
            if snap is None:
                raise RuntimeError("No feature snapshots found in SQLite DB.")
            self._snapshot_id = snap

            df = pd.read_sql_query(
                """
                SELECT
                    suf.spatial_unit_id AS cell_id,
                    su.lat AS lat,
                    su.lon AS lon,
                    suf.solar_cf_mean,
                    suf.wind_cf_mean,
                    suf.price_usd_per_mwh_mean,
                    suf.carbon_g_per_kwh_mean,
                    suf.nearest_transmission_km,
                    suf.price_hub_id,
                    suf.grid_zone_id,
                    suf.load_gw,
                    suf.renewable_percent
                FROM spatial_unit_features suf
                JOIN spatial_units su
                  ON su.spatial_unit_id = suf.spatial_unit_id
                WHERE suf.snapshot_id = ?
                """,
                conn,
                params=(snap,),
            )

        self._df = df
        self._cell_id_index = {
            str(cell_id): idx for idx, cell_id in enumerate(self._df["cell_id"].astype(str))
        }
        self._build_spatial_index()
        self._is_loaded = True

    def _build_spatial_index(self) -> None:
        # STRtree over POINT geometries for nearest lookup.
        from shapely import STRtree  # noqa: PLC0415
        from shapely.geometry import Point  # noqa: PLC0415

        if self._df is None:
            self._spatial_index = None
            self._geometry_to_index = None
            return

        geometries = [Point(lon, lat) for lon, lat in zip(self._df["lon"], self._df["lat"])]
        self._spatial_index = STRtree(geometries)
        self._geometry_to_index = {id(geom): idx for idx, geom in enumerate(geometries)}

    def get_all_cells(self) -> pd.DataFrame:
        if self._df is None:
            raise RuntimeError("Store not loaded. Call load() first.")
        return self._df.copy()

    def get_cell_by_id(self, cell_id: str | int) -> pd.Series | None:
        if self._df is None or self._cell_id_index is None:
            raise RuntimeError("Store not loaded. Call load() first.")

        idx = self._cell_id_index.get(str(cell_id))
        if idx is None:
            return None
        return self._df.iloc[idx].copy()

    def get_nearest_cell(self, lat: float, lon: float) -> pd.Series | None:
        if self._df is None or self._spatial_index is None or self._geometry_to_index is None:
            raise RuntimeError("Store not loaded. Call load() first.")

        from shapely.geometry import Point  # noqa: PLC0415

        point = Point(lon, lat)
        nearest_geom = self._spatial_index.nearest(point)
        if nearest_geom is None:
            return None

        idx = self._geometry_to_index.get(id(nearest_geom))
        if idx is None:
            return None
        return self._df.iloc[idx].copy()

    def get_column(self, name: str) -> np.ndarray:
        if self._df is None:
            raise RuntimeError("Store not loaded. Call load() first.")
        return self._df[name].to_numpy()


def _latest_snapshot_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT snapshot_id FROM feature_snapshots ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return str(row["snapshot_id"])


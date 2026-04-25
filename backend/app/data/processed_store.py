"""Processed artifact store with caching and fast lookups.

Loads GeoPackage data into memory and provides vectorized access for scoring.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    import geopandas as gpd
    from shapely import STRtree

from backend.app.data.contracts import (
    LAYER_NAME,
    validate_processed_artifact,
    get_column_names,
    print_validation_report,
)


class ProcessedStore:
    """In-memory store for processed cell data with fast lookups.

    Loads a GeoPackage file once at startup and keeps it cached for fast
    vectorized operations. Supports lookups by cell_id and nearest neighbor
    queries by lat/lon.
    """

    _instance: ProcessedStore | None = None
    _gdf: gpd.GeoDataFrame | None = None  # type: ignore[name-defined]
    _df: pd.DataFrame | None = None  # Non-geometry version for fast numeric ops
    _cell_id_index: dict[str | int, int] | None = None  # cell_id -> row index
    _spatial_index: STRtree | None = None  # type: ignore[name-defined]
    _geometry_to_index: dict[int, int] | None = None  # id(geometry) -> row index
    _is_loaded: bool = False

    @classmethod
    def get_instance(cls) -> "ProcessedStore":
        """Get the singleton instance of the store."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load(self, gpkg_path: str | Path, validate: bool = True) -> None:
        """Load processed data from a GeoPackage file.

        Args:
            gpkg_path: Path to the GeoPackage file
            validate: Whether to validate the schema against the contract

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If validation fails
        """
        import geopandas as gpd  # noqa: PLC0415

        path = Path(gpkg_path)
        if not path.exists():
            raise FileNotFoundError(f"Processed artifact not found: {path}")

        # Load the layer
        self._gdf = gpd.read_file(path, layer=LAYER_NAME)

        if validate:
            result = validate_processed_artifact(self._gdf)
            if not result["valid"]:
                print_validation_report(result)
                raise ValueError(f"Processed artifact validation failed for {path}")

        # Create a non-geometry DataFrame for fast numeric operations
        # This avoids geometry overhead during vectorized scoring
        self._df = pd.DataFrame(self._gdf.drop(columns=["geometry"]))

        # Build cell_id lookup index
        self._cell_id_index = {
            cell_id: idx for idx, cell_id in enumerate(self._df["cell_id"])
        }

        # Build spatial index for nearest neighbor queries
        from shapely import STRtree  # noqa: PLC0415

        geometries = list(self._gdf.geometry)
        self._spatial_index = STRtree(geometries)
        # STRtree returns geometries; keep a stable mapping to dataframe row index
        self._geometry_to_index = {id(geom): idx for idx, geom in enumerate(geometries)}

        self._is_loaded = True

    def load_from_dataframe(self, df: pd.DataFrame, validate: bool = True) -> None:
        """Load processed data directly from a pandas DataFrame.

        Useful for tests and notebooks where you have data already in memory
        and don't need to read a GeoPackage file. Spatial (lat/lon) lookups
        are unavailable when loading this way; use ``get_cell_by_id`` instead.

        Args:
            df: DataFrame matching the processed artifact contract (no geometry needed)
            validate: Whether to validate the schema against the contract

        Raises:
            ValueError: If validation fails
        """
        if validate:
            result = validate_processed_artifact(df)
            if not result["valid"]:
                print_validation_report(result)
                raise ValueError("DataFrame validation failed against processed artifact contract")

        self._df = df.copy()
        self._gdf = None
        self._spatial_index = None
        self._geometry_to_index = None

        self._cell_id_index = {
            cell_id: idx for idx, cell_id in enumerate(self._df["cell_id"])
        }
        self._is_loaded = True

    def is_loaded(self) -> bool:
        """Check if data has been loaded."""
        return self._is_loaded

    @property
    def row_count(self) -> int:
        """Return the number of cells in the dataset."""
        if self._df is None:
            return 0
        return len(self._df)

    @property
    def columns(self) -> list[str]:
        """Return available column names."""
        if self._df is None:
            return []
        return list(self._df.columns)

    def get_all_cells(self) -> pd.DataFrame:
        """Get all cells as a DataFrame (no geometry).

        Returns:
            DataFrame with all cell data for vectorized operations
        """
        if self._df is None:
            raise RuntimeError("Store not loaded. Call load() first.")
        return self._df.copy()

    def get_cell_by_id(self, cell_id: str | int) -> pd.Series | None:
        """Get a single cell by its ID.

        Args:
            cell_id: The cell identifier

        Returns:
            Series with cell data, or None if not found
        """
        if self._cell_id_index is None or self._df is None:
            raise RuntimeError("Store not loaded. Call load() first.")

        idx = self._cell_id_index.get(cell_id)
        if idx is None:
            return None
        return self._df.iloc[idx].copy()

    def get_nearest_cell(self, lat: float, lon: float) -> pd.Series | None:
        """Get the nearest cell to a lat/lon point.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Series with nearest cell data, or None if no cells
        """
        if self._spatial_index is None or self._gdf is None or self._df is None:
            raise RuntimeError("Store not loaded. Call load() first.")

        from shapely.geometry import Point  # noqa: PLC0415

        point = Point(lon, lat)
        nearest_geom = self._spatial_index.nearest(point)
        if nearest_geom is None:
            return None

        if self._geometry_to_index is None:
            raise RuntimeError("Spatial index mapping not built.")

        idx = self._geometry_to_index.get(id(nearest_geom))
        if idx is None:
            # Fallback: slow path search (should be rare)
            try:
                idx = int(self._gdf.geometry.equals(nearest_geom).to_numpy().nonzero()[0][0])
            except Exception:
                return None

        return self._df.iloc[idx].copy()

    def get_column(self, name: str) -> np.ndarray:
        """Get a column as a numpy array for vectorized operations.

        Args:
            name: Column name

        Returns:
            Numpy array of column values
        """
        if self._df is None:
            raise RuntimeError("Store not loaded. Call load() first.")
        return self._df[name].to_numpy()

    def get_capacity_factor(self, technology: str) -> np.ndarray:
        """Get capacity factor column for a technology.

        Args:
            technology: 'solar' or 'wind'

        Returns:
            Numpy array of capacity factors (0-1)
        """
        if technology == "solar":
            return self.get_column("solar_cf_mean")
        elif technology == "wind":
            return self.get_column("wind_cf_mean")
        else:
            raise ValueError(f"Unknown technology: {technology}. Use 'solar' or 'wind'.")

    def get_summary_stats(self) -> dict:
        """Get summary statistics for the loaded dataset.

        Returns:
            Dictionary with summary information
        """
        if self._df is None:
            return {"loaded": False}

        required_cols = get_column_names()["required"]
        stats = {
            "loaded": True,
            "row_count": len(self._df),
            "columns": list(self._df.columns),
            "required_columns_present": all(c in self._df.columns for c in required_cols),
        }

        # Add numeric summaries for key columns
        for col in ["solar_cf_mean", "wind_cf_mean", "price_usd_per_mwh_mean", "carbon_g_per_kwh_mean"]:
            if col in self._df.columns:
                stats[f"{col}_range"] = {
                    "min": float(self._df[col].min()),
                    "max": float(self._df[col].max()),
                    "mean": float(self._df[col].mean()),
                }

        return stats


def get_store() -> ProcessedStore:
    """Get the singleton ProcessedStore instance.

    Returns:
        The global ProcessedStore instance
    """
    return ProcessedStore.get_instance()

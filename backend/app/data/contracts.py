"""GeoPackage processed artifact contract definitions.

Defines the expected schema for the lumen_cells layer and validation utilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, get_args

import pandas as pd

if TYPE_CHECKING:
    import geopandas as gpd

TechnologyType = Literal["solar", "wind"]
TECHNOLOGY_TYPES: tuple[str, ...] = get_args(TechnologyType)

LAYER_NAME: str = "lumen_cells"


@dataclass(frozen=True)
class ColumnSpec:
    """Specification for a required column in the processed artifact."""

    name: str
    dtype: str
    description: str
    min_value: float | None = None
    max_value: float | None = None


# Required columns for MVP scored cell rendering
# Supports Deck.gl heatmap, grid, scatter, H3 layers
REQUIRED_COLUMNS: list[ColumnSpec] = [
    ColumnSpec("cell_id", "string", "Unique cell identifier"),
    ColumnSpec("lat", "float64", "Cell centroid latitude", -90.0, 90.0),
    ColumnSpec("lon", "float64", "Cell centroid longitude", -180.0, 180.0),
    ColumnSpec("solar_cf_mean", "float64", "Mean solar capacity factor (0-1)", 0.0, 1.0),
    ColumnSpec("wind_cf_mean", "float64", "Mean wind capacity factor (0-1)", 0.0, 1.0),
    ColumnSpec("price_usd_per_mwh_mean", "float64", "Mean wholesale price USD/MWh", 0.0, None),
    ColumnSpec("carbon_g_per_kwh_mean", "float64", "Mean grid carbon intensity gCO2/kWh", 0.0, None),
]

# Optional columns that enhance the analysis but aren't strictly required
OPTIONAL_COLUMNS: list[ColumnSpec] = [
    ColumnSpec("nearest_transmission_km", "float64", "Distance to nearest transmission line (km)", 0.0, None),
    ColumnSpec("price_hub_id", "string", "Nearest wholesale price hub identifier"),
    ColumnSpec("grid_zone_id", "string", "Grid balancing authority or zone identifier"),
]

ALL_COLUMNS: list[ColumnSpec] = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


def validate_processed_artifact(gdf: gpd.GeoDataFrame | pd.DataFrame) -> dict:
    """Validate that a GeoDataFrame or DataFrame matches the processed artifact contract.

    Args:
        gdf: The data to validate

    Returns:
        Validation result dictionary with keys:
        - valid: bool - whether validation passed
        - missing_required: list[str] - missing required column names
        - present_optional: list[str] - optional columns that are present
        - type_errors: list[str] - columns with wrong types
        - range_errors: list[str] - columns with values outside expected ranges
        - row_count: int - number of rows
    """
    result: dict = {
        "valid": True,
        "missing_required": [],
        "present_optional": [],
        "type_errors": [],
        "range_errors": [],
        "row_count": len(gdf),
    }

    # Check required columns
    for spec in REQUIRED_COLUMNS:
        if spec.name not in gdf.columns:
            result["missing_required"].append(spec.name)
            result["valid"] = False
            continue

        # Check dtype (loose match for numeric types)
        col = gdf[spec.name]
        actual_dtype = str(col.dtype)

        if spec.dtype == "float64" and not pd.api.types.is_float_dtype(col):
            result["type_errors"].append(f"{spec.name}: expected float64, got {actual_dtype}")
            result["valid"] = False
        elif spec.dtype == "string" and not pd.api.types.is_string_dtype(col):
            # Try to check if it can be treated as string/object
            if not (pd.api.types.is_object_dtype(col) or pd.api.types.is_string_dtype(col)):
                result["type_errors"].append(f"{spec.name}: expected string, got {actual_dtype}")
                result["valid"] = False

        # Check value ranges if specified
        if spec.min_value is not None and col.min() < spec.min_value:
            result["range_errors"].append(
                f"{spec.name}: min value {col.min()} below expected {spec.min_value}"
            )
            result["valid"] = False
        if spec.max_value is not None and col.max() > spec.max_value:
            result["range_errors"].append(
                f"{spec.name}: max value {col.max()} above expected {spec.max_value}"
            )
            result["valid"] = False

    # Check optional columns
    for spec in OPTIONAL_COLUMNS:
        if spec.name in gdf.columns:
            result["present_optional"].append(spec.name)

    return result


def get_column_names() -> dict[str, list[str]]:
    """Get organized lists of column names by category.

    Returns:
        Dictionary with keys: required, optional, all
    """
    return {
        "required": [c.name for c in REQUIRED_COLUMNS],
        "optional": [c.name for c in OPTIONAL_COLUMNS],
        "all": [c.name for c in ALL_COLUMNS],
    }


def print_validation_report(result: dict) -> None:
    """Print a human-readable validation report."""
    print(f"Processed Artifact Validation Report")
    print(f"=" * 50)
    print(f"Valid: {result['valid']}")
    print(f"Row count: {result['row_count']}")
    print()

    if result["missing_required"]:
        print(f"Missing required columns: {', '.join(result['missing_required'])}")
    else:
        print("All required columns present")

    if result["present_optional"]:
        print(f"Present optional columns: {', '.join(result['present_optional'])}")
    else:
        print("No optional columns present")

    if result["type_errors"]:
        print(f"\nType errors:")
        for err in result["type_errors"]:
            print(f"  - {err}")

    if result["range_errors"]:
        print(f"\nRange errors:")
        for err in result["range_errors"]:
            print(f"  - {err}")

    print("=" * 50)

#!/usr/bin/env python3
"""CLI utility to validate processed artifact GeoPackage files.

Usage:
    python scripts/validate_processed_artifact.py [path_to_gpkg]

If no path is provided, uses the default from settings.
"""

import sys
from pathlib import Path

import geopandas as gpd

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.core.config import settings
from backend.app.data.contracts import (
    LAYER_NAME,
    print_validation_report,
    validate_processed_artifact,
)


def main() -> int:
    """Validate a processed artifact file."""
    # Get path from command line or use default
    if len(sys.argv) > 1:
        gpkg_path = sys.argv[1]
    else:
        gpkg_path = settings.processed_dataset_path

    print(f"Validating: {gpkg_path}")
    print()

    path = Path(gpkg_path)
    if not path.exists():
        print(f"Error: File not found: {path}")
        return 1

    try:
        # Load the layer
        print(f"Loading layer '{LAYER_NAME}'...")
        gdf = gpd.read_file(path, layer=LAYER_NAME)
        print(f"Loaded {len(gdf)} rows")
        print()

        # Validate
        result = validate_processed_artifact(gdf)
        print_validation_report(result)

        # Additional stats
        if result["valid"]:
            print("\nColumn Statistics:")
            print("-" * 30)

            numeric_cols = [
                "lat", "lon",
                "solar_cf_mean", "wind_cf_mean",
                "price_usd_per_mwh_mean",
                "carbon_g_per_kwh_mean",
            ]

            for col in numeric_cols:
                if col in gdf.columns:
                    print(f"  {col}:")
                    print(f"    min:  {gdf[col].min():.4f}")
                    print(f"    max:  {gdf[col].max():.4f}")
                    print(f"    mean: {gdf[col].mean():.4f}")
                    print(f"    null: {gdf[col].isna().sum()} / {len(gdf)}")

            if "nearest_transmission_km" in gdf.columns:
                print(f"  nearest_transmission_km:")
                print(f"    present: {gdf['nearest_transmission_km'].notna().sum()} / {len(gdf)}")

        return 0 if result["valid"] else 1

    except Exception as e:
        print(f"Error loading or validating file: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""Tests for the processed artifact contract validator.

All tests use plain pandas DataFrames (no GeoPackage / geopandas needed).
"""

import pandas as pd
import pytest

from backend.app.data.contracts import (
    LAYER_NAME,
    REQUIRED_COLUMNS,
    get_column_names,
    validate_processed_artifact,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_valid_df(**overrides) -> pd.DataFrame:
    """Return a minimal valid DataFrame; overrides replace individual columns."""
    data = {
        "cell_id": ["a", "b"],
        "lat": [30.0, 40.0],
        "lon": [-100.0, -90.0],
        "solar_cf_mean": [0.25, 0.20],
        "wind_cf_mean": [0.40, 0.35],
        "price_usd_per_mwh_mean": [34.0, 28.0],
        "carbon_g_per_kwh_mean": [400.0, 380.0],
    }
    data.update(overrides)
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Layer name constant
# ---------------------------------------------------------------------------


def test_layer_name_is_lumen_cells() -> None:
    assert LAYER_NAME == "lumen_cells"


# ---------------------------------------------------------------------------
# Valid DataFrame passes
# ---------------------------------------------------------------------------


def test_valid_dataframe_passes() -> None:
    result = validate_processed_artifact(make_valid_df())
    assert result["valid"] is True
    assert result["missing_required"] == []
    assert result["type_errors"] == []
    assert result["range_errors"] == []


def test_valid_row_count_recorded() -> None:
    result = validate_processed_artifact(make_valid_df())
    assert result["row_count"] == 2


def test_valid_with_optional_columns_detected() -> None:
    df = make_valid_df()
    df["nearest_transmission_km"] = [5.0, 12.0]
    df["grid_zone_id"] = ["ERCOT", "SPP"]
    result = validate_processed_artifact(df)
    assert result["valid"] is True
    assert "nearest_transmission_km" in result["present_optional"]
    assert "grid_zone_id" in result["present_optional"]


# ---------------------------------------------------------------------------
# Missing required columns
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("missing_col", [c.name for c in REQUIRED_COLUMNS])
def test_missing_required_column_fails(missing_col: str) -> None:
    df = make_valid_df()
    df = df.drop(columns=[missing_col])
    result = validate_processed_artifact(df)
    assert result["valid"] is False
    assert missing_col in result["missing_required"]


# ---------------------------------------------------------------------------
# Range violations
# ---------------------------------------------------------------------------


def test_solar_cf_above_one_fails() -> None:
    result = validate_processed_artifact(make_valid_df(solar_cf_mean=[1.5, 0.2]))
    assert result["valid"] is False
    assert any("solar_cf_mean" in e for e in result["range_errors"])


def test_wind_cf_above_one_fails() -> None:
    result = validate_processed_artifact(make_valid_df(wind_cf_mean=[0.3, 1.1]))
    assert result["valid"] is False
    assert any("wind_cf_mean" in e for e in result["range_errors"])


def test_solar_cf_below_zero_fails() -> None:
    result = validate_processed_artifact(make_valid_df(solar_cf_mean=[-0.1, 0.2]))
    assert result["valid"] is False
    assert any("solar_cf_mean" in e for e in result["range_errors"])


def test_lat_out_of_range_fails() -> None:
    result = validate_processed_artifact(make_valid_df(lat=[91.0, 40.0]))
    assert result["valid"] is False
    assert any("lat" in e for e in result["range_errors"])


def test_lon_out_of_range_fails() -> None:
    result = validate_processed_artifact(make_valid_df(lon=[-181.0, -90.0]))
    assert result["valid"] is False
    assert any("lon" in e for e in result["range_errors"])


def test_price_at_zero_is_valid() -> None:
    result = validate_processed_artifact(
        make_valid_df(price_usd_per_mwh_mean=[0.0, 34.0])
    )
    assert result["valid"] is True


# ---------------------------------------------------------------------------
# get_column_names helper
# ---------------------------------------------------------------------------


def test_get_column_names_has_expected_keys() -> None:
    names = get_column_names()
    assert "required" in names
    assert "optional" in names
    assert "all" in names


def test_get_column_names_required_count() -> None:
    names = get_column_names()
    assert len(names["required"]) == len(REQUIRED_COLUMNS)


def test_get_column_names_all_is_union() -> None:
    names = get_column_names()
    assert set(names["all"]) == set(names["required"]) | set(names["optional"])

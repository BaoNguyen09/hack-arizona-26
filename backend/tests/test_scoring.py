"""Tests for the vectorized scoring engine.

Covers unit correctness (math / physical units), edge cases, and
score_all_cells DataFrame integration. No API or GeoPackage dependencies.
"""

import numpy as np
import pandas as pd
import pytest

from backend.app.engine.scoring import (
    compute_annual_generation_mwh,
    compute_capital_recovery_factor,
    compute_carbon_value_per_mwh,
    compute_composite_score,
    compute_lcoe_per_mwh,
    compute_revenue_per_mwh,
    score_all_cells,
    score_single_cell,
)
from backend.app.schemas.scenario import ScenarioRequest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_SCENARIO = ScenarioRequest(
    technology="solar",
    capacity_mw=50.0,
    capex_usd_per_kw=1200.0,
    opex_usd_per_kw_year=35.0,
    discount_rate=0.06,
    project_lifetime_years=25,
    carbon_price_usd_per_ton=50.0,
    cost_weight=1.0,
    revenue_weight=1.0,
    carbon_weight=1.0,
)

MINIMAL_DF = pd.DataFrame(
    {
        "cell_id": ["tx_001", "ks_001", "nm_001"],
        "lat": [31.97, 39.01, 35.08],
        "lon": [-99.90, -98.48, -106.65],
        "solar_cf_mean": [0.27, 0.20, 0.28],
        "wind_cf_mean": [0.40, 0.45, 0.35],
        "price_usd_per_mwh_mean": [34.0, 28.0, 30.0],
        "carbon_g_per_kwh_mean": [410.0, 380.0, 350.0],
    }
)


# ---------------------------------------------------------------------------
# Capital recovery factor
# ---------------------------------------------------------------------------


def test_crf_zero_discount_rate_is_inverse_lifetime() -> None:
    crf = compute_capital_recovery_factor(0.0, 20)
    assert pytest.approx(crf, rel=1e-6) == 1.0 / 20


def test_crf_positive_rate_is_greater_than_zero_rate() -> None:
    crf_zero = compute_capital_recovery_factor(0.0, 25)
    crf_six = compute_capital_recovery_factor(0.06, 25)
    assert crf_six > crf_zero


def test_crf_known_value() -> None:
    # r=0.06, n=25: CRF ≈ 0.07823
    crf = compute_capital_recovery_factor(0.06, 25)
    assert pytest.approx(crf, abs=1e-4) == 0.07823


# ---------------------------------------------------------------------------
# LCOE
# ---------------------------------------------------------------------------


def test_lcoe_decreases_as_cf_increases() -> None:
    """Higher capacity factor → lower LCOE (monotonic)."""
    crf = compute_capital_recovery_factor(0.06, 25)
    cfs = np.array([0.10, 0.20, 0.25, 0.30, 0.35])
    lcoes = compute_lcoe_per_mwh(cfs, 1200.0, 35.0, crf)
    assert list(lcoes) == sorted(lcoes, reverse=True)


def test_lcoe_zero_cf_gives_inf() -> None:
    crf = compute_capital_recovery_factor(0.06, 25)
    lcoe = compute_lcoe_per_mwh(np.array([0.0]), 1200.0, 35.0, crf)
    assert lcoe[0] == np.inf


def test_lcoe_known_value() -> None:
    """Manual calculation: CF=0.25, CAPEX=$1200/kW, OPEX=$35/kW/yr, CRF≈0.07823.
    annualized_capex = 1200 * 0.07823 = 93.876 $/kW/yr
    annual_gen       = 0.25 * 8760   = 2190 kWh/kW/yr
    lcoe             = (93.876 + 35) / 2190 * 1000 ≈ 58.85 $/MWh
    """
    crf = compute_capital_recovery_factor(0.06, 25)
    lcoe = compute_lcoe_per_mwh(np.array([0.25]), 1200.0, 35.0, crf)
    assert pytest.approx(lcoe[0], rel=0.01) == 58.85


def test_lcoe_is_positive_for_positive_cf() -> None:
    crf = compute_capital_recovery_factor(0.06, 25)
    lcoe = compute_lcoe_per_mwh(np.array([0.20, 0.30]), 1200.0, 35.0, crf)
    assert (lcoe > 0).all()


# ---------------------------------------------------------------------------
# Carbon value  (critical unit test — gCO2/kWh → $/MWh)
# ---------------------------------------------------------------------------


def test_carbon_value_400g_50usd() -> None:
    """400 gCO2/kWh, $50/ton → $20/MWh.

    Derivation:
      1 MWh = 1000 kWh
      Displaced: 400 g/kWh * 1000 kWh = 400,000 g CO2 = 0.4 tons CO2
      Value: 0.4 tons * $50/ton = $20/MWh
    """
    cf = np.array([0.25])  # unused for MVP, kept for signature
    val = compute_carbon_value_per_mwh(cf, np.array([400.0]), 50.0)
    assert pytest.approx(val[0], rel=1e-6) == 20.0


def test_carbon_value_zero_intensity_is_zero() -> None:
    val = compute_carbon_value_per_mwh(np.array([0.3]), np.array([0.0]), 50.0)
    assert val[0] == 0.0


def test_carbon_value_zero_price_is_zero() -> None:
    val = compute_carbon_value_per_mwh(np.array([0.3]), np.array([400.0]), 0.0)
    assert val[0] == 0.0


def test_carbon_value_scales_linearly_with_price() -> None:
    cf = np.array([0.25])
    intensity = np.array([300.0])
    val_50 = compute_carbon_value_per_mwh(cf, intensity, 50.0)[0]
    val_100 = compute_carbon_value_per_mwh(cf, intensity, 100.0)[0]
    assert pytest.approx(val_100, rel=1e-6) == 2 * val_50


# ---------------------------------------------------------------------------
# Revenue
# ---------------------------------------------------------------------------


def test_revenue_equals_price_for_mvp() -> None:
    """MVP: revenue/MWh is just the wholesale price (no correlation adjustment)."""
    price = np.array([34.0, 28.0])
    rev = compute_revenue_per_mwh(np.array([0.25, 0.4]), price)
    assert (rev == price).all()


# ---------------------------------------------------------------------------
# Annual generation
# ---------------------------------------------------------------------------


def test_annual_generation_math() -> None:
    """50 MW at CF=0.25 → 50 * 0.25 * 8760 = 109,500 MWh."""
    gen = compute_annual_generation_mwh(50.0, np.array([0.25]))
    assert pytest.approx(gen[0], rel=1e-6) == 109_500.0


def test_annual_generation_zero_cf_is_zero() -> None:
    gen = compute_annual_generation_mwh(100.0, np.array([0.0]))
    assert gen[0] == 0.0


# ---------------------------------------------------------------------------
# Composite score
# ---------------------------------------------------------------------------


def test_composite_score_formula() -> None:
    """score = w1*LCOE - w2*Revenue - w3*Carbon (lower is better)."""
    lcoe = np.array([60.0])
    rev = np.array([34.0])
    carbon = np.array([20.0])
    score = compute_composite_score(lcoe, rev, carbon, 1.0, 1.0, 1.0)
    assert pytest.approx(score[0], rel=1e-6) == 60.0 - 34.0 - 20.0  # = 6.0


def test_higher_revenue_weight_lowers_score() -> None:
    lcoe = np.array([60.0])
    rev = np.array([34.0])
    carbon = np.array([20.0])
    score_base = compute_composite_score(lcoe, rev, carbon, 1.0, 1.0, 1.0)[0]
    score_high_rev = compute_composite_score(lcoe, rev, carbon, 1.0, 2.0, 1.0)[0]
    assert score_high_rev < score_base


def test_zero_weights_give_zero_score() -> None:
    score = compute_composite_score(
        np.array([60.0]),
        np.array([34.0]),
        np.array([20.0]),
        0.0,
        0.0,
        0.0,
    )
    assert score[0] == 0.0


# ---------------------------------------------------------------------------
# score_all_cells (DataFrame integration)
# ---------------------------------------------------------------------------


def test_score_all_cells_returns_required_columns() -> None:
    result = score_all_cells(MINIMAL_DF.copy(), DEFAULT_SCENARIO)
    for col in (
        "selected_cf",
        "lcoe_usd_per_mwh",
        "revenue_usd_per_mwh",
        "carbon_value_usd_per_mwh",
        "composite_score",
        "annual_generation_mwh",
    ):
        assert col in result.columns, f"Missing column: {col}"


def test_score_all_cells_row_count_preserved() -> None:
    result = score_all_cells(MINIMAL_DF.copy(), DEFAULT_SCENARIO)
    assert len(result) == len(MINIMAL_DF)


def test_score_all_cells_solar_cf_matches_source() -> None:
    result = score_all_cells(MINIMAL_DF.copy(), DEFAULT_SCENARIO)
    pd.testing.assert_series_equal(
        result["selected_cf"].reset_index(drop=True),
        MINIMAL_DF["solar_cf_mean"].reset_index(drop=True),
        check_names=False,
    )


def test_score_all_cells_wind_uses_wind_cf() -> None:
    wind_scenario = ScenarioRequest(
        **{**DEFAULT_SCENARIO.model_dump(), "technology": "wind"}
    )
    result = score_all_cells(MINIMAL_DF.copy(), wind_scenario)
    pd.testing.assert_series_equal(
        result["selected_cf"].reset_index(drop=True),
        MINIMAL_DF["wind_cf_mean"].reset_index(drop=True),
        check_names=False,
    )


def test_score_all_cells_higher_cf_means_lower_lcoe() -> None:
    result = score_all_cells(MINIMAL_DF.copy(), DEFAULT_SCENARIO)
    # nm_001 has highest solar CF (0.28), should have lowest LCOE
    nm = result[result["cell_id"] == "nm_001"].iloc[0]
    ks = result[result["cell_id"] == "ks_001"].iloc[0]
    assert nm["lcoe_usd_per_mwh"] < ks["lcoe_usd_per_mwh"]


# ---------------------------------------------------------------------------
# score_single_cell (site detail)
# ---------------------------------------------------------------------------


def test_score_single_cell_keys_present() -> None:
    row = MINIMAL_DF.iloc[0]
    metrics = score_single_cell(row, DEFAULT_SCENARIO)
    for key in (
        "lcoe_usd_per_mwh",
        "lcoe_components",
        "revenue_usd_per_mwh",
        "carbon_value_usd_per_mwh",
        "annual_generation_mwh",
        "annual_generation_gwh",
        "capex_total_usd_millions",
        "annual_revenue_usd_millions",
        "annual_carbon_displacement_tons",
        "annual_carbon_value_usd",
        "selected_cf",
    ):
        assert key in metrics, f"Missing key: {key}"


def test_score_single_cell_lcoe_components_add_up() -> None:
    row = MINIMAL_DF.iloc[0]
    metrics = score_single_cell(row, DEFAULT_SCENARIO)
    lcoe = metrics["lcoe_usd_per_mwh"]
    capex_share = metrics["lcoe_components"]["capex_share_usd_per_mwh"]
    opex_share = metrics["lcoe_components"]["opex_share_usd_per_mwh"]
    assert pytest.approx(capex_share + opex_share, rel=1e-4) == lcoe


def test_score_single_cell_carbon_value_math() -> None:
    """tx_001: 410 gCO2/kWh * $50/ton → 410/1000 * 50 = $20.5/MWh."""
    row = MINIMAL_DF[MINIMAL_DF["cell_id"] == "tx_001"].iloc[0]
    metrics = score_single_cell(row, DEFAULT_SCENARIO)
    assert pytest.approx(metrics["carbon_value_usd_per_mwh"], rel=1e-4) == 20.5


def test_score_single_cell_annual_carbon_tons() -> None:
    """tx_001: CF=0.27, cap=50MW → gen=0.27*50*8760=118,260 MWh.
    Tons = 118,260 * 410/1000 = 48,486.6 tons.
    """
    row = MINIMAL_DF[MINIMAL_DF["cell_id"] == "tx_001"].iloc[0]
    metrics = score_single_cell(row, DEFAULT_SCENARIO)
    expected_gen = 0.27 * 50.0 * 8760.0  # MWh
    expected_tons = expected_gen * (410.0 / 1000.0)
    assert (
        pytest.approx(metrics["annual_carbon_displacement_tons"], rel=1e-4)
        == expected_tons
    )


def test_score_single_cell_capex_total_usd_millions() -> None:
    """50 MW * 1000 kW/MW * $1200/kW = $60,000,000 = $60M."""
    row = MINIMAL_DF.iloc[0]
    metrics = score_single_cell(row, DEFAULT_SCENARIO)
    assert pytest.approx(metrics["capex_total_usd_millions"], rel=1e-6) == 60.0

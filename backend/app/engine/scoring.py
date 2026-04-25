"""Vectorized cost optimization scoring engine.

Computes LCOE, revenue potential, carbon value, and composite scores
using NumPy vectorized operations for fast recalculation across ~3,500 cells.

Based on the mathematical model from the project spec:
- LCOE(i,j) = (CAPEX * CRF + OPEX) / (CF(i,j) * 8760)
- Revenue(i,j) = sum(Generation * Price) / MWh
- Carbon_Value(i,j) = sum(Generation * Grid_Intensity * Carbon_Price) / MWh
- Composite_Score(i,j) = w1*LCOE - w2*Revenue - w3*Carbon_Value
"""

import numpy as np
import pandas as pd

from backend.app.schemas.scenario import ScenarioRequest


def compute_capital_recovery_factor(discount_rate: float, lifetime_years: int) -> float:
    """Compute the Capital Recovery Factor (CRF) for LCOE calculation.

    CRF = r / (1 - (1 + r)^-n)

    where r = discount_rate, n = lifetime_years

    Args:
        discount_rate: Project discount rate (e.g., 0.06 for 6%)
        lifetime_years: Project lifetime in years

    Returns:
        Capital recovery factor
    """
    if discount_rate == 0:
        return 1.0 / lifetime_years
    return discount_rate / (1 - (1 + discount_rate) ** (-lifetime_years))


def compute_lcoe_per_mwh(
    capacity_factor: np.ndarray,
    capex_per_kw: float,
    opex_per_kw_year: float,
    crf: float,
) -> np.ndarray:
    """Compute LCOE (Levelized Cost of Energy) in USD/MWh.

    LCOE = (CAPEX * CRF + OPEX_per_year) / (CF * 8760 hours)

    Args:
        capacity_factor: Array of capacity factors (0-1)
        capex_per_kw: Capital expenditure per kW (USD/kW)
        opex_per_kw_year: Fixed O&M per kW per year (USD/kW/year)
        crf: Capital recovery factor

    Returns:
        Array of LCOE values in USD/MWh
    """
    # Annualized capital cost per kW
    annualized_capex_per_kw = capex_per_kw * crf

    # Total annual cost per kW of capacity
    annual_cost_per_kw = annualized_capex_per_kw + opex_per_kw_year

    # Annual generation per kW of capacity (kWh/kW/year)
    # CF * 8760 hours = kWh generated per kW of capacity per year
    annual_generation_per_kw = capacity_factor * 8760.0

    # Avoid division by zero for cells with zero capacity factor
    # LCOE = $/kW/year / (kWh/kW/year) = $/kWh * 1000 = $/MWh
    lcoe_per_kwh = np.where(
        annual_generation_per_kw > 0,
        annual_cost_per_kw / annual_generation_per_kw,
        np.inf,  # Infinite cost if no generation
    )

    # Convert to $/MWh
    return lcoe_per_kwh * 1000.0


def compute_revenue_per_mwh(
    capacity_factor: np.ndarray,
    avg_price_per_mwh: np.ndarray,
) -> np.ndarray:
    """Compute revenue potential per MWh of generation.

    Revenue/MWh = Average wholesale price at nearest hub

    Note: For more sophisticated analysis, this would account for:
    - Hourly price correlation with generation profile
    - Curtailment risk during high-generation, low-price periods
    - Capacity value beyond energy-only markets

    For MVP, we use the simple mean price as a proxy.

    Args:
        capacity_factor: Array of capacity factors (used for correlation weights later)
        avg_price_per_mwh: Array of average wholesale prices (USD/MWh)

    Returns:
        Array of revenue per MWh (USD/MWh)
    """
    return avg_price_per_mwh


def compute_carbon_value_per_mwh(
    capacity_factor: np.ndarray,
    grid_carbon_intensity_g_per_kwh: np.ndarray,
    carbon_price_per_ton: float,
) -> np.ndarray:
    """Compute carbon value per MWh of clean generation.

    Carbon Value/MWh = Grid_Intensity (gCO2/kWh) * Carbon_Price ($/ton) / 1000

    Each MWh of clean generation displaces grid carbon proportional to
    the local grid intensity. At $50/ton, a 400 gCO2/kWh grid yields
    $20/MWh in carbon value.

    Args:
        capacity_factor: Array of capacity factors (unused for MVP, kept for extension)
        grid_carbon_intensity_g_per_kwh: Array of grid carbon intensity (gCO2/kWh)
        carbon_price_per_ton: Carbon price in USD per metric ton CO2

    Returns:
        Array of carbon value per MWh (USD/MWh)
    """
    # Convert g/kWh to tons/MWh: 1000 g = 1 kg, 1000 kg = 1 ton, 1000 kWh = 1 MWh
    # g/kWh * (1 ton / 1,000,000 g) * (1000 kWh / 1 MWh) = tons/MWh
    # Simpler: g/kWh / 1000 = kg/MWh; kg/MWh / 1000 = tons/MWh
    # So: g/kWh / 1,000,000 = tons/MWh, but that's wrong.
    # Let's be careful:
    # - 1 MWh = 1000 kWh
    # - 1 ton = 1,000,000 g (1e6 g)
    # Grid intensity: X gCO2 per kWh
    # For 1 MWh (1000 kWh): X * 1000 gCO2 = X * 1000 / 1e6 tons
    # = X / 1000 tons CO2 per MWh
    tons_co2_per_mwh = grid_carbon_intensity_g_per_kwh / 1000.0

    # Carbon value = tons/MWh * $/ton = $/MWh
    return tons_co2_per_mwh * carbon_price_per_ton


def compute_composite_score(
    lcoe_per_mwh: np.ndarray,
    revenue_per_mwh: np.ndarray,
    carbon_value_per_mwh: np.ndarray,
    cost_weight: float,
    revenue_weight: float,
    carbon_weight: float,
) -> np.ndarray:
    """Compute composite optimization score.

    Score = w1 * LCOE - w2 * Revenue - w3 * Carbon_Value

    Lower scores are better. The negative signs on revenue and carbon
    value reflect that higher values in those dimensions improve the site.

    Args:
        lcoe_per_mwh: Array of LCOE values (USD/MWh)
        revenue_per_mwh: Array of revenue per MWh (USD/MWh)
        carbon_value_per_mwh: Array of carbon value per MWh (USD/MWh)
        cost_weight: Weight for LCOE minimization (w1)
        revenue_weight: Weight for revenue maximization (w2)
        carbon_weight: Weight for carbon value maximization (w3)

    Returns:
        Array of composite scores (lower is better)
    """
    # Base score: cost component (positive, lower is better)
    score = cost_weight * lcoe_per_mwh

    # Revenue component: subtract because higher revenue is better
    # (reduces the score, making site more attractive)
    score = score - revenue_weight * revenue_per_mwh

    # Carbon component: subtract because higher carbon value is better
    score = score - carbon_weight * carbon_value_per_mwh

    return score


def compute_annual_generation_mwh(
    capacity_mw: float, capacity_factor: np.ndarray
) -> np.ndarray:
    """Compute estimated annual generation in MWh.

    Annual_MWh = Capacity_MW * CF * 8760 hours/year * 1000 kW/MW / 1000 kWh/MWh
                 = Capacity_MW * CF * 8760

    Args:
        capacity_mw: Installed capacity in megawatts
        capacity_factor: Array of capacity factors (0-1)

    Returns:
        Array of annual generation in MWh
    """
    return capacity_mw * capacity_factor * 8760.0


def score_all_cells(
    df: pd.DataFrame,
    scenario: ScenarioRequest,
) -> pd.DataFrame:
    """Compute all scores for all cells in a DataFrame.

    This is the main entry point for vectorized scoring. Takes a DataFrame
    with the required columns and returns a DataFrame with score columns added.

    Args:
        df: DataFrame with columns including:
            - cell_id, lat, lon
            - solar_cf_mean, wind_cf_mean
            - price_usd_per_mwh_mean
            - carbon_g_per_kwh_mean
            - optional: nearest_transmission_km, price_hub_id, grid_zone_id
        scenario: User scenario parameters

    Returns:
        DataFrame with additional columns:
            - selected_cf: capacity factor for selected technology
            - lcoe_usd_per_mwh
            - revenue_usd_per_mwh
            - carbon_value_usd_per_mwh
            - composite_score
            - annual_generation_mwh
    """
    # Select capacity factor based on technology
    if scenario.technology == "solar":
        capacity_factor = df["solar_cf_mean"].to_numpy()
    elif scenario.technology == "wind":
        capacity_factor = df["wind_cf_mean"].to_numpy()
    else:
        raise ValueError(f"Unknown technology: {scenario.technology}")

    # Compute CRF once
    crf = compute_capital_recovery_factor(
        scenario.discount_rate, scenario.project_lifetime_years
    )

    # Compute component scores (all vectorized)
    lcoe = compute_lcoe_per_mwh(
        capacity_factor,
        scenario.capex_usd_per_kw,
        scenario.opex_usd_per_kw_year,
        crf,
    )

    revenue = compute_revenue_per_mwh(
        capacity_factor,
        df["price_usd_per_mwh_mean"].to_numpy(),
    )

    carbon_value = compute_carbon_value_per_mwh(
        capacity_factor,
        df["carbon_g_per_kwh_mean"].to_numpy(),
        scenario.carbon_price_usd_per_ton,
    )

    # Compute composite score
    composite = compute_composite_score(
        lcoe,
        revenue,
        carbon_value,
        scenario.cost_weight,
        scenario.revenue_weight,
        scenario.carbon_weight,
    )

    # Compute annual generation
    annual_gen = compute_annual_generation_mwh(
        scenario.capacity_mw,
        capacity_factor,
    )

    # Create result DataFrame
    result = df.copy()
    result["selected_cf"] = capacity_factor
    result["lcoe_usd_per_mwh"] = lcoe
    result["revenue_usd_per_mwh"] = revenue
    result["carbon_value_usd_per_mwh"] = carbon_value
    result["composite_score"] = composite
    result["annual_generation_mwh"] = annual_gen

    return result


def score_single_cell(
    row: pd.Series,
    scenario: ScenarioRequest,
) -> dict:
    """Compute scores for a single cell (for site detail view).

    This is used when we need detailed metrics for one specific cell,
    including component breakdowns that are useful for the UI panel.

    Args:
        row: Series with cell data (from ProcessedStore)
        scenario: User scenario parameters

    Returns:
        Dictionary with computed metrics
    """
    # Convert to 1-row arrays for reuse of vectorized functions
    if scenario.technology == "solar":
        cf = np.array([row["solar_cf_mean"]])
    else:
        cf = np.array([row["wind_cf_mean"]])

    price = np.array([row["price_usd_per_mwh_mean"]])
    carbon_intensity = np.array([row["carbon_g_per_kwh_mean"]])

    crf = compute_capital_recovery_factor(
        scenario.discount_rate, scenario.project_lifetime_years
    )

    # Compute all components
    lcoe = compute_lcoe_per_mwh(
        cf, scenario.capex_usd_per_kw, scenario.opex_usd_per_kw_year, crf
    )[0]
    revenue = compute_revenue_per_mwh(cf, price)[0]
    carbon_value = compute_carbon_value_per_mwh(
        cf, carbon_intensity, scenario.carbon_price_usd_per_ton
    )[0]

    annual_gen_mwh = compute_annual_generation_mwh(scenario.capacity_mw, cf)[0]
    annual_gen_gwh = annual_gen_mwh / 1000.0

    # Compute component breakdowns for LCOE
    annualized_capex_per_kw = scenario.capex_usd_per_kw * crf
    annual_gen_per_kw = cf[0] * 8760.0

    if annual_gen_per_kw > 0:
        capex_share = (annualized_capex_per_kw / annual_gen_per_kw) * 1000.0  # $/MWh
        opex_share = (
            scenario.opex_usd_per_kw_year / annual_gen_per_kw
        ) * 1000.0  # $/MWh
    else:
        capex_share = np.inf
        opex_share = np.inf

    # Total CAPEX
    total_capex = scenario.capacity_mw * 1000 * scenario.capex_usd_per_kw  # MW -> kW
    total_capex_millions = total_capex / 1e6

    # Annual revenue and carbon displacement
    annual_revenue = annual_gen_mwh * revenue / 1e6  # millions USD
    # carbon_intensity is in gCO2/kWh.
    # For 1 MWh (1000 kWh), emissions displaced = g/kWh * 1000 kWh = g/MWh.
    # Convert g to tons: 1 ton = 1,000,000 g.
    # So tons/MWh = (g/kWh * 1000) / 1e6 = g/kWh / 1000.
    annual_carbon_tons = annual_gen_mwh * (carbon_intensity[0] / 1000.0)  # tons CO2
    annual_carbon_value = annual_carbon_tons * scenario.carbon_price_usd_per_ton

    return {
        "lcoe_usd_per_mwh": float(lcoe),
        "lcoe_components": {
            "capex_share_usd_per_mwh": float(capex_share),
            "opex_share_usd_per_mwh": float(opex_share),
        },
        "revenue_usd_per_mwh": float(revenue),
        "carbon_value_usd_per_mwh": float(carbon_value),
        "annual_generation_mwh": float(annual_gen_mwh),
        "annual_generation_gwh": float(annual_gen_gwh),
        "capex_total_usd_millions": float(total_capex_millions),
        "annual_revenue_usd_millions": float(annual_revenue),
        "annual_carbon_displacement_tons": float(annual_carbon_tons),
        "annual_carbon_value_usd": float(annual_carbon_value),
        "selected_cf": float(cf[0]),
        "crf": float(crf),
    }

"""Site detail and investigation panel service.

Provides detailed metrics for individual cells when users click
on the map or search for specific locations.
"""

import time

import pandas as pd

from backend.app.data.processed_store import get_store
from backend.app.engine.scoring import score_all_cells, score_single_cell
from backend.app.schemas.scenario import (
    ScenarioRequest,
    SiteMetrics,
    SiteRequest,
    SiteResponse,
)


def get_site_response(request: SiteRequest, scenario: ScenarioRequest) -> SiteResponse:
    """Get detailed metrics for a specific site/cell.

    Looks up the cell by ID or nearest lat/lon, computes full
    metrics including LCOE breakdown, revenue estimates, and
    carbon displacement.

    Args:
        request: Site lookup parameters (cell_id or lat/lon)
        scenario: User scenario configuration for computing metrics

    Returns:
        SiteResponse with full metrics and ranking

    Raises:
        ValueError: If cell not found
        RuntimeError: If store not loaded
    """
    start_time = time.perf_counter()

    store = get_store()
    if not store.is_loaded():
        raise RuntimeError("Processed store not loaded. Cannot retrieve site.")

    # Lookup the cell
    if request.cell_id is not None:
        row = store.get_cell_by_id(request.cell_id)
        if row is None:
            raise ValueError(f"Cell not found: {request.cell_id}")
    elif request.lat is not None and request.lon is not None:
        row = store.get_nearest_cell(request.lat, request.lon)
        if row is None:
            raise ValueError(f"No cells found near lat={request.lat}, lon={request.lon}")
    else:
        raise ValueError("Must provide cell_id or both lat and lon")

    cell_id = str(row["cell_id"])

    # Compute all scores to get ranking
    df = store.get_all_cells()
    scored_df = score_all_cells(df, scenario)
    scored_df = scored_df.sort_values("composite_score").reset_index(drop=True)

    # Find this cell's rank
    cell_mask = scored_df["cell_id"].astype(str) == cell_id
    if cell_mask.any():
        rank = int(scored_df[cell_mask].index[0]) + 1  # 1-indexed
    else:
        rank = -1  # Shouldn't happen if cell exists

    # Compute detailed metrics for this cell
    scores = score_single_cell(row, scenario)

    # Build SiteMetrics
    metrics = SiteMetrics(
        cell_id=cell_id,
        lat=float(row["lat"]),
        lon=float(row["lon"]),
        solar_cf_mean=float(row.get("solar_cf_mean", 0)),
        wind_cf_mean=float(row.get("wind_cf_mean", 0)),
        selected_technology=scenario.technology,
        selected_cf_mean=scores["selected_cf"],
        estimated_annual_generation_gwh=scores["annual_generation_gwh"],
        lcoe_usd_per_mwh=scores["lcoe_usd_per_mwh"],
        lcoe_components=scores["lcoe_components"],
        capex_total_usd_millions=scores["capex_total_usd_millions"],
        price_hub_id=row.get("price_hub_id"),
        avg_wholesale_price_usd_per_mwh=float(row.get("price_usd_per_mwh_mean", 0)),
        estimated_annual_revenue_usd_millions=scores["annual_revenue_usd_millions"],
        revenue_per_mwh_usd=scores["revenue_usd_per_mwh"],
        grid_carbon_intensity_g_per_kwh=float(row.get("carbon_g_per_kwh_mean", 0)),
        annual_carbon_displacement_tons=scores["annual_carbon_displacement_tons"],
        carbon_value_usd_per_year=scores["annual_carbon_value_usd"],
        carbon_value_usd_per_mwh=scores["carbon_value_usd_per_mwh"],
        nearest_transmission_km=float(row.get("nearest_transmission_km")) if pd.notna(row.get("nearest_transmission_km")) else None,
        grid_zone_id=row.get("grid_zone_id"),
    )

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    print(f"Retrieved site {cell_id} (rank {rank}) in {elapsed_ms:.2f}ms")

    return SiteResponse(
        site=metrics,
        scenario=scenario,
        score_rank=rank,
        total_cells=len(df),
    )

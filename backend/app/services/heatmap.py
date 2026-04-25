"""Heatmap/scored cells service.

Builds scored cell responses using the vectorized scoring engine
and processed data store.
"""

from backend.app.core.perf import (
    cache_key_for_scenario,
    heatmap_cache,
    timed,
)
from backend.app.data.processed_store import get_store
from backend.app.engine.scoring import score_all_cells
from backend.app.schemas.scenario import HeatmapResponse, ScenarioRequest, ScoredCell


@timed("build_heatmap")
def build_heatmap_response(payload: ScenarioRequest) -> HeatmapResponse:
    """Build a scored cell response for the map layer.

    Uses vectorized scoring over all cells in the processed store,
    computing composite scores based on scenario parameters.

    Results are cached when scenario parameters match a previous call,
    enabling sub-200ms responses for repeated similar queries.

    Args:
        payload: User scenario configuration

    Returns:
        HeatmapResponse with scored cells sorted by composite score

    Raises:
        RuntimeError: If the processed store is not loaded
    """
    store = get_store()
    if not store.is_loaded():
        raise RuntimeError("Processed store not loaded. Cannot compute scores.")

    # Check cache for exact scenario match
    cache_key = cache_key_for_scenario(
        payload.technology,
        payload.capacity_mw,
        payload.capex_usd_per_kw,
        payload.opex_usd_per_kw_year,
        payload.discount_rate,
        payload.project_lifetime_years,
        payload.carbon_price_usd_per_ton,
        payload.cost_weight,
        payload.revenue_weight,
        payload.carbon_weight,
    )
    cached, cached_result = heatmap_cache.get(cache_key)
    if cached:
        return cached_result

    # Get all cells as DataFrame
    df = store.get_all_cells()

    # Apply vectorized scoring
    scored_df = score_all_cells(df, payload)

    # Sort by composite score (lower is better)
    scored_df = scored_df.sort_values("composite_score")

    # Build scored cell models
    cells = []
    for _, row in scored_df.iterrows():
        cells.append(
            ScoredCell(
                cell_id=str(row["cell_id"]),
                lat=float(row["lat"]),
                lon=float(row["lon"]),
                score=float(row["composite_score"]),
                raw_capacity_factor=float(row["selected_cf"]),
                raw_lcoe_usd_per_mwh=float(row["lcoe_usd_per_mwh"]),
                raw_revenue_usd_per_mwh=float(row["revenue_usd_per_mwh"]),
                raw_carbon_value_usd_per_mwh=float(row["carbon_value_usd_per_mwh"]),
            )
        )

    # Compute score range
    scores = scored_df["composite_score"].to_numpy()
    score_min = float(scores.min())
    score_max = float(scores.max())

    response = HeatmapResponse(
        technology=payload.technology,
        score_min=score_min,
        score_max=score_max,
        score_unit="composite_score (lower is better)",
        cell_count=len(cells),
        cells=cells,
    )

    # Cache the result
    heatmap_cache.set(response, cache_key)

    return response

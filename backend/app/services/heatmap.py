"""Heatmap/scored cells service.

Builds scored cell responses using the vectorized scoring engine
and processed data store.  Falls back to the bundled CSV dataset
when the main store (GeoPackage / SQLite) is not loaded.
"""

from __future__ import annotations

from pathlib import Path

from backend.app.core.config import settings
from backend.app.core.perf import (
    cache_key_for_scenario,
    heatmap_cache,
    timed,
)
from backend.app.data.processed_store import get_store
from backend.app.engine.scoring import score_all_cells
from backend.app.schemas.scenario import HeatmapResponse, ScenarioRequest, ScoredCell

_CSV_PATH = Path(settings.data_dir) / "processed" / "lumen_cells.csv"


def _load_csv_dataframe():
    """Load the bundled CSV as a scoring-compatible DataFrame."""
    from backend.app.data.processed_dataset import load_as_scoring_dataframe  # noqa: PLC0415

    return load_as_scoring_dataframe(_CSV_PATH)


@timed("build_heatmap")
def build_heatmap_response(payload: ScenarioRequest) -> HeatmapResponse:
    """Build a scored cell response for the map layer.

    Uses vectorized scoring over all cells in the processed store.
    Falls back to the bundled 28-cell CSV when the main store is not loaded.

    Results are cached when scenario parameters match a previous call,
    enabling sub-200ms responses for repeated similar queries.
    """
    store = get_store()

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
        payload.weather_adjustment,
        str(payload.simulation_weather) if payload.simulation_weather else None,
    )
    cached, cached_result = heatmap_cache.get(cache_key)
    if cached:
        return cached_result

    # Get all cells as DataFrame — prefer main store, fall back to CSV
    if store.is_loaded():
        df = store.get_all_cells()
    elif _CSV_PATH.exists():
        df = _load_csv_dataframe()
    else:
        raise RuntimeError(
            "Processed store not loaded and bundled CSV not found. "
            "Run the bootstrap script or provide data/processed/lumen_cells.csv."
        )

    # Apply vectorized scoring
    scored_df = score_all_cells(df, payload)
    scored_df = scored_df.sort_values("composite_score")

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

    scores = scored_df["composite_score"].to_numpy()
    response = HeatmapResponse(
        technology=payload.technology,
        score_min=float(scores.min()),
        score_max=float(scores.max()),
        score_unit="composite_score (lower is better)",
        cell_count=len(cells),
        cells=cells,
    )

    heatmap_cache.set(response, cache_key)
    return response

from backend.app.schemas.scenario import HeatmapPoint, HeatmapResponse, ScenarioRequest


def build_heatmap_response(payload: ScenarioRequest) -> HeatmapResponse:
    # Placeholder until the pre-computed dataset and optimization engine land.
    score = (
        payload.capex_usd_per_kw * payload.cost_weight
        - 20.0 * payload.revenue_weight
        - payload.carbon_price_usd_per_ton * 0.1 * payload.carbon_weight
    )

    points = [
        HeatmapPoint(lat=31.9686, lon=-99.9018, score=score),
        HeatmapPoint(lat=39.0119, lon=-98.4842, score=score * 0.92),
        HeatmapPoint(lat=35.0844, lon=-106.6504, score=score * 1.04),
    ]
    return HeatmapResponse(technology=payload.technology, points=points)

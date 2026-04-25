from fastapi import APIRouter

from backend.app.schemas.scenario import HeatmapResponse, HealthResponse, ScenarioRequest
from backend.app.services.heatmap import build_heatmap_response

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/heatmap", response_model=HeatmapResponse)
def heatmap(payload: ScenarioRequest) -> HeatmapResponse:
    return build_heatmap_response(payload)

"""API routes for Lumen backend.

Exposes endpoints for health checks, scored cell layers (/heatmap),
and site investigation (/site).
"""

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.scenario import (
    HealthResponse,
    HeatmapResponse,
    ScenarioRequest,
    SiteRequest,
    SiteResponse,
)
from backend.app.services.heatmap import build_heatmap_response
from backend.app.services.site import get_site_response
from backend.app.data.processed_store import get_store
from backend.app.core.config import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Health check endpoint.

    Returns service status and information about loaded data.
    """
    store = get_store()
    return HealthResponse(
        status="ok",
        store_loaded=store.is_loaded(),
        store_row_count=store.row_count if store.is_loaded() else 0,
    )


@router.post("/heatmap", response_model=HeatmapResponse)
def heatmap(payload: ScenarioRequest) -> HeatmapResponse:
    """Get scored cells for map rendering.

    Returns all cells with composite scores computed based on the
    provided scenario parameters. Compatible with any Deck.gl layer
    (heatmap, grid cell, scatterplot, H3, etc.).

    Score computation:
    - LCOE (Levelized Cost of Energy) based on capacity factor and CAPEX
    - Revenue potential from wholesale prices
    - Carbon value from displaced grid emissions
    - Composite = w1*LCOE - w2*Revenue - w3*CarbonValue (lower is better)

    Cells are returned sorted by composite score (best sites first).
    """
    try:
        return build_heatmap_response(payload)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing scores: {e}")


@router.get("/site", response_model=SiteResponse)
def site(
    cell_id: str | None = Query(None, description="Cell identifier"),
    lat: float | None = Query(None, ge=-90, le=90, description="Latitude for nearest lookup"),
    lon: float | None = Query(None, ge=-180, le=180, description="Longitude for nearest lookup"),
    # Scenario parameters (using defaults from ScenarioRequest)
    technology: str = Query("solar", description="Technology: solar or wind"),
    capacity_mw: float = Query(50.0, gt=0, description="Capacity in MW"),
    capex_usd_per_kw: float = Query(1200.0, gt=0, description="CAPEX USD/kW"),
    opex_usd_per_kw_year: float = Query(35.0, ge=0, description="OPEX USD/kW/year"),
    discount_rate: float = Query(0.06, ge=0, le=1, description="Discount rate"),
    project_lifetime_years: int = Query(25, ge=1, description="Project lifetime years"),
    carbon_price_usd_per_ton: float = Query(50.0, ge=0, description="Carbon price USD/ton"),
    cost_weight: float = Query(1.0, ge=0, description="Cost minimization weight"),
    revenue_weight: float = Query(1.0, ge=0, description="Revenue maximization weight"),
    carbon_weight: float = Query(1.0, ge=0, description="Carbon value weight"),
) -> SiteResponse:
    """Get detailed metrics for a specific site/cell.

    Look up a cell by ID or find the nearest cell to lat/lon coordinates,
    then return comprehensive metrics including:
    - Capacity factors and estimated generation
    - LCOE with component breakdown
    - Revenue estimates from wholesale prices
    - Carbon displacement and value
    - Infrastructure proximity

    Also includes the cell's rank by composite score among all cells.
    """
    try:
        # Build request objects
        site_request = SiteRequest(cell_id=cell_id, lat=lat, lon=lon)
        scenario = ScenarioRequest(
            technology=technology,  # type: ignore[arg-type]
            capacity_mw=capacity_mw,
            capex_usd_per_kw=capex_usd_per_kw,
            opex_usd_per_kw_year=opex_usd_per_kw_year,
            discount_rate=discount_rate,
            project_lifetime_years=project_lifetime_years,
            carbon_price_usd_per_ton=carbon_price_usd_per_ton,
            cost_weight=cost_weight,
            revenue_weight=revenue_weight,
            carbon_weight=carbon_weight,
        )

        return get_site_response(site_request, scenario)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving site: {e}")


@router.post("/brief")
def brief() -> dict:
    """Generate AI site assessment brief (stub for future implementation).

    Will accept site metrics and return an LLM-generated brief.
    """
    return {"status": "not_implemented", "message": "Brief generation coming soon"}


@router.post("/query")
def query() -> dict:
    """Natural language scenario query parser (stub for future implementation).

    Will parse natural language queries into structured scenario parameters.
    """
    return {"status": "not_implemented", "message": "NL query parsing coming soon"}

"""API routes for Lumen backend.

Exposes endpoints for health checks, scored cell layers (/heatmap),
and site investigation (/site).
"""

from fastapi import APIRouter, HTTPException, Query

from backend.app.data.processed_store import get_store
from backend.app.schemas.scenario import (
    HealthResponse,
    HeatmapResponse,
    ScenarioRequest,
    SiteRequest,
    SiteResponse,
)
from backend.app.services.heatmap import build_heatmap_response
from backend.app.services.site import get_site_response
from backend.app.data.county_store import generate_county_data
from backend.app.engine.scoring import score_single_cell
from backend.app.schemas.scenario import SiteMetrics
import pandas as pd

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
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error computing scores: {e}"
        ) from e


@router.get("/site", response_model=SiteResponse)
def site(
    cell_id: str | None = Query(None, description="Cell identifier"),
    lat: float | None = Query(
        None, ge=-90, le=90, description="Latitude for nearest lookup"
    ),
    lon: float | None = Query(
        None, ge=-180, le=180, description="Longitude for nearest lookup"
    ),
    # Scenario parameters (using defaults from ScenarioRequest)
    technology: str = Query("solar", description="Technology: solar or wind"),
    capacity_mw: float = Query(50.0, gt=0, description="Capacity in MW"),
    capex_usd_per_kw: float = Query(1200.0, gt=0, description="CAPEX USD/kW"),
    opex_usd_per_kw_year: float = Query(35.0, ge=0, description="OPEX USD/kW/year"),
    discount_rate: float = Query(0.06, ge=0, le=1, description="Discount rate"),
    project_lifetime_years: int = Query(25, ge=1, description="Project lifetime years"),
    carbon_price_usd_per_ton: float = Query(
        50.0, ge=0, description="Carbon price USD/ton"
    ),
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
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving site: {e}"
        ) from e


@router.get("/county/{fips_code}", response_model=SiteResponse)
def county_site(
    fips_code: str,
    technology: str = Query("solar", description="Technology: solar or wind"),
    capacity_mw: float = Query(50.0, gt=0, description="Capacity in MW"),
    capex_usd_per_kw: float = Query(1200.0, gt=0, description="CAPEX USD/kW"),
    opex_usd_per_kw_year: float = Query(35.0, ge=0, description="OPEX USD/kW/year"),
    discount_rate: float = Query(0.06, ge=0, le=1, description="Discount rate"),
    project_lifetime_years: int = Query(25, ge=1, description="Project lifetime years"),
    carbon_price_usd_per_ton: float = Query(
        50.0, ge=0, description="Carbon price USD/ton"
    ),
    cost_weight: float = Query(1.0, ge=0, description="Cost minimization weight"),
    revenue_weight: float = Query(1.0, ge=0, description="Revenue maximization weight"),
    carbon_weight: float = Query(1.0, ge=0, description="Carbon value weight"),
) -> SiteResponse:
    """Get detailed metrics for a specific county FIPS code deterministically."""
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
    
    # Generate deterministic county data
    row = generate_county_data(fips_code, technology)
    scores = score_single_cell(row, scenario)
    
    metrics = SiteMetrics(
        cell_id=row["cell_id"],
        lat=row["lat"],
        lon=row["lon"],
        solar_cf_mean=row["solar_cf_mean"],
        wind_cf_mean=row["wind_cf_mean"],
        selected_technology=scenario.technology,
        selected_cf_mean=scores["selected_cf"],
        estimated_annual_generation_gwh=scores["annual_generation_gwh"],
        lcoe_usd_per_mwh=scores["lcoe_usd_per_mwh"],
        lcoe_components=scores["lcoe_components"],
        capex_total_usd_millions=scores["capex_total_usd_millions"],
        price_hub_id=row["price_hub_id"],
        avg_wholesale_price_usd_per_mwh=row["price_usd_per_mwh_mean"],
        estimated_annual_revenue_usd_millions=scores["annual_revenue_usd_millions"],
        revenue_per_mwh_usd=scores["revenue_usd_per_mwh"],
        grid_carbon_intensity_g_per_kwh=row["carbon_g_per_kwh_mean"],
        annual_carbon_displacement_tons=scores["annual_carbon_displacement_tons"],
        carbon_value_usd_per_year=scores["annual_carbon_value_usd"],
        carbon_value_usd_per_mwh=scores["carbon_value_usd_per_mwh"],
        nearest_transmission_km=row["nearest_transmission_km"],
        grid_zone_id=row["grid_zone_id"],
    )

    return SiteResponse(
        site=metrics,
        scenario=scenario,
        score_rank=1,
        total_cells=3143,
    )


from pydantic import BaseModel

class BriefRequest(BaseModel):
    site: dict
    scenario: dict

@router.post("/brief")
def brief(payload: BriefRequest) -> dict:
    """Generate AI site assessment brief."""
    site = payload.site
    cf = site.get("selected_cf_mean", 0) * 100
    lcoe = site.get("lcoe_usd_per_mwh", 0)
    rev = site.get("avg_wholesale_price_usd_per_mwh", 0)
    carbon = site.get("grid_carbon_intensity_g_per_kwh", 0)
    trans = site.get("nearest_transmission_km", 0)
    
    text = (
        f"Site Assessment: This county location offers a capacity factor of {cf:.1f}%, "
        f"yielding an estimated LCOE of ${lcoe:.1f}/MWh. "
        f"Wholesale prices at the nearest hub average ${rev:.1f}/MWh, creating positive margin. "
        f"Grid carbon intensity here is {carbon:.1f} gCO₂/kWh, meaning each MWh displaces {carbon/1000:.2f} tCO₂. "
        f"Nearest 345kV transmission line is {trans:.1f} km away. "
        f"Key risk: curtailment during spring months when supply exceeds demand."
    )
    return {"status": "success", "text": text}


@router.post("/query")
def query() -> dict:
    """Natural language scenario query parser (stub for future implementation).

    Will parse natural language queries into structured scenario parameters.
    """
    return {"status": "not_implemented", "message": "NL query parsing coming soon"}

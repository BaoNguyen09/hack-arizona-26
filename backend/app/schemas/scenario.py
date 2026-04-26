from typing import Any, Literal

from pydantic import BaseModel, Field

TechnologyType = Literal["solar", "wind"]


class ScenarioRequest(BaseModel):
    """Request model for scenario-based scoring.

    Defines user-adjustable parameters for computing composite scores across
    all grid cells.
    """

    technology: TechnologyType = Field(
        default="solar",
        description="Renewable technology type: solar PV or onshore wind",
    )
    capacity_mw: float = Field(
        default=50.0, gt=0, description="Target capacity in megawatts"
    )
    capex_usd_per_kw: float = Field(
        default=1200.0,
        gt=0,
        description="Capital expenditure per kW of capacity (USD/kW)",
    )
    opex_usd_per_kw_year: float = Field(
        default=35.0, ge=0, description="Fixed O&M costs per kW per year (USD/kW/year)"
    )
    discount_rate: float = Field(
        default=0.06,
        ge=0,
        le=1,
        description="Project discount rate for LCOE calculation",
    )
    project_lifetime_years: int = Field(
        default=25, ge=1, description="Expected project lifetime in years"
    )
    carbon_price_usd_per_ton: float = Field(
        default=50.0,
        ge=0,
        description="Social cost of carbon or carbon credit price (USD/ton CO2)",
    )
    cost_weight: float = Field(
        default=1.0, ge=0, description="Weight for LCOE minimization in composite score"
    )
    revenue_weight: float = Field(
        default=1.0, ge=0, description="Weight for revenue potential in composite score"
    )
    carbon_weight: float = Field(
        default=1.0,
        ge=0,
        description="Weight for carbon displacement value in composite score",
    )


class ScoredCell(BaseModel):
    """A single scored cell for map rendering.

    Generic output that supports Deck.gl heatmap, grid cell, scatterplot,
    or H3 layers. Includes all fields needed for frontend visualization.
    """

    cell_id: str = Field(description="Unique cell identifier")
    lat: float = Field(description="Cell centroid latitude", ge=-90, le=90)
    lon: float = Field(description="Cell centroid longitude", ge=-180, le=180)
    score: float = Field(description="Composite optimization score (lower is better)")
    raw_capacity_factor: float = Field(
        description="Capacity factor for selected technology (0-1)"
    )
    raw_lcoe_usd_per_mwh: float = Field(
        description="Levelized cost of energy estimate (USD/MWh)"
    )
    raw_revenue_usd_per_mwh: float = Field(
        description="Estimated revenue potential (USD/MWh)"
    )
    raw_carbon_value_usd_per_mwh: float = Field(
        description="Carbon value per MWh generated (USD/MWh)"
    )


class HeatmapResponse(BaseModel):
    """Response for scored cell layer rendering.

    Returns scored cells with metadata for frontend visualization.
    Compatible with any Deck.gl layer type (heatmap, grid, scatter, H3).
    """

    technology: TechnologyType
    score_min: float = Field(description="Minimum score across all cells")
    score_max: float = Field(description="Maximum score across all cells")
    score_unit: str = Field(
        default="composite_score", description="Unit/description of the score field"
    )
    cell_count: int = Field(description="Number of cells in response")
    cells: list[ScoredCell] = Field(
        description="Scored cells for map rendering, ordered by score (best first)"
    )


class SiteRequest(BaseModel):
    """Request to get detailed metrics for a specific cell."""

    cell_id: str | None = Field(
        default=None, description="Cell identifier (alternative to lat/lon)"
    )
    lat: float | None = Field(
        default=None, ge=-90, le=90, description="Latitude for nearest-cell lookup"
    )
    lon: float | None = Field(
        default=None, ge=-180, le=180, description="Longitude for nearest-cell lookup"
    )

    def get_lookup_key(self) -> tuple[str, float | None, float | None]:
        """Return the lookup strategy for this request."""
        if self.cell_id is not None:
            return ("cell_id", None, None)
        if self.lat is not None and self.lon is not None:
            return ("latlon", self.lat, self.lon)
        raise ValueError("Must provide either cell_id or both lat and lon")


class SiteMetrics(BaseModel):
    """Core metrics for a specific site/cell.

    These are the base metrics derived from the processed artifact and
    scenario parameters, before any AI-generated brief.
    """

    cell_id: str
    lat: float
    lon: float

    # Capacity and generation
    solar_cf_mean: float = Field(description="Mean solar capacity factor (0-1)")
    wind_cf_mean: float = Field(description="Mean wind capacity factor (0-1)")
    selected_technology: TechnologyType
    selected_cf_mean: float = Field(
        description="Capacity factor for selected tech (0-1)"
    )
    estimated_annual_generation_gwh: float = Field(
        description="Estimated annual generation at requested capacity (GWh/year)"
    )

    # Cost metrics
    lcoe_usd_per_mwh: float = Field(description="Levelized cost of energy (USD/MWh)")
    lcoe_components: dict = Field(description="LCOE breakdown: capex_share, opex_share")
    capex_total_usd_millions: float = Field(
        description="Total CAPEX for requested capacity (millions USD)"
    )

    # Revenue metrics
    price_hub_id: str | None = Field(description="Nearest wholesale price hub")
    avg_wholesale_price_usd_per_mwh: float = Field(
        description="Average wholesale price at nearest hub (USD/MWh)"
    )
    estimated_annual_revenue_usd_millions: float = Field(
        description="Estimated annual revenue (millions USD)"
    )
    revenue_per_mwh_usd: float = Field(description="Revenue per MWh (USD/MWh)")

    # Carbon metrics
    grid_carbon_intensity_g_per_kwh: float = Field(
        description="Grid carbon intensity (gCO2/kWh)"
    )
    annual_carbon_displacement_tons: float = Field(
        description="Annual CO2 displaced by clean generation (tons/year)"
    )
    carbon_value_usd_per_year: float = Field(
        description="Annual carbon value at given carbon price (USD/year)"
    )
    carbon_value_usd_per_mwh: float = Field(
        description="Carbon value per MWh generated (USD/MWh)"
    )

    # Infrastructure
    nearest_transmission_km: float | None = Field(
        description="Distance to nearest transmission line (km)"
    )
    grid_zone_id: str | None = Field(description="Grid zone/balancing authority")
    load_gw: float | None = Field(
        default=None, description="Estimated electricity load in GW"
    )
    renewable_percent: float | None = Field(
        default=None, ge=0, le=100, description="Estimated renewable generation share"
    )
    generation_profile: list[dict[str, float]] | None = Field(
        default=None, description="Optional hourly generation and price profile"
    )
    carbon_profile: list[dict[str, float]] | None = Field(
        default=None, description="Optional hourly carbon intensity profile"
    )


class SiteResponse(BaseModel):
    """Full response for site investigation panel.

    Includes all metrics for a cell plus metadata for the frontend
    to render charts and comparison views.
    """

    site: SiteMetrics
    scenario: ScenarioRequest = Field(
        description="The scenario parameters used to compute these metrics"
    )
    score_rank: int = Field(
        description="Rank of this cell by composite score (1 = best)"
    )
    total_cells: int = Field(description="Total number of cells in dataset")


class HealthResponse(BaseModel):
    """Simple health check response."""

    status: str
    store_loaded: bool = Field(
        default=False, description="Whether processed data is loaded"
    )
    store_row_count: int = Field(default=0, description="Number of cells in store")


class BriefRequest(BaseModel):
    """Input for site assessment brief generation."""

    site: dict[str, Any]
    scenario: dict[str, Any]


class BriefResponse(BaseModel):
    """Site assessment brief response."""

    status: str = "success"
    text: str
    job_id: str | None = None
    cached: bool = False


class CountyJobRequest(BaseModel):
    """Request body for asynchronously computing a county site response."""

    fips_code: str = Field(description="5-digit county FIPS code")
    scenario: ScenarioRequest = Field(default_factory=ScenarioRequest)


class BriefJobRequest(BaseModel):
    """Request body for asynchronously generating a site assessment brief."""

    site: dict[str, Any]
    scenario: dict[str, Any]


class JobSubmitResponse(BaseModel):
    """Response returned when a local async job is submitted."""

    job_id: str
    status: str
    cached: bool = False


class JobStatusResponse(BaseModel):
    """Serializable status for an async orchestration job."""

    job_id: str
    job_type: str
    status: str
    created_at: str
    updated_at: str
    input_hash: str
    artifact_key: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None

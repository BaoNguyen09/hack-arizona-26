from typing import Literal

from pydantic import BaseModel, Field


TechnologyType = Literal["solar", "wind"]


class ScenarioRequest(BaseModel):
    technology: TechnologyType = "solar"
    capacity_mw: float = Field(default=50.0, gt=0)
    capex_usd_per_kw: float = Field(default=1200.0, gt=0)
    carbon_price_usd_per_ton: float = Field(default=50.0, ge=0)
    cost_weight: float = Field(default=1.0, ge=0)
    revenue_weight: float = Field(default=1.0, ge=0)
    carbon_weight: float = Field(default=1.0, ge=0)


class HeatmapPoint(BaseModel):
    lat: float
    lon: float
    score: float


class HeatmapResponse(BaseModel):
    technology: TechnologyType
    points: list[HeatmapPoint]


class HealthResponse(BaseModel):
    status: str

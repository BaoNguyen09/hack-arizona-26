"""County-level model steps used by the orchestration layer."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from backend.app.data.contracts import validate_county_artifact
from backend.app.data.county_store import generate_county_data
from backend.app.engine.scoring import score_single_cell
from backend.app.models.base import BaseModelStep
from backend.app.schemas.scenario import ScenarioRequest, SiteMetrics, SiteResponse


class SimulatedCountyModel(BaseModelStep):
    """Deterministic county feature model for the current demo data."""

    name = "simulated_county"
    version = "1.0.0"

    def run(self, payload: dict[str, Any]) -> pd.Series:
        """Generate a county row matching the processed county contract."""
        fips = str(payload["fips_code"])
        technology = str(payload.get("technology", "solar"))
        row = generate_county_data(fips, technology)
        row["fips"] = fips

        df = pd.DataFrame([row])
        validation = validate_county_artifact(df)
        if not validation["valid"]:
            raise ValueError(f"Invalid county artifact: {validation}")

        return df.iloc[0].copy()


class CountyScoringModel(BaseModelStep):
    """Scenario scoring model for one county."""

    name = "county_scoring"
    version = "1.0.0"

    def run(self, payload: dict[str, Any]) -> SiteResponse:
        """Score a generated county row and shape it for the existing API."""
        row = payload["row"]
        scenario = payload["scenario"]
        if not isinstance(scenario, ScenarioRequest):
            scenario = ScenarioRequest(**scenario)

        scores = score_single_cell(row, scenario)
        metrics = SiteMetrics(
            cell_id=str(row["cell_id"]),
            lat=float(row["lat"]),
            lon=float(row["lon"]),
            solar_cf_mean=float(row["solar_cf_mean"]),
            wind_cf_mean=float(row["wind_cf_mean"]),
            selected_technology=scenario.technology,
            selected_cf_mean=scores["selected_cf"],
            estimated_annual_generation_gwh=scores["annual_generation_gwh"],
            lcoe_usd_per_mwh=scores["lcoe_usd_per_mwh"],
            lcoe_components=scores["lcoe_components"],
            capex_total_usd_millions=scores["capex_total_usd_millions"],
            price_hub_id=row.get("price_hub_id"),
            avg_wholesale_price_usd_per_mwh=float(row["price_usd_per_mwh_mean"]),
            estimated_annual_revenue_usd_millions=scores[
                "annual_revenue_usd_millions"
            ],
            revenue_per_mwh_usd=scores["revenue_usd_per_mwh"],
            grid_carbon_intensity_g_per_kwh=float(row["carbon_g_per_kwh_mean"]),
            annual_carbon_displacement_tons=scores[
                "annual_carbon_displacement_tons"
            ],
            carbon_value_usd_per_year=scores["annual_carbon_value_usd"],
            carbon_value_usd_per_mwh=scores["carbon_value_usd_per_mwh"],
            nearest_transmission_km=float(row["nearest_transmission_km"])
            if pd.notna(row.get("nearest_transmission_km"))
            else None,
            grid_zone_id=row.get("grid_zone_id"),
            load_gw=float(row["load_gw"]) if pd.notna(row.get("load_gw")) else None,
            renewable_percent=float(row["renewable_percent"])
            if pd.notna(row.get("renewable_percent"))
            else None,
            generation_profile=_generation_profile(row, scenario),
            carbon_profile=_carbon_profile(row),
        )

        return SiteResponse(
            site=metrics,
            scenario=scenario,
            score_rank=1,
            total_cells=3143,
        )


class RealWeatherIngestModel(BaseModelStep):
    """Contract-ready placeholder for NOAA/NASA weather ingestion."""

    name = "real_weather_ingest"
    version = "0.1.0"

    def run(self, payload: Any) -> Any:
        raise NotImplementedError("Real weather ingestion is not wired yet.")


class RealPriceIngestModel(BaseModelStep):
    """Contract-ready placeholder for EIA price ingestion."""

    name = "real_price_ingest"
    version = "0.1.0"

    def run(self, payload: Any) -> Any:
        raise NotImplementedError("Real price ingestion is not wired yet.")


class RealCarbonIngestModel(BaseModelStep):
    """Contract-ready placeholder for carbon intensity ingestion."""

    name = "real_carbon_ingest"
    version = "0.1.0"

    def run(self, payload: Any) -> Any:
        raise NotImplementedError("Real carbon ingestion is not wired yet.")


def _generation_profile(
    row: pd.Series,
    scenario: ScenarioRequest,
) -> list[dict[str, float]]:
    """Create deterministic hourly values until real time-series models arrive."""
    selected_cf = (
        float(row["solar_cf_mean"])
        if scenario.technology == "solar"
        else float(row["wind_cf_mean"])
    )
    avg_price = float(row["price_usd_per_mwh_mean"])

    points: list[dict[str, float]] = []
    for hour in range(24):
        if scenario.technology == "solar":
            daylight_shape = max(0.0, math.sin((hour - 6) / 12 * math.pi))
            generation = scenario.capacity_mw * selected_cf * daylight_shape
        else:
            generation = scenario.capacity_mw * selected_cf * (
                0.75 + 0.25 * math.sin(hour / 24 * 2 * math.pi)
            )
        price = avg_price * (0.9 + 0.2 * math.sin((hour - 15) / 24 * 2 * math.pi))
        points.append(
            {
                "hour": float(hour),
                "generation": round(generation, 3),
                "price": round(price, 3),
            }
        )

    return points


def _carbon_profile(row: pd.Series) -> list[dict[str, float]]:
    """Create deterministic hourly carbon data for the current county model."""
    base_carbon = float(row["carbon_g_per_kwh_mean"])
    points: list[dict[str, float]] = []
    for hour in range(24):
        multiplier = 0.9 + 0.1 * math.sin((hour - 18) / 24 * 2 * math.pi)
        grid_intensity = base_carbon * multiplier
        points.append(
            {
                "hour": float(hour),
                "gridIntensity": round(grid_intensity, 3),
                "displaced": round(grid_intensity / 1000.0, 4),
            }
        )
    return points

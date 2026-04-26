"""Brief generation model steps."""

from __future__ import annotations

import textwrap
from typing import Any

from google import genai

from backend.app.core.config import settings
from backend.app.models.base import BaseModelStep
from backend.app.schemas.scenario import BriefResponse


class TemplateBriefModel(BaseModelStep):
    """Deterministic site assessment brief used as the safe fallback."""

    name = "template_brief"
    version = "1.0.0"

    def run(self, payload: dict[str, Any]) -> BriefResponse:
        site = payload["site"]
        cf = site.get("selected_cf_mean", 0) * 100
        lcoe = site.get("lcoe_usd_per_mwh", 0)
        rev = site.get("avg_wholesale_price_usd_per_mwh", 0)
        carbon = site.get("grid_carbon_intensity_g_per_kwh", 0)
        trans = site.get("nearest_transmission_km", 0)
        technology = site.get("selected_technology", "renewable")

        text = (
            f"Site Assessment: This county offers a {technology} capacity factor "
            f"of {cf:.1f}%, yielding an estimated LCOE of ${lcoe:.1f}/MWh. "
            f"Wholesale prices at the nearest hub average ${rev:.1f}/MWh, "
            "which indicates the local revenue opportunity for this scenario. "
            f"Grid carbon intensity here is {carbon:.1f} gCO2/kWh, so each MWh "
            f"of clean output displaces about {carbon / 1000:.2f} tCO2. "
            f"Nearest transmission is approximately {trans:.1f} km away. "
            "Key risk: local curtailment and interconnection constraints should be "
            "validated before committing development capital."
        )
        return BriefResponse(status="success", text=text)


class LLMBriefModel(BaseModelStep):
    """Gemini-backed site assessment brief model."""

    name = "llm_brief"
    version = "gemini-2.5-flash-v1"

    def __init__(self) -> None:
        self._client: genai.Client | None = None

    @property
    def configured(self) -> bool:
        """Return whether Gemini is configured."""
        return bool(settings.gemini_api_key)

    def _client_for_request(self) -> genai.Client:
        if not self.configured:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        if self._client is None:
            self._client = genai.Client(api_key=settings.gemini_api_key)
        return self._client

    def run(self, payload: dict[str, Any]) -> BriefResponse:
        site = payload["site"]
        scenario = payload["scenario"]

        cf = site.get("selected_cf_mean", 0) * 100
        lcoe = site.get("lcoe_usd_per_mwh", 0)
        rev = site.get("avg_wholesale_price_usd_per_mwh", 0)
        annual_revenue = site.get("estimated_annual_revenue_usd_millions", 0)
        carbon = site.get("grid_carbon_intensity_g_per_kwh", 0)
        displaced = site.get("annual_carbon_displacement_tons", 0)
        trans = site.get("nearest_transmission_km", 0)
        technology = site.get("selected_technology", "renewable")
        capacity_mw = scenario.get("capacity_mw", 0)
        capex = scenario.get("capex_usd_per_kw", 0)
        carbon_price = scenario.get("carbon_price_usd_per_ton", 0)

        prompt = textwrap.dedent(
            f"""
            You are a senior renewable energy investment analyst preparing a county-level site screening memo for an infrastructure investor.

Write a professional site assessment brief for a potential {technology} energy project using ONLY the metrics provided below. Treat all assumptions as preliminary screening inputs.

Strict Rules:
- Do NOT invent additional facts, assumptions, or calculations.
- Do NOT mention permitting status, land control, interconnection queue position, tax credits, policy incentives, transmission upgrades, or financing terms unless explicitly provided.
- If uncertainty exists, frame it as a diligence item rather than a fact.
- Maintain an objective, investment-grade tone.

Provided Metrics:
- Technology: {technology}
- Capacity: {capacity_mw:.1f} MW
- Capacity Factor: {cf:.1f}%
- Estimated LCOE: ${lcoe:.1f}/MWh
- Average Wholesale Power Price: ${rev:.1f}/MWh
- Estimated Annual Revenue: ${annual_revenue:.2f} million
- Grid Carbon Intensity: {carbon:.1f} gCO2/kWh
- Estimated Annual Carbon Displacement: {displaced:.1f} tons CO2
- Carbon Price Assumption: ${carbon_price:.1f}/ton
- Distance to Nearest Transmission: {trans:.1f} km
- CAPEX Assumption: ${capex:.1f}/kW

Required Coverage:
1. Assess economic attractiveness using LCOE, market price, revenue, and CAPEX.
2. Explain environmental value using carbon displacement metrics.
3. Comment on transmission proximity and likely interconnection implications.
4. Identify one key execution or development risk.
5. Conclude with an overall screening view (attractive / mixed / challenged).

Output Requirements:
- Length: 110 to 160 words.
- Single cohesive brief (no bullets).
- Clear, concise, analytical writing.
            """
        ).strip()

        response = self._client_for_request().models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Gemini returned an empty brief")
        return BriefResponse(status="success", text=text)

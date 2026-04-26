"""Brief generation model steps."""

from __future__ import annotations

import textwrap
from typing import Any

from google import genai

from backend.app.core.config import settings
from backend.app.models.base import BaseModelStep
from backend.app.schemas.scenario import BriefResponse


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _technology_label(technology: str) -> str:
    return "Solar PV" if technology == "solar" else "Onshore Wind"


def _transmission_risk_band(distance_km: float) -> tuple[str, str]:
    if distance_km <= 10:
        return "low", "nearby transmission access"
    if distance_km <= 25:
        return "moderate", "manageable but non-trivial interconnection distance"
    return "elevated", "long transmission reach that could add cost and schedule risk"


def _economics_view(margin: float) -> tuple[str, str]:
    if margin >= 15:
        return "strong", "LCOE sits comfortably below local wholesale pricing"
    if margin >= 5:
        return "favorable", "LCOE is below local wholesale pricing with a usable merchant spread"
    if margin >= 0:
        return "mixed", "LCOE is only modestly below local wholesale pricing"
    return "challenged", "LCOE is above local wholesale pricing on a merchant basis"


def _carbon_view(carbon_intensity: float) -> str:
    if carbon_intensity >= 500:
        return "high avoided-emissions value"
    if carbon_intensity >= 300:
        return "meaningful avoided-emissions value"
    return "more moderate avoided-emissions value"


def _verdict_label(margin: float, distance_km: float) -> str:
    if margin >= 10 and distance_km <= 20:
        return "Attractive"
    if margin >= 0:
        return "Mixed"
    return "Challenged"


def _build_brief_inputs(payload: dict[str, Any]) -> dict[str, Any]:
    site = payload["site"]
    scenario = payload["scenario"]

    technology = str(site.get("selected_technology", "renewable"))
    capacity_mw = _as_float(scenario.get("capacity_mw"))
    capacity_factor = _as_float(site.get("selected_cf_mean")) * 100
    lcoe = _as_float(site.get("lcoe_usd_per_mwh"))
    wholesale_price = _as_float(site.get("avg_wholesale_price_usd_per_mwh"))
    annual_revenue_m = _as_float(site.get("estimated_annual_revenue_usd_millions"))
    carbon_intensity = _as_float(site.get("grid_carbon_intensity_g_per_kwh"))
    annual_displacement = _as_float(site.get("annual_carbon_displacement_tons"))
    transmission_km = _as_float(site.get("nearest_transmission_km"))
    capex = _as_float(scenario.get("capex_usd_per_kw"))
    carbon_price = _as_float(scenario.get("carbon_price_usd_per_ton"))
    annual_carbon_value_m = _as_float(site.get("carbon_value_usd_per_year")) / 1_000_000
    merchant_margin = wholesale_price - lcoe

    economics_view, economics_reason = _economics_view(merchant_margin)
    transmission_band, transmission_reason = _transmission_risk_band(transmission_km)
    carbon_reason = _carbon_view(carbon_intensity)
    verdict = _verdict_label(merchant_margin, transmission_km)

    return {
        "technology": technology,
        "technology_label": _technology_label(technology),
        "capacity_mw": capacity_mw,
        "capacity_factor": capacity_factor,
        "lcoe": lcoe,
        "wholesale_price": wholesale_price,
        "annual_revenue_m": annual_revenue_m,
        "carbon_intensity": carbon_intensity,
        "annual_displacement": annual_displacement,
        "transmission_km": transmission_km,
        "capex": capex,
        "carbon_price": carbon_price,
        "annual_carbon_value_m": annual_carbon_value_m,
        "merchant_margin": merchant_margin,
        "economics_view": economics_view,
        "economics_reason": economics_reason,
        "transmission_band": transmission_band,
        "transmission_reason": transmission_reason,
        "carbon_reason": carbon_reason,
        "verdict": verdict,
    }


def _render_template_brief(inputs: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Verdict: {inputs['verdict']} screening case for {inputs['technology_label'].lower()}.",
            (
                "Economics: "
                f"{inputs['economics_reason']}. Estimated LCOE is ${inputs['lcoe']:.1f}/MWh "
                f"versus ${inputs['wholesale_price']:.1f}/MWh wholesale pricing, a "
                f"${inputs['merchant_margin']:.1f}/MWh spread, on ${inputs['capex']:.0f}/kW CAPEX."
            ),
            (
                "Carbon: "
                f"The site offers {inputs['carbon_reason']}, with grid intensity at "
                f"{inputs['carbon_intensity']:.1f} gCO2/kWh and estimated annual displacement "
                f"of {inputs['annual_displacement']:.0f} tons CO2."
            ),
            (
                "Grid: "
                f"Transmission distance is {inputs['transmission_km']:.1f} km, indicating "
                f"{inputs['transmission_reason']}."
            ),
            (
                "Key Risk: "
                f"The primary diligence item is {inputs['transmission_band']} interconnection risk; "
                "queue position, upgrade scope, and curtailment exposure still need confirmation."
            ),
        ]
    )


class TemplateBriefModel(BaseModelStep):
    """Deterministic site assessment brief used as the safe fallback."""

    name = "template_brief"
    version = "1.1.0"

    def run(self, payload: dict[str, Any]) -> BriefResponse:
        text = _render_template_brief(_build_brief_inputs(payload))
        return BriefResponse(status="success", text=text)


class LLMBriefModel(BaseModelStep):
    """Gemini-backed site assessment brief model."""

    name = "llm_brief"
    version = "gemini-2.5-flash-v2"

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
        inputs = _build_brief_inputs(payload)

        prompt = textwrap.dedent(
            f"""
            You are a senior renewable energy investment analyst writing a county-level screening note.

            Use only the provided metrics and screening signals. Do not invent policy, incentives,
            permitting status, land control, queue position, transmission upgrades, or financing terms.
            If a point is uncertain, frame it as a diligence item.

            Inputs:
            - Technology: {inputs['technology_label']}
            - Capacity: {inputs['capacity_mw']:.1f} MW
            - Capacity factor: {inputs['capacity_factor']:.1f}%
            - LCOE: ${inputs['lcoe']:.1f}/MWh
            - Wholesale price: ${inputs['wholesale_price']:.1f}/MWh
            - Merchant margin: ${inputs['merchant_margin']:.1f}/MWh
            - Estimated annual revenue: ${inputs['annual_revenue_m']:.2f} million
            - Grid carbon intensity: {inputs['carbon_intensity']:.1f} gCO2/kWh
            - Annual carbon displacement: {inputs['annual_displacement']:.0f} tons CO2
            - Annual carbon value: ${inputs['annual_carbon_value_m']:.2f} million
            - Transmission distance: {inputs['transmission_km']:.1f} km
            - CAPEX assumption: ${inputs['capex']:.0f}/kW
            - Carbon price assumption: ${inputs['carbon_price']:.0f}/ton

            Deterministic screening signals:
            - Economics view: {inputs['economics_view']}
            - Economics rationale: {inputs['economics_reason']}
            - Carbon value view: {inputs['carbon_reason']}
            - Transmission risk: {inputs['transmission_band']}
            - Transmission rationale: {inputs['transmission_reason']}
            - Overall verdict: {inputs['verdict']}

            Output exactly five lines with these labels:
            Verdict:
            Economics:
            Carbon:
            Grid:
            Key Risk:

            Style rules:
            - 14 to 24 words per line.
            - Analytical and restrained, not promotional.
            - Use "attractive" only if the verdict is Attractive.
            - Keep the total under 130 words.
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

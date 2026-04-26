"""Brief generation model steps."""

from __future__ import annotations

import json
from typing import Any

from backend.app.models.base import BaseModelStep
from backend.app.schemas.scenario import BriefResponse


class TemplateBriefModel(BaseModelStep):
    """Deterministic site assessment brief used until an LLM is configured."""

    name = "template_brief"
    version = "1.0.0"

    def run(self, payload: dict[str, Any]) -> BriefResponse:
        site = payload["site"]
        scenario = payload.get("scenario", {})
        cf = site.get("selected_cf_mean", 0) * 100
        lcoe = site.get("lcoe_usd_per_mwh", 0)
        rev = site.get("avg_wholesale_price_usd_per_mwh", 0)
        carbon = site.get("grid_carbon_intensity_g_per_kwh", 0)
        trans = site.get("nearest_transmission_km", 0) or 0
        technology = site.get("selected_technology", "renewable")
        region = site.get("grid_zone_id", "this region")
        capacity = scenario.get("capacity_mw", 50)
        capex = scenario.get("capex_usd_per_kw", 1200)
        carbon_price = scenario.get("carbon_price_usd_per_ton", 50)

        margin = rev - lcoe
        margin_str = f"${abs(margin):.1f}/MWh {'surplus' if margin > 0 else 'deficit'}"
        carbon_value = (carbon / 1000) * carbon_price

        if lcoe < 30:
            economics = "excellent — well below national median"
        elif lcoe < 50:
            economics = "competitive"
        else:
            economics = "challenging given current CAPEX assumptions"

        text = (
            f"Site Assessment: This location in {region} offers a {technology} capacity factor "
            f"of {cf:.1f}%, yielding an estimated LCOE of ${lcoe:.1f}/MWh — economics are {economics}. "
            f"For a {capacity:.0f} MW project at ${capex:.0f}/kW CAPEX, wholesale prices average "
            f"${rev:.1f}/MWh, creating a revenue {margin_str}. "
            f"Grid carbon intensity is {carbon:.0f} gCO₂/kWh — each MWh displaces {carbon/1000:.2f} tCO₂, "
            f"worth ${carbon_value:.1f}/MWh at the current carbon price of ${carbon_price:.0f}/ton. "
            f"Nearest transmission is approximately {trans:.1f} km away. "
            "Key risk: local curtailment and interconnection constraints should be "
            "validated before committing development capital."
        )
        return BriefResponse(status="success", text=text)


class LLMBriefModel(BaseModelStep):
    """OpenAI-backed LLM brief — auto-enabled when OPENAI_API_KEY is set."""

    name = "llm_brief"
    version = "1.0.0"

    def run(self, payload: dict[str, Any]) -> BriefResponse:
        from backend.app.core.config import settings  # noqa: PLC0415

        api_key = settings.openai_api_key
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured.")

        site = payload["site"]
        scenario = payload.get("scenario", {})

        system_prompt = (
            "You are a renewable energy site assessment expert. "
            "Write a concise (130-160 word) site assessment brief for energy developers. "
            "Be specific, data-driven, and professional. Focus on economics, carbon value, and risks. "
            "Do NOT use markdown or bullet points — plain prose only."
        )
        user_prompt = (
            "Generate a site assessment brief for the following site metrics:\n"
            f"{json.dumps(site, indent=2)}\n\n"
            f"Scenario parameters:\n{json.dumps(scenario, indent=2)}"
        )

        try:
            import httpx  # noqa: PLC0415

            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 300,
                    "temperature": 0.4,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"].strip()
            return BriefResponse(status="success", text=text)

        except Exception as exc:
            # Fall back to template if LLM call fails
            fallback = TemplateBriefModel()
            result = fallback.run(payload)
            result.status = f"fallback (LLM error: {type(exc).__name__})"
            return result

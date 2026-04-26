"""Brief generation model steps."""

from __future__ import annotations

from typing import Any

from backend.app.models.base import BaseModelStep
from backend.app.schemas.scenario import BriefResponse


class TemplateBriefModel(BaseModelStep):
    """Deterministic site assessment brief used until an LLM is configured."""

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
    """Placeholder for a provider-backed LLM brief implementation."""

    name = "llm_brief"
    version = "0.1.0"

    def run(self, payload: dict[str, Any]) -> BriefResponse:
        raise NotImplementedError("LLM brief generation is not wired yet.")

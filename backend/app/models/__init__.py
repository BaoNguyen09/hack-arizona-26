"""Model registration for Lumen orchestration."""

from backend.app.models.brief import LLMBriefModel, TemplateBriefModel
from backend.app.models.county import (
    CountyScoringModel,
    RealCarbonIngestModel,
    RealPriceIngestModel,
    RealWeatherIngestModel,
    SimulatedCountyModel,
)
from backend.app.models.registry import model_registry


def register_default_models() -> None:
    """Register the default local model implementations."""
    model_registry.register(SimulatedCountyModel())
    model_registry.register(CountyScoringModel())
    model_registry.register(TemplateBriefModel())
    model_registry.register(LLMBriefModel())
    model_registry.register(RealWeatherIngestModel())
    model_registry.register(RealPriceIngestModel())
    model_registry.register(RealCarbonIngestModel())


register_default_models()

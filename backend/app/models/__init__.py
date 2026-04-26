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
    """Register the default local model implementations.

    The brief model auto-selects LLMBriefModel (OpenAI) when
    OPENAI_API_KEY is configured, otherwise falls back to
    TemplateBriefModel.  Both register under the ``template_brief``
    name so the orchestrator resolves by that key.
    """
    from backend.app.core.config import settings  # noqa: PLC0415

    model_registry.register(SimulatedCountyModel())
    model_registry.register(CountyScoringModel())

    brief_model: TemplateBriefModel | LLMBriefModel = (
        LLMBriefModel() if settings.openai_api_key else TemplateBriefModel()
    )
    # Force both to register under the canonical orchestrator key
    model_registry._models["template_brief"] = brief_model

    model_registry.register(RealWeatherIngestModel())
    model_registry.register(RealPriceIngestModel())
    model_registry.register(RealCarbonIngestModel())


register_default_models()

"""Registry for orchestration model implementations."""

from __future__ import annotations

from backend.app.models.base import BaseModelStep


class ModelRegistry:
    """In-memory registry keyed by model step name."""

    def __init__(self) -> None:
        self._models: dict[str, BaseModelStep] = {}

    def register(self, model: BaseModelStep) -> None:
        """Register or replace a model implementation."""
        self._models[model.name] = model

    def get(self, name: str) -> BaseModelStep:
        """Return a registered model by name."""
        try:
            return self._models[name]
        except KeyError as exc:
            raise KeyError(f"Model is not registered: {name}") from exc

    def versions(self) -> dict[str, str]:
        """Return registered model versions for artifact metadata."""
        return {name: model.version for name, model in self._models.items()}


model_registry = ModelRegistry()

"""Shared interfaces for pluggable model steps."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseModelStep(ABC):
    """Small contract every orchestration model implements."""

    name: str
    version: str

    @abstractmethod
    def run(self, payload: Any) -> Any:
        """Execute the model step for a typed payload."""
        raise NotImplementedError

    @property
    def model_id(self) -> str:
        """Stable identifier used in artifact metadata and cache keys."""
        return f"{self.name}:{self.version}"

"""Versioned artifact storage and content hashing."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from backend.app.core.config import settings


def stable_payload_hash(payload: dict[str, Any]) -> str:
    """Create a deterministic hash for JSON-compatible payload data."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def to_jsonable(value: Any) -> Any:
    """Convert Pydantic objects and nested values to JSON-compatible data."""
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    return value


class ArtifactStore:
    """File-backed artifact store under ``data/processed``."""

    def __init__(self, root_dir: str | Path | None = None) -> None:
        base = Path(root_dir or settings.data_dir)
        self.root = base / "processed" / "artifacts"
        self.root.mkdir(parents=True, exist_ok=True)

    def exists(self, namespace: str, key: str) -> bool:
        """Return whether an artifact exists."""
        return self._artifact_path(namespace, key).exists()

    def load(self, namespace: str, key: str) -> dict[str, Any]:
        """Load a stored artifact payload."""
        path = self._artifact_path(namespace, key)
        with path.open("r", encoding="utf-8") as file:
            data: dict[str, Any] = json.load(file)
        return data

    def save(
        self,
        namespace: str,
        key: str,
        payload: Any,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Persist payload plus metadata and return the artifact envelope."""
        directory = self.root / namespace
        directory.mkdir(parents=True, exist_ok=True)
        artifact = {
            "key": key,
            "namespace": namespace,
            "created_at": datetime.now(UTC).isoformat(),
            "metadata": to_jsonable(metadata),
            "payload": to_jsonable(payload),
        }
        path = self._artifact_path(namespace, key)
        with path.open("w", encoding="utf-8") as file:
            json.dump(artifact, file, sort_keys=True)
        return artifact

    def _artifact_path(self, namespace: str, key: str) -> Path:
        return self.root / namespace / f"{key}.json"


artifact_store = ArtifactStore()

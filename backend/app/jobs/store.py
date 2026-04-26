"""SQLite-backed job status persistence."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.core.config import settings
from backend.app.jobs.artifacts import to_jsonable


class JobStatusStore:
    """Persist local async job lifecycle state in SQLite."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        base = Path(settings.data_dir) / "processed"
        base.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path or base / "jobs.sqlite3")
        self._init_db()

    def create(
        self,
        job_id: str,
        job_type: str,
        input_hash: str,
        artifact_key: str | None = None,
    ) -> dict[str, Any]:
        """Create a queued job record."""
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO jobs (
                    job_id, job_type, status, created_at, updated_at,
                    input_hash, artifact_key, result_json, error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    job_type,
                    "queued",
                    now,
                    now,
                    input_hash,
                    artifact_key,
                    None,
                    None,
                ),
            )
        return self.get(job_id)

    def mark_running(self, job_id: str) -> None:
        """Mark a job as running."""
        self._update(job_id, status="running")

    def mark_completed(
        self,
        job_id: str,
        result: dict[str, Any],
        artifact_key: str | None = None,
    ) -> None:
        """Mark a job as completed with a JSON result."""
        self._update(
            job_id,
            status="completed",
            result_json=json.dumps(to_jsonable(result), sort_keys=True),
            artifact_key=artifact_key,
            error=None,
        )

    def mark_failed(self, job_id: str, error: str) -> None:
        """Mark a job as failed."""
        self._update(job_id, status="failed", error=error)

    def get(self, job_id: str) -> dict[str, Any]:
        """Return a job record by id."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT job_id, job_type, status, created_at, updated_at,
                       input_hash, artifact_key, result_json, error
                FROM jobs WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"Job not found: {job_id}")

        result = json.loads(row["result_json"]) if row["result_json"] else None
        return {
            "job_id": row["job_id"],
            "job_type": row["job_type"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "input_hash": row["input_hash"],
            "artifact_key": row["artifact_key"],
            "result": result,
            "error": row["error"],
        }

    def _update(self, job_id: str, **fields: Any) -> None:
        allowed = {"status", "result_json", "error", "artifact_key"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        updates["updated_at"] = _now()

        assignments = ", ".join(f"{field} = ?" for field in updates)
        values = list(updates.values()) + [job_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE jobs SET {assignments} WHERE job_id = ?", values)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    input_hash TEXT NOT NULL,
                    artifact_key TEXT,
                    result_json TEXT,
                    error TEXT
                )
                """
            )


def _now() -> str:
    return datetime.now(UTC).isoformat()


job_status_store = JobStatusStore()

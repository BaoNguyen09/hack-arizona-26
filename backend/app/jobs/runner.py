"""Local async job runner for orchestration tasks."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from backend.app.jobs.store import job_status_store


class LocalJobRunner:
    """Small in-process background runner backed by a thread pool."""

    def __init__(self, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: dict[str, Future] = {}

    def submit(
        self,
        job_type: str,
        input_hash: str,
        artifact_key: str | None,
        func: Callable[[], dict[str, Any]],
    ) -> str:
        """Create a job record and execute the callable in the background."""
        job_id = str(uuid.uuid4())
        job_status_store.create(job_id, job_type, input_hash, artifact_key)

        def wrapped() -> dict[str, Any]:
            job_status_store.mark_running(job_id)
            try:
                result = func()
            except Exception as exc:
                job_status_store.mark_failed(job_id, str(exc))
                raise
            job_status_store.mark_completed(job_id, result, artifact_key)
            return result

        self._futures[job_id] = self._executor.submit(wrapped)
        return job_id

    def wait(self, job_id: str, timeout: float | None = None) -> dict[str, Any]:
        """Wait for a submitted job and return the persisted status."""
        future = self._futures[job_id]
        future.result(timeout=timeout)
        return job_status_store.get(job_id)


job_runner = LocalJobRunner()

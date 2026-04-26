"""County-first orchestration API used by FastAPI routes."""

from __future__ import annotations

from typing import Any

from backend.app.core.config import settings
from backend.app.jobs.artifacts import artifact_store, stable_payload_hash
from backend.app.jobs.runner import job_runner
from backend.app.jobs.store import job_status_store
from backend.app.models import register_default_models  # noqa: F401
from backend.app.models.registry import model_registry
from backend.app.schemas.scenario import BriefResponse, ScenarioRequest, SiteResponse

DATA_VINTAGE = "simulated-eia-state-2026-02"


def scenario_to_dict(scenario: ScenarioRequest) -> dict[str, Any]:
    """Return a stable JSON-compatible scenario dictionary."""
    return scenario.model_dump()


def county_artifact_key(fips_code: str, scenario: ScenarioRequest) -> str:
    """Build a cache key for a county computation."""
    model_versions = {
        "simulated_county": model_registry.get("simulated_county").version,
        "county_scoring": model_registry.get("county_scoring").version,
    }
    return stable_payload_hash(
        {
            "kind": "county_site",
            "fips_code": fips_code,
            "scenario": scenario_to_dict(scenario),
            "data_vintage": DATA_VINTAGE,
            "model_versions": model_versions,
        }
    )


def brief_artifact_key(site: dict[str, Any], scenario: dict[str, Any]) -> str:
    """Build a cache key for a brief request."""
    llm_model = model_registry.get("llm_brief")
    template_model = model_registry.get("template_brief")
    brief_strategy = (
        f"{settings.gemini_model}:{llm_model.version}"
        if getattr(llm_model, "configured", False)
        else template_model.model_id
    )
    return stable_payload_hash(
        {
            "kind": "site_brief",
            "site": site,
            "scenario": scenario,
            "brief_strategy": brief_strategy,
        }
    )


def compute_county_response(fips_code: str, scenario: ScenarioRequest) -> SiteResponse:
    """Run the county generation and scoring model chain."""
    county_model = model_registry.get("simulated_county")
    scoring_model = model_registry.get("county_scoring")
    row = county_model.run(
        {"fips_code": fips_code, "technology": scenario.technology}
    )
    response = scoring_model.run({"row": row, "scenario": scenario})
    if not isinstance(response, SiteResponse):
        raise TypeError("County scoring model returned an unexpected response.")
    return response


def get_or_compute_county_response(
    fips_code: str,
    scenario: ScenarioRequest,
) -> tuple[SiteResponse, bool]:
    """Return a county response, using artifact cache when available."""
    key = county_artifact_key(fips_code, scenario)
    if artifact_store.exists("county", key):
        artifact = artifact_store.load("county", key)
        return SiteResponse(**artifact["payload"]), True

    response = compute_county_response(fips_code, scenario)
    artifact_store.save(
        "county",
        key,
        response,
        {
            "fips_code": fips_code,
            "scenario": scenario,
            "data_vintage": DATA_VINTAGE,
            "model_versions": model_registry.versions(),
        },
    )
    return response, False


def submit_county_job(fips_code: str, scenario: ScenarioRequest) -> tuple[str, bool]:
    """Submit a county computation job, or return cached marker if present."""
    key = county_artifact_key(fips_code, scenario)
    input_hash = key
    if artifact_store.exists("county", key):
        job_id = job_runner.submit(
            "county",
            input_hash,
            key,
            lambda: artifact_store.load("county", key)["payload"],
        )
        return job_id, True

    def run() -> dict[str, Any]:
        response = compute_county_response(fips_code, scenario)
        artifact = artifact_store.save(
            "county",
            key,
            response,
            {
                "fips_code": fips_code,
                "scenario": scenario,
                "data_vintage": DATA_VINTAGE,
                "model_versions": model_registry.versions(),
            },
        )
        return artifact["payload"]

    return job_runner.submit("county", input_hash, key, run), False


def generate_brief(site: dict[str, Any], scenario: dict[str, Any]) -> BriefResponse:
    """Return a brief response, using artifact cache when available."""
    key = brief_artifact_key(site, scenario)
    if artifact_store.exists("brief", key):
        artifact = artifact_store.load("brief", key)
        response = BriefResponse(**artifact["payload"])
        response.cached = True
        return response

    llm_model = model_registry.get("llm_brief")
    template_model = model_registry.get("template_brief")
    model = llm_model if getattr(llm_model, "configured", False) else template_model
    used_model = model
    try:
        response = model.run({"site": site, "scenario": scenario})
    except Exception:
        if model is template_model:
            raise
        used_model = template_model
        response = template_model.run({"site": site, "scenario": scenario})
    if not isinstance(response, BriefResponse):
        raise TypeError("Brief model returned an unexpected response.")
    artifact_store.save(
        "brief",
        key,
        response,
        {
            "scenario": scenario,
            "model_versions": {
                "llm_brief": llm_model.version,
                "template_brief": template_model.version,
            },
            "gemini_model": settings.gemini_model,
            "used_model": used_model.model_id,
        },
    )
    return response


def submit_brief_job(
    site: dict[str, Any],
    scenario: dict[str, Any],
) -> tuple[str, bool]:
    """Submit a brief generation job."""
    key = brief_artifact_key(site, scenario)
    if artifact_store.exists("brief", key):
        job_id = job_runner.submit(
            "brief",
            key,
            key,
            lambda: artifact_store.load("brief", key)["payload"],
        )
        return job_id, True

    def run() -> dict[str, Any]:
        response = generate_brief(site, scenario)
        return response.model_dump()

    return job_runner.submit("brief", key, key, run), False


def wait_for_job(job_id: str, timeout: float = 5.0) -> dict[str, Any]:
    """Wait for a local job and return its status record."""
    return job_runner.wait(job_id, timeout=timeout)


def get_job_status(job_id: str) -> dict[str, Any]:
    """Return a persisted job status."""
    return job_status_store.get(job_id)

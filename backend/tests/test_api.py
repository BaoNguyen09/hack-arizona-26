"""Tests for POST /heatmap and GET /site API endpoints.

Covers:
- 503 when no processed artifact is loaded
- Response shape when store is loaded
- Sorting, score range, cell count invariants
- Technology toggle (solar vs wind produces different scores)
- Site lookup by cell_id
- 404 for unknown cell_id
- 422 validation for bad query params
"""

import time

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.services import query as query_service

SOLAR_PAYLOAD = {
    "technology": "solar",
    "capacity_mw": 50.0,
    "capex_usd_per_kw": 1200.0,
    "opex_usd_per_kw_year": 35.0,
    "discount_rate": 0.06,
    "project_lifetime_years": 25,
    "carbon_price_usd_per_ton": 50.0,
    "cost_weight": 1.0,
    "revenue_weight": 1.0,
    "carbon_weight": 1.0,
}

WIND_PAYLOAD = {**SOLAR_PAYLOAD, "technology": "wind"}


# ---------------------------------------------------------------------------
# Unloaded behaviour — store has no data
# ---------------------------------------------------------------------------


class TestHeatmapUnloaded:
    def test_returns_503(self, client: TestClient) -> None:
        response = client.post("/heatmap", json=SOLAR_PAYLOAD)
        assert response.status_code == 503

    def test_error_detail_is_descriptive(self, client: TestClient) -> None:
        body = client.post("/heatmap", json=SOLAR_PAYLOAD).json()
        assert "detail" in body


class TestSiteUnloaded:
    def test_returns_503(self, client: TestClient) -> None:
        response = client.get("/site?cell_id=tx_001")
        assert response.status_code == 503


# ---------------------------------------------------------------------------
# Heatmap — loaded store
# ---------------------------------------------------------------------------


class TestHeatmapLoaded:
    def test_returns_200(self, loaded_client: TestClient) -> None:
        response = loaded_client.post("/heatmap", json=SOLAR_PAYLOAD)
        assert response.status_code == 200

    def test_response_has_required_top_level_fields(
        self, loaded_client: TestClient
    ) -> None:
        body = loaded_client.post("/heatmap", json=SOLAR_PAYLOAD).json()
        for field in ("technology", "score_min", "score_max", "cell_count", "cells"):
            assert field in body, f"Missing field: {field}"

    def test_cell_count_matches_dataset(self, loaded_client: TestClient) -> None:
        body = loaded_client.post("/heatmap", json=SOLAR_PAYLOAD).json()
        assert body["cell_count"] == 5
        assert len(body["cells"]) == 5

    def test_cells_sorted_ascending_by_score(self, loaded_client: TestClient) -> None:
        cells = loaded_client.post("/heatmap", json=SOLAR_PAYLOAD).json()["cells"]
        scores = [c["score"] for c in cells]
        assert scores == sorted(scores), "Cells must be sorted ascending by score"

    def test_score_min_max_consistent_with_cells(
        self, loaded_client: TestClient
    ) -> None:
        body = loaded_client.post("/heatmap", json=SOLAR_PAYLOAD).json()
        scores = [c["score"] for c in body["cells"]]
        assert pytest.approx(body["score_min"], rel=1e-6) == min(scores)
        assert pytest.approx(body["score_max"], rel=1e-6) == max(scores)

    def test_cell_has_required_fields(self, loaded_client: TestClient) -> None:
        cell = loaded_client.post("/heatmap", json=SOLAR_PAYLOAD).json()["cells"][0]
        for field in (
            "cell_id",
            "lat",
            "lon",
            "score",
            "raw_capacity_factor",
            "raw_lcoe_usd_per_mwh",
            "raw_revenue_usd_per_mwh",
            "raw_carbon_value_usd_per_mwh",
        ):
            assert field in cell, f"Missing cell field: {field}"

    def test_technology_reflected_in_response(self, loaded_client: TestClient) -> None:
        body = loaded_client.post("/heatmap", json=SOLAR_PAYLOAD).json()
        assert body["technology"] == "solar"

        body_wind = loaded_client.post("/heatmap", json=WIND_PAYLOAD).json()
        assert body_wind["technology"] == "wind"

    def test_solar_and_wind_produce_different_scores(
        self, loaded_client: TestClient
    ) -> None:
        solar_scores = {
            c["cell_id"]: c["score"]
            for c in loaded_client.post("/heatmap", json=SOLAR_PAYLOAD).json()["cells"]
        }
        wind_scores = {
            c["cell_id"]: c["score"]
            for c in loaded_client.post("/heatmap", json=WIND_PAYLOAD).json()["cells"]
        }
        # At least one cell must have a different score between technologies
        assert any(solar_scores[k] != wind_scores[k] for k in solar_scores)

    def test_score_min_less_than_score_max(self, loaded_client: TestClient) -> None:
        body = loaded_client.post("/heatmap", json=SOLAR_PAYLOAD).json()
        assert body["score_min"] < body["score_max"]

    def test_capacity_factor_in_range(self, loaded_client: TestClient) -> None:
        cells = loaded_client.post("/heatmap", json=SOLAR_PAYLOAD).json()["cells"]
        for cell in cells:
            assert 0.0 <= cell["raw_capacity_factor"] <= 1.0

    def test_lat_lon_in_valid_range(self, loaded_client: TestClient) -> None:
        cells = loaded_client.post("/heatmap", json=SOLAR_PAYLOAD).json()["cells"]
        for cell in cells:
            assert -90 <= cell["lat"] <= 90
            assert -180 <= cell["lon"] <= 180

    def test_invalid_technology_returns_422(self, loaded_client: TestClient) -> None:
        bad_payload = {**SOLAR_PAYLOAD, "technology": "nuclear"}
        response = loaded_client.post("/heatmap", json=bad_payload)
        assert response.status_code == 422

    def test_negative_capacity_returns_422(self, loaded_client: TestClient) -> None:
        bad_payload = {**SOLAR_PAYLOAD, "capacity_mw": -10}
        response = loaded_client.post("/heatmap", json=bad_payload)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Site — loaded store
# ---------------------------------------------------------------------------


class TestSiteLoaded:
    def test_returns_200_by_cell_id(self, loaded_client: TestClient) -> None:
        response = loaded_client.get("/site?cell_id=tx_001&technology=solar")
        assert response.status_code == 200

    def test_response_has_required_fields(self, loaded_client: TestClient) -> None:
        body = loaded_client.get("/site?cell_id=tx_001&technology=solar").json()
        assert "site" in body
        assert "scenario" in body
        assert "score_rank" in body
        assert "total_cells" in body

    def test_total_cells_matches_dataset(self, loaded_client: TestClient) -> None:
        body = loaded_client.get("/site?cell_id=tx_001&technology=solar").json()
        assert body["total_cells"] == 5

    def test_score_rank_is_valid(self, loaded_client: TestClient) -> None:
        body = loaded_client.get("/site?cell_id=tx_001&technology=solar").json()
        assert 1 <= body["score_rank"] <= 5

    def test_site_cell_id_matches_request(self, loaded_client: TestClient) -> None:
        body = loaded_client.get("/site?cell_id=nm_001&technology=solar").json()
        assert body["site"]["cell_id"] == "nm_001"

    def test_site_has_all_metric_fields(self, loaded_client: TestClient) -> None:
        site = loaded_client.get("/site?cell_id=tx_001&technology=solar").json()["site"]
        for field in (
            "cell_id",
            "lat",
            "lon",
            "solar_cf_mean",
            "wind_cf_mean",
            "selected_cf_mean",
            "lcoe_usd_per_mwh",
            "lcoe_components",
            "capex_total_usd_millions",
            "avg_wholesale_price_usd_per_mwh",
            "estimated_annual_revenue_usd_millions",
            "grid_carbon_intensity_g_per_kwh",
            "annual_carbon_displacement_tons",
            "carbon_value_usd_per_mwh",
        ):
            assert field in site, f"Missing site field: {field}"

    def test_lcoe_components_sum_to_lcoe(self, loaded_client: TestClient) -> None:
        site = loaded_client.get("/site?cell_id=tx_001&technology=solar").json()["site"]
        capex_share = site["lcoe_components"]["capex_share_usd_per_mwh"]
        opex_share = site["lcoe_components"]["opex_share_usd_per_mwh"]
        total = site["lcoe_usd_per_mwh"]
        assert pytest.approx(capex_share + opex_share, rel=1e-4) == total

    def test_unknown_cell_id_returns_404(self, loaded_client: TestClient) -> None:
        response = loaded_client.get("/site?cell_id=does_not_exist")
        assert response.status_code == 404

    def test_missing_all_lookup_params_returns_404(
        self, loaded_client: TestClient
    ) -> None:
        # No cell_id and no lat/lon → ValueError in service → 404
        response = loaded_client.get("/site?technology=solar")
        assert response.status_code == 404

    def test_scenario_echoed_in_response(self, loaded_client: TestClient) -> None:
        body = loaded_client.get(
            "/site?cell_id=tx_001&technology=wind&carbon_price_usd_per_ton=100"
        ).json()
        assert body["scenario"]["technology"] == "wind"
        assert body["scenario"]["carbon_price_usd_per_ton"] == 100.0


# ---------------------------------------------------------------------------
# Stub endpoints
# ---------------------------------------------------------------------------


class TestStubs:
    def test_brief_stub_returns_200(self, client: TestClient) -> None:
        response = client.post("/brief")
        assert response.status_code == 200
        assert response.json()["status"] == "not_implemented"

    def test_query_unparsed_returns_friendly_message(self, client: TestClient) -> None:
        response = client.post("/query", json={"query": "tell me something interesting"})
        assert response.status_code == 200
        body = response.json()
        assert body["parsed"] is False
        assert "couldn't parse" in body["message"].lower()
        assert body["matched_cell_ids"] == []
        assert body["matched_county_fips"] == []

    def test_query_returns_structured_filters_and_matches(
        self,
        loaded_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        county_df = pd.DataFrame(
            {
                "fips": ["48201", "35001", "06037"],
                "cell_id": ["county_48201", "county_35001", "county_06037"],
                "lat": [29.76, 35.08, 34.05],
                "lon": [-95.36, -106.65, -118.24],
                "solar_cf_mean": [0.29, 0.31, 0.22],
                "wind_cf_mean": [0.20, 0.25, 0.18],
                "price_usd_per_mwh_mean": [42.0, 39.0, 45.0],
                "carbon_g_per_kwh_mean": [430.0, 320.0, 210.0],
                "nearest_transmission_km": [8.0, 12.0, 5.0],
                "renewable_percent": [28.0, 52.0, 48.0],
                "county_name": ["Harris", "Bernalillo", "Los Angeles"],
                "state_fips": ["48", "35", "06"],
                "state_abbr": ["TX", "NM", "CA"],
                "state_name": ["Texas", "New Mexico", "California"],
            }
        )
        monkeypatch.setattr(query_service, "get_county_index", lambda: county_df)

        response = loaded_client.post(
            "/query",
            json={
                "query": (
                    "Find solar in Texas with capacity factor above 25% and "
                    "LCOE below 60"
                )
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["parsed"] is True
        assert body["filters"]["technology"] == "solar"
        assert body["filters"]["region"] == "texas"
        assert body["filters"]["min_cf"] == pytest.approx(0.25)
        assert body["filters"]["max_lcoe"] == pytest.approx(60.0)
        assert body["matched_cell_ids"] == ["tx_001"]
        assert body["matched_county_fips"] == ["48201"]

    def test_query_supports_lcoe_greater_than(
        self,
        loaded_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        county_df = pd.DataFrame(
            {
                "fips": ["48201", "48113"],
                "cell_id": ["county_48201", "county_48113"],
                "lat": [29.76, 32.76],
                "lon": [-95.36, -96.79],
                "solar_cf_mean": [0.29, 0.31],
                "wind_cf_mean": [0.20, 0.25],
                "price_usd_per_mwh_mean": [42.0, 39.0],
                "carbon_g_per_kwh_mean": [430.0, 320.0],
                "nearest_transmission_km": [8.0, 12.0],
                "renewable_percent": [28.0, 52.0],
                "county_name": ["Harris", "Dallas"],
                "state_fips": ["48", "48"],
                "state_abbr": ["TX", "TX"],
                "state_name": ["Texas", "Texas"],
            }
        )
        monkeypatch.setattr(query_service, "get_county_index", lambda: county_df)

        response = loaded_client.post(
            "/query",
            json={"query": "Data in Texas with LCOE greater than 20"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["parsed"] is True
        assert body["filters"]["region"] == "texas"
        assert body["filters"]["min_lcoe"] == pytest.approx(20.0)
        assert body["matched_cell_ids"] == ["tx_001"]
        assert set(body["matched_county_fips"]) == {"48113", "48201"}


class TestJobs:
    def test_county_job_completes_with_site_response(self, client: TestClient) -> None:
        response = client.post(
            "/jobs/county",
            json={"fips_code": "48201", "scenario": SOLAR_PAYLOAD},
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]

        status = _wait_for_completed_job(client, job_id)
        assert status["job_type"] == "county"
        assert status["result"]["site"]["cell_id"] == "county_48201"

    def test_brief_job_completes_with_text(self, client: TestClient) -> None:
        site = {
            "selected_cf_mean": 0.26,
            "lcoe_usd_per_mwh": 32.4,
            "avg_wholesale_price_usd_per_mwh": 38.2,
            "grid_carbon_intensity_g_per_kwh": 432,
            "nearest_transmission_km": 18.3,
            "selected_technology": "solar",
        }
        response = client.post(
            "/jobs/brief",
            json={"site": site, "scenario": SOLAR_PAYLOAD},
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]

        status = _wait_for_completed_job(client, job_id)
        assert status["job_type"] == "brief"
        assert "Site Assessment" in status["result"]["text"]

    def test_unknown_job_returns_404(self, client: TestClient) -> None:
        response = client.get("/jobs/does-not-exist")
        assert response.status_code == 404


def _wait_for_completed_job(client: TestClient, job_id: str) -> dict:
    for _ in range(20):
        status_response = client.get(f"/jobs/{job_id}")
        assert status_response.status_code == 200
        status = status_response.json()
        if status["status"] == "completed":
            return status
        if status["status"] == "failed":
            raise AssertionError(status["error"])
        time.sleep(0.01)
    raise AssertionError(f"Job did not complete: {job_id}")

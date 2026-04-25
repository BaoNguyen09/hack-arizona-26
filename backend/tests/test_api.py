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

import pytest
from fastapi.testclient import TestClient


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

    def test_response_has_required_top_level_fields(self, loaded_client: TestClient) -> None:
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

    def test_score_min_max_consistent_with_cells(self, loaded_client: TestClient) -> None:
        body = loaded_client.post("/heatmap", json=SOLAR_PAYLOAD).json()
        scores = [c["score"] for c in body["cells"]]
        assert pytest.approx(body["score_min"], rel=1e-6) == min(scores)
        assert pytest.approx(body["score_max"], rel=1e-6) == max(scores)

    def test_cell_has_required_fields(self, loaded_client: TestClient) -> None:
        cell = loaded_client.post("/heatmap", json=SOLAR_PAYLOAD).json()["cells"][0]
        for field in (
            "cell_id", "lat", "lon", "score",
            "raw_capacity_factor", "raw_lcoe_usd_per_mwh",
            "raw_revenue_usd_per_mwh", "raw_carbon_value_usd_per_mwh",
        ):
            assert field in cell, f"Missing cell field: {field}"

    def test_technology_reflected_in_response(self, loaded_client: TestClient) -> None:
        body = loaded_client.post("/heatmap", json=SOLAR_PAYLOAD).json()
        assert body["technology"] == "solar"

        body_wind = loaded_client.post("/heatmap", json=WIND_PAYLOAD).json()
        assert body_wind["technology"] == "wind"

    def test_solar_and_wind_produce_different_scores(self, loaded_client: TestClient) -> None:
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
            "cell_id", "lat", "lon",
            "solar_cf_mean", "wind_cf_mean", "selected_cf_mean",
            "lcoe_usd_per_mwh", "lcoe_components", "capex_total_usd_millions",
            "avg_wholesale_price_usd_per_mwh", "estimated_annual_revenue_usd_millions",
            "grid_carbon_intensity_g_per_kwh", "annual_carbon_displacement_tons",
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

    def test_missing_all_lookup_params_returns_404(self, loaded_client: TestClient) -> None:
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

    def test_query_stub_returns_200(self, client: TestClient) -> None:
        response = client.post("/query")
        assert response.status_code == 200
        assert response.json()["status"] == "not_implemented"

"""Shared fixtures for the Lumen API harness test suite.

Strategy:
- All tests use a plain pandas DataFrame (no GeoPackage / geopandas needed).
- ``reset_store`` is autouse so every test starts from a clean singleton.
- ``loaded_store`` pre-populates the singleton via ``load_from_dataframe``.
- The FastAPI lifespan tries (and silently fails) to read a missing .gpkg file,
  leaving pre-set store state intact.
"""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.data.processed_store import ProcessedStore
from backend.app.main import app

# ---------------------------------------------------------------------------
# Minimal 5-cell dataset covering the required contract columns
# ---------------------------------------------------------------------------
MINIMAL_DF = pd.DataFrame(
    {
        "cell_id": ["tx_001", "ks_001", "nm_001", "ok_001", "co_001"],
        "lat": [31.97, 39.01, 35.08, 35.47, 39.55],
        "lon": [-99.90, -98.48, -106.65, -97.52, -105.78],
        # TX/NM are the "best" solar sites; KS/ND are the "best" wind sites
        "solar_cf_mean": [0.27, 0.20, 0.28, 0.22, 0.24],
        "wind_cf_mean": [0.40, 0.45, 0.35, 0.42, 0.38],
        "price_usd_per_mwh_mean": [34.0, 28.0, 30.0, 32.0, 29.0],
        "carbon_g_per_kwh_mean": [410.0, 380.0, 350.0, 420.0, 400.0],
    }
)


@pytest.fixture(autouse=True)
def reset_store():
    """Reset the ProcessedStore singleton before and after every test."""
    ProcessedStore._instance = None
    yield
    ProcessedStore._instance = None


@pytest.fixture()
def minimal_df() -> pd.DataFrame:
    """Return a copy of the minimal valid DataFrame."""
    return MINIMAL_DF.copy()


@pytest.fixture()
def loaded_store(minimal_df: pd.DataFrame) -> ProcessedStore:
    """Return a fully loaded ProcessedStore populated from the minimal DataFrame.

    Uses ``load_from_dataframe`` so no GeoPackage / geopandas is required.
    """
    store = ProcessedStore.get_instance()
    store.load_from_dataframe(minimal_df)
    return store


@pytest.fixture()
def client() -> TestClient:
    """Unloaded TestClient — store has no data, mimics cold start without .gpkg."""
    return TestClient(app)


@pytest.fixture()
def loaded_client(loaded_store: ProcessedStore) -> TestClient:
    """TestClient with a pre-loaded store.

    ``loaded_store`` is created first (populating the singleton), then the
    TestClient is constructed.  The lifespan ``store.load()`` call raises
    FileNotFoundError (no .gpkg file exists) which is silently caught in
    ``main.py``, leaving our pre-populated singleton intact.
    """
    return TestClient(app)

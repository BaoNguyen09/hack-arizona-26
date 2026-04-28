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
from backend.app.data.sqlite_store import SqliteProcessedStore
from backend.app.db.schema import init_db
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
    """Reset the ProcessedStore singleton and heatmap cache before/after every test."""
    from backend.app.core.perf import heatmap_cache  # noqa: PLC0415

    ProcessedStore._instance = None
    SqliteProcessedStore._instance = None
    heatmap_cache.clear()
    yield
    ProcessedStore._instance = None
    SqliteProcessedStore._instance = None
    heatmap_cache.clear()


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


@pytest.fixture()
def sqlite_county_client(tmp_path: "pytest.TempPathFactory", monkeypatch: pytest.MonkeyPatch) -> TestClient:  # type: ignore[name-defined]
    """TestClient backed by a minimal SQLite DB containing one county row."""
    from backend.app.core.config import settings  # noqa: PLC0415
    from backend.app.db.schema import connect  # noqa: PLC0415

    db_path = tmp_path / "lumen.sqlite3"  # type: ignore[operator]
    init_db(db_path)

    # Create a minimal snapshot with one county. Use Los Angeles County (06037).
    snapshot_id = "test_snapshot"
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO feature_snapshots(snapshot_id, created_at, source, notes)
            VALUES(?, ?, ?, ?)
            """,
            (snapshot_id, "2026-01-01T00:00:00Z", "test", "pytest seed"),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO spatial_units(spatial_unit_id, unit_type, fips, name, lat, lon)
            VALUES(?, 'county', ?, ?, ?, ?)
            """,
            ("county_06037", "06037", "Los Angeles", 34.196398, -118.261861),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO spatial_unit_features(
                snapshot_id, spatial_unit_id,
                solar_cf_mean, wind_cf_mean,
                price_usd_per_mwh_mean, carbon_g_per_kwh_mean,
                nearest_transmission_km, price_hub_id, grid_zone_id, load_gw, renewable_percent
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                "county_06037",
                0.25,
                0.30,
                45.0,
                200.0,
                10.0,
                "EIA_STATE_CA",
                "CAMX",
                1.0,
                40.0,
            ),
        )

    monkeypatch.setattr(settings, "use_sqlite_db", True)
    monkeypatch.setattr(settings, "lumen_db_path", str(db_path))
    return TestClient(app)

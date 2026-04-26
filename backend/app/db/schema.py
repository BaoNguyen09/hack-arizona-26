"""SQLite + SpatiaLite schema for Lumen.

This module owns the canonical DDL for the local demo database.

Design goals:
- Keep tables aligned with the existing scoring/data contracts.
- Prefer plain SQLite types; store timestamps as ISO-8601 TEXT to match existing code.
- Enable SpatiaLite geometry when available, but fall back gracefully if the extension
  can't be loaded (still allows local demo for non-spatial queries).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_VERSION = 1


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection suitable for SpatiaLite initialization."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def try_enable_spatialite(conn: sqlite3.Connection) -> bool:
    """Attempt to load SpatiaLite. Returns True if enabled.

    On macOS, the module is commonly named `mod_spatialite`.
    """
    try:
        conn.enable_load_extension(True)
    except Exception:
        return False

    for module_name in ("mod_spatialite", "mod_spatialite.dylib", "libspatialite"):
        try:
            conn.load_extension(module_name)
            return True
        except Exception:
            continue
    return False


def init_db(db_path: str | Path) -> None:
    """Create the database file and apply schema if needed."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        spatial_enabled = try_enable_spatialite(conn)
        _init_pragmas(conn)
        _init_meta(conn)
        _create_tables(conn, spatial_enabled=spatial_enabled)
        _set_schema_version(conn, SCHEMA_VERSION)


def _init_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")


def _init_meta(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
        ("schema_version", str(version)),
    )


def _create_tables(conn: sqlite3.Connection, spatial_enabled: bool) -> None:
    # Core spatial units (county now; grid cells later)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS spatial_units (
            spatial_unit_id TEXT PRIMARY KEY,
            unit_type TEXT NOT NULL CHECK (unit_type IN ('county','grid_cell')),
            fips TEXT,
            name TEXT,
            lat REAL NOT NULL,
            lon REAL NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_spatial_units_type_fips ON spatial_units(unit_type, fips)"
    )

    # Feature snapshots (versioned processed artifacts)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS feature_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            source TEXT NOT NULL,
            time_start TEXT,
            time_end TEXT,
            notes TEXT
        )
        """
    )

    # Per-spatial-unit mean features (matches contracts.py columns)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS spatial_unit_features (
            snapshot_id TEXT NOT NULL,
            spatial_unit_id TEXT NOT NULL,
            solar_cf_mean REAL NOT NULL,
            wind_cf_mean REAL NOT NULL,
            price_usd_per_mwh_mean REAL NOT NULL,
            carbon_g_per_kwh_mean REAL NOT NULL,
            nearest_transmission_km REAL,
            price_hub_id TEXT,
            grid_zone_id TEXT,
            load_gw REAL,
            renewable_percent REAL,
            PRIMARY KEY (snapshot_id, spatial_unit_id),
            FOREIGN KEY (snapshot_id) REFERENCES feature_snapshots(snapshot_id),
            FOREIGN KEY (spatial_unit_id) REFERENCES spatial_units(spatial_unit_id)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_features_snapshot_inputs
        ON spatial_unit_features(snapshot_id, price_hub_id, grid_zone_id)
        """
    )

    # Dimension tables
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS price_hubs (
            price_hub_id TEXT PRIMARY KEY,
            name TEXT,
            iso TEXT,
            lat REAL,
            lon REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS grid_zones (
            grid_zone_id TEXT PRIMARY KEY,
            name TEXT,
            region TEXT
        )
        """
    )

    # Time series tables (optional, but we create them for bootstrap)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS hub_prices_hourly (
            price_hub_id TEXT NOT NULL,
            ts_utc TEXT NOT NULL,
            price_usd_per_mwh REAL NOT NULL,
            PRIMARY KEY (price_hub_id, ts_utc),
            FOREIGN KEY (price_hub_id) REFERENCES price_hubs(price_hub_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS zone_carbon_hourly (
            grid_zone_id TEXT NOT NULL,
            ts_utc TEXT NOT NULL,
            carbon_g_per_kwh REAL NOT NULL,
            PRIMARY KEY (grid_zone_id, ts_utc),
            FOREIGN KEY (grid_zone_id) REFERENCES grid_zones(grid_zone_id)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS spatial_unit_generation_hourly (
            snapshot_id TEXT NOT NULL,
            spatial_unit_id TEXT NOT NULL,
            technology TEXT NOT NULL CHECK (technology IN ('solar','wind')),
            ts_utc TEXT NOT NULL,
            cf REAL,
            mw_at_1mw_nameplate REAL,
            PRIMARY KEY (snapshot_id, spatial_unit_id, technology, ts_utc),
            FOREIGN KEY (snapshot_id) REFERENCES feature_snapshots(snapshot_id),
            FOREIGN KEY (spatial_unit_id) REFERENCES spatial_units(spatial_unit_id)
        )
        """
    )

    # Scenarios & runs (local demo caching / reproducibility)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scenarios (
            scenario_id TEXT PRIMARY KEY,
            scenario_hash TEXT NOT NULL UNIQUE,
            scenario_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scenario_runs (
            run_id TEXT PRIMARY KEY,
            scenario_id TEXT NOT NULL,
            snapshot_id TEXT NOT NULL,
            computed_at TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            FOREIGN KEY (scenario_id) REFERENCES scenarios(scenario_id),
            FOREIGN KEY (snapshot_id) REFERENCES feature_snapshots(snapshot_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_scenario_runs_lookup ON scenario_runs(scenario_id, snapshot_id)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scenario_run_results (
            run_id TEXT NOT NULL,
            spatial_unit_id TEXT NOT NULL,
            selected_cf REAL NOT NULL,
            lcoe_usd_per_mwh REAL NOT NULL,
            revenue_usd_per_mwh REAL NOT NULL,
            carbon_value_usd_per_mwh REAL NOT NULL,
            composite_score REAL NOT NULL,
            annual_generation_mwh REAL NOT NULL,
            rank INTEGER NOT NULL,
            PRIMARY KEY (run_id, spatial_unit_id),
            FOREIGN KEY (run_id) REFERENCES scenario_runs(run_id),
            FOREIGN KEY (spatial_unit_id) REFERENCES spatial_units(spatial_unit_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_run_results_rank ON scenario_run_results(run_id, rank)"
    )

    # Brief cache (LLM or template) keyed by stable hash
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS brief_cache (
            brief_hash TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            model TEXT,
            prompt_version TEXT,
            brief_text TEXT NOT NULL,
            site_spatial_unit_id TEXT,
            scenario_hash TEXT
        )
        """
    )

    # Jobs table (compatible with existing JobStatusStore)
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

    # Ingest provenance
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ingests (
            ingest_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL,
            details_json TEXT
        )
        """
    )

    # Spatial overlays (plants, transmission). Geometry optional if SpatiaLite missing.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS plants (
            plant_id TEXT PRIMARY KEY,
            name TEXT,
            fuel_type TEXT,
            capacity_mw REAL,
            lat REAL,
            lon REAL,
            source TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transmission_lines (
            line_id TEXT PRIMARY KEY,
            name TEXT,
            voltage_kv REAL,
            source TEXT
        )
        """
    )

    if spatial_enabled:
        # Initialize spatial metadata if not present
        conn.execute("SELECT InitSpatialMetaData(1);")

        # Add centroid geometry to spatial_units
        conn.execute(
            "SELECT AddGeometryColumn('spatial_units', 'geom', 4326, 'POINT', 'XY');"
        )
        conn.execute("SELECT CreateSpatialIndex('spatial_units', 'geom');")

        # Plants point geometry
        conn.execute("SELECT AddGeometryColumn('plants', 'geom', 4326, 'POINT', 'XY');")
        conn.execute("SELECT CreateSpatialIndex('plants', 'geom');")

        # Transmission line geometry
        conn.execute(
            "SELECT AddGeometryColumn('transmission_lines', 'geom', 4326, 'LINESTRING', 'XY');"
        )
        conn.execute("SELECT CreateSpatialIndex('transmission_lines', 'geom');")


"""Bootstrap a local Lumen SQLite + SpatiaLite database.

This script is intended to be the one-command setup for a local demo:
- Create DB + schema
- Seed counties (centroids + baseline features)
- Optionally ingest external datasets (plants, transmission, prices, carbon, weather)

By default it runs the always-available deterministic seed so the backend works
immediately even if network sources fail.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import zipfile
from datetime import UTC, datetime
from io import TextIOWrapper
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from backend.app.data.county_store import generate_county_data
from backend.app.db.schema import connect, init_db, try_enable_spatialite


DEFAULT_DB_PATH = Path("data/processed/lumen.sqlite3")
DEFAULT_COUNTY_GAZETTEER_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2024_Gazetteer/2024_Gaz_counties_national.zip"
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap Lumen local database.")
    parser.add_argument(
        "--db",
        type=str,
        default=str(DEFAULT_DB_PATH),
        help="Path to SQLite database file.",
    )
    parser.add_argument(
        "--county-gazetteer-url",
        type=str,
        default=DEFAULT_COUNTY_GAZETTEER_URL,
        help="US Census county gazetteer zip URL (for FIPS+centroids).",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Skip deterministic county seed (not recommended).",
    )
    parser.add_argument(
        "--with-eia860",
        action="store_true",
        help="Ingest EIA Form 860 plants (requires providing a file/url in v1).",
    )
    parser.add_argument(
        "--with-hifld",
        action="store_true",
        help="Ingest HIFLD transmission lines (requires providing a file/url in v1).",
    )
    parser.add_argument(
        "--with-eia-prices",
        action="store_true",
        help="Ingest EIA prices (requires EIA_API_KEY env var in v1).",
    )
    parser.add_argument(
        "--with-egrid",
        action="store_true",
        help="Ingest EPA eGRID (requires providing a file/url in v1).",
    )
    parser.add_argument(
        "--with-electricitymap",
        action="store_true",
        help="Ingest ElectricityMap carbon data (requires ELECTRICITY_MAPS_API_KEY).",
    )
    parser.add_argument(
        "--with-gfs",
        action="store_true",
        help="Ingest NOAA GFS weather (heavy; stubbed in v1).",
    )
    parser.add_argument(
        "--input",
        type=str,
        default="",
        help="Optional path/URL to a dataset archive for ingesters that require one (v1).",
    )

    args = parser.parse_args(argv)

    db_path = Path(args.db)
    init_db(db_path)
    print(f"Initialized DB at {db_path}")

    if not args.no_seed:
        seed_counties(db_path, args.county_gazetteer_url)

    # v1: external ingesters are scaffolded behind flags; some require API keys
    # or known-good dataset URLs. We register ingest provenance for visibility.
    if args.with_eia860:
        ingest_mark(db_path, source="eia860", status="skipped", details={"reason": "v1 expects --input to be a local EIA-860 CSV/ZIP path; ingestion implementation pending."})
        print("EIA-860 ingest is scaffolded; provide dataset and implement parser next.")
    if args.with_hifld:
        ingest_mark(db_path, source="hifld_transmission", status="skipped", details={"reason": "v1 expects --input to be a local HIFLD GeoJSON path; ingestion implementation pending."})
        print("HIFLD ingest is scaffolded; provide dataset and implement parser next.")
    if args.with_eia_prices:
        ingest_mark(db_path, source="eia_prices", status="skipped", details={"reason": "v1 expects EIA_API_KEY and hub mapping; ingestion implementation pending."})
        print("EIA price ingest is scaffolded; implement API fetch next.")
    if args.with_egrid:
        ingest_mark(db_path, source="epa_egrid", status="skipped", details={"reason": "v1 expects eGRID CSV path/url; ingestion implementation pending."})
        print("eGRID ingest is scaffolded; implement downloader/parser next.")
    if args.with_electricitymap:
        ingest_mark(db_path, source="electricitymap", status="skipped", details={"reason": "v1 expects ELECTRICITY_MAPS_API_KEY; ingestion implementation pending."})
        print("ElectricityMap ingest is scaffolded; implement API fetch next.")
    if args.with_gfs:
        ingest_mark(db_path, source="noaa_gfs", status="skipped", details={"reason": "GFS ingest is heavy; implement precompute pipeline next."})
        print("GFS ingest is scaffolded; implement pipeline next.")

    print("Done.")
    return 0


def ingest_mark(db_path: Path, source: str, status: str, details: dict[str, Any]) -> None:
    ingest_id = f"{source}:{_now()}"
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO ingests(ingest_id, source, started_at, completed_at, status, details_json)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (ingest_id, source, _now(), _now(), status, json.dumps(details, sort_keys=True)),
        )


def seed_counties(db_path: Path, county_gazetteer_url: str) -> None:
    """Seed all counties using deterministic features and Census centroids."""
    print("Seeding counties from gazetteer centroids + deterministic features...")

    counties = load_county_centroids(county_gazetteer_url)
    created_at = _now()
    snapshot_id = f"seed_counties:{created_at}"

    with connect(db_path) as conn:
        spatial_enabled = try_enable_spatialite(conn)

        conn.execute(
            """
            INSERT OR REPLACE INTO feature_snapshots(snapshot_id, created_at, source, notes)
            VALUES(?, ?, ?, ?)
            """,
            (snapshot_id, created_at, "deterministic_seed", "Deterministic baseline seed"),
        )

        # Insert spatial units
        spatial_rows = []
        feature_rows = []
        for fips, name, lat, lon in counties:
            spatial_unit_id = f"county_{fips}"
            spatial_rows.append((spatial_unit_id, "county", fips, name, lat, lon))

            base = generate_county_data(fips, technology="solar")
            # Override with real centroid coords from gazetteer
            base["lat"] = lat
            base["lon"] = lon

            feature_rows.append(
                (
                    snapshot_id,
                    spatial_unit_id,
                    float(base["solar_cf_mean"]),
                    float(base["wind_cf_mean"]),
                    float(base["price_usd_per_mwh_mean"]),
                    float(base["carbon_g_per_kwh_mean"]),
                    float(base.get("nearest_transmission_km", 0.0)),
                    str(base.get("price_hub_id")) if base.get("price_hub_id") else None,
                    str(base.get("grid_zone_id")) if base.get("grid_zone_id") else None,
                    float(base.get("load_gw")) if base.get("load_gw") is not None else None,
                    float(base.get("renewable_percent"))
                    if base.get("renewable_percent") is not None
                    else None,
                )
            )

        conn.executemany(
            """
            INSERT OR REPLACE INTO spatial_units(
                spatial_unit_id, unit_type, fips, name, lat, lon
            ) VALUES(?, ?, ?, ?, ?, ?)
            """,
            spatial_rows,
        )

        conn.executemany(
            """
            INSERT OR REPLACE INTO spatial_unit_features(
                snapshot_id, spatial_unit_id,
                solar_cf_mean, wind_cf_mean,
                price_usd_per_mwh_mean, carbon_g_per_kwh_mean,
                nearest_transmission_km,
                price_hub_id, grid_zone_id, load_gw, renewable_percent
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            feature_rows,
        )

        if spatial_enabled:
            # Populate POINT geometry from lat/lon for spatial_units.
            conn.execute(
                """
                UPDATE spatial_units
                SET geom = MakePoint(lon, lat, 4326)
                WHERE geom IS NULL
                """
            )

    print(f"Seeded {len(counties)} counties into snapshot {snapshot_id}")


def load_county_centroids(url_or_path: str) -> list[tuple[str, str, float, float]]:
    """Return list of (fips, name, lat, lon) for US counties."""
    data = fetch_bytes(url_or_path)
    zf = zipfile.ZipFile(data)  # type: ignore[arg-type]
    # The archive contains a single .txt with tab-delimited rows.
    txt_names = [n for n in zf.namelist() if n.endswith(".txt")]
    if not txt_names:
        raise RuntimeError("County gazetteer archive did not contain a .txt file.")

    with zf.open(txt_names[0], "r") as raw:
        wrapper = TextIOWrapper(raw, encoding="utf-8", newline="")
        reader = csv.DictReader(wrapper, delimiter="\t")
        rows: list[tuple[str, str, float, float]] = []
        for r in reader:
            # Columns per Census gazetteer: GEOID, NAME, INTPTLAT, INTPTLONG, etc.
            geoid = (r.get("GEOID") or "").strip()
            name = (r.get("NAME") or "").strip()
            lat = float((r.get("INTPTLAT") or "0").strip())
            lon = float((r.get("INTPTLONG") or "0").strip())
            if len(geoid) == 5:
                rows.append((geoid, name, lat, lon))
        if not rows:
            raise RuntimeError("No county rows parsed from gazetteer.")
        return rows


def fetch_bytes(url_or_path: str) -> Any:
    """Fetch into a file-like object usable by ZipFile.

    - If url_or_path is a local path, open it.
    - If it's a URL, download to an in-memory BytesIO.
    """
    from io import BytesIO

    parsed = urlparse(url_or_path)
    if parsed.scheme in ("http", "https"):
        resp = requests.get(url_or_path, timeout=60)
        resp.raise_for_status()
        return BytesIO(resp.content)
    return BytesIO(Path(url_or_path).read_bytes())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


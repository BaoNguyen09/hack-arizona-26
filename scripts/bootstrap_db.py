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
from shapely.geometry import Point

# Ensure repo root is on sys.path so `backend.*` imports work when invoked as:
#   python scripts/bootstrap_db.py
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
        try:
            ingest_eia_state_retail_prices(db_path)
        except Exception as exc:
            ingest_mark(
                db_path,
                source="eia_prices",
                status="failed",
                details={"error": str(exc)},
            )
            raise
    if args.with_egrid:
        try:
            ingest_egrid_subregion_carbon(db_path)
        except Exception as exc:
            ingest_mark(
                db_path,
                source="epa_egrid",
                status="failed",
                details={"error": str(exc)},
            )
            raise
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


EGRID2023_SUBREGION_SHAPEFILE_URL = (
    "https://www.epa.gov/system/files/other-files/2025-01/egrid2023_subregions.zip"
)
EGRID2023_SUBREGION_RATES_SOURCE_URL = "https://www.epa.gov/egrid/summary-data"

# From EPA eGRID 2023 summary tables (Rev2). Values are CO2e total output emission
# rates in lb/MWh by eGRID subregion.
EGRID2023_CO2E_LB_PER_MWH: dict[str, float] = {
    "AKGD": 905.109,
    "AKMS": 522.400,
    "AZNM": 706.189,
    "CAMX": 429.983,
    "ERCT": 736.629,
    "FRCC": 784.785,
    "HIMS": 1133.294,
    "HIOA": 1498.947,
    "MROE": 1404.963,
    "MROW": 926.552,
    "NEWE": 543.178,
    "NWPP": 635.267,
    "NYCW": 865.744,
    "NYLI": 1189.333,
    "NYUP": 242.776,
    "PRMS": 1548.530,
    "RFCE": 599.170,
    "RFCM": 975.978,
    "RFCW": 916.054,
    "RMPA": 1042.539,
    "SPNO": 867.740,
    "SPSO": 875.567,
    "SRMV": 741.741,
    "SRMW": 1248.582,
    "SRSO": 846.007,
    "SRTV": 903.306,
    "SRVC": 596.326,
}

STATE_FIPS_TO_USPS: dict[str, str] = {
    "01": "AL",
    "02": "AK",
    "04": "AZ",
    "05": "AR",
    "06": "CA",
    "08": "CO",
    "09": "CT",
    "10": "DE",
    "11": "DC",
    "12": "FL",
    "13": "GA",
    "15": "HI",
    "16": "ID",
    "17": "IL",
    "18": "IN",
    "19": "IA",
    "20": "KS",
    "21": "KY",
    "22": "LA",
    "23": "ME",
    "24": "MD",
    "25": "MA",
    "26": "MI",
    "27": "MN",
    "28": "MS",
    "29": "MO",
    "30": "MT",
    "31": "NE",
    "32": "NV",
    "33": "NH",
    "34": "NJ",
    "35": "NM",
    "36": "NY",
    "37": "NC",
    "38": "ND",
    "39": "OH",
    "40": "OK",
    "41": "OR",
    "42": "PA",
    "44": "RI",
    "45": "SC",
    "46": "SD",
    "47": "TN",
    "48": "TX",
    "49": "UT",
    "50": "VT",
    "51": "VA",
    "53": "WA",
    "54": "WV",
    "55": "WI",
    "56": "WY",
}


def ingest_eia_state_retail_prices(db_path: Path) -> None:
    """Fetch latest EIA retail electricity price by state and apply to counties.

    This is a pragmatic proxy for "wholesale" prices for the hackathon MVP when
    hub-level wholesale series are not available in EIA APIv2.

    Source:
      EIA APIv2 /electricity/retail-sales (price, cents/kWh) by state, sector=ALL.
    """
    from backend.app.core.config import settings

    api_key = (settings.eia_api_key or "").strip() or "DEMO_KEY"
    print("Ingesting EIA state price proxy (retail-sales, sector=ALL)...")

    # Pull the latest period per-state (the API returns a max period available).
    url = "https://api.eia.gov/v2/electricity/retail-sales/data/"
    params = {
        "api_key": api_key,
        "frequency": "monthly",
        "data[0]": "price",
        "facets[sectorid][]": "ALL",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": 5000,
    }
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    payload = resp.json()
    rows = payload.get("response", {}).get("data", [])
    if not rows:
        raise RuntimeError("EIA retail-sales returned no rows for price.")

    # Determine the latest month present and filter to that.
    latest_period = max(str(r.get("period", "")) for r in rows)
    latest = [r for r in rows if str(r.get("period")) == latest_period]

    # Map USPS -> cents/kWh
    price_cents_per_kwh: dict[str, float] = {}
    for r in latest:
        state = str(r.get("stateid") or "").strip()
        if not state:
            continue
        try:
            price_cents_per_kwh[state] = float(r["price"])
        except Exception:
            continue

    if not price_cents_per_kwh:
        raise RuntimeError("Could not parse any state price values from EIA response.")

    # Apply to counties via state FIPS prefix.
    with connect(db_path) as conn:
        snap_row = conn.execute(
            "SELECT snapshot_id FROM feature_snapshots ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        snapshot_id = str(snap_row["snapshot_id"]) if snap_row else None
        if snapshot_id is None:
            raise RuntimeError("No feature snapshots found; seed counties first.")

        counties = conn.execute(
            """
            SELECT spatial_unit_id, fips
            FROM spatial_units
            WHERE unit_type = 'county' AND fips IS NOT NULL
            """
        ).fetchall()

        updated = 0
        hub_inserts: list[tuple[str, str, float]] = []
        for c in counties:
            fips = str(c["fips"])
            state_fips = fips[:2]
            usps = STATE_FIPS_TO_USPS.get(state_fips)
            if usps is None:
                continue
            cents = price_cents_per_kwh.get(usps)
            if cents is None:
                continue
            usd_per_mwh = float(cents) * 10.0  # cents/kWh → $/MWh
            price_hub_id = f"EIA_STATE_{usps}"
            conn.execute(
                """
                UPDATE spatial_unit_features
                   SET price_usd_per_mwh_mean = ?,
                       price_hub_id = ?
                 WHERE snapshot_id = ?
                   AND spatial_unit_id = ?
                """,
                (usd_per_mwh, price_hub_id, snapshot_id, str(c["spatial_unit_id"])),
            )
            updated += 1
            hub_inserts.append((price_hub_id, f"EIA state proxy {usps}", None))  # type: ignore[arg-type]

        # Record the state proxy prices into hub_prices_hourly at the month start.
        ts_utc = f"{latest_period}-01T00"
        for usps, cents in price_cents_per_kwh.items():
            price_hub_id = f"EIA_STATE_{usps}"
            conn.execute(
                """
                INSERT OR IGNORE INTO price_hubs(price_hub_id, name, iso, lat, lon)
                VALUES(?, ?, ?, NULL, NULL)
                """,
                (price_hub_id, f"EIA state proxy {usps}", "EIA"),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO hub_prices_hourly(price_hub_id, ts_utc, price_usd_per_mwh)
                VALUES(?, ?, ?)
                """,
                (price_hub_id, ts_utc, float(cents) * 10.0),
            )

    ingest_mark(
        db_path,
        source="eia_prices",
        status="completed",
        details={
            "method": "state_price_proxy_from_retail_sales_sector_ALL",
            "api": "https://api.eia.gov/v2/electricity/retail-sales/data/",
            "period": latest_period,
            "sectorid": "ALL",
            "snapshot_id": snapshot_id,
            "updated_counties": updated,
            "units": {"input": "cents/kWh", "stored": "$/MWh (cents/kWh * 10)"},
        },
    )
    print(f"Updated price proxy for {updated} counties (snapshot {snapshot_id}).")


def ingest_egrid_subregion_carbon(db_path: Path) -> None:
    """Map county centroids to eGRID subregions and update carbon intensity.

    Uses the EPA eGRID 2023 subregion polygons and the published subregion CO2e
    emission rates (lb/MWh) to derive mean grid carbon intensity for counties.

    Carbon conversion:
      lb/MWh → g/kWh = lb/MWh * 453.59237 / 1000 = lb/MWh * 0.45359237
    """
    print("Ingesting eGRID subregion carbon intensity (county centroid → subregion)...")
    started_at = _now()
    snapshot_id: str | None = None
    updated = 0

    # Load centroids from DB
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT snapshot_id FROM feature_snapshots ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        snapshot_id = str(row["snapshot_id"]) if row else None
        if snapshot_id is None:
            raise RuntimeError("No feature snapshots found; seed counties first.")

        counties = conn.execute(
            """
            SELECT spatial_unit_id, fips, lat, lon
            FROM spatial_units
            WHERE unit_type = 'county'
            """
        ).fetchall()

    if not counties:
        raise RuntimeError("No counties found in spatial_units; seed counties first.")

    try:
        import geopandas as gpd
        import pandas as pd
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("geopandas and pandas are required for eGRID ingestion") from exc

    county_df = pd.DataFrame(
        [
            {
                "spatial_unit_id": r["spatial_unit_id"],
                "fips": r["fips"],
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
            }
            for r in counties
        ]
    )
    county_gdf = gpd.GeoDataFrame(
        county_df,
        geometry=[Point(lon, lat) for lon, lat in zip(county_df["lon"], county_df["lat"])],
        crs="EPSG:4326",
    )

    # Download shapefile zip to disk (fiona/geopandas read_file expects a path)
    raw_dir = Path("data/raw")
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / "egrid2023_subregions.zip"
    if not zip_path.exists():
        resp = requests.get(EGRID2023_SUBREGION_SHAPEFILE_URL, timeout=120)
        resp.raise_for_status()
        zip_path.write_bytes(resp.content)

    subregions = gpd.read_file(zip_path)
    if subregions.empty:
        raise RuntimeError("Loaded eGRID subregion shapefile but it contained no rows.")

    # Find the column that contains subregion IDs (e.g., ERCT, CAMX, ...)
    keys = set(EGRID2023_CO2E_LB_PER_MWH.keys())
    subregion_col: str | None = None
    best_hits = 0
    for col in subregions.columns:
        if col == "geometry":
            continue
        values = set(str(v).strip() for v in subregions[col].dropna().unique().tolist())
        hits = len(values.intersection(keys))
        if hits > best_hits:
            best_hits = hits
            subregion_col = col
    if subregion_col is None or best_hits == 0:
        raise RuntimeError(
            f"Could not find eGRID subregion ID column in shapefile. Columns: {list(subregions.columns)}"
        )

    subregions = subregions.loc[:, [subregion_col, "geometry"]].copy()
    subregions.rename(columns={subregion_col: "egrid_subregion"}, inplace=True)

    joined = gpd.sjoin(county_gdf, subregions, how="left", predicate="within")
    if "egrid_subregion" not in joined.columns:
        raise RuntimeError("Spatial join did not produce egrid_subregion assignments.")

    # Compute g/kWh from CO2e lb/MWh
    def _lb_per_mwh_to_g_per_kwh(lb_per_mwh: float) -> float:
        return float(lb_per_mwh) * 0.45359237

    joined["carbon_g_per_kwh_mean"] = joined["egrid_subregion"].map(
        lambda x: _lb_per_mwh_to_g_per_kwh(EGRID2023_CO2E_LB_PER_MWH[str(x).strip()])
        if str(x).strip() in EGRID2023_CO2E_LB_PER_MWH
        else None
    )

    updates = joined.loc[
        joined["carbon_g_per_kwh_mean"].notna(),
        ["spatial_unit_id", "egrid_subregion", "carbon_g_per_kwh_mean"],
    ].to_dict("records")

    with connect(db_path) as conn:
        for u in updates:
            conn.execute(
                """
                UPDATE spatial_unit_features
                   SET carbon_g_per_kwh_mean = ?,
                       grid_zone_id = ?
                 WHERE snapshot_id = ?
                   AND spatial_unit_id = ?
                """,
                (
                    float(u["carbon_g_per_kwh_mean"]),
                    str(u["egrid_subregion"]),
                    snapshot_id,
                    str(u["spatial_unit_id"]),
                ),
            )
            updated += 1

    ingest_mark(
        db_path,
        source="epa_egrid",
        status="completed",
        details={
            "method": "county_centroid_spatial_join_to_egrid2023_subregions",
            "subregion_shapefile_url": EGRID2023_SUBREGION_SHAPEFILE_URL,
            "subregion_rates_source_url": EGRID2023_SUBREGION_RATES_SOURCE_URL,
            "snapshot_id": snapshot_id,
            "updated_counties": updated,
            "subregion_column_detected": subregion_col,
            "unit_conversion": "lb/MWh_to_g/kWh (multiply by 0.45359237)",
        },
    )
    print(f"Updated carbon intensity for {updated} counties (snapshot {snapshot_id}).")


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
            # Gazetteer headers occasionally contain trailing spaces (notably INTPTLONG).
            # Normalize row keys once to ensure stable access.
            normalized = {str(k).strip(): v for k, v in r.items()}
            # Columns per Census gazetteer: GEOID, NAME, INTPTLAT, INTPTLONG, etc.
            geoid = (normalized.get("GEOID") or "").strip()
            name = (normalized.get("NAME") or "").strip()
            lat = float((normalized.get("INTPTLAT") or "0").strip())
            lon = float((normalized.get("INTPTLONG") or "0").strip())
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


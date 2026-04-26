"""Initialize the SQLite database for the Green Grid hackathon project."""

from __future__ import annotations

import os
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path


DB_FILENAME = "green_grid.db"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("GREEN_GRID_DB_PATH", BASE_DIR / "data" / "app" / DB_FILENAME))
LEGACY_DB_PATH = BASE_DIR / DB_FILENAME

ALLOWED_METRIC_TYPES = (
    "carbon_intensity",
    "renewable_percentage",
    "carbon_free_percentage",
    "day_ahead_price",
    "total_load",
    "net_load",
)


def connect_db() -> sqlite3.Connection:
    """Create a SQLite connection with production-friendly defaults."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists() and LEGACY_DB_PATH.exists():
        LEGACY_DB_PATH.replace(DB_PATH)

    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute("PRAGMA journal_mode = WAL;")
    connection.execute("PRAGMA busy_timeout = 5000;")
    return connection


def create_tables(connection: sqlite3.Connection) -> None:
    """Create database tables if they do not already exist."""
    metric_type_check = ", ".join(f"'{metric_type}'" for metric_type in ALLOWED_METRIC_TYPES)

    schema = f"""
    CREATE TABLE IF NOT EXISTS zones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zone_code TEXT UNIQUE NOT NULL,
        zone_name TEXT,
        country TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zone_id INTEGER NOT NULL,
        metric_type TEXT NOT NULL CHECK (metric_type IN ({metric_type_check})),
        value REAL NOT NULL,
        unit TEXT,
        timestamp DATETIME NOT NULL,
        is_forecast INTEGER NOT NULL DEFAULT 0 CHECK (is_forecast IN (0, 1)),
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE ON UPDATE CASCADE,
        UNIQUE (zone_id, metric_type, timestamp, is_forecast)
    );

    CREATE TABLE IF NOT EXISTS electricity_mix (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zone_id INTEGER NOT NULL,
        source_type TEXT NOT NULL,
        power_mw REAL CHECK (power_mw IS NULL OR power_mw >= 0),
        percentage REAL CHECK (percentage IS NULL OR (percentage >= 0 AND percentage <= 100)),
        timestamp DATETIME NOT NULL,
        is_forecast INTEGER NOT NULL DEFAULT 0 CHECK (is_forecast IN (0, 1)),
        FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE ON UPDATE CASCADE,
        UNIQUE (zone_id, source_type, timestamp, is_forecast)
    );

    CREATE TABLE IF NOT EXISTS recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zone_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        action_type TEXT,
        estimated_co2_saved REAL CHECK (estimated_co2_saved IS NULL OR estimated_co2_saved >= 0),
        recommended_time DATETIME,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE ON UPDATE CASCADE
    );

    CREATE TABLE IF NOT EXISTS user_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recommendation_id INTEGER,
        action_taken TEXT,
        completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
        completed_at DATETIME,
        FOREIGN KEY (recommendation_id) REFERENCES recommendations(id) ON DELETE CASCADE ON UPDATE CASCADE
    );

    CREATE TABLE IF NOT EXISTS api_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        endpoint TEXT,
        zone_code TEXT,
        raw_json TEXT,
        fetched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """

    with connection:
        connection.executescript(schema)


def create_indexes(connection: sqlite3.Connection) -> None:
    """Create indexes used by common lookup patterns."""
    index_sql = """
    CREATE INDEX IF NOT EXISTS idx_metrics_zone_metric_timestamp
        ON metrics(zone_id, metric_type, timestamp);

    CREATE INDEX IF NOT EXISTS idx_electricity_mix_zone_timestamp
        ON electricity_mix(zone_id, timestamp);

    CREATE INDEX IF NOT EXISTS idx_recommendations_zone_id
        ON recommendations(zone_id);
    """

    with connection:
        connection.executescript(index_sql)


def seed_sample_data(connection: sqlite3.Connection) -> None:
    """Insert sample records for local development and demos."""

    def fmt(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    now_utc = datetime.now(timezone.utc).replace(microsecond=0)

    with connection:
        connection.execute(
            """
            INSERT INTO zones (zone_code, zone_name, country)
            VALUES (?, ?, ?)
            ON CONFLICT(zone_code) DO UPDATE SET
                zone_name = excluded.zone_name,
                country = excluded.country
            """,
            ("US-AZ", "Arizona", "United States"),
        )
        connection.execute(
            """
            INSERT INTO zones (zone_code, zone_name, country)
            VALUES (?, ?, ?)
            ON CONFLICT(zone_code) DO UPDATE SET
                zone_name = excluded.zone_name,
                country = excluded.country
            """,
            ("US-CA", "California", "United States"),
        )

        zone_rows = connection.execute(
            "SELECT id, zone_code FROM zones WHERE zone_code IN (?, ?)",
            ("US-AZ", "US-CA"),
        ).fetchall()
        zone_ids = {row["zone_code"]: row["id"] for row in zone_rows}

        metrics_rows = [
            (
                zone_ids["US-AZ"],
                "carbon_intensity",
                412.6,
                "gCO2eq/kWh",
                fmt(now_utc - timedelta(hours=1)),
                0,
            ),
            (
                zone_ids["US-AZ"],
                "renewable_percentage",
                34.2,
                "%",
                fmt(now_utc - timedelta(hours=1)),
                0,
            ),
            (
                zone_ids["US-AZ"],
                "carbon_intensity",
                355.1,
                "gCO2eq/kWh",
                fmt(now_utc + timedelta(hours=2)),
                1,
            ),
            (
                zone_ids["US-CA"],
                "carbon_intensity",
                198.4,
                "gCO2eq/kWh",
                fmt(now_utc - timedelta(hours=1)),
                0,
            ),
            (
                zone_ids["US-CA"],
                "renewable_percentage",
                52.8,
                "%",
                fmt(now_utc - timedelta(hours=1)),
                0,
            ),
        ]
        connection.executemany(
            """
            INSERT INTO metrics (zone_id, metric_type, value, unit, timestamp, is_forecast)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(zone_id, metric_type, timestamp, is_forecast) DO UPDATE SET
                value = excluded.value,
                unit = excluded.unit
            """,
            metrics_rows,
        )

        mix_rows = [
            (
                zone_ids["US-AZ"],
                "solar",
                1800.0,
                22.5,
                fmt(now_utc - timedelta(hours=1)),
                0,
            ),
            (
                zone_ids["US-AZ"],
                "natural_gas",
                3600.0,
                45.0,
                fmt(now_utc - timedelta(hours=1)),
                0,
            ),
            (
                zone_ids["US-CA"],
                "solar",
                6400.0,
                31.2,
                fmt(now_utc - timedelta(hours=1)),
                0,
            ),
            (
                zone_ids["US-CA"],
                "wind",
                2900.0,
                14.1,
                fmt(now_utc - timedelta(hours=1)),
                0,
            ),
        ]
        connection.executemany(
            """
            INSERT INTO electricity_mix (
                zone_id,
                source_type,
                power_mw,
                percentage,
                timestamp,
                is_forecast
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(zone_id, source_type, timestamp, is_forecast) DO UPDATE SET
                power_mw = excluded.power_mw,
                percentage = excluded.percentage
            """,
            mix_rows,
        )

        recommendation_message = (
            "Run high-energy appliances after 8 PM local time when forecasted carbon intensity is lower."
        )
        recommended_time = fmt(now_utc + timedelta(hours=2))
        existing_recommendations = connection.execute(
            """
            SELECT id
            FROM recommendations
            WHERE zone_id = ? AND message = ? AND action_type = ?
            ORDER BY id
            """,
            (zone_ids["US-AZ"], recommendation_message, "shift_usage_time"),
        ).fetchall()

        if existing_recommendations:
            primary_recommendation_id = existing_recommendations[0]["id"]
            connection.execute(
                """
                UPDATE recommendations
                SET estimated_co2_saved = ?, recommended_time = ?
                WHERE id = ?
                """,
                (1.8, recommended_time, primary_recommendation_id),
            )

            duplicate_ids = [row["id"] for row in existing_recommendations[1:]]
            if duplicate_ids:
                placeholders = ", ".join("?" for _ in duplicate_ids)
                connection.execute(
                    f"DELETE FROM recommendations WHERE id IN ({placeholders})",
                    duplicate_ids,
                )
        else:
            connection.execute(
                """
                INSERT INTO recommendations (
                    zone_id,
                    message,
                    action_type,
                    estimated_co2_saved,
                    recommended_time
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    zone_ids["US-AZ"],
                    recommendation_message,
                    "shift_usage_time",
                    1.8,
                    recommended_time,
                ),
            )


def main() -> None:
    """Create the database schema and insert sample data."""
    try:
        with closing(connect_db()) as connection:
            create_tables(connection)
            create_indexes(connection)
            seed_sample_data(connection)
        print("Database initialized successfully.")
    except sqlite3.Error as exc:
        print(f"Database initialization failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

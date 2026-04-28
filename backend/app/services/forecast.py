from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backend.app.services.weather import fetch_open_meteo_hourly

from backend.MLModel.forecast_future_usage import (  # type: ignore[import-not-found]
    forecast_from_files,
    forecast_from_files_with_weather_adjustment,
)
from backend.MLModel.weather_adjustment import (  # type: ignore[import-not-found]
    WeatherAdjustmentConfig,
    weather_rows_from_open_meteo_frames,
)


@dataclass(frozen=True)
class LatLon:
    lat: float
    lon: float


def _mlmodel_dir() -> Path:
    # backend/app/services/forecast.py -> backend/app/services -> backend/app -> backend -> MLModel
    return Path(__file__).resolve().parents[2] / "MLModel"


def _default_model_path() -> Path:
    return _mlmodel_dir() / "electricity_usage_model.pkl"


def _default_history_path() -> Path:
    return _mlmodel_dir() / "state_energy_timeseries.csv"


def forecast_usage_and_cost(
    *,
    start: str,
    end: str | None = None,
    hours: int | None = None,
    states: list[str] | None = None,
    assumption_window_hours: int = 24 * 30,
    weather_adjustment: bool = False,
    state_locations: dict[str, LatLon] | None = None,
    weather_config: WeatherAdjustmentConfig | None = None,
) -> pd.DataFrame:
    """
    Main-backend friendly forecast entry point.

    - Baseline: runs the bundled ridge model forecast.
    - Weather-adjusted: fetches Open‑Meteo hourly weather and applies a
      bounded multiplier to baseline predictions.
    """
    model_path = _default_model_path()
    history_path = _default_history_path()

    if not weather_adjustment:
        return forecast_from_files(
            start=start,
            end=end,
            hours=hours,
            states=states,
            model_path=model_path,
            history_path=history_path,
            assumption_window_hours=assumption_window_hours,
        )

    if not state_locations:
        raise ValueError("state_locations is required when weather_adjustment is enabled.")

    # Build weather rows for requested states.
    states_to_fetch = states or sorted(state_locations.keys())
    weather_frames: list[pd.DataFrame] = []
    for state_code in states_to_fetch:
        loc = state_locations.get(state_code)
        if loc is None:
            continue

        # We fetch slightly wider than the requested range (hour-flooring handled in client).
        weather = fetch_open_meteo_hourly(
            lat=loc.lat,
            lon=loc.lon,
            start=start,
            end=(end if end is not None else _end_from_start_hours(start, hours)),
        )
        rows = weather_rows_from_open_meteo_frames(state_code=state_code, frame=weather.frame)
        rows["weather_source_status"] = weather.source_status
        rows["weather_fetched_at_utc"] = weather.fetched_at_utc
        weather_frames.append(rows)

    weather_rows = pd.concat(weather_frames, ignore_index=True) if weather_frames else pd.DataFrame()
    return forecast_from_files_with_weather_adjustment(
        start=start,
        end=end,
        hours=hours,
        states=states,
        model_path=model_path,
        history_path=history_path,
        assumption_window_hours=assumption_window_hours,
        weather_rows=weather_rows,
        weather_config=weather_config,
    )


def _end_from_start_hours(start: str, hours: int | None) -> str | None:
    if hours is None:
        return None
    start_ts = pd.Timestamp(start)
    if start_ts.tzinfo is None:
        start_ts = start_ts.tz_localize(timezone.utc)
    else:
        start_ts = start_ts.tz_convert(timezone.utc)
    end_ts = start_ts + pd.Timedelta(hours=int(hours))
    return end_ts.isoformat().replace("+00:00", "Z")


def to_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    cleaned = frame.where(frame.notna(), None)
    return cleaned.to_dict(orient="records")


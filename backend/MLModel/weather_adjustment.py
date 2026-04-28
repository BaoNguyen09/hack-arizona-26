from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class WeatherAdjustmentConfig:
    """
    A lightweight post-model adjustment that turns weather into a bounded
    multiplier on predicted electricity usage.

    This is intentionally simple so we can ship weather impacts without needing
    to retrain the bundled ridge model (which doesn't include weather features).
    """

    # Degree-hour weights
    cooling_degree_hour_weight: float = 0.007  # +0.7% per CDH above baseline
    heating_degree_hour_weight: float = 0.005  # +0.5% per HDH above baseline

    # Wind + cloud adjustments (used primarily for explanatory visuals)
    cloud_cover_weight: float = 0.0015  # per 1.0 (fractional) cloud delta
    wind_speed_weight: float = 0.01  # per m/s wind delta

    # Bounds to prevent unrealistic swings
    multiplier_min: float = 0.85
    multiplier_max: float = 1.15

    # Baseline temperature for degree-hours
    degree_hour_base_temp_c: float = 18.0


def apply_weather_adjustment(
    *,
    forecast_rows: pd.DataFrame,
    weather_rows: pd.DataFrame,
    config: WeatherAdjustmentConfig | None = None,
) -> pd.DataFrame:
    """
    Join weather rows to forecast rows and compute weather-adjusted usage/cost.

    Required forecast columns:
    - state_code, timestamp, predicted_total_kwh_usage, estimated_total_cost

    Required weather columns:
    - state_code, timestamp
    - and any of: temp_c, cooling_degree_hours, heating_degree_hours,
      cloud_cover_pct, wind_speed_m_s
    """
    cfg = config or WeatherAdjustmentConfig()

    forecast = forecast_rows.copy()
    weather = weather_rows.copy()

    forecast["timestamp"] = pd.to_datetime(forecast["timestamp"], errors="coerce", utc=True)
    weather["timestamp"] = pd.to_datetime(weather["timestamp"], errors="coerce", utc=True)

    merged = forecast.merge(
        weather,
        on=["state_code", "timestamp"],
        how="left",
        suffixes=("", "_weather"),
    )

    if "cooling_degree_hours" not in merged.columns or "heating_degree_hours" not in merged.columns:
        temp = pd.to_numeric(merged.get("temp_c"), errors="coerce")
        if temp is not None:
            merged["cooling_degree_hours"] = np.maximum(temp - cfg.degree_hour_base_temp_c, 0.0)
            merged["heating_degree_hours"] = np.maximum(cfg.degree_hour_base_temp_c - temp, 0.0)
        else:
            merged["cooling_degree_hours"] = np.nan
            merged["heating_degree_hours"] = np.nan

    # Per-state baselines (recent mean over returned range) so we model *changes* not absolute climate.
    group = merged.groupby("state_code", dropna=False, sort=False)
    cdh0 = group["cooling_degree_hours"].transform("mean")
    hdh0 = group["heating_degree_hours"].transform("mean")
    cloud0 = group["cloud_cover_pct"].transform("mean") if "cloud_cover_pct" in merged.columns else np.nan
    wind0 = group["wind_speed_m_s"].transform("mean") if "wind_speed_m_s" in merged.columns else np.nan

    cdh = pd.to_numeric(merged["cooling_degree_hours"], errors="coerce")
    hdh = pd.to_numeric(merged["heating_degree_hours"], errors="coerce")

    cloud = pd.to_numeric(merged.get("cloud_cover_pct"), errors="coerce")
    wind = pd.to_numeric(merged.get("wind_speed_m_s"), errors="coerce")

    # Cloud comes in as percent; convert to fraction delta if present.
    cloud_delta = (cloud - cloud0) / 100.0 if isinstance(cloud, pd.Series) else 0.0
    wind_delta = (wind - wind0) if isinstance(wind, pd.Series) else 0.0

    multiplier = (
        1.0
        + cfg.cooling_degree_hour_weight * (cdh - cdh0)
        + cfg.heating_degree_hour_weight * (hdh - hdh0)
    )

    if isinstance(cloud_delta, pd.Series):
        multiplier = multiplier + cfg.cloud_cover_weight * cloud_delta
    if isinstance(wind_delta, pd.Series):
        multiplier = multiplier + cfg.wind_speed_weight * wind_delta

    multiplier = np.clip(multiplier.to_numpy(dtype=float), cfg.multiplier_min, cfg.multiplier_max)
    merged["weather_multiplier"] = multiplier

    base_kwh = pd.to_numeric(merged["predicted_total_kwh_usage"], errors="coerce").fillna(0.0)
    merged["weather_adjusted_total_kwh_usage"] = (base_kwh * merged["weather_multiplier"]).astype(float)

    cents = pd.to_numeric(merged.get("avg_electricity_cost_cents_per_kwh"), errors="coerce")
    if cents is not None and "avg_electricity_cost_cents_per_kwh" in merged.columns:
        merged["weather_adjusted_total_cost"] = merged["weather_adjusted_total_kwh_usage"] * cents / 100.0
    else:
        # Fall back to scaling whatever estimated_total_cost exists.
        base_cost = pd.to_numeric(merged.get("estimated_total_cost"), errors="coerce")
        merged["weather_adjusted_total_cost"] = base_cost * merged["weather_multiplier"]

    merged["delta_kwh_usage"] = merged["weather_adjusted_total_kwh_usage"] - base_kwh
    merged["delta_total_cost"] = merged["weather_adjusted_total_cost"] - pd.to_numeric(
        merged.get("estimated_total_cost"), errors="coerce"
    )

    # Serialize timestamps back to the API shape (Z suffix) where possible.
    merged["timestamp"] = merged["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return merged


def weather_rows_from_open_meteo_frames(
    *,
    state_code: str,
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """
    Convert an Open‑Meteo hourly frame (timestamp + canonical columns) into the
    joinable format for apply_weather_adjustment().
    """
    out = frame.copy()
    if "timestamp" not in out.columns:
        raise ValueError("Open-Meteo frame must include timestamp")
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce", utc=True).dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    out.insert(0, "state_code", state_code)
    return out


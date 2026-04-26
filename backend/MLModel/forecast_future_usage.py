from __future__ import annotations

import pickle
from io import StringIO
from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from electricity_cost_model import (
    BASE_NUMERIC_FEATURES,
    CALENDAR_FEATURES,
    CATEGORICAL_FEATURES,
    LAG_FEATURES,
    MIX_COLUMNS,
    ElectricityUsageModel,
    _month_to_datetime,
)


DEFAULT_MODEL_PATH = "electricity_usage_model.pkl"
DEFAULT_HISTORY_PATH = "state_energy_timeseries.csv"
TARGET = "total_kw_usage"

EMBEDDED_STATE_PROFILE_CSV = """state_code,state_name,avg_electricity_cost_cents_per_kwh,pct_solar,pct_wind,pct_hydro,pct_fossil,data_period
AL,Alabama,12.7,0.99,0.0,5.34,57.92,2026-02
AK,Alaska,23.31,0.15,1.94,35.9,61.46,2026-02
AZ,Arizona,12.29,13.93,2.49,5.87,44.47,2026-02
AR,Arkansas,10.0,6.83,0.86,4.06,62.45,2026-02
CA,California,26.55,26.74,8.98,14.37,31.19,2026-02
CO,Colorado,13.44,11.09,34.46,4.7,49.47,2026-02
CT,Connecticut,27.61,1.17,0.03,0.64,57.62,2026-02
DE,Delaware,15.23,2.7,0.04,0.0,96.68,2026-02
FL,Florida,14.31,10.6,0.0,0.06,76.49,2026-02
GA,Georgia,12.09,6.88,0.0,1.95,56.26,2026-02
HI,Hawaii,37.78,8.97,6.14,1.61,75.85,2026-02
ID,Idaho,10.14,4.4,14.22,54.25,24.56,2026-02
IL,Illinois,13.88,3.75,15.67,0.05,30.71,2026-02
IN,Indiana,13.21,5.9,9.56,0.25,83.9,2026-02
IA,Iowa,9.08,1.39,60.61,1.72,36.06,2026-02
KS,Kansas,11.9,0.93,52.37,0.03,29.03,2026-02
KY,Kentucky,11.25,2.3,0.0,5.12,92.02,2026-02
LA,Louisiana,9.77,2.36,0.0,0.75,76.18,2026-02
ME,Maine,26.67,7.68,20.92,14.05,44.47,2026-02
MD,Maryland,19.06,3.8,2.49,2.82,59.1,2026-02
MA,Massachusetts,27.06,9.57,0.68,3.34,81.5,2026-02
MI,Michigan,15.14,2.3,8.23,1.42,64.01,2026-02
MN,Minnesota,12.52,4.32,27.2,2.02,42.83,2026-02
MS,Mississippi,12.32,4.19,1.03,0.0,86.39,2026-02
MO,Missouri,10.75,3.76,11.74,1.18,68.06,2026-02
MT,Montana,11.33,0.71,26.12,42.88,29.22,2026-02
NE,Nebraska,9.49,0.57,29.78,4.13,48.89,2026-02
NV,Nevada,10.09,28.08,0.88,1.64,58.91,2026-02
NH,New Hampshire,24.25,0.03,2.62,5.97,31.81,2026-02
NJ,New Jersey,19.49,2.59,0.03,0.0,52.44,2026-02
NM,New Mexico,8.97,16.02,41.66,0.65,41.83,2026-02
NY,New York,24.88,3.29,4.62,16.94,53.26,2026-02
NC,North Carolina,12.55,6.97,0.79,2.72,57.66,2026-02
ND,North Dakota,8.87,0.0,36.4,6.3,57.22,2026-02
OH,Ohio,14.52,4.51,1.74,0.22,82.33,2026-02
OK,Oklahoma,9.36,1.5,52.95,1.81,43.47,2026-02
OR,Oregon,11.39,2.13,9.14,54.52,32.76,2026-02
PA,Pennsylvania,16.52,0.6,1.44,0.85,66.94,2026-02
RI,Rhode Island,26.23,6.45,2.07,0.09,88.97,2026-02
SC,South Carolina,13.1,2.86,0.0,2.03,40.27,2026-02
SD,South Dakota,11.54,1.44,55.18,27.63,15.68,2026-02
TN,Tennessee,11.73,1.63,0.0,9.11,40.46,2026-02
TX,Texas,10.39,11.29,26.35,0.19,54.0,2026-02
UT,Utah,10.65,13.17,1.84,2.77,80.49,2026-02
VT,Vermont,20.42,7.07,16.13,50.75,1.02,2026-02
VA,Virginia,13.92,5.97,0.06,0.83,63.88,2026-02
WA,Washington,12.19,0.26,6.85,76.77,8.58,2026-02
WV,West Virginia,11.64,0.43,3.58,2.09,93.9,2026-02
WI,Wisconsin,13.95,5.28,3.25,4.49,69.16,2026-02
WY,Wyoming,10.12,0.88,39.14,3.38,56.36,2026-02
"""


@dataclass(frozen=True)
class ForecastRequest:
    start: str
    end: str | None = None
    hours: int | None = None
    states: tuple[str, ...] | None = None
    assumption_window_hours: int = 24 * 30
    feature_overrides: dict[str, dict[str, float]] | None = None
    profile_features: dict[str, dict[str, float]] | None = None


def load_usage_model(path: str | Path = DEFAULT_MODEL_PATH) -> ElectricityUsageModel:
    with open(path, "rb") as handle:
        return pickle.load(handle)


def load_history(path: str | Path = DEFAULT_HISTORY_PATH) -> pd.DataFrame:
    history = pd.read_csv(path)
    history["date"] = _month_to_datetime(history["month"])
    history = history.dropna(subset=["date", TARGET])
    return history.sort_values(["state_code", "date"]).reset_index(drop=True)


def load_state_energy_profile() -> dict[str, dict[str, float]]:
    frame = pd.read_csv(StringIO(EMBEDDED_STATE_PROFILE_CSV))
    rename_map = {
        "pct_solar": "pct_solar_state",
        "pct_wind": "pct_wind_state",
        "pct_hydro": "pct_hydro_state",
        "pct_fossil": "pct_fossil_state",
    }
    frame = frame.rename(columns=rename_map)

    required = ["state_code", *BASE_NUMERIC_FEATURES[:5]]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"State energy profile is missing columns: {missing}")

    profiles: dict[str, dict[str, float]] = {}
    for _, row in frame.iterrows():
        state_code = str(row["state_code"])
        profiles[state_code] = {
            column: safe_float(row.get(column))
            for column in BASE_NUMERIC_FEATURES
            if column in frame.columns
        }
    return profiles


def forecast_usage(
    fitted_model: ElectricityUsageModel,
    history: pd.DataFrame,
    request: ForecastRequest,
) -> pd.DataFrame:
    """
    Recursively forecast hourly state usage and split usage/cost by source.

    Future non-usage features are estimated from each state's recent historical
    averages. Predicted usage is appended back into history so later future
    hours can use earlier forecast hours as lag inputs.
    """
    working_history = history.copy()
    working_history["date"] = _month_to_datetime(working_history["month"])
    working_history = working_history.dropna(subset=["date", TARGET])
    working_history = working_history.sort_values(["state_code", "date"]).reset_index(drop=True)

    future_timestamps = build_future_timestamps(request)
    state_profiles = build_state_profiles(
        working_history,
        request.states,
        request.assumption_window_hours,
        request.feature_overrides,
        request.profile_features,
    )
    if not state_profiles:
        raise ValueError("No matching states found in history.")

    output_rows: list[dict[str, Any]] = []
    for timestamp in future_timestamps:
        rows_for_timestamp: list[dict[str, Any]] = []
        for profile in state_profiles.values():
            row = build_future_feature_row(working_history, profile, timestamp)
            rows_for_timestamp.append(row)

        feature_frame = pd.DataFrame(rows_for_timestamp)
        predictions = fitted_model.model.predict(feature_frame[fitted_model.feature_columns])
        feature_frame["predicted_total_kwh_usage"] = np.maximum(predictions, 0)

        for _, row in feature_frame.iterrows():
            output_row = build_output_row(row)
            output_rows.append(output_row)
            working_history = append_prediction_to_history(working_history, row)

    return pd.DataFrame(output_rows)


def build_future_timestamps(request: ForecastRequest) -> pd.DatetimeIndex:
    start = pd.Timestamp(request.start)
    if start.tzinfo is None:
        start = start.tz_localize(timezone.utc)
    else:
        start = start.tz_convert(timezone.utc)

    if request.hours is not None:
        if request.hours <= 0:
            raise ValueError("hours must be greater than 0.")
        return pd.date_range(start=start, periods=request.hours, freq="h")

    if request.end is None:
        raise ValueError("Provide either hours or end.")

    end = pd.Timestamp(request.end)
    if end.tzinfo is None:
        end = end.tz_localize(timezone.utc)
    else:
        end = end.tz_convert(timezone.utc)
    if end <= start:
        raise ValueError("end must be after start.")
    return pd.date_range(start=start, end=end, freq="h", inclusive="left")


def build_state_profiles(
    history: pd.DataFrame,
    states: Iterable[str] | None,
    assumption_window_hours: int,
    feature_overrides: dict[str, dict[str, float]] | None = None,
    profile_features: dict[str, dict[str, float]] | None = None,
) -> dict[str, dict[str, Any]]:
    selected = history
    if states:
        selected = selected[selected["state_code"].isin(states)]

    profiles: dict[str, dict[str, Any]] = {}
    for state_code, group in selected.groupby("state_code", sort=True):
        group = group.sort_values("date")
        recent_cutoff = group["date"].max() - pd.Timedelta(hours=assumption_window_hours)
        recent = group[group["date"] >= recent_cutoff]
        if recent.empty:
            recent = group

        latest = group.iloc[-1]
        profile: dict[str, Any] = {
            "state_code": latest["state_code"],
            "state_name": latest["state_name"],
            "electricity_maps_zone_id": latest["electricity_maps_zone_id"],
        }
        for column in BASE_NUMERIC_FEATURES:
            profile[column] = pd.to_numeric(recent[column], errors="coerce").mean()
        profile.update((profile_features or {}).get("__default__", {}))
        profile.update((profile_features or {}).get(state_code, {}))
        profile.update((feature_overrides or {}).get("__default__", {}))
        profile.update((feature_overrides or {}).get(state_code, {}))
        profiles[state_code] = profile
    return profiles


def build_future_feature_row(
    history: pd.DataFrame,
    profile: dict[str, Any],
    timestamp: pd.Timestamp,
) -> dict[str, Any]:
    state_history = history[history["state_code"] == profile["state_code"]].sort_values("date")
    usage = pd.to_numeric(state_history[TARGET], errors="coerce").dropna()

    row = dict(profile)
    row["month"] = timestamp.isoformat().replace("+00:00", "Z")
    row["date"] = timestamp
    row.update(build_lag_features(usage))
    row.update(build_calendar_features(timestamp))
    return row


def build_lag_features(usage: pd.Series) -> dict[str, float]:
    features: dict[str, float] = {}
    for lag in (1, 7, 14, 30):
        features[f"usage_lag_{lag}"] = float(usage.iloc[-lag]) if len(usage) >= lag else np.nan

    features["usage_roll_7_mean"] = float(usage.tail(7).mean()) if len(usage) >= 2 else np.nan
    features["usage_roll_14_mean"] = float(usage.tail(14).mean()) if len(usage) >= 3 else np.nan
    features["usage_roll_30_mean"] = float(usage.tail(30).mean()) if len(usage) >= 5 else np.nan
    features["usage_roll_30_std"] = float(usage.tail(30).std()) if len(usage) >= 5 else np.nan
    return features


def build_calendar_features(timestamp: pd.Timestamp) -> dict[str, float]:
    month_num = timestamp.month
    day_of_week = timestamp.dayofweek
    hour = timestamp.hour
    return {
        "month_num": month_num,
        "month_sin": np.sin(2 * np.pi * month_num / 12),
        "month_cos": np.cos(2 * np.pi * month_num / 12),
        "day_of_week": day_of_week,
        "day_of_week_sin": np.sin(2 * np.pi * day_of_week / 7),
        "day_of_week_cos": np.cos(2 * np.pi * day_of_week / 7),
        "hour": hour,
        "hour_sin": np.sin(2 * np.pi * hour / 24),
        "hour_cos": np.cos(2 * np.pi * hour / 24),
    }


def build_output_row(row: pd.Series) -> dict[str, Any]:
    predicted_kwh = float(row["predicted_total_kwh_usage"])
    cents_per_kwh = safe_float(row.get("avg_electricity_cost_cents_per_kwh"))
    total_cost = predicted_kwh * cents_per_kwh / 100 if cents_per_kwh is not None else None

    output: dict[str, Any] = {
        "state_code": row["state_code"],
        "state_name": row["state_name"],
        "electricity_maps_zone_id": row["electricity_maps_zone_id"],
        "timestamp": row["date"].isoformat().replace("+00:00", "Z"),
        "predicted_total_kwh_usage": predicted_kwh,
        "avg_electricity_cost_cents_per_kwh": cents_per_kwh,
        "estimated_total_cost": total_cost,
    }

    mix_total = sum(safe_float(row.get(column)) or 0 for column in MIX_COLUMNS)
    for column in MIX_COLUMNS:
        source = column.removeprefix("pct_").removesuffix("_state")
        pct = safe_float(row.get(column))
        source_kwh = predicted_kwh * pct / mix_total if pct is not None and mix_total else None
        source_cost = source_kwh * cents_per_kwh / 100 if source_kwh is not None and cents_per_kwh is not None else None
        output[f"pct_{source}"] = pct
        output[f"predicted_{source}_kwh_usage"] = source_kwh
        output[f"estimated_{source}_cost"] = source_cost

    return output


def append_prediction_to_history(history: pd.DataFrame, row: pd.Series) -> pd.DataFrame:
    prediction_row = {
        "state_code": row["state_code"],
        "state_name": row["state_name"],
        "electricity_maps_zone_id": row["electricity_maps_zone_id"],
        "month": row["month"],
        "date": row["date"],
        TARGET: row["predicted_total_kwh_usage"],
    }
    for column in BASE_NUMERIC_FEATURES:
        prediction_row[column] = row.get(column)
    return pd.concat([history, pd.DataFrame([prediction_row])], ignore_index=True)


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(number) else number


def forecast_from_files(
    start: str,
    end: str | None = None,
    hours: int | None = None,
    states: Iterable[str] | None = None,
    model_path: str | Path = DEFAULT_MODEL_PATH,
    history_path: str | Path = DEFAULT_HISTORY_PATH,
    assumption_window_hours: int = 24 * 30,
    feature_overrides: dict[str, dict[str, float]] | None = None,
) -> pd.DataFrame:
    fitted_model = load_usage_model(model_path)
    history = load_history(history_path)
    profile_features = load_state_energy_profile()
    request = ForecastRequest(
        start=start,
        end=end,
        hours=hours,
        states=tuple(states) if states else None,
        assumption_window_hours=assumption_window_hours,
        feature_overrides=feature_overrides,
        profile_features=profile_features,
    )
    return forecast_usage(fitted_model, history, request)

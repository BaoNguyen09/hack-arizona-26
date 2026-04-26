from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


TARGET = "total_kw_usage"

CATEGORICAL_FEATURES = [
    "state_code",
    "state_name",
    "electricity_maps_zone_id",
]

MIX_COLUMNS = [
    "pct_solar_state",
    "pct_wind_state",
    "pct_hydro_state",
    "pct_fossil_state",
]

BASE_NUMERIC_FEATURES = [
    "avg_electricity_cost_cents_per_kwh",
    "pct_solar_state",
    "pct_wind_state",
    "pct_hydro_state",
    "pct_fossil_state",
    "carbon_g_per_kwh_zone",
    "renewable_pct_zone",
    "carbon_free_pct_zone",
]

LAG_FEATURES = [
    "usage_lag_1",
    "usage_lag_7",
    "usage_lag_14",
    "usage_lag_30",
    "usage_roll_7_mean",
    "usage_roll_14_mean",
    "usage_roll_30_mean",
    "usage_roll_30_std",
]

CALENDAR_FEATURES = [
    "month_num",
    "month_sin",
    "month_cos",
    "day_of_week",
    "day_of_week_sin",
    "day_of_week_cos",
    "hour",
    "hour_sin",
    "hour_cos",
]


@dataclass
class ElectricityUsageModel:
    model: "RidgeUsageRegressor"
    feature_columns: list[str]
    target: str = TARGET


@dataclass
class RidgeUsageRegressor:
    coefficients: np.ndarray
    encoded_columns: list[str]
    numeric_features: list[str]
    categorical_features: list[str]
    numeric_medians: pd.Series
    numeric_means: pd.Series
    numeric_stds: pd.Series

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        matrix = encode_features(
            frame,
            self.numeric_features,
            self.categorical_features,
            encoded_columns=self.encoded_columns,
            numeric_medians=self.numeric_medians,
            numeric_means=self.numeric_means,
            numeric_stds=self.numeric_stds,
        )
        matrix = np.column_stack([np.ones(len(matrix)), matrix])
        return matrix @ self.coefficients


def _month_to_datetime(series: pd.Series) -> pd.Series:
    """Accepts monthly or daily date-like values and returns pandas datetimes."""
    parsed = pd.to_datetime(series, errors="coerce")
    if parsed.isna().any():
        parsed_month = pd.to_datetime(series.astype(str) + "-01", errors="coerce")
        parsed = parsed.fillna(parsed_month)
    return parsed


def build_training_frame(df: pd.DataFrame, target: str = TARGET) -> pd.DataFrame:
    """
    Build one row per state/date with prior-30-day usage features.

    The current row's target is never used as an input. All lag/rolling features
    are shifted so they only see observations before the prediction date.
    """
    required_columns = set(CATEGORICAL_FEATURES + BASE_NUMERIC_FEATURES + ["month", target])
    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    data = df.copy()
    data["date"] = _month_to_datetime(data["month"])
    data = data.dropna(subset=["date", target])
    data = data.sort_values(["state_code", "date"])

    grouped = data.groupby("state_code", sort=False)[target]
    data["usage_lag_1"] = grouped.shift(1)
    data["usage_lag_7"] = grouped.shift(7)
    data["usage_lag_14"] = grouped.shift(14)
    data["usage_lag_30"] = grouped.shift(30)

    shifted_usage = grouped.shift(1)
    data["usage_roll_7_mean"] = shifted_usage.groupby(data["state_code"]).rolling(7, min_periods=2).mean().reset_index(level=0, drop=True)
    data["usage_roll_14_mean"] = shifted_usage.groupby(data["state_code"]).rolling(14, min_periods=3).mean().reset_index(level=0, drop=True)
    data["usage_roll_30_mean"] = shifted_usage.groupby(data["state_code"]).rolling(30, min_periods=5).mean().reset_index(level=0, drop=True)
    data["usage_roll_30_std"] = shifted_usage.groupby(data["state_code"]).rolling(30, min_periods=5).std().reset_index(level=0, drop=True)

    data["month_num"] = data["date"].dt.month
    data["month_sin"] = np.sin(2 * np.pi * data["month_num"] / 12)
    data["month_cos"] = np.cos(2 * np.pi * data["month_num"] / 12)
    data["day_of_week"] = data["date"].dt.dayofweek
    data["day_of_week_sin"] = np.sin(2 * np.pi * data["day_of_week"] / 7)
    data["day_of_week_cos"] = np.cos(2 * np.pi * data["day_of_week"] / 7)
    data["hour"] = data["date"].dt.hour
    data["hour_sin"] = np.sin(2 * np.pi * data["hour"] / 24)
    data["hour_cos"] = np.cos(2 * np.pi * data["hour"] / 24)
    return data


def encode_features(
    frame: pd.DataFrame,
    numeric_features: list[str],
    categorical_features: list[str],
    encoded_columns: list[str] | None = None,
    numeric_medians: pd.Series | None = None,
    numeric_means: pd.Series | None = None,
    numeric_stds: pd.Series | None = None,
) -> np.ndarray:
    numeric = frame[numeric_features].apply(pd.to_numeric, errors="coerce")
    if numeric_medians is None:
        numeric_medians = numeric.median().fillna(0)
    numeric = numeric.fillna(numeric_medians)

    if numeric_means is None:
        numeric_means = numeric.mean().fillna(0)
    if numeric_stds is None:
        numeric_stds = numeric.std().replace(0, 1).fillna(1)
    numeric = (numeric - numeric_means) / numeric_stds

    categorical = frame[categorical_features].fillna("unknown").astype(str)
    categorical = pd.get_dummies(categorical, columns=categorical_features, dtype=float)

    encoded = pd.concat([numeric.reset_index(drop=True), categorical.reset_index(drop=True)], axis=1)
    if encoded_columns is None:
        encoded_columns = encoded.columns.tolist()
    encoded = encoded.reindex(columns=encoded_columns, fill_value=0)
    return encoded.to_numpy(dtype=float)


def fit_ridge_regressor(
    X: pd.DataFrame,
    y: pd.Series,
    numeric_features: list[str],
    categorical_features: list[str],
    alpha: float = 1.0,
) -> RidgeUsageRegressor:
    numeric = X[numeric_features].apply(pd.to_numeric, errors="coerce")
    numeric_medians = numeric.median().fillna(0)
    numeric = numeric.fillna(numeric_medians)
    numeric_means = numeric.mean().fillna(0)
    numeric_stds = numeric.std().replace(0, 1).fillna(1)

    matrix = encode_features(
        X,
        numeric_features,
        categorical_features,
        numeric_medians=numeric_medians,
        numeric_means=numeric_means,
        numeric_stds=numeric_stds,
    )
    encoded_columns = (
        list(numeric_features)
        + pd.get_dummies(X[categorical_features].fillna("unknown").astype(str), columns=categorical_features, dtype=float)
        .columns.tolist()
    )
    matrix = np.column_stack([np.ones(len(matrix)), matrix])
    target = y.to_numpy(dtype=float)

    penalty = np.eye(matrix.shape[1]) * alpha
    penalty[0, 0] = 0
    coefficients = np.linalg.solve(matrix.T @ matrix + penalty, matrix.T @ target)
    return RidgeUsageRegressor(
        coefficients=coefficients,
        encoded_columns=encoded_columns,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        numeric_medians=numeric_medians,
        numeric_means=numeric_means,
        numeric_stds=numeric_stds,
    )


def regression_metrics(actual: pd.Series, predicted: np.ndarray) -> dict[str, float]:
    actual_values = actual.to_numpy(dtype=float)
    errors = actual_values - predicted
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors**2)))
    total_variance = float(np.sum((actual_values - actual_values.mean()) ** 2))
    residual_variance = float(np.sum(errors**2))
    r2 = float(1 - residual_variance / total_variance) if total_variance else 0.0
    return {
        "mae_kw_usage": mae,
        "rmse_kw_usage": rmse,
        "r2": r2,
    }


def train_electricity_usage_model(
    df: pd.DataFrame,
    target: str = TARGET,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[ElectricityUsageModel, dict[str, float]]:
    """
    Train one global usage model for all states.

    The model learns state/zone differences, pricing signals, generation mix,
    carbon intensity, and each state's prior usage pattern.
    """
    training_frame = build_training_frame(df, target=target)
    feature_columns = CATEGORICAL_FEATURES + BASE_NUMERIC_FEATURES + LAG_FEATURES + CALENDAR_FEATURES

    unique_dates = training_frame["date"].drop_duplicates().sort_values().reset_index(drop=True)
    if len(unique_dates) < 2:
        raise ValueError("Need at least two unique timestamps to create a time-based train/test split.")

    split_index = max(1, int(len(unique_dates) * (1 - test_size)))
    split_index = min(split_index, len(unique_dates) - 1)
    test_start = unique_dates.iloc[split_index]
    train_rows = training_frame["date"] < test_start
    test_rows = training_frame["date"] >= test_start

    X_train = training_frame.loc[train_rows, feature_columns]
    y_train = training_frame.loc[train_rows, target]
    X_test = training_frame.loc[test_rows, feature_columns]
    y_test = training_frame.loc[test_rows, target]

    numeric_features = BASE_NUMERIC_FEATURES + LAG_FEATURES + CALENDAR_FEATURES
    model = fit_ridge_regressor(
        X_train,
        y_train,
        numeric_features=numeric_features,
        categorical_features=CATEGORICAL_FEATURES,
    )

    predictions = model.predict(X_test)
    metrics = regression_metrics(y_test, predictions)
    return ElectricityUsageModel(model=model, feature_columns=feature_columns, target=target), metrics


def predict_usage_by_state(
    fitted: ElectricityUsageModel,
    df: pd.DataFrame,
    states: Iterable[str] | None = None,
) -> pd.DataFrame:
    """
    Predict total kW usage for each state/date in df.

    The output includes source-weighted predicted usage and estimated spend.
    Spend is computed from predicted usage * cents/kWh / 100.
    """
    prediction_frame = build_training_frame(df, target=fitted.target)
    if states is not None:
        prediction_frame = prediction_frame[prediction_frame["state_code"].isin(states)]

    result = prediction_frame[
        [
            "state_code",
            "state_name",
            "electricity_maps_zone_id",
            "date",
            "avg_electricity_cost_cents_per_kwh",
        ]
        + MIX_COLUMNS
    ].copy()
    result["predicted_total_kw_usage"] = fitted.model.predict(prediction_frame[fitted.feature_columns])
    result["estimated_total_cost"] = (
        result["predicted_total_kw_usage"] * result["avg_electricity_cost_cents_per_kwh"] / 100
    )

    mix_total = result[MIX_COLUMNS].sum(axis=1).replace(0, np.nan)
    for column in MIX_COLUMNS:
        source = column.removeprefix("pct_").removesuffix("_state")
        result[f"predicted_{source}_kw_usage"] = (
            result["predicted_total_kw_usage"] * result[column] / mix_total
        )
        result[f"estimated_{source}_cost"] = (
            result[f"predicted_{source}_kw_usage"] * result["avg_electricity_cost_cents_per_kwh"] / 100
        )

    return result


# Backward-compatible aliases for older imports during exploration.
ElectricityCostModel = ElectricityUsageModel
train_electricity_cost_model = train_electricity_usage_model
predict_cost_by_state = predict_usage_by_state


if __name__ == "__main__":
    # Example:
    # df = pd.read_csv("state_energy_daily.csv")
    # fitted_model, scores = train_electricity_usage_model(df)
    # predictions = predict_usage_by_state(fitted_model, df)
    # predictions.to_csv("state_usage_predictions.csv", index=False)
    pass

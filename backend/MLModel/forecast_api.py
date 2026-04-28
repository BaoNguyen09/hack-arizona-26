from __future__ import annotations

from typing import Any

try:
    from .forecast_future_usage import forecast_from_files  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    from forecast_future_usage import forecast_from_files

from fastapi import FastAPI
from pydantic import BaseModel, Field


class ForecastPayload(BaseModel):
    start: str = Field(..., examples=["2026-04-27T14:00:00Z"])
    end: str | None = Field(None, examples=["2026-04-28T00:00:00Z"])
    hours: int | None = Field(None, ge=1, examples=[1])
    states: list[str] | None = Field(None, examples=[["CA", "TX", "NY"]])
    model_path: str = "electricity_usage_model.pkl"
    history_path: str = "state_energy_timeseries.csv"
    assumption_window_hours: int = Field(24 * 30, ge=1)


app = FastAPI(title="Electricity Usage Forecast API")


@app.post("/forecast")
def forecast(payload: ForecastPayload) -> list[dict[str, Any]]:
    """
    Forecast future state-level kWh usage and estimated source-weighted cost.

    Provide either `hours` or `end`. If both are present, `hours` wins.
    """
    predictions = forecast_from_files(
        start=payload.start,
        end=payload.end,
        hours=payload.hours,
        states=payload.states,
        model_path=payload.model_path,
        history_path=payload.history_path,
        assumption_window_hours=payload.assumption_window_hours,
    )
    return predictions.where(predictions.notna(), None).to_dict(orient="records")

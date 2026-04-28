from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx
import numpy as np
import orjson
import pandas as pd
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from backend.app.core.config import settings
from backend.app.core.perf import SimpleLRUCache


DEFAULT_HOURLY_VARS: tuple[str, ...] = (
    "temperature_2m",
    "relative_humidity_2m",
    "cloud_cover",
    "wind_speed_10m",
    "precipitation",
)


def _to_utc_hour(ts: str | datetime) -> pd.Timestamp:
    value = pd.Timestamp(ts)
    if value.tzinfo is None:
        value = value.tz_localize(timezone.utc)
    return value.tz_convert(timezone.utc).floor("h")


def _cache_dir() -> Path:
    root = Path(settings.data_dir) / "cache" / "open_meteo"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _cache_key(*parts: str) -> str:
    joined = "|".join(parts).encode("utf-8")
    return hashlib.sha256(joined).hexdigest()[:32]


def _cache_path(key: str) -> Path:
    return _cache_dir() / f"{key}.json"


def _read_disk_cache(key: str) -> dict[str, Any] | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        return orjson.loads(path.read_bytes())
    except Exception:
        return None


def _write_disk_cache(key: str, payload: dict[str, Any]) -> None:
    path = _cache_path(key)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(orjson.dumps(payload))
    os.replace(tmp, path)


_memory_cache: SimpleLRUCache = SimpleLRUCache(maxsize=256)


@dataclass(frozen=True)
class WeatherFetchResult:
    frame: pd.DataFrame
    source_status: str  # "live" | "cache" | "cache_stale" | "failed"
    fetched_at_utc: str | None = None


class OpenMeteoError(RuntimeError):
    pass


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, OpenMeteoError)),
    wait=wait_exponential_jitter(initial=0.5, max=6.0),
    stop=stop_after_attempt(3),
)
def _fetch_open_meteo_json(
    *,
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    hourly_vars: tuple[str, ...],
) -> dict[str, Any]:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(hourly_vars),
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "UTC",
        "timeformat": "iso8601",
    }
    with httpx.Client(timeout=httpx.Timeout(10.0)) as client:
        resp = client.get(url, params=params)
        if resp.status_code != 200:
            raise OpenMeteoError(f"Open-Meteo error {resp.status_code}")
        return resp.json()


def fetch_open_meteo_hourly(
    *,
    lat: float,
    lon: float,
    start: str | datetime,
    end: str | datetime,
    hourly_vars: Iterable[str] = DEFAULT_HOURLY_VARS,
    use_disk_cache: bool = True,
) -> WeatherFetchResult:
    """
    Fetch hourly weather from Open‑Meteo and return a normalized hourly DataFrame.

    Returned columns (when available):
    - timestamp (UTC, hourly)
    - temp_c, relative_humidity_pct, cloud_cover_pct, wind_speed_m_s, precip_mm
    - cooling_degree_hours, heating_degree_hours (base 18°C)
    """
    start_ts = _to_utc_hour(start)
    end_ts = _to_utc_hour(end)
    if end_ts <= start_ts:
        raise ValueError("end must be after start")

    hourly_vars_t = tuple(hourly_vars)
    start_date = start_ts.date().isoformat()
    # Open‑Meteo end_date is inclusive; request the day containing the last hour.
    end_date = end_ts.date().isoformat()

    key = _cache_key(
        f"{lat:.4f}",
        f"{lon:.4f}",
        start_date,
        end_date,
        ",".join(hourly_vars_t),
    )

    mem_hit, mem_value = _memory_cache.get(key)
    if mem_hit and isinstance(mem_value, dict):
        payload = mem_value
        status = "cache"
        fetched_at = payload.get("_fetched_at_utc")
    else:
        payload = None
        status = "failed"
        fetched_at = None

        if use_disk_cache:
            disk_payload = _read_disk_cache(key)
            if disk_payload is not None:
                payload = disk_payload
                status = "cache"
                fetched_at = disk_payload.get("_fetched_at_utc")

        if payload is None:
            live = _fetch_open_meteo_json(
                lat=lat,
                lon=lon,
                start_date=start_date,
                end_date=end_date,
                hourly_vars=hourly_vars_t,
            )
            payload = dict(live)
            payload["_fetched_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            status = "live"
            fetched_at = payload["_fetched_at_utc"]
            _memory_cache.set(payload, key)
            if use_disk_cache:
                _write_disk_cache(key, payload)

    frame = _normalize_open_meteo_hourly(payload)
    mask = (frame["timestamp"] >= start_ts) & (frame["timestamp"] < end_ts)
    frame = frame.loc[mask].reset_index(drop=True)

    return WeatherFetchResult(frame=frame, source_status=status, fetched_at_utc=fetched_at)


def _normalize_open_meteo_hourly(payload: dict[str, Any]) -> pd.DataFrame:
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    ts = pd.to_datetime(times, errors="coerce", utc=True)

    df = pd.DataFrame({"timestamp": ts})
    # Map Open‑Meteo variable names to our canonical names
    mapping = {
        "temperature_2m": "temp_c",
        "relative_humidity_2m": "relative_humidity_pct",
        "cloud_cover": "cloud_cover_pct",
        "wind_speed_10m": "wind_speed_m_s",
        "precipitation": "precip_mm",
    }
    for raw, canonical in mapping.items():
        values = hourly.get(raw)
        if values is None:
            continue
        df[canonical] = pd.to_numeric(pd.Series(values), errors="coerce")

    base_temp_c = 18.0
    temp = df.get("temp_c")
    if temp is not None:
        df["cooling_degree_hours"] = np.maximum(temp - base_temp_c, 0.0)
        df["heating_degree_hours"] = np.maximum(base_temp_c - temp, 0.0)
    else:
        df["cooling_degree_hours"] = np.nan
        df["heating_degree_hours"] = np.nan

    return df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)


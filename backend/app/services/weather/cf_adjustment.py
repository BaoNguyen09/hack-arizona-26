from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class WeatherCfAdjustment:
    """
    Simple Tier-1 weather -> capacity-factor adjustment.

    This is not a physics model; it’s a bounded heuristic designed to support
    simulation + “what if” exploration without heavy dependencies.
    """

    solar_cloud_cover_strength: float = 0.35  # 100% cloud reduces CF by up to 35%
    solar_temp_penalty_per_c_above_25: float = 0.002  # 0.2% per °C above 25°C

    wind_speed_ref_m_s: float = 7.0
    wind_speed_sensitivity: float = 0.06  # ~6% CF change per 1 m/s vs ref (bounded)

    cf_multiplier_min: float = 0.7
    cf_multiplier_max: float = 1.25


def adjusted_capacity_factor(
    *,
    base_cf: np.ndarray,
    technology: str,
    temp_c: np.ndarray | None = None,
    cloud_cover_pct: np.ndarray | None = None,
    wind_speed_m_s: np.ndarray | None = None,
    config: WeatherCfAdjustment | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    cfg = config or WeatherCfAdjustment()

    mult = np.ones_like(base_cf, dtype=float)
    if technology == "solar":
        if cloud_cover_pct is not None:
            cloud = np.clip(cloud_cover_pct, 0.0, 100.0) / 100.0
            mult = mult * (1.0 - cfg.solar_cloud_cover_strength * cloud)
        if temp_c is not None:
            temp = temp_c.astype(float)
            mult = mult * (1.0 - cfg.solar_temp_penalty_per_c_above_25 * np.maximum(temp - 25.0, 0.0))
    elif technology == "wind":
        if wind_speed_m_s is not None:
            wind = wind_speed_m_s.astype(float)
            mult = mult * (1.0 + cfg.wind_speed_sensitivity * (wind - cfg.wind_speed_ref_m_s))
    else:
        raise ValueError(f"Unknown technology: {technology}")

    mult = np.clip(mult, cfg.cf_multiplier_min, cfg.cf_multiplier_max)
    cf = np.clip(base_cf * mult, 0.0, 1.0)
    return cf, mult


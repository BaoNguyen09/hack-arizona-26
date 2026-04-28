"""County data store and deterministic generator.

Provides deterministic county-level data based on FIPS codes,
mirroring the behavior of the frontend to allow the API to function
without a fully populated database of grid cells.
"""

import math
from functools import lru_cache

from .state_data import STATE_DATA

# FIPS → State abbreviation (all 50 + DC)
STATE_FIPS_TO_ABBR: dict[str, str] = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA",
    "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
    "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN",
    "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
    "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
    "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI",
    "56": "WY",
}

# Approximate state centroid coordinates for more realistic county placement
STATE_CENTROIDS: dict[str, tuple[float, float]] = {
    "AL": (32.8, -86.8), "AK": (64.0, -153.0), "AZ": (34.3, -111.7),
    "AR": (34.8, -92.2), "CA": (37.2, -119.5), "CO": (39.0, -105.5),
    "CT": (41.6, -72.7), "DE": (39.0, -75.5), "DC": (38.9, -77.0),
    "FL": (28.6, -82.4), "GA": (32.7, -83.4), "HI": (20.8, -156.3),
    "ID": (44.4, -114.6), "IL": (40.0, -89.2), "IN": (39.8, -86.3),
    "IA": (42.0, -93.5), "KS": (38.5, -98.3), "KY": (37.8, -85.7),
    "LA": (31.1, -91.9), "ME": (45.4, -69.2), "MD": (39.0, -76.7),
    "MA": (42.2, -71.8), "MI": (44.3, -84.5), "MN": (46.3, -94.3),
    "MS": (32.7, -89.7), "MO": (38.4, -92.5), "MT": (47.0, -109.6),
    "NE": (41.5, -99.8), "NV": (39.3, -116.6), "NH": (43.7, -71.6),
    "NJ": (40.2, -74.7), "NM": (34.5, -106.0), "NY": (42.9, -75.5),
    "NC": (35.6, -79.4), "ND": (47.4, -100.5), "OH": (40.3, -82.8),
    "OK": (35.6, -97.5), "OR": (43.9, -120.6), "PA": (40.9, -77.8),
    "RI": (41.7, -71.5), "SC": (33.9, -80.9), "SD": (44.4, -100.2),
    "TN": (35.8, -86.3), "TX": (31.5, -99.3), "UT": (39.3, -111.7),
    "VT": (44.1, -72.7), "VA": (37.5, -78.8), "WA": (47.4, -120.5),
    "WV": (38.6, -80.6), "WI": (44.6, -89.7), "WY": (43.0, -107.5),
}


class _LCG:
    """Linear Congruential Generator matching the frontend seededRandom exactly."""

    __slots__ = ("s",)

    def __init__(self, seed: int) -> None:
        self.s = (seed ^ 0x5DEECE66D) & 0x7FFFFFFF
        if self.s == 0:
            self.s = 1
        for _ in range(5):
            self.s = (self.s * 16807) % 2147483647

    def rand(self) -> float:
        self.s = (self.s * 16807) % 2147483647
        return (self.s - 1) / 2147483646.0


@lru_cache(maxsize=4096)
def generate_county_data(fips: str, technology: str = "solar") -> dict:
    """Generate deterministic energy metrics for a given county FIPS code.

    Args:
        fips: 5-digit county FIPS code as string
        technology: 'solar' or 'wind'

    Returns:
        Dictionary of raw metrics mimicking a processed database row.
    """
    try:
        fips_int = int(fips)
    except ValueError:
        fips_int = sum(ord(c) for c in fips)

    rng = _LCG(fips_int)

    state_fips = fips[:2]
    state = STATE_FIPS_TO_ABBR.get(state_fips, "OTHER")

    # Fetch state baseline from the provided CSV data
    base = STATE_DATA.get(
        state,
        {"price": 100.0, "solar": 5.0, "wind": 5.0, "hydro": 5.0, "fossil": 85.0},
    )

    # Carbon intensity: heavily influenced by fossil percentage
    ci_base = base["fossil"] * 8
    carbon_intensity = max(
        10, ci_base + (rng.rand() * (ci_base * 0.8) - (ci_base * 0.4))
    )

    # Renewable and carbon-free metrics
    state_renewable = base["solar"] + base["wind"] + base["hydro"]
    renewable_percent = min(95, max(5, state_renewable + (rng.rand() * 30 - 15)))

    state_price = base["price"] * 10  # cents/kWh → $/MWh
    price = max(
        10, state_price + (rng.rand() * (state_price * 0.4) - (state_price * 0.2))
    )

    # Capacity factors — mirrors frontend zones.ts exactly
    solar_cf = max(
        0.1,
        min(0.35, 0.15 + (base["solar"] / 100.0 * 0.5) + (rng.rand() * 0.1 - 0.05)),
    )
    wind_cf = max(
        0.1,
        min(0.55, 0.2 + (base["wind"] / 100.0 * 0.5) + (rng.rand() * 0.1 - 0.05)),
    )

    load_base = 0.1 + (rng.rand() * 3.4)
    transmission_km = 0.5 + (rng.rand() * 44.5)

    # Use state centroid with FIPS-seeded jitter for realistic coordinates
    centroid = STATE_CENTROIDS.get(state, (37.0, -96.0))
    lat = centroid[0] + (rng.rand() * 4.0 - 2.0)
    lon = centroid[1] + (rng.rand() * 6.0 - 3.0)

    return {
        "cell_id": f"county_{fips}",
        "lat": lat,
        "lon": lon,
        "solar_cf_mean": solar_cf,
        "wind_cf_mean": wind_cf,
        "price_usd_per_mwh_mean": price,
        "carbon_g_per_kwh_mean": carbon_intensity,
        "nearest_transmission_km": transmission_km,
        "price_hub_id": f"HUB_{state}",
        "grid_zone_id": f"ZONE_{state}",
        "load_gw": load_base,
        "renewable_percent": min(100.0, renewable_percent),
    }


def generate_county_profiles(
    fips: str, solar_cf: float, wind_cf: float, carbon_intensity: float, price: float
) -> tuple[list[dict], list[dict]]:
    """Generate deterministic 24h generation and carbon intensity profiles.

    Returns:
        Tuple of (generation_profile, carbon_profile) each with 24 hourly entries.
    """
    generation_profile: list[dict] = []
    carbon_profile: list[dict] = []

    for h in range(24):
        # Solar generation curve: peaks at ~13h, zero at night
        solar_gen = max(0.0, math.sin((h - 6) * math.pi / 12))
        # Wind generation: stronger overnight, weaker midday
        wind_gen = 0.4 + 0.2 * math.sin(h * math.pi / 8)

        # Price modulation: higher when solar generation is low
        price_mult = 1.0 + 0.35 * (1.0 - solar_gen) - 0.15 * solar_gen
        hour_price = price * price_mult

        # Carbon modulation: grid is dirtier when renewables are low
        carbon_mult = 1.0 + 0.3 * (1.0 - solar_gen)
        hour_carbon = carbon_intensity * carbon_mult

        # Generation in MW for a 50 MW project
        gen_mw = solar_cf * solar_gen * 50.0 + wind_cf * wind_gen * 10.0

        generation_profile.append({
            "hour": h,
            "generation": round(gen_mw, 2),
            "price": round(hour_price, 2),
        })
        carbon_profile.append({
            "hour": h,
            "gridIntensity": round(hour_carbon, 1),
            "displaced": round(gen_mw * carbon_intensity / 1e6, 4),
        })

    return generation_profile, carbon_profile

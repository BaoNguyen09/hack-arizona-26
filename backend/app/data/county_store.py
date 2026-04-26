"""County data store and deterministic generator.

Provides deterministic county-level data based on FIPS codes,
mirroring the behavior of the frontend to allow the API to function
without a fully populated database of grid cells.
"""

from .state_data import STATE_DATA

# Base FIPS prefixes for major states to give them realistic profiles
STATE_PROFILES = {
    "06": "CA",
    "48": "TX",
    "36": "NY",
    "17": "IL",
    "12": "FL",
    "53": "WA",
    "41": "OR",
}

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
        # Fallback using sum of char codes, similar to TS
        fips_int = sum(ord(c) for c in fips)
        
    # Implement the exact same LCG as the frontend to guarantee identical values
    class LCG:
        def __init__(self, seed: int):
            self.s = (seed ^ 0x5deece66d) & 0x7fffffff
            if self.s == 0:
                self.s = 1
            for _ in range(5):
                self.s = (self.s * 16807) % 2147483647
                
        def rand(self) -> float:
            self.s = (self.s * 16807) % 2147483647
            return (self.s - 1) / 2147483646.0
            
    rng = LCG(fips_int)
    
    state_fips = fips[:2]
    state = STATE_PROFILES.get(state_fips, "OTHER")
    
    # Regional energy characteristics
    is_west = state in ["WA", "OR", "CA", "ID"]
    is_midwest = state in ["ND", "SD", "NE", "KS", "IA", "MO"]
    is_south = state in ["TX", "LA", "MS", "AL", "GA", "FL"]
    is_east = state in [
        "NY",
        "PA",
        "NJ",
        "MA",
        "CT",
        "VT",
        "ME",
        "NH",
        "RI",
        "MD",
        "DE",
    ]

    ci_base = 400
    if is_west:
        ci_base = 150
    if is_midwest:
        ci_base = 550
    if is_east:
        ci_base = 350
    if is_south:
        ci_base = 450
    
    # Fetch state baseline from the provided CSV data
    # Fallback if state not found
    base = STATE_DATA.get(
        state,
        {
            "price": 100.0,
            "solar": 5.0,
            "wind": 5.0,
            "hydro": 5.0,
            "fossil": 85.0,
        },
    )
    
    # Real world carbon logic: heavily influenced by fossil %
    # 100% fossil ≈ 800 gCO₂eq/kWh, 0% = 0
    ci_base = base["fossil"] * 8
    
    # Massive localized county variance so adjacent counties look very different
    # rng.rand() gives 0 to 1.
    carbon_intensity = max(
        10,
        ci_base + (rng.rand() * (ci_base * 0.8) - (ci_base * 0.4)),
    )
    
    # Calculate renewable and carbon free metrics
    state_renewable = base["solar"] + base["wind"] + base["hydro"]
    renewable_percent = min(95, max(5, state_renewable + (rng.rand() * 30 - 15)))
    
    state_price = base["price"] * 10  # convert cents/kWh to $/MWh
    price = max(
        10,
        state_price + (rng.rand() * (state_price * 0.4) - (state_price * 0.2)),
    )
    
    # For the frontend API response, we need CFs which are roughly 0.1 to 0.4.
    # We will derive them roughly from the state percentage just for consistency.
    solar_cf = max(
        0.1,
        min(
            0.35,
            0.15 + (base["solar"] / 100.0 * 0.5) + (rng.rand() * 0.1 - 0.05),
        ),
    )
    wind_cf = max(
        0.1,
        min(
            0.55,
            0.2 + (base["wind"] / 100.0 * 0.5) + (rng.rand() * 0.1 - 0.05),
        ),
    )
    
    carbon = carbon_intensity
    
    # Generate a realistic load (GW) based on the FIPS
    load_base = 0.1 + (rng.rand() * 3.4)
    
    # Nearest transmission
    transmission_km = 0.5 + (rng.rand() * 44.5)

    # We return a dict that maps perfectly to what `score_single_cell` expects
    # inside backend.app.services.site or what we use to build SiteMetrics
    lat = 25.0 + rng.rand() * 24.0
    lon = -125.0 + rng.rand() * 58.0

    return {
        "cell_id": f"county_{fips}",
        "lat": lat,  # Rough US bounds until county centroids are wired in
        "lon": lon,
        "solar_cf_mean": solar_cf,
        "wind_cf_mean": wind_cf,
        "price_usd_per_mwh_mean": price,
        "carbon_g_per_kwh_mean": carbon,
        "nearest_transmission_km": transmission_km,
        "price_hub_id": f"HUB_{state}",
        "grid_zone_id": f"ZONE_{state}",
        "load_gw": load_base,
        "renewable_percent": min(100.0, renewable_percent)
    }

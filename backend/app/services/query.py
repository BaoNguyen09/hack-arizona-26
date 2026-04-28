"""Natural-language query parsing and filter application."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from backend.app.core.config import settings
from backend.app.data.county_store import generate_county_data
from backend.app.data.processed_store import get_store
from backend.app.engine.scoring import score_all_cells
from backend.app.schemas.scenario import (
    QueryFilters,
    QueryResponse,
    QuerySummaryStats,
    ScenarioRequest,
)

OPENAI_TIMEOUT_SECONDS = 10.0

STATE_ABBR_TO_NAME: dict[str, str] = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "DC": "District of Columbia",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}
STATE_NAME_TO_ABBR = {
    name.lower(): abbr for abbr, name in STATE_ABBR_TO_NAME.items()
}
STATE_FIPS_TO_ABBR: dict[str, str] = {
    "01": "AL",
    "02": "AK",
    "04": "AZ",
    "05": "AR",
    "06": "CA",
    "08": "CO",
    "09": "CT",
    "10": "DE",
    "11": "DC",
    "12": "FL",
    "13": "GA",
    "15": "HI",
    "16": "ID",
    "17": "IL",
    "18": "IN",
    "19": "IA",
    "20": "KS",
    "21": "KY",
    "22": "LA",
    "23": "ME",
    "24": "MD",
    "25": "MA",
    "26": "MI",
    "27": "MN",
    "28": "MS",
    "29": "MO",
    "30": "MT",
    "31": "NE",
    "32": "NV",
    "33": "NH",
    "34": "NJ",
    "35": "NM",
    "36": "NY",
    "37": "NC",
    "38": "ND",
    "39": "OH",
    "40": "OK",
    "41": "OR",
    "42": "PA",
    "44": "RI",
    "45": "SC",
    "46": "SD",
    "47": "TN",
    "48": "TX",
    "49": "UT",
    "50": "VT",
    "51": "VA",
    "53": "WA",
    "54": "WV",
    "55": "WI",
    "56": "WY",
}
MACRO_REGIONS: dict[str, set[str]] = {
    "southwest": {"AZ", "NM", "NV", "UT", "CA"},
    "west": {"WA", "OR", "CA", "NV", "ID", "MT", "WY", "UT", "AZ", "CO", "NM"},
    "pacific northwest": {"WA", "OR", "ID"},
    "great plains": {"ND", "SD", "NE", "KS", "OK", "TX", "MT", "WY", "CO"},
    "midwest": {"ND", "SD", "NE", "KS", "MN", "IA", "MO", "WI", "IL", "IN", "MI", "OH"},
    "northeast": {"ME", "NH", "VT", "MA", "RI", "CT", "NY", "NJ", "PA"},
    "southeast": {"VA", "NC", "SC", "GA", "FL", "AL", "MS", "TN", "KY", "LA", "AR"},
    "ercot": {"TX"},
    "caiso": {"CA"},
}
ZONE_KEYWORDS = ("ercot", "caiso", "pjm", "miso", "spp", "nyiso", "isone", "iso-ne")

PERCENT_FIELDS = {"min_cf"}


def run_query(query: str) -> QueryResponse:
    """Parse a natural-language query and return matched cells/counties."""
    filters = extract_filters(query)
    if filters is None or not filters.has_any_value():
        return QueryResponse(
            parsed=False,
            message=(
                "I couldn't parse that query yet. Try something like "
                "'solar in Texas with capacity factor above 30% and LCOE below 50'."
            ),
            filters=None,
            effective_technology=None,
        )

    effective_technology = filters.technology or "solar"
    matched_cell_ids = _filter_scored_cells(filters, effective_technology)
    matched_county_fips, summary = _filter_counties(filters, effective_technology)

    if matched_cell_ids or matched_county_fips:
        county_word = "county" if len(matched_county_fips) == 1 else "counties"
        best_note = ""
        if summary and summary.best_county_name:
            best_note = f" Best match: {summary.best_county_name}."
        message = (
            f"Found {len(matched_county_fips)} matching {county_word} "
            f"across {len(_non_null_filter_values(filters))} filters.{best_note}"
        )
    else:
        message = "I parsed the query, but no counties matched those filters."

    return QueryResponse(
        parsed=True,
        message=message,
        filters=filters,
        effective_technology=effective_technology,
        matched_cell_ids=matched_cell_ids,
        matched_county_fips=matched_county_fips,
        matched_cell_count=len(matched_cell_ids),
        matched_county_count=len(matched_county_fips),
        summary=summary,
    )


def extract_filters(query: str) -> QueryFilters | None:
    """Extract structured filters via GPT-4o-mini or deterministic fallback."""
    llm_filters = _extract_filters_with_openai(query)
    if llm_filters is not None and llm_filters.has_any_value():
        return llm_filters
    fallback_filters = _extract_filters_with_fallback(query)
    if fallback_filters.has_any_value():
        return fallback_filters
    return None


def _extract_filters_with_openai(query: str) -> QueryFilters | None:
    """Use GPT-4o-mini function calling when OPENAI_API_KEY is configured."""
    if not settings.openai_api_key:
        return None

    tool_schema = {
        "type": "function",
        "function": {
            "name": "extract_filters",
            "description": "Extract structured renewable siting filters from a user query.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "technology": {"type": ["string", "null"], "enum": ["solar", "wind", None]},
                    "region": {"type": ["string", "null"]},
                    "min_cf": {"type": ["number", "null"]},
                    "min_lcoe": {"type": ["number", "null"]},
                    "max_lcoe": {"type": ["number", "null"]},
                    "min_carbon_intensity": {"type": ["number", "null"]},
                    "max_carbon_intensity": {"type": ["number", "null"]},
                    "min_price": {"type": ["number", "null"]},
                    "max_price": {"type": ["number", "null"]},
                    "min_renewable_percent": {"type": ["number", "null"]},
                    "max_transmission_km": {"type": ["number", "null"]},
                },
                "additionalProperties": False,
            },
        },
    }

    system_prompt = (
        "Extract only explicit filters from the user's renewable-energy siting query. "
        "Capacity factor fields must be returned as fractions from 0 to 1. "
        "If a filter is not explicitly present, return null for it."
    )

    try:
        with httpx.Client(timeout=OPENAI_TIMEOUT_SECONDS) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.openai_query_model,
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query},
                    ],
                    "tools": [tool_schema],
                    "tool_choice": {
                        "type": "function",
                        "function": {"name": "extract_filters"},
                    },
                },
            )
            response.raise_for_status()
            body = response.json()
    except Exception:
        return None

    try:
        tool_call = body["choices"][0]["message"]["tool_calls"][0]
        arguments = json.loads(tool_call["function"]["arguments"])
    except Exception:
        return None

    return _normalize_filters(arguments)


def _extract_filters_with_fallback(query: str) -> QueryFilters:
    """Parse common patterns locally so the feature works without LLM access."""
    lowered = query.lower()
    parsed: dict[str, Any] = {}

    if "solar" in lowered:
        parsed["technology"] = "solar"
    elif "wind" in lowered:
        parsed["technology"] = "wind"

    region = _extract_region(lowered)
    if region is not None:
        parsed["region"] = region

    min_cf = _extract_numeric(
        lowered,
        (
            r"(?:capacity factor|cf)[^0-9]*(?:above|over|at least|minimum of|>=)\s*\$?\s*(\d+(?:\.\d+)?)\s*%?",
            r"(?:above|over|at least|minimum of|>=)\s*\$?\s*(\d+(?:\.\d+)?)\s*%?\s*(?:capacity factor|cf)",
        ),
        is_percent=True,
    )
    if min_cf is not None:
        parsed["min_cf"] = min_cf

    min_lcoe = _extract_numeric(
        lowered,
        (
            r"lcoe[^0-9]*(?:above|over|greater than|more than|at least|minimum of|>=)\s*\$?\s*(\d+(?:\.\d+)?)",
            r"(?:above|over|greater than|more than|at least|minimum of|>=)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:/mwh|usd/mwh|dollars per mwh)?[^.]*lcoe",
        ),
    )
    if min_lcoe is not None:
        parsed["min_lcoe"] = min_lcoe

    max_lcoe = _extract_numeric(
        lowered,
        (
            r"lcoe[^0-9]*(?:under|below|less than|at most|max(?:imum)? of|<=)\s*\$?\s*(\d+(?:\.\d+)?)",
            r"(?:under|below|less than|at most|max(?:imum)? of|<=)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:/mwh|usd/mwh|dollars per mwh)?[^.]*lcoe",
        ),
    )
    if max_lcoe is not None:
        parsed["max_lcoe"] = max_lcoe

    min_carbon = _extract_numeric(
        lowered,
        (
            r"(?:carbon intensity|carbon)[^0-9]*(?:above|over|at least|minimum of|>=)\s*(\d+(?:\.\d+)?)",
            r"(?:above|over|at least|minimum of|>=)\s*(\d+(?:\.\d+)?)\s*(?:g|gco2/kwh|carbon intensity|carbon)",
        ),
    )
    if min_carbon is not None:
        parsed["min_carbon_intensity"] = min_carbon

    max_carbon = _extract_numeric(
        lowered,
        (
            r"(?:carbon intensity|carbon)[^0-9]*(?:under|below|less than|at most|max(?:imum)? of|<=)\s*(\d+(?:\.\d+)?)",
            r"(?:under|below|less than|at most|max(?:imum)? of|<=)\s*(\d+(?:\.\d+)?)\s*(?:g|gco2/kwh|carbon intensity|carbon)",
        ),
    )
    if max_carbon is not None:
        parsed["max_carbon_intensity"] = max_carbon

    min_price = _extract_numeric(
        lowered,
        (
            r"(?:price|wholesale price|power price)[^0-9]*(?:above|over|at least|minimum of|>=)\s*\$?\s*(\d+(?:\.\d+)?)",
            r"(?:above|over|at least|minimum of|>=)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:/mwh|usd/mwh|price)",
        ),
    )
    if min_price is not None:
        parsed["min_price"] = min_price

    max_price = _extract_numeric(
        lowered,
        (
            r"(?:price|wholesale price|power price)[^0-9]*(?:under|below|less than|at most|max(?:imum)? of|<=)\s*\$?\s*(\d+(?:\.\d+)?)",
            r"(?:under|below|less than|at most|max(?:imum)? of|<=)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:/mwh|usd/mwh|price)",
        ),
    )
    if max_price is not None:
        parsed["max_price"] = max_price

    min_renewable = _extract_numeric(
        lowered,
        (
            r"(?:renewable share|renewable|renewables)[^0-9]*(?:above|over|at least|minimum of|>=)\s*(\d+(?:\.\d+)?)\s*%?",
            r"(?:above|over|at least|minimum of|>=)\s*(\d+(?:\.\d+)?)\s*%?\s*(?:renewable share|renewable|renewables)",
        ),
    )
    if min_renewable is not None:
        parsed["min_renewable_percent"] = min_renewable

    max_transmission = _extract_numeric(
        lowered,
        (
            r"(?:transmission|interconnect(?:ion)?)[^0-9]*(?:under|below|less than|at most|max(?:imum)? of|<=)\s*(\d+(?:\.\d+)?)\s*(?:km|kilometers?)",
            r"(?:under|below|less than|at most|max(?:imum)? of|<=)\s*(\d+(?:\.\d+)?)\s*(?:km|kilometers?)[^.]*transmission",
        ),
    )
    if max_transmission is not None:
        parsed["max_transmission_km"] = max_transmission

    # ── Top-N / ranking queries ("top 10", "best 5", "cheapest 20") ──
    top_match = re.search(
        r"(?:top|best|cheapest|lowest|highest|worst)\s+(\d+)", lowered
    )
    if top_match:
        parsed["top_n"] = int(top_match.group(1))

    # ── Sort preference ("sort by lcoe", "ranked by carbon") ──
    sort_match = re.search(
        r"(?:sort|rank|order)(?:ed)?\s+by\s+(\w+)", lowered
    )
    if sort_match:
        sort_key = sort_match.group(1).lower()
        sort_map = {
            "lcoe": "lcoe",
            "cost": "lcoe",
            "carbon": "carbon_intensity",
            "renewable": "renewable_percent",
            "price": "price",
            "score": "composite_score",
        }
        parsed["sort_by"] = sort_map.get(sort_key, "composite_score")

    # Infer sort for comparative queries
    if "cheapest" in lowered or "lowest cost" in lowered:
        parsed.setdefault("sort_by", "lcoe")
    elif "cleanest" in lowered or "lowest carbon" in lowered or "greenest" in lowered:
        parsed.setdefault("sort_by", "carbon_intensity")
    elif "most renewable" in lowered or "highest renewable" in lowered:
        parsed.setdefault("sort_by", "renewable_percent")

    # If top_n specified but no other filters, add a default tech so has_any_value passes
    if parsed.get("top_n") and len(parsed) == 1:
        parsed["technology"] = "solar"

    return _normalize_filters(parsed) or QueryFilters()


def _extract_region(lowered_query: str) -> str | None:
    """Extract a recognizable region keyword or state."""
    for phrase in sorted(MACRO_REGIONS.keys(), key=len, reverse=True):
        if phrase in lowered_query:
            return phrase

    for zone in ZONE_KEYWORDS:
        if zone in lowered_query:
            return zone

    for state_name in sorted(STATE_NAME_TO_ABBR.keys(), key=len, reverse=True):
        if state_name in lowered_query:
            return state_name

    tokens = re.findall(r"\b[a-z]{2}\b", lowered_query)
    for token in tokens:
        if token.upper() in STATE_ABBR_TO_NAME:
            return token.upper()

    return None


def _extract_numeric(
    query: str,
    patterns: tuple[str, ...],
    *,
    is_percent: bool = False,
) -> float | None:
    """Extract the first numeric match from a list of regex patterns."""
    for pattern in patterns:
        match = re.search(pattern, query)
        if match is None:
            continue
        value = float(match.group(1))
        if is_percent and value > 1:
            value = value / 100.0
        return value
    return None


def _normalize_filters(payload: dict[str, Any]) -> QueryFilters | None:
    """Normalize raw parser output into validated query filters."""
    normalized: dict[str, Any] = {}
    for key, value in payload.items():
        if value in (None, "", []):
            continue
        if key in PERCENT_FIELDS and isinstance(value, (int, float)) and value > 1:
            normalized[key] = float(value) / 100.0
        else:
            normalized[key] = value

    if not normalized:
        return None

    try:
        return QueryFilters(**normalized)
    except Exception:
        return None


def _filter_scored_cells(
    filters: QueryFilters,
    effective_technology: str,
) -> list[str]:
    """Apply extracted filters to the loaded scored cell dataset."""
    store = get_store()
    if not store.is_loaded():
        return []

    df = store.get_all_cells()
    scenario = ScenarioRequest(technology=effective_technology)
    scored_df = score_all_cells(df, scenario)
    filtered_df = _apply_filters(scored_df, filters)
    return filtered_df["cell_id"].astype(str).tolist()


def _filter_counties(
    filters: QueryFilters,
    effective_technology: str,
) -> tuple[list[str], QuerySummaryStats | None]:
    """Apply extracted filters to the county dataset used by the frontend."""
    county_df = get_county_index()
    scenario = ScenarioRequest(technology=effective_technology)
    scored_df = score_all_cells(county_df, scenario)
    filtered_df = _apply_filters(scored_df, filters)

    # Apply sort_by if specified
    sort_col_map = {
        "lcoe": "lcoe_usd_per_mwh",
        "carbon_intensity": "carbon_g_per_kwh_mean",
        "renewable_percent": "renewable_percent",
        "price": "price_usd_per_mwh_mean",
        "composite_score": "composite_score",
    }
    sort_col = sort_col_map.get(filters.sort_by or "", "composite_score")
    ascending = sort_col != "renewable_percent"  # higher renewable is better
    if sort_col in filtered_df.columns:
        filtered_df = filtered_df.sort_values(sort_col, ascending=ascending)

    # Apply top_n limit
    if filters.top_n and len(filtered_df) > filters.top_n:
        filtered_df = filtered_df.head(filters.top_n)

    # Build summary statistics
    summary = None
    if not filtered_df.empty:
        best = filtered_df.iloc[0]
        summary = QuerySummaryStats(
            mean_lcoe=float(filtered_df["lcoe_usd_per_mwh"].mean()),
            min_lcoe=float(filtered_df["lcoe_usd_per_mwh"].min()),
            max_lcoe=float(filtered_df["lcoe_usd_per_mwh"].max()),
            mean_carbon_intensity=float(filtered_df["carbon_g_per_kwh_mean"].mean()),
            mean_renewable_percent=float(filtered_df["renewable_percent"].mean()) if "renewable_percent" in filtered_df else None,
            best_county_fips=str(best.get("fips", "")),
            best_county_name=str(best.get("county_name", "")) + ", " + str(best.get("state_abbr", "")),
            best_composite_score=float(best.get("composite_score", 0)),
        )

    return filtered_df["fips"].astype(str).tolist(), summary


def _apply_filters(df: pd.DataFrame, filters: QueryFilters) -> pd.DataFrame:
    """Filter a scored dataframe using normalized query filters."""
    filtered = df.copy()

    if filters.min_cf is not None:
        filtered = filtered[filtered["selected_cf"] >= filters.min_cf]
    if filters.min_lcoe is not None:
        filtered = filtered[filtered["lcoe_usd_per_mwh"] >= filters.min_lcoe]
    if filters.max_lcoe is not None:
        filtered = filtered[filtered["lcoe_usd_per_mwh"] <= filters.max_lcoe]
    if filters.min_carbon_intensity is not None:
        filtered = filtered[
            filtered["carbon_g_per_kwh_mean"] >= filters.min_carbon_intensity
        ]
    if filters.max_carbon_intensity is not None:
        filtered = filtered[
            filtered["carbon_g_per_kwh_mean"] <= filters.max_carbon_intensity
        ]
    if filters.min_price is not None:
        filtered = filtered[filtered["price_usd_per_mwh_mean"] >= filters.min_price]
    if filters.max_price is not None:
        filtered = filtered[filtered["price_usd_per_mwh_mean"] <= filters.max_price]
    if filters.min_renewable_percent is not None and "renewable_percent" in filtered:
        filtered = filtered[
            filtered["renewable_percent"] >= filters.min_renewable_percent
        ]
    if filters.max_transmission_km is not None and "nearest_transmission_km" in filtered:
        filtered = filtered[
            filtered["nearest_transmission_km"] <= filters.max_transmission_km
        ]
    if filters.region is not None:
        region_mask = filtered.apply(
            lambda row: _row_matches_region(row, filters.region or ""),
            axis=1,
        )
        filtered = filtered[region_mask]

    return filtered.sort_values("composite_score")


def _row_matches_region(row: pd.Series, region: str) -> bool:
    """Return True when a row matches a geographic filter."""
    normalized_region = _normalize_text(region)
    region_states = _resolve_region_states(region)

    state_abbr = str(row.get("state_abbr", "")).upper()
    state_name = _normalize_text(str(row.get("state_name", "")))
    county_name = _normalize_text(str(row.get("county_name", "")))
    grid_zone = _normalize_text(str(row.get("grid_zone_id", "")))
    price_hub = _normalize_text(str(row.get("price_hub_id", "")))
    cell_id = str(row.get("cell_id", ""))
    cell_prefix = ""
    if "_" in cell_id:
        cell_prefix = cell_id.split("_", 1)[0].upper()

    if state_abbr and state_abbr in region_states:
        return True
    if cell_prefix and cell_prefix in region_states:
        return True
    if state_name and normalized_region == state_name:
        return True
    if county_name and normalized_region in county_name:
        return True
    if state_abbr and normalized_region == state_abbr.lower():
        return True
    if cell_prefix and cell_prefix == normalized_region.upper():
        return True
    if normalized_region and normalized_region in grid_zone:
        return True
    if normalized_region and normalized_region in price_hub:
        return True

    return False


def _resolve_region_states(region: str) -> set[str]:
    """Resolve a region string to one or more state abbreviations."""
    lowered = region.lower().strip()
    if lowered in MACRO_REGIONS:
        return MACRO_REGIONS[lowered]
    if lowered in STATE_NAME_TO_ABBR:
        return {STATE_NAME_TO_ABBR[lowered]}
    if lowered.upper() in STATE_ABBR_TO_NAME:
        return {lowered.upper()}
    return set()


def _normalize_text(value: str) -> str:
    """Normalize free-text values for matching."""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _non_null_filter_values(filters: QueryFilters) -> list[Any]:
    """Return non-null filter values."""
    return [value for value in filters.model_dump().values() if value is not None]


@lru_cache(maxsize=1)
def get_county_index() -> pd.DataFrame:
    """Load the county metadata used by the frontend and attach deterministic metrics."""
    counties_path = (
        Path(__file__).resolve().parents[3]
        / "frontend"
        / "public"
        / "data"
        / "us-counties.json"
    )
    with counties_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    rows: list[dict[str, Any]] = []
    for feature in data.get("features", []):
        properties = feature.get("properties", {})
        fips = str(feature.get("id") or properties.get("id") or "").zfill(5)
        if not fips or fips == "00000":
            continue
        state_fips = str(properties.get("STATE") or fips[:2]).zfill(2)
        state_abbr = STATE_FIPS_TO_ABBR.get(state_fips, "")
        state_name = STATE_ABBR_TO_NAME.get(state_abbr, state_abbr)
        county_name = str(properties.get("NAME") or properties.get("name") or "Unknown")
        row = generate_county_data(fips)
        row.update(
            {
                "fips": fips,
                "county_name": county_name,
                "state_fips": state_fips,
                "state_abbr": state_abbr,
                "state_name": state_name,
            }
        )
        rows.append(row)

    return pd.DataFrame(rows)

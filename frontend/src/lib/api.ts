export const API_BASE_URL = "http://localhost:8000";

/** Normalize fetch errors into user-readable strings. */
function normalizeApiError(err: unknown, endpoint: string): Error {
  if (err instanceof TypeError && err.message.toLowerCase().includes("fetch")) {
    return new Error(
      `Backend unreachable — is the API server running at ${API_BASE_URL}? (${endpoint})`
    );
  }
  if (err instanceof Error) return err;
  return new Error(`Unexpected error calling ${endpoint}`);
}

export interface QueryFilters {
  technology: "solar" | "wind" | null;
  region: string | null;
  min_cf: number | null;
  min_lcoe: number | null;
  max_lcoe: number | null;
  min_carbon_intensity: number | null;
  max_carbon_intensity: number | null;
  min_price: number | null;
  max_price: number | null;
  min_renewable_percent: number | null;
  max_transmission_km: number | null;
}

export interface QueryResponse {
  parsed: boolean;
  message: string;
  filters: QueryFilters | null;
  effective_technology: "solar" | "wind" | null;
  matched_cell_ids: string[];
  matched_county_fips: string[];
  matched_cell_count: number;
  matched_county_count: number;
}

export async function fetchCountyMetrics(
  fips: string,
  params: {
    technology: string;
    capacity_mw: number;
    capex_usd_per_kw: number;
    carbon_price_usd_per_ton: number;
  }
) {
  const endpoint = `/county/${fips}`;
  try {
    const query = new URLSearchParams({
      technology: params.technology,
      capacity_mw: params.capacity_mw.toString(),
      capex_usd_per_kw: params.capex_usd_per_kw.toString(),
      carbon_price_usd_per_ton: params.carbon_price_usd_per_ton.toString(),
    });
    const response = await fetch(`${API_BASE_URL}${endpoint}?${query.toString()}`);
    if (!response.ok) throw new Error(`API error ${response.status}: ${response.statusText}`);
    return response.json();
  } catch (err) {
    throw normalizeApiError(err, endpoint);
  }
}

export async function submitCountyJob(
  fips: string,
  params: {
    technology: string;
    capacity_mw: number;
    capex_usd_per_kw: number;
    carbon_price_usd_per_ton: number;
  }
) {
  const endpoint = "/jobs/county";
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        fips_code: fips,
        scenario: {
          technology: params.technology,
          capacity_mw: params.capacity_mw,
          capex_usd_per_kw: params.capex_usd_per_kw,
          carbon_price_usd_per_ton: params.carbon_price_usd_per_ton,
        },
      }),
    });
    if (!response.ok) throw new Error(`API error ${response.status}: ${response.statusText}`);
    return response.json();
  } catch (err) {
    throw normalizeApiError(err, endpoint);
  }
}

export async function fetchJobStatus(jobId: string) {
  const endpoint = `/jobs/${jobId}`;
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`);
    if (!response.ok) throw new Error(`API error ${response.status}: ${response.statusText}`);
    return response.json();
  } catch (err) {
    throw normalizeApiError(err, endpoint);
  }
}

export async function fetchCountyMetricsViaJob(
  fips: string,
  params: {
    technology: string;
    capacity_mw: number;
    capex_usd_per_kw: number;
    carbon_price_usd_per_ton: number;
  }
) {
  const { job_id } = await submitCountyJob(fips, params);
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const status = await fetchJobStatus(job_id);
    if (status.status === "completed" && status.result) {
      return status.result;
    }
    if (status.status === "failed") {
      throw new Error(status.error || "County job failed");
    }
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  throw new Error("County job timed out");
}

export async function fetchCountyBrief(siteMetrics: unknown, scenario: unknown) {
  const endpoint = "/brief";
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ site: siteMetrics, scenario }),
    });
    if (!response.ok) throw new Error(`API error ${response.status}: ${response.statusText}`);
    return response.json();
  } catch (err) {
    throw normalizeApiError(err, endpoint);
  }
}

export async function submitNaturalLanguageQuery(query: string): Promise<QueryResponse> {
  const endpoint = "/query";
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    if (!response.ok) throw new Error(`API error ${response.status}: ${response.statusText}`);
    return response.json();
  } catch (err) {
    throw normalizeApiError(err, endpoint);
  }
}

export interface HeatmapCell {
  cell_id: string;
  lat: number;
  lon: number;
  score: number;
  raw_capacity_factor: number;
  raw_lcoe_usd_per_mwh: number;
  raw_revenue_usd_per_mwh: number;
  raw_carbon_value_usd_per_mwh: number;
}

export interface HeatmapResponse {
  technology: "solar" | "wind";
  score_min: number;
  score_max: number;
  score_unit: string;
  cell_count: number;
  cells: HeatmapCell[];
}

export async function fetchHeatmap(payload: {
  technology: "solar" | "wind";
  capacity_mw: number;
  capex_usd_per_kw: number;
  opex_usd_per_kw_year?: number;
  discount_rate?: number;
  project_lifetime_years?: number;
  carbon_price_usd_per_ton: number;
  cost_weight: number;
  revenue_weight: number;
  carbon_weight: number;
  weather_adjustment?: boolean;
  simulation_weather?: {
    temp_c?: number;
    cloud_cover_pct?: number;
    wind_speed_m_s?: number;
  } | null;
}): Promise<HeatmapResponse> {
  const endpoint = "/heatmap";
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        technology: payload.technology,
        capacity_mw: payload.capacity_mw,
        capex_usd_per_kw: payload.capex_usd_per_kw,
        opex_usd_per_kw_year: payload.opex_usd_per_kw_year ?? 35.0,
        discount_rate: payload.discount_rate ?? 0.06,
        project_lifetime_years: payload.project_lifetime_years ?? 25,
        carbon_price_usd_per_ton: payload.carbon_price_usd_per_ton,
        cost_weight: payload.cost_weight,
        revenue_weight: payload.revenue_weight,
        carbon_weight: payload.carbon_weight,
        weather_adjustment: payload.weather_adjustment ?? false,
        simulation_weather: payload.simulation_weather ?? null,
      }),
    });
    if (!response.ok) throw new Error(`API error ${response.status}: ${response.statusText}`);
    return response.json();
  } catch (err) {
    throw normalizeApiError(err, endpoint);
  }
}

export interface ForecastRow {
  state_code: string;
  state_name: string;
  electricity_maps_zone_id: string;
  timestamp: string;
  predicted_total_kwh_usage: number;
  avg_electricity_cost_cents_per_kwh: number | null;
  estimated_total_cost: number | null;

  // Weather-adjustment outputs (present when weather_adjustment enabled in backend proxy)
  weather_multiplier?: number;
  weather_adjusted_total_kwh_usage?: number;
  weather_adjusted_total_cost?: number | null;
  delta_kwh_usage?: number;
  delta_total_cost?: number | null;

  // Weather columns (present when available)
  temp_c?: number;
  cloud_cover_pct?: number;
  wind_speed_m_s?: number;
  heating_degree_hours?: number;
  cooling_degree_hours?: number;
}

export interface ForecastResponse {
  rows: ForecastRow[];
}

export async function fetchForecast(payload: {
  start: string;
  end?: string | null;
  hours?: number | null;
  states?: string[] | null;
  assumption_window_hours?: number;
  weather_adjustment?: boolean;
  state_locations?: Record<string, { lat: number; lon: number }> | null;
}): Promise<ForecastResponse> {
  const endpoint = "/forecast";
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        start: payload.start,
        end: payload.end ?? null,
        hours: payload.hours ?? null,
        states: payload.states ?? null,
        assumption_window_hours: payload.assumption_window_hours ?? 24 * 30,
        weather_adjustment: payload.weather_adjustment ?? false,
        state_locations: payload.state_locations ?? null,
      }),
    });
    if (!response.ok) throw new Error(`API error ${response.status}: ${response.statusText}`);
    return response.json();
  } catch (err) {
    throw normalizeApiError(err, endpoint);
  }
}

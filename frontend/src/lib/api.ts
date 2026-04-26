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

export const API_BASE_URL = "http://localhost:8000";

export async function fetchCountyMetrics(
  fips: string,
  params: {
    technology: string;
    capacity_mw: number;
    capex_usd_per_kw: number;
    carbon_price_usd_per_ton: number;
  }
) {
  const query = new URLSearchParams({
    technology: params.technology,
    capacity_mw: params.capacity_mw.toString(),
    capex_usd_per_kw: params.capex_usd_per_kw.toString(),
    carbon_price_usd_per_ton: params.carbon_price_usd_per_ton.toString(),
  });
  
  const response = await fetch(`${API_BASE_URL}/county/${fips}?${query.toString()}`);
  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }
  return response.json();
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
  const response = await fetch(`${API_BASE_URL}/jobs/county`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
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
  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchJobStatus(jobId: string) {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`);
  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }
  return response.json();
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

export async function fetchCountyBrief(siteMetrics: any, scenario: any) {
  const response = await fetch(`${API_BASE_URL}/brief`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ site: siteMetrics, scenario }),
  });
  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }
  return response.json();
}

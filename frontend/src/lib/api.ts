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

// ── Grid Cell Type ──────────────────────────────────────
export interface GridCell {
  id: string;
  lat: number;
  lon: number;
  costScore: number;       // 0-100, lower = better (cheaper)
  carbonIntensity: number; // gCO₂eq/kWh
  capacityFactor: number;  // 0-1
  lcoe: number;            // $/MWh
  revenue: number;         // $/MWh
  avgPrice: number;        // $/MWh wholesale
  nearestTransmissionKm: number;
  region: string;
  zone: string;
}

// ── Time Series Types ──────────────────────────────────
export interface TimeSeriesPoint {
  hour: number;
  timestamp: string;
  carbonIntensity: number;
  solar: number;
  wind: number;
  hydro: number;
  nuclear: number;
  gas: number;
  coal: number;
  load: number;
  price: number;
  netFlow: number;
}

export interface InstalledCapacity {
  source: string;
  capacity: number;  // GW
  color: string;
}

export interface ElectricityFlow {
  region: string;
  imported: number;   // GW
  exported: number;   // GW
  color: string;
}

// ── Site Assessment ────────────────────────────────────
export interface SiteAssessment {
  coordinates: { lat: number; lon: number };
  region: string;
  zone: string;
  capacityFactor: number;
  lcoe: number;
  revenue: number;
  carbonDisplacement: number; // tCO₂/MWh
  nearestTransmissionKm: number;
  generationProfile: { hour: number; generation: number; price: number }[];
  lcoeBreakdown: { category: string; value: number; color: string }[];
  carbonOverlay: { hour: number; gridIntensity: number; displaced: number }[];
  aiSummary: string;
}

// ── Helper: seeded random ──────────────────────────────
function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

/**
 * Diurnal price multiplier for grid cells — same logic as zones.ts diurnalFactors
 * but kept local to avoid cross-importing the full zones module.
 */
function gridDiurnalPriceMultiplier(hour: number, techType: "solar" | "wind"): number {
  const h = ((hour % 24) + 24) % 24;
  if (techType === "solar") {
    const solarGen = Math.max(0, Math.sin(((h - 6) * Math.PI) / 12));
    return 1 + 0.35 * (1 - solarGen) - 0.15 * solarGen;
  }
  const windBoost = 0.5 + 0.5 * Math.cos(((h - 14) * Math.PI) / 12);
  const loadPressure = 0.4 + 0.3 * Math.sin(((h - 8) * Math.PI) / 10);
  return 1 + 0.2 * loadPressure - 0.12 * windBoost;
}

function gridDiurnalCarbonMultiplier(hour: number, techType: "solar" | "wind"): number {
  const h = ((hour % 24) + 24) % 24;
  if (techType === "solar") {
    const solarGen = Math.max(0, Math.sin(((h - 6) * Math.PI) / 12));
    return 1 + 0.3 * (1 - solarGen);
  }
  const windBoost = 0.5 + 0.5 * Math.cos(((h - 14) * Math.PI) / 12);
  const loadPressure = 0.4 + 0.3 * Math.sin(((h - 8) * Math.PI) / 10);
  return 1 + 0.2 * loadPressure - 0.1 * windBoost;
}

// ── Generate Grid Cells (US focused) ───────────────────
export function generateGridCells(
  techType: "solar" | "wind" = "solar",
  carbonPrice: number = 50,
  capex: number = 1000,
  timeHour: number = 12,
  weightLcoe: number = 1,
  weightRevenue: number = 1,
  weightCarbon: number = 1,
): GridCell[] {
  const cells: GridCell[] = [];
  const rand = seededRandom(42);

  // Roughly covering CONUS
  for (let lat = 25; lat <= 49; lat += 0.8) {
    for (let lon = -125; lon <= -67; lon += 1.0) {
      const r = rand();

      // Solar: best in Southwest. Wind: best in Great Plains
      let baseCF: number;
      if (techType === "solar") {
        // Higher in south/southwest
        const latFactor = Math.max(0, 1 - (lat - 30) / 25);
        const lonFactor = lon > -110 && lon < -95 ? 0.85 : lon < -110 ? 0.95 : 0.7;
        baseCF = 0.12 + latFactor * 0.18 * lonFactor + r * 0.06;
      } else {
        // Wind: best in central plains corridor
        const plainsFactor = Math.exp(-Math.pow((lon + 100) / 12, 2)) * 1.2;
        const latBoost = lat > 35 && lat < 48 ? 0.08 : 0;
        baseCF = 0.15 + plainsFactor * 0.2 + latBoost + r * 0.06;
      }
      baseCF = Math.min(0.45, Math.max(0.08, baseCF));

      // LCOE = (CAPEX * CRF + OPEX) / (CF * 8760)
      const crf = 0.08; // capital recovery factor
      const opex = techType === "solar" ? 15 : 25; // $/kW-yr
      const lcoe = ((capex * crf + opex) / (baseCF * 8760)) * 1000;

      // Regional price variation
      const basePrice = 30 + rand() * 40;

      // Carbon intensity by region (approximate)
      const carbonBase = lon < -105 ? 280 : lon < -90 ? 420 : 380;
      const carbonIntensity = carbonBase + rand() * 120 - 60;

      // Apply hour-of-day modulation to price and carbon (makes the surface animate)
      const priceMult = gridDiurnalPriceMultiplier(timeHour, techType);
      const carbonMult = gridDiurnalCarbonMultiplier(timeHour, techType);
      const hourPrice = basePrice * priceMult;
      const hourCarbon = carbonIntensity * carbonMult;

      const revenue = baseCF * 8760 * hourPrice / 1000;
      const carbonValue = baseCF * 8760 * hourCarbon / 1e6 * carbonPrice;

      // Composite cost score: lower = better (weights applied)
      const costScore = Math.max(0, Math.min(100,
        weightLcoe * (lcoe / 80 * 40)
        - weightRevenue * (revenue / 300 * 20)
        - weightCarbon * (carbonValue / 50 * 15)
        + rand() * 25
      ));

      const regions = [
        { name: "CAISO", zone: "US-CAL-CISO", lonMin: -125, lonMax: -114, latMin: 32, latMax: 42 },
        { name: "ERCOT", zone: "US-TEX-ERCO", lonMin: -106, lonMax: -93, latMin: 26, latMax: 37 },
        { name: "SPP", zone: "US-CENT-SPP", lonMin: -105, lonMax: -90, latMin: 33, latMax: 49 },
        { name: "MISO", zone: "US-MIDW-MISO", lonMin: -95, lonMax: -83, latMin: 29, latMax: 49 },
        { name: "PJM", zone: "US-MIDA-PJM", lonMin: -83, lonMax: -74, latMin: 36, latMax: 42 },
        { name: "NYISO", zone: "US-NY-NYIS", lonMin: -80, lonMax: -71, latMin: 40, latMax: 45 },
        { name: "ISO-NE", zone: "US-NE-ISNE", lonMin: -74, lonMax: -67, latMin: 41, latMax: 48 },
      ];

      const region = regions.find(
        r => lon >= r.lonMin && lon <= r.lonMax && lat >= r.latMin && lat <= r.latMax
      );

      cells.push({
        id: `${lat.toFixed(1)}_${lon.toFixed(1)}`,
        lat,
        lon,
        costScore,
        carbonIntensity: Math.round(hourCarbon),
        capacityFactor: baseCF,
        lcoe,
        revenue,
        avgPrice: Math.round(hourPrice),
        nearestTransmissionKm: 5 + rand() * 80,
        region: region?.name ?? "Other",
        zone: region?.zone ?? "US-OTHER",
      });
    }
  }

  return cells;
}

// ── Generate Time Series (24h for left sidebar) ────────
export function generateTimeSeries(): TimeSeriesPoint[] {
  const rand = seededRandom(123);
  const points: TimeSeriesPoint[] = [];

  for (let h = 0; h < 24; h++) {
    const solarCurve = Math.max(0, Math.sin((h - 6) * Math.PI / 12)) * (0.8 + rand() * 0.2);
    const windCurve = 0.3 + 0.15 * Math.sin(h * Math.PI / 6) + rand() * 0.15;

    points.push({
      hour: h,
      timestamp: `2026-04-25T${h.toString().padStart(2, "0")}:00:00Z`,
      carbonIntensity: 200 + 250 * (1 - solarCurve * 0.7) + rand() * 50,
      solar: solarCurve * 18.5,  // GW
      wind: windCurve * 12.2,
      hydro: 2.8 + rand() * 0.5,
      nuclear: 9.1 + rand() * 0.2,
      gas: 8 + (1 - solarCurve) * 15 + rand() * 3,
      coal: 2 + (1 - solarCurve) * 4 + rand() * 1.5,
      load: 35 + solarCurve * 8 + rand() * 5,
      price: 20 + (1 - solarCurve) * 40 + rand() * 15,
      netFlow: -2 + rand() * 4,
    });
  }

  return points;
}

// ── Installed Capacity ─────────────────────────────────
export const installedCapacity: InstalledCapacity[] = [
  { source: "Solar", capacity: 28.4, color: "#f59e0b" },
  { source: "Wind", capacity: 15.2, color: "#06b6d4" },
  { source: "Nuclear", capacity: 9.3, color: "#8b5cf6" },
  { source: "Hydro", capacity: 7.1, color: "#3b82f6" },
  { source: "Gas", capacity: 42.8, color: "#6b7280" },
  { source: "Coal", capacity: 8.2, color: "#374151" },
  { source: "Battery", capacity: 5.6, color: "#10b981" },
  { source: "Geothermal", capacity: 1.2, color: "#ef4444" },
];

// ── Electricity Flows ──────────────────────────────────
export const electricityFlows: ElectricityFlow[] = [
  { region: "MX", imported: 0.3, exported: 0.1, color: "#ef4444" },
  { region: "US-NW-PACW", imported: 1.2, exported: 0.8, color: "#3b82f6" },
  { region: "US-SW-AZPS", imported: 0.9, exported: 1.4, color: "#10b981" },
  { region: "US-SW-SRP", imported: 0.4, exported: 0.2, color: "#f59e0b" },
  { region: "US-NV-NEVP", imported: 0.7, exported: 0.3, color: "#8b5cf6" },
];

// ── Generate Site Assessment ───────────────────────────
export function generateSiteAssessment(cell: GridCell): SiteAssessment {
  const rand = seededRandom(Math.round(cell.lat * 100 + cell.lon * 10));

  const generationProfile = Array.from({ length: 24 }, (_, h) => {
    const solarShape = Math.max(0, Math.sin((h - 6) * Math.PI / 12));
    const windShape = 0.4 + 0.2 * Math.sin(h * Math.PI / 8);
    const gen = cell.capacityFactor * (cell.zone.includes("CAL") ? solarShape : windShape) * 100;
    return {
      hour: h,
      generation: gen + rand() * 5,
      price: 20 + (1 - solarShape) * 40 + rand() * 10,
    };
  });

  const lcoeBreakdown = [
    { category: "CAPEX", value: cell.lcoe * 0.55, color: "#3b82f6" },
    { category: "OPEX", value: cell.lcoe * 0.18, color: "#06b6d4" },
    { category: "Financing", value: cell.lcoe * 0.15, color: "#8b5cf6" },
    { category: "Grid", value: cell.lcoe * 0.07, color: "#f59e0b" },
    { category: "Other", value: cell.lcoe * 0.05, color: "#6b7280" },
  ];

  const carbonOverlay = Array.from({ length: 24 }, (_, h) => {
    const solarShape = Math.max(0, Math.sin((h - 6) * Math.PI / 12));
    return {
      hour: h,
      gridIntensity: cell.carbonIntensity * (1 + (1 - solarShape) * 0.3) + rand() * 30,
      displaced: cell.capacityFactor * solarShape * cell.carbonIntensity / 1000 + rand() * 0.05,
    };
  });

  const cfPct = (cell.capacityFactor * 100).toFixed(1);
  const lcoeFmt = cell.lcoe.toFixed(1);
  const carbonDisp = (cell.capacityFactor * cell.carbonIntensity / 1000).toFixed(2);

  const aiSummary = `Site Assessment: This location in ${cell.region} (${cell.zone}) offers a ${cell.region.includes("CAL") || cell.region.includes("ERCOT") ? "solar" : "wind"} capacity factor of ${cfPct}%, yielding an estimated LCOE of $${lcoeFmt}/MWh — ${cell.lcoe < 35 ? "significantly below" : cell.lcoe < 50 ? "near" : "above"} the national median. Wholesale prices at the nearest hub average $${cell.avgPrice.toFixed(0)}/MWh during peak generation hours, creating ${cell.avgPrice > cell.lcoe ? "positive" : "negative"} margin. Grid carbon intensity here is ${cell.carbonIntensity.toFixed(0)} gCO₂/kWh, meaning each MWh of generation displaces approximately ${carbonDisp} tCO₂. Nearest transmission infrastructure is ${cell.nearestTransmissionKm.toFixed(0)} km away. ${cell.costScore < 30 ? "This is a high-potential site with excellent economics and grid value." : cell.costScore < 60 ? "This site has moderate potential — economics depend on CAPEX assumptions and PPA structure." : "Challenging economics at this location — consider alternative sites or technology types."}`;

  return {
    coordinates: { lat: cell.lat, lon: cell.lon },
    region: cell.region,
    zone: cell.zone,
    capacityFactor: cell.capacityFactor,
    lcoe: cell.lcoe,
    revenue: cell.revenue,
    carbonDisplacement: parseFloat(carbonDisp),
    nearestTransmissionKm: cell.nearestTransmissionKm,
    generationProfile,
    lcoeBreakdown,
    carbonOverlay,
    aiSummary,
  };
}

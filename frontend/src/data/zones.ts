import { STATE_DATA } from "./stateData";

export type TechType = "solar" | "wind";

// ── Zone Types ─────────────────────────────────────────
export interface ZoneData {
  id: string;          // County FIPS code (e.g. '06037')
  name: string;        // County name, e.g., 'Los Angeles'
  state: string;       // State abbreviation, e.g., 'CA'
  carbonIntensity: number;   // gCO₂eq/kWh
  renewablePercent: number;
  carbonFreePercent: number;
  price: number;             // $/MWh
  lcoe: number;              // $/MWh (static, unscored)
  load: number;              // GW
  generation: Record<string, number>; // source → GW
  solarCF: number;           // capacity factor 0-1
  windCF: number;            // capacity factor 0-1
}

// ── Carbon Intensity → Color (Discrete Palette) ──────────
export function carbonToColor(ci: number): string {
  if (ci < 100) return "#10b981"; // Emerald
  if (ci < 200) return "#84cc16"; // Lime
  if (ci < 300) return "#eab308"; // Yellow
  if (ci < 400) return "#f59e0b"; // Amber
  if (ci < 500) return "#ea580c"; // Orange
  if (ci < 650) return "#dc2626"; // Red
  if (ci < 800) return "#991b1b"; // Dark Red
  return "#450a0a"; // Extremely Dark Red/Brown
}

// ── Cost Score → Color (green=cheap, red=expensive) ──────
// normalizedScore: 0 = cheapest (green), 1 = most expensive (red)
export function scoreToColor(t: number): string {
  const clamped = Math.max(0, Math.min(1, t));
  if (clamped < 0.33) {
    const s = clamped / 0.33;
    return `rgb(${Math.round(34 + s * 211)},${Math.round(197 - s * 39)},${Math.round(94 - s * 83)})`;
  } else if (clamped < 0.66) {
    const s = (clamped - 0.33) / 0.33;
    return `rgb(${Math.round(245 - s * 6)},${Math.round(158 - s * 90)},${Math.round(11 + s * 57)})`;
  } else {
    const s = (clamped - 0.66) / 0.34;
    return `rgb(${Math.round(239 - s * 20)},${Math.round(68 - s * 30)},${Math.round(68 - s * 10)})`;
  }
}

// ── Scoring Engine (mirrors backend engine/scoring.py) ───

function computeCRF(discountRate = 0.06, lifetimeYears = 25): number {
  if (discountRate === 0) return 1 / lifetimeYears;
  return discountRate / (1 - Math.pow(1 + discountRate, -lifetimeYears));
}

/** LCOE in $/MWh: (CAPEX * CRF + OPEX) / (CF * 8760) * 1000 */
export function computeLCOE(cf: number, capex: number, techType: TechType = "solar"): number {
  if (cf <= 0) return 9999;
  const opex = techType === "solar" ? 15 : 25; // $/kW/year
  const crf = computeCRF();
  const annualCostPerKw = capex * crf + opex;
  const annualGenPerKw = cf * 8760;
  return (annualCostPerKw / annualGenPerKw) * 1000; // $/MWh
}

/**
 * Composite cost score (lower = better site).
 *   Score = LCOE - Revenue - CarbonValue
 * Matches the backend formula exactly.
 */
export function computeCompositeCostScore(
  county: ZoneData,
  techType: TechType,
  capex: number,
  carbonPrice: number,
): number {
  const cf = techType === "solar" ? county.solarCF : county.windCF;
  const lcoe = computeLCOE(cf, capex, techType);
  const revenue = county.price; // $/MWh (wholesale)
  const carbonValue = (county.carbonIntensity / 1000) * carbonPrice; // tons/MWh * $/ton
  return lcoe - revenue - carbonValue;
}

// ── FIPS to State Abbreviation Map ─────────────────────
export const fipsToState: Record<string, string> = {
  "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA",
  "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
  "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN",
  "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
  "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
  "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
  "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
  "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
  "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
  "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY"
};

// ── Helpers ────────────────────────────────────────────
function seededRandom(seed: number): () => number {
  // Hash seed to break linear correlation of contiguous FIPS codes
  let s = (seed ^ 0x5deece66d) & 0x7fffffff;
  if (s === 0) s = 1;
  for (let i = 0; i < 5; i++) {
    s = (s * 16807) % 2147483647;
  }
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

export function generateCountyData(fips: string, name: string, stateFips: string): ZoneData {
  const state = fipsToState[stateFips] || "US";
  const seed = parseInt(fips, 10) || name.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0);
  const rand = seededRandom(seed);

  const base = STATE_DATA[state] || { price: 100.0, solar: 5.0, wind: 5.0, hydro: 5.0, fossil: 85.0 };

  const ciBase = base.fossil * 8;
  const carbonIntensity = Math.max(10, ciBase + (rand() * (ciBase * 0.8) - (ciBase * 0.4)));

  const stateRenewable = base.solar + base.wind + base.hydro;
  const renewablePercent = Math.min(95, Math.max(5, stateRenewable + (rand() * 30 - 15)));
  const carbonFreePercent = Math.min(100, Math.max(renewablePercent, (100 - base.fossil) + (rand() * 10 - 5)));

  const statePrice = base.price * 10;
  const price = Math.max(10, statePrice + (rand() * (statePrice * 0.4) - (statePrice * 0.2)));

  // Solar & wind capacity factors — mirrors backend county_store.py exactly
  const solarCF = Math.max(0.1, Math.min(0.35, 0.15 + (base.solar / 100 * 0.5) + (rand() * 0.1 - 0.05)));
  const windCF = Math.max(0.1, Math.min(0.55, 0.2 + (base.wind / 100 * 0.5) + (rand() * 0.1 - 0.05)));

  // Static LCOE (for display-only, not scoring)
  const lcoe = Math.max(15, 60 + (rand() * 80 - 40));

  const totalGen = 2 + rand() * 10;

  return {
    id: fips,
    name,
    state,
    carbonIntensity: Math.round(carbonIntensity),
    renewablePercent: Math.round(renewablePercent),
    carbonFreePercent: Math.round(carbonFreePercent),
    price: Math.round(price),
    lcoe: Math.round(lcoe),
    load: Math.round(1 + rand() * 15 * 10) / 10,
    generation: {
      solar: (base.solar / 100) * totalGen,
      wind: (base.wind / 100) * totalGen,
      hydro: (base.hydro / 100) * totalGen,
      nuclear: (Math.max(0, 100 - base.fossil - stateRenewable) / 100) * totalGen,
      gas: (base.fossil / 200) * totalGen,
      coal: (base.fossil / 200) * totalGen,
    },
    solarCF,
    windCF,
  };
}

// Map cache for lazily generated counties (county base data is stable)
const countiesCache: Record<string, ZoneData> = {};

export function getCounty(fips: string, name = "Unknown", stateFips = "00"): ZoneData {
  if (!countiesCache[fips]) {
    countiesCache[fips] = generateCountyData(fips, name, stateFips);
  }
  return countiesCache[fips];
}

// ── Scenario-Aware GeoJSON Enhancement ────────────────

export interface EnhanceOptions {
  techType?: TechType;
  capex?: number;
  carbonPrice?: number;
  colorMode?: "cost" | "carbon";
}

/**
 * Enhance a raw US counties GeoJSON with:
 * - Composite cost scores based on current scenario (technology, capex, carbon price)
 * - Color derived from the scenario-aware composite score
 * - Tooltip-ready properties (CF, LCOE, carbon, price)
 */
export function enhanceCountyGeoJSON(
  geojson: GeoJSON.FeatureCollection,
  options: EnhanceOptions = {},
): GeoJSON.FeatureCollection {
  const {
    techType = "solar",
    capex = 1200,
    carbonPrice = 50,
    colorMode = "cost",
  } = options;

  // First pass: compute raw scores for all counties to normalize
  const counties: ZoneData[] = [];
  const fipsArr: string[] = [];

  for (const f of geojson.features) {
    const fips = (f.id as string) || f.properties?.id || "00000";
    const name = f.properties?.NAME || f.properties?.name || "Unknown County";
    const stateFips = f.properties?.STATE || fips.substring(0, 2);
    const county = getCounty(fips, name, stateFips);
    counties.push(county);
    fipsArr.push(fips);
  }

  let scores: number[];
  if (colorMode === "cost") {
    scores = counties.map(c => computeCompositeCostScore(c, techType, capex, carbonPrice));
    const minScore = Math.min(...scores);
    const maxScore = Math.max(...scores);
    const range = maxScore - minScore || 1;

    const features = geojson.features.map((f, i) => {
      const county = counties[i];
      const score = scores[i];
      const normalizedScore = (score - minScore) / range;
      const cf = techType === "solar" ? county.solarCF : county.windCF;
      const lcoe = computeLCOE(cf, capex, techType);

      return {
        ...f,
        id: fipsArr[i],
        properties: {
          ...f.properties,
          id: county.id,
          name: county.name,
          state: county.state,
          shortName: `${county.name}, ${county.state}`,
          color: scoreToColor(normalizedScore),
          carbonIntensity: county.carbonIntensity,
          lcoe: Math.round(lcoe),
          renewablePercent: county.renewablePercent,
          price: county.price,
          capacityFactor: Math.round(cf * 1000) / 1000,
          costScore: Math.round(score * 10) / 10,
        },
      };
    });

    return { ...geojson, features };
  }

  // Carbon mode (original behavior)
  const features = geojson.features.map((f, i) => {
    const county = counties[i];
    return {
      ...f,
      id: fipsArr[i],
      properties: {
        ...f.properties,
        id: county.id,
        name: county.name,
        state: county.state,
        shortName: `${county.name}, ${county.state}`,
        color: carbonToColor(county.carbonIntensity),
        carbonIntensity: county.carbonIntensity,
        lcoe: county.lcoe,
        renewablePercent: county.renewablePercent,
        price: county.price,
        capacityFactor: Math.round(county.solarCF * 1000) / 1000,
        costScore: 0,
      },
    };
  });

  return { ...geojson, features };
}

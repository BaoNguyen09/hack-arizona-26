import { STATE_DATA } from "./stateData";

// ── Zone Types ─────────────────────────────────────────
export interface ZoneData {
  id: string;          // County FIPS code (e.g. '06037')
  name: string;        // County name, e.g., 'Los Angeles'
  state: string;       // State abbreviation, e.g., 'CA'
  carbonIntensity: number;   // gCO₂eq/kWh
  renewablePercent: number;
  carbonFreePercent: number;
  price: number;             // $/MWh
  lcoe: number;              // $/MWh (Levelized Cost of Energy)
  load: number;              // GW
  generation: Record<string, number>; // source → GW
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
// Helper: seeded random to keep data consistent
function seededRandom(seed: number): () => number {
  // Hash the seed slightly to break linear correlation of contiguous FIPS codes
  let s = (seed ^ 0x5deece66d) & 0x7fffffff;
  if (s === 0) s = 1;
  
  // Advance the generator a few times to thoroughly mix
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
  
  // Use FIPS as a stable numerical seed
  const seed = parseInt(fips, 10) || name.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0);
  const rand = seededRandom(seed);
  
  // Regional energy characteristics (state level)
  // Fetch state baseline from the provided CSV data
  const base = STATE_DATA[state] || { price: 100.0, solar: 5.0, wind: 5.0, hydro: 5.0, fossil: 85.0 };
  
  // Real world carbon logic: heavily influenced by fossil %
  // 100% fossil ≈ 800 gCO₂eq/kWh, 0% = 0
  const ciBase = base.fossil * 8;
  
  // Massive localized county variance so adjacent counties look very different
  // rand() gives 0 to 1.
  const carbonIntensity = Math.max(10, ciBase + (rand() * (ciBase * 0.8) - (ciBase * 0.4)));
  
  const lcoe = Math.max(15, 60 + (rand() * 80 - 40));
  
  // Calculate renewable and carbon free metrics
  const stateRenewable = base.solar + base.wind + base.hydro;
  const renewablePercent = Math.min(95, Math.max(5, stateRenewable + (rand() * 30 - 15)));
  const carbonFreePercent = Math.min(100, Math.max(renewablePercent, (100 - base.fossil) + (rand() * 10 - 5)));
  
  const statePrice = base.price * 10; // convert cents/kWh to $/MWh
  const price = Math.max(10, statePrice + (rand() * (statePrice * 0.4) - (statePrice * 0.2)));
  
  // Generation breakdown roughly matches the state mix
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
    load: Math.round(1 + rand() * 15 * 10) / 10, // counties have smaller load
    generation: {
      solar: (base.solar / 100) * totalGen,
      wind: (base.wind / 100) * totalGen,
      hydro: (base.hydro / 100) * totalGen,
      nuclear: (Math.max(0, 100 - base.fossil - stateRenewable) / 100) * totalGen,
      gas: (base.fossil / 200) * totalGen,
      coal: (base.fossil / 200) * totalGen,
    }
  };
}

// Map cache for lazily generated counties
const countiesCache: Record<string, ZoneData> = {};

export function getCounty(fips: string, name: string = "Unknown", stateFips: string = "00"): ZoneData {
  if (!countiesCache[fips]) {
    countiesCache[fips] = generateCountyData(fips, name, stateFips);
  }
  return countiesCache[fips];
}

// ── Pre-process GeoJSON ────────────────────────────────
export function enhanceCountyGeoJSON(geojson: GeoJSON.FeatureCollection): GeoJSON.FeatureCollection {
  const features = geojson.features.map(f => {
    // The FIPS code is either the feature ID or embedded in properties.
    const fips = (f.id as string) || f.properties?.id || "00000";
    const name = f.properties?.NAME || f.properties?.name || "Unknown County";
    const stateFips = f.properties?.STATE || fips.substring(0, 2);
    
    const countyData = getCounty(fips, name, stateFips);
    
    return {
      ...f,
      id: fips,
      properties: {
        ...f.properties,
        id: countyData.id,
        name: countyData.name,
        state: countyData.state,
        shortName: `${countyData.name}, ${countyData.state}`,
        color: carbonToColor(countyData.carbonIntensity), // Discrete carbon color
        carbonIntensity: countyData.carbonIntensity,
        lcoe: countyData.lcoe,
        renewablePercent: countyData.renewablePercent,
        price: countyData.price
      }
    };
  });
  return { ...geojson, features };
}

import { create } from "zustand";
import { SiteAssessment } from "../data/mockData";
import { type ZoneData, type TechType } from "../data/zones";
import {
  fetchCountyBrief,
  fetchCountyMetricsViaJob,
  fetchForecast,
  fetchHeatmap,
  submitNaturalLanguageQuery,
  type ForecastRow,
  type HeatmapCell,
  type QueryFilters,
} from "../lib/api";

export type { TechType };

interface LumenState {
  techType: TechType;
  carbonPrice: number;
  capex: number;
  timeHour: number;
  isLive: boolean;

  weightLcoe: number;
  weightRevenue: number;
  weightCarbon: number;

  siteAssessment: SiteAssessment | null;
  rightPanelOpen: boolean;

  selectedCountyId: string | null;
  selectedCounty: ZoneData | null;
  matchedCountyFips: string[];
  matchedCellIds: string[];
  queryFilters: QueryFilters | null;
  queryMessage: string | null;
  activeQueryText: string;
  queryPending: boolean;

  countyFetchStatus: "idle" | "loading" | "success" | "error";
  countyFetchError: string | null;

  pinnedCountyIds: string[];
  pinnedCounties: Record<string, ZoneData>;

  leftSidebarOpen: boolean;
  sidebarTab: "overview" | "carbon" | "mix" | "price";

  showTransmission: boolean;
  showHeatmap: boolean;
  showZones: boolean;

  weatherSimulationEnabled: boolean;
  simulationWeather: {
    temp_c: number;
    cloud_cover_pct: number;
    wind_speed_m_s: number;
  };

  forecastRows: ForecastRow[];
  forecastStatus: "idle" | "loading" | "success" | "error";
  forecastError: string | null;

  countyMetricsByFips: Record<string, HeatmapCell>;
  countyMetricsStatus: "idle" | "loading" | "success" | "error";
  countyMetricsError: string | null;

  setTechType: (t: TechType) => void;
  setCarbonPrice: (p: number) => void;
  setCapex: (c: number) => void;
  setTimeHour: (h: number) => void;
  setIsLive: (live: boolean) => void;
  setWeights: (w: { weightLcoe?: number; weightRevenue?: number; weightCarbon?: number }) => void;
  fetchCountyData: (fips: string | null, name?: string, stateFips?: string) => Promise<void>;
  retryCountyFetch: () => Promise<void>;
  pinCounty: (fips: string, data: ZoneData) => void;
  unpinCounty: (fips: string) => void;
  clearPinnedCounties: () => void;
  runNaturalLanguageQuery: (query: string) => Promise<void>;
  clearQueryResults: () => void;
  toggleLeftSidebar: () => void;
  setSidebarTab: (tab: LumenState["sidebarTab"]) => void;
  toggleTransmission: () => void;
  toggleHeatmap: () => void;
  toggleZones: () => void;

  setWeatherSimulationEnabled: (enabled: boolean) => void;
  setSimulationWeather: (patch: Partial<LumenState["simulationWeather"]>) => void;
  refreshForecast: () => Promise<void>;

  recalculate: () => void;
  refreshCountyMetrics: () => Promise<void>;
}

export const useLumenStore = create<LumenState>((set, get) => ({
  techType: "solar",
  carbonPrice: 50,
  capex: 1000,
  timeHour: 14,
  isLive: true,

  weightLcoe: 1.0,
  weightRevenue: 1.0,
  weightCarbon: 1.0,

  weatherSimulationEnabled: false,
  simulationWeather: {
    temp_c: 18,
    cloud_cover_pct: 20,
    wind_speed_m_s: 7,
  },

  forecastRows: [],
  forecastStatus: "idle",
  forecastError: null,

  siteAssessment: null,
  rightPanelOpen: false,

  selectedCountyId: null,
  selectedCounty: null,
  matchedCountyFips: [],
  matchedCellIds: [],
  queryFilters: null,
  queryMessage: null,
  activeQueryText: "",
  queryPending: false,

  countyFetchStatus: "idle",
  countyFetchError: null,

  pinnedCountyIds: [],
  pinnedCounties: {},

  leftSidebarOpen: true,
  sidebarTab: "overview",

  showTransmission: false,
  showHeatmap: true,
  showZones: true,

  countyMetricsByFips: {},
  countyMetricsStatus: "idle",
  countyMetricsError: null,

  setTechType: (t) => {
    set({ techType: t });
    get().recalculate();
  },
  setCarbonPrice: (p) => {
    set({ carbonPrice: p });
    get().recalculate();
  },
  setCapex: (c) => {
    set({ capex: c });
    get().recalculate();
  },
  setTimeHour: (h) => {
    set({ timeHour: h });
    const { weatherSimulationEnabled, forecastRows } = get();
    if (weatherSimulationEnabled && forecastRows.length > 0) {
      const hourIdx = ((Math.floor(h) % 24) + 24) % 24;
      const row = forecastRows[hourIdx];
      if (row) {
        const patch: any = {};
        if (typeof row.temp_c === "number") patch.temp_c = row.temp_c;
        if (typeof row.cloud_cover_pct === "number") patch.cloud_cover_pct = row.cloud_cover_pct;
        if (typeof row.wind_speed_m_s === "number") patch.wind_speed_m_s = row.wind_speed_m_s;
        if (Object.keys(patch).length > 0) {
          set((s) => ({ simulationWeather: { ...s.simulationWeather, ...patch } }));
        }
      }
    }
    get().recalculate();
  },
  setIsLive: (live) => {
    set({ isLive: live });
    if (!live) {
      const { weatherSimulationEnabled, forecastRows } = get();
      if (!weatherSimulationEnabled) set({ weatherSimulationEnabled: true });
      if (!forecastRows || forecastRows.length === 0) void get().refreshForecast();
    }
  },
  setWeights: (w) => {
    set(w);
    get().recalculate();
  },

  fetchCountyData: async (fips, name, stateFips) => {
    if (!fips) {
      set({
        selectedCountyId: null,
        selectedCounty: null,
        siteAssessment: null,
        rightPanelOpen: false,
        countyFetchStatus: "idle",
        countyFetchError: null,
      });
      return;
    }

    set({
      selectedCountyId: fips,
      selectedCounty: null,
      siteAssessment: null,
      rightPanelOpen: true,
      countyFetchStatus: "loading",
      countyFetchError: null,
    });

    try {
      const { techType, capex, carbonPrice } = get();
      const data = await fetchCountyMetricsViaJob(fips, {
        technology: techType,
        capacity_mw: 50.0,
        capex_usd_per_kw: capex,
        carbon_price_usd_per_ton: carbonPrice,
      });

      const briefData = await fetchCountyBrief(data.site, data.scenario);
      const metrics = data.site;

      const assessment: SiteAssessment = {
        region: name || `County ${fips}`,
        zone: stateFips ? `Zone ${stateFips}` : metrics.grid_zone_id,
        coordinates: { lat: metrics.lat, lon: metrics.lon },
        aiSummary: briefData.text,
        capacityFactor: metrics.selected_cf_mean,
        lcoe: metrics.lcoe_usd_per_mwh,
        revenue: metrics.estimated_annual_revenue_usd_millions * 1000000,
        carbonDisplacement: metrics.annual_carbon_displacement_tons,
        nearestTransmissionKm: metrics.nearest_transmission_km || 12,
        generationProfile:
          metrics.generation_profile ||
          Array.from({ length: 24 }).map((_, i) => ({
            hour: i,
            generation: 0,
            price: metrics.avg_wholesale_price_usd_per_mwh,
          })),
        lcoeBreakdown: [
          { category: "CAPEX", value: metrics.lcoe_components.capex_share_usd_per_mwh || 20, color: "#3b82f6" },
          { category: "OPEX", value: metrics.lcoe_components.opex_share_usd_per_mwh || 5, color: "#06b6d4" },
          { category: "Transmission", value: 3.5, color: "#f59e0b" },
          { category: "Financing", value: 2.1, color: "#8b5cf6" },
        ],
        carbonOverlay:
          metrics.carbon_profile ||
          Array.from({ length: 24 }).map((_, i) => ({
            hour: i,
            gridIntensity: metrics.grid_carbon_intensity_g_per_kwh,
            displaced: metrics.grid_carbon_intensity_g_per_kwh / 1000,
          })),
      };

      const countyData = {
        id: fips,
        name: name || `County ${fips}`,
        state: stateFips || "",
        carbonIntensity: metrics.grid_carbon_intensity_g_per_kwh,
        renewablePercent: metrics.renewable_percent || 0,
        lcoe: metrics.lcoe_usd_per_mwh,
        load: metrics.load_gw || 0,
        generation: { solar: metrics.solar_cf_mean * 100, wind: metrics.wind_cf_mean * 100, gas: 40 },
        carbonFreePercent: (metrics.renewable_percent || 0) + 10,
        price: metrics.avg_wholesale_price_usd_per_mwh,
      };

      set({
        selectedCounty: countyData as any,
        siteAssessment: assessment,
        countyFetchStatus: "success",
        countyFetchError: null,
      });
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Unknown error fetching county data.";
      console.error("Failed to fetch county data:", error);
      set({ countyFetchStatus: "error", countyFetchError: msg });
    }
  },

  retryCountyFetch: async () => {
    const { selectedCountyId, fetchCountyData } = get();
    if (selectedCountyId) await fetchCountyData(selectedCountyId);
  },

  pinCounty: (fips, data) => {
    const { pinnedCountyIds, pinnedCounties } = get();
    if (pinnedCountyIds.includes(fips)) return;
    if (pinnedCountyIds.length >= 3) return;
    set({ pinnedCountyIds: [...pinnedCountyIds, fips], pinnedCounties: { ...pinnedCounties, [fips]: data } });
  },

  unpinCounty: (fips) => {
    const { pinnedCountyIds, pinnedCounties } = get();
    const next = { ...pinnedCounties };
    delete next[fips];
    set({ pinnedCountyIds: pinnedCountyIds.filter((id) => id !== fips), pinnedCounties: next });
  },

  clearPinnedCounties: () => set({ pinnedCountyIds: [], pinnedCounties: {} }),

  runNaturalLanguageQuery: async (query) => {
    const trimmed = query.trim();
    if (!trimmed) {
      set({
        activeQueryText: "",
        queryMessage: "Enter a query to filter counties.",
        queryFilters: null,
        matchedCountyFips: [],
        matchedCellIds: [],
        queryPending: false,
      });
      return;
    }

    set({ queryPending: true, activeQueryText: trimmed, queryMessage: null });
    try {
      const response = await submitNaturalLanguageQuery(trimmed);
      set((state) => ({
        queryPending: false,
        queryMessage: response.message,
        queryFilters: response.filters,
        matchedCountyFips: response.matched_county_fips,
        matchedCellIds: response.matched_cell_ids,
        showZones: response.parsed && response.matched_county_fips.length > 0 ? true : state.showZones,
      }));
    } catch (error) {
      console.error("Failed to run natural language query:", error);
      set({
        queryPending: false,
        queryMessage: "Query request failed. Try again.",
        queryFilters: null,
        matchedCountyFips: [],
        matchedCellIds: [],
      });
    }
  },

  clearQueryResults: () =>
    set({
      activeQueryText: "",
      queryMessage: null,
      queryFilters: null,
      matchedCountyFips: [],
      matchedCellIds: [],
      queryPending: false,
    }),

  toggleLeftSidebar: () => set((s) => ({ leftSidebarOpen: !s.leftSidebarOpen })),
  setSidebarTab: (tab) => set({ sidebarTab: tab }),
  toggleTransmission: () => set((s) => ({ showTransmission: !s.showTransmission })),
  toggleHeatmap: () => set((s) => ({ showHeatmap: !s.showHeatmap })),
  toggleZones: () => set((s) => ({ showZones: !s.showZones })),

  setWeatherSimulationEnabled: (enabled) => {
    set({ weatherSimulationEnabled: enabled });
    if (enabled) void get().refreshForecast();
    get().recalculate();
  },
  setSimulationWeather: (patch) => {
    set((s) => ({ simulationWeather: { ...s.simulationWeather, ...patch } }));
    get().recalculate();
  },
  refreshForecast: async () => {
    set({ forecastStatus: "loading", forecastError: null });
    try {
      const start = new Date();
      start.setUTCMinutes(0, 0, 0);
      const startIso = start.toISOString().replace(".000Z", "Z");
      const resp = await fetchForecast({
        start: startIso,
        hours: 24,
        states: ["TX"],
        weather_adjustment: true,
        state_locations: { TX: { lat: 31.5, lon: -99.3 } },
      });
      set({ forecastRows: resp.rows, forecastStatus: "success", forecastError: null });
    } catch (e) {
      set({ forecastStatus: "error", forecastError: e instanceof Error ? e.message : "Failed to fetch forecast" });
    }
  },

  recalculate: () => {
    void get().refreshCountyMetrics();
  },

  refreshCountyMetrics: async () => {
    const { techType, capex, carbonPrice, weightLcoe, weightRevenue, weightCarbon, weatherSimulationEnabled, simulationWeather } =
      get();
    set({ countyMetricsStatus: "loading", countyMetricsError: null });
    try {
      const resp = await fetchHeatmap({
        technology: techType,
        capacity_mw: 50.0,
        capex_usd_per_kw: capex,
        carbon_price_usd_per_ton: carbonPrice,
        cost_weight: weightLcoe,
        revenue_weight: weightRevenue,
        carbon_weight: weightCarbon,
        weather_adjustment: weatherSimulationEnabled,
        simulation_weather: weatherSimulationEnabled ? simulationWeather : null,
      });
      const byFips: Record<string, HeatmapCell> = {};
      for (const cell of resp.cells) {
        const id = cell.cell_id || "";
        if (id.startsWith("county_")) {
          const fips = id.replace("county_", "");
          byFips[fips] = { ...cell };
        }
      }
      set({ countyMetricsByFips: byFips, countyMetricsStatus: "success", countyMetricsError: null });
    } catch (e) {
      set({
        countyMetricsStatus: "error",
        countyMetricsError: e instanceof Error ? e.message : "Failed to fetch county metrics",
      });
    }
  },
}));

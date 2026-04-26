import { create } from "zustand";
import {
  GridCell,
  SiteAssessment,
  generateGridCells,
} from "../data/mockData";
import { type ZoneData, type TechType } from "../data/zones";
import {
  fetchCountyMetricsViaJob,
  fetchCountyBrief,
  submitNaturalLanguageQuery,
  type QueryFilters,
} from "../lib/api";

export type { TechType };

interface LumenState {
  // Scenario controls
  techType: TechType;
  carbonPrice: number;
  capex: number;
  timeHour: number;
  isLive: boolean;

  // Scoring weight sliders (0–1, should sum to 1 but are applied as raw multipliers)
  weightLcoe: number;
  weightRevenue: number;
  weightCarbon: number;

  // Grid data
  gridCells: GridCell[];

  // Selected site (grid cell mode)
  selectedCell: GridCell | null;
  siteAssessment: SiteAssessment | null;
  rightPanelOpen: boolean;

  // Selected zone/county
  selectedCountyId: string | null;
  selectedCounty: ZoneData | null;
  matchedCountyFips: string[];
  matchedCellIds: string[];
  queryFilters: QueryFilters | null;
  queryMessage: string | null;
  activeQueryText: string;
  queryPending: boolean;

  // County job fetch status
  countyFetchStatus: "idle" | "loading" | "success" | "error";
  countyFetchError: string | null;

  // Comparison mode — up to 3 pinned counties
  pinnedCountyIds: string[];
  pinnedCounties: Record<string, ZoneData>;

  // Left sidebar
  leftSidebarOpen: boolean;
  sidebarTab: "overview" | "carbon" | "mix" | "price";

  // Layer toggles
  showTransmission: boolean;
  showHeatmap: boolean;
  showZones: boolean;

  // Actions
  setTechType: (t: TechType) => void;
  setCarbonPrice: (p: number) => void;
  setCapex: (c: number) => void;
  setTimeHour: (h: number) => void;
  setIsLive: (live: boolean) => void;
  setWeights: (w: { weightLcoe?: number; weightRevenue?: number; weightCarbon?: number }) => void;
  selectCell: (cell: GridCell | null) => void;
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
  recalculate: () => void;
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

  gridCells: generateGridCells("solar", 50, 1000, 14, 1.0, 1.0, 1.0),

  selectedCell: null,
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
    get().recalculate();
  },
  setIsLive: (live) => set({ isLive: live }),
  setWeights: (w) => {
    set(w);
    get().recalculate();
  },

  selectCell: (cell) => {
    if (cell) {
      set({
        selectedCell: cell,
        rightPanelOpen: true,
        selectedCountyId: null,
        selectedCounty: null,
      });
    } else {
      set({
        selectedCell: null,
        siteAssessment: null,
        rightPanelOpen: false,
      });
    }
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

    // Open panel immediately with loading state
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

      // Map API response to the expected frontend SiteAssessment schema
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
          {
            category: "CAPEX",
            value: metrics.lcoe_components.capex_share_usd_per_mwh || 20,
            color: "#3b82f6",
          },
          {
            category: "OPEX",
            value: metrics.lcoe_components.opex_share_usd_per_mwh || 5,
            color: "#06b6d4",
          },
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

      // Also set selectedCounty with basic data so CountyPanelContent works
      const countyData = {
        id: fips,
        name: name || `County ${fips}`,
        state: stateFips || "",
        carbonIntensity: metrics.grid_carbon_intensity_g_per_kwh,
        renewablePercent: metrics.renewable_percent || 0,
        lcoe: metrics.lcoe_usd_per_mwh,
        load: metrics.load_gw || 0,
        generation: {
          solar: metrics.solar_cf_mean * 100,
          wind: metrics.wind_cf_mean * 100,
          gas: 40,
        },
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
      const msg =
        error instanceof Error ? error.message : "Unknown error fetching county data.";
      console.error("Failed to fetch county data:", error);
      set({
        countyFetchStatus: "error",
        countyFetchError: msg,
      });
    }
  },

  retryCountyFetch: async () => {
    const { selectedCountyId, fetchCountyData } = get();
    if (selectedCountyId) {
      await fetchCountyData(selectedCountyId);
    }
  },

  pinCounty: (fips, data) => {
    const { pinnedCountyIds, pinnedCounties } = get();
    if (pinnedCountyIds.includes(fips)) return; // already pinned
    if (pinnedCountyIds.length >= 3) return;     // max 3
    set({
      pinnedCountyIds: [...pinnedCountyIds, fips],
      pinnedCounties: { ...pinnedCounties, [fips]: data },
    });
  },

  unpinCounty: (fips) => {
    const { pinnedCountyIds, pinnedCounties } = get();
    const next = { ...pinnedCounties };
    delete next[fips];
    set({
      pinnedCountyIds: pinnedCountyIds.filter((id) => id !== fips),
      pinnedCounties: next,
    });
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

    set({
      queryPending: true,
      activeQueryText: trimmed,
      queryMessage: null,
    });

    try {
      const response = await submitNaturalLanguageQuery(trimmed);
      set((state) => ({
        queryPending: false,
        queryMessage: response.message,
        queryFilters: response.filters,
        matchedCountyFips: response.matched_county_fips,
        matchedCellIds: response.matched_cell_ids,
        showZones:
          response.parsed && response.matched_county_fips.length > 0
            ? true
            : state.showZones,
        showHeatmap:
          response.parsed && response.matched_county_fips.length > 0
            ? false
            : state.showHeatmap,
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

  toggleLeftSidebar: () =>
    set((s) => ({ leftSidebarOpen: !s.leftSidebarOpen })),
  setSidebarTab: (tab) => set({ sidebarTab: tab }),
  toggleTransmission: () =>
    set((s) => ({ showTransmission: !s.showTransmission })),
  toggleHeatmap: () => set((s) => ({ showHeatmap: !s.showHeatmap })),
  toggleZones: () => set((s) => ({ showZones: !s.showZones })),

  recalculate: () => {
    const { techType, carbonPrice, capex, timeHour, weightLcoe, weightRevenue, weightCarbon } = get();
    set({ gridCells: generateGridCells(techType, carbonPrice, capex, timeHour, weightLcoe, weightRevenue, weightCarbon) });
  },
}));

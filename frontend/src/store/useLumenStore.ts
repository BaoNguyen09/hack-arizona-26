import { create } from "zustand";
import {
  GridCell,
  SiteAssessment,
  generateGridCells,
} from "../data/mockData";
import { type ZoneData } from "../data/zones";
import { fetchCountyMetricsViaJob, fetchCountyBrief } from "../lib/api";

export type TechType = "solar" | "wind";

interface LumenState {
  // Scenario controls
  techType: TechType;
  carbonPrice: number;
  capex: number;
  timeHour: number;
  isLive: boolean;

  // Grid data
  gridCells: GridCell[];

  // Selected site (grid cell mode)
  selectedCell: GridCell | null;
  siteAssessment: SiteAssessment | null;
  rightPanelOpen: boolean;

  // Selected zone/county
  selectedCountyId: string | null;
  selectedCounty: ZoneData | null;

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
  selectCell: (cell: GridCell | null) => void;
  fetchCountyData: (fips: string | null, name?: string, stateFips?: string) => Promise<void>;
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

  gridCells: generateGridCells("solar", 50, 1000),

  selectedCell: null,
  siteAssessment: null,
  rightPanelOpen: false,

  selectedCountyId: null,
  selectedCounty: null,

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
  setTimeHour: (h) => set({ timeHour: h }),
  setIsLive: (live) => set({ isLive: live }),

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
      });
      return;
    }

    // Optimistically open panel and clear old data
    set({
      selectedCountyId: fips,
      selectedCounty: null,
      siteAssessment: null,
      rightPanelOpen: true,
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
      });
    } catch (error) {
      console.error("Failed to fetch county data:", error);
    }
  },

  toggleLeftSidebar: () =>
    set((s) => ({ leftSidebarOpen: !s.leftSidebarOpen })),
  setSidebarTab: (tab) => set({ sidebarTab: tab }),
  toggleTransmission: () =>
    set((s) => ({ showTransmission: !s.showTransmission })),
  toggleHeatmap: () => set((s) => ({ showHeatmap: !s.showHeatmap })),
  toggleZones: () => set((s) => ({ showZones: !s.showZones })),

  recalculate: () => {
    const { techType, carbonPrice, capex } = get();
    set({ gridCells: generateGridCells(techType, carbonPrice, capex) });
  },
}));

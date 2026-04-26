import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  Zap,
  Leaf,
  BarChart3,
  TrendingUp,
  DollarSign,
  ChevronLeft,
  Radio,
  Clock,
  Info,
  ExternalLink,
  SlidersHorizontal,
  Wind,
  Sun,
  Droplets,
  Flame,
  Atom,
} from "lucide-react";
import { useLumenStore } from "../store/useLumenStore";
import { AnimatedNumber } from "./AnimatedNumber";
import {
  generateTimeSeries,
  installedCapacity,
} from "../data/mockData";
import {
  CarbonIntensityChart,
  ElectricityMixChart,
  PriceChart,
  LoadChart,
  CapacityBar,
} from "./Charts";

const tabs = [
  { id: "overview" as const, label: "Overview", icon: Activity },
  { id: "carbon" as const, label: "Carbon", icon: Leaf },
  { id: "mix" as const, label: "Mix", icon: BarChart3 },
  { id: "price" as const, label: "Price", icon: DollarSign },
];

export function LeftSidebar() {
  const {
    leftSidebarOpen,
    toggleLeftSidebar,
    sidebarTab,
    setSidebarTab,
    isLive,
    setIsLive,
    timeHour,
    weightLcoe,
    weightRevenue,
    weightCarbon,
    setWeights,
  } = useLumenStore();

  const timeSeries = useMemo(() => generateTimeSeries(), []);

  // Current metrics from time series at selected hour
  const currentData = timeSeries[timeHour] || timeSeries[14];

  const carbonFree = useMemo(() => {
    const clean =
      currentData.solar +
      currentData.wind +
      currentData.nuclear +
      currentData.hydro;
    const total = clean + currentData.gas + currentData.coal;
    return Math.round((clean / total) * 100);
  }, [currentData]);

  const renewable = useMemo(() => {
    const ren =
      currentData.solar + currentData.wind + currentData.hydro;
    const total =
      ren + currentData.nuclear + currentData.gas + currentData.coal;
    return Math.round((ren / total) * 100);
  }, [currentData]);

  return (
    <>
      {/* ── Collapse button ────────────────────────── */}
      <AnimatePresence>
        {!leftSidebarOpen && (
          <motion.button
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            onClick={toggleLeftSidebar}
            className="fixed top-16 left-3 z-40 w-9 h-9 rounded-lg glass-panel flex items-center justify-center hover:bg-gray-700/40 transition-colors"
          >
            <BarChart3 className="w-4 h-4 text-white" />
          </motion.button>
        )}
      </AnimatePresence>

      {/* ── Sidebar Panel ──────────────────────────── */}
      <AnimatePresence>
        {leftSidebarOpen && (
          <motion.aside
            id="left-sidebar"
            initial={{ x: -380, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -380, opacity: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="fixed top-14 left-0 bottom-0 z-30 w-[360px] overflow-y-auto overflow-x-hidden"
            style={{
              background: "rgba(10, 10, 10, 0.85)",
              backdropFilter: "blur(24px)",
              WebkitBackdropFilter: "blur(24px)",
              borderRight: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            {/* ── Header ─────────────────────────────── */}
            <div className="sticky top-0 z-10 px-4 pt-4 pb-3" style={{ background: "inherit" }}>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-lg">🇺🇸</span>
                  <h2 className="text-sm font-semibold text-white">
                    CONUS Grid
                  </h2>
                </div>
                <button
                  onClick={toggleLeftSidebar}
                  className="w-7 h-7 rounded-md flex items-center justify-center hover:bg-gray-700/40 transition-colors"
                >
                  <ChevronLeft className="w-4 h-4 text-gray-400" />
                </button>
              </div>

              <div className="flex items-center gap-3 text-[11px] text-gray-400">
                <div className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  <span>Apr 25, 2026, {timeHour}:00 PM PDT</span>
                </div>
              </div>

              {/* Live / Forecast toggle */}
              <div className="flex items-center gap-1 mt-2 bg-gray-800/60 rounded-lg p-0.5 border border-gray-700/40 w-fit">
                <button
                  onClick={() => setIsLive(true)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${
                    isLive
                      ? "bg-white/10 text-white border border-white/20"
                      : "text-gray-500 hover:text-gray-400"
                  }`}
                >
                  <Radio className="w-3 h-3" />
                  Live
                </button>
                <button
                  onClick={() => setIsLive(false)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${
                    !isLive
                      ? "bg-white/10 text-white border border-white/20"
                      : "text-gray-500 hover:text-gray-400"
                  }`}
                >
                  <TrendingUp className="w-3 h-3" />
                  Forecast
                </button>
              </div>
            </div>

            {/* ── Carbon Intensity Gauge (Electricity Maps style) ─── */}
            <div className="px-4 pb-4">
              <CarbonGauge
                value={currentData.carbonIntensity}
                carbonFree={carbonFree}
                renewable={renewable}
              />

              {/* ── Power Origin Breakdown (Electricity Maps style) ─── */}
              <div className="mt-4">
                <PowerOriginBreakdown currentData={currentData} />
              </div>

              {/* ── Tab navigation ───────────────────── */}
              <div className="flex gap-0.5 mb-4 mt-5 bg-gray-800/40 rounded-lg p-0.5 border border-gray-700/30">
                {tabs.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setSidebarTab(tab.id)}
                    className={`flex-1 flex items-center justify-center gap-1 py-1.5 rounded-md text-[10px] font-medium transition-all ${
                      sidebarTab === tab.id
                        ? "bg-white/10 text-white border border-white/20"
                        : "text-gray-500 hover:text-gray-400"
                    }`}
                  >
                    <tab.icon className="w-3 h-3" />
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* ── Tab Content ───────────────────────── */}
              <AnimatePresence mode="wait">
                <motion.div
                  key={sidebarTab}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2 }}
                >
                  {sidebarTab === "overview" && (
                    <OverviewTab
                      timeSeries={timeSeries}
                      currentData={currentData}
                    />
                  )}
                  {sidebarTab === "carbon" && (
                    <CarbonTab timeSeries={timeSeries} />
                  )}
                  {sidebarTab === "mix" && (
                    <MixTab timeSeries={timeSeries} />
                  )}
                  {sidebarTab === "price" && (
                    <PriceTab timeSeries={timeSeries} />
                  )}
                </motion.div>
              </AnimatePresence>
            </div>

            {/* ── Scoring Weights ─────────────────────── */}
            <div className="px-4 py-3 border-t border-gray-800/60 space-y-2.5">
              <div className="flex items-center gap-1.5 mb-1">
                <SlidersHorizontal className="w-3 h-3 text-gray-500" />
                <span className="text-[10px] font-medium text-gray-400 uppercase tracking-wider">
                  Scoring Weights
                </span>
              </div>

              <WeightSlider
                label="LCOE"
                value={weightLcoe}
                onChange={(v) => setWeights({ weightLcoe: v })}
                color="#3b82f6"
              />
              <WeightSlider
                label="Revenue"
                value={weightRevenue}
                onChange={(v) => setWeights({ weightRevenue: v })}
                color="#10b981"
              />
              <WeightSlider
                label="Carbon"
                value={weightCarbon}
                onChange={(v) => setWeights({ weightCarbon: v })}
                color="#f59e0b"
              />
            </div>

            {/* ── Footer ─────────────────────────────── */}
            <div className="px-4 py-3 border-t border-gray-800/60">
              <button className="flex items-center gap-1.5 text-[11px] text-gray-500 hover:text-gray-400 transition-colors">
                <Info className="w-3 h-3" />
                Methodologies & data sources
                <ExternalLink className="w-3 h-3" />
              </button>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  );
}

// ── Carbon Intensity Gauge (Electricity Maps-inspired) ──────
function CarbonGauge({
  value,
  carbonFree,
  renewable,
}: {
  value: number;
  carbonFree: number;
  renewable: number;
}) {
  const gaugeColor =
    value < 100 ? "#10b981" :
    value < 200 ? "#84cc16" :
    value < 350 ? "#f59e0b" :
    value < 500 ? "#ea580c" : "#ef4444";

  // Gauge arc (0-600 range mapped to 0-180 degrees)
  const angle = Math.min(180, (value / 600) * 180);
  const radius = 60;
  const cx = 70;
  const cy = 65;

  const startAngle = Math.PI;
  const endAngle = startAngle - (angle * Math.PI) / 180;
  const x1 = cx + radius * Math.cos(startAngle);
  const y1 = cy + radius * Math.sin(startAngle);
  const x2 = cx + radius * Math.cos(endAngle);
  const y2 = cy + radius * Math.sin(endAngle);
  const largeArc = angle > 180 ? 1 : 0;

  const trackPath = `M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`;
  const valuePath = angle > 0
    ? `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`
    : "";

  return (
    <div className="flex items-start gap-4">
      {/* Gauge */}
      <div className="relative flex-shrink-0">
        <svg width="140" height="80" viewBox="0 0 140 80">
          {/* Track */}
          <path
            d={trackPath}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth="10"
            strokeLinecap="round"
          />
          {/* Value */}
          {valuePath && (
            <motion.path
              d={valuePath}
              fill="none"
              stroke={gaugeColor}
              strokeWidth="10"
              strokeLinecap="round"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 1, ease: "easeOut" }}
              style={{ filter: `drop-shadow(0 0 8px ${gaugeColor}50)` }}
            />
          )}
        </svg>
        <div className="absolute inset-x-0 bottom-0 text-center">
          <span className="text-2xl font-bold tabular-nums" style={{ color: gaugeColor }}>
            <AnimatedNumber value={value} decimals={0} />
          </span>
          <p className="text-[9px] text-gray-500 -mt-0.5">gCO₂eq/kWh</p>
        </div>
      </div>

      {/* Key metrics */}
      <div className="flex-1 space-y-2.5 pt-1">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-gray-500 uppercase tracking-wide">Low-carbon</span>
          <div className="flex items-center gap-1.5">
            <div className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                style={{ background: "#10b981" }}
                initial={{ width: 0 }}
                animate={{ width: `${carbonFree}%` }}
                transition={{ duration: 0.8, ease: "easeOut" }}
              />
            </div>
            <span className="text-[11px] font-semibold text-white tabular-nums w-8 text-right">
              <AnimatedNumber value={carbonFree} decimals={0} suffix="%" />
            </span>
          </div>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-gray-500 uppercase tracking-wide">Renewable</span>
          <div className="flex items-center gap-1.5">
            <div className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                style={{ background: "#22d3ee" }}
                initial={{ width: 0 }}
                animate={{ width: `${renewable}%` }}
                transition={{ duration: 0.8, ease: "easeOut", delay: 0.1 }}
              />
            </div>
            <span className="text-[11px] font-semibold text-white tabular-nums w-8 text-right">
              <AnimatedNumber value={renewable} decimals={0} suffix="%" />
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Power Origin Breakdown (Electricity Maps-inspired) ──────
const SOURCE_CONFIG = [
  { key: "solar", label: "Solar", icon: Sun, color: "#f59e0b" },
  { key: "wind", label: "Wind", icon: Wind, color: "#06b6d4" },
  { key: "hydro", label: "Hydro", icon: Droplets, color: "#3b82f6" },
  { key: "nuclear", label: "Nuclear", icon: Atom, color: "#8b5cf6" },
  { key: "gas", label: "Natural Gas", icon: Flame, color: "#6b7280" },
  { key: "coal", label: "Coal", icon: Flame, color: "#374151" },
] as const;

function PowerOriginBreakdown({ currentData }: { currentData: any }) {
  const sources = SOURCE_CONFIG.map((s) => ({
    ...s,
    value: currentData[s.key] as number,
  }));
  const total = sources.reduce((sum, s) => sum + s.value, 0);

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2.5">
        <Zap className="w-3 h-3 text-gray-500" />
        <h3 className="text-[10px] font-medium text-gray-400 uppercase tracking-wider">
          Power Origin
        </h3>
        <span className="ml-auto text-[10px] text-gray-500 tabular-nums">
          {total.toFixed(1)} GW
        </span>
      </div>

      {/* Stacked bar */}
      <div className="flex h-3 rounded-full overflow-hidden mb-3">
        {sources.map((s) => (
          <motion.div
            key={s.key}
            className="relative group"
            style={{ background: s.color }}
            initial={{ width: 0 }}
            animate={{ width: `${(s.value / total) * 100}%` }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          />
        ))}
      </div>

      {/* Source rows */}
      <div className="space-y-1">
        {sources.map((s) => {
          const pct = total > 0 ? (s.value / total) * 100 : 0;
          const Icon = s.icon;
          return (
            <div
              key={s.key}
              className="flex items-center gap-2 py-1 px-2 rounded-md hover:bg-white/[0.03] transition-colors group"
            >
              <div
                className="w-5 h-5 rounded flex items-center justify-center flex-shrink-0"
                style={{ background: `${s.color}20` }}
              >
                <Icon className="w-3 h-3" style={{ color: s.color }} />
              </div>
              <span className="text-[11px] text-gray-300 flex-1">{s.label}</span>
              <div className="flex items-center gap-3">
                {/* Mini bar */}
                <div className="w-14 h-1 bg-gray-800 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ background: s.color }}
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.5, ease: "easeOut" }}
                  />
                </div>
                <span className="text-[10px] text-gray-400 tabular-nums w-10 text-right">
                  {pct.toFixed(1)}%
                </span>
                <span className="text-[10px] text-gray-500 tabular-nums w-12 text-right">
                  {s.value.toFixed(1)} GW
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Overview Tab ───────────────────────────────────────
function OverviewTab({
  timeSeries,
  currentData,
}: {
  timeSeries: any[];
  currentData: any;
}) {
  return (
    <div className="space-y-4">
      {/* Installed Capacity */}
      <Section title="Installed capacity (GW)" icon={Zap}>
        <CapacityBar data={installedCapacity} />
      </Section>

      {/* Carbon over time (mini) */}
      <Section title="Carbon intensity (gCO₂eq/kWh)" icon={Leaf}>
        <CarbonIntensityChart data={timeSeries} />
      </Section>
    </div>
  );
}

// ── Carbon Tab ─────────────────────────────────────────
function CarbonTab({ timeSeries }: { timeSeries: any[] }) {
  return (
    <div className="space-y-4">
      <Section title="Carbon intensity over time" icon={Leaf}>
        <CarbonIntensityChart data={timeSeries} />
      </Section>
      <div className="text-xs text-gray-500 leading-relaxed">
        Carbon intensity represents the average CO₂ emissions per kWh of
        electricity consumed. Lower values indicate cleaner grid power.
        Values update based on real-time generation mix.
      </div>
    </div>
  );
}

// ── Mix Tab ────────────────────────────────────────────
function MixTab({ timeSeries }: { timeSeries: any[] }) {
  return (
    <div className="space-y-4">
      <Section title="Electricity mix (GW)" icon={BarChart3}>
        <ElectricityMixChart data={timeSeries} />
      </Section>
      <Section title="Installed capacity (GW)" icon={Zap}>
        <CapacityBar data={installedCapacity} />
      </Section>
    </div>
  );
}

// ── Price Tab ──────────────────────────────────────────
function PriceTab({ timeSeries }: { timeSeries: any[] }) {
  return (
    <div className="space-y-4">
      <Section title="Wholesale price ($/MWh)" icon={DollarSign}>
        <PriceChart data={timeSeries} />
      </Section>
      <Section title="System load (GW)" icon={TrendingUp}>
        <LoadChart data={timeSeries} />
      </Section>
    </div>
  );
}

// ── Section Wrapper ────────────────────────────────────
function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        <Icon className="w-3 h-3 text-gray-500" />
        <h3 className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">
          {title}
        </h3>
      </div>
      {children}
    </div>
  );
}

// ── Weight Slider ──────────────────────────────────────
function WeightSlider({
  label,
  value,
  onChange,
  color,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  color: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-gray-400 w-14 flex-shrink-0">{label}</span>
      <input
        type="range"
        min={0}
        max={2}
        step={0.1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="flex-1"
        style={{ accentColor: color }}
      />
      <span
        className="text-[10px] font-medium tabular-nums w-6 text-right flex-shrink-0"
        style={{ color }}
      >
        {value.toFixed(1)}
      </span>
    </div>
  );
}

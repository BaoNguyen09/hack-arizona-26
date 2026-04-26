import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  Zap,
  Leaf,
  BarChart3,
  ArrowRightLeft,
  TrendingUp,
  DollarSign,
  ChevronLeft,
  Radio,
  Clock,
  Info,
  ExternalLink,
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
                    Lumen Analytics
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

            {/* ── Big Metrics ────────────────────────── */}
            <div className="px-4 pb-4">
              <div className="grid grid-cols-3 gap-3 mb-4">
                <MetricRing
                  label="Carbon Intensity"
                  value={currentData.carbonIntensity}
                  unit="gCO₂eq/kWh"
                  color={
                    currentData.carbonIntensity < 200
                      ? "#10b981"
                      : currentData.carbonIntensity < 350
                      ? "#f59e0b"
                      : "#ef4444"
                  }
                  progress={Math.min(100, (currentData.carbonIntensity / 600) * 100)}
                />
                <MetricRing
                  label="Carbon-free"
                  value={carbonFree}
                  unit="%"
                  color="#a1a1aa"
                  progress={carbonFree}
                />
                <MetricRing
                  label="Renewable"
                  value={renewable}
                  unit="%"
                  color="#fff"
                  progress={renewable}
                />
              </div>

              {/* ── Tab navigation ───────────────────── */}
              <div className="flex gap-0.5 mb-4 bg-gray-800/40 rounded-lg p-0.5 border border-gray-700/30">
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

// ── Metric Ring Component ──────────────────────────────
function MetricRing({
  label,
  value,
  unit,
  color,
  progress,
}: {
  label: string;
  value: number;
  unit: string;
  color: string;
  progress: number;
}) {
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (progress / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative w-16 h-16">
        <svg className="w-16 h-16 -rotate-90" viewBox="0 0 64 64">
          <circle
            cx="32"
            cy="32"
            r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.05)"
            strokeWidth="4"
          />
          <motion.circle
            cx="32"
            cy="32"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1, ease: "easeOut" }}
            style={{ filter: `drop-shadow(0 0 6px ${color}40)` }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-sm font-bold text-white" style={{ color }}>
            <AnimatedNumber value={value} decimals={0} />
          </span>
        </div>
      </div>
      <span className="text-[9px] text-gray-400 text-center leading-tight">
        {unit}
      </span>
      <span className="text-[9px] text-gray-500 text-center leading-tight">
        {label}
      </span>
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

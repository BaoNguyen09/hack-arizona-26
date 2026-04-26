import { useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  MapPin,
  Sparkles,
  Zap,
  DollarSign,
  Leaf,
  Radio,
  TrendingUp,
  BarChart3,
} from "lucide-react";
import { useLumenStore } from "../store/useLumenStore";
import { AnimatedNumber } from "./AnimatedNumber";
import {
  GenerationPriceChart,
  LCOEBreakdownChart,
  CarbonOverlayChart,
  ElectricityMixChart,
  CapacityBar,
} from "./Charts";
import { carbonToColor } from "../data/zones";
import { generateTimeSeries } from "../data/mockData";

export function RightPanel() {
  const {
    rightPanelOpen,
    siteAssessment,
    selectedCounty,
    selectCell,
    fetchCountyData,
    techType,
  } = useLumenStore();

  const closePanel = () => {
    selectCell(null);
    fetchCountyData(null);
  };

  return (
    <AnimatePresence>
      {rightPanelOpen && (selectedCounty || siteAssessment) && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-30 pointer-events-none"
            style={{
              background: "linear-gradient(to left, rgba(0,0,0,0.3) 0%, transparent 50%)",
            }}
          />

          <motion.aside
            id="right-panel"
            initial={{ x: 420, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 420, opacity: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="fixed top-14 right-0 bottom-0 z-40 w-[400px] overflow-y-auto"
            style={{
              background: "rgba(10, 10, 10, 0.85)",
              backdropFilter: "blur(24px)",
              WebkitBackdropFilter: "blur(24px)",
              borderLeft: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            {selectedCounty ? (
              <CountyPanelContent county={selectedCounty} onClose={closePanel} />
            ) : siteAssessment ? (
              <SitePanelContent
                assessment={siteAssessment}
                techType={techType}
                onClose={closePanel}
              />
            ) : null}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

// ── County Panel ───────────────────────────────────────
function CountyPanelContent({
  county,
  onClose,
}: {
  county: NonNullable<ReturnType<typeof useLumenStore.getState>["selectedCounty"]>;
  onClose: () => void;
}) {
  const ciColor = carbonToColor(county.carbonIntensity);
  const timeSeries = useMemo(() => generateTimeSeries(), []);

  // Build capacity bar data from county generation
  const capacityData = useMemo(() => {
    const colors: Record<string, string> = {
      solar: "#f59e0b", wind: "#06b6d4", hydro: "#3b82f6",
      nuclear: "#8b5cf6", gas: "#6b7280", coal: "#374151",
    };
    return Object.entries(county.generation).map(([source, capacity]) => ({
      source: source.charAt(0).toUpperCase() + source.slice(1),
      capacity: capacity as number,
      color: colors[source] || "#6b7280",
    }));
  }, [county]);

  const totalGen = Object.values(county.generation).reduce((s, v) => s + (v as number), 0);

  return (
    <>
      {/* Header */}
      <div className="sticky top-0 z-10 px-5 pt-4 pb-3" style={{ background: "inherit" }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div
              className="w-3 h-3 rounded-full flex-shrink-0"
              style={{ background: ciColor, boxShadow: `0 0 8px ${ciColor}40` }}
            />
            <div>
              <h2 className="text-sm font-semibold text-white">{county.name} County, {county.state}</h2>
              <p className="text-[11px] text-gray-500">FIPS: {county.id} • Regional Metrics</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-md flex items-center justify-center hover:bg-gray-700/40 transition-colors"
          >
            <X className="w-4 h-4 text-gray-400" />
          </button>
        </div>
      </div>

      <div className="px-5 pb-6 space-y-5">
        {/* Key Metrics */}
        <div className="grid grid-cols-2 gap-3">
          <MetricCard icon={Leaf} label="Carbon Intensity" color={ciColor}>
            <AnimatedNumber value={county.carbonIntensity} decimals={0} />
            <span className="text-[10px] text-gray-500 ml-1">gCO₂/kWh</span>
          </MetricCard>
          <MetricCard icon={Zap} label="Renewable" color="#a1a1aa">
            <AnimatedNumber value={county.renewablePercent} decimals={0} suffix="%" />
          </MetricCard>
          <MetricCard icon={DollarSign} label="LCOE" color="#fff">
            $<AnimatedNumber value={county.lcoe} decimals={0} />
            <span className="text-[10px] text-gray-500 ml-1">/MWh</span>
          </MetricCard>
          <MetricCard icon={TrendingUp} label="Load" color="#d4d4d8">
            <AnimatedNumber value={county.load} decimals={1} />
            <span className="text-[10px] text-gray-500 ml-1">GW</span>
          </MetricCard>
        </div>

        {/* Generation Mix */}
        <Section title="Local Generation Mix" icon={BarChart3}>
          <CapacityBar data={capacityData} />
          <p className="text-[10px] text-gray-500 mt-2">
            Total: {totalGen.toFixed(1)} GW •
            Carbon-free: {county.carbonFreePercent}%
          </p>
        </Section>

        {/* Electricity Mix Chart */}
        <Section title="Local Energy Mix (24h)" icon={BarChart3}>
          <ElectricityMixChart data={timeSeries} />
        </Section>
      </div>
    </>
  );
}

// ── Site Panel (Grid Cell Mode) ────────────────────────
function SitePanelContent({
  assessment,
  techType,
  onClose,
}: {
  assessment: NonNullable<ReturnType<typeof useLumenStore.getState>["siteAssessment"]>;
  techType: string;
  onClose: () => void;
}) {
  return (
    <>
      <div className="sticky top-0 z-10 px-5 pt-4 pb-3" style={{ background: "inherit" }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MapPin className="w-4 h-4 text-white" />
            <div>
              <h2 className="text-sm font-semibold text-white">
                {assessment.region} — Site Analysis
              </h2>
              <p className="text-[11px] text-gray-500">
                {assessment.coordinates.lat.toFixed(2)}°N,{" "}
                {Math.abs(assessment.coordinates.lon).toFixed(2)}°W • {assessment.zone}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-md flex items-center justify-center hover:bg-gray-700/40 transition-colors"
          >
            <X className="w-4 h-4 text-gray-400" />
          </button>
        </div>
        <div className="flex items-center gap-2 mt-2">
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-white/10 text-white border border-white/20">
            <Sparkles className="w-3 h-3" />
            AI Site Assessment
          </span>
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-white/5 text-gray-300 border border-white/10">
            {techType === "solar" ? "☀️ Solar PV" : "💨 Wind"}
          </span>
        </div>
      </div>

      <div className="px-5 pb-6 space-y-5">
        {/* Metrics */}
        <div className="grid grid-cols-2 gap-3">
          <MetricCard
            icon={Zap}
            label="Capacity Factor"
            color={assessment.capacityFactor > 0.25 ? "#fff" : "#a1a1aa"}
          >
            <AnimatedNumber value={assessment.capacityFactor * 100} decimals={1} suffix="%" />
          </MetricCard>
          <MetricCard
            icon={DollarSign}
            label="LCOE"
            color={assessment.lcoe < 35 ? "#fff" : "#a1a1aa"}
          >
            $<AnimatedNumber value={assessment.lcoe} decimals={1} />
            <span className="text-[10px] text-gray-500 ml-1">/MWh</span>
          </MetricCard>
          <MetricCard icon={TrendingUp} label="Revenue" color="#d4d4d8">
            $<AnimatedNumber value={assessment.revenue} decimals={0} />
          </MetricCard>
          <MetricCard icon={Leaf} label="Carbon Displaced" color="#a1a1aa">
            <AnimatedNumber value={assessment.carbonDisplacement} decimals={2} />
            <span className="text-[10px] text-gray-500 ml-1">tCO₂</span>
          </MetricCard>
        </div>

        {/* Transmission */}
        <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-gray-800/40 border border-gray-700/30">
          <Radio className="w-4 h-4 text-gray-400 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-[11px] text-gray-400">Nearest Transmission</p>
            <p className="text-sm text-white font-medium">
              <AnimatedNumber value={assessment.nearestTransmissionKm} decimals={0} /> km
            </p>
          </div>
        </div>

        <Section title="Generation vs Price" icon={BarChart3}>
          <GenerationPriceChart data={assessment.generationProfile} />
        </Section>

        <Section title="LCOE Breakdown" icon={DollarSign}>
          <LCOEBreakdownChart data={assessment.lcoeBreakdown} />
        </Section>

        <Section title="Carbon Intensity Overlay" icon={Leaf}>
          <CarbonOverlayChart data={assessment.carbonOverlay} />
        </Section>

        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <Sparkles className="w-3.5 h-3.5 text-white" />
            <h3 className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">
              AI Assessment
            </h3>
          </div>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="relative px-4 py-3 rounded-xl text-[12px] leading-relaxed text-gray-300 bg-gray-800/40 border border-gray-700/30"
          >
            <div
              className="absolute top-0 left-0 w-full h-px"
              style={{
                background: "linear-gradient(to right, transparent, rgba(255,255,255,0.1), transparent)",
              }}
            />
            {assessment.aiSummary}
          </motion.div>
        </div>
      </div>
    </>
  );
}

// ── Shared components ──────────────────────────────────
function MetricCard({
  icon: Icon,
  label,
  color,
  children,
}: {
  icon: React.ElementType;
  label: string;
  color: string;
  children: React.ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="px-3 py-3 rounded-xl bg-gray-800/40 border border-gray-700/30 hover:border-gray-600/40 transition-colors"
    >
      <div className="flex items-center gap-1.5 mb-1.5">
        <Icon className="w-3 h-3" style={{ color }} />
        <span className="text-[10px] text-gray-500 uppercase tracking-wide">{label}</span>
      </div>
      <div className="text-xl font-bold" style={{ color }}>
        {children}
      </div>
    </motion.div>
  );
}

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

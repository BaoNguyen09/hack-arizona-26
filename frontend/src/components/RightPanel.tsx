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
  AlertCircle,
  RefreshCw,
  Pin,
  PinOff,
  Download,
} from "lucide-react";
import { useLumenStore } from "../store/useLumenStore";
import { exportAssessmentPdf } from "../lib/exportPdf";
import { AnimatedNumber } from "./AnimatedNumber";
import {
  GenerationPriceChart,
  LCOEBreakdownChart,
  CarbonOverlayChart,
  ElectricityMixChart,
  CapacityBar,
} from "./Charts";
import { carbonToColor } from "../data/zones";
import { generateFallbackConusSeries } from "../lib/timeseries";

export function RightPanel() {
  const {
    rightPanelOpen,
    siteAssessment,
    selectedCounty,
    selectedCountyId,
    fetchCountyData,
    retryCountyFetch,
    techType,
    countyFetchStatus,
    countyFetchError,
  } = useLumenStore();

  const closePanel = () => {
    fetchCountyData(null);
  };

  // Panel is open when rightPanelOpen is set — this includes loading + error states
  const isOpen = rightPanelOpen && (selectedCountyId !== null || siteAssessment !== null || selectedCounty !== null);

  return (
    <AnimatePresence>
      {isOpen && (
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
            {countyFetchStatus === "loading" ? (
              <RightPanelSkeleton onClose={closePanel} />
            ) : countyFetchStatus === "error" ? (
              <RightPanelError
                message={countyFetchError ?? "Something went wrong."}
                onClose={closePanel}
                onRetry={retryCountyFetch}
              />
            ) : selectedCounty ? (
              <CountyPanelContent
                county={selectedCounty}
                assessment={siteAssessment}
                techType={techType}
                onClose={closePanel}
              />
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

// ── Loading Skeleton ───────────────────────────────────
function RightPanelSkeleton({ onClose }: { onClose: () => void }) {
  return (
    <>
      <div className="sticky top-0 z-10 px-5 pt-4 pb-3" style={{ background: "rgba(10,10,10,0.85)" }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="skeleton w-3 h-3 rounded-full" />
            <div className="space-y-1.5">
              <div className="skeleton h-3.5 w-36 rounded" />
              <div className="skeleton h-2.5 w-24 rounded" />
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
          <div className="skeleton h-5 w-24 rounded-full" />
          <div className="skeleton h-5 w-16 rounded-full" />
        </div>
      </div>

      <div className="px-5 pb-6 space-y-5">
        {/* Metric cards */}
        <div className="grid grid-cols-2 gap-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="px-3 py-3 rounded-xl bg-gray-800/40 border border-gray-700/30 space-y-2">
              <div className="skeleton h-2.5 w-20 rounded" />
              <div className="skeleton h-6 w-16 rounded" />
            </div>
          ))}
        </div>
        {/* Chart placeholders */}
        <div className="space-y-1">
          <div className="skeleton h-2.5 w-28 rounded" />
          <div className="skeleton h-24 w-full rounded-lg" />
        </div>
        <div className="space-y-1">
          <div className="skeleton h-2.5 w-32 rounded" />
          <div className="skeleton h-32 w-full rounded-lg" />
        </div>
        <div className="space-y-1">
          <div className="skeleton h-2.5 w-24 rounded" />
          <div className="skeleton h-20 w-full rounded-lg" />
        </div>
        {/* AI brief placeholder */}
        <div className="px-4 py-3 rounded-xl bg-gray-800/40 border border-gray-700/30 space-y-2">
          <div className="skeleton h-2.5 w-full rounded" />
          <div className="skeleton h-2.5 w-5/6 rounded" />
          <div className="skeleton h-2.5 w-4/6 rounded" />
        </div>
      </div>
    </>
  );
}

// ── Error State ────────────────────────────────────────
function RightPanelError({
  message,
  onClose,
  onRetry,
}: {
  message: string;
  onClose: () => void;
  onRetry: () => void;
}) {
  return (
    <>
      <div className="sticky top-0 z-10 px-5 pt-4 pb-3" style={{ background: "rgba(10,10,10,0.85)" }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-400" />
            <span className="text-sm font-medium text-white">Load failed</span>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-md flex items-center justify-center hover:bg-gray-700/40 transition-colors"
          >
            <X className="w-4 h-4 text-gray-400" />
          </button>
        </div>
      </div>

      <div className="px-5 py-6 flex flex-col items-center gap-4 text-center">
        <div className="w-12 h-12 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center">
          <AlertCircle className="w-6 h-6 text-red-400" />
        </div>
        <div>
          <p className="text-sm font-medium text-white mb-1">Couldn't load county data</p>
          <p className="text-[12px] text-gray-400 max-w-[280px] leading-relaxed">{message}</p>
        </div>
        <button
          onClick={onRetry}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/10 hover:bg-white/15 border border-white/10 text-sm text-white transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Retry
        </button>
      </div>
    </>
  );
}

// ── County Panel ───────────────────────────────────────
function CountyPanelContent({
  county,
  assessment,
  techType,
  onClose,
}: {
  county: NonNullable<ReturnType<typeof useLumenStore.getState>["selectedCounty"]>;
  assessment: ReturnType<typeof useLumenStore.getState>["siteAssessment"];
  techType: string;
  onClose: () => void;
}) {
  const { pinCounty, unpinCounty, pinnedCountyIds, capex, carbonPrice } = useLumenStore();
  const ciColor = carbonToColor(county.carbonIntensity);
  const timeSeries = useMemo(() => generateFallbackConusSeries(parseInt(county.id) || 42), [county.id]);
  const isPinned = pinnedCountyIds.includes(county.id);
  const canPin = !isPinned && pinnedCountyIds.length < 3;

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
          <div className="flex items-center gap-1">
            <button
              onClick={() =>
                exportAssessmentPdf(county as any, assessment, techType, { capex, carbonPrice })
              }
              title="Download PDF assessment"
              className="w-7 h-7 rounded-md flex items-center justify-center hover:bg-gray-700/40 transition-colors"
            >
              <Download className="w-3.5 h-3.5 text-gray-400" />
            </button>
            <button
              onClick={onClose}
              className="w-7 h-7 rounded-md flex items-center justify-center hover:bg-gray-700/40 transition-colors"
            >
              <X className="w-4 h-4 text-gray-400" />
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2 mt-2 flex-wrap">
          {assessment ? (
            <>
              <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-white/10 text-white border border-white/20">
                <Sparkles className="w-3 h-3" />
                AI County Brief
              </span>
              <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-white/5 text-gray-300 border border-white/10">
                {techType === "solar" ? "☀️ Solar PV" : "💨 Wind"}
              </span>
            </>
          ) : null}
          <button
            onClick={() =>
              isPinned ? unpinCounty(county.id) : pinCounty(county.id, county as any)
            }
            disabled={!isPinned && !canPin}
            title={
              isPinned
                ? "Remove from comparison"
                : canPin
                  ? "Add to comparison (up to 3)"
                  : "Max 3 counties pinned"
            }
            className={`ml-auto flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border transition-colors ${
              isPinned
                ? "bg-cyan-500/15 text-cyan-300 border-cyan-500/30 hover:bg-cyan-500/25"
                : canPin
                  ? "bg-white/5 text-gray-400 border-white/10 hover:bg-white/10 hover:text-white"
                  : "opacity-40 cursor-not-allowed bg-white/5 text-gray-600 border-white/10"
            }`}
          >
            {isPinned ? (
              <><PinOff className="w-3 h-3" />Pinned</>
            ) : (
              <><Pin className="w-3 h-3" />Compare</>
            )}
          </button>
        </div>
      </div>

      <div className="px-5 pb-6 space-y-5">
        {/* Key Metrics */}
        <div className="grid grid-cols-2 gap-3">
          <MetricCard icon={Leaf} label="Carbon Intensity" color={ciColor} delay={0}>
            <AnimatedNumber value={county.carbonIntensity} decimals={0} />
            <span className="text-[10px] text-gray-500 ml-1">gCO₂/kWh</span>
          </MetricCard>
          <MetricCard icon={Zap} label="Renewable" color="#a1a1aa" delay={0.05}>
            <AnimatedNumber value={county.renewablePercent} decimals={0} suffix="%" />
          </MetricCard>
          <MetricCard icon={DollarSign} label="LCOE" color="#fff" delay={0.1}>
            $<AnimatedNumber value={county.lcoe} decimals={0} />
            <span className="text-[10px] text-gray-500 ml-1">/MWh</span>
          </MetricCard>
          <MetricCard icon={TrendingUp} label="Load" color="#d4d4d8" delay={0.15}>
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

        {assessment ? (
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <Sparkles className="w-3.5 h-3.5 text-white" />
              <h3 className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">
                AI Assessment
              </h3>
            </div>
            <AssessmentCard text={assessment.aiSummary} />
          </div>
        ) : null}
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
  const { capex, carbonPrice } = useLumenStore();
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
          <div className="flex items-center gap-1">
            <button
              onClick={() =>
                exportAssessmentPdf(null, assessment, techType, { capex, carbonPrice })
              }
              title="Download PDF assessment"
              className="w-7 h-7 rounded-md flex items-center justify-center hover:bg-gray-700/40 transition-colors"
            >
              <Download className="w-3.5 h-3.5 text-gray-400" />
            </button>
            <button
              onClick={onClose}
              className="w-7 h-7 rounded-md flex items-center justify-center hover:bg-gray-700/40 transition-colors"
            >
              <X className="w-4 h-4 text-gray-400" />
            </button>
          </div>
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
          <AssessmentCard text={assessment.aiSummary} />
        </div>
      </div>
    </>
  );
}

// ── Shared components ──────────────────────────────────
function AssessmentCard({ text }: { text: string }) {
  const lines = text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const verdictLine = lines.find((line) => line.startsWith("Verdict:"));
  const detailLines = lines.filter((line) => !line.startsWith("Verdict:"));
  const verdictText = verdictLine?.replace(/^Verdict:\s*/, "") ?? "";

  const verdictTone = verdictText.toLowerCase().includes("attractive")
    ? "text-emerald-200"
    : verdictText.toLowerCase().includes("challenged")
      ? "text-rose-200"
      : "text-amber-100";

  return (
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
      {verdictText ? (
        <div className="mb-3">
          <p className="text-[13px] font-semibold text-white">
            <span className="text-gray-400">Verdict: </span>
            <span className={verdictTone}>{verdictText}</span>
          </p>
        </div>
      ) : null}
      {detailLines.length > 0 ? (
        <div className="space-y-3">
          {detailLines.map((line) => {
            const match = line.match(/^([^:]+):\s*(.*)$/);
            if (!match) {
              return (
                <p key={line} className="whitespace-pre-line text-gray-300">
                  {line}
                </p>
              );
            }

            const [, label, body] = match;
            return (
              <p key={line} className="text-[12px] leading-relaxed text-gray-200">
                <strong className="font-semibold text-white">{label}: </strong>
                {body}
              </p>
            );
          })}
        </div>
      ) : (
        <p className="whitespace-pre-line text-gray-300">{text}</p>
      )}
    </motion.div>
  );
}

function MetricCard({
  icon: Icon,
  label,
  color,
  delay = 0,
  children,
}: {
  icon: React.ElementType;
  label: string;
  color: string;
  delay?: number;
  children: React.ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay }}
      whileHover={{ scale: 1.02, borderColor: "rgba(255,255,255,0.15)" }}
      className="px-3 py-3 rounded-xl bg-gray-800/40 border border-gray-700/30 hover:border-gray-600/40 transition-colors cursor-default"
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

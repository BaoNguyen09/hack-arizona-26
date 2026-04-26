import { motion, AnimatePresence } from "framer-motion";
import { X, Columns2, Trash2, TrendingDown, TrendingUp } from "lucide-react";
import { useLumenStore } from "../store/useLumenStore";
import { type ZoneData, carbonToColor, computeLCOE, computeCompositeCostScore } from "../data/zones";
import { AnimatedNumber } from "./AnimatedNumber";

const ACCENT_COLORS = ["#22d3ee", "#a78bfa", "#f472b6"];

export function ComparisonPanel() {
  const {
    pinnedCountyIds,
    pinnedCounties,
    unpinCounty,
    clearPinnedCounties,
    leftSidebarOpen,
    rightPanelOpen,
    techType,
    capex,
    carbonPrice,
    timeHour,
  } = useLumenStore();

  const isOpen = pinnedCountyIds.length >= 2;

  const leftOffset = leftSidebarOpen ? 360 : 0;
  const rightOffset = rightPanelOpen ? 400 : 0;

  const counties = pinnedCountyIds
    .map((id) => pinnedCounties[id])
    .filter(Boolean) as ZoneData[];

  const baseline = counties[0];

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ y: 140, opacity: 0, x: "-50%" }}
          animate={{ y: 0, opacity: 1, x: "-50%" }}
          exit={{ y: 140, opacity: 0, x: "-50%" }}
          transition={{ type: "spring", stiffness: 280, damping: 28 }}
          className="fixed z-50 rounded-2xl shadow-2xl overflow-hidden"
          style={{
            bottom: "108px",
            left: `calc(50% + ${leftOffset / 2}px - ${rightOffset / 2}px)`,
            background: "rgba(6, 6, 6, 0.96)",
            backdropFilter: "blur(24px)",
            WebkitBackdropFilter: "blur(24px)",
            border: "1px solid rgba(255, 255, 255, 0.15)",
            boxShadow: "0 25px 60px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255,255,255,0.06) inset",
            transition: "left 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
            maxWidth: "900px",
            width: "calc(100vw - 80px)",
          }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3 border-b border-white/10"
            style={{ background: "linear-gradient(to right, rgba(34, 211, 238, 0.06), rgba(167, 139, 250, 0.06))" }}
          >
            <div className="flex items-center gap-2.5">
              <div className="w-6 h-6 rounded-md bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center">
                <Columns2 className="w-3.5 h-3.5 text-cyan-400" />
              </div>
              <span className="text-[12px] font-semibold text-white tracking-wide">
                Comparing {counties.length} Counties
              </span>
            </div>
            <button
              onClick={clearPinnedCounties}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] text-gray-400 hover:text-red-300 hover:bg-red-500/10 border border-transparent hover:border-red-500/20 transition-all duration-200"
            >
              <Trash2 className="w-3 h-3" />
              Clear
            </button>
          </div>

          {/* County cards */}
          <div className="flex">
            {counties.map((county, i) => (
              <CountyCompareCard
                key={county.id}
                county={county}
                baseline={i === 0 ? null : baseline}
                techType={techType}
                capex={capex}
                carbonPrice={carbonPrice}
                timeHour={timeHour}
                isBaseline={i === 0}
                accent={ACCENT_COLORS[i % ACCENT_COLORS.length]}
                onUnpin={() => unpinCounty(county.id)}
              />
            ))}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ── Individual County Card ─────────────────────────────
function CountyCompareCard({
  county,
  baseline,
  techType,
  capex,
  carbonPrice,
  timeHour,
  isBaseline,
  accent,
  onUnpin,
}: {
  county: ZoneData;
  baseline: ZoneData | null;
  techType: string;
  capex: number;
  carbonPrice: number;
  timeHour: number;
  isBaseline: boolean;
  accent: string;
  onUnpin: () => void;
}) {
  const cf = techType === "solar" ? county.solarCF : county.windCF;
  const lcoe = computeLCOE(cf, capex, techType as "solar" | "wind");
  const score = computeCompositeCostScore(
    county,
    techType as "solar" | "wind",
    capex,
    carbonPrice,
    timeHour,
  );

  let deltaLcoe: number | null = null;
  let deltaScore: number | null = null;
  let deltaCi: number | null = null;

  if (baseline) {
    const baseCf = techType === "solar" ? baseline.solarCF : baseline.windCF;
    const baseLcoe = computeLCOE(baseCf, capex, techType as "solar" | "wind");
    const baseScore = computeCompositeCostScore(
      baseline,
      techType as "solar" | "wind",
      capex,
      carbonPrice,
      timeHour,
    );
    deltaLcoe = lcoe - baseLcoe;
    deltaScore = score - baseScore;
    deltaCi = county.carbonIntensity - baseline.carbonIntensity;
  }

  const ciColor = carbonToColor(county.carbonIntensity);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: isBaseline ? 0 : 0.1 }}
      className="flex-1 min-w-0 relative"
      style={{
        borderRight: "1px solid rgba(255,255,255,0.08)",
      }}
    >
      {/* Accent top stripe */}
      <div className="h-0.5" style={{ background: accent }} />

      <div className="px-5 py-4">
        {/* Unpin */}
        <button
          onClick={onUnpin}
          className="absolute top-3 right-3 w-6 h-6 rounded-md flex items-center justify-center hover:bg-white/10 transition-colors"
        >
          <X className="w-3 h-3 text-gray-500 hover:text-white transition-colors" />
        </button>

        {/* County name + baseline badge */}
        <div className="flex items-start gap-2.5 mb-4 pr-8">
          <div
            className="w-2.5 h-2.5 rounded-full flex-shrink-0 mt-0.5"
            style={{ background: ciColor, boxShadow: `0 0 8px ${ciColor}50` }}
          />
          <div>
            <p className="text-[13px] font-semibold text-white leading-tight">
              {county.name}
            </p>
            <p className="text-[11px] text-gray-500 mt-0.5">{county.state}</p>
          </div>
          {isBaseline && (
            <span
              className="ml-auto text-[9px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap flex-shrink-0 uppercase tracking-wider"
              style={{
                background: `${accent}20`,
                color: accent,
                border: `1px solid ${accent}40`,
              }}
            >
              baseline
            </span>
          )}
        </div>

        {/* Metrics */}
        <div className="space-y-3">
          <CompStat
            label="LCOE"
            value={`$${lcoe.toFixed(1)}`}
            unit="/MWh"
            delta={deltaLcoe}
            deltaUnit="/MWh"
            lowerIsBetter
          />
          <CompStat
            label="Cost Score"
            value={score.toFixed(1)}
            delta={deltaScore}
            lowerIsBetter
          />
          <CompStat
            label="Capacity Factor"
            value={`${(cf * 100).toFixed(1)}%`}
            delta={
              baseline
                ? (cf - (techType === "solar" ? baseline.solarCF : baseline.windCF)) * 100
                : undefined
            }
            deltaUnit="%"
            lowerIsBetter={false}
          />
          <CompStat
            label="Carbon Intensity"
            value={`${county.carbonIntensity}`}
            unit=" gCO₂/kWh"
            delta={deltaCi}
            deltaUnit=" g"
            lowerIsBetter
          />
        </div>
      </div>
    </motion.div>
  );
}

function CompStat({
  label,
  value,
  unit = "",
  delta,
  deltaUnit = "",
  lowerIsBetter = true,
}: {
  label: string;
  value: string;
  unit?: string;
  delta?: number | null;
  deltaUnit?: string;
  lowerIsBetter?: boolean;
}) {
  const isGood = delta != null
    ? lowerIsBetter ? delta < 0 : delta > 0
    : null;
  const absDelta = delta != null ? Math.abs(delta) : 0;
  const isNeutral = absDelta < 0.05;

  return (
    <div className="flex items-center justify-between">
      <span className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-[13px] font-bold text-white tabular-nums">
          {value}
          {unit && <span className="text-[10px] text-gray-500 font-normal">{unit}</span>}
        </span>
        {delta != null && !isNeutral && (
          <span
            className="flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold tabular-nums"
            style={{
              background: isGood ? "rgba(16, 185, 129, 0.12)" : "rgba(239, 68, 68, 0.12)",
              color: isGood ? "#34d399" : "#f87171",
              border: `1px solid ${isGood ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)"}`,
            }}
          >
            {isGood ? <TrendingDown className="w-3 h-3" /> : <TrendingUp className="w-3 h-3" />}
            {delta >= 0 ? "+" : ""}
            {delta.toFixed(1)}{deltaUnit}
          </span>
        )}
      </div>
    </div>
  );
}

export { AnimatedNumber };

import { motion, AnimatePresence } from "framer-motion";
import { X, Columns2, Trash2 } from "lucide-react";
import { useLumenStore } from "../store/useLumenStore";
import { type ZoneData, carbonToColor, computeLCOE, computeCompositeCostScore } from "../data/zones";
import { AnimatedNumber } from "./AnimatedNumber";

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

  // Sidebar-aware centering (mirrors TimeSlider)
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
          className="fixed z-50 rounded-2xl shadow-2xl"
          style={{
            bottom: "108px",
            left: `calc(50% + ${leftOffset / 2}px - ${rightOffset / 2}px)`,
            background: "rgba(10, 10, 10, 0.92)",
            backdropFilter: "blur(24px)",
            WebkitBackdropFilter: "blur(24px)",
            border: "1px solid rgba(255, 255, 255, 0.1)",
            transition: "left 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
            maxWidth: "860px",
            width: "calc(100vw - 80px)",
          }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/8">
            <div className="flex items-center gap-2">
              <Columns2 className="w-3.5 h-3.5 text-gray-400" />
              <span className="text-[11px] font-medium text-gray-300 uppercase tracking-wider">
                Comparing {counties.length} counties
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <button
                onClick={clearPinnedCounties}
                className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] text-gray-500 hover:text-gray-300 hover:bg-white/5 transition-colors"
              >
                <Trash2 className="w-3 h-3" />
                Clear all
              </button>
            </div>
          </div>

          {/* County cards */}
          <div className="flex divide-x divide-white/5">
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
  onUnpin,
}: {
  county: ZoneData;
  baseline: ZoneData | null;
  techType: string;
  capex: number;
  carbonPrice: number;
  timeHour: number;
  isBaseline: boolean;
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
    <div className="flex-1 min-w-0 px-4 py-3 relative">
      {/* Unpin */}
      <button
        onClick={onUnpin}
        className="absolute top-2.5 right-2.5 w-5 h-5 rounded flex items-center justify-center hover:bg-white/10 transition-colors"
      >
        <X className="w-3 h-3 text-gray-500" />
      </button>

      {/* County name + baseline badge */}
      <div className="flex items-start gap-2 mb-3 pr-6">
        <div
          className="w-2 h-2 rounded-full flex-shrink-0 mt-1"
          style={{ background: ciColor, boxShadow: `0 0 6px ${ciColor}50` }}
        />
        <div>
          <p className="text-[12px] font-semibold text-white leading-tight">
            {county.name}
          </p>
          <p className="text-[10px] text-gray-500">{county.state}</p>
        </div>
        {isBaseline && (
          <span className="ml-auto text-[9px] font-medium px-1.5 py-0.5 rounded bg-white/10 text-gray-300 border border-white/10 whitespace-nowrap flex-shrink-0">
            baseline
          </span>
        )}
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-2">
        <Stat
          label="LCOE"
          value={`$${lcoe.toFixed(1)}/MWh`}
          delta={deltaLcoe !== null ? deltaLcoe : undefined}
          deltaUnit="/MWh"
          lowerIsBetter
        />
        <Stat
          label="Cost score"
          value={score.toFixed(1)}
          delta={deltaScore !== null ? deltaScore : undefined}
          lowerIsBetter
        />
        <Stat
          label="Cap. Factor"
          value={`${(cf * 100).toFixed(1)}%`}
          delta={
            baseline
              ? (cf - (techType === "solar" ? baseline.solarCF : baseline.windCF)) * 100
              : undefined
          }
          deltaUnit="%"
          lowerIsBetter={false}
        />
        <Stat
          label="Carbon"
          value={`${county.carbonIntensity} g`}
          delta={deltaCi !== null ? deltaCi : undefined}
          deltaUnit=" g"
          lowerIsBetter
        />
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  delta,
  deltaUnit = "",
  lowerIsBetter = true,
}: {
  label: string;
  value: string;
  delta?: number;
  deltaUnit?: string;
  lowerIsBetter?: boolean;
}) {
  const isGood = delta !== undefined
    ? lowerIsBetter ? delta < 0 : delta > 0
    : null;
  const deltaColor =
    delta === undefined || Math.abs(delta) < 0.05
      ? "text-gray-500"
      : isGood
        ? "text-emerald-400"
        : "text-rose-400";

  return (
    <div>
      <p className="text-[9px] text-gray-500 uppercase tracking-wide mb-0.5">{label}</p>
      <p className="text-[12px] font-semibold text-white tabular-nums">{value}</p>
      {delta !== undefined && (
        <p className={`text-[10px] tabular-nums ${deltaColor}`}>
          {delta >= 0 ? "+" : ""}
          {delta.toFixed(1)}{deltaUnit}
        </p>
      )}
    </div>
  );
}

// Tiny numeric animation is overkill for delta rows; AnimatedNumber used for main values only
export { AnimatedNumber };

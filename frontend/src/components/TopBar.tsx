import { useState } from "react";
import { motion } from "framer-motion";
import {
  Sun,
  Wind,
  DollarSign,
  Leaf,
  Search,
  Map,
  Grid3x3,
  ChevronDown,
} from "lucide-react";
import { useLumenStore } from "../store/useLumenStore";

export function TopBar() {
  const [queryText, setQueryText] = useState("");
  const {
    techType,
    setTechType,
    carbonPrice,
    setCarbonPrice,
    capex,
    setCapex,
    showZones,
    toggleZones,
    showHeatmap,
    toggleHeatmap,
    runNaturalLanguageQuery,
    clearQueryResults,
    queryMessage,
    queryPending,
  } = useLumenStore();

  return (
    <motion.header
      initial={{ y: -60, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: [0.23, 1, 0.32, 1] }}
      className="fixed top-0 left-0 right-0 z-50 h-14 flex items-center px-4 gap-3 border-b border-white/10"
      style={{
        background: "rgba(10, 10, 10, 0.85)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
      }}
    >
      <div className="flex items-center gap-2.5 mr-3">
        <div className="w-7 h-7 rounded-lg bg-white/10 flex items-center justify-center border border-white/20">
          <Wind className="text-white w-4 h-4" />
        </div>
        <span className="text-base font-semibold tracking-tight text-white">Lumen</span>
        <span className="ml-3 px-1.5 py-0.5 rounded text-[9px] font-medium bg-white/10 text-white border border-white/20 uppercase tracking-widest">
          BETA
        </span>
      </div>

      <div className="w-px h-6 bg-gray-700/50" />

      <div className="flex items-center gap-1 bg-gray-800/60 rounded-lg p-0.5 border border-gray-700/40">
        <button
          id="tech-solar"
          onClick={() => setTechType("solar")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200 ${
            techType === "solar"
              ? "bg-white/10 text-white border border-white/20"
              : "text-gray-400 hover:text-white border border-transparent"
          }`}
        >
          <Sun className="w-3.5 h-3.5" />
          Solar
        </button>
        <button
          id="tech-wind"
          onClick={() => setTechType("wind")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200 ${
            techType === "wind"
              ? "bg-white/10 text-white border border-white/20"
              : "text-gray-400 hover:text-white border border-transparent"
          }`}
        >
          <Wind className="w-3.5 h-3.5" />
          Wind
        </button>
      </div>

      <div className="w-px h-6 bg-gray-700/50" />

      <div className="flex items-center gap-2">
        <Leaf className="w-3.5 h-3.5 text-gray-400" />
        <span className="text-[11px] text-gray-400 whitespace-nowrap">Carbon</span>
        <input
          id="carbon-price-slider"
          type="range"
          min={0}
          max={200}
          value={carbonPrice}
          onChange={(e) => setCarbonPrice(Number(e.target.value))}
          className="w-20"
        />
        <span className="text-xs text-gray-300 font-medium tabular-nums w-10">
          ${carbonPrice}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <DollarSign className="w-3.5 h-3.5 text-gray-400" />
        <span className="text-[11px] text-gray-400 whitespace-nowrap">CAPEX</span>
        <input
          id="capex-slider"
          type="range"
          min={500}
          max={3000}
          step={50}
          value={capex}
          onChange={(e) => setCapex(Number(e.target.value))}
          className="w-20"
        />
        <span className="text-xs text-gray-300 font-medium tabular-nums w-14">
          ${capex}/kW
        </span>
      </div>

      <div className="w-px h-6 bg-gray-700/50" />

      <div className="flex items-center gap-1">
        <LayerBtn
          active={showZones}
          onClick={toggleZones}
          icon={Map}
          label="Zones"
          activeColor="white"
        />
        <LayerBtn
          active={showHeatmap && !showZones}
          onClick={() => {
            if (showZones) toggleZones();
            if (!showHeatmap) toggleHeatmap();
            else if (!showZones) toggleHeatmap();
          }}
          icon={Grid3x3}
          label="Grid"
          activeColor="white"
        />
      </div>

      <div className="flex-1" />

      <div className="relative max-w-xs w-full">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
        <input
          id="nl-query"
          type="text"
          placeholder="Ask Lumen anything..."
          value={queryText}
          onChange={(e) => setQueryText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              void runNaturalLanguageQuery(queryText);
            }
            if (e.key === "Escape") {
              setQueryText("");
              clearQueryResults();
            }
          }}
          className="w-full pl-9 pr-12 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300 placeholder-gray-500 focus:outline-none focus:border-white/30 transition-all"
        />
        <button
          type="button"
          onClick={() => void runNaturalLanguageQuery(queryText)}
          className="absolute right-1.5 top-1/2 -translate-y-1/2 px-2 py-1 rounded-md text-[10px] border border-white/10 bg-black/50 text-gray-300 hover:bg-white/10 transition-all disabled:opacity-60"
          disabled={queryPending}
        >
          {queryPending ? "..." : "Run"}
        </button>
        {queryMessage ? (
          <div className="absolute top-full left-0 right-0 mt-1 rounded-md border border-white/10 bg-black/85 px-2 py-1.5 text-[10px] text-gray-300 shadow-lg">
            {queryMessage}
          </div>
        ) : null}
      </div>

      <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300 hover:bg-white/10 transition-all">
        CONUS
        <ChevronDown className="w-3 h-3 text-gray-500" />
      </button>
    </motion.header>
  );
}

function LayerBtn({
  active,
  onClick,
  icon: Icon,
  label,
  activeColor,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ElementType;
  label: string;
  activeColor: string;
}) {
  const colorMap: Record<string, string> = {
    white: "bg-white/10 text-white border-white/20",
  };

  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-all duration-200 border ${
        active
          ? colorMap[activeColor]
          : "text-gray-500 border-transparent hover:text-white hover:bg-gray-800/50"
      }`}
    >
      <Icon className="w-3 h-3" />
      {label}
    </button>
  );
}

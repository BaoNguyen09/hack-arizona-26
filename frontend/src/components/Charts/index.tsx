import { useMemo } from "react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ComposedChart,
  ReferenceLine,
} from "recharts";
import { useLumenStore } from "../../store/useLumenStore";

// ── Dark tooltip ───────────────────────────────────────
function DarkTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass-panel rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-gray-400 mb-1">{label}</p>
      {payload.map((p: any, i: number) => (
        <p key={i} className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full inline-block"
            style={{ background: p.color }}
          />
          <span className="text-gray-300">{p.name}:</span>
          <span className="text-white font-medium">{typeof p.value === "number" ? p.value.toFixed(1) : p.value}</span>
        </p>
      ))}
    </div>
  );
}

// ── Carbon Intensity Chart ─────────────────────────────
export function CarbonIntensityChart({ data }: { data: any[] }) {
  const { timeHour } = useLumenStore();
  return (
    <ResponsiveContainer width="100%" height={140}>
      <AreaChart data={data} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="carbonGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#f59e0b" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" />
        <ReferenceLine x={timeHour} stroke="rgba(255,255,255,0.4)" strokeDasharray="3 3" />
        <XAxis
          dataKey="hour"
          tick={{ fontSize: 10 }}
          tickFormatter={(h) => `${h}:00`}
          interval={5}
        />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip content={<DarkTooltip />} />
        <Area
          type="monotone"
          dataKey="carbonIntensity"
          name="gCO₂eq/kWh"
          stroke="#f59e0b"
          fill="url(#carbonGrad)"
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ── Electricity Mix Stacked Area ───────────────────────
export function ElectricityMixChart({ data }: { data: any[] }) {
  const { timeHour } = useLumenStore();
  const sources = [
    { key: "solar", color: "#f59e0b" },
    { key: "wind", color: "#06b6d4" },
    { key: "nuclear", color: "#8b5cf6" },
    { key: "hydro", color: "#3b82f6" },
    { key: "gas", color: "#6b7280" },
    { key: "coal", color: "#374151" },
  ];

  return (
    <ResponsiveContainer width="100%" height={160}>
      <AreaChart data={data} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
        <defs>
          {sources.map(({ key, color }) => (
            <linearGradient key={key} id={`mix_${key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.6} />
              <stop offset="100%" stopColor={color} stopOpacity={0.1} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="hour"
          tick={{ fontSize: 10 }}
          tickFormatter={(h) => `${h}:00`}
          interval={5}
        />
        <YAxis tick={{ fontSize: 10 }} unit=" GW" />
        <Tooltip content={<DarkTooltip />} />
        {sources.map(({ key, color }) => (
          <Area
            key={key}
            type="monotone"
            dataKey={key}
            name={key.charAt(0).toUpperCase() + key.slice(1)}
            stackId="1"
            stroke={color}
            fill={`url(#mix_${key})`}
            strokeWidth={1}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ── Price Chart ────────────────────────────────────────
export function PriceChart({ data }: { data: any[] }) {
  const { timeHour } = useLumenStore();
  return (
    <ResponsiveContainer width="100%" height={120}>
      <LineChart data={data} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <ReferenceLine x={timeHour} stroke="rgba(255,255,255,0.4)" strokeDasharray="3 3" />
        <XAxis
          dataKey="hour"
          tick={{ fontSize: 10 }}
          tickFormatter={(h) => `${h}:00`}
          interval={5}
        />
        <YAxis tick={{ fontSize: 10 }} unit="$" />
        <Tooltip content={<DarkTooltip />} />
        <Line
          type="monotone"
          dataKey="price"
          name="$/MWh"
          stroke="#10b981"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ── Load Chart ─────────────────────────────────────────
export function LoadChart({ data }: { data: any[] }) {
  const { timeHour } = useLumenStore();
  return (
    <ResponsiveContainer width="100%" height={120}>
      <AreaChart data={data} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="loadGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="hour"
          tick={{ fontSize: 10 }}
          tickFormatter={(h) => `${h}:00`}
          interval={5}
        />
        <YAxis tick={{ fontSize: 10 }} unit=" GW" />
        <Tooltip content={<DarkTooltip />} />
        <Area
          type="monotone"
          dataKey="load"
          name="Load (GW)"
          stroke="#8b5cf6"
          fill="url(#loadGrad)"
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ── Net Flow Chart ─────────────────────────────────────
export function NetFlowChart({ data }: { data: any[] }) {
  const { timeHour } = useLumenStore();
  return (
    <ResponsiveContainer width="100%" height={120}>
      <BarChart data={data} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <ReferenceLine x={timeHour} stroke="rgba(255,255,255,0.4)" strokeDasharray="3 3" />
        <XAxis
          dataKey="hour"
          tick={{ fontSize: 10 }}
          tickFormatter={(h) => `${h}:00`}
          interval={5}
        />
        <YAxis tick={{ fontSize: 10 }} unit=" GW" />
        <Tooltip content={<DarkTooltip />} />
        <Bar
          dataKey="netFlow"
          name="Net Flow (GW)"
          fill="#06b6d4"
          radius={[2, 2, 0, 0]}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Generation vs Price (Site Panel) ───────────────────
export function GenerationPriceChart({
  data,
}: {
  data: { hour: number; generation: number; price: number }[];
}) {
  const { timeHour } = useLumenStore();
  return (
    <ResponsiveContainer width="100%" height={180}>
      <ComposedChart data={data} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="genGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#10b981" stopOpacity={0.4} />
            <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="hour"
          tick={{ fontSize: 10 }}
          tickFormatter={(h) => `${h}:00`}
          interval={5}
        />
        <YAxis yAxisId="gen" tick={{ fontSize: 10 }} unit=" MW" />
        <YAxis yAxisId="price" orientation="right" tick={{ fontSize: 10 }} unit="$" />
        <Tooltip content={<DarkTooltip />} />
        <Area
          yAxisId="gen"
          type="monotone"
          dataKey="generation"
          name="Generation (MW)"
          stroke="#10b981"
          fill="url(#genGrad)"
          strokeWidth={2}
        />
        <Line
          yAxisId="price"
          type="monotone"
          dataKey="price"
          name="Price ($/MWh)"
          stroke="#f59e0b"
          strokeWidth={2}
          strokeDasharray="4 4"
          dot={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// ── LCOE Breakdown Bar Chart ───────────────────────────
export function LCOEBreakdownChart({
  data,
}: {
  data: { category: string; value: number; color: string }[];
}) {
  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 4, right: 16, left: 0, bottom: 0 }}
      >
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 10 }} unit="$" />
        <YAxis
          type="category"
          dataKey="category"
          tick={{ fontSize: 11 }}
          width={60}
        />
        <Tooltip content={<DarkTooltip />} />
        <Bar dataKey="value" name="$/MWh" radius={[0, 4, 4, 0]}>
          {data.map((entry, i) => (
            <rect key={i} fill={entry.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Carbon Overlay (Site Panel) ────────────────────────
export function CarbonOverlayChart({
  data,
}: {
  data: { hour: number; gridIntensity: number; displaced: number }[];
}) {
  return (
    <ResponsiveContainer width="100%" height={150}>
      <ComposedChart data={data} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="dispGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="hour"
          tick={{ fontSize: 10 }}
          tickFormatter={(h) => `${h}:00`}
          interval={5}
        />
        <YAxis yAxisId="ci" tick={{ fontSize: 10 }} />
        <YAxis yAxisId="disp" orientation="right" tick={{ fontSize: 10 }} />
        <Tooltip content={<DarkTooltip />} />
        <Area
          yAxisId="ci"
          type="monotone"
          dataKey="gridIntensity"
          name="Grid CI (gCO₂/kWh)"
          stroke="#ef4444"
          fill="none"
          strokeWidth={2}
        />
        <Area
          yAxisId="disp"
          type="monotone"
          dataKey="displaced"
          name="Displaced (tCO₂)"
          stroke="#10b981"
          fill="url(#dispGrad)"
          strokeWidth={2}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// ── Horizontal Capacity Bar ────────────────────────────
export function CapacityBar({
  data,
}: {
  data: { source: string; capacity: number; color: string }[];
}) {
  const total = useMemo(
    () => data.reduce((sum, d) => sum + d.capacity, 0),
    [data]
  );

  return (
    <div>
      {/* Stacked bar */}
      <div className="flex h-5 rounded overflow-hidden mb-3">
        {data.map((d) => (
          <div
            key={d.source}
            className="relative group transition-all duration-300 hover:brightness-125"
            style={{
              width: `${(d.capacity / total) * 100}%`,
              background: d.color,
            }}
          >
            <div className="absolute -top-8 left-1/2 -translate-x-1/2 glass-panel px-2 py-1 rounded text-[10px] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
              {d.source}: {d.capacity.toFixed(1)} GW
            </div>
          </div>
        ))}
      </div>
      {/* Legend */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
        {data.map((d) => (
          <div key={d.source} className="flex items-center gap-2 text-xs">
            <span
              className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
              style={{ background: d.color }}
            />
            <span className="text-gray-400 flex-1">{d.source}</span>
            <span className="text-gray-300 font-medium tabular-nums">
              {d.capacity.toFixed(1)} GW
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

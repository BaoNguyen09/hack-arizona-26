import { motion } from "framer-motion";
import { Play, Pause, SkipBack, SkipForward } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { useLumenStore } from "../store/useLumenStore";

const HOURS = Array.from({ length: 24 }, (_, i) => i);

export function TimeSlider() {
  const { timeHour, setTimeHour, leftSidebarOpen, rightPanelOpen } = useLumenStore();
  const [isPlaying, setIsPlaying] = useState(false);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    if (isPlaying) {
      intervalRef.current = window.setInterval(() => {
        setTimeHour((timeHour + 1) % 24);
      }, 800);
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isPlaying, timeHour, setTimeHour]);

  // Compute sidebar-aware offsets
  const leftOffset = leftSidebarOpen ? 360 : 0;
  const rightOffset = rightPanelOpen ? 400 : 0;

  return (
    <motion.div
      initial={{ y: 80, opacity: 0, x: "-50%" }}
      animate={{ y: 0, opacity: 1, x: "-50%" }}
      transition={{ duration: 0.6, delay: 0.3, ease: [0.23, 1, 0.32, 1] }}
      className="fixed bottom-6 z-40 h-16 flex items-center gap-6 px-6 rounded-full shadow-2xl"
      style={{
        left: `calc(50% + ${leftOffset / 2}px - ${rightOffset / 2}px)`,
        width: '600px',
        background: "rgba(10, 10, 10, 0.85)",
        backdropFilter: "blur(24px)",
        WebkitBackdropFilter: "blur(24px)",
        border: "1px solid rgba(255, 255, 255, 0.1)",
        transition: "left 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
      }}
    >
      {/* Controls */}
      <div className="flex items-center gap-1.5">
        <button
          onClick={() => setTimeHour(Math.max(0, timeHour - 1))}
          className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-white/10 transition-colors text-gray-400 hover:text-white"
        >
          <SkipBack className="w-4 h-4" />
        </button>
        <button
          id="play-pause"
          onClick={() => setIsPlaying(!isPlaying)}
          className="w-10 h-10 rounded-full flex items-center justify-center bg-white/10 text-white hover:bg-white/20 transition-colors border border-white/10 shadow-sm"
        >
          {isPlaying ? (
            <Pause className="w-4 h-4" />
          ) : (
            <Play className="w-4 h-4 ml-0.5" />
          )}
        </button>
        <button
          onClick={() => setTimeHour(Math.min(23, timeHour + 1))}
          className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-white/10 transition-colors text-gray-400 hover:text-white"
        >
          <SkipForward className="w-4 h-4" />
        </button>
      </div>

      {/* Time display */}
      <div className="text-center min-w-[70px]">
        <p className="text-sm font-semibold text-white tabular-nums">
          {timeHour.toString().padStart(2, "0")}:00
        </p>
        <p className="text-[9px] text-gray-500">Apr 25, 2026</p>
      </div>

      {/* Slider with hour markers */}
      <div className="flex-1 flex flex-col justify-center translate-y-0.5">
        <input
          id="time-slider"
          type="range"
          min={0}
          max={23}
          value={timeHour}
          onChange={(e) => setTimeHour(Number(e.target.value))}
        />
        <div className="flex justify-between mt-1.5 px-1">
          {HOURS.filter((h) => h % 4 === 0).map((h) => (
            <span
              key={h}
              className={`text-[9px] font-medium tracking-wider ${
                h === timeHour ? "text-white" : "text-gray-500"
              }`}
            >
              {h.toString().padStart(2, "0")}:00
            </span>
          ))}
        </div>
      </div>

      {/* UTC indicator */}
      <div className="text-[10px] text-gray-600">
        UTC-7 (PDT)
      </div>
    </motion.div>
  );
}

import { TopBar } from "./components/TopBar";
import { LeftSidebar } from "./components/LeftSidebar";
import { MapView } from "./components/MapView";
import { RightPanel } from "./components/RightPanel";
import { TimeSlider } from "./components/TimeSlider";
import { ComparisonPanel } from "./components/ComparisonPanel";

export function App() {
  return (
    <div className="relative w-screen h-screen overflow-hidden bg-[#0B0F14]">
      {/* Map (fills entire screen, z-0) */}
      <MapView />

      {/* Overlays */}
      <TopBar />
      <LeftSidebar />
      <RightPanel />
      <ComparisonPanel />
      <TimeSlider />
    </div>
  );
}

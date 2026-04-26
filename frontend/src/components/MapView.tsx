import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import { useLumenStore } from "../store/useLumenStore";
import { enhanceCountyGeoJSON, carbonToColor } from "../data/zones";

function costToColor(score: number): string {
  const t = Math.min(1, Math.max(0, score / 100));
  if (t < 0.33) {
    const s = t / 0.33;
    return `rgb(${Math.round(34 + s * 211)},${Math.round(197 - s * 39)},${Math.round(94 - s * 83)})`;
  }
  if (t < 0.66) {
    const s = (t - 0.33) / 0.33;
    return `rgb(${Math.round(245 - s * 6)},${Math.round(158 - s * 90)},${Math.round(11 + s * 57)})`;
  }
  const s = (t - 0.66) / 0.34;
  return `rgb(${Math.round(239 - s * 20)},${Math.round(68 - s * 30)},${Math.round(68 - s * 10)})`;
}

function createCountyFilter(ids: string[]) {
  return ids.length > 0 ? (["in", "id", ...ids] as any) : (["==", "id", ""] as any);
}

export function MapView() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  const {
    gridCells,
    showHeatmap,
    showZones,
    selectCell,
    fetchCountyData,
    matchedCountyFips,
    leftSidebarOpen,
    rightPanelOpen,
    techType,
  } = useLumenStore();

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        name: "Dark",
        sources: {
          "carto-dark": {
            type: "raster",
            tiles: [
              "https://a.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}@2x.png",
              "https://b.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}@2x.png",
              "https://c.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}@2x.png",
            ],
            tileSize: 256,
            attribution:
              '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
          },
        },
        layers: [
          {
            id: "carto-dark-layer",
            type: "raster",
            source: "carto-dark",
            minzoom: 0,
            maxzoom: 19,
          },
        ],
        glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
      },
      center: [-96, 39],
      zoom: 4.2,
      minZoom: 3,
      maxZoom: 10,
    });

    map.addControl(new maplibregl.NavigationControl(), "bottom-right");
    map.on("load", () => {
      setMapLoaded(true);
    });

    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current || !mapLoaded) return;
    const map = mapRef.current;

    Promise.all([
      fetch("/data/us-counties.json").then((res) => res.json()),
      fetch("/data/us-states.json").then((res) => res.json()),
    ]).then(([countiesData, statesData]) => {
      const enhancedCounties = enhanceCountyGeoJSON(countiesData);

      if (map.getSource("states")) {
        (map.getSource("states") as maplibregl.GeoJSONSource).setData(statesData as any);
      } else {
        map.addSource("states", { type: "geojson", data: statesData as any });
      }

      if (map.getSource("counties")) {
        (map.getSource("counties") as maplibregl.GeoJSONSource).setData(
          enhancedCounties as any
        );
      } else {
        map.addSource("counties", { type: "geojson", data: enhancedCounties as any });

        map.addLayer({
          id: "counties-fill",
          type: "fill",
          source: "counties",
          paint: {
            "fill-color": ["get", "color"],
            "fill-opacity": 0.65,
          },
        });

        map.addLayer({
          id: "counties-border",
          type: "line",
          source: "counties",
          paint: {
            "line-color": "rgba(255,255,255,0.05)",
            "line-width": 0.5,
          },
        });

        map.addLayer({
          id: "states-border",
          type: "line",
          source: "states",
          paint: {
            "line-color": "rgba(255,255,255,0.6)",
            "line-width": 1.5,
          },
        });

        map.addLayer({
          id: "counties-hover",
          type: "fill",
          source: "counties",
          paint: {
            "fill-color": "#ffffff",
            "fill-opacity": 0.15,
          },
          filter: ["==", "id", ""],
        });

        map.addLayer({
          id: "counties-query-match-fill",
          type: "fill",
          source: "counties",
          paint: {
            "fill-color": "#ffffff",
            "fill-opacity": 0,
          },
          filter: ["==", "id", ""],
        });

        map.addLayer({
          id: "counties-query-match-line",
          type: "line",
          source: "counties",
          paint: {
            "line-color": "#ffffff",
            "line-width": 0,
            "line-opacity": 0,
          },
          filter: ["==", "id", ""],
        });

        map.on("mousemove", "counties-fill", (e) => {
          map.getCanvas().style.cursor = "pointer";
          if (!e.features?.length) return;
          const props = e.features[0].properties!;

          map.setFilter("counties-hover", ["==", "id", props.id]);

          if (popupRef.current) popupRef.current.remove();

          const ci = Number(props.carbonIntensity).toFixed(0);
          const ciColor = carbonToColor(Number(ci));

          popupRef.current = new maplibregl.Popup({
            closeButton: false,
            closeOnClick: false,
            offset: 14,
          })
            .setLngLat(e.lngLat)
            .setHTML(
              `<div style="font-family:Inter,sans-serif; background: rgba(11, 15, 20, 0.95); backdrop-filter: blur(8px); border: 1px solid rgba(31, 41, 55, 0.5); padding: 8px; border-radius: 8px;">
                <div style="font-size:13px;font-weight:600;margin-bottom:6px;display:flex;align-items:center;gap:6px;color:white;">
                  <span style="width:8px;height:8px;border-radius:2px;background:${ciColor};display:inline-block;"></span>
                  ${props.shortName}
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:3px 14px;font-size:11px;">
                  <span style="color:#9ca3af;">Carbon</span>
                  <span style="color:${ciColor};font-weight:600;text-align:right;">${ci} gCO2/kWh</span>
                  <span style="color:#9ca3af;">LCOE</span>
                  <span style="color:white;font-weight:600;text-align:right;">$${Number(props.lcoe).toFixed(1)}/MWh</span>
                  <span style="color:#9ca3af;">Renewable</span>
                  <span style="color:white;font-weight:500;text-align:right;">${props.renewablePercent}%</span>
                </div>
              </div>`
            )
            .addTo(map);
        });

        map.on("mouseleave", "counties-fill", () => {
          map.getCanvas().style.cursor = "";
          map.setFilter("counties-hover", ["==", "id", ""]);
          if (popupRef.current) {
            popupRef.current.remove();
            popupRef.current = null;
          }
        });

        map.on("click", "counties-fill", (e) => {
          if (!e.features?.length) return;
          const props = e.features[0].properties!;
          void fetchCountyData(props.id, props.shortName || props.name, props.state);
        });
      }
    });
  }, [mapLoaded, fetchCountyData]);

  useEffect(() => {
    if (!mapRef.current || !mapLoaded) return;
    const map = mapRef.current;
    const filter = createCountyFilter(matchedCountyFips);

    if (map.getLayer("counties-query-match-fill")) {
      map.setFilter("counties-query-match-fill", filter);
    }
    if (map.getLayer("counties-query-match-line")) {
      map.setFilter("counties-query-match-line", filter);
    }
  }, [matchedCountyFips, mapLoaded]);

  useEffect(() => {
    if (!mapRef.current || !mapLoaded || matchedCountyFips.length === 0) return;
    const map = mapRef.current;
    let frameId = 0;
    let active = true;

    const tick = () => {
      if (!active) return;
      const phase = (Date.now() % 1800) / 1800;
      const pulse = 0.18 + (Math.sin(phase * Math.PI * 2) + 1) * 0.16;

      if (map.getLayer("counties-query-match-fill")) {
        map.setPaintProperty("counties-query-match-fill", "fill-opacity", pulse);
      }
      if (map.getLayer("counties-query-match-line")) {
        map.setPaintProperty("counties-query-match-line", "line-opacity", 0.55);
        map.setPaintProperty(
          "counties-query-match-line",
          "line-width",
          1.2 + pulse * 2.4
        );
      }

      frameId = window.requestAnimationFrame(tick);
    };

    frameId = window.requestAnimationFrame(tick);

    return () => {
      active = false;
      window.cancelAnimationFrame(frameId);
      if (map.getLayer("counties-query-match-fill")) {
        map.setPaintProperty("counties-query-match-fill", "fill-opacity", 0);
      }
      if (map.getLayer("counties-query-match-line")) {
        map.setPaintProperty("counties-query-match-line", "line-opacity", 0);
        map.setPaintProperty("counties-query-match-line", "line-width", 0);
      }
    };
  }, [matchedCountyFips, mapLoaded]);

  useEffect(() => {
    if (!mapRef.current || !mapLoaded) return;
    const map = mapRef.current;
    const vis = showZones ? "visible" : "none";
    [
      "counties-fill",
      "counties-border",
      "states-border",
      "counties-hover",
      "counties-query-match-fill",
      "counties-query-match-line",
    ].forEach((id) => {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", vis);
    });
  }, [showZones, mapLoaded]);

  useEffect(() => {
    if (!mapRef.current || !mapLoaded) return;
    const map = mapRef.current;

    const features = gridCells.map((cell) => ({
      type: "Feature" as const,
      properties: {
        id: cell.id,
        costScore: cell.costScore,
        carbonIntensity: cell.carbonIntensity,
        capacityFactor: cell.capacityFactor,
        lcoe: cell.lcoe,
        avgPrice: cell.avgPrice,
        region: cell.region,
        color: costToColor(cell.costScore),
      },
      geometry: {
        type: "Polygon" as const,
        coordinates: [[
          [cell.lon - 0.5, cell.lat - 0.4],
          [cell.lon + 0.5, cell.lat - 0.4],
          [cell.lon + 0.5, cell.lat + 0.4],
          [cell.lon - 0.5, cell.lat + 0.4],
          [cell.lon - 0.5, cell.lat - 0.4],
        ]],
      },
    }));

    const geojson = { type: "FeatureCollection" as const, features };

    if (map.getSource("grid-cells")) {
      (map.getSource("grid-cells") as maplibregl.GeoJSONSource).setData(geojson as any);
    } else {
      map.addSource("grid-cells", { type: "geojson", data: geojson as any });

      map.addLayer({
        id: "grid-cells-fill",
        type: "fill",
        source: "grid-cells",
        paint: { "fill-color": ["get", "color"], "fill-opacity": 0.4 },
      });
      map.addLayer({
        id: "grid-cells-line",
        type: "line",
        source: "grid-cells",
        paint: {
          "line-color": ["get", "color"],
          "line-width": 0.3,
          "line-opacity": 0.15,
        },
      });
      map.addLayer({
        id: "grid-cells-hover",
        type: "fill",
        source: "grid-cells",
        paint: { "fill-color": "#ffffff", "fill-opacity": 0 },
        filter: ["==", "id", ""],
      });

      map.on("mousemove", "grid-cells-fill", (e) => {
        if (showZones) return;
        map.getCanvas().style.cursor = "pointer";
        if (!e.features?.length) return;
        const props = e.features[0].properties!;

        map.setFilter("grid-cells-hover", ["==", "id", props.id]);
        map.setPaintProperty("grid-cells-hover", "fill-opacity", 0.12);

        if (popupRef.current) popupRef.current.remove();
        const costColor =
          props.costScore < 30
            ? "#10b981"
            : props.costScore < 50
              ? "#22d3ee"
              : props.costScore < 70
                ? "#f59e0b"
                : "#ef4444";
        const costLabel =
          props.costScore < 30
            ? "Excellent"
            : props.costScore < 50
              ? "Good"
              : props.costScore < 70
                ? "Moderate"
                : "High Cost";

        popupRef.current = new maplibregl.Popup({
          closeButton: false,
          closeOnClick: false,
          offset: 12,
        })
          .setLngLat(e.lngLat)
          .setHTML(
            `<div style="font-family:Inter,sans-serif; background: rgba(11, 15, 20, 0.95); backdrop-filter: blur(8px); border: 1px solid rgba(31, 41, 55, 0.5); padding: 8px; border-radius: 8px;">
              <div style="font-size:12px;font-weight:600;margin-bottom:5px;color:${costColor}">${costLabel} <span style="color:#9ca3af;font-weight:400;font-size:10px;">- ${props.region}</span></div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:3px 14px;font-size:11px;">
                <span style="color:#9ca3af;">CF</span><span style="color:white;font-weight:500;text-align:right;">${(props.capacityFactor * 100).toFixed(1)}%</span>
                <span style="color:#9ca3af;">LCOE</span><span style="color:white;font-weight:500;text-align:right;">$${Number(props.lcoe).toFixed(1)}/MWh</span>
                <span style="color:#9ca3af;">Carbon</span><span style="color:white;font-weight:500;text-align:right;">${Number(props.carbonIntensity).toFixed(0)} g</span>
                <span style="color:#9ca3af;">Price</span><span style="color:white;font-weight:500;text-align:right;">$${Number(props.avgPrice).toFixed(0)}/MWh</span>
              </div>
            </div>`
          )
          .addTo(map);
      });

      map.on("mouseleave", "grid-cells-fill", () => {
        if (showZones) return;
        map.getCanvas().style.cursor = "";
        map.setFilter("grid-cells-hover", ["==", "id", ""]);
        map.setPaintProperty("grid-cells-hover", "fill-opacity", 0);
        popupRef.current?.remove();
        popupRef.current = null;
      });

      map.on("click", "grid-cells-fill", (e) => {
        if (showZones) return;
        if (!e.features?.length) return;
        const cell = gridCells.find((c) => c.id === e.features![0].properties!.id);
        if (cell) selectCell(cell);
      });
    }
  }, [gridCells, mapLoaded, selectCell, showZones]);

  useEffect(() => {
    if (!mapRef.current || !mapLoaded) return;
    const map = mapRef.current;
    const vis = showHeatmap && !showZones ? "visible" : "none";
    ["grid-cells-fill", "grid-cells-line", "grid-cells-hover"].forEach((id) => {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", vis);
    });
  }, [showHeatmap, showZones, mapLoaded]);

  useEffect(() => {
    if (!mapRef.current) return;
    setTimeout(() => mapRef.current?.resize(), 350);
  }, [leftSidebarOpen, rightPanelOpen]);

  return (
    <div className="fixed inset-0 z-0">
      <div ref={mapContainer} className="w-full h-full" />

      <div
        className="fixed z-20 glass-panel rounded-lg px-3 py-2.5 shadow-lg"
        style={{
          bottom: "24px",
          right: rightPanelOpen ? "424px" : "24px",
          transition: "right 0.3s ease",
        }}
      >
        {showZones ? (
          <>
            <p className="text-[9px] text-gray-400 uppercase tracking-wider mb-1.5 font-medium">
              Carbon (gCO2eq/kWh)
            </p>
            <div className="flex items-center gap-1.5">
              <span className="text-[9px] text-gray-400 w-4 text-right">0</span>
              <div className="flex w-24 h-1.5 rounded overflow-hidden">
                <div className="flex-1" style={{ background: "#10b981" }} />
                <div className="flex-1" style={{ background: "#84cc16" }} />
                <div className="flex-1" style={{ background: "#eab308" }} />
                <div className="flex-1" style={{ background: "#f59e0b" }} />
                <div className="flex-1" style={{ background: "#ea580c" }} />
                <div className="flex-1" style={{ background: "#dc2626" }} />
                <div className="flex-1" style={{ background: "#991b1b" }} />
                <div className="flex-1" style={{ background: "#450a0a" }} />
              </div>
              <span className="text-[9px] text-gray-400">800+</span>
            </div>
          </>
        ) : showHeatmap ? (
          <>
            <p className="text-[9px] text-gray-400 uppercase tracking-wider mb-1.5 font-medium">
              Cost Score - {techType === "solar" ? "Solar" : "Wind"}
            </p>
            <div className="flex items-center gap-1.5">
              <span className="text-[9px] text-gray-400">Low</span>
              <div
                className="w-24 h-1.5 rounded-full"
                style={{
                  background: "linear-gradient(to right, #22c55e, #eab308, #ef4444)",
                }}
              />
              <span className="text-[9px] text-gray-400">High</span>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}

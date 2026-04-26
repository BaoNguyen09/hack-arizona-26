import type { SiteAssessment } from "../data/mockData";
import type { ZoneData } from "../data/zones";

/**
 * Generates a clean print-ready HTML page in a hidden div and triggers
 * window.print() so the browser's native PDF export dialog opens.
 *
 * The element is cleaned up after the print dialog closes.
 */
export function exportAssessmentPdf(
  county: ZoneData | null,
  assessment: SiteAssessment | null,
  techType: string,
  scenarioParams: { capex: number; carbonPrice: number },
) {
  if (!county && !assessment) return;

  const name = county?.name ?? assessment?.region ?? "Site";
  const state = county?.state ?? "";
  const date = new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const lcoe = assessment?.lcoe ?? county?.lcoe ?? 0;
  const cf = (assessment?.capacityFactor ?? 0) * 100;
  const carbon = county?.carbonIntensity ?? 0;
  const renewable = county?.renewablePercent ?? 0;
  const aiText = assessment?.aiSummary ?? "";

  const generationRows = (assessment?.generationProfile ?? [])
    .filter((_, i) => i % 4 === 0)
    .map(
      (p) =>
        `<tr><td>${p.hour}:00</td><td>${p.generation.toFixed(1)} MW</td><td>$${p.price.toFixed(0)}/MWh</td></tr>`,
    )
    .join("");

  const html = `
    <style>
      body { font-family: Inter, Helvetica, sans-serif; color: #111; background: #fff; margin: 0; padding: 40px; }
      h1 { font-size: 22px; font-weight: 700; margin: 0 0 4px; }
      h2 { font-size: 13px; font-weight: 600; color: #444; border-bottom: 1px solid #eee; padding-bottom: 6px; margin: 24px 0 10px; }
      .meta { font-size: 12px; color: #777; margin-bottom: 28px; }
      .grid { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 16px; margin-bottom: 8px; }
      .card { background: #f8f8f8; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px 16px; }
      .card-label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; color: #9ca3af; margin-bottom: 4px; }
      .card-value { font-size: 18px; font-weight: 700; color: #111; }
      .card-unit { font-size: 11px; color: #6b7280; }
      table { width: 100%; border-collapse: collapse; font-size: 12px; }
      th { text-align: left; font-weight: 600; padding: 6px 8px; background: #f3f4f6; border-bottom: 1px solid #e5e7eb; }
      td { padding: 5px 8px; border-bottom: 1px solid #f3f4f6; }
      .brief { font-size: 12px; line-height: 1.7; color: #374151; background: #f9fafb; padding: 16px; border-radius: 8px; border: 1px solid #e5e7eb; }
      .footer { margin-top: 40px; font-size: 10px; color: #9ca3af; border-top: 1px solid #eee; padding-top: 12px; display: flex; justify-content: space-between; }
      .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #f3f4f6; font-size: 11px; color: #374151; margin-right: 6px; }
    </style>

    <h1>Site Assessment — ${name}${state ? `, ${state}` : ""}</h1>
    <div class="meta">
      <span class="badge">Lumen</span>
      <span class="badge">${techType === "solar" ? "☀️ Solar PV" : "💨 Wind"}</span>
      <span class="badge">CAPEX $${scenarioParams.capex}/kW</span>
      <span class="badge">Carbon $${scenarioParams.carbonPrice}/ton</span>
      &nbsp;·&nbsp; Generated ${date}
    </div>

    <h2>Key Metrics</h2>
    <div class="grid">
      <div class="card">
        <div class="card-label">LCOE</div>
        <div class="card-value">$${lcoe.toFixed(1)}<span class="card-unit"> /MWh</span></div>
      </div>
      <div class="card">
        <div class="card-label">Capacity Factor</div>
        <div class="card-value">${cf.toFixed(1)}<span class="card-unit"> %</span></div>
      </div>
      <div class="card">
        <div class="card-label">Carbon Intensity</div>
        <div class="card-value">${carbon}<span class="card-unit"> gCO₂/kWh</span></div>
      </div>
      <div class="card">
        <div class="card-label">Renewable Mix</div>
        <div class="card-value">${renewable}<span class="card-unit"> %</span></div>
      </div>
    </div>

    ${
      generationRows
        ? `<h2>Generation & Price Profile (every 4h)</h2>
           <table>
             <tr><th>Hour</th><th>Generation</th><th>Wholesale Price</th></tr>
             ${generationRows}
           </table>`
        : ""
    }

    ${
      aiText
        ? `<h2>AI Site Assessment</h2>
           <div class="brief">${aiText.replace(/\n/g, "<br/>")}</div>`
        : ""
    }

    <div class="footer">
      <span>Lumen Energy Intelligence Platform — Confidential</span>
      <span>${date}</span>
    </div>
  `;

  // Inject into hidden print root
  let root = document.getElementById("lumen-print-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "lumen-print-root";
    document.body.appendChild(root);
  }
  root.innerHTML = html;

  // Wait a tick for DOM paint, then print
  requestAnimationFrame(() => {
    window.print();
    // Clean up after dialog closes (slight delay to be safe)
    setTimeout(() => {
      if (root) root.innerHTML = "";
    }, 1000);
  });
}

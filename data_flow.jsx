import { useState } from "react";

const NODES = {
  // CSV Sources
  "faostat_west": { id: "faostat_west", label: "FAOSTAT_data_western_europe.csv", type: "csv", x: 60, y: 80 },
  "faostat_south": { id: "faostat_south", label: "FAOSTAT_southern_europe.csv", type: "csv", x: 60, y: 160 },
  "faostat_fv": { id: "faostat_fv", label: "FAOSTAT_data_fruit_veg.csv", type: "csv", x: 60, y: 240 },
  "faostat_all": { id: "faostat_all", label: "FAOSTAT_data_all_ag.csv", type: "csv", x: 60, y: 320 },
  "data_csv": { id: "data_csv", label: "data.csv (FAOSTAT emissions)", type: "csv", x: 60, y: 500 },
  "italy_csv": { id: "italy_csv", label: "italy_co-emissions-by-sector.csv", type: "csv", x: 60, y: 720 },
  "uba_csv": { id: "uba_csv", label: "UBA_sectors.csv", type: "csv", x: 60, y: 800 },
  "world_bank": { id: "world_bank", label: "World Bank GDP API", type: "api", x: 60, y: 580 },
  "unsd_m49": { id: "unsd_m49", label: "UNSD M49 Lookup (web)", type: "api", x: 60, y: 640 },
  "statista": { id: "statista", label: "Statista (Spain, hardcoded)", type: "api", x: 60, y: 876 },
  "france_manual": { id: "france_manual", label: "France data (hardcoded)", type: "api", x: 60, y: 940 },

  // Scripts
  "ag_data": { id: "ag_data", label: "ag_data.py", type: "script", x: 420, y: 200, desc: "Agricultural Gross Production Index analysis for W. & S. Europe (Italy, Spain, France, Germany). Compares production indices, top items by 5-year bins." },
  "clean_dat": { id: "clean_dat", label: "clean_dat.py", type: "script", x: 420, y: 570, desc: "GHG emissions analysis. Loads emissions, merges M49 codes, fetches World Bank GDP, computes emissions intensity, indexes to 1990=100, computes slopes & % change." },
  "sectors": { id: "sectors", label: "sectors.py", type: "script", x: 420, y: 850, desc: "Sector-level GHG emissions breakdown for 2023. Combines Spain, Germany, France, Italy into a heatmap of proportional sector emissions." },

  // Outputs
  "out_agprod": { id: "out_agprod", label: "agricultural_gross_production_index.png", type: "output", x: 760, y: 100 },
  "out_fv": { id: "out_fv", label: "fruit_veg_production_index.png", type: "output", x: 760, y: 180 },
  "out_top": { id: "out_top", label: "top_item_every_5_years_by_country.png", type: "output", x: 760, y: 260 },
  "out_fig1": { id: "out_fig1", label: "fig1_emissions_intensity.png", type: "output", x: 760, y: 500 },
  "out_fig2": { id: "out_fig2", label: "fig2_emissions_index.png", type: "output", x: 760, y: 580 },
  "out_pct": { id: "out_pct", label: "% change 1990→latest (printed)", type: "output", x: 760, y: 660 },
  "out_slopes": { id: "out_slopes", label: "Annual slopes table (printed)", type: "output", x: 760, y: 730 },
  "out_heatmap": { id: "out_heatmap", label: "ghg_emissions_by_sector_heatmap.png", type: "output", x: 760, y: 850 },
};

const EDGES = [
  // ag_data.py inputs
  { from: "faostat_west", to: "ag_data" },
  { from: "faostat_south", to: "ag_data" },
  { from: "faostat_fv", to: "ag_data" },
  { from: "faostat_all", to: "ag_data" },
  // ag_data.py outputs
  { from: "ag_data", to: "out_agprod" },
  { from: "ag_data", to: "out_fv" },
  { from: "ag_data", to: "out_top" },
  // clean_dat.py inputs
  { from: "data_csv", to: "clean_dat" },
  { from: "world_bank", to: "clean_dat" },
  { from: "unsd_m49", to: "clean_dat" },
  // clean_dat.py outputs
  { from: "clean_dat", to: "out_fig1" },
  { from: "clean_dat", to: "out_fig2" },
  { from: "clean_dat", to: "out_pct" },
  { from: "clean_dat", to: "out_slopes" },
  // sectors.py inputs
  { from: "italy_csv", to: "sectors" },
  { from: "uba_csv", to: "sectors" },
  { from: "statista", to: "sectors" },
  { from: "france_manual", to: "sectors" },
  // sectors.py outputs
  { from: "sectors", to: "out_heatmap" },
];

const TYPE_STYLES = {
  csv: { bg: "#1a2e4a", border: "#3b82f6", text: "#93c5fd", icon: "📄" },
  api: { bg: "#1a3a2a", border: "#22c55e", text: "#86efac", icon: "🌐" },
  script: { bg: "#2d1a4a", border: "#a855f7", text: "#d8b4fe", icon: "⚙️" },
  output: { bg: "#3a1a1a", border: "#f59e0b", text: "#fcd34d", icon: "📊" },
};

const SVG_W = 940;
const SVG_H = 1060;

function midpoint(a, b) {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

function edgePath(from, to) {
  const fx = from.x + 175;
  const fy = from.y + 22;
  const tx = to.x;
  const ty = to.y + 22;
  const mx = (fx + tx) / 2;
  return `M ${fx} ${fy} C ${mx} ${fy}, ${mx} ${ty}, ${tx} ${ty}`;
}

export default function DataFlow() {
  const [hovered, setHovered] = useState(null);
  const [selected, setSelected] = useState(null);

  const active = selected || hovered;

  const highlightedNodes = new Set();
  const highlightedEdges = new Set();

  if (active) {
    highlightedNodes.add(active);
    EDGES.forEach((e, i) => {
      if (e.from === active || e.to === active) {
        highlightedNodes.add(e.from);
        highlightedNodes.add(e.to);
        highlightedEdges.add(i);
      }
    });
  }

  const dim = active !== null;

  return (
    <div style={{ background: "#0a0a12", minHeight: "100vh", fontFamily: "'Courier New', monospace", padding: "24px" }}>
      <div style={{ maxWidth: 980, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 16, marginBottom: 6 }}>
            <h1 style={{ color: "#e2e8f0", fontSize: 22, fontWeight: 700, margin: 0, letterSpacing: "0.05em" }}>
              DATA FLOW MAP
            </h1>
            <span style={{ color: "#475569", fontSize: 11, letterSpacing: "0.12em" }}>EUROPEAN GHG + AGRICULTURE ANALYSIS</span>
          </div>
          <p style={{ color: "#64748b", fontSize: 12, margin: 0 }}>Click or hover any node to highlight its connections</p>
        </div>

        {/* Legend */}
        <div style={{ display: "flex", gap: 20, marginBottom: 20, flexWrap: "wrap" }}>
          {Object.entries(TYPE_STYLES).map(([type, s]) => (
            <div key={type} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 12, height: 12, borderRadius: 2, background: s.bg, border: `1.5px solid ${s.border}` }} />
              <span style={{ color: "#94a3b8", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em" }}>{type}</span>
            </div>
          ))}
        </div>

        {/* Detail panel */}
        {active && NODES[active]?.desc && (
          <div style={{ background: "#12122a", border: "1px solid #a855f7", borderRadius: 8, padding: "12px 16px", marginBottom: 16, maxWidth: 600 }}>
            <div style={{ color: "#d8b4fe", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>{NODES[active].label}</div>
            <div style={{ color: "#94a3b8", fontSize: 12, lineHeight: 1.6 }}>{NODES[active].desc}</div>
          </div>
        )}

        {/* SVG */}
        <div style={{ background: "#0d0d1a", borderRadius: 12, border: "1px solid #1e293b", overflow: "hidden" }}>
          <svg width="100%" viewBox={`0 0 ${SVG_W} ${SVG_H}`} style={{ display: "block" }}>
            <defs>
              <marker id="arrow" markerWidth="7" markerHeight="7" refX="5" refY="3.5" orient="auto">
                <polygon points="0 0, 7 3.5, 0 7" fill="#334155" />
              </marker>
              <marker id="arrow-active" markerWidth="7" markerHeight="7" refX="5" refY="3.5" orient="auto">
                <polygon points="0 0, 7 3.5, 0 7" fill="#a855f7" />
              </marker>

              {/* Grid pattern */}
              <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#0f172a" strokeWidth="0.5" />
              </pattern>
            </defs>

            {/* Background grid */}
            <rect width={SVG_W} height={SVG_H} fill="url(#grid)" />

            {/* Column labels */}
            {[
              { x: 60 + 87, label: "SOURCES", color: "#1e40af" },
              { x: 420 + 87, label: "SCRIPTS", color: "#6b21a8" },
              { x: 760 + 87, label: "OUTPUTS", color: "#92400e" },
            ].map(col => (
              <g key={col.label}>
                <line x1={col.x} y1={20} x2={col.x} y2={SVG_H - 20} stroke={col.color} strokeWidth="0.5" strokeDasharray="4,6" opacity="0.5" />
                <text x={col.x} y={14} textAnchor="middle" fill={col.color} fontSize="9" letterSpacing="2" opacity="0.8">{col.label}</text>
              </g>
            ))}

            {/* Edges */}
            {EDGES.map((e, i) => {
              const from = NODES[e.from];
              const to = NODES[e.to];
              if (!from || !to) return null;
              const isHighlighted = highlightedEdges.has(i);
              const isDimmed = dim && !isHighlighted;
              return (
                <path
                  key={i}
                  d={edgePath(from, to)}
                  fill="none"
                  stroke={isHighlighted ? "#a855f7" : "#1e293b"}
                  strokeWidth={isHighlighted ? 2 : 1}
                  markerEnd={isHighlighted ? "url(#arrow-active)" : "url(#arrow)"}
                  opacity={isDimmed ? 0.08 : isHighlighted ? 1 : 0.6}
                  style={{ transition: "opacity 0.2s, stroke 0.2s" }}
                />
              );
            })}

            {/* Nodes */}
            {Object.values(NODES).map(node => {
              const s = TYPE_STYLES[node.type];
              const isActive = node.id === active;
              const isConnected = highlightedNodes.has(node.id);
              const isDimmed = dim && !isConnected;
              const isScript = node.type === "script";

              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x}, ${node.y})`}
                  style={{ cursor: "pointer" }}
                  onMouseEnter={() => setHovered(node.id)}
                  onMouseLeave={() => setHovered(null)}
                  onClick={() => setSelected(selected === node.id ? null : node.id)}
                >
                  <rect
                    x={0} y={0}
                    width={isScript ? 170 : 175}
                    height={isScript ? 44 : 40}
                    rx={isScript ? 6 : 4}
                    fill={s.bg}
                    stroke={isActive ? "#ffffff" : isConnected ? s.border : s.border}
                    strokeWidth={isActive ? 2 : isConnected ? 1.5 : 0.8}
                    opacity={isDimmed ? 0.2 : 1}
                    style={{ transition: "opacity 0.2s" }}
                  />
                  {/* Accent line on left for scripts */}
                  {isScript && (
                    <rect x={0} y={0} width={4} height={44} rx={2} fill={s.border} opacity={isDimmed ? 0.2 : 0.8} />
                  )}
                  <text
                    x={isScript ? 14 : 8}
                    y={isScript ? 16 : 14}
                    fill={s.text}
                    fontSize={isScript ? 12 : 9}
                    fontWeight={isScript ? 700 : 400}
                    opacity={isDimmed ? 0.3 : 1}
                    style={{ transition: "opacity 0.2s", userSelect: "none" }}
                  >
                    {s.icon} {isScript ? node.label : ""}
                  </text>
                  {!isScript && (
                    <text
                      x={8} y={14}
                      fill={s.text}
                      fontSize={9}
                      opacity={isDimmed ? 0.3 : 1}
                      style={{ userSelect: "none" }}
                    >
                      {s.icon}{" "}
                      {node.label.length > 28 ? node.label.slice(0, 27) + "…" : node.label}
                    </text>
                  )}
                  {isScript && (
                    <text
                      x={14} y={32}
                      fill={s.text}
                      fontSize={8.5}
                      opacity={isDimmed ? 0.2 : 0.55}
                      style={{ userSelect: "none" }}
                    >
                      {node.label.replace(".py", "")}
                    </text>
                  )}
                  {!isScript && node.label.length > 28 && (
                    <title>{node.label}</title>
                  )}
                </g>
              );
            })}

            {/* Section brackets */}
            {[
              { y1: 60, y2: 340, label: "Agricultural indices", x: 248 },
              { y1: 470, y2: 680, label: "Emissions intensity", x: 248 },
              { y1: 695, y2: 970, label: "Sector breakdown", x: 248 },
            ].map((b, i) => (
              <g key={i} opacity={0.25}>
                <line x1={b.x} y1={b.y1} x2={b.x} y2={b.y2} stroke="#475569" strokeWidth="1" />
                <line x1={b.x} y1={b.y1} x2={b.x + 6} y2={b.y1} stroke="#475569" strokeWidth="1" />
                <line x1={b.x} y1={b.y2} x2={b.x + 6} y2={b.y2} stroke="#475569" strokeWidth="1" />
                <text
                  x={b.x - 4}
                  y={(b.y1 + b.y2) / 2}
                  fill="#94a3b8"
                  fontSize={8}
                  textAnchor="middle"
                  transform={`rotate(-90, ${b.x - 4}, ${(b.y1 + b.y2) / 2})`}
                  letterSpacing="1.5"
                >
                  {b.label.toUpperCase()}
                </text>
              </g>
            ))}
          </svg>
        </div>

        {/* Footer */}
        <div style={{ marginTop: 16, display: "flex", gap: 24, flexWrap: "wrap" }}>
          <div style={{ color: "#334155", fontSize: 11 }}>
            {Object.values(NODES).filter(n => n.type === "csv").length} CSV files ·{" "}
            {Object.values(NODES).filter(n => n.type === "api").length} external sources ·{" "}
            {Object.values(NODES).filter(n => n.type === "script").length} scripts ·{" "}
            {Object.values(NODES).filter(n => n.type === "output").length} outputs ·{" "}
            {EDGES.length} connections
          </div>
        </div>
      </div>
    </div>
  );
}

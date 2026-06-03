import { useMemo } from "react";
import { AGENT_CONFIG } from "../../config/agents";
import type { GraphState, Finding } from "../../types/api";
import type { ReasoningStep } from "../../types/events";

/**
 * Clean live agent graph: who-calls-whom topology (fan-out from recon,
 * fan-in to the analyst), live per-node status, per-agent tool usage, and a
 * compact execution trace. Pure SVG — no graph library dependency.
 */

interface Node {
  id: string;
  x: number;
  y: number;
}

// Layered top-down layout that fits the narrow detail panel (viewBox 360xH).
const NODES: Node[] = [
  { id: "recon", x: 180, y: 34 },
  { id: "crawler", x: 48, y: 120 },
  { id: "fuzzer", x: 136, y: 120 },
  { id: "vuln_scanner", x: 224, y: 120 },
  { id: "web_search", x: 312, y: 120 },
  { id: "exploit_analyst", x: 180, y: 210 },
  { id: "report_writer", x: 180, y: 292 },
];
const SSH_NODES: Node[] = [
  { id: "privesc", x: 90, y: 210 },
  { id: "tunnel_pivot", x: 270, y: 210 },
  { id: "post_exploit", x: 180, y: 250 },
];

const EDGES: [string, string][] = [
  ["recon", "crawler"],
  ["recon", "fuzzer"],
  ["recon", "vuln_scanner"],
  ["recon", "web_search"],
  ["crawler", "exploit_analyst"],
  ["fuzzer", "exploit_analyst"],
  ["vuln_scanner", "exploit_analyst"],
  ["web_search", "exploit_analyst"],
  ["exploit_analyst", "report_writer"],
];

const NW = 74;
const NH = 42;
const COLORS = { idle: "#33415570", active: "#3b82f6", done: "#10b981" };

type Status = "idle" | "active" | "done";

interface Props {
  graphState: GraphState;
  steps: ReasoningStep[];
  findings: Finding[];
  isLive: boolean;
}

export function AgentGraph({ graphState, steps, findings, isLive }: Props) {
  const stats = useMemo(() => {
    const s: Record<string, { tools: number; findings: number; lastTool: string }> = {};
    const get = (a: string) => (s[a] ??= { tools: 0, findings: 0, lastTool: "" });
    for (const st of steps) {
      if (!st.agent) continue;
      if (st.type === "tool_call") {
        get(st.agent).tools++;
        if (st.tool) get(st.agent).lastTool = st.tool;
      }
    }
    for (const f of findings) if (f.agent_source) get(f.agent_source).findings++;
    return s;
  }, [steps, findings]);

  const statusOf = (id: string): Status => {
    if ((graphState.completed_nodes || []).includes(id)) return "done";
    if ((graphState.active_nodes || []).includes(id)) return "active";
    if (steps.some((st) => st.agent === id && st.type === "agent_complete")) return "done";
    if (steps.some((st) => st.agent === id)) return "active";
    return "idle";
  };

  const sshActive = SSH_NODES.some(
    (n) => statusOf(n.id) !== "idle" || (graphState.active_nodes || []).includes(n.id),
  );
  const nodes = sshActive ? [...NODES, ...SSH_NODES] : NODES;
  const pos = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const height = 330;

  const edgeColor = (from: string): string => {
    const s = statusOf(from);
    return s === "done" ? COLORS.done : s === "active" ? COLORS.active : "#2a3548";
  };

  const trace = useMemo(
    () =>
      steps
        .filter((s) => ["agent_start", "tool_call", "tool_result", "finding", "agent_complete"].includes(s.type))
        .slice(-40)
        .reverse(),
    [steps],
  );

  return (
    <div className="p-2">
      <svg viewBox={`0 0 360 ${height}`} className="w-full" style={{ maxHeight: 360 }}>
        <defs>
          <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" fill="#3b5172" />
          </marker>
        </defs>

        {/* edges */}
        {EDGES.filter(([a, b]) => pos[a] && pos[b]).map(([a, b]) => {
          const s = pos[a], t = pos[b];
          const x1 = s.x, y1 = s.y + NH / 2, x2 = t.x, y2 = t.y - NH / 2;
          const my = (y1 + y2) / 2;
          const active = statusOf(a) !== "idle";
          return (
            <path
              key={`${a}-${b}`}
              d={`M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}`}
              fill="none"
              stroke={edgeColor(a)}
              strokeWidth={active ? 1.6 : 1}
              markerEnd="url(#arrow)"
              opacity={active ? 0.9 : 0.45}
            />
          );
        })}

        {/* nodes */}
        {nodes.map((n) => {
          const cfg = AGENT_CONFIG[n.id];
          if (!cfg) return null;
          const st = statusOf(n.id);
          const stat = stats[n.id];
          const stroke = st === "done" ? COLORS.done : st === "active" ? cfg.color : "#2f3b4f";
          const fill = st === "idle" ? "#0e1622" : `${cfg.color}14`;
          return (
            <g key={n.id} transform={`translate(${n.x - NW / 2},${n.y - NH / 2})`}>
              <rect
                width={NW} height={NH} rx={8}
                fill={st === "done" ? "#10b98114" : fill}
                stroke={stroke}
                strokeWidth={st === "active" ? 2 : 1}
              >
                {st === "active" && isLive && (
                  <animate attributeName="opacity" values="1;0.45;1" dur="1.4s" repeatCount="indefinite" />
                )}
              </rect>
              <circle cx={13} cy={NH / 2} r={7} fill={cfg.color} opacity={st === "idle" ? 0.4 : 1} />
              <text x={13} y={NH / 2 + 3} textAnchor="middle" fontSize="8" fontWeight="700" fill="#0b0f14">
                {cfg.abbrev}
              </text>
              <text x={26} y={NH / 2 - 2} fontSize="9" fontWeight="600"
                    fill={st === "idle" ? "#5b6b82" : "#dbe7f5"}>
                {cfg.shortLabel.slice(0, 8)}
              </text>
              <text x={26} y={NH / 2 + 9} fontSize="7.5" fill="#7488a3">
                {st === "idle"
                  ? "waiting"
                  : `${stat?.tools ?? 0}⚙ ${stat?.findings ?? 0}⬡`}
              </text>
            </g>
          );
        })}
      </svg>

      {/* legend */}
      <div className="flex items-center gap-3 px-2 mt-1 text-[9px] text-rw-dim">
        <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full inline-block" style={{ background: COLORS.active }} /> running</span>
        <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full inline-block" style={{ background: COLORS.done }} /> done</span>
        <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full inline-block bg-slate-600" /> waiting</span>
        {findings.length > 0 && <span className="ml-auto text-rw-accent">{findings.length} findings</span>}
      </div>

      {/* trace */}
      {trace.length > 0 && (
        <div className="mt-2 border-t border-rw-border pt-2">
          <div className="text-[9px] font-bold uppercase tracking-widest text-rw-dim/60 mb-1 px-1">Trace</div>
          <div className="max-h-48 overflow-auto space-y-0.5 px-1">
            {trace.map((s, i) => {
              const cfg = AGENT_CONFIG[s.agent || ""];
              return (
                <div key={i} className="flex items-start gap-1.5 text-[10px] leading-tight">
                  <span className="shrink-0 font-semibold" style={{ color: cfg?.color || "#7488a3" }}>
                    {cfg?.shortLabel || s.agent}
                  </span>
                  <span className="text-rw-dim/70 shrink-0">
                    {s.type === "tool_call" ? `⚙ ${s.tool || ""}` : s.type.replace("agent_", "")}
                  </span>
                  {s.content && <span className="text-rw-muted truncate">{s.content.slice(0, 60)}</span>}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import { Network, ShieldOff } from "lucide-react";
import { api } from "../../services/api";
import type { AttackGraph, GraphNode } from "../../services/api";
import { severityHex } from "../../config/theme";
import { EmptyState } from "../ui/EmptyState";
import { Spinner } from "../ui/Spinner";
import { cn } from "../../lib/cn";

interface Props {
  runId: string;
  className?: string;
}

/** Column order, left → right. Unknown types fall into a trailing "other" lane. */
const COLUMN_ORDER = ["target", "host", "service", "cve", "exploit"] as const;
const COLUMN_LABELS: Record<string, string> = {
  target: "Target",
  host: "Host",
  service: "Service",
  cve: "CVE",
  exploit: "Exploit",
  other: "Other",
};

/** Severity-driven types are colored by severity; structural types use accent. */
const SEVERITY_TYPES = new Set(["cve", "exploit"]);

const COL_W = 190;
const NODE_W = 152;
const NODE_H = 40;
const ROW_GAP = 18;
const TOP_PAD = 44;
const BOT_PAD = 24;

interface Placed {
  node: GraphNode;
  x: number;
  y: number;
  cx: number;
  cy: number;
}

function columnKey(type: string): string {
  const t = (type || "").toLowerCase();
  return (COLUMN_ORDER as readonly string[]).includes(t) ? t : "other";
}

function nodeColor(node: GraphNode): string {
  if (SEVERITY_TYPES.has(columnKey(node.type))) return severityHex(node.severity);
  return "#3b82f6";
}

/**
 * Renders an attack graph for a run as a layered left-to-right SVG: nodes are
 * grouped into columns by `type` (target → host → service → cve → exploit) and
 * edges are drawn as curved arrows between columns. Mirrors the dark SVG style
 * of AgentGraph; CVE / exploit nodes are tinted by severity.
 */
export function AttackGraphView({ runId, className }: Props) {
  const [graph, setGraph] = useState<AttackGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    setLoading(true);
    setError(false);
    api.runs
      .attackGraph(runId)
      .then((g) => {
        if (!cancelled) setGraph(g);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [runId]);

  const layout = useMemo(() => {
    const nodes = graph?.nodes ?? [];
    const columns = ["target", "host", "service", "cve", "exploit", "other"];
    const byCol: Record<string, GraphNode[]> = {};
    for (const c of columns) byCol[c] = [];
    for (const n of nodes) byCol[columnKey(n.type)].push(n);

    // Only render columns that actually contain nodes, keeping canonical order.
    const usedCols = columns.filter((c) => byCol[c].length > 0);
    const maxRows = usedCols.reduce((m, c) => Math.max(m, byCol[c].length), 0);

    const placed: Record<string, Placed> = {};
    usedCols.forEach((col, ci) => {
      const list = byCol[col];
      const colHeight = list.length * NODE_H + (list.length - 1) * ROW_GAP;
      const contentHeight = maxRows * NODE_H + (maxRows - 1) * ROW_GAP;
      const yStart = TOP_PAD + (contentHeight - colHeight) / 2;
      list.forEach((node, ri) => {
        const x = ci * COL_W + (COL_W - NODE_W) / 2;
        const y = yStart + ri * (NODE_H + ROW_GAP);
        placed[node.id] = {
          node,
          x,
          y,
          cx: x + NODE_W / 2,
          cy: y + NODE_H / 2,
        };
      });
    });

    const width = Math.max(usedCols.length * COL_W, COL_W);
    const height =
      TOP_PAD + maxRows * NODE_H + (maxRows - 1) * ROW_GAP + BOT_PAD;

    return { placed, usedCols, byCol, width, height };
  }, [graph]);

  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center">
        <Spinner size="md" label="Loading attack graph…" />
      </div>
    );
  }

  if (error) {
    return (
      <EmptyState
        icon={<ShieldOff size={32} />}
        title="Could not load attack graph"
        description="The attack graph for this run is unavailable. Try again shortly."
      />
    );
  }

  const nodes = graph?.nodes ?? [];
  if (nodes.length === 0) {
    return (
      <EmptyState
        icon={<Network size={32} />}
        title="No attack graph yet"
        description="Once the run correlates hosts, services, and CVEs into an attack path, it will be visualized here."
      />
    );
  }

  const edges = (graph?.edges ?? []).filter(
    (e) => layout.placed[e.source] && layout.placed[e.target],
  );

  return (
    <div
      className={cn(
        "overflow-x-auto rounded-xl border border-rw-border bg-rw-elevated p-4",
        className,
      )}
    >
      <svg
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        width={layout.width}
        height={layout.height}
        className="min-w-full"
      >
        <defs>
          <marker
            id="attack-arrow"
            markerWidth="7"
            markerHeight="7"
            refX="6"
            refY="3.5"
            orient="auto"
          >
            <path d="M0,0 L7,3.5 L0,7 Z" fill="#3b5172" />
          </marker>
        </defs>

        {/* column headers */}
        {layout.usedCols.map((col, ci) => (
          <text
            key={`hdr-${col}`}
            x={ci * COL_W + COL_W / 2}
            y={22}
            textAnchor="middle"
            fontSize="10"
            fontWeight="700"
            letterSpacing="1.5"
            fill="#8b9cb3"
          >
            {(COLUMN_LABELS[col] ?? col).toUpperCase()}
          </text>
        ))}

        {/* edges */}
        {edges.map((e, i) => {
          const s = layout.placed[e.source];
          const t = layout.placed[e.target];
          const x1 = s.x + NODE_W;
          const y1 = s.cy;
          const x2 = t.x;
          const y2 = t.cy;
          const mx = (x1 + x2) / 2;
          const d = `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;
          return (
            <path
              key={`edge-${i}`}
              d={d}
              fill="none"
              stroke="#2f3b4f"
              strokeWidth={1.4}
              opacity={0.7}
              markerEnd="url(#attack-arrow)"
            />
          );
        })}

        {/* nodes */}
        {nodes
          .map((n) => layout.placed[n.id])
          .filter(Boolean)
          .map((p) => {
            const color = nodeColor(p.node);
            return (
              <g key={p.node.id} transform={`translate(${p.x},${p.y})`}>
                <rect
                  width={NODE_W}
                  height={NODE_H}
                  rx={8}
                  fill={`${color}1f`}
                  stroke={color}
                  strokeWidth={1.4}
                />
                <rect width={4} height={NODE_H} rx={2} fill={color} />
                <text
                  x={14}
                  y={NODE_H / 2 + 3.5}
                  fontSize="10.5"
                  fontWeight="600"
                  fill="#dbe7f5"
                >
                  {p.node.label.length > 20
                    ? `${p.node.label.slice(0, 19)}…`
                    : p.node.label}
                </text>
              </g>
            );
          })}
      </svg>
    </div>
  );
}

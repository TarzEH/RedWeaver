import { Route } from "lucide-react";
import type { AttackChain } from "../../../services/api";
import { severityHex } from "../../../config/theme";
import { cn } from "../../../lib/cn";

interface AttackPathGraphProps {
  chains: AttackChain[];
  className?: string;
}

/* SVG layout constants for a single horizontal step flow. */
const NODE_W = 150;
const NODE_H = 56;
const GAP = 64; // horizontal space between steps (room for the edge + label)
const PAD_X = 8;
const PAD_Y = 12;
const ROW_H = NODE_H + PAD_Y * 2;

/** Wrap a step string into up to 3 lines for the fixed-width node box. */
function wrapLabel(text: string, maxChars = 20, maxLines = 3): string[] {
  const words = text.trim().split(/\s+/);
  const lines: string[] = [];
  let current = "";
  for (const w of words) {
    if ((current + " " + w).trim().length > maxChars && current) {
      lines.push(current);
      current = w;
    } else {
      current = (current + " " + w).trim();
    }
    if (lines.length === maxLines - 1 && current.length > maxChars) break;
  }
  if (current) lines.push(current);
  if (lines.length > maxLines) {
    const kept = lines.slice(0, maxLines);
    kept[maxLines - 1] = kept[maxLines - 1].slice(0, maxChars - 1) + "…";
    return kept;
  }
  return lines.length ? lines : [text];
}

function ChainFlow({ chain }: { chain: AttackChain }) {
  const steps = chain.steps ?? [];
  const accent = severityHex((chain.severity || "info").toLowerCase());
  const count = steps.length;
  const width = count > 0 ? count * NODE_W + (count - 1) * GAP + PAD_X * 2 : NODE_W + PAD_X * 2;

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${width} ${ROW_H}`}
        width={width}
        height={ROW_H}
        role="img"
        aria-label={`Attack path: ${chain.name}`}
        className="max-w-none"
      >
        <defs>
          <marker
            id={`apg-arrow-${chain.id}`}
            markerWidth="7"
            markerHeight="7"
            refX="6"
            refY="3.5"
            orient="auto"
          >
            <path d="M0,0 L7,3.5 L0,7 Z" fill={accent} />
          </marker>
        </defs>

        {steps.map((step, i) => {
          const x = PAD_X + i * (NODE_W + GAP);
          const y = PAD_Y;
          const cy = y + NODE_H / 2;
          const lines = wrapLabel(step);
          const startDy = -((lines.length - 1) * 6);
          return (
            <g key={i}>
              {/* edge from previous node */}
              {i > 0 && (
                <line
                  x1={x - GAP}
                  y1={cy}
                  x2={x - 4}
                  y2={cy}
                  stroke={accent}
                  strokeWidth={1.6}
                  opacity={0.7}
                  markerEnd={`url(#apg-arrow-${chain.id})`}
                />
              )}
              <rect
                x={x}
                y={y}
                width={NODE_W}
                height={NODE_H}
                rx={10}
                fill={`${accent}14`}
                stroke={`${accent}66`}
                strokeWidth={1.4}
              />
              {/* step index chip */}
              <circle cx={x + 14} cy={y + 14} r={9} fill={accent} />
              <text x={x + 14} y={y + 14 + 3} textAnchor="middle" fontSize="9" fontWeight="700" fill="#0b0f14">
                {i + 1}
              </text>
              <text
                x={x + NODE_W / 2 + 6}
                y={cy}
                textAnchor="middle"
                fontSize="10.5"
                fill="#dbe7f5"
              >
                {lines.map((ln, li) => (
                  <tspan key={li} x={x + NODE_W / 2 + 6} dy={li === 0 ? startDy : 12}>
                    {ln}
                  </tspan>
                ))}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function AttackPathGraph({ chains, className }: AttackPathGraphProps) {
  const list = chains ?? [];

  return (
    <div className={cn("rounded-xl border border-rw-border bg-rw-elevated p-4", className)}>
      <div className="mb-3 flex items-center gap-2">
        <Route size={16} className="text-rw-accent" />
        <span className="text-sm font-semibold text-rw-text">Attack Paths</span>
        <span className="ml-auto text-xs text-rw-dim">{list.length} chain{list.length === 1 ? "" : "s"}</span>
      </div>

      {list.length === 0 ? (
        <div className="flex h-24 items-center justify-center rounded-lg border border-dashed border-rw-border-subtle text-xs text-rw-dim">
          No attack chains were correlated for this assessment.
        </div>
      ) : (
        <div className="space-y-4">
          {list.map((chain) => {
            const accent = severityHex((chain.severity || "info").toLowerCase());
            return (
              <div key={chain.id} className="rounded-lg border border-rw-border-subtle bg-rw-surface/30 p-3">
                <div className="mb-2 flex items-start gap-2">
                  <span
                    aria-hidden
                    className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ background: accent }}
                  />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h4 className="truncate text-sm font-semibold text-rw-text">{chain.name}</h4>
                      <span
                        className="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide"
                        style={{ color: accent, background: `${accent}1f`, border: `1px solid ${accent}40` }}
                      >
                        {chain.severity}
                      </span>
                    </div>
                    {chain.description && (
                      <p className="mt-0.5 text-xs text-rw-dim">{chain.description}</p>
                    )}
                  </div>
                </div>
                <ChainFlow chain={chain} />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

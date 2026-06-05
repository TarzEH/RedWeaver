import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Server, Network, Cpu, ArrowUpDown, ShieldOff, Zap } from "lucide-react";
import { api } from "../../services/api";
import type { AssetInventory, AssetHost } from "../../services/api";
import type { Finding, Severity } from "../../types/api";
import { SEVERITY_ORDER, severityHex, severityStyle } from "../../config/theme";
import { EmptyState } from "../../components/ui/EmptyState";
import { Skeleton } from "../../components/ui/Skeleton";
import { cn } from "../../lib/cn";
import { ExposureCard } from "./ExposureCard";
import { PostureTrend } from "../../components/domain/PostureTrend";

type SortKey = "severity" | "findings";

/** Normalize an arbitrary severity string to a known Severity. */
function normSeverity(value: string): Severity {
  const v = value?.toLowerCase() as Severity;
  return SEVERITY_ORDER.includes(v) ? v : "info";
}

/** Rank for sorting — lower index (critical) sorts first when descending. */
function severityRank(value: string): number {
  return SEVERITY_ORDER.indexOf(normSeverity(value));
}

/**
 * The assets endpoint returns per-host max-severity + a finding count rather
 * than full Finding objects. Synthesize lightweight Finding stand-ins so the
 * ExposureCard can score the inventory: each host contributes one finding at
 * its max severity, plus the remaining findings at "low" (a conservative
 * floor we cannot resolve precisely from the summary payload).
 */
function syntheticFindings(assets: AssetHost[]): Finding[] {
  const out: Finding[] = [];
  for (const a of assets) {
    const sev = normSeverity(a.max_severity);
    const n = Math.max(a.findings, sev !== "info" ? 1 : 0);
    for (let i = 0; i < n; i++) {
      out.push({
        id: `${a.host}-${i}`,
        title: "",
        severity: i === 0 ? sev : "low",
        description: "",
        affected_url: a.host,
        agent_source: "asset-inventory",
        cve_ids: [],
        timestamp: "",
      });
    }
  }
  return out;
}

function MaxSeverityBadge({ severity }: { severity: string }) {
  const sev = normSeverity(severity);
  const s = severityStyle(sev);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide",
        s.bg,
        s.color,
        s.border,
      )}
    >
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: severityHex(sev) }}
        aria-hidden
      />
      {s.label}
    </span>
  );
}

function Chips({
  items,
  tone,
  empty,
}: {
  items: (string | number)[];
  tone: "accent" | "muted";
  empty: string;
}) {
  if (!items.length) {
    return <span className="text-[11px] text-rw-dim">{empty}</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((it) => (
        <span
          key={String(it)}
          className={cn(
            "rounded border px-1.5 py-0.5 font-mono text-[10px]",
            tone === "accent"
              ? "border-rw-accent/30 bg-rw-accent/10 text-rw-accent-hover"
              : "border-rw-border bg-rw-surface text-rw-muted",
          )}
        >
          {it}
        </span>
      ))}
    </div>
  );
}

function SortHeader({
  label,
  active,
  onClick,
  className,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  className?: string;
}) {
  return (
    <th className={cn("px-4 py-2.5", className)}>
      <button
        onClick={onClick}
        className={cn(
          "inline-flex items-center gap-1 transition-colors hover:text-rw-text",
          active ? "text-rw-text" : "text-rw-dim",
        )}
      >
        {label}
        <ArrowUpDown size={11} className={active ? "text-rw-accent" : "text-rw-dim"} />
      </button>
    </th>
  );
}

/**
 * Asset Inventory — a premium host grid for a session. One row per host with
 * its max-severity badge, open-port chips, technology chips, and finding
 * count. Sortable by severity or finding count; headed by an ExposureCard and
 * a compact severity summary.
 */
export function AssetInventoryPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [data, setData] = useState<AssetInventory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("severity");

  useEffect(() => {
    if (!sessionId) return;
    setLoading(true);
    setError(false);
    api.insights
      .assets(sessionId)
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [sessionId]);

  const assets = data?.assets ?? [];

  const sorted = useMemo(() => {
    const copy = [...assets];
    copy.sort((a, b) => {
      if (sortKey === "findings") {
        if (b.findings !== a.findings) return b.findings - a.findings;
        return severityRank(a.max_severity) - severityRank(b.max_severity);
      }
      // severity (default): most severe first, then by finding count
      const rank = severityRank(a.max_severity) - severityRank(b.max_severity);
      if (rank !== 0) return rank;
      return b.findings - a.findings;
    });
    return copy;
  }, [assets, sortKey]);

  const sevSummary = useMemo(() => {
    const counts: Record<Severity, number> = {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
      info: 0,
    };
    for (const a of assets) counts[normSeverity(a.max_severity)] += 1;
    return counts;
  }, [assets]);

  const exposureFindings = useMemo(() => syntheticFindings(assets), [assets]);

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl p-6">
        <div className="mb-5 flex items-end justify-between gap-4">
          <div className="space-y-2">
            <Skeleton className="h-7 w-56" />
            <Skeleton className="h-4 w-40" />
          </div>
          <div className="flex gap-1.5">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-7 w-16 rounded-md" />
            ))}
          </div>
        </div>
        <Skeleton className="mb-5 h-28 w-full rounded-xl" />
        <div className="space-y-2 rounded-xl border border-rw-border bg-rw-elevated p-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl p-6">
      {/* Header */}
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold text-rw-text">
            <Server size={22} className="text-rw-accent" />
            Asset Inventory
          </h1>
          <p className="mt-1 text-sm text-rw-dim">
            <span className="font-mono font-semibold text-rw-muted">
              {data?.asset_count ?? assets.length}
            </span>{" "}
            host{(data?.asset_count ?? assets.length) === 1 ? "" : "s"} discovered
            {sessionId && (
              <>
                {" "}
                · session{" "}
                <span className="font-mono text-rw-dim">{sessionId}</span>
              </>
            )}
          </p>
        </div>

        {/* Compact per-host max-severity summary */}
        <div className="flex flex-wrap gap-1.5">
          {SEVERITY_ORDER.map((sev) => (
            <div
              key={sev}
              className="flex items-center gap-1.5 rounded-md border border-rw-border bg-rw-surface px-2 py-1"
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: severityHex(sev) }}
                aria-hidden
              />
              <span className="text-[10px] font-medium capitalize text-rw-muted">
                {sev}
              </span>
              <span className="font-mono text-[11px] font-semibold text-rw-text">
                {sevSummary[sev]}
              </span>
            </div>
          ))}
        </div>
      </div>

      {error ? (
        <EmptyState
          icon={<ShieldOff size={32} />}
          title="Could not load assets"
          description="The asset inventory for this session is unavailable. Try again shortly."
        />
      ) : assets.length === 0 ? (
        <EmptyState
          icon={<Server size={32} />}
          title="No assets discovered"
          description="Once recon and scanning agents have mapped hosts for this session, they will appear here."
        />
      ) : (
        <>
          {/* Exposure header */}
          <ExposureCard
            className="mb-5"
            findings={exposureFindings}
            subtitle={`Across ${assets.length} host${assets.length === 1 ? "" : "s"} in this session`}
          />

          {/* Posture over time */}
          {sessionId && <div className="mb-5"><PostureTrend sessionId={sessionId} /></div>}

          {/* Host table */}
          <div className="overflow-hidden rounded-xl border border-rw-border bg-rw-elevated">
            <table className="w-full text-sm">
              <thead className="bg-rw-surface/50 text-left text-[11px] uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-2.5 text-rw-dim">Host</th>
                  <SortHeader
                    label="Max severity"
                    active={sortKey === "severity"}
                    onClick={() => setSortKey("severity")}
                  />
                  <th className="px-4 py-2.5 text-rw-dim">
                    <span className="inline-flex items-center gap-1">
                      <Network size={11} /> Open ports
                    </span>
                  </th>
                  <th className="px-4 py-2.5 text-rw-dim">
                    <span className="inline-flex items-center gap-1">
                      <Cpu size={11} /> Technologies
                    </span>
                  </th>
                  <th className="px-4 py-2.5 text-rw-dim">
                    <span className="inline-flex items-center gap-1">
                      <ShieldOff size={11} /> CVEs
                    </span>
                  </th>
                  <SortHeader
                    label="Findings"
                    active={sortKey === "findings"}
                    onClick={() => setSortKey("findings")}
                    className="text-right"
                  />
                </tr>
              </thead>
              <tbody>
                {sorted.map((host) => (
                  <tr
                    key={host.host}
                    className="border-t border-rw-border/60 transition-colors hover:bg-rw-surface/40"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        {host.screenshot && (
                          <img
                            src={host.screenshot}
                            alt={`Screenshot of ${host.host}`}
                            loading="lazy"
                            className="h-10 w-16 shrink-0 rounded border border-rw-border object-cover"
                            onError={(e) => {
                              e.currentTarget.style.display = "none";
                            }}
                          />
                        )}
                        <div className="flex min-w-0 flex-col gap-1">
                          <span className="truncate font-mono text-rw-text">{host.host}</span>
                          {host.exploit_available && (
                            <span className="inline-flex w-fit items-center gap-1 rounded border border-red-500/40 bg-red-500/15 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-red-400">
                              <Zap size={9} /> Exploit
                            </span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <MaxSeverityBadge severity={host.max_severity} />
                    </td>
                    <td className="max-w-xs px-4 py-3">
                      <Chips items={host.ports} tone="accent" empty="—" />
                    </td>
                    <td className="max-w-sm px-4 py-3">
                      <Chips items={host.technologies} tone="muted" empty="—" />
                    </td>
                    <td className="max-w-xs px-4 py-3">
                      <Chips items={host.cves} tone="muted" empty="—" />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="font-mono font-semibold text-rw-text">
                        {host.findings}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

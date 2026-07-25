import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Server, Network, Cpu, ArrowUpDown, ShieldOff, Zap } from "lucide-react";
import { api } from "../../services/api";
import type { AssetInventory, AssetHost } from "../../services/api";
import type { Finding, Severity } from "../../types/api";
import { SEVERITY_ORDER, severityHex } from "../../config/theme";
import { Card } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { SeverityBadge } from "../../components/ui/SeverityBadge";
import { Skeleton } from "../../components/ui/Skeleton";
import { Table, TableScroll, THead, TBody, TH, TR, TD } from "../../components/ui/Table";
import { PageHeader } from "../../components/layout/PageHeader";
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

/**
 * Per-severity count chip, shared by this page's header summary and the
 * ExposureCard breakdown. Label + count are always written out.
 */
function SeverityCountChip({ severity, count }: { severity: Severity; count: number }) {
  return (
    <div className="flex items-center gap-1.5 rounded-md border border-rw-border bg-rw-surface px-2 py-1">
      <span
        aria-hidden
        className="h-2 w-2 rounded-full"
        style={{ backgroundColor: severityHex(severity) }}
      />
      <span className="text-[10px] font-medium capitalize text-rw-muted">{severity}</span>
      <span className="font-mono text-[11px] font-semibold tabular-nums text-rw-text">{count}</span>
    </div>
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
    <TH className={className} aria-sort={active ? "descending" : "none"}>
      <button
        type="button"
        onClick={onClick}
        aria-label={`Sort by ${label}`}
        className={cn(
          "inline-flex items-center gap-1 rounded transition-colors hover:text-rw-text",
          active ? "text-rw-text" : "text-rw-dim",
        )}
      >
        {label}
        <ArrowUpDown size={11} aria-hidden className={active ? "text-rw-accent" : "text-rw-dim"} />
      </button>
    </TH>
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
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl p-6">
          <div className="mb-6 flex items-center justify-between gap-4">
            <div className="space-y-2">
              <Skeleton className="h-6 w-56" />
              <Skeleton className="h-4 w-40" />
            </div>
            <div className="flex gap-1.5">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-7 w-16 rounded-md" />
              ))}
            </div>
          </div>
          <Skeleton className="mb-5 h-28 w-full rounded-xl" />
          <Card padding="sm" className="space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </Card>
        </div>
      </div>
    );
  }

  const hostCount = data?.asset_count ?? assets.length;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-6xl p-6">
        <PageHeader
          title="Asset Inventory"
          subtitle={`${hostCount} host${hostCount === 1 ? "" : "s"} discovered${
            sessionId ? ` · session ${sessionId}` : ""
          }`}
          actions={
            /* Compact per-host max-severity summary */
            <div className="flex flex-wrap gap-1.5">
              {SEVERITY_ORDER.map((sev) => (
                <SeverityCountChip key={sev} severity={sev} count={sevSummary[sev]} />
              ))}
            </div>
          }
        />

      {error ? (
        <Card>
          <EmptyState
            icon={<ShieldOff size={32} />}
            title="Could not load assets"
            description="The asset inventory for this session is unavailable. Try again shortly."
          />
        </Card>
      ) : assets.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Server size={32} />}
            title="No assets discovered"
            description="Once recon and scanning agents have mapped hosts for this session, they will appear here."
          />
        </Card>
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
          <Card padding="none" className="overflow-hidden">
            <TableScroll label="Discovered hosts">
            <Table stickyHeader stickyFirstCol>
              <THead>
                <tr>
                  <TH>Host</TH>
                  <SortHeader
                    label="Max severity"
                    active={sortKey === "severity"}
                    onClick={() => setSortKey("severity")}
                  />
                  <TH>
                    <span className="inline-flex items-center gap-1">
                      <Network size={11} aria-hidden /> Open ports
                    </span>
                  </TH>
                  <TH>
                    <span className="inline-flex items-center gap-1">
                      <Cpu size={11} aria-hidden /> Technologies
                    </span>
                  </TH>
                  <TH>
                    <span className="inline-flex items-center gap-1">
                      <ShieldOff size={11} aria-hidden /> CVEs
                    </span>
                  </TH>
                  <SortHeader
                    label="Findings"
                    active={sortKey === "findings"}
                    onClick={() => setSortKey("findings")}
                    className="text-right"
                  />
                </tr>
              </THead>
              <TBody>
                {sorted.map((host) => (
                  <TR key={host.host} className="hover:bg-rw-surface/40">
                    <TD className="py-3">
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
                              <Zap size={9} aria-hidden /> Exploit
                            </span>
                          )}
                        </div>
                      </div>
                    </TD>
                    <TD className="py-3">
                      <SeverityBadge severity={normSeverity(host.max_severity)} dot />
                    </TD>
                    <TD className="max-w-xs py-3">
                      <Chips items={host.ports} tone="accent" empty="—" />
                    </TD>
                    <TD className="max-w-sm py-3">
                      <Chips items={host.technologies} tone="muted" empty="—" />
                    </TD>
                    <TD className="max-w-xs py-3">
                      <Chips items={host.cves} tone="muted" empty="—" />
                    </TD>
                    <TD className="py-3 text-right">
                      <span className="font-mono font-semibold tabular-nums text-rw-text">
                        {host.findings}
                      </span>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            </TableScroll>
          </Card>
        </>
      )}
      </div>
    </div>
  );
}

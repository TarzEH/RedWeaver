import { useMemo } from "react";
import { ShieldCheck, Users } from "lucide-react";
import { cn } from "../../../lib/cn";

interface VerificationSummaryProps {
  /** `false_positive_count` from `build_report()`. */
  falsePositiveCount?: number;
  /** `false_positive_titles` from `build_report()`. */
  falsePositiveTitles?: string[];
  /** `findings_by_agent` — agent name → count (false positives already excluded). */
  findingsByAgent?: Record<string, number>;
  className?: string;
}

const AGENT_LABELS: Record<string, string> = {
  recon: "Recon",
  crawler: "Crawler",
  vuln_scanner: "Vulnerability Scanner",
  fuzzer: "Fuzzer",
  web_search: "Web Search",
  exploit_analyst: "Exploit Analyst",
  report_writer: "Report Writer",
  verifier: "Verifier",
};

function agentLabel(name: string): string {
  return AGENT_LABELS[name] ?? name.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Two things `build_report()` returns that the report never showed: what the
 * verification pass **ruled out**, and which agent found what.
 *
 * The false-positive list matters because those findings are deliberately
 * excluded from the severity counts and the remediation plan — without this
 * panel they simply vanish, and a reader cannot tell a clean target from a
 * heavily-triaged one.
 */
export function VerificationSummary({
  falsePositiveCount,
  falsePositiveTitles,
  findingsByAgent,
  className,
}: VerificationSummaryProps) {
  const agents = useMemo(
    () =>
      Object.entries(findingsByAgent ?? {})
        .map(([name, count]) => ({ name, count: Number(count) || 0 }))
        .filter((a) => a.count > 0)
        .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name)),
    [findingsByAgent],
  );

  const fpCount = Number(falsePositiveCount ?? falsePositiveTitles?.length ?? 0) || 0;
  const titles = falsePositiveTitles ?? [];
  const agentMax = agents.reduce((m, a) => Math.max(m, a.count), 0);
  const agentTotal = agents.reduce((s, a) => s + a.count, 0);

  if (agents.length === 0 && fpCount === 0 && titles.length === 0) return null;

  return (
    <div className={cn("grid grid-cols-1 gap-6 lg:grid-cols-2", className)}>
      {agents.length > 0 && (
        <div className="rounded-xl border border-rw-border bg-rw-elevated p-4">
          <div className="mb-3 flex items-center gap-2">
            <Users size={15} className="text-rw-accent" aria-hidden />
            <span className="text-sm font-semibold text-rw-text">Findings by Agent</span>
            <span className="ml-auto text-xs text-rw-dim tabular-nums">{agentTotal} counted</span>
          </div>
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">
              Confirmed findings attributed to each agent in the hunt. Excludes findings ruled out as
              false positives. Each row is an agent and its finding count.
            </caption>
            <tbody>
              {agents.map((a) => (
                <tr key={a.name}>
                  <th
                    scope="row"
                    className="w-2/5 py-1 pr-3 text-left text-xs font-medium text-rw-muted"
                  >
                    {agentLabel(a.name)}
                  </th>
                  <td className="py-1">
                    <div className="flex items-center gap-2">
                      <div
                        aria-hidden
                        className="h-2 rounded-full bg-rw-accent"
                        style={{
                          width: `${agentMax > 0 ? Math.max(6, (a.count / agentMax) * 100) : 0}%`,
                        }}
                      />
                      <span className="text-xs font-semibold tabular-nums text-rw-text">
                        {a.count}
                      </span>
                      <span className="sr-only">
                        finding{a.count === 1 ? "" : "s"}
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="rounded-xl border border-rw-border bg-rw-elevated p-4">
        <div className="mb-3 flex items-center gap-2">
          <ShieldCheck size={15} className="text-rw-accent" aria-hidden />
          <span className="text-sm font-semibold text-rw-text">Ruled Out by Verification</span>
          <span className="ml-auto text-xs text-rw-dim tabular-nums">
            {fpCount} false positive{fpCount === 1 ? "" : "s"}
          </span>
        </div>
        {fpCount === 0 ? (
          <p className="text-xs leading-relaxed text-rw-dim">
            The verification pass did not rule out any reported finding.
          </p>
        ) : (
          <>
            <p className="mb-2 text-xs leading-relaxed text-rw-dim">
              Excluded from the severity counts, risk rating and remediation plan below.
            </p>
            <ul className="space-y-1">
              {titles.map((t, i) => (
                <li
                  key={`${t}-${i}`}
                  className="flex items-start gap-2 rounded-lg border border-rw-border-subtle bg-rw-surface/30 px-2.5 py-1.5 text-xs text-rw-muted"
                >
                  <span aria-hidden className="mt-0.5 font-mono text-[11px] text-rw-dim">
                    ✕
                  </span>
                  <span className="min-w-0 break-words line-through decoration-rw-dim/60">{t}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}

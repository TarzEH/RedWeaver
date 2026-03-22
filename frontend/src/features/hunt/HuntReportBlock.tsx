import { useEffect, useState } from "react";
import { FileText, Download } from "lucide-react";
import { MarkdownRenderer } from "../../components/domain/MarkdownRenderer";
import { Spinner } from "../../components/ui/Spinner";
import { buildReportMarkdown } from "../report/buildReportMarkdown";
import { api } from "../../services/api";
import { ApiError } from "../../services/http";
import type { VulnerabilityReport } from "../../types/api";
import { useHuntContext } from "../../contexts/HuntContext";

interface HuntReportBlockProps {
  runId: string | null;
  onContentLoaded?: () => void;
}

/**
 * Full-width Markdown report in the hunt thread — infographic-style card with enhanced typography.
 */
export function HuntReportBlock({ runId, onContentLoaded }: HuntReportBlockProps) {
  const [report, setReport] = useState<VulnerabilityReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { done } = useHuntContext();

  useEffect(() => {
    if (!runId) {
      setReport(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setReport(null);
    setError(null);
    setLoading(true);
    api.runs
      .report(runId)
      .then((r) => {
        if (!cancelled) setReport(r);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setReport(null);
          setError(
            e instanceof ApiError ? `${e.status}: ${e.message}` : e instanceof Error ? e.message : "Failed to load",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [runId, done]);

  useEffect(() => {
    if (report && !loading) onContentLoaded?.();
  }, [report, loading, onContentLoaded]);

  if (!runId) return null;

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-6 text-rw-dim text-xs">
        <Spinner size="sm" />
        <span>Loading report…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-xs text-rw-dim border border-rw-border/60 rounded-lg px-3 py-2 bg-rw-surface/50">
        Report: {error}
      </div>
    );
  }

  if (!report) return null;

  const hasBody =
    Boolean(report.report_markdown?.trim()) ||
    Boolean(report.executive_summary?.trim()) ||
    Boolean(report.methodology?.trim()) ||
    (report.findings?.length ?? 0) > 0;

  if (!hasBody) {
    return (
      <div className="text-xs text-rw-dim italic border border-dashed border-rw-border rounded-lg px-3 py-2">
        Final report will appear here when the assessment finishes.
      </div>
    );
  }

  const markdown = buildReportMarkdown(report);

  return (
    <section className="huntReportInfographic animate-fade-in" aria-label="Penetration test report">
      <div className="huntReportInfographic__header">
        <div className="flex items-center gap-2 min-w-0">
          <div className="shrink-0 w-9 h-9 rounded-lg bg-gradient-to-br from-sky-500/20 to-violet-600/20 border border-white/10 flex items-center justify-center">
            <FileText size={18} className="text-sky-300" />
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-rw-text tracking-tight">Assessment report</h3>
            <p className="text-[10px] text-rw-dim truncate font-mono">{report.target}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            const blob = new Blob([markdown], { type: "text/markdown" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `report-${runId.slice(0, 8)}.md`;
            a.click();
            URL.revokeObjectURL(url);
          }}
          className="shrink-0 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-sky-300/90 hover:text-sky-200 border border-sky-500/30 rounded-md px-2 py-1.5 transition-colors"
        >
          <Download size={12} />
          .md
        </button>
      </div>
      <div className="huntReportInfographic__body">
        <MarkdownRenderer content={markdown} variant="enhanced" className="huntReportInfographic__md" />
      </div>
    </section>
  );
}

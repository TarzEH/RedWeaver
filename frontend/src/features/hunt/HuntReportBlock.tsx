import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FileText, Download, Printer, LayoutDashboard, GitCompare } from "lucide-react";
import { MarkdownRenderer } from "../../components/domain/MarkdownRenderer";
import { Spinner } from "../../components/ui/Spinner";
import { buildReportMarkdown } from "../report/buildReportMarkdown";
import { api } from "../../services/api";
import { ApiError, getToken } from "../../services/http";
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

  const downloadMd = () => {
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `report-${runId.slice(0, 8)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadExport = async (fmt: "json" | "csv" | "sarif" | "html") => {
    const token = getToken();
    const res = await fetch(`/api/runs/${runId}/report/export?fmt=${fmt}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `redweaver-${runId.slice(0, 8)}.${fmt}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportBtn = "shrink-0 rounded-md border border-rw-border px-2 py-1.5 text-[10px] font-medium uppercase tracking-wider text-rw-muted transition-colors hover:border-rw-accent/40 hover:text-rw-text";

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
        <div className="flex shrink-0 items-center gap-1.5">
          <Link to={`/hunt/${runId}/report`} className={`${exportBtn} inline-flex items-center gap-1 !text-rw-accent-hover !border-rw-accent/30`} title="Open the premium visual report">
            <LayoutDashboard size={12} /> Visual
          </Link>
          <Link to={`/hunt/${runId}/compare`} className={`${exportBtn} inline-flex items-center gap-1`} title="Compare with another run">
            <GitCompare size={12} /> Diff
          </Link>
          <button type="button" onClick={downloadMd} className={`${exportBtn} inline-flex items-center gap-1`} title="Download Markdown">
            <Download size={12} /> MD
          </button>
          <button type="button" onClick={() => downloadExport("html")} className={exportBtn} title="Download HTML report">HTML</button>
          <button type="button" onClick={() => downloadExport("json")} className={exportBtn} title="Download JSON">JSON</button>
          <button type="button" onClick={() => downloadExport("csv")} className={exportBtn} title="Download CSV">CSV</button>
          <button type="button" onClick={() => downloadExport("sarif")} className={exportBtn} title="Download SARIF (CI/CD)">SARIF</button>
          <button type="button" onClick={() => window.print()} className={`${exportBtn} inline-flex items-center gap-1`} title="Print / Save as PDF">
            <Printer size={12} /> PDF
          </button>
        </div>
      </div>
      <div className="huntReportInfographic__body">
        <MarkdownRenderer content={markdown} variant="enhanced" className="huntReportInfographic__md" />
      </div>
    </section>
  );
}

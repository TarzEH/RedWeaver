import { useEffect, useState } from "react";
import { FileText, Download, AlertCircle } from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Spinner";
import { EmptyState } from "../../components/ui/EmptyState";
import { SeverityBadge } from "../../components/ui/SeverityBadge";
import {
  MarkdownRenderer,
  REPORT_VIEW_STORAGE_KEY,
  type MarkdownRendererVariant,
} from "../../components/domain/MarkdownRenderer";
import { api } from "../../services/api";
import { ApiError } from "../../services/http";
import type { VulnerabilityReport, Severity } from "../../types/api";
import { buildReportMarkdown } from "./buildReportMarkdown";

function readStoredReportView(): MarkdownRendererVariant {
  if (typeof window === "undefined") return "default";
  try {
    return sessionStorage.getItem(REPORT_VIEW_STORAGE_KEY) === "enhanced" ? "enhanced" : "default";
  } catch {
    return "default";
  }
}

function persistReportView(mode: MarkdownRendererVariant) {
  try {
    sessionStorage.setItem(REPORT_VIEW_STORAGE_KEY, mode);
  } catch {
    /* ignore */
  }
}

interface ReportPageProps {
  runId: string | null;
  compact?: boolean;
}

export function ReportPage({ runId, compact = false }: ReportPageProps) {
  const [report, setReport] = useState<VulnerabilityReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [markdownView, setMarkdownView] = useState<MarkdownRendererVariant>(readStoredReportView);

  useEffect(() => {
    if (!runId) {
      setReport(null);
      setLoadError(null);
      return;
    }
    setReport(null);
    setLoadError(null);
    setLoading(true);
    api.runs
      .report(runId)
      .then(setReport)
      .catch((e: unknown) => {
        setReport(null);
        const msg =
          e instanceof ApiError ? `${e.status}: ${e.message}` : e instanceof Error ? e.message : "Failed to load report";
        setLoadError(msg);
      })
      .finally(() => setLoading(false));
  }, [runId]);

  if (!runId) {
    return <EmptyState icon={<FileText size={28} />} title="Select a hunt to view the report." />;
  }

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center min-h-[8rem]">
        <Spinner size="md" />
      </div>
    );
  }

  if (loadError) {
    return (
      <EmptyState
        icon={<AlertCircle size={28} />}
        title="Could not load report"
        description={loadError}
      />
    );
  }

  if (!report) {
    return (
      <EmptyState
        icon={<AlertCircle size={28} />}
        title="No report data"
        description="Try again after the hunt finishes."
      />
    );
  }

  const hasBody =
    Boolean(report.report_markdown?.trim()) ||
    Boolean(report.executive_summary?.trim()) ||
    Boolean(report.methodology?.trim()) ||
    (report.findings?.length ?? 0) > 0;

  if (!hasBody) {
    return (
      <EmptyState
        icon={<AlertCircle size={28} />}
        title="No report available yet."
        description="Run a hunt to completion so the Report Writer can generate Markdown."
      />
    );
  }

  const markdown = buildReportMarkdown(report);
  const sevCounts = report.total_by_severity || report.findings_by_severity || {};
  const totalFindings = report.findings?.length || 0;

  if (compact) {
    return (
      <div className="flex flex-col flex-1 min-h-0 gap-2 p-2">
        <div className="flex items-center justify-between gap-2 shrink-0">
          <span className="text-xs font-medium text-rw-muted truncate">Report</span>
          <div className="flex items-center gap-1 shrink-0">
            {report.risk_rating && (
              <SeverityBadge severity={report.risk_rating as Severity} className="text-[10px]" />
            )}
            <button
              type="button"
              onClick={() => {
                const next = markdownView === "enhanced" ? "default" : "enhanced";
                setMarkdownView(next);
                persistReportView(next);
              }}
              className="text-[10px] px-2 py-0.5 rounded border border-rw-border text-rw-dim hover:text-rw-muted"
            >
              {markdownView === "enhanced" ? "Standard" : "Enhanced"}
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-1.5 text-xs shrink-0">
          <div className="bg-rw-surface rounded p-2">
            <span className="text-rw-dim block text-[10px]">Findings</span>
            <span className="text-rw-text font-medium">{totalFindings}</span>
          </div>
          <div className="bg-rw-surface rounded p-2">
            <span className="text-rw-dim block text-[10px]">Agents</span>
            <span className="text-rw-text font-medium">{report.agents_executed?.length || 0}</span>
          </div>
        </div>
        {Object.keys(sevCounts).length > 0 && (
          <div className="flex flex-wrap gap-1 shrink-0">
            {Object.entries(sevCounts).map(([sev]) => (
              <SeverityBadge key={sev} severity={sev as Severity} className="text-[10px]" />
            ))}
          </div>
        )}
        <div className="flex-1 min-h-0 overflow-y-auto rounded-lg border border-rw-border bg-rw-surface/50 p-2">
          <MarkdownRenderer
            content={markdown}
            variant={markdownView}
            className="!text-xs leading-relaxed"
          />
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-xl font-semibold text-rw-text flex items-center gap-2">
            <FileText size={20} className="text-rw-accent" />
            Penetration Testing Report
          </h1>
          <p className="text-xs text-rw-dim mt-1">Target: {report.target}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] text-rw-dim uppercase tracking-wider mr-1 hidden sm:inline">View</span>
          <div className="inline-flex rounded-lg border border-rw-border overflow-hidden">
            <button
              type="button"
              onClick={() => {
                setMarkdownView("default");
                persistReportView("default");
              }}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                markdownView === "default"
                  ? "bg-rw-accent text-white"
                  : "bg-rw-surface text-rw-muted hover:bg-rw-surface-hover"
              }`}
            >
              Standard
            </button>
            <button
              type="button"
              onClick={() => {
                setMarkdownView("enhanced");
                persistReportView("enhanced");
              }}
              className={`px-3 py-1.5 text-xs font-medium border-l border-rw-border transition-colors ${
                markdownView === "enhanced"
                  ? "bg-rw-accent text-white"
                  : "bg-rw-surface text-rw-muted hover:bg-rw-surface-hover"
              }`}
            >
              Enhanced
            </button>
          </div>
          <Button
            variant="secondary"
            size="sm"
            icon={<Download size={12} />}
            onClick={() => {
              const blob = new Blob([markdown], { type: "text/markdown" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `report-${runId?.slice(0, 8)}.md`;
              a.click();
            }}
          >
            Markdown
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3 mb-6">
        {[
          {
            label: "Risk Rating",
            value: (report.risk_rating || "N/A").toUpperCase(),
            color:
              report.risk_rating === "critical"
                ? "text-red-400"
                : report.risk_rating === "high"
                  ? "text-orange-400"
                  : "text-yellow-400",
          },
          { label: "Total Findings", value: String(totalFindings), color: "text-rw-text" },
          { label: "Agents Used", value: String(report.agents_executed?.length || 0), color: "text-rw-accent" },
          { label: "Tools Used", value: String(report.tools_used?.length || 0), color: "text-rw-muted" },
        ].map((s) => (
          <Card key={s.label} padding="sm">
            <span className="text-[10px] text-rw-dim uppercase tracking-wider block mb-1">{s.label}</span>
            <span className={`text-lg font-bold ${s.color}`}>{s.value}</span>
          </Card>
        ))}
      </div>

      <Card padding="lg" className="max-w-4xl">
        <MarkdownRenderer content={markdown} variant={markdownView} />
      </Card>
    </div>
  );
}

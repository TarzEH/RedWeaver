import type { VulnerabilityReport } from "../../types/api";

/** LLM report often claims "0 findings" while Redis has the real list — same heuristics as backend reconcile. */
function narrativeClaimsZeroButHasFindings(markdown: string): boolean {
  const low = markdown.toLowerCase();
  if (/identified\s+0\s+finding/.test(low)) return true;
  if (
    /0\s+critical,\s*0\s+high,\s*0\s+medium,\s*(?:0\s+low,\s*)?(?:and\s*)?0\s+informational/.test(low)
  )
    return true;
  return false;
}

/** Build Markdown for display when `report_markdown` is empty but structured fields exist. */
export function buildReportMarkdown(report: VulnerabilityReport): string {
  const md = report.report_markdown?.trim();
  const n = report.findings?.length ?? 0;
  const exec = report.executive_summary?.trim();

  if (md) {
    // Prefer API summary when the stored narrative contradicts finding count (report_writer missed context).
    if (n > 0 && exec && narrativeClaimsZeroButHasFindings(md)) {
      const replaced = md.replace(
        /^##\s*Executive\s+summary\b[^\n]*\n[\s\S]*?(?=\n##\s[^\n#]|\n#\s[^\n#]|$)/im,
        `## Executive summary\n\n${exec}\n\n---\n\n`,
      );
      return replaced !== md ? replaced : `## Executive summary\n\n${exec}\n\n---\n\n${md}`;
    }
    return md;
  }
  const parts: string[] = [`# Report`, ``];
  if (report.executive_summary?.trim()) {
    parts.push(`## Executive Summary`, ``, report.executive_summary.trim());
  }
  if (report.methodology?.trim()) {
    parts.push(``, `## Methodology`, ``, report.methodology.trim());
  }
  if (report.findings?.length) {
    parts.push(``, `## Findings`, ``);
    for (const f of report.findings) {
      parts.push(`- **${f.severity?.toUpperCase() ?? "INFO"}** ${f.title}`, ``);
    }
  }
  return parts.join("\n") || `_No narrative report yet. Run the hunt to completion for a full Markdown report._`;
}

import type { RunMessage } from "../types/api";

/**
 * Remove assistant chat bubbles that duplicate the structured report (legacy runs stored
 * full `report_markdown` as a message; the infographic block loads the same from the API).
 */
export function filterDuplicateReportFromMessages(
  messages: RunMessage[],
  reportMarkdown: string | undefined,
): RunMessage[] {
  const rm = reportMarkdown?.trim();

  return messages.filter((m) => {
    if (m.role !== "assistant" || !m.content) return true;
    const c = m.content.trim();

    if (rm && rm.length >= 40) {
      if (c === rm) return false;
      const n = Math.min(c.length, rm.length, 4000);
      if (n >= 200 && c.slice(0, n) === rm.slice(0, n)) return false;
    }

    if (!rm && isLikelyEmbeddedReportOnlyMessage(c)) return false;

    return true;
  });
}

/** Heuristic for old Redis rows without graph_state.report_markdown populated. */
function isLikelyEmbeddedReportOnlyMessage(content: string): boolean {
  if (content.length < 600) return false;
  if (!/^#\s+/m.test(content)) return false;
  const markers = ["## Executive Summary", "## Detailed Findings", "## Target Overview", "## Methodology"];
  const hits = markers.filter((x) => content.includes(x)).length;
  return hits >= 2;
}

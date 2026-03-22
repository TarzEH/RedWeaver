const REPORT_VIEW_STORAGE_KEY = "rw.reportMarkdownView";

export type MarkdownRendererVariant = "default" | "enhanced";

interface MarkdownRendererProps {
  content: string;
  className?: string;
  /** Enhanced applies larger typography and spacing (see `index.css`). */
  variant?: MarkdownRendererVariant;
}

export function MarkdownRenderer({ content, className, variant = "default" }: MarkdownRendererProps) {
  const html = markdownToHtml(content);
  const variantClass = variant === "enhanced" ? "markdownRenderer--enhanced" : "";
  return (
    <div
      className={`markdownRenderer ${variantClass} ${className || ""}`.trim()}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

export { REPORT_VIEW_STORAGE_KEY };

function markdownToHtml(md: string): string {
  let html = escapeHtml(md);

  const codeBlocks: string[] = [];
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_m, lang, code) => {
    const idx = codeBlocks.length;
    const langClass = lang ? ` data-lang="${lang}"` : "";
    codeBlocks.push(`<pre class="mdCodeBlock"${langClass}><code>${code.trim()}</code></pre>`);
    return `%%CODEBLOCK_${idx}%%`;
  });

  const inlineCodes: string[] = [];
  html = html.replace(/`([^`]+)`/g, (_m, code) => {
    const idx = inlineCodes.length;
    inlineCodes.push(`<code class="mdInlineCode">${code}</code>`);
    return `%%INLINECODE_${idx}%%`;
  });

  html = html.replace(/(?:^|\n)((?:\|[^\n]+\|\n)+)/g, (_m, tableBlock: string) => "\n" + parseTable(tableBlock.trim()) + "\n");
  html = html.replace(/((?:^&gt; .+\n?)+)/gm, (_m, block: string) => {
    const firstLine = block.split("\n")[0]?.replace(/^&gt; ?/, "").trim() ?? "";
    let callout = "";
    const label = firstLine.match(/^\*\*(Note|Tip|Warning|Important):\*\*/);
    if (label) {
      callout = ` mdCallout mdCallout--${label[1].toLowerCase()}`;
    }
    const inner = block.split("\n").map((line) => line.replace(/^&gt; ?/, "")).join("<br />");
    return `<blockquote class="mdBlockquote${callout}">${inner}</blockquote>`;
  });

  html = html.replace(/^#### (.+)$/gm, '<h4 class="mdH4">$1</h4>');
  html = html.replace(/^### (.+)$/gm, '<h3 class="mdH3">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 class="mdH2">$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1 class="mdH1">$1</h1>');
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a class="mdLink" href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  html = html.replace(/^---$/gm, '<hr class="mdHr" />');
  html = html.replace(/^\d+\. (.+)$/gm, '<li class="mdOlLi">$1</li>');
  html = html.replace(/((?:<li class="mdOlLi">.*<\/li>\n?)+)/g, '<ol class="mdOl">$1</ol>');
  html = html.replace(/^- (.+)$/gm, '<li class="mdLi">$1</li>');
  html = html.replace(/((?:<li class="mdLi">.*<\/li>\n?)+)/g, '<ul class="mdUl">$1</ul>');
  html = html.replace(/\n\n/g, "</p><p>");
  html = `<p>${html}</p>`;
  html = html.replace(/<p><\/p>/g, "");
  html = html.replace(/<p>(<h[1-4])/g, "$1");
  html = html.replace(/(<\/h[1-4]>)<\/p>/g, "$1");
  html = html.replace(/<p>(<pre)/g, "$1");
  html = html.replace(/(<\/pre>)<\/p>/g, "$1");
  html = html.replace(/<p>(<ul)/g, "$1");
  html = html.replace(/(<\/ul>)<\/p>/g, "$1");
  html = html.replace(/<p>(<ol)/g, "$1");
  html = html.replace(/(<\/ol>)<\/p>/g, "$1");
  html = html.replace(/<p>(<hr)/g, "$1");
  html = html.replace(/<p>(<table)/g, "$1");
  html = html.replace(/(<\/table>)<\/p>/g, "$1");
  html = html.replace(/<p>(<blockquote)/g, "$1");
  html = html.replace(/(<\/blockquote>)<\/p>/g, "$1");
  html = html.replace(/\n/g, "<br />");

  for (let i = 0; i < codeBlocks.length; i++) html = html.replace(`%%CODEBLOCK_${i}%%`, codeBlocks[i]);
  for (let i = 0; i < inlineCodes.length; i++) html = html.replace(`%%INLINECODE_${i}%%`, inlineCodes[i]);

  return html;
}

function parseTable(tableStr: string): string {
  const rows = tableStr.split("\n").filter((r) => r.trim());
  if (rows.length < 2) return tableStr;
  const hasSeparator = rows.length >= 2 && /^[\s|:-]+$/.test(rows[1].replace(/[^|:-\s]/g, ""));
  const parseCells = (row: string) => row.split("|").slice(1, -1).map((c) => c.trim());
  let thead = "";
  let startIdx = 0;
  if (hasSeparator) {
    const headerCells = parseCells(rows[0]);
    thead = `<thead><tr>${headerCells.map((c) => `<th>${c}</th>`).join("")}</tr></thead>`;
    startIdx = 2;
  }
  const bodyRows = rows.slice(startIdx);
  const tbody = bodyRows.map((row) => { const cells = parseCells(row); return `<tr>${cells.map((c) => `<td>${c}</td>`).join("")}</tr>`; }).join("");
  return `<table class="mdTable">${thead}<tbody>${tbody}</tbody></table>`;
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

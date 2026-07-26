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

/* ------------------------------------------------------------------ *
 * SECURITY CORE
 *
 * This renderer feeds `dangerouslySetInnerHTML`, and the markdown it
 * renders is model output derived from content scraped off the target
 * under scan - i.e. attacker-influenced. Every value that reaches the
 * generated HTML must go through the helpers below.
 *
 * Two rules:
 *   1. Text -> `escapeHtml`. It covers text nodes AND quoted attribute
 *      values: `"` and `'` are escaped, so an attribute cannot be
 *      broken out of.
 *   2. URLs -> `sanitizeUrl`, which allow-lists the scheme. Escaping
 *      alone does not stop `javascript:` or `data:text/html`.
 *
 * The helpers are exported so they can be unit-tested in isolation.
 * ------------------------------------------------------------------ */

/** Schemes permitted on `<a href>`. Everything else is dropped. */
export const ALLOWED_LINK_SCHEMES: readonly string[] = ["http", "https", "mailto"];
/** Schemes permitted on `<img src>`. Narrower: no `mailto`, no `data:`. */
export const ALLOWED_IMAGE_SCHEMES: readonly string[] = ["http", "https"];

/**
 * Escape text for insertion into an HTML text node *or* a quoted
 * attribute value.
 *
 * `&` MUST be replaced first, otherwise the ampersands introduced by the
 * later replacements get escaped a second time and the user sees a
 * literal `&amp;lt;`.
 */
export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Exact inverse of `escapeHtml` (reverse order, `&amp;` last). Used to
 * recover the author's original URL text before scheme validation, so
 * `sanitizeUrl` can be reasoned about - and tested - on raw input.
 */
export function unescapeHtml(text: string): string {
  return text
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&gt;/g, ">")
    .replace(/&lt;/g, "<")
    .replace(/&amp;/g, "&");
}

const NAMED_ENTITIES: Readonly<Record<string, string>> = {
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
  colon: ":",
  tab: "\t",
  newline: "\n",
  sol: "/",
  nbsp: " ",
  semi: ";",
  num: "#",
  lpar: "(",
  rpar: ")",
};

/**
 * Decode HTML entities. Deliberately lenient (trailing `;` optional,
 * case-insensitive named refs): this is only ever used to build the
 * *probe* string for scheme detection, never to build output, so
 * over-decoding can only cause a URL to be rejected, never accepted.
 */
export function decodeEntities(value: string): string {
  return value.replace(/&(#[xX][0-9a-fA-F]+|#[0-9]+|[a-zA-Z][a-zA-Z0-9]*);?/g, (match, body: string) => {
    if (body[0] === "#") {
      const codePoint =
        body[1] === "x" || body[1] === "X"
          ? Number.parseInt(body.slice(2), 16)
          : Number.parseInt(body.slice(1), 10);
      if (!Number.isFinite(codePoint) || codePoint < 0 || codePoint > 0x10ffff) return match;
      try {
        return String.fromCodePoint(codePoint);
      } catch {
        return match;
      }
    }
    const named = NAMED_ENTITIES[body.toLowerCase()];
    return named === undefined ? match : named;
  });
}

/** C0 controls (incl. tab/newline) and DEL - never legitimate in a URL. */
function isControlChar(code: number): boolean {
  return code <= 0x1f || code === 0x7f;
}

/**
 * Anything invisible: controls, every flavour of space, C1 range, the
 * bidi/zero-width block, line & paragraph separators, and the BOM.
 * Written with char codes on purpose - a regex class of `\x..` escapes
 * is far too easy to get subtly wrong.
 */
function isInvisibleChar(code: number): boolean {
  if (code <= 0x20 || code === 0x7f) return true; // controls + space
  if (code >= 0x80 && code <= 0xa0) return true; // C1 + NBSP
  if (code === 0x1680) return true; // OGHAM SPACE MARK
  if (code >= 0x2000 && code <= 0x200f) return true; // en/em spaces, ZWSP, bidi marks
  if (code >= 0x2028 && code <= 0x202f) return true; // LS, PS, bidi embedding, NNBSP
  if (code >= 0x205f && code <= 0x2060) return true; // MMSP, word joiner
  if (code >= 0x2066 && code <= 0x2069) return true; // bidi isolates
  if (code === 0x3000) return true; // IDEOGRAPHIC SPACE
  if (code === 0xfeff) return true; // BOM / ZWNBSP
  return false;
}

function filterChars(value: string, drop: (code: number) => boolean): string {
  let out = "";
  for (let i = 0; i < value.length; i++) {
    if (!drop(value.charCodeAt(i))) out += value[i];
  }
  return out;
}

/**
 * Normalise a URL for scheme inspection: repeatedly decode entities (so
 * `&amp;#58;` -> `&#58;` -> `:` is caught), strip every invisible
 * character (so `java<TAB>script:` and a leading-space `javascript:`
 * both collapse), then lowercase.
 */
function schemeProbe(rawUrl: string): string {
  let probe = rawUrl;
  for (let i = 0; i < 4; i++) {
    const decoded = decodeEntities(probe);
    if (decoded === probe) break;
    probe = decoded;
  }
  return filterChars(probe, isInvisibleChar).toLowerCase();
}

/**
 * Validate a URL against a scheme allow-list.
 *
 * Takes the *raw* (unescaped) URL and returns the cleaned raw URL, or
 * `null` if it must not be emitted. Callers must still run `escapeHtml`
 * on the result before putting it into an attribute.
 *
 * Accepted: allow-listed absolute schemes, plus scheme-less URLs
 * (relative paths, `#anchor`, query-only, protocol-relative `//host`).
 * Everything else - `javascript:`, `data:`, `vbscript:`, `file:` and any
 * obfuscated spelling of them - is rejected.
 */
export function sanitizeUrl(
  rawUrl: string,
  allowedSchemes: readonly string[] = ALLOWED_LINK_SCHEMES,
): string | null {
  if (typeof rawUrl !== "string") return null;

  // Control characters never belong in a URL and are the classic way to
  // smuggle `java<TAB>script:` past a naive check. Drop them outright.
  const cleaned = filterChars(rawUrl, isControlChar).trim();
  if (!cleaned) return null;

  const probe = schemeProbe(cleaned);
  if (!probe) return null;

  // Browsers normalise `\` to `/`; do not let it disguise the target.
  if (probe.startsWith("\\") || probe.startsWith("/\\")) return null;

  const schemeMatch = /^([a-z][a-z0-9+.-]*):/.exec(probe);
  if (schemeMatch) {
    return allowedSchemes.includes(schemeMatch[1]) ? cleaned : null;
  }

  // No scheme => relative / anchor / protocol-relative. Safe: it can only
  // resolve against the current document's http(s) origin.
  return cleaned;
}

/**
 * Sanitize a URL that arrived already HTML-escaped (as everything in this
 * pipeline has) and return a value ready to drop into a quoted attribute,
 * or `null` if the URL is not allowed.
 */
function sanitizeEscapedUrlForAttribute(
  escapedUrl: string,
  allowedSchemes: readonly string[],
): string | null {
  const safe = sanitizeUrl(unescapeHtml(escapedUrl), allowedSchemes);
  return safe === null ? null : escapeHtml(safe);
}

/* ------------------------------------------------------------------ *
 * RENDERER
 * ------------------------------------------------------------------ */

/** Sentinels used to park finished HTML so later passes cannot rewrite it. */
const SENTINEL = /%%(?:CODEBLOCK|INLINECODE|MDIMAGE)_\d+%%/g;

export function markdownToHtml(md: string): string {
  // Strip any literal sentinel the author (i.e. the model, i.e. the
  // scanned target) may have written, so it cannot hijack a restore slot.
  let html = escapeHtml(String(md ?? "").replace(SENTINEL, ""));

  const codeBlocks: string[] = [];
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_m, lang: string, code: string) => {
    const idx = codeBlocks.length;
    const langClass = lang ? ` data-lang="${escapeHtml(lang)}"` : "";
    codeBlocks.push(`<pre class="mdCodeBlock"${langClass}><code>${code.trim()}</code></pre>`);
    return `%%CODEBLOCK_${idx}%%`;
  });

  const inlineCodes: string[] = [];
  html = html.replace(/`([^`]+)`/g, (_m, code: string) => {
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

  // Images run BEFORE the link rule (otherwise `![a](u)` is eaten by it)
  // and BEFORE emphasis, so `alt` holds plain escaped text rather than
  // generated tags. The finished tag is parked behind a sentinel so no
  // later pass can inject anything into its attributes.
  const images: string[] = [];
  html = html.replace(/!\[([^\]]*)\]\(([^)\s]*)(?:\s+&quot;[^)]*&quot;)?\)/g, (_m, alt: string, src: string) => {
    const safeSrc = sanitizeEscapedUrlForAttribute(src, ALLOWED_IMAGE_SCHEMES);
    if (safeSrc === null) return alt; // drop the image, keep its alt text
    const idx = images.length;
    images.push(
      `<img class="mdImage" src="${safeSrc}" alt="${alt}" loading="lazy" ` +
        `referrerpolicy="no-referrer" style="max-width:100%;height:auto" />`,
    );
    return `%%MDIMAGE_${idx}%%`;
  });

  html = html.replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, text: string, href: string) => {
    const safeHref = sanitizeEscapedUrlForAttribute(href, ALLOWED_LINK_SCHEMES);
    // Disallowed scheme -> render the label as plain text. Emitting a dead
    // `href="#"` would only disguise a hostile link as a working one.
    if (safeHref === null) return text;
    return `<a class="mdLink" href="${safeHref}" target="_blank" rel="noopener noreferrer">${text}</a>`;
  });
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

  // Function replacements: a *string* replacement would interpret `$&`,
  // `$'` and backtick-`$` sequences inside code as substitution patterns.
  for (let i = 0; i < codeBlocks.length; i++) html = html.replace(`%%CODEBLOCK_${i}%%`, () => codeBlocks[i]);
  for (let i = 0; i < inlineCodes.length; i++) html = html.replace(`%%INLINECODE_${i}%%`, () => inlineCodes[i]);
  for (let i = 0; i < images.length; i++) html = html.replace(`%%MDIMAGE_${i}%%`, () => images[i]);

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

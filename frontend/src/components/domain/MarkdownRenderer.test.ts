/**
 * Tests for the MarkdownRenderer security core.
 *
 * NOTE: this repo has no test runner configured (no vitest/jest in
 * `frontend/package.json`), and adding one was out of scope. This file is
 * therefore written framework-free: it exports `runMarkdownRendererTests()`,
 * which returns a plain array of results and is trivially adaptable to any
 * runner later (`it("...", () => expect(...))` per entry).
 *
 * To run it today:
 *   npx tsc src/components/domain/MarkdownRenderer.test.ts --outDir <dir> \
 *     --target es2020 --module esnext --jsx react-jsx --moduleResolution bundler
 *   node -e "import('<dir>/.../MarkdownRenderer.test.js').then(m => ...)"
 */

import {
  ALLOWED_IMAGE_SCHEMES,
  decodeEntities,
  escapeHtml,
  markdownToHtml,
  sanitizeUrl,
  unescapeHtml,
} from "./MarkdownRenderer";

export interface TestResult {
  name: string;
  passed: boolean;
  detail?: string;
}

const TAB = String.fromCharCode(9);
const NUL_ISH = String.fromCharCode(1);

/** Pull the first tag of the given name out of a rendered string. */
function firstTag(html: string, tagName: string): string | null {
  const match = new RegExp(`<${tagName}\\b[^>]*>`).exec(html);
  return match ? match[0] : null;
}

/**
 * Number of raw `"` characters in a tag. This is the attribute-breakout
 * detector: we know exactly how many attributes we emit, so any extra raw
 * quote means a value escaped its delimiters and became new markup.
 */
function rawQuoteCount(tag: string): number {
  return (tag.match(/"/g) || []).length;
}

export function runMarkdownRendererTests(): TestResult[] {
  const results: TestResult[] = [];
  const check = (name: string, passed: boolean, detail?: string) => {
    results.push(detail === undefined ? { name, passed } : { name, passed, detail });
  };

  /* ---------------- escaping ---------------- */

  check(
    "escapeHtml escapes &, <, >, \" and ' with & handled first",
    escapeHtml(`<a href="x">&'`) === "&lt;a href=&quot;x&quot;&gt;&amp;&#39;",
    escapeHtml(`<a href="x">&'`),
  );

  check(
    "escapeHtml does not double-escape (round-trips through unescapeHtml)",
    unescapeHtml(escapeHtml(`a & b < c > d " e ' f`)) === `a & b < c > d " e ' f`,
  );

  check(
    "decodeEntities resolves numeric, hex and named colons",
    decodeEntities("a&#58;b&#x3A;c&colon;d") === "a:b:c:d",
    decodeEntities("a&#58;b&#x3A;c&colon;d"),
  );

  /* ---------------- attribute breakout ---------------- */

  {
    const html = markdownToHtml(`[click](" onmouseover="alert(document.cookie))`);
    const anchor = firstTag(html, "a");
    // class + href + target + rel = 4 attributes = 8 delimiter quotes.
    check(
      "attribute-breakout payload cannot add an attribute to <a>",
      anchor !== null && rawQuoteCount(anchor) === 8,
      anchor ?? html,
    );
    check(
      "attribute-breakout payload emits no raw onmouseover=\" ",
      !html.includes('onmouseover="'),
      html,
    );
  }

  {
    const html = markdownToHtml(`![" onerror="alert(1)](https://example.com/a.png)`);
    const img = firstTag(html, "img");
    // class + src + alt + loading + referrerpolicy + style = 6 = 12 quotes.
    check(
      "image alt cannot break out of its attribute",
      img !== null && rawQuoteCount(img) === 12,
      img ?? html,
    );
    check("image alt breakout emits no raw onerror=\" ", !html.includes('onerror="'), html);
  }

  /* ---------------- scheme allow-list ---------------- */

  const blockedLinkPayloads: Array<[string, string]> = [
    ["javascript: plain", "javascript:alert(1)"],
    ["javascript: mixed case", "JaVaScRiPt:alert(1)"],
    ["javascript: leading whitespace", "   javascript:alert(1)"],
    ["javascript: embedded tab", `java${TAB}script:alert(1)`],
    ["javascript: embedded newline", "java\nscript:alert(1)"],
    ["javascript: embedded control char", `${NUL_ISH}javascript:alert(1)`],
    ["javascript: entity-encoded colon", "javascript&#58;alert(1)"],
    ["javascript: entity-encoded j", "&#106;avascript:alert(1)"],
    ["javascript: hex-entity colon", "javascript&#x3a;alert(1)"],
    ["data:text/html", "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg=="],
    ["data:text/html plain", "data:text/html,<script>alert(1)</script>"],
    ["vbscript:", "vbscript:msgbox(1)"],
    ["file:", "file:///etc/passwd"],
  ];

  for (const [label, payload] of blockedLinkPayloads) {
    const html = markdownToHtml(`[x](${payload})`);
    check(
      `link with ${label} renders no anchor`,
      !html.includes("<a ") && html.includes("x"),
      html,
    );
  }

  for (const [label, payload] of blockedLinkPayloads) {
    check(`sanitizeUrl rejects ${label}`, sanitizeUrl(payload) === null, payload);
  }

  check(
    "image with javascript: src renders no img and keeps alt text",
    (() => {
      const html = markdownToHtml("![logo](javascript:alert(1))");
      return !html.includes("<img") && html.includes("logo");
    })(),
  );

  check(
    "image with data: src is rejected (data not in image allow-list)",
    sanitizeUrl("data:image/png;base64,iVBORw0KGgo=", ALLOWED_IMAGE_SCHEMES) === null,
  );

  /* ---------------- allowed URLs ---------------- */

  const allowedUrls = [
    "https://example.com/path?a=1&b=2#frag",
    "http://example.com",
    "HTTPS://EXAMPLE.COM/x",
    "mailto:security@example.com",
    "/relative/path",
    "relative/path",
    "#anchor",
    "?query=1",
    "//cdn.example.com/x.js",
  ];
  for (const url of allowedUrls) {
    check(`sanitizeUrl allows ${url}`, sanitizeUrl(url) !== null, url);
  }

  /* ---------------- legitimate rendering ---------------- */

  {
    const html = markdownToHtml("[RedWeaver](https://example.com/a?b=1&c=2)");
    check(
      "ordinary link still renders with escaped ampersand",
      html.includes('<a class="mdLink" href="https://example.com/a?b=1&amp;c=2" target="_blank" rel="noopener noreferrer">RedWeaver</a>'),
      html,
    );
  }

  check(
    "mailto link still renders",
    markdownToHtml("[mail](mailto:a@b.com)").includes('href="mailto:a@b.com"'),
  );

  check(
    "relative link still renders",
    markdownToHtml("[docs](/docs/report)").includes('href="/docs/report"'),
  );

  {
    const html = markdownToHtml("![Screenshot](https://example.com/shot.png)");
    check(
      "ordinary image still renders",
      html.includes('<img class="mdImage" src="https://example.com/shot.png"') &&
        html.includes('alt="Screenshot"'),
      html,
    );
  }

  {
    const html = markdownToHtml("```bash\nnmap -sV target\n```");
    check(
      "fenced code block still renders with language",
      html.includes('<pre class="mdCodeBlock" data-lang="bash"><code>nmap -sV target</code></pre>'),
      html,
    );
  }

  {
    // `$&`, `$'` and `` $` `` are String.replace substitution patterns; a string
    // replacement when restoring the block would corrupt/duplicate markup.
    const html = markdownToHtml("```\necho \"$&\" \"$'\" \"$`\"\n```");
    check(
      "code block containing $& / $' survives placeholder restore verbatim",
      html.includes("echo &quot;$&amp;&quot; &quot;$&#39;&quot; &quot;$`&quot;"),
      html,
    );
  }

  check(
    "inline code still renders",
    markdownToHtml("use `curl -I` here").includes('<code class="mdInlineCode">curl -I</code>'),
  );

  {
    const html = markdownToHtml("# H1\n\n## H2\n\n### H3\n\n#### H4");
    check(
      "headings still render",
      html.includes('<h1 class="mdH1">H1</h1>') &&
        html.includes('<h2 class="mdH2">H2</h2>') &&
        html.includes('<h3 class="mdH3">H3</h3>') &&
        html.includes('<h4 class="mdH4">H4</h4>'),
      html,
    );
  }

  {
    const html = markdownToHtml("| Sev | Finding |\n| --- | --- |\n| High | XSS |\n");
    check(
      "tables still render",
      html.includes('<table class="mdTable">') && html.includes("<th>Sev</th>") && html.includes("<td>XSS</td>"),
      html,
    );
  }

  {
    const html = markdownToHtml("- one\n- two\n");
    check("unordered lists still render", html.includes('<ul class="mdUl">') && html.includes('<li class="mdLi">one</li>'), html);
  }

  {
    const html = markdownToHtml("1. one\n2. two\n");
    check("ordered lists still render", html.includes('<ol class="mdOl">') && html.includes('<li class="mdOlLi">one</li>'), html);
  }

  {
    const html = markdownToHtml("> **Warning:** rotate the key\n");
    check(
      "blockquote callouts still render",
      html.includes("mdCallout--warning") && html.includes("<strong>Warning:</strong>"),
      html,
    );
  }

  check(
    "bold and italic still render",
    markdownToHtml("**b** and *i*").includes("<strong>b</strong>") &&
      markdownToHtml("**b** and *i*").includes("<em>i</em>"),
  );

  {
    const html = markdownToHtml(`it's a "quoted" word`);
    check(
      "quotes and apostrophes in prose are escaped, not dropped",
      html.includes("it&#39;s a &quot;quoted&quot; word"),
      html,
    );
  }

  {
    // A hostile document that writes our own sentinel must not be able to
    // steal the restore slot of a real code block.
    const html = markdownToHtml("%%CODEBLOCK_0%% intro\n\n```\nreal code\n```");
    check(
      "author-supplied sentinel cannot hijack a code-block restore slot",
      html.includes("<code>real code</code>") && !html.includes("%%CODEBLOCK_0%%"),
      html,
    );
  }

  return results;
}

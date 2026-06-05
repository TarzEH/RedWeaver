/** Shared helpers for the Knowledge Base viewer. */

/** Humanize a category slug (e.g. "privilege_escalation" → "Privilege Escalation"). */
export function categoryLabel(slug: string): string {
  if (!slug) return "Uncategorized";
  return slug
    .split(/[_\-/]/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/** Last path segment of a KB file, without extension — used as a friendly fallback title. */
export function fileBaseName(file: string): string {
  const base = file.split(/[\\/]/).pop() || file;
  return base.replace(/\.[^.]+$/, "");
}

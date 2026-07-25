/**
 * Route → page-name map.
 *
 * Every screen lives in `features/` and none of them set `document.title`, so
 * all eleven routes shipped the same static title. That breaks two things at
 * once: browser history / tab lists are unusable, and a route announcer has no
 * authoritative name to read out. Setting titles per screen would mean touching
 * eleven feature files; the router already owns the full route table, so the map
 * lives here instead.
 *
 * Names are written to be read aloud — short, descriptive, and distinct from
 * each other, since a screen-reader user hears only this on navigation.
 */

import { matchPath } from "react-router-dom";

export const APP_NAME = "RedWeaver";

/**
 * Most-specific first. `matchPath` defaults to `end: true` (full-path match), so
 * the ordering is defensive rather than load-bearing.
 */
const ROUTE_TITLES: ReadonlyArray<readonly [pattern: string, name: string]> = [
  ["/hunt/:runId/findings", "Findings"],
  ["/hunt/:runId/report", "Hunt report"],
  ["/hunt/:runId/compare", "Run comparison"],
  ["/hunt/:runId", "Hunt"],
  ["/hunt", "Hunts"],
  ["/sessions/:sessionId/assets", "Asset inventory"],
  ["/sessions", "Sessions"],
  ["/debug/:runId", "Behind the scenes"],
  ["/dashboard", "Dashboard"],
  ["/knowledge", "Knowledge base"],
  ["/settings", "Settings"],
];

/** The mapped page name for a pathname, or `null` when the route is unknown. */
export function routeName(pathname: string): string | null {
  for (const [pattern, name] of ROUTE_TITLES) {
    if (matchPath({ path: pattern, end: true }, pathname)) return name;
  }
  return null;
}

/**
 * Last-resort name derived from the URL itself, e.g. `/hunt/abc/findings` →
 * "Findings". Only reached for a route that is in neither the map nor rendering
 * an `<h1>`.
 */
export function nameFromPathname(pathname: string): string {
  const segment = pathname.split("/").filter(Boolean).pop();
  if (!segment) return "Home";
  const words = segment.replace(/[-_]+/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** `"Findings"` → `"Findings · RedWeaver"`. */
export function documentTitleFor(name: string): string {
  return `${name} · ${APP_NAME}`;
}

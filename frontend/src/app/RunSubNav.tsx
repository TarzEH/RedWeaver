/**
 * Contextual navigation for a single run.
 *
 * Two finished screens had no way in — a grep across `src/` found zero `<Link>`
 * or `navigate()` references to either:
 *
 *   • `/hunt/:runId/findings`         the findings triage screen
 *   • `/sessions/:sessionId/assets`   the asset inventory
 *
 * Neither can live in the Sidebar: the Sidebar is global chrome with no run or
 * session in scope, and both routes are parameterised. They belong on a bar that
 * appears once a run *is* in scope, which is what this is. `/hunt/:runId/report`
 * and `/compare` are included for consistency — they were previously reachable
 * only from inside a rendered report block, i.e. only after a run produced one.
 *
 * The asset inventory is keyed by session, not run, so its link depends on
 * resolving the run's owning session. `RunDetail.session_id` carries that, which
 * is why this component fetches. The request is one small GET, fired only on run
 * routes and only when the run id actually changes.
 */

import { useEffect, useState } from "react";
import { Link, matchPath, useLocation } from "react-router-dom";
import { Activity, GitCompare, Server, Shield, Swords, FileText } from "lucide-react";
import { api } from "../services/api";
import { cn } from "../lib/cn";

/** The run id currently in scope, from either the hunt or the debug route. */
function runIdFrom(pathname: string): string | null {
  const hunt = matchPath({ path: "/hunt/:runId", end: false }, pathname);
  if (hunt?.params.runId) return hunt.params.runId;
  const debug = matchPath({ path: "/debug/:runId", end: false }, pathname);
  return debug?.params.runId ?? null;
}

type SubNavItem = {
  to: string;
  label: string;
  icon: typeof Shield;
  /** Match only this exact path (used for the run overview). */
  exact?: boolean;
};

export function RunSubNav() {
  const { pathname } = useLocation();
  const runId = runIdFrom(pathname);
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) {
      setSessionId(null);
      return;
    }
    let alive = true;
    api.runs
      .get(runId)
      .then((run) => {
        if (alive) setSessionId(run.session_id ?? null);
      })
      // A run that can't be loaded just means no asset link; the rest of the bar
      // stays useful, so this failure is not worth surfacing.
      .catch(() => {
        if (alive) setSessionId(null);
      });
    return () => {
      alive = false;
    };
  }, [runId]);

  if (!runId) return null;

  const items: SubNavItem[] = [
    { to: `/hunt/${runId}`, label: "Overview", icon: Activity, exact: true },
    { to: `/hunt/${runId}/findings`, label: "Findings", icon: Shield },
    { to: `/hunt/${runId}/report`, label: "Report", icon: FileText },
    { to: `/hunt/${runId}/compare`, label: "Compare", icon: GitCompare },
    { to: `/debug/${runId}`, label: "Behind the scenes", icon: Swords },
  ];
  if (sessionId) {
    items.push({ to: `/sessions/${sessionId}/assets`, label: "Assets", icon: Server });
  }

  return (
    <nav
      aria-label="Run sections"
      className="shrink-0 flex items-center gap-1 px-3 border-b border-rw-border bg-rw-elevated overflow-x-auto"
    >
      {items.map(({ to, label, icon: Icon, exact }) => {
        const active = exact ? pathname === to : pathname.startsWith(to);
        return (
          <Link
            key={to}
            to={to}
            aria-current={active ? "page" : undefined}
            className={cn(
              "inline-flex items-center gap-1.5 whitespace-nowrap px-3 py-2 text-xs font-medium",
              "border-b-2 -mb-px transition-colors",
              active
                ? "text-rw-accent border-rw-accent"
                : "text-rw-dim border-transparent hover:text-rw-muted",
            )}
          >
            <Icon size={13} aria-hidden="true" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

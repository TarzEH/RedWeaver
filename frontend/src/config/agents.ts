/**
 * Centralized agent configuration — single source of truth for all agent
 * display names, colors, abbreviations, and ordering across the frontend.
 */

export interface AgentInfo {
  displayName: string;
  shortLabel: string;
  abbrev: string;
  color: string;
  category: "core" | "ssh" | "report";
}

export const AGENT_CONFIG: Record<string, AgentInfo> = {
  orchestrator:    { displayName: "Orchestrator",         shortLabel: "Orch",    abbrev: "O", color: "#00d4aa", category: "core" },
  recon:           { displayName: "Reconnaissance",       shortLabel: "Recon",   abbrev: "R", color: "#8b5cf6", category: "core" },
  crawler:         { displayName: "Web Crawler",          shortLabel: "Crawl",   abbrev: "C", color: "#06b6d4", category: "core" },
  vuln_scanner:    { displayName: "Vuln Scanner",         shortLabel: "Vuln",    abbrev: "V", color: "#ef4444", category: "core" },
  fuzzer:          { displayName: "Fuzzer",               shortLabel: "Fuzz",    abbrev: "F", color: "#f97316", category: "core" },
  web_search:      { displayName: "Web Search",           shortLabel: "Search",  abbrev: "W", color: "#eab308", category: "core" },
  exploit_analyst: { displayName: "Exploit Analyst",      shortLabel: "Exploit", abbrev: "E", color: "#ec4899", category: "core" },
  privesc:         { displayName: "Privilege Escalation",  shortLabel: "PrivEsc", abbrev: "X", color: "#a855f7", category: "ssh" },
  tunnel_pivot:    { displayName: "Tunnel & Pivot",       shortLabel: "Tunnel",  abbrev: "T", color: "#14b8a6", category: "ssh" },
  post_exploit:    { displayName: "Post-Exploitation",    shortLabel: "PostEx",  abbrev: "Z", color: "#f43f5e", category: "ssh" },
  report_writer:   { displayName: "Report Writer",        shortLabel: "Report",  abbrev: "P", color: "#22c55e", category: "report" },
};

// Derived helpers
export const AGENT_ORDER = Object.keys(AGENT_CONFIG);

export const AGENT_DISPLAY_NAMES: Record<string, string> = Object.fromEntries(
  Object.entries(AGENT_CONFIG).map(([k, v]) => [k, v.displayName]),
);

export const AGENT_COLORS: Record<string, string> = Object.fromEntries(
  Object.entries(AGENT_CONFIG).map(([k, v]) => [k, v.color]),
);

export const AGENT_ABBREVS: Record<string, string> = Object.fromEntries(
  Object.entries(AGENT_CONFIG).map(([k, v]) => [k, v.abbrev]),
);

export const AGENT_SHORT_LABELS: Record<string, string> = Object.fromEntries(
  Object.entries(AGENT_CONFIG).map(([k, v]) => [k, v.shortLabel]),
);

/** Label lookup including alternate node IDs from backend graph topology. */
export const LABELS: Record<string, string> = {
  __start__: "START",
  __end__: "END",
  plan: "Orchestrator",
  crawl: "Crawl",
  vuln_scan: "Vuln Scan",
  fuzz: "Fuzz",
  analyze: "Analyze",
  report: "Report",
  ...AGENT_DISPLAY_NAMES,
};

/**
 * Centralized design system — single source of truth for all colors,
 * status labels, severity styling, and UI constants.
 */

import type { Severity } from "../types/api";

// --- Run Status ---

export type RunStatus = "running" | "completed" | "failed" | "queued" | "idle";

const STATUS_CONFIG: Record<RunStatus, { label: string; color: string; bg: string; dot: string }> = {
  running:   { label: "Running",   color: "#60a5fa", bg: "rgba(96,165,250,0.12)", dot: "bg-blue-400" },
  completed: { label: "Completed", color: "#34d399", bg: "rgba(52,211,153,0.12)", dot: "bg-emerald-400" },
  failed:    { label: "Failed",    color: "#f87171", bg: "rgba(248,113,113,0.12)", dot: "bg-red-400" },
  queued:    { label: "Queued",    color: "#a78bfa", bg: "rgba(167,139,250,0.12)", dot: "bg-violet-400" },
  idle:      { label: "Idle",      color: "#64748b", bg: "rgba(100,116,139,0.12)", dot: "bg-slate-400" },
};

export function statusLabel(status: string): string {
  return STATUS_CONFIG[status as RunStatus]?.label ?? status;
}

export function statusColor(status: string): { color: string; bg: string; dot: string } {
  return STATUS_CONFIG[status as RunStatus] ?? STATUS_CONFIG.idle;
}

// --- Severity ---

// Severity type is imported from types/api.ts (single source of truth)
export type { Severity } from "../types/api";

const SEV_CONFIG: Record<Severity, { color: string; bg: string; border: string; label: string }> = {
  critical: { color: "text-red-400",    bg: "bg-red-500/15",    border: "border-red-500/30",    label: "Critical" },
  high:     { color: "text-orange-400", bg: "bg-orange-500/15", border: "border-orange-500/30", label: "High" },
  medium:   { color: "text-yellow-400", bg: "bg-yellow-500/15", border: "border-yellow-500/30", label: "Medium" },
  low:      { color: "text-blue-400",    bg: "bg-blue-500/15",    border: "border-blue-500/30",    label: "Low" },
  info:     { color: "text-slate-400",  bg: "bg-slate-500/15",  border: "border-slate-500/30",  label: "Info" },
};

export function severityStyle(sev: string) {
  return SEV_CONFIG[sev as Severity] ?? SEV_CONFIG.info;
}

export const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];

const SEV_HEX: Record<Severity, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#eab308",
  low: "#3b82f6",
  info: "#64748b",
};

export function severityHex(sev: string): string {
  return SEV_HEX[sev as Severity] ?? SEV_HEX.info;
}

// --- API Base ---

let _apiBase = "";
let _apiBaseInit = false;

export function getApiBase(): string {
  if (!_apiBaseInit) {
    const raw: string = (import.meta as any).env?.VITE_BACKEND_URL || "";
    _apiBase = raw.endsWith("/") ? raw.slice(0, -1) : raw;
    _apiBaseInit = true;
  }
  return _apiBase;
}

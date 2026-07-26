/**
 * Sequential colour scale + ATT&CK tactic lookup shared by the report's
 * ATT&CK views.
 *
 * ## The scale
 *
 * Cividis, **authored for this dark ground** rather than inverted from a light
 * palette (inverting breaks the low→high luminance mapping and the low stops
 * disappear into the panel). Full cividis runs `#00204d → #fee838`; its bottom
 * ~40% is *darker* than the `#111827` panel it sits on, so those stops would be
 * invisible here. We therefore take the upper segment of the real cividis ramp
 * and pull the first stop down slightly so that every stop simultaneously:
 *
 *   - clears WCAG 1.4.11 (3:1 non-text contrast) against the `#111827` panel,
 *     since colour is carrying information here; and
 *   - can carry a 4.5:1 numeric label in one of two inks.
 *
 * Measured against `#111827` (relative luminance 0.0101):
 *
 * | stop      | vs panel | ink       | ink contrast |
 * |-----------|----------|-----------|--------------|
 * | `#686b71` |  3.3:1   | `#f1f5f9` |    4.9:1     |
 * | `#8a8678` |  4.8:1   | `#0a0f1e` |    5.3:1     |
 * | `#a59c74` |  6.3:1   | `#0a0f1e` |    6.9:1     |
 * | `#c3b369` |  8.3:1   | `#0a0f1e` |    9.1:1     |
 * | `#e1cc55` | 10.8:1   | `#0a0f1e` |   11.8:1     |
 * | `#fee838` | 14.0:1   | `#0a0f1e` |   15.3:1     |
 *
 * Cividis is monotonic in luminance and optimised for deuteranopia, so the ramp
 * survives greyscale printing and red-green colour blindness. Deliberately not
 * a rainbow and deliberately not red→green.
 */

/** Low → high. Index 0 is the dimmest *visible* stop; there is no "zero" stop. */
export const ATTACK_SCALE = [
  "#686b71",
  "#8a8678",
  "#a59c74",
  "#c3b369",
  "#e1cc55",
  "#fee838",
] as const;

/** Ink that clears 4.5:1 on the corresponding {@link ATTACK_SCALE} stop. */
const ATTACK_SCALE_INK = ["#f1f5f9", "#0a0f1e", "#0a0f1e", "#0a0f1e", "#0a0f1e", "#0a0f1e"] as const;

/**
 * A *scored zero* — the measure was evaluated and came out at 0. Painted, with
 * a solid border, so it reads as a real data point. Distinct from "no data",
 * which is never painted at all (see `NO_DATA` styling in the view).
 */
export const ATTACK_ZERO_FILL = "#1e293b";

/** Ink for a scored zero — `--color-rw-muted`, readable on {@link ATTACK_ZERO_FILL}. */
export const ATTACK_ZERO_INK = "#94a3b8";

/**
 * Bin `count` into a {@link ATTACK_SCALE} index. `count <= 0` returns `-1`,
 * which callers must render as the zero/no-data treatment, never as a colour.
 */
function attackScaleStep(count: number, max: number): number {
  if (!(count > 0) || !(max > 0)) return -1;
  const n = ATTACK_SCALE.length;
  return Math.min(n - 1, Math.max(0, Math.ceil((count / max) * n) - 1));
}

/** `{ fill, ink }` for a positive count; callers handle `count <= 0` themselves. */
export function attackCellColors(count: number, max: number): { fill: string; ink: string } {
  const i = attackScaleStep(count, max);
  if (i < 0) return { fill: ATTACK_ZERO_FILL, ink: ATTACK_ZERO_INK };
  return { fill: ATTACK_SCALE[i], ink: ATTACK_SCALE_INK[i] };
}

// --- ATT&CK tactics -------------------------------------------------------

export interface Tactic {
  /** ATT&CK tactic id, e.g. `TA0001`. */
  id: string;
  /** ATT&CK slug as emitted by the backend, e.g. `initial-access`. */
  slug: string;
  name: string;
}

/** The 14 Enterprise tactics, in kill-chain order. This order is semantic — it
 *  is the reason the kill-chain view is not sorted by count. */
export const TACTICS: Tactic[] = [
  { id: "TA0043", slug: "reconnaissance", name: "Reconnaissance" },
  { id: "TA0042", slug: "resource-development", name: "Resource Development" },
  { id: "TA0001", slug: "initial-access", name: "Initial Access" },
  { id: "TA0002", slug: "execution", name: "Execution" },
  { id: "TA0003", slug: "persistence", name: "Persistence" },
  { id: "TA0004", slug: "privilege-escalation", name: "Privilege Escalation" },
  { id: "TA0005", slug: "defense-evasion", name: "Defense Evasion" },
  { id: "TA0006", slug: "credential-access", name: "Credential Access" },
  { id: "TA0007", slug: "discovery", name: "Discovery" },
  { id: "TA0008", slug: "lateral-movement", name: "Lateral Movement" },
  { id: "TA0009", slug: "collection", name: "Collection" },
  { id: "TA0011", slug: "command-and-control", name: "Command & Control" },
  { id: "TA0010", slug: "exfiltration", name: "Exfiltration" },
  { id: "TA0040", slug: "impact", name: "Impact" },
];

/**
 * Technique id → tactic slug for every technique the backend's finding mapper
 * can emit (`backend/apps/findings/attack_map.py`, which knows the tactic but
 * drops it before serialising — the report API only sends `technique` + `count`).
 *
 * These pairings are MITRE's own technique→tactic assignments, not RedWeaver
 * policy, so they are stable. Unknown ids fall back to the parent technique and
 * then to `null`, which the views render as "Unmapped" rather than guessing.
 */
const TECHNIQUE_TACTIC: Record<string, string> = {
  T1003: "credential-access",
  T1041: "exfiltration",
  T1046: "discovery",
  T1059: "execution",
  T1068: "privilege-escalation",
  T1083: "discovery",
  T1110: "credential-access",
  T1190: "initial-access",
  T1505: "persistence",
  T1557: "credential-access",
  T1595: "reconnaissance",
};

export interface ParsedTechnique {
  /** e.g. `T1059.007`; empty when the label had no recognisable id. */
  id: string;
  /** e.g. `JavaScript`; falls back to the whole label. */
  name: string;
  /** Tactic slug, or `null` when the technique is not in the lookup. */
  tactic: string | null;
  count: number;
}

const TECHNIQUE_RE = /^(T\d{4}(?:\.\d{3})?)\s*(.*)$/;

/**
 * Split the backend's `"T1190 Exploit Public-Facing Application"` label into its
 * id and name and attach the tactic.
 */
export function parseTechnique(label: string, count: number): ParsedTechnique {
  const m = TECHNIQUE_RE.exec((label || "").trim());
  if (!m) return { id: "", name: label || "Unknown technique", tactic: null, count };
  const id = m[1];
  const parent = id.split(".")[0];
  return {
    id,
    name: m[2] || id,
    tactic: TECHNIQUE_TACTIC[id] ?? TECHNIQUE_TACTIC[parent] ?? null,
    count,
  };
}

export function tacticName(slug: string | null): string {
  if (!slug) return "Unmapped";
  return TACTICS.find((t) => t.slug === slug)?.name ?? slug;
}

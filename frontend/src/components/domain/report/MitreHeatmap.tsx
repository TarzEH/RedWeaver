import { useMemo, useState } from "react";
import { Crosshair, ListOrdered, X } from "lucide-react";
import type { MitreTechnique } from "../../../types/api";
import { cn } from "../../../lib/cn";
import {
  ATTACK_SCALE,
  ATTACK_ZERO_FILL,
  ATTACK_ZERO_INK,
  attackCellColors,
  parseTechnique,
  tacticName,
  TACTICS,
  type ParsedTechnique,
} from "./attackScale";

interface MitreHeatmapProps {
  /** `compliance.mitre_attack` from `build_report()` — technique label → count. */
  techniques?: MitreTechnique[];
  className?: string;
}

type View = "chain" | "ranked";

interface TacticRow {
  id: string;
  slug: string;
  name: string;
  /** Sum of finding counts across the techniques mapped to this tactic. */
  count: number;
  /** False when the hunt mapped nothing here — "no data", not a scored zero. */
  observed: boolean;
  techniques: ParsedTechnique[];
}

/* -------------------------------------------------------------------------- */

/** Shared cell: a proportional fill carrying the count as text on top of it. */
function CountCell({
  count,
  max,
  observed,
  label,
}: {
  count: number;
  max: number;
  observed: boolean;
  /** Row identity, used for the screen-reader sentence. */
  label: string;
}) {
  if (!observed) {
    // MITRE Navigator's documented treatment for unscored techniques: leave the
    // cell transparent. Absence is not painted, and it carries a glyph + words
    // so it can never be confused with a scored zero.
    return (
      <td className="py-1 pl-3">
        <div className="flex h-7 items-center gap-2 rounded-md border border-dashed border-rw-border px-2">
          <span aria-hidden className="font-mono text-xs text-rw-dim">
            —
          </span>
          <span aria-hidden className="text-[11px] text-rw-dim">
            no findings mapped
          </span>
          <span className="sr-only">No findings mapped to {label}.</span>
        </div>
      </td>
    );
  }

  const zero = count === 0;
  const { fill, ink } = attackCellColors(count, max);
  // Every fill still shows at least a stub so the count text always has its
  // measured background under it, never the panel.
  const pct = max > 0 ? Math.max(22, Math.round((count / max) * 100)) : 100;

  return (
    <td className="py-1 pl-3">
      <div className="relative h-7 overflow-hidden rounded-md border border-rw-border-subtle bg-rw-surface/40">
        <div
          aria-hidden
          className="absolute inset-y-0 left-0 rounded-md"
          style={{ width: `${pct}%`, background: zero ? ATTACK_ZERO_FILL : fill }}
        />
        <span
          className="absolute inset-y-0 left-2 flex items-center text-xs font-bold tabular-nums"
          style={{ color: zero ? ATTACK_ZERO_INK : ink }}
        >
          {count}
        </span>
        <span className="sr-only">
          {count} finding{count === 1 ? "" : "s"} in {label}.
        </span>
      </div>
    </td>
  );
}

function Legend({ max, techniqueCount }: { max: number; techniqueCount: number }) {
  return (
    <div className="mt-4 space-y-2 border-t border-rw-border-subtle pt-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium uppercase tracking-wider text-rw-dim">
            Findings
          </span>
          <span className="font-mono text-[11px] tabular-nums text-rw-muted">1</span>
          <span aria-hidden className="flex overflow-hidden rounded-sm border border-rw-border-subtle">
            {ATTACK_SCALE.map((c) => (
              <span key={c} className="block h-3 w-6" style={{ background: c }} />
            ))}
          </span>
          <span className="font-mono text-[11px] tabular-nums text-rw-muted">{Math.max(max, 1)}</span>
        </div>

        <span className="flex items-center gap-1.5 text-[11px] text-rw-dim">
          <span
            aria-hidden
            className="inline-block h-3 w-6 rounded-sm border border-rw-border-subtle"
            style={{ background: ATTACK_ZERO_FILL }}
          />
          scored 0
        </span>

        <span className="flex items-center gap-1.5 text-[11px] text-rw-dim">
          <span
            aria-hidden
            className="inline-block h-3 w-6 rounded-sm border border-dashed border-rw-border"
          />
          no findings mapped
        </span>
      </div>
      <p className="text-[11px] leading-relaxed text-rw-dim">
        Shade encodes the number of findings mapped to that row, from 1 to{" "}
        <span className="font-mono tabular-nums">{Math.max(max, 1)}</span>. The count is printed in
        every cell, so the colour is never the only signal. A dashed, unpainted cell means the hunt
        mapped nothing there — that is <em>absence of data</em>, not a measured zero.
        {techniqueCount > 0 && (
          <>
            {" "}
            Mapping is derived from finding text by RedWeaver&apos;s ATT&amp;CK mapper, not asserted
            by the model.
          </>
        )}
      </p>
    </div>
  );
}

/* -------------------------------------------------------------------------- */

/**
 * The report's ATT&CK view: what *this hunt actually found*, mapped onto the
 * ATT&CK kill chain. (Distinct from `KbAttackHeatmap`, which shows what the
 * knowledge base *documents*.)
 *
 * ## Why this is not a heatmap
 *
 * The report API exposes ATT&CK as a one-dimensional `technique → count` map;
 * severity and verification status are not joinable to a technique without
 * re-implementing the backend's keyword mapper in the browser. A one-dimensional
 * measure whose rows you would sort by their own total is a **sorted bar list**,
 * not a heatmap — a heatmap earns its place only when both axes are categorical.
 * So both views below are ranked/ordered bar lists with a sequential fill, and
 * both are rendered as real `<table>`s.
 *
 * Two peer views, because they answer different questions:
 *  - **Kill chain** — all 14 tactics in ATT&CK's semantic order (deliberately
 *    *not* sorted by count), so the gaps are as legible as the hits.
 *  - **Ranked** — techniques sorted by count, the "what's the top item" view.
 */
export function MitreHeatmap({ techniques, className }: MitreHeatmapProps) {
  const [view, setView] = useState<View>("chain");
  const [tacticFilter, setTacticFilter] = useState<string | null>(null);

  const parsed = useMemo<ParsedTechnique[]>(
    () =>
      (techniques ?? [])
        .filter((t) => t?.technique)
        .map((t) => parseTechnique(t.technique, Number(t.count) || 0))
        .sort((a, b) => b.count - a.count || a.id.localeCompare(b.id)),
    [techniques],
  );

  const tacticRows = useMemo<TacticRow[]>(() => {
    const byTactic = new Map<string, ParsedTechnique[]>();
    for (const t of parsed) {
      if (!t.tactic) continue;
      const bucket = byTactic.get(t.tactic);
      if (bucket) bucket.push(t);
      else byTactic.set(t.tactic, [t]);
    }
    return TACTICS.map((tac) => {
      const techs = byTactic.get(tac.slug) ?? [];
      return {
        id: tac.id,
        slug: tac.slug,
        name: tac.name,
        count: techs.reduce((s, t) => s + t.count, 0),
        observed: techs.length > 0,
        techniques: techs,
      };
    });
  }, [parsed]);

  const unmapped = useMemo(() => parsed.filter((t) => !t.tactic), [parsed]);

  const chainMax = useMemo(
    () => tacticRows.reduce((m, r) => Math.max(m, r.count), 0),
    [tacticRows],
  );
  const techniqueMax = useMemo(() => parsed.reduce((m, t) => Math.max(m, t.count), 0), [parsed]);

  const rankedRows = useMemo(
    () => (tacticFilter ? parsed.filter((t) => t.tactic === tacticFilter) : parsed),
    [parsed, tacticFilter],
  );

  const coveredTactics = tacticRows.filter((r) => r.observed).length;
  const totalMappings = parsed.reduce((s, t) => s + t.count, 0);

  const showRanked = (slug: string | null) => {
    setTacticFilter(slug);
    setView("ranked");
  };

  const tabClass = (active: boolean) =>
    cn(
      "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rw-accent",
      active
        ? "bg-rw-surface text-rw-text"
        : "text-rw-dim hover:bg-rw-surface/50 hover:text-rw-muted",
    );

  return (
    <div className={cn("rounded-xl border border-rw-border bg-rw-elevated p-4", className)}>
      <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="text-sm font-semibold text-rw-text">ATT&amp;CK Findings Coverage</span>
        <span className="text-xs text-rw-dim">
          {coveredTactics}/{TACTICS.length} tactics · {parsed.length} technique
          {parsed.length === 1 ? "" : "s"} · {totalMappings} mapping
          {totalMappings === 1 ? "" : "s"}
        </span>

        {/* Two peer views of the same data — neither is a fallback. */}
        <div
          role="tablist"
          aria-label="ATT&CK view"
          className="ml-auto flex items-center gap-1 rounded-lg border border-rw-border bg-rw-bg/40 p-0.5"
        >
          <button
            role="tab"
            id="attack-tab-chain"
            aria-selected={view === "chain"}
            aria-controls="attack-panel-chain"
            onClick={() => setView("chain")}
            className={tabClass(view === "chain")}
          >
            <Crosshair size={13} aria-hidden /> Kill chain
          </button>
          <button
            role="tab"
            id="attack-tab-ranked"
            aria-selected={view === "ranked"}
            aria-controls="attack-panel-ranked"
            onClick={() => setView("ranked")}
            className={tabClass(view === "ranked")}
          >
            <ListOrdered size={13} aria-hidden /> Ranked techniques
          </button>
        </div>
      </div>

      {parsed.length === 0 ? (
        <div className="flex h-24 items-center justify-center rounded-lg border border-dashed border-rw-border-subtle text-xs text-rw-dim">
          No ATT&amp;CK techniques mapped for this assessment.
        </div>
      ) : view === "chain" ? (
        <div
          role="tabpanel"
          id="attack-panel-chain"
          aria-labelledby="attack-tab-chain"
          tabIndex={-1}
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[26rem] border-collapse text-sm">
              <caption className="sr-only">
                Findings mapped to MITRE ATT&amp;CK tactics, listed in kill-chain order rather than
                by count. Tactics the hunt mapped nothing to are marked &quot;no findings
                mapped&quot;.
              </caption>
              <thead>
                <tr className="border-b border-rw-border-subtle text-left">
                  <th
                    scope="col"
                    className="w-8 pb-2 pr-2 text-[11px] font-semibold uppercase tracking-wider text-rw-dim"
                  >
                    <span aria-hidden>#</span>
                    <span className="sr-only">Position in the kill chain</span>
                  </th>
                  <th
                    scope="col"
                    className="pb-2 text-[11px] font-semibold uppercase tracking-wider text-rw-dim"
                  >
                    Tactic
                  </th>
                  <th
                    scope="col"
                    className="w-[48%] pb-2 pl-3 text-[11px] font-semibold uppercase tracking-wider text-rw-dim"
                  >
                    Findings
                  </th>
                </tr>
              </thead>
              <tbody>
                {tacticRows.map((r, i) => (
                  <tr key={r.id} className="border-b border-rw-border-subtle/40 last:border-0">
                    <td className="pr-2 font-mono text-[11px] tabular-nums text-rw-dim">{i + 1}</td>
                    <th
                      scope="row"
                      className={cn(
                        "py-1 pr-2 text-left text-xs font-medium",
                        r.observed ? "text-rw-text" : "text-rw-dim",
                      )}
                    >
                      {r.observed ? (
                        <button
                          onClick={() => showRanked(r.slug)}
                          className="rounded text-left underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rw-accent"
                        >
                          {r.name}
                          <span className="sr-only">
                            {" "}
                            — show the {r.techniques.length} technique
                            {r.techniques.length === 1 ? "" : "s"} behind this tactic
                          </span>
                        </button>
                      ) : (
                        r.name
                      )}
                      <span className="ml-1.5 font-mono text-[10px] font-normal text-rw-dim">
                        {r.id}
                      </span>
                    </th>
                    <CountCell
                      count={r.count}
                      max={chainMax}
                      observed={r.observed}
                      label={r.name}
                    />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {unmapped.length > 0 && (
            <p className="mt-2 text-[11px] text-rw-dim">
              {unmapped.length} technique{unmapped.length === 1 ? "" : "s"} could not be placed on a
              tactic and {unmapped.length === 1 ? "is" : "are"} listed under &quot;Unmapped&quot; in
              the ranked view.
            </p>
          )}

          <Legend max={chainMax} techniqueCount={parsed.length} />
        </div>
      ) : (
        <div
          role="tabpanel"
          id="attack-panel-ranked"
          aria-labelledby="attack-tab-ranked"
          tabIndex={-1}
        >
          {tacticFilter && (
            <div className="mb-2 flex items-center gap-2">
              <span className="text-[11px] text-rw-dim">Filtered to</span>
              <button
                onClick={() => setTacticFilter(null)}
                className="inline-flex items-center gap-1 rounded-md border border-rw-border bg-rw-surface/50 px-2 py-0.5 text-[11px] text-rw-muted transition-colors hover:text-rw-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rw-accent"
              >
                {tacticName(tacticFilter)}
                <X size={11} aria-hidden />
                <span className="sr-only">Clear tactic filter</span>
              </button>
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full min-w-[30rem] border-collapse text-sm">
              <caption className="sr-only">
                MITRE ATT&amp;CK techniques observed in this hunt, ranked by number of findings.
              </caption>
              <thead>
                <tr className="border-b border-rw-border-subtle text-left">
                  <th
                    scope="col"
                    className="pb-2 pr-2 text-[11px] font-semibold uppercase tracking-wider text-rw-dim"
                  >
                    Technique
                  </th>
                  <th
                    scope="col"
                    className="pb-2 pr-2 text-[11px] font-semibold uppercase tracking-wider text-rw-dim"
                  >
                    Tactic
                  </th>
                  <th
                    scope="col"
                    className="w-[38%] pb-2 pl-3 text-[11px] font-semibold uppercase tracking-wider text-rw-dim"
                  >
                    Findings
                  </th>
                </tr>
              </thead>
              <tbody>
                {rankedRows.map((t) => (
                  <tr
                    key={t.id || t.name}
                    className="border-b border-rw-border-subtle/40 last:border-0"
                  >
                    <th scope="row" className="py-1 pr-2 text-left text-xs font-medium text-rw-text">
                      {t.id && (
                        <span className="mr-1.5 font-mono text-[11px] text-rw-muted">{t.id}</span>
                      )}
                      {t.name}
                    </th>
                    <td className="py-1 pr-2 text-xs text-rw-muted">{tacticName(t.tactic)}</td>
                    <CountCell
                      count={t.count}
                      max={techniqueMax}
                      observed
                      label={`${t.id || t.name} ${t.name}`}
                    />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Legend max={techniqueMax} techniqueCount={parsed.length} />
        </div>
      )}
    </div>
  );
}

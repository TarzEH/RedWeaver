import { useEffect, useMemo, useState } from "react";
import { Grid3x3 } from "lucide-react";
import { api } from "../../services/api";
import { Skeleton } from "../ui/Skeleton";
import { cn } from "../../lib/cn";

interface Props {
  className?: string;
}

interface CategoryCount {
  category: string;
  files: number;
}

/** ATT&CK enterprise tactics, in kill-chain order. */
interface Tactic {
  id: string;
  name: string;
}

const TACTICS: Tactic[] = [
  { id: "TA0043", name: "Reconnaissance" },
  { id: "TA0042", name: "Resource Dev" },
  { id: "TA0001", name: "Initial Access" },
  { id: "TA0002", name: "Execution" },
  { id: "TA0003", name: "Persistence" },
  { id: "TA0004", name: "Privilege Escalation" },
  { id: "TA0005", name: "Defense Evasion" },
  { id: "TA0006", name: "Credential Access" },
  { id: "TA0007", name: "Discovery" },
  { id: "TA0008", name: "Lateral Movement" },
  { id: "TA0009", name: "Collection" },
  { id: "TA0011", name: "Command & Control" },
  { id: "TA0010", name: "Exfiltration" },
  { id: "TA0040", name: "Impact" },
];

/**
 * Map a KB category slug to an ATT&CK tactic id. The KB doesn't expose ATT&CK
 * tags, so this is a heuristic mapping over the slug tokens. Returns null when
 * no reasonable tactic applies.
 */
function tacticForCategory(slug: string): string | null {
  const s = (slug || "").toLowerCase();
  const has = (...keys: string[]) => keys.some((k) => s.includes(k));

  if (has("recon", "osint", "enumeration", "scanning", "footprint")) return "TA0043";
  if (has("web", "phishing", "initial-access", "initial_access", "exposure", "exploit-public"))
    return "TA0001";
  if (has("exploit", "rce", "code-execution", "command-injection", "execution")) return "TA0002";
  if (has("persistence", "backdoor", "implant")) return "TA0003";
  if (has("privesc", "privilege")) return "TA0004";
  if (has("evasion", "bypass", "obfuscation", "av", "edr")) return "TA0005";
  if (has("password", "credential", "hash", "kerberos", "brute")) return "TA0006";
  if (has("discovery")) return "TA0007";
  if (has("lateral", "pivot")) return "TA0008";
  if (has("tunnel", "tunneling", "c2", "command-and-control", "beacon")) return "TA0011";
  if (has("post-exploit", "post_exploit", "post-exploitation", "loot", "collection")) return "TA0009";
  if (has("exfil")) return "TA0010";
  if (has("impact", "ransom", "dos", "denial")) return "TA0040";
  if (has("resource")) return "TA0042";
  // Generic exploitation/exploits fall under Execution.
  if (has("exploits")) return "TA0002";
  return null;
}

function cellShade(count: number, max: number): { bg: string; border: string; text: string } {
  if (count <= 0 || max <= 0) {
    return { bg: "rgba(30,41,59,0.4)", border: "rgba(51,65,85,0.6)", text: "#64748b" };
  }
  const t = Math.max(0.18, count / max);
  return {
    bg: `rgba(59,130,246,${(0.12 + t * 0.4).toFixed(3)})`,
    border: `rgba(96,165,250,${(0.3 + t * 0.5).toFixed(3)})`,
    text: t > 0.55 ? "#f1f5f9" : "#cbd5e1",
  };
}

/**
 * MITRE ATT&CK-style coverage heatmap for the Knowledge Base. Maps KB
 * categories onto ATT&CK tactics (heuristic — the KB has no native ATT&CK tags)
 * and shades each tactic cell by the number of KB files covering it.
 */
export function KbAttackHeatmap({ className }: Props) {
  const [cats, setCats] = useState<CategoryCount[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.knowledge
      .categories()
      .then((d) => {
        if (!cancelled) {
          setCats((d.categories || []).map((c) => ({ category: c.category, files: c.files })));
        }
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const { counts, max, mapped, total } = useMemo(() => {
    const byTactic: Record<string, number> = {};
    let mappedCount = 0;
    let totalFiles = 0;
    for (const c of cats ?? []) {
      totalFiles += c.files;
      const tac = tacticForCategory(c.category);
      if (tac) {
        byTactic[tac] = (byTactic[tac] || 0) + c.files;
        mappedCount += c.files;
      }
    }
    const m = Object.values(byTactic).reduce((acc, v) => Math.max(acc, v), 0);
    return { counts: byTactic, max: m, mapped: mappedCount, total: totalFiles };
  }, [cats]);

  const covered = TACTICS.filter((t) => (counts[t.id] || 0) > 0).length;

  return (
    <div className={cn("rounded-xl border border-rw-border bg-rw-elevated p-4", className)}>
      <div className="mb-3 flex items-center gap-2">
        <Grid3x3 size={16} className="text-rw-accent" />
        <span className="text-sm font-semibold text-rw-text">ATT&CK Coverage (KB)</span>
        <span className="ml-auto text-xs text-rw-dim">
          {covered}/{TACTICS.length} tactics · {mapped}/{total} files mapped
        </span>
      </div>

      {error ? (
        <div className="flex h-24 items-center justify-center rounded-lg border border-dashed border-rw-border-subtle text-xs text-rw-dim">
          Could not load knowledge base categories.
        </div>
      ) : cats === null ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-16 rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          {TACTICS.map((t) => {
            const count = counts[t.id] || 0;
            const shade = cellShade(count, max);
            return (
              <div
                key={t.id}
                className="flex flex-col justify-between gap-2 rounded-lg border p-3 transition-colors"
                style={{ background: shade.bg, borderColor: shade.border }}
                title={`${t.id} ${t.name} — ${count} KB file${count === 1 ? "" : "s"}`}
              >
                <div className="flex flex-col">
                  <span className="font-mono text-[9px] uppercase tracking-wide" style={{ color: shade.text, opacity: 0.7 }}>
                    {t.id}
                  </span>
                  <span className="text-xs font-medium leading-snug" style={{ color: shade.text }}>
                    {t.name}
                  </span>
                </div>
                <span className="self-end text-lg font-bold tabular-nums" style={{ color: shade.text }}>
                  {count}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

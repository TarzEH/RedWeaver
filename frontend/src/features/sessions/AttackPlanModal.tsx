import { useEffect, useMemo, useState } from "react";
import { Crosshair, ExternalLink, X, Wand2, Upload } from "lucide-react";
import { api } from "../../services/api";
import type { AttackPlan } from "../../services/api";
import { Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Spinner";
import { useToast } from "../../components/ui/feedback";
import { openInNavigator, NAVIGATOR_URL } from "../../lib/navigator";
import { cn } from "../../lib/cn";

/** Curated ATT&CK techniques RedWeaver can exercise, grouped by tactic. Ids here
 * mirror the backend technique→tactic map so picks resolve to a real plan.
 * The operator can also paste a full Navigator layer for anything beyond this. */
const CATALOG: { tactic: string; label: string; techniques: { id: string; name: string }[] }[] = [
  {
    tactic: "reconnaissance",
    label: "Reconnaissance",
    techniques: [
      { id: "T1595", name: "Active Scanning" },
      { id: "T1590", name: "Gather Victim Network Information" },
      { id: "T1596", name: "Search Open Technical Databases" },
    ],
  },
  {
    tactic: "initial-access",
    label: "Initial Access",
    techniques: [
      { id: "T1190", name: "Exploit Public-Facing Application" },
      { id: "T1133", name: "External Remote Services" },
      { id: "T1078", name: "Valid Accounts" },
    ],
  },
  {
    tactic: "execution",
    label: "Execution",
    techniques: [
      { id: "T1059", name: "Command & Scripting Interpreter" },
      { id: "T1203", name: "Exploitation for Client Execution" },
    ],
  },
  {
    tactic: "discovery",
    label: "Discovery",
    techniques: [
      { id: "T1046", name: "Network Service Discovery" },
      { id: "T1083", name: "File & Directory Discovery" },
      { id: "T1087", name: "Account Discovery" },
      { id: "T1018", name: "Remote System Discovery" },
    ],
  },
  {
    tactic: "credential-access",
    label: "Credential Access",
    techniques: [
      { id: "T1110", name: "Brute Force" },
      { id: "T1003", name: "OS Credential Dumping" },
      { id: "T1552", name: "Unsecured Credentials" },
      { id: "T1558", name: "Steal/Forge Kerberos Tickets" },
    ],
  },
  {
    tactic: "privilege-escalation",
    label: "Privilege Escalation",
    techniques: [
      { id: "T1068", name: "Exploitation for Priv-Esc" },
      { id: "T1548", name: "Abuse Elevation Control" },
    ],
  },
  {
    tactic: "lateral-movement",
    label: "Lateral Movement",
    techniques: [
      { id: "T1021", name: "Remote Services" },
      { id: "T1210", name: "Exploitation of Remote Services" },
    ],
  },
  {
    tactic: "command-and-control",
    label: "Command & Control",
    techniques: [
      { id: "T1071", name: "Application Layer Protocol" },
      { id: "T1572", name: "Protocol Tunneling" },
    ],
  },
  {
    tactic: "exfiltration",
    label: "Exfiltration",
    techniques: [{ id: "T1041", name: "Exfiltration Over C2 Channel" }],
  },
];

interface AttackPlanModalProps {
  /** Representative target string (drives target-type scoping in the preview). */
  target: string;
  /** SSH config, if the hunt will target a host over SSH (enables SSH-tier agents). */
  sshConfig?: Record<string, unknown>;
  launching?: boolean;
  onClose: () => void;
  /** Launch the hunt scoped to the chosen techniques (empty = full comprehensive). */
  onLaunch: (techniques: string[]) => void;
}

export function AttackPlanModal({
  target,
  sshConfig,
  launching,
  onClose,
  onLaunch,
}: AttackPlanModalProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [layerText, setLayerText] = useState("");
  const [layerError, setLayerError] = useState<string | null>(null);
  const [plan, setPlan] = useState<AttackPlan | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const toast = useToast();

  const openPlanInNavigator = () => {
    if (!plan?.layer) return;
    openInNavigator(plan.layer, "redweaver-attack-plan.json");
    toast.info("Plan layer downloaded — in the Navigator choose 'Open Existing Layer → Upload'.");
  };

  // Techniques to send: explicit picks, else parsed-from-layer ids (best-effort
  // local parse just to drive the preview; the server re-parses authoritatively).
  const layerTechniques = useMemo(() => {
    if (!layerText.trim()) return null;
    try {
      const parsed = JSON.parse(layerText);
      setLayerError(null);
      const techs = Array.isArray(parsed?.techniques) ? parsed.techniques : [];
      return techs
        .filter((t: { enabled?: boolean }) => t?.enabled !== false)
        .map((t: { techniqueID?: string }) => (t?.techniqueID || "").toUpperCase())
        .filter(Boolean);
    } catch {
      setLayerError("Invalid JSON — paste a layer exported from the ATT&CK Navigator.");
      return null;
    }
  }, [layerText]);

  const activeTechniques = useMemo(
    () => (selected.size > 0 ? [...selected] : layerTechniques || []),
    [selected, layerTechniques],
  );

  // Debounced live preview from the backend.
  useEffect(() => {
    if (activeTechniques.length === 0) {
      setPlan(null);
      return;
    }
    let cancelled = false;
    setPreviewing(true);
    const t = setTimeout(() => {
      api.attack
        .plan({ target, attack_techniques: activeTechniques, ssh_config: sshConfig })
        .then((p) => !cancelled && setPlan(p))
        .catch(() => !cancelled && setPlan(null))
        .finally(() => !cancelled && setPreviewing(false));
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [activeTechniques, target, sshConfig]);

  // Esc to close
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const total = activeTechniques.length;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 flex max-h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-rw-border bg-rw-elevated shadow-2xl animate-fade-in">
        {/* Header */}
        <div className="flex items-center gap-3 border-b border-rw-border px-5 py-4">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-rw-accent/15">
            <Crosshair size={18} className="text-rw-accent" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="text-base font-semibold text-rw-text">Plan hunt with ATT&CK</h2>
            <p className="truncate text-xs text-rw-dim">
              Scope the hunt to specific MITRE ATT&CK techniques · {target || "no target"}
            </p>
          </div>
          <a
            href={NAVIGATOR_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md border border-rw-border px-2.5 py-1.5 text-xs text-rw-muted transition-colors hover:text-rw-text"
          >
            <ExternalLink size={13} /> Open Navigator
          </a>
          <button onClick={onClose} className="rounded-md p-1.5 text-rw-dim hover:text-rw-text">
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="grid flex-1 grid-cols-1 gap-0 overflow-hidden md:grid-cols-[1fr_300px]">
          {/* Left: pickers */}
          <div className="overflow-y-auto p-5">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {CATALOG.map((group) => (
                <div key={group.tactic}>
                  <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-rw-dim">
                    {group.label}
                  </div>
                  <div className="space-y-1">
                    {group.techniques.map((t) => {
                      const on = selected.has(t.id);
                      return (
                        <button
                          key={t.id}
                          onClick={() => toggle(t.id)}
                          className={cn(
                            "flex w-full items-center gap-2 rounded-lg border px-2.5 py-1.5 text-left text-xs transition-colors",
                            on
                              ? "border-rw-accent/50 bg-rw-accent/10 text-rw-text"
                              : "border-rw-border-subtle bg-rw-surface/30 text-rw-muted hover:border-rw-border",
                          )}
                        >
                          <span
                            className={cn(
                              "flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-sm border",
                              on ? "border-rw-accent bg-rw-accent" : "border-rw-border",
                            )}
                          >
                            {on && <span className="text-[9px] font-bold text-white">✓</span>}
                          </span>
                          <span className="font-mono text-[10px] text-rw-dim">{t.id}</span>
                          <span className="truncate">{t.name}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>

            {/* Navigator layer paste */}
            <div className="mt-5 border-t border-rw-border-subtle pt-4">
              <label className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-rw-dim">
                <Upload size={12} /> Or paste an ATT&CK Navigator layer (JSON)
              </label>
              <textarea
                value={layerText}
                onChange={(e) => setLayerText(e.target.value)}
                placeholder='{ "techniques": [ { "techniqueID": "T1190", "score": 1 } ] }'
                rows={4}
                className="w-full rounded-lg border border-rw-border bg-rw-surface/50 px-3 py-2 font-mono text-[11px] text-rw-text placeholder:text-rw-dim focus:border-rw-accent focus:outline-none"
              />
              {layerError && <p className="mt-1 text-[11px] text-rw-danger">{layerError}</p>}
              {selected.size > 0 && layerText.trim() && (
                <p className="mt-1 text-[11px] text-rw-dim">
                  Using the {selected.size} checked technique(s); clear them to use the pasted layer.
                </p>
              )}
            </div>
          </div>

          {/* Right: live plan preview */}
          <div className="overflow-y-auto border-t border-rw-border bg-rw-surface/30 p-5 md:border-l md:border-t-0">
            <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-rw-dim">
              <Wand2 size={12} /> Plan preview
              {previewing && <Spinner size="sm" />}
            </div>

            {total === 0 ? (
              <p className="text-xs text-rw-dim">
                Pick techniques (or paste a layer) to see which agents the hunt will run.
              </p>
            ) : (
              <div className="space-y-3 text-xs">
                <div>
                  <div className="text-rw-dim">Techniques in scope</div>
                  <div className="font-mono text-sm font-semibold text-rw-text">{total}</div>
                </div>
                {plan && (
                  <>
                    <div>
                      <div className="mb-1 text-rw-dim">Target type</div>
                      <span className="rounded border border-rw-border bg-rw-surface px-1.5 py-0.5 font-mono text-[10px] text-rw-muted">
                        {plan.target_type}
                      </span>
                    </div>
                    <div>
                      <div className="mb-1 text-rw-dim">Tactics</div>
                      <div className="flex flex-wrap gap-1">
                        {plan.tactics.length === 0 && <span className="text-rw-dim">—</span>}
                        {plan.tactics.map((t) => (
                          <span
                            key={t}
                            className="rounded border border-rw-accent/30 bg-rw-accent/10 px-1.5 py-0.5 text-[10px] text-rw-accent-hover"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="mb-1 text-rw-dim">Agents that will run</div>
                      <div className="flex flex-wrap gap-1">
                        {plan.agent_selection.map((a) => (
                          <span
                            key={a}
                            className="rounded border border-rw-border bg-rw-surface px-1.5 py-0.5 font-mono text-[10px] text-rw-muted"
                          >
                            {a}
                          </span>
                        ))}
                      </div>
                    </div>
                    {plan.unknown.length > 0 && (
                      <div className="rounded-lg border border-rw-warning/30 bg-rw-warning/10 px-2.5 py-2 text-[11px] text-rw-warning">
                        {plan.unknown.length} technique(s) not in RedWeaver's map and won't scope
                        agents: {plan.unknown.join(", ")}
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-3 border-t border-rw-border px-5 py-3">
          <p className="text-[11px] text-rw-dim">
            {total === 0
              ? "No techniques selected — launches a full comprehensive hunt."
              : `Hunt scoped to ${total} ATT&CK technique${total === 1 ? "" : "s"}.`}
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              icon={<ExternalLink size={14} />}
              disabled={!plan?.layer || total === 0}
              onClick={openPlanInNavigator}
            >
              Open plan in Navigator
            </Button>
            <Button variant="ghost" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              loading={launching}
              icon={<Crosshair size={14} />}
              onClick={() => onLaunch(activeTechniques)}
            >
              {total === 0 ? "Launch comprehensive" : "Launch scoped hunt"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

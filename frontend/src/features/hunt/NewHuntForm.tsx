import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Crosshair,
  DollarSign,
  Lock,
  Play,
  Target as TargetIcon,
} from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Input, fieldBase } from "../../components/ui/Input";
import { AttackPlanModal } from "../sessions/AttackPlanModal";
import { cn } from "../../lib/cn";
import type { SSHConfig } from "../../types/api";

/** What the form hands back; the caller turns it into the run-creation POST. */
export interface NewHuntValues {
  target: string;
  objective: string;
  scope: string;
  budget_usd?: number;
  ssh_config?: SSHConfig;
  attack_techniques?: string[];
}

interface NewHuntFormProps {
  submitting: boolean;
  error: string | null;
  onSubmit: (values: NewHuntValues) => void;
}

/**
 * The three objectives the pipeline actually distinguishes — the same vocabulary
 * the old free-text parser could recover, now stated instead of guessed.
 */
const OBJECTIVES = [
  {
    value: "comprehensive",
    label: "Comprehensive",
    hint: "Every agent: recon, crawl, scan, fuzz, analyse. Slowest, most thorough.",
  },
  { value: "quick", label: "Quick", hint: "Fewer passes. Faster and cheaper, shallower coverage." },
  { value: "stealth", label: "Stealth", hint: "Low-noise probing; skips the loud, aggressive scans." },
] as const;

const SSH_FIELDS = [
  { label: "Host", key: "host" as const, placeholder: "10.10.14.5", type: "text" },
  { label: "User", key: "username" as const, placeholder: "root", type: "text" },
  { label: "Password", key: "password" as const, placeholder: "Optional", type: "password" },
  { label: "Key path", key: "key_path" as const, placeholder: "/keys/id_rsa", type: "text" },
] as const;

/** Shared treatment for the optional-section disclosure buttons. */
const discloseCls =
  "flex w-full items-center gap-2 rounded-md px-1 py-1 text-xs text-rw-dim transition-colors " +
  "hover:text-rw-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rw-accent";

/**
 * State 1 — start a hunt.
 *
 * This replaces a chat box that ran a regex over the message to recover exactly
 * three things (target, `quick`, `stealth`) and could reject a valid target that
 * lacked a scan verb. A form cannot fail that way, so every control that used to
 * hide in the chat empty state lives here instead.
 */
export function NewHuntForm({ submitting, error, onSubmit }: NewHuntFormProps) {
  const [target, setTarget] = useState("");
  const [objective, setObjective] = useState<string>("comprehensive");
  const [scope, setScope] = useState("");
  const [showSSH, setShowSSH] = useState(false);
  const [sshConfig, setSSHConfig] = useState<SSHConfig>({ host: "", username: "root", port: 22 });
  const [showBudget, setShowBudget] = useState(false);
  // Kept as a string so the field can be cleared; parsed only on submit.
  const [budgetUsd, setBudgetUsd] = useState("");
  const [techniques, setTechniques] = useState<string[]>([]);
  const [showAttackPlan, setShowAttackPlan] = useState(false);

  const trimmedTarget = target.trim();
  const canSubmit = trimmedTarget.length > 0 && !submitting;

  const buildValues = (attackTechniques: string[]): NewHuntValues => {
    const values: NewHuntValues = { target: trimmedTarget, objective, scope: scope.trim() };
    // Only send a usable ceiling; anything else means "no limit".
    const budget = Number(budgetUsd);
    if (budgetUsd.trim() && Number.isFinite(budget) && budget > 0) values.budget_usd = budget;
    if (sshConfig.host && sshConfig.username) values.ssh_config = sshConfig;
    if (attackTechniques.length > 0) values.attack_techniques = attackTechniques;
    return values;
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    onSubmit(buildValues(techniques));
  };

  return (
    <div className="flex-1 overflow-y-auto bg-rw-bg px-4 py-8">
      {showAttackPlan && (
        <AttackPlanModal
          target={trimmedTarget}
          sshConfig={sshConfig.host ? (sshConfig as unknown as Record<string, unknown>) : undefined}
          launching={submitting}
          onClose={() => setShowAttackPlan(false)}
          onLaunch={(picked) => {
            setTechniques(picked);
            setShowAttackPlan(false);
            if (trimmedTarget) onSubmit(buildValues(picked));
          }}
        />
      )}

      <form onSubmit={submit} className="mx-auto w-full max-w-xl space-y-6">
        <header className="text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-rw-surface">
            <Crosshair size={24} className="text-rw-accent" aria-hidden />
          </div>
          <h2 className="text-lg font-semibold text-rw-text">Start a hunt</h2>
          <p className="mt-1 text-sm text-rw-dim">
            Name a target and how hard to push. AI agents run recon, scanning, fuzzing and analysis.
          </p>
        </header>

        {error && (
          <p
            role="alert"
            className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-400"
          >
            {error}
          </p>
        )}

        {/* Target */}
        <div>
          <label htmlFor="hunt-target" className="mb-1.5 block text-xs font-medium text-rw-muted">
            Target
          </label>
          <Input
            id="hunt-target"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder="https://example.com · example.com · 192.168.1.0/24"
            icon={<TargetIcon size={14} />}
            autoFocus
            spellCheck={false}
            className="font-mono"
          />
          <p className="mt-1.5 text-xs text-rw-dim">A URL, domain, host, or CIDR range.</p>
        </div>

        {/* Objective */}
        <fieldset>
          <legend className="mb-1.5 text-xs font-medium text-rw-muted">Objective</legend>
          <div className="grid gap-2 sm:grid-cols-3">
            {OBJECTIVES.map((opt) => {
              const active = objective === opt.value;
              return (
                <label
                  key={opt.value}
                  className={cn(
                    "cursor-pointer rounded-lg border p-3 transition-colors",
                    "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-rw-accent",
                    active
                      ? "border-rw-accent/50 bg-rw-accent/10"
                      : "border-rw-border bg-rw-elevated hover:border-rw-border",
                  )}
                >
                  <input
                    type="radio"
                    name="objective"
                    value={opt.value}
                    checked={active}
                    onChange={() => setObjective(opt.value)}
                    className="sr-only"
                  />
                  <span
                    className={cn(
                      "block text-sm font-medium",
                      active ? "text-rw-accent" : "text-rw-text",
                    )}
                  >
                    {opt.label}
                  </span>
                  <span className="mt-1 block text-[11px] leading-snug text-rw-dim">{opt.hint}</span>
                </label>
              );
            })}
          </div>
        </fieldset>

        {/* Scope */}
        <div>
          <label htmlFor="hunt-scope" className="mb-1.5 block text-xs font-medium text-rw-muted">
            Scope <span className="font-normal text-rw-dim">(optional)</span>
          </label>
          <Input
            id="hunt-scope"
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            placeholder="*.example.com, exclude /admin"
            spellCheck={false}
          />
          <p className="mt-1.5 text-xs text-rw-dim">
            What the agents may and may not touch. Recorded on the run and shown in the report.
          </p>
        </div>

        {/* Spend limit */}
        <div className="rounded-lg border border-rw-border bg-rw-elevated p-3">
          <button type="button" onClick={() => setShowBudget((v) => !v)} className={discloseCls} aria-expanded={showBudget}>
            <DollarSign size={12} aria-hidden />
            <span className="font-medium">Spend limit</span>
            {Number(budgetUsd) > 0 && (
              <span className="font-mono text-[10px] tabular-nums text-rw-accent">
                ${Number(budgetUsd).toFixed(2)}
              </span>
            )}
            <span className="ml-auto" aria-hidden>
              {showBudget ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            </span>
          </button>
          {showBudget && (
            <div className="mt-3 animate-fade-in">
              <div className="flex items-center gap-2">
                <label htmlFor="budget-usd" className="w-20 shrink-0 text-[11px] text-rw-dim">
                  Max USD
                </label>
                <input
                  id="budget-usd"
                  type="number"
                  min="0"
                  step="0.25"
                  placeholder="No limit"
                  value={budgetUsd}
                  onChange={(e) => setBudgetUsd(e.target.value)}
                  className={cn(fieldBase, "w-28 rounded border-rw-border px-2 py-1 text-xs tabular-nums")}
                />
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-rw-dim">
                The hunt stops once estimated LLM spend reaches this, keeping whatever it found.
                Checked between agent tasks, so a single task can overshoot slightly.
              </p>
            </div>
          )}
        </div>

        {/* SSH access */}
        <div className="rounded-lg border border-rw-border bg-rw-elevated p-3">
          <button type="button" onClick={() => setShowSSH((v) => !v)} className={discloseCls} aria-expanded={showSSH}>
            <Lock size={12} aria-hidden />
            <span className="font-medium">SSH access</span>
            {sshConfig.host && (
              <span className="text-[10px] font-medium text-rw-accent">Enabled</span>
            )}
            <span className="ml-auto" aria-hidden>
              {showSSH ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            </span>
          </button>
          {showSSH && (
            <div className="mt-3 animate-fade-in space-y-2">
              {SSH_FIELDS.map((field) => (
                <div key={field.key} className="flex items-center gap-2">
                  <label htmlFor={`ssh-${field.key}`} className="w-20 shrink-0 text-[11px] text-rw-dim">
                    {field.label}
                  </label>
                  <input
                    id={`ssh-${field.key}`}
                    type={field.type}
                    placeholder={field.placeholder}
                    value={String((sshConfig as unknown as Record<string, unknown>)[field.key] || "")}
                    onChange={(e) =>
                      setSSHConfig((c) => ({ ...c, [field.key]: e.target.value || undefined }))
                    }
                    className={cn(fieldBase, "w-auto flex-1 rounded border-rw-border px-2 py-1 text-xs")}
                  />
                </div>
              ))}
              <div className="flex items-center gap-2">
                <label htmlFor="ssh-port" className="w-20 shrink-0 text-[11px] text-rw-dim">
                  Port
                </label>
                <input
                  id="ssh-port"
                  type="number"
                  value={sshConfig.port || 22}
                  onChange={(e) =>
                    setSSHConfig((c) => ({ ...c, port: parseInt(e.target.value, 10) || 22 }))
                  }
                  className={cn(fieldBase, "w-24 rounded border-rw-border px-2 py-1 text-xs tabular-nums")}
                />
              </div>
              <p className="text-[11px] leading-relaxed text-rw-dim">
                Enables the SSH-tier agents so the hunt can work from on the host, not just against
                it.
              </p>
            </div>
          )}
        </div>

        {/* Submit */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="submit"
            size="lg"
            disabled={!canSubmit}
            loading={submitting}
            icon={<Play size={14} />}
            className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rw-accent"
          >
            Start hunt
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="lg"
            disabled={!trimmedTarget || submitting}
            onClick={() => setShowAttackPlan(true)}
            title={
              trimmedTarget
                ? "Scope the hunt to chosen MITRE ATT&CK techniques"
                : "Enter a target first"
            }
            className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rw-accent"
          >
            ATT&CK focus{techniques.length > 0 ? ` (${techniques.length})` : ""}
          </Button>
        </div>
      </form>
    </div>
  );
}

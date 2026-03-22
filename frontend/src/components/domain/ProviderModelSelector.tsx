/**
 * ProviderModelSelector — provider + model picker for RedWeaver settings.
 *
 * Uses Tailwind v4 utility classes with rw-* theme tokens.
 * Replaces the inline provider cards previously in SettingsView.
 */

import { CheckCircle, XCircle, Wifi, WifiOff, Loader2, Zap, Info } from "lucide-react";
import { PROVIDERS, PROVIDER_KEYS, sortModelsDesc } from "../../config/providers";
import type { ModelDef } from "../../config/providers";
import type { KeysStatus, OllamaModel } from "../../types/api";

/* ── Provider logos (inline SVG) ─────────────────────── */

function OpenAILogo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.998 5.998 0 0 0-3.998 2.9 6.05 6.05 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855l-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023l-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135l-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365l2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z" fill="currentColor" />
    </svg>
  );
}

function AnthropicLogo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M13.827 3.52h3.603L24 20.48h-3.603l-6.57-16.96zm-7.258 0L0 20.48h3.505l1.396-3.79h7.227l1.395 3.79h3.505L10.46 3.52H6.57zm1.38 5.085l2.397 5.965H5.552l2.397-5.965z" fill="currentColor" />
    </svg>
  );
}

function GoogleLogo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
    </svg>
  );
}

function OllamaLogo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8z" fill="currentColor" opacity="0.3" />
      <path d="M12 4c-1.1 0-2.1.23-3.04.63C10.17 5.52 11 6.9 11 8.5c0 .17-.02.33-.04.5h2.08c-.02-.17-.04-.33-.04-.5 0-1.6.83-2.98 2.04-3.87A7.96 7.96 0 0 0 12 4z" fill="currentColor" />
      <circle cx="9" cy="12" r="1.5" fill="currentColor" />
      <circle cx="15" cy="12" r="1.5" fill="currentColor" />
      <path d="M12 17.5c-2.33 0-4.32-1.45-5.12-3.5h-.38c-.83 0-1.5-.67-1.5-1.5S5.67 11 6.5 11h.38a5.98 5.98 0 0 1 10.24 0h.38c.83 0 1.5.67 1.5 1.5s-.67 1.5-1.5 1.5h-.38c-.8 2.05-2.79 3.5-5.12 3.5z" fill="currentColor" opacity="0.6" />
      <path d="M8.5 15.5c.55.31 1.13.54 1.75.68.14-.45.55-.78 1.03-.78h1.44c.48 0 .89.33 1.03.78.62-.14 1.2-.37 1.75-.68" stroke="currentColor" strokeWidth="0.8" strokeLinecap="round" fill="none" />
    </svg>
  );
}

function MetaLogo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M6.915 4.03c-1.968 0-3.293 1.09-4.079 2.466C1.748 8.18 1.396 10.596 1.396 12c0 2.035.592 3.72 1.756 4.837 1.091 1.049 2.478 1.4 3.763 1.4.989 0 2.067-.31 3.122-1.16.972-.783 1.991-2.025 3.13-3.912l.48-.797.477.797c1.138 1.887 2.158 3.129 3.13 3.912 1.055.85 2.133 1.16 3.122 1.16 1.285 0 2.672-.351 3.763-1.4 1.164-1.116 1.756-2.802 1.756-4.837 0-1.404-.352-3.82-1.44-5.504-.786-1.376-2.111-2.466-4.079-2.466-1.075 0-2.165.398-3.217 1.353-1.003.91-2.022 2.3-3.037 4.216l-.454.858-.454-.858c-1.015-1.916-2.034-3.306-3.037-4.216C9.08 4.428 7.99 4.03 6.915 4.03zm0 1.675c.704 0 1.496.272 2.346 1.044.862.783 1.754 2.01 2.69 3.778L12 10.63l.049-.103c.936-1.768 1.828-2.995 2.69-3.778.85-.772 1.642-1.044 2.346-1.044 1.395 0 2.316.746 2.906 1.778.65 1.14.981 2.895.981 4.517 0 1.697-.444 2.886-1.216 3.627-.749.719-1.7.957-2.632.957-.655 0-1.399-.222-2.207-.874-.772-.622-1.606-1.61-2.525-3.13l-.79-1.305h0l-.063-.104-.791 1.31c-.92 1.522-1.755 2.51-2.528 3.133-.808.65-1.55.87-2.205.87-.932 0-1.883-.238-2.632-.957C2.84 14.886 2.396 13.697 2.396 12c0-1.622.331-3.377.981-4.517.59-1.032 1.511-1.778 2.906-1.778h.632z" fill="currentColor" />
    </svg>
  );
}

function ProviderLogo({ provider, size = 28 }: { provider: string; size?: number }) {
  switch (provider) {
    case "openai":    return <OpenAILogo size={size} />;
    case "anthropic": return <AnthropicLogo size={size} />;
    case "google":    return <GoogleLogo size={size} />;
    case "ollama":    return <OllamaLogo size={size} />;
    case "meta":      return <MetaLogo size={size} />;
    default:          return null;
  }
}

/* ── Props ────────────────────────────────────────────── */

export interface ProviderModelSelectorProps {
  activeProvider: string;
  providerModels: Record<string, string>;
  /** Dynamically fetched models keyed by provider. */
  dynamicModels: Record<string, { value: string; label: string }[]>;
  /** Ollama models (separate shape with size/modified_at). */
  ollamaModels: OllamaModel[];
  apiKeyInputs: Record<string, string>;
  ollamaUrl: string;
  status: KeysStatus | null;
  ollamaHealth: "connected" | "disconnected" | "checking";
  loading: boolean;
  onProviderChange: (provider: string) => void;
  onModelSelect: (provider: string, model: string) => void;
  onApiKeyChange: (provider: string, value: string) => void;
  onOllamaUrlChange: (url: string) => void;
  onTestOllama: () => void;
}

/* ── Helper: merge dynamic + static models ───────────── */

function getEffectiveModels(
  provider: string,
  dynamicModels: Record<string, { value: string; label: string }[]>,
  ollamaModels: OllamaModel[],
): { id: string; label: string; date: string }[] {
  const def = PROVIDERS[provider];
  if (!def) return [];

  // Ollama: use dynamic models only
  if (provider === "ollama") {
    return ollamaModels.map((m) => ({
      id: m.name,
      label: m.name,
      date: m.modified_at ? m.modified_at.slice(0, 7) : "2024-01",
    }));
  }

  // For providers with dynamic fetching: use dynamic list if available, else fallback
  if (def.dynamicModels && dynamicModels[provider]?.length) {
    // Dynamic models don't carry a date, so we preserve ordering (already sorted by backend)
    return dynamicModels[provider].map((m, i) => ({
      id: m.value,
      label: m.label,
      // Assign descending synthetic dates to preserve backend sort order
      date: `9999-${String(99 - i).padStart(2, "0")}`,
    }));
  }

  // Fallback: use static config
  return [...def.models];
}

/* ── Helper: is provider configured ──────────────────── */

function isConfigured(provider: string, status: KeysStatus | null): boolean {
  if (!status) return false;
  switch (provider) {
    case "openai":    return status.openai_configured;
    case "anthropic": return status.anthropic_configured;
    case "google":    return status.google_configured ?? false;
    case "ollama":    return status.ollama_configured;
    case "meta":      return status.ollama_configured; // Meta routes through Ollama
    default:          return false;
  }
}

/* ── Sub-component: Model Dropdown ───────────────────── */

function ModelDropdown({
  provider,
  models,
  selected,
  disabled,
  onSelect,
}: {
  provider: string;
  models: { id: string; label: string; date: string }[];
  selected: string;
  disabled: boolean;
  onSelect: (provider: string, model: string) => void;
}) {
  const sorted = sortModelsDesc(models as ModelDef[]);
  const latestId = sorted[0]?.id;

  if (sorted.length === 0) {
    return (
      <div className="text-rw-dim text-[13px] italic py-1.5">
        {provider === "ollama"
          ? "No models found — is Ollama running?"
          : "No models available"}
      </div>
    );
  }

  return (
    <div className="relative">
      <select
        className="w-full bg-white/[0.05] border border-white/[0.08] rounded-lg px-3 py-2 text-[13px]
                   text-rw-text appearance-none cursor-pointer transition-colors duration-150
                   hover:border-white/[0.15] focus:border-rw-accent/50 focus:outline-none
                   disabled:opacity-40 disabled:cursor-not-allowed"
        value={selected}
        onChange={(e) => onSelect(provider, e.target.value)}
        disabled={disabled}
      >
        {sorted.map((m) => (
          <option key={m.id} value={m.id} className="bg-[#0d1117] text-rw-text">
            {m.label}{m.id === latestId ? " ★ Latest" : ""}{m.date.startsWith("9999") ? "" : ` (${m.date})`}
          </option>
        ))}
      </select>
      {/* Dropdown chevron */}
      <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-rw-muted">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path d="M2 3.5L5 6.5L8 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </div>
  );
}

/* ── Sub-component: Provider Card ────────────────────── */

function ProviderCard({
  providerKey,
  isActive,
  model,
  models,
  apiKeyValue,
  ollamaUrl,
  ollamaHealth,
  configured,
  loading,
  onActivate,
  onModelSelect,
  onApiKeyChange,
  onOllamaUrlChange,
  onTestOllama,
}: {
  providerKey: string;
  isActive: boolean;
  model: string;
  models: { id: string; label: string; date: string }[];
  apiKeyValue: string;
  ollamaUrl: string;
  ollamaHealth: "connected" | "disconnected" | "checking";
  configured: boolean;
  loading: boolean;
  onActivate: () => void;
  onModelSelect: (provider: string, model: string) => void;
  onApiKeyChange: (provider: string, value: string) => void;
  onOllamaUrlChange: (url: string) => void;
  onTestOllama: () => void;
}) {
  const def = PROVIDERS[providerKey];
  if (!def) return null;

  const isMeta = !!def.routesThrough;

  return (
    <div
      className={`relative rounded-xl border p-5 transition-all duration-200
        ${isActive
          ? "border-rw-accent/35 bg-rw-accent/[0.03] shadow-[0_0_20px_rgba(0,212,170,0.06)]"
          : "border-white/[0.06] bg-white/[0.02] hover:border-white/[0.12]"
        }`}
    >
      {/* Header: logo + name + radio */}
      <div className="flex items-center gap-3 mb-4">
        <div
          className="flex items-center justify-center w-10 h-10 rounded-lg"
          style={{ background: `${def.color}18`, color: def.color }}
        >
          <ProviderLogo provider={providerKey} size={24} />
        </div>
        <div className="flex-1 min-w-0">
          <span className="block text-[14px] font-semibold text-rw-text">{def.name}</span>
          <span className="block text-[12px] text-rw-muted">{def.description}</span>
        </div>
        <label className="flex items-center gap-1.5 cursor-pointer shrink-0">
          <input
            type="radio"
            name="rw-provider"
            className="w-4 h-4 accent-[#00d4aa] cursor-pointer"
            checked={isActive}
            onChange={onActivate}
          />
          {isActive && (
            <span className="flex items-center gap-1 text-[11px] font-medium text-rw-accent">
              <Zap size={10} /> Active
            </span>
          )}
        </label>
      </div>

      {/* API key input (only for providers that need one) */}
      {def.requiresApiKey && (
        <div className="mb-3">
          <label className="block text-[12px] font-medium text-rw-muted mb-1">API Key</label>
          <input
            type="password"
            placeholder={configured ? "••••••••••••" : def.keyPlaceholder}
            value={apiKeyValue}
            onChange={(e) => onApiKeyChange(providerKey, e.target.value)}
            disabled={loading}
            autoComplete="off"
            className="w-full bg-white/[0.05] border border-white/[0.08] rounded-lg px-3 py-2
                       text-[13px] text-rw-text placeholder:text-rw-dim transition-colors duration-150
                       hover:border-white/[0.15] focus:border-rw-accent/50 focus:outline-none
                       disabled:opacity-40"
          />
        </div>
      )}

      {/* Ollama URL input */}
      {def.requiresBaseUrl && (
        <div className="mb-3">
          <label className="block text-[12px] font-medium text-rw-muted mb-1">Base URL</label>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder={def.urlPlaceholder}
              value={ollamaUrl}
              onChange={(e) => onOllamaUrlChange(e.target.value)}
              disabled={loading}
              autoComplete="off"
              className="flex-1 bg-white/[0.05] border border-white/[0.08] rounded-lg px-3 py-2
                         text-[13px] text-rw-text placeholder:text-rw-dim transition-colors duration-150
                         hover:border-white/[0.15] focus:border-rw-accent/50 focus:outline-none
                         disabled:opacity-40"
            />
            <button
              type="button"
              onClick={onTestOllama}
              disabled={loading}
              className="flex items-center gap-1 px-3 py-2 rounded-lg text-[12px] font-medium
                         bg-white/[0.05] border border-white/[0.08] text-rw-muted
                         hover:border-white/[0.15] hover:text-rw-text transition-colors duration-150
                         disabled:opacity-40"
            >
              {ollamaHealth === "checking" ? (
                <Loader2 size={12} className="animate-spin" />
              ) : ollamaHealth === "connected" ? (
                <Wifi size={12} />
              ) : (
                <WifiOff size={12} />
              )}
              Test
            </button>
          </div>
          {ollamaHealth !== "checking" && (
            <span className={`inline-flex items-center gap-1 mt-1.5 text-[11px] font-medium
              ${ollamaHealth === "connected" ? "text-rw-success" : "text-rw-danger"}`}>
              {ollamaHealth === "connected" ? <><Wifi size={10} /> Connected</> : <><WifiOff size={10} /> Disconnected</>}
            </span>
          )}
        </div>
      )}

      {/* Meta: Ollama requirement notice */}
      {isMeta && (
        <div className="flex items-start gap-2 mb-3 p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.05]">
          <Info size={14} className="text-rw-muted shrink-0 mt-0.5" />
          <div className="text-[12px] text-rw-muted leading-relaxed">
            Requires Ollama running locally. Pull models first:
            <code className="block mt-1 text-[11px] text-rw-accent/80 font-mono">ollama pull llama3.3</code>
          </div>
        </div>
      )}

      {/* Model selector */}
      <div className="mb-3">
        <label className="block text-[12px] font-medium text-rw-muted mb-1">Model</label>
        <ModelDropdown
          provider={providerKey}
          models={models}
          selected={model}
          disabled={!isActive}
          onSelect={onModelSelect}
        />
      </div>

      {/* Status badge */}
      <div className="flex items-center">
        {configured ? (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-rw-success">
            <CheckCircle size={12} /> Configured
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-rw-dim">
            <XCircle size={12} /> Not configured
          </span>
        )}
      </div>
    </div>
  );
}

/* ── Main Component ──────────────────────────────────── */

export function ProviderModelSelector({
  activeProvider,
  providerModels,
  dynamicModels,
  ollamaModels,
  apiKeyInputs,
  ollamaUrl,
  status,
  ollamaHealth,
  loading,
  onProviderChange,
  onModelSelect,
  onApiKeyChange,
  onOllamaUrlChange,
  onTestOllama,
}: ProviderModelSelectorProps) {
  return (
    <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
      {PROVIDER_KEYS.map((key) => {
        const models = getEffectiveModels(key, dynamicModels, ollamaModels);
        const currentModel = providerModels[key] || models[0]?.id || "";

        return (
          <ProviderCard
            key={key}
            providerKey={key}
            isActive={activeProvider === key}
            model={currentModel}
            models={models}
            apiKeyValue={apiKeyInputs[key] || ""}
            ollamaUrl={ollamaUrl}
            ollamaHealth={ollamaHealth}
            configured={isConfigured(key, status)}
            loading={loading}
            onActivate={() => onProviderChange(key)}
            onModelSelect={onModelSelect}
            onApiKeyChange={onApiKeyChange}
            onOllamaUrlChange={onOllamaUrlChange}
            onTestOllama={onTestOllama}
          />
        );
      })}
    </div>
  );
}

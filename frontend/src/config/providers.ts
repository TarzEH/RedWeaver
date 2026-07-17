/** Static provider & model definitions for RedWeaver. */

export interface ModelDef {
  id: string;
  label: string;
  /** "YYYY-MM" for deterministic sort (latest first). */
  date: string;
}

export interface ProviderDef {
  name: string;
  description: string;
  /** Hex color for the provider logo accent. */
  color: string;
  requiresApiKey: boolean;
  requiresBaseUrl: boolean;
  keyPlaceholder?: string;
  urlPlaceholder?: string;
  /** Whether models are fetched dynamically from the backend. */
  dynamicModels: boolean;
  /** Backend route for dynamic model fetching. */
  modelsEndpoint?: string;
  /** If set, this provider routes through another provider's backend (e.g. Meta → Ollama). */
  routesThrough?: string;
  /** Fallback / static model list (used when dynamic fetch fails or is unavailable). */
  models: ModelDef[];
}

/** Sort models by date descending (latest first). */
export function sortModelsDesc(models: ModelDef[]): ModelDef[] {
  return [...models].sort((a, b) => b.date.localeCompare(a.date));
}

export const PROVIDERS: Record<string, ProviderDef> = {
  openai: {
    name: "OpenAI",
    description: "GPT-5.4, GPT-5 Nano, o4-mini",
    color: "#10a37f",
    requiresApiKey: true,
    requiresBaseUrl: false,
    keyPlaceholder: "sk-...",
    dynamicModels: true,
    modelsEndpoint: "/api/settings/models/openai",
    models: [
      { id: "gpt-5.4", label: "GPT-5.4", date: "2026-03" },
      { id: "gpt-5.2", label: "GPT-5.2", date: "2025-12" },
      { id: "gpt-5", label: "GPT-5", date: "2025-08" },
      { id: "gpt-5-mini", label: "GPT-5 Mini", date: "2025-08" },
      { id: "gpt-5-nano", label: "GPT-5 Nano", date: "2025-08" },
      { id: "gpt-4.1", label: "GPT-4.1", date: "2025-04" },
      { id: "o4-mini", label: "o4-mini", date: "2025-04" },
    ],
  },

  anthropic: {
    name: "Anthropic",
    description: "Claude 4.6 Sonnet, Opus, Haiku",
    color: "#cc965a",
    requiresApiKey: true,
    requiresBaseUrl: false,
    keyPlaceholder: "sk-ant-...",
    dynamicModels: true,
    modelsEndpoint: "/api/settings/models/anthropic",
    models: [
      { id: "claude-sonnet-4-6-20260218", label: "Claude Sonnet 4.6", date: "2026-02" },
      { id: "claude-opus-4-6-20260204", label: "Claude Opus 4.6", date: "2026-02" },
      { id: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5", date: "2025-10" },
      { id: "claude-sonnet-4-20250514", label: "Claude Sonnet 4", date: "2025-05" },
      { id: "claude-opus-4-20250514", label: "Claude Opus 4", date: "2025-05" },
    ],
  },

  google: {
    name: "Google",
    description: "Gemini 3.1, Gemini 3, Gemini 2.5",
    color: "#4285f4",
    requiresApiKey: true,
    requiresBaseUrl: false,
    keyPlaceholder: "AIza...",
    dynamicModels: true,
    modelsEndpoint: "/api/settings/models/google",
    models: [
      { id: "gemini-3.1-pro", label: "Gemini 3.1 Pro", date: "2026-02" },
      { id: "gemini-3.1-flash-lite", label: "Gemini 3.1 Flash Lite", date: "2026-03" },
      { id: "gemini-3-flash", label: "Gemini 3 Flash", date: "2026-01" },
      { id: "gemini-2.5-pro", label: "Gemini 2.5 Pro", date: "2025-09" },
      { id: "gemini-2.5-flash", label: "Gemini 2.5 Flash", date: "2025-05" },
      { id: "gemini-2.0-flash", label: "Gemini 2.0 Flash", date: "2025-02" },
    ],
  },

  ollama: {
    name: "Ollama",
    description: "Local models — Llama, Mistral, Qwen",
    color: "#e8edf4",
    requiresApiKey: false,
    requiresBaseUrl: true,
    urlPlaceholder: "http://localhost:11434",
    dynamicModels: true,
    modelsEndpoint: "/api/settings/ollama/models",
    models: [],
  },

  meta: {
    name: "Meta",
    description: "Llama 3.3, Llama 3.2 (via Ollama)",
    color: "#0668E1",
    requiresApiKey: false,
    requiresBaseUrl: false,
    dynamicModels: false,
    routesThrough: "ollama",
    models: [
      { id: "llama3.3:latest", label: "Llama 3.3 70B", date: "2024-12" },
      { id: "llama3.2:latest", label: "Llama 3.2 3B", date: "2024-09" },
      { id: "llama3.2:1b", label: "Llama 3.2 1B", date: "2024-09" },
      { id: "llama3.1:latest", label: "Llama 3.1 8B", date: "2024-07" },
    ],
  },
};

/** All provider keys in display order. */
export const PROVIDER_KEYS = Object.keys(PROVIDERS);

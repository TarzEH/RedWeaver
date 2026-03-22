import { useEffect, useState, useCallback } from "react";
import { CheckCircle, XCircle, Wrench, Zap } from "lucide-react";
import { Card, CardHeader } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { PageHeader } from "../../components/layout/PageHeader";
import { ProviderModelSelector } from "../../components/domain/ProviderModelSelector";
import { PROVIDERS, sortModelsDesc } from "../../config/providers";
import { api } from "../../services/api";
import type { KeysStatus, ToolInfo, ToolsAPIResponse, OllamaModel } from "../../types/api";

export function SettingsPage() {
  const [openaiKey, setOpenaiKey] = useState("");
  const [anthropicKey, setAnthropicKey] = useState("");
  const [googleKey, setGoogleKey] = useState("");
  const [ollamaUrl, setOllamaUrl] = useState("");
  const [activeProvider, setActiveProvider] = useState<string>("openai");
  const [status, setStatus] = useState<KeysStatus | null>(null);
  const [ollamaModels, setOllamaModels] = useState<OllamaModel[]>([]);
  const [ollamaHealth, setOllamaHealth] = useState<"connected" | "disconnected" | "checking">("checking");
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);
  const [dynamicModels, setDynamicModels] = useState<Record<string, { value: string; label: string }[]>>({});

  const defaultModels: Record<string, string> = {};
  for (const [key, def] of Object.entries(PROVIDERS)) {
    const sorted = sortModelsDesc(def.models);
    defaultModels[key] = sorted[0]?.id ?? "";
  }
  const [providerModels, setProviderModels] = useState<Record<string, string>>(defaultModels);
  const selectedModel = providerModels[activeProvider] || "";

  const fetchStatus = useCallback(() => {
    api.settings.getKeys()
      .then((data) => {
        setStatus(data);
        if (data.model_provider) setActiveProvider(data.model_provider);
        if (data.selected_model) {
          const provider = data.model_provider || "openai";
          setProviderModels((prev) => ({ ...prev, [provider]: data.selected_model! }));
        }
        if (data.ollama_base_url) setOllamaUrl(data.ollama_base_url);
      })
      .catch(() =>
        setStatus({
          openai_configured: false, anthropic_configured: false, google_configured: false,
          ollama_configured: false, ollama_base_url: null, model_provider: null, selected_model: null,
        }),
      );
  }, []);

  const fetchTools = useCallback(() => {
    api.settings.getTools()
      .then((data: ToolsAPIResponse) => {
        const allTools: ToolInfo[] = [];
        if (data.categories) {
          for (const [cat, catTools] of Object.entries(data.categories)) {
            for (const tool of catTools) allTools.push({ ...tool, category: cat });
          }
        }
        setTools(allTools);
      })
      .catch(() => setTools([]));
  }, []);

  const fetchModelsForProvider = useCallback((provider: string) => {
    const def = PROVIDERS[provider];
    if (!def?.dynamicModels || !def.modelsEndpoint) return;
    api.settings.getModels(provider)
      .then((data) => {
        if (data.models?.length) {
          const models = data.models.map((m) => ({ value: m.id, label: m.name }));
          setDynamicModels((prev) => ({ ...prev, [provider]: models }));
          setProviderModels((prev) => {
            const inList = models.some((m) => m.value === prev[provider]);
            return inList ? prev : { ...prev, [provider]: models[0].value };
          });
        }
      })
      .catch((err) => { if (import.meta.env.DEV) console.warn("Failed to fetch models:", err); });
  }, []);

  const fetchOllamaModels = useCallback((url?: string) => {
    api.settings.ollamaModels(url || ollamaUrl || undefined)
      .then((data) => {
        const models: OllamaModel[] = (data.models || []) as unknown as OllamaModel[];
        setOllamaModels(models);
        setOllamaHealth("connected");
        if (models.length > 0) {
          setProviderModels((prev) => {
            const inList = models.some((m) => m.name === prev.ollama);
            return inList ? prev : { ...prev, ollama: models[0].name };
          });
        }
      })
      .catch(() => { setOllamaModels([]); setOllamaHealth("disconnected"); });
  }, [ollamaUrl]);

  const testOllamaConnection = useCallback(() => {
    setOllamaHealth("checking");
    api.settings.ollamaHealth(ollamaUrl || undefined)
      .then((data) => {
        setOllamaHealth(data.status === "connected" ? "connected" : "disconnected");
        if (data.status === "connected") fetchOllamaModels(ollamaUrl);
      })
      .catch(() => setOllamaHealth("disconnected"));
  }, [ollamaUrl, fetchOllamaModels]);

  useEffect(() => {
    fetchStatus(); fetchTools();
    fetchModelsForProvider("openai"); fetchModelsForProvider("anthropic"); fetchModelsForProvider("google");
    testOllamaConnection();
  }, []);

  useEffect(() => {
    if (status?.openai_configured) fetchModelsForProvider("openai");
    if (status?.anthropic_configured) fetchModelsForProvider("anthropic");
    if (status?.google_configured) fetchModelsForProvider("google");
  }, [status?.openai_configured, status?.anthropic_configured, status?.google_configured]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true); setMessage(null);
    try {
      const body: Record<string, unknown> = {};
      if (openaiKey) body.openai_api_key = openaiKey;
      if (anthropicKey) body.anthropic_api_key = anthropicKey;
      if (googleKey) body.google_api_key = googleKey;
      if (ollamaUrl !== (status?.ollama_base_url ?? "")) body.ollama_base_url = ollamaUrl;
      const effectiveProvider = PROVIDERS[activeProvider]?.routesThrough || activeProvider;
      body.model_provider = effectiveProvider;
      if (selectedModel) body.selected_model = selectedModel;
      const data = await api.settings.saveKeys(body);
      setStatus(data); setOpenaiKey(""); setAnthropicKey(""); setGoogleKey("");
      setMessage({ text: "Settings saved successfully.", type: "success" });
      if (data.openai_configured) fetchModelsForProvider("openai");
      if (data.anthropic_configured) fetchModelsForProvider("anthropic");
      if (data.google_configured) fetchModelsForProvider("google");
      if (effectiveProvider === "ollama") fetchOllamaModels();
    } catch (err: unknown) {
      setMessage({ text: `Error: ${err instanceof Error ? err.message : "Unknown error"}`, type: "error" });
    } finally { setLoading(false); }
  };

  const handleClear = async () => {
    setLoading(true); setMessage(null);
    try {
      const data = await api.settings.saveKeys({ clear: true });
      setStatus(data); setActiveProvider("openai"); setOllamaUrl(""); setOllamaModels([]); setDynamicModels({});
      setProviderModels({ ...defaultModels });
      setMessage({ text: "All settings cleared.", type: "success" });
    } catch (err: unknown) {
      setMessage({ text: `Error: ${err instanceof Error ? err.message : "Unknown error"}`, type: "error" });
    } finally { setLoading(false); }
  };

  const availableTools = tools.filter((t) => t.available);
  const categories = [...new Set(tools.map((t) => t.category))].sort();

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 animate-fade-in">
      <PageHeader title="Settings" />

      <form onSubmit={handleSave}>
        <Card padding="lg">
          <CardHeader icon={<Zap size={18} />} title="LLM Providers" subtitle="Select your provider, then choose a model." />

          <ProviderModelSelector
            activeProvider={activeProvider}
            providerModels={providerModels}
            dynamicModels={dynamicModels}
            ollamaModels={ollamaModels}
            apiKeyInputs={{ openai: openaiKey, anthropic: anthropicKey, google: googleKey }}
            ollamaUrl={ollamaUrl}
            status={status}
            ollamaHealth={ollamaHealth}
            loading={loading}
            onProviderChange={(p) => {
              setActiveProvider(p);
              const def = PROVIDERS[p];
              if (def) {
                const dynamicList = dynamicModels[p];
                if (dynamicList?.length) setProviderModels((prev) => ({ ...prev, [p]: dynamicList[0].value }));
                else { const sorted = sortModelsDesc(def.models); if (sorted.length) setProviderModels((prev) => ({ ...prev, [p]: sorted[0].id })); }
              }
              if (p === "ollama" || p === "meta") fetchOllamaModels();
            }}
            onModelSelect={(p, m) => setProviderModels((prev) => ({ ...prev, [p]: m }))}
            onApiKeyChange={(p, v) => {
              if (p === "openai") setOpenaiKey(v);
              else if (p === "anthropic") setAnthropicKey(v);
              else if (p === "google") setGoogleKey(v);
            }}
            onOllamaUrlChange={setOllamaUrl}
            onTestOllama={testOllamaConnection}
          />

          <div className="flex gap-2 mt-4">
            <Button type="submit" loading={loading}>
              Save settings
            </Button>
            <Button variant="danger" type="button" onClick={handleClear} disabled={loading}>
              Clear all
            </Button>
          </div>

          {message && (
            <p className={`text-sm mt-3 ${message.type === "error" ? "text-red-400" : "text-emerald-400"}`}>
              {message.text}
            </p>
          )}
        </Card>
      </form>

      {/* Security Tools */}
      <Card padding="lg">
        <CardHeader
          icon={<Wrench size={18} />}
          title="Security Tools"
          subtitle={`CLI tools in the Docker container. ${availableTools.length} of ${tools.length} installed.`}
        />
        {tools.length > 0 ? (
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
            {categories.map((cat) => {
              const catTools = tools.filter((t) => t.category === cat);
              return (
                <div key={cat}>
                  <h4 className="text-xs font-medium text-rw-muted uppercase tracking-wider mb-2">
                    {cat.replace(/_/g, " ")}
                  </h4>
                  <div className="space-y-1">
                    {catTools.map((tool) => (
                      <div key={tool.name} className="flex items-center gap-2 text-xs py-0.5" title={tool.description}>
                        {tool.available ? (
                          <CheckCircle size={12} className="text-emerald-400 shrink-0" />
                        ) : (
                          <XCircle size={12} className="text-red-400/50 shrink-0" />
                        )}
                        <span className={tool.available ? "text-rw-text" : "text-rw-dim"}>
                          {tool.name.replace(/_/g, " ")}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-rw-dim/50">Loading tools...</p>
        )}
      </Card>
    </div>
  );
}

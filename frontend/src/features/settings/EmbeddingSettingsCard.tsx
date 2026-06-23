import { useCallback, useEffect, useRef, useState } from "react";
import { Database, RefreshCw, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { Card, CardHeader } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { api } from "../../services/api";
import type { EmbeddingConfig } from "../../types/api";

const inputCls =
  "w-full bg-white/[0.05] border border-white/[0.08] rounded-lg px-3 py-2 text-[13px] " +
  "text-rw-text transition-colors duration-150 hover:border-white/[0.15] " +
  "focus:border-rw-accent/50 focus:outline-none disabled:opacity-40";

export function EmbeddingSettingsCard() {
  const [cfg, setCfg] = useState<EmbeddingConfig | null>(null);
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("");
  const [device, setDevice] = useState("cpu");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const apply = useCallback((data: EmbeddingConfig) => {
    setCfg(data);
    setProvider(data.provider);
    setModel(data.model);
    setDevice(data.device || "cpu");
  }, []);

  const fetchCfg = useCallback(() => {
    api.knowledge.embeddingConfig().then(apply).catch(() => setCfg(null));
  }, [apply]);

  useEffect(() => {
    fetchCfg();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [fetchCfg]);

  // Poll while a re-index is running so the status/progress stays live.
  useEffect(() => {
    if (cfg?.status === "running" && !pollRef.current) {
      pollRef.current = setInterval(() => {
        api.knowledge.embeddingConfig().then((d) => {
          setCfg(d);
          if (d.status !== "running" && pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
        }).catch(() => {});
      }, 2000);
    }
  }, [cfg?.status]);

  const providerOpt = cfg?.providers.find((p) => p.id === provider);
  const running = cfg?.status === "running";
  const needsKey = providerOpt?.needs_key && !cfg?.openai_key_configured;

  const handleSave = async () => {
    setBusy(true); setMessage(null);
    try {
      const data = await api.knowledge.saveEmbeddingConfig({ provider, model, device });
      apply(data);
      setMessage({ text: "Embedding settings saved. Re-index to apply.", type: "success" });
    } catch (err) {
      setMessage({ text: `Error: ${err instanceof Error ? err.message : "Unknown"}`, type: "error" });
    } finally { setBusy(false); }
  };

  const handleReindex = async () => {
    setBusy(true); setMessage(null);
    try {
      // Persist the current selection first, then kick off the rebuild.
      await api.knowledge.saveEmbeddingConfig({ provider, model, device });
      const data = await api.knowledge.reindex();
      setCfg(data);
      setMessage({ text: "Re-index started — embedding the knowledge base…", type: "success" });
    } catch (err) {
      setMessage({ text: `Error: ${err instanceof Error ? err.message : "Unknown"}`, type: "error" });
    } finally { setBusy(false); }
  };

  return (
    <Card padding="lg">
      <CardHeader
        icon={<Database size={18} />}
        title="Knowledge Base Embeddings"
        subtitle="Choose how the pgvector KB is embedded — OpenAI or a local offline model. No env vars needed."
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="block text-xs text-rw-muted mb-1.5">Provider</label>
          <select
            className={inputCls + " appearance-none cursor-pointer"}
            value={provider}
            onChange={(e) => {
              const p = e.target.value;
              setProvider(p);
              const opt = cfg?.providers.find((x) => x.id === p);
              setModel(opt?.models[0]?.id ?? "");
            }}
            disabled={running || busy}
          >
            {cfg?.providers.map((p) => (
              <option key={p.id} value={p.id} className="bg-[#0d1117]">{p.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs text-rw-muted mb-1.5">
            Model <span className="text-rw-dim">(dimension auto-detected on re-index)</span>
          </label>
          <input
            className={inputCls}
            list="embed-model-options"
            value={model}
            placeholder={provider === "huggingface" ? "sentence-transformers/all-MiniLM-L6-v2" : "text-embedding-3-small"}
            onChange={(e) => setModel(e.target.value)}
            disabled={running || busy}
          />
          <datalist id="embed-model-options">
            {providerOpt?.models.map((m) => (
              <option key={m.id} value={m.id}>{m.label}</option>
            ))}
          </datalist>
        </div>

        {provider === "huggingface" && (
          <div>
            <label className="block text-xs text-rw-muted mb-1.5">Device</label>
            <select
              className={inputCls + " appearance-none cursor-pointer"}
              value={device}
              onChange={(e) => setDevice(e.target.value)}
              disabled={running || busy}
            >
              <option value="cpu" className="bg-[#0d1117]">CPU</option>
              <option value="cuda" className="bg-[#0d1117]">CUDA (GPU)</option>
            </select>
          </div>
        )}
      </div>

      {needsKey && (
        <p className="text-xs text-amber-400 mt-3">
          OpenAI embeddings need an OpenAI API key (set it in LLM Providers above).
          The HuggingFace provider runs offline with no key.
        </p>
      )}

      <div className="flex items-center gap-2 mt-4">
        <Button type="button" onClick={handleSave} disabled={busy || running}>
          Save
        </Button>
        <Button
          type="button"
          variant="secondary"
          onClick={handleReindex}
          disabled={busy || running || needsKey}
          icon={<RefreshCw size={14} />}
        >
          Re-index knowledge base
        </Button>
      </div>

      {/* Status row */}
      {cfg && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs mt-3 text-rw-muted">
          <span className="flex items-center gap-1.5">
            {running ? (
              <><Loader2 size={12} className="animate-spin text-rw-accent" /> Indexing…</>
            ) : cfg.status === "done" ? (
              <><CheckCircle size={12} className="text-emerald-400" /> Indexed</>
            ) : cfg.status === "error" ? (
              <><XCircle size={12} className="text-red-400" /> Error</>
            ) : (
              <>Idle</>
            )}
          </span>
          <span>Active: <span className="text-rw-text">{cfg.provider}</span> / {cfg.model || "default"} ({cfg.dimension}d)</span>
          <span>{cfg.chunk_count} chunks</span>
          {cfg.last_indexed_at && (
            <span>last: {new Date(cfg.last_indexed_at).toLocaleString()}</span>
          )}
        </div>
      )}

      {cfg?.status === "error" && cfg.last_error && (
        <p className="text-xs text-red-400 mt-2 font-mono break-all">{cfg.last_error}</p>
      )}
      {message && (
        <p className={`text-sm mt-3 ${message.type === "error" ? "text-red-400" : "text-emerald-400"}`}>
          {message.text}
        </p>
      )}
    </Card>
  );
}

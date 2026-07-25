import { useCallback, useEffect, useRef, useState } from "react";
import { Database, RefreshCw, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { Card, CardHeader } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Input, Select } from "../../components/ui/Input";
import { useToast } from "../../components/ui/feedback";
import { api } from "../../services/api";
import type { EmbeddingConfig } from "../../types/api";

/** Field labels here match the rest of Settings. */
const labelCls = "mb-1.5 block text-xs text-rw-muted";

export function EmbeddingSettingsCard() {
  const [cfg, setCfg] = useState<EmbeddingConfig | null>(null);
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("");
  const [device, setDevice] = useState("cpu");
  const [busy, setBusy] = useState(false);
  const toast = useToast();
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
    setBusy(true);
    try {
      const data = await api.knowledge.saveEmbeddingConfig({ provider, model, device });
      apply(data);
      toast.success("Embedding settings saved. Re-index to apply.");
    } catch (err) {
      toast.error(`Could not save embedding settings: ${err instanceof Error ? err.message : "Unknown"}`);
    } finally { setBusy(false); }
  };

  const handleReindex = async () => {
    setBusy(true);
    try {
      // Persist the current selection first, then kick off the rebuild.
      await api.knowledge.saveEmbeddingConfig({ provider, model, device });
      const data = await api.knowledge.reindex();
      setCfg(data);
      toast.info("Re-index started — embedding the knowledge base…");
    } catch (err) {
      toast.error(`Could not start the re-index: ${err instanceof Error ? err.message : "Unknown"}`);
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
          <label htmlFor="embed-provider" className={labelCls}>Provider</label>
          <Select
            id="embed-provider"
            value={provider}
            onChange={(e) => {
              const p = e.target.value;
              setProvider(p);
              const opt = cfg?.providers.find((x) => x.id === p);
              setModel(opt?.models[0]?.id ?? "");
            }}
            disabled={running || busy}
            options={(cfg?.providers ?? []).map((p) => ({ value: p.id, label: p.label }))}
          />
        </div>

        <div>
          <label htmlFor="embed-model" className={labelCls}>
            Model <span className="text-rw-dim">(dimension auto-detected on re-index)</span>
          </label>
          <Input
            id="embed-model"
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
            <label htmlFor="embed-device" className={labelCls}>Device</label>
            <Select
              id="embed-device"
              value={device}
              onChange={(e) => setDevice(e.target.value)}
              disabled={running || busy}
              options={[
                { value: "cpu", label: "CPU" },
                { value: "cuda", label: "CUDA (GPU)" },
              ]}
            />
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
        <p role="alert" className="mt-2 break-all font-mono text-xs text-red-400">
          {cfg.last_error}
        </p>
      )}
    </Card>
  );
}

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Send, ChevronDown, ChevronRight, Trash2, Crosshair, Lock, FolderOpen } from "lucide-react";
import { useHuntContext } from "../../contexts/HuntContext";
import { ThinkingStream } from "../../components/domain/ThinkingStream";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { SeverityBadge } from "../../components/ui/SeverityBadge";
import { Spinner } from "../../components/ui/Spinner";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { IconButton } from "../../components/ui/IconButton";
import { groupMessages } from "../../utils/messageGrouping";
import { filterDuplicateReportFromMessages } from "../../utils/filterReportChat";
import { api } from "../../services/api";
import type { RunDetail, RunMessage, SSHConfig } from "../../types/api";
import { HuntReportBlock } from "./HuntReportBlock";

interface ChatPanelProps {
  selectedRunId: string | null;
  onSelectRun: (runId: string | null) => void;
  onRunDeleted?: () => void;
}

export function ChatPanel({ selectedRunId, onSelectRun, onRunDeleted }: ChatPanelProps) {
  const [message, setMessage] = useState("");
  const [selectedRun, setSelectedRun] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chatReplies, setChatReplies] = useState<RunMessage[]>([]);
  const [traceExpanded, setTraceExpanded] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const [showReasoning, setShowReasoning] = useState(true);
  const [showSSH, setShowSSH] = useState(false);
  const [sshConfig, setSSHConfig] = useState<SSHConfig>({ host: "", username: "root", port: 22 });
  const threadEndRef = useRef<HTMLDivElement>(null);

  const isRunning = selectedRun?.status === "running" || selectedRun?.status === "queued";
  const stream = useHuntContext();

  const hasStreamActivity =
    stream.steps.length > 0 ||
    (stream.graphState.active_nodes?.length ?? 0) > 0 ||
    stream.activeAgent != null ||
    stream.findings.length > 0;

  // Fetch run details — clear stale hunt immediately when switching runs (avoid cache bleed).
  useEffect(() => {
    if (!selectedRunId) {
      setSelectedRun(null);
      setChatReplies([]);
      return;
    }
    let cancelled = false;
    setSelectedRun((prev) => (prev?.run_id === selectedRunId ? prev : null));
    api.runs
      .get(selectedRunId)
      .then((run) => {
        if (!cancelled) setSelectedRun(run);
      })
      .catch(() => {
        if (!cancelled) setSelectedRun(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedRunId]);

  // Refresh on stream done
  useEffect(() => {
    if (stream.done && selectedRunId) {
      api.runs.get(selectedRunId).then(setSelectedRun).catch(() => {});
    }
  }, [stream.done, selectedRunId]);

  // Polling fallback
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    if (!selectedRunId || !isRunning || stream.connected) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      return;
    }
    pollRef.current = setInterval(() => {
      api.runs.get(selectedRunId).then(setSelectedRun).catch(() => {});
    }, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [selectedRunId, isRunning, stream.connected]);

  const scrollThreadToEnd = useCallback(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  // Auto-scroll
  useEffect(() => {
    scrollThreadToEnd();
  }, [stream.steps.length, chatReplies.length, scrollThreadToEnd]);

  const sendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    const text = message.trim();
    if (!text) return;
    setLoading(true);
    setError(null);
    setChatReplies((prev) => [...prev, { role: "user", content: text }]);
    setMessage("");

    const chatBody: Record<string, unknown> = { message: text, run_id: selectedRun?.run_id };
    if (showSSH && sshConfig.host && sshConfig.username) chatBody.ssh_config = sshConfig;

    api.chat
      .send(chatBody)
      .then((data) => {
        setChatReplies((prev) => [...prev, { role: "assistant", content: data.reply }]);
        if (data.deferred && data.run_id) {
          setLoading(false);
          onSelectRun(data.run_id);
          api.runs.get(data.run_id).then((run) =>
            setSelectedRun({ ...run, messages: [...(run.messages || []), { role: "assistant", content: data.reply }] }),
          );
          stream.reset();
          return;
        }
        if (data.created_run && data.run_id) {
          setChatReplies([]);
          api.runs.get(data.run_id).then((run) => { setSelectedRun(run); onSelectRun(data.run_id ?? null); });
        }
      })
      .catch((e) => { setError(e.message); setChatReplies((prev) => prev.slice(0, -1)); })
      .finally(() => setLoading(false));
  };

  const deleteCurrentHunt = () => {
    if (!selectedRun?.run_id || deleting) return;
    if (!window.confirm("Delete this hunt? This cannot be undone.")) return;
    setDeleting(true);
    api.runs
      .delete(selectedRun.run_id)
      .then(() => { onSelectRun(null); onRunDeleted?.(); })
      .catch((e) => setError(e.message))
      .finally(() => setDeleting(false));
  };

  const messagesToShow = useMemo(() => {
    const raw = selectedRun ? selectedRun.messages : chatReplies;
    if (!selectedRun) return raw;
    return filterDuplicateReportFromMessages(raw, selectedRun.graph_state?.report_markdown);
  }, [selectedRun, chatReplies]);

  const messageGroups = groupMessages(messagesToShow);
  const toggleTrace = (key: string) =>
    setTraceExpanded((prev) => {
      const n = new Set(prev);
      if (n.has(key)) n.delete(key);
      else n.add(key);
      return n;
    });

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-rw-bg">
      {/* Context bar */}
      {selectedRun && (
        <div className="flex items-center gap-3 px-4 py-2 border-b border-rw-border bg-rw-elevated text-sm animate-fade-in">
          <Crosshair size={14} className="text-rw-accent shrink-0" />
          <span className="font-mono text-xs text-rw-text">{selectedRun.target}</span>
          {selectedRun.scope && <span className="text-xs text-rw-dim">Scope: {selectedRun.scope}</span>}
          <StatusBadge status={selectedRun.status} />
          {selectedRun.session_id && (
            <span
              className="inline-flex items-center gap-1 text-[10px] font-medium uppercase tracking-wide text-rw-accent/90 bg-rw-accent/10 border border-rw-accent/20 px-2 py-0.5 rounded"
              title={selectedRun.workspace_name && selectedRun.session_name
                ? `${selectedRun.workspace_name} · ${selectedRun.session_name}`
                : selectedRun.session_name ?? "Workspace session"}
            >
              <FolderOpen size={11} />
              Project
            </span>
          )}
          {stream.connected && (
            <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider">LIVE</span>
          )}
          <div className="ml-auto">
            <IconButton
              icon={<Trash2 size={14} />}
              label="Delete hunt"
              variant="danger"
              onClick={deleteCurrentHunt}
              disabled={deleting}
            />
          </div>
        </div>
      )}

      {/* Thread */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {error && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 text-sm rounded-lg px-3 py-2 animate-fade-in">
            {error}
          </div>
        )}

        {/* Empty state */}
        {messagesToShow.length === 0 && !selectedRun && stream.steps.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center animate-scale-in">
            <div className="w-14 h-14 rounded-2xl bg-rw-surface flex items-center justify-center mb-4">
              <Crosshair size={28} className="text-rw-accent" />
            </div>
            <h3 className="text-lg font-semibold text-rw-text mb-1">Start a hunt</h3>
            <p className="text-sm text-rw-dim mb-6 max-w-sm">
              Enter a URL or target below. AI agents will automatically run recon, scanning, fuzzing, and analysis.
            </p>
            <div className="flex flex-wrap gap-2 justify-center">
              {["https://example.com", "scan example.com", "192.168.1.0/24"].map((hint) => (
                <button
                  key={hint}
                  onClick={() => setMessage(hint)}
                  className="px-3 py-1.5 text-xs text-rw-muted bg-rw-surface border border-rw-border rounded-full hover:text-rw-accent hover:border-rw-accent/30 transition-colors"
                >
                  {hint}
                </button>
              ))}
            </div>

            {/* SSH config */}
            <div className="mt-6 w-full max-w-sm">
              <button
                onClick={() => setShowSSH(!showSSH)}
                className="flex items-center gap-2 text-xs text-rw-dim hover:text-rw-muted transition-colors mx-auto"
              >
                <Lock size={12} /> SSH Access{" "}
                {showSSH ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                {showSSH && sshConfig.host && (
                  <span className="text-[10px] text-rw-accent font-medium">Enabled</span>
                )}
              </button>
              {showSSH && (
                <div className="mt-3 space-y-2 bg-rw-elevated border border-rw-border rounded-lg p-3 animate-fade-in">
                  {(
                    [
                      { label: "Host", key: "host" as const, placeholder: "10.10.14.5", type: "text" },
                      { label: "User", key: "username" as const, placeholder: "root", type: "text" },
                      { label: "Password", key: "password" as const, placeholder: "Optional", type: "password" },
                      { label: "Key Path", key: "key_path" as const, placeholder: "/keys/id_rsa", type: "text" },
                    ] as const
                  ).map((field) => (
                    <div key={field.key} className="flex items-center gap-2">
                      <label className="text-[10px] text-rw-dim w-14 shrink-0">{field.label}</label>
                      <input
                        type={field.type}
                        placeholder={field.placeholder}
                        value={String((sshConfig as unknown as Record<string, unknown>)[field.key] || "")}
                        onChange={(e) => setSSHConfig((c) => ({ ...c, [field.key]: e.target.value || undefined }))}
                        className="flex-1 bg-rw-input border border-rw-border rounded px-2 py-1 text-xs text-rw-text placeholder-rw-dim focus:border-rw-accent/50 outline-none"
                      />
                    </div>
                  ))}
                  <div className="flex items-center gap-2">
                    <label className="text-[10px] text-rw-dim w-14 shrink-0">Port</label>
                    <input
                      type="number"
                      value={sshConfig.port || 22}
                      onChange={(e) => setSSHConfig((c) => ({ ...c, port: parseInt(e.target.value) || 22 }))}
                      className="w-20 bg-rw-input border border-rw-border rounded px-2 py-1 text-xs text-rw-text focus:border-rw-accent/50 outline-none"
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Thinking stream */}
        {stream.steps.length > 0 && (
          <ThinkingStream
            steps={stream.steps}
            activeAgent={stream.activeAgent}
            isActive={!!isRunning}
            collapsed={!showReasoning}
            onToggle={() => setShowReasoning((v) => !v)}
          />
        )}

        {/* Loading indicator */}
        {((selectedRun && isRunning) || (selectedRunId && stream.connected)) && !hasStreamActivity && (
          <Spinner size="sm" label={stream.connected ? "Initializing agents..." : "Connecting..."} />
        )}

        {/* Live findings */}
        {stream.findings.length > 0 && (
          <div className="bg-rw-elevated border border-rw-border rounded-xl p-3 animate-fade-in">
            <div className="text-xs font-medium text-rw-muted mb-2">
              Live Findings ({stream.findings.length})
            </div>
            <div className="space-y-1">
              {stream.findings.slice(-10).map((f) => (
                <div key={f.id} className="flex items-center gap-2 text-xs">
                  <SeverityBadge severity={f.severity} />
                  <span className="text-rw-text truncate">{f.title}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {selectedRunId && (
          <HuntReportBlock runId={selectedRunId} onContentLoaded={scrollThreadToEnd} />
        )}

        {/* Chat messages */}
        {messageGroups.map((group) => {
          if (group.kind === "user") {
            return (
              <div key={group.key} className="flex justify-end animate-fade-in">
                <div className="max-w-[70%] bg-rw-accent/10 border border-rw-accent/20 rounded-xl px-3 py-2 text-sm text-rw-text">
                  {group.messages[0].content}
                </div>
              </div>
            );
          }
          if (group.kind === "error") {
            const count = group.messages.length;
            return (
              <div key={group.key} className="bg-red-500/10 border border-red-500/20 text-red-400 text-xs rounded-lg px-3 py-2">
                {group.messages[0].content}
                {count > 1 ? ` (x${count})` : ""}
              </div>
            );
          }
          if (group.kind === "toolTrace") {
            const isExpanded = traceExpanded.has(group.key);
            return (
              <div key={group.key} className="border-l-2 border-rw-border-subtle pl-3">
                <button
                  onClick={() => toggleTrace(group.key)}
                  className="flex items-center gap-1 text-xs text-rw-dim hover:text-rw-muted transition-colors"
                >
                  {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                  Trace ({group.messages.length})
                </button>
                {isExpanded && (
                  <pre className="mt-1 text-xs text-rw-dim bg-rw-surface rounded p-2 overflow-x-auto max-h-40 font-mono animate-fade-in">
                    {group.messages.map((m) => m.content).join("\n\n")}
                  </pre>
                )}
              </div>
            );
          }
          if (group.kind === "summary") {
            return (
              <div key={group.key} className="bg-rw-elevated border border-rw-border rounded-xl px-4 py-3 text-sm text-rw-text whitespace-pre-wrap animate-fade-in">
                {group.messages[0].content}
              </div>
            );
          }
          return null;
        })}

        {loading && <Spinner size="sm" label="Processing..." />}
        <div ref={threadEndRef} />
      </div>

      {/* Input bar */}
      <div className="border-t border-rw-border p-3">
        <form onSubmit={sendMessage} className="flex items-center gap-2">
          <Input
            placeholder="Enter a target URL or describe what to scan..."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            disabled={loading}
          />
          <Button type="submit" disabled={loading || !message.trim()} icon={<Send size={14} />}>
            {selectedRun ? "Send" : "Hunt"}
          </Button>
        </form>
      </div>
    </div>
  );
}

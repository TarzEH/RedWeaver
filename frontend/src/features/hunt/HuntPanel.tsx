import { useCallback, useEffect, useRef, useState } from "react";
import { useHuntContext } from "../../contexts/HuntContext";
import { ThinkingStream } from "../../components/domain/ThinkingStream";
import { SeverityBadge } from "../../components/ui/SeverityBadge";
import { Spinner } from "../../components/ui/Spinner";
import { useConfirm } from "../../components/ui/feedback";
import { api } from "../../services/api";
import type { RunDetail, RunStatus } from "../../types/api";
import { HuntReportBlock } from "./HuntReportBlock";
import { HuntRunHeader } from "./HuntRunHeader";
import { NewHuntForm, type NewHuntValues } from "./NewHuntForm";

interface HuntPanelProps {
  selectedRunId: string | null;
  onSelectRun: (runId: string | null) => void;
  onRunDeleted?: () => void;
}

/** Statuses where the run is over — nothing more will stream in. */
const TERMINAL: RunStatus[] = ["completed", "failed", "cancelled"];
const isTerminal = (s: RunStatus) => TERMINAL.includes(s);

/**
 * API errors surface as the raw response body. Show the server's `detail`
 * rather than a wall of JSON.
 */
function readableError(e: unknown): string {
  const raw = e instanceof Error ? e.message : String(e);
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.detail === "string") return parsed.detail;
  } catch {
    /* not JSON — the raw text is the best we have */
  }
  return raw || "Something went wrong.";
}

/**
 * The hunt surface, in three states: a form to start one, a progress view while
 * it runs, and the report when it is done.
 *
 * There is deliberately no message thread. The endpoint behind the old chat box
 * never called a model — it regex-matched a target and answered with a template
 * string — so the "conversation" was two form fields wearing a costume.
 */
export function HuntPanel({ selectedRunId, onSelectRun, onRunDeleted }: HuntPanelProps) {
  const [selectedRun, setSelectedRun] = useState<RunDetail | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [showReasoning, setShowReasoning] = useState(true);
  const bodyEndRef = useRef<HTMLDivElement>(null);

  const stream = useHuntContext();
  const confirm = useConfirm();

  const isRunning = selectedRun?.status === "running" || selectedRun?.status === "queued";
  const hasStreamActivity =
    stream.steps.length > 0 ||
    (stream.graphState.active_nodes?.length ?? 0) > 0 ||
    stream.activeAgent != null ||
    stream.findings.length > 0;

  // Fetch run details — clear the stale run immediately when switching (avoid cache bleed).
  useEffect(() => {
    if (!selectedRunId) {
      setSelectedRun(null);
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

  // Refresh once the stream reports the run finished.
  useEffect(() => {
    if (stream.done && selectedRunId) {
      api.runs.get(selectedRunId).then(setSelectedRun).catch(() => {});
    }
  }, [stream.done, selectedRunId]);

  // Poll while running. This also refreshes cost_usd/total_tokens, which the
  // header renders live — the same poll used to fetch and discard them.
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    if (!selectedRunId || !isRunning) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    pollRef.current = setInterval(() => {
      api.runs.get(selectedRunId).then(setSelectedRun).catch(() => {});
    }, 3000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [selectedRunId, isRunning]);

  const scrollToEnd = useCallback(() => {
    bodyEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToEnd();
  }, [stream.steps.length, scrollToEnd]);

  const startHunt = (values: NewHuntValues) => {
    setStarting(true);
    setError(null);
    api.chat
      .send(values as unknown as Record<string, unknown>)
      .then((data) => {
        if (!data.run_id) throw new Error("The server created no run.");
        stream.reset();
        onSelectRun(data.run_id);
      })
      .catch((e) => setError(readableError(e)))
      .finally(() => setStarting(false));
  };

  const stopHunt = () => {
    if (!selectedRun?.run_id || stopping) return;
    setStopping(true);
    setError(null);
    // `hunts` and `runs` are the same model server-side, so the run id is the pk
    // this endpoint expects. The backend marks the run `cancelled` → "Stopped".
    api.hunts
      .stop(selectedRun.run_id)
      .then(() => api.runs.get(selectedRun.run_id))
      .then(setSelectedRun)
      .catch((e) => setError(readableError(e)))
      .finally(() => setStopping(false));
  };

  const deleteHunt = async () => {
    if (!selectedRun?.run_id || deleting) return;
    const ok = await confirm({
      title: "Delete hunt?",
      message: "This permanently deletes the hunt and cannot be undone.",
      danger: true,
      confirmLabel: "Delete",
    });
    if (!ok) return;
    setDeleting(true);
    api.runs
      .delete(selectedRun.run_id)
      .then(() => {
        onSelectRun(null);
        onRunDeleted?.();
      })
      .catch((e) => setError(readableError(e)))
      .finally(() => setDeleting(false));
  };

  /* ── State 1: no run selected → start one ── */
  if (!selectedRunId) {
    return (
      <div className="flex flex-1 flex-col overflow-hidden bg-rw-bg">
        <NewHuntForm submitting={starting} error={error} onSubmit={startHunt} />
      </div>
    );
  }

  const finished = selectedRun != null && isTerminal(selectedRun.status);

  /* ── States 2 & 3: a run is selected → progress, then report ── */
  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-rw-bg">
      {selectedRun && (
        <HuntRunHeader
          run={selectedRun}
          live={stream.connected}
          stoppable={!!isRunning}
          stopping={stopping}
          deleting={deleting}
          onStop={stopHunt}
          onDelete={deleteHunt}
        />
      )}

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {error && (
          <p
            role="alert"
            className="animate-fade-in rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-400"
          >
            {error}
          </p>
        )}

        {/* Agent reasoning — live while running, replayed from history once done. */}
        {stream.steps.length > 0 && (
          <ThinkingStream
            steps={stream.steps}
            activeAgent={stream.activeAgent}
            isActive={!!isRunning}
            collapsed={!showReasoning}
            onToggle={() => setShowReasoning((v) => !v)}
          />
        )}

        {!finished && !hasStreamActivity && (
          <Spinner
            size="sm"
            label={stream.connected ? "Initializing agents..." : "Connecting..."}
          />
        )}

        {/* Findings as they land. Once finished, the report and the findings
            panel are the authority, so this transient list steps aside. */}
        {!finished && stream.findings.length > 0 && (
          <div className="animate-fade-in rounded-xl border border-rw-border bg-rw-elevated p-3">
            <h3 className="mb-2 text-xs font-medium text-rw-muted">
              Findings so far ({stream.findings.length})
            </h3>
            <ul className="space-y-1">
              {stream.findings.slice(-10).map((f) => (
                <li key={f.id} className="flex items-center gap-2 text-xs">
                  <SeverityBadge severity={f.severity} />
                  <span className="truncate text-rw-text">{f.title}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* State 3 — the report. */}
        <HuntReportBlock runId={selectedRunId} onContentLoaded={scrollToEnd} />

        <div ref={bodyEndRef} />
      </div>
    </div>
  );
}

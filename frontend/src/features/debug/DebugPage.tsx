import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../../services/api";
import type {
  AgentStepRow,
  EventLogRow,
  ScreenshotRow,
  ToolExecutionRow,
} from "../../services/api";
import { MarkdownRenderer } from "../../components/domain/MarkdownRenderer";

type Tab = "tools" | "steps" | "screenshots" | "events" | "offsec";

/**
 * Behind-the-scenes debug view for a single run: raw tool output, agent
 * reasoning steps, screenshots, full event log, and the on-demand OffSec
 * playbook (a separate offensive-security agent grounded in the knowledge
 * base + web research over the findings).
 */
export function DebugPage() {
  const { runId } = useParams<{ runId: string }>();
  const [tab, setTab] = useState<Tab>("offsec");
  const [tools, setTools] = useState<ToolExecutionRow[]>([]);
  const [steps, setSteps] = useState<AgentStepRow[]>([]);
  const [shots, setShots] = useState<ScreenshotRow[]>([]);
  const [events, setEvents] = useState<EventLogRow[]>([]);
  const [loading, setLoading] = useState(false);

  const [offsecStatus, setOffsecStatus] = useState<string>("none");
  const [offsecMd, setOffsecMd] = useState<string>("");
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    Promise.all([
      api.debug.toolExecutions(runId),
      api.debug.agentSteps(runId),
      api.debug.screenshots(runId),
      api.debug.events(runId),
      api.runs.offsecGet(runId),
    ])
      .then(([t, s, sh, e, off]) => {
        setTools(t.results);
        setSteps(s.results);
        setShots(sh.results);
        setEvents(e.results);
        setOffsecStatus(off.status);
        setOffsecMd(off.markdown || "");
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [runId]);

  const startOffsec = useCallback(async () => {
    if (!runId) return;
    await api.runs.offsecStart(runId);
    setOffsecStatus("queued");
    if (pollRef.current) window.clearInterval(pollRef.current);
    pollRef.current = window.setInterval(async () => {
      const off = await api.runs.offsecGet(runId);
      setOffsecStatus(off.status);
      setOffsecMd(off.markdown || "");
      if (off.status === "completed" || off.status === "failed") {
        if (pollRef.current) window.clearInterval(pollRef.current);
      }
    }, 3000);
  }, [runId]);

  const busy = offsecStatus === "queued" || offsecStatus === "running";

  const tabBtn = (id: Tab, label: string, n?: number) => (
    <button
      onClick={() => setTab(id)}
      className={`px-3 py-1.5 rounded text-sm ${
        tab === id ? "bg-cyan-600 text-white" : "bg-slate-800 text-slate-300"
      }`}
    >
      {label}
      {n != null && <span className="opacity-60"> ({n})</span>}
    </button>
  );

  return (
    <div className="p-4 text-slate-200">
      <h1 className="text-xl font-semibold mb-1">Behind the scenes</h1>
      <p className="text-xs text-slate-400 mb-4">run {runId}</p>

      <div className="flex flex-wrap gap-2 mb-4">
        {tabBtn("offsec", "⚔ OffSec Playbook")}
        {tabBtn("tools", "Tool executions", tools.length)}
        {tabBtn("steps", "Agent steps", steps.length)}
        {tabBtn("screenshots", "Screenshots", shots.length)}
        {tabBtn("events", "Event log", events.length)}
      </div>

      {loading && <p className="text-slate-400">Loading…</p>}

      {tab === "offsec" && (
        <div>
          <div className="flex items-center gap-3 mb-3 flex-wrap">
            <button
              onClick={startOffsec}
              disabled={busy}
              className={`px-4 py-2 rounded font-medium text-sm ${
                busy ? "bg-slate-700 text-slate-400" : "bg-rose-600 hover:bg-rose-500 text-white"
              }`}
            >
              {busy ? "Generating…" : offsecMd ? "Regenerate OffSec playbook" : "Generate OffSec playbook"}
            </button>
            <span className="text-xs text-slate-400">
              Offensive-security agent · knowledge base + web research over the findings · status: {offsecStatus}
            </span>
          </div>
          {busy && (
            <p className="text-amber-400 text-sm animate-pulse">
              The OffSec operator is researching findings (knowledge base + web) and building the attack flow…
            </p>
          )}
          {offsecMd ? (
            <div className="bg-slate-900/60 rounded-lg p-4 border border-slate-800">
              <MarkdownRenderer content={offsecMd} variant="enhanced" />
            </div>
          ) : (
            !busy && <p className="text-slate-500 text-sm">No playbook yet — click Generate.</p>
          )}
        </div>
      )}

      {tab === "tools" &&
        tools.map((t) => (
          <details key={t.id} className="mb-2 bg-slate-900 rounded p-2">
            <summary className="cursor-pointer text-sm">
              <span className="text-cyan-400">{t.tool_name}</span> · {t.agent_name} ·{" "}
              <span className="text-slate-400">exit {t.exit_code ?? "—"} · {t.duration_ms ?? "—"}ms · {t.status}</span>
            </summary>
            <div className="mt-2 text-xs">
              <div className="text-slate-400">$ {t.command_str}</div>
              <pre className="mt-1 max-h-80 overflow-auto whitespace-pre-wrap bg-black/40 p-2 rounded">
                {t.raw_stdout || "(no stdout)"}
              </pre>
              {t.raw_stderr && (
                <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap bg-red-950/40 p-2 rounded">
                  {t.raw_stderr}
                </pre>
              )}
            </div>
          </details>
        ))}

      {tab === "steps" && (
        <table className="w-full text-xs">
          <thead className="text-slate-400 text-left">
            <tr><th>#</th><th>agent</th><th>type</th><th>summary</th><th>conf</th></tr>
          </thead>
          <tbody>
            {steps.map((s) => (
              <tr key={s.id} className="border-t border-slate-800">
                <td>{s.sequence}</td>
                <td className="text-cyan-400">{s.agent_name}</td>
                <td>{s.step_type}</td>
                <td className="max-w-xl truncate">{s.output_summary || s.reasoning_text}</td>
                <td>{s.confidence ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === "screenshots" && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {shots.map((s) => (
            <a key={s.id} href={s.image_url ?? "#"} target="_blank" rel="noreferrer"
               className="block bg-slate-900 rounded overflow-hidden">
              {s.image_url && <img src={s.image_url} alt={s.url} className="w-full" />}
              <div className="p-2 text-xs">
                <div className="truncate">{s.page_title || s.url}</div>
                <div className="text-slate-400">{s.agent_name} · {s.http_status ?? ""}</div>
              </div>
            </a>
          ))}
        </div>
      )}

      {tab === "events" && (
        <table className="w-full text-xs">
          <thead className="text-slate-400 text-left">
            <tr><th>#</th><th>type</th><th>agent</th><th>time</th></tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id} className="border-t border-slate-800">
                <td>{e.sequence}</td>
                <td className="text-cyan-400">{e.event_type}</td>
                <td>{e.agent_name}</td>
                <td className="text-slate-400">{e.timestamp}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

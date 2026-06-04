import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Swords, Terminal, Activity, Image as ImageIcon, ListTree } from "lucide-react";
import { api } from "../../services/api";
import type {
  AgentStepRow,
  EventLogRow,
  ScreenshotRow,
  ToolExecutionRow,
} from "../../services/api";
import { MarkdownRenderer } from "../../components/domain/MarkdownRenderer";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Spinner } from "../../components/ui/Spinner";
import { EmptyState } from "../../components/ui/EmptyState";
import { useToast } from "../../components/ui/feedback";
import { cn } from "../../lib/cn";

type Tab = "offsec" | "tools" | "steps" | "screenshots" | "events";

const TABS: { id: Tab; label: string; icon: typeof Terminal }[] = [
  { id: "offsec", label: "OffSec Playbook", icon: Swords },
  { id: "tools", label: "Tool executions", icon: Terminal },
  { id: "steps", label: "Agent steps", icon: Activity },
  { id: "screenshots", label: "Screenshots", icon: ImageIcon },
  { id: "events", label: "Event log", icon: ListTree },
];

function statusVariant(status: string): "success" | "danger" | "warning" | "default" {
  if (status === "success" || status === "completed") return "success";
  if (status === "error" || status === "failed" || status === "blocked") return "danger";
  if (status === "running" || status === "queued") return "warning";
  return "default";
}

/**
 * Behind-the-scenes debug view for a single run: raw tool output, agent
 * reasoning steps, screenshots, full event log, and the on-demand OffSec
 * playbook (a separate offensive-security agent grounded in the knowledge
 * base + web research over the findings).
 */
export function DebugPage() {
  const { runId } = useParams<{ runId: string }>();
  const toast = useToast();
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
      .catch(() => toast.error("Failed to load run telemetry"))
      .finally(() => setLoading(false));
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [runId]);

  const startOffsec = useCallback(async () => {
    if (!runId) return;
    try {
      await api.runs.offsecStart(runId);
    } catch {
      toast.error("Could not start the OffSec playbook");
      return;
    }
    setOffsecStatus("queued");
    toast.info("OffSec operator is researching the findings…");
    if (pollRef.current) window.clearInterval(pollRef.current);
    pollRef.current = window.setInterval(async () => {
      const off = await api.runs.offsecGet(runId);
      setOffsecStatus(off.status);
      setOffsecMd(off.markdown || "");
      if (off.status === "completed" || off.status === "failed") {
        if (pollRef.current) window.clearInterval(pollRef.current);
        if (off.status === "completed") toast.success("OffSec playbook ready");
        if (off.status === "failed") toast.error("OffSec playbook failed");
      }
    }, 3000);
  }, [runId, toast]);

  const busy = offsecStatus === "queued" || offsecStatus === "running";
  const count: Record<Tab, number | undefined> = {
    offsec: undefined,
    tools: tools.length,
    steps: steps.length,
    screenshots: shots.length,
    events: events.length,
  };

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-5">
        <h1 className="text-2xl font-semibold text-rw-text">Behind the scenes</h1>
        <p className="mt-1 font-mono text-xs text-rw-dim">run {runId}</p>
      </div>

      {/* Tabs */}
      <div className="mb-5 flex flex-wrap gap-1.5 border-b border-rw-border pb-3">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={cn(
              "inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors",
              tab === id
                ? "bg-rw-accent/15 text-rw-accent-hover"
                : "text-rw-muted hover:bg-rw-surface hover:text-rw-text",
            )}
          >
            <Icon size={14} />
            {label}
            {count[id] != null && <span className="text-rw-dim">({count[id]})</span>}
          </button>
        ))}
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-rw-muted">
          <Spinner /> <span className="text-sm">Loading telemetry…</span>
        </div>
      )}

      {/* OffSec */}
      {tab === "offsec" && (
        <div>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <Button
              variant="danger"
              onClick={startOffsec}
              loading={busy}
              icon={!busy ? <Swords size={14} /> : undefined}
            >
              {busy ? "Generating…" : offsecMd ? "Regenerate playbook" : "Generate OffSec playbook"}
            </Button>
            <span className="text-xs text-rw-dim">
              Offensive-security agent · KB + web research over the findings · status:{" "}
              <Badge variant={statusVariant(offsecStatus)}>{offsecStatus}</Badge>
            </span>
          </div>
          {offsecMd ? (
            <Card padding="lg" className="max-h-[72vh] overflow-y-auto">
              <MarkdownRenderer content={offsecMd} variant="enhanced" className="offsecPlaybook" />
            </Card>
          ) : (
            !busy && (
              <EmptyState
                icon={<Swords size={32} />}
                title="No playbook yet"
                description="Generate a per-finding attack playbook with commands and MITRE ATT&CK techniques, grounded in the knowledge base."
              />
            )
          )}
        </div>
      )}

      {/* Tool executions */}
      {tab === "tools" && (
        <div className="flex flex-col gap-2">
          {tools.length === 0 && !loading ? (
            <EmptyState icon={<Terminal size={32} />} title="No tool executions" />
          ) : (
            tools.map((t) => (
              <details key={t.id} className="group rounded-lg border border-rw-border bg-rw-elevated">
                <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-2.5 text-sm">
                  <span className="font-mono font-medium text-rw-accent-hover">{t.tool_name}</span>
                  <span className="text-rw-dim">·</span>
                  <span className="text-rw-muted">{t.agent_name}</span>
                  <span className="ml-auto flex items-center gap-2 text-xs text-rw-dim">
                    <span className="font-mono">exit {t.exit_code ?? "—"}</span>
                    <span className="font-mono">{t.duration_ms ?? "—"}ms</span>
                    <Badge variant={statusVariant(t.status)}>{t.status}</Badge>
                  </span>
                </summary>
                <div className="border-t border-rw-border px-4 py-3 text-xs">
                  <div className="font-mono text-rw-dim">$ {t.command_str}</div>
                  <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded-md bg-rw-bg p-3 font-mono text-rw-muted">
                    {t.raw_stdout || "(no stdout)"}
                  </pre>
                  {t.raw_stderr && (
                    <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-md border border-rw-danger/20 bg-rw-danger/5 p-3 font-mono text-rw-danger">
                      {t.raw_stderr}
                    </pre>
                  )}
                </div>
              </details>
            ))
          )}
        </div>
      )}

      {/* Agent steps */}
      {tab === "steps" && (
        <Card padding="none" className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-rw-surface/50 text-left text-xs uppercase tracking-wide text-rw-dim">
              <tr>
                <th className="px-4 py-2.5">#</th>
                <th className="px-4 py-2.5">Agent</th>
                <th className="px-4 py-2.5">Type</th>
                <th className="px-4 py-2.5">Summary</th>
                <th className="px-4 py-2.5">Conf.</th>
              </tr>
            </thead>
            <tbody>
              {steps.map((s) => (
                <tr key={s.id} className="border-t border-rw-border/60">
                  <td className="px-4 py-2 font-mono text-rw-dim">{s.sequence}</td>
                  <td className="px-4 py-2 text-rw-accent-hover">{s.agent_name}</td>
                  <td className="px-4 py-2 text-rw-muted">{s.step_type}</td>
                  <td className="max-w-xl truncate px-4 py-2 text-rw-text">
                    {s.output_summary || s.reasoning_text}
                  </td>
                  <td className="px-4 py-2 font-mono text-rw-muted">{s.confidence ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {/* Screenshots */}
      {tab === "screenshots" && (
        shots.length === 0 && !loading ? (
          <EmptyState icon={<ImageIcon size={32} />} title="No screenshots captured" />
        ) : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            {shots.map((s) => (
              <a
                key={s.id}
                href={s.image_url ?? "#"}
                target="_blank"
                rel="noreferrer"
                className="block overflow-hidden rounded-lg border border-rw-border bg-rw-elevated transition-colors hover:border-rw-accent/40"
              >
                {s.image_url && <img src={s.image_url} alt={s.url} className="w-full" />}
                <div className="p-2.5 text-xs">
                  <div className="truncate text-rw-text">{s.page_title || s.url}</div>
                  <div className="mt-0.5 text-rw-dim">
                    {s.agent_name} {s.http_status ? `· ${s.http_status}` : ""}
                  </div>
                </div>
              </a>
            ))}
          </div>
        )
      )}

      {/* Event log */}
      {tab === "events" && (
        <Card padding="none" className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-rw-surface/50 text-left text-xs uppercase tracking-wide text-rw-dim">
              <tr>
                <th className="px-4 py-2.5">#</th>
                <th className="px-4 py-2.5">Type</th>
                <th className="px-4 py-2.5">Agent</th>
                <th className="px-4 py-2.5">Time</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id} className="border-t border-rw-border/60">
                  <td className="px-4 py-2 font-mono text-rw-dim">{e.sequence}</td>
                  <td className="px-4 py-2 font-mono text-rw-accent-hover">{e.event_type}</td>
                  <td className="px-4 py-2 text-rw-muted">{e.agent_name}</td>
                  <td className="px-4 py-2 text-rw-dim">{e.timestamp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

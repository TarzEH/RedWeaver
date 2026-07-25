import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Swords,
  Terminal,
  Activity,
  Image as ImageIcon,
  ListTree,
  Crosshair,
  ChevronDown,
} from "lucide-react";
import { api } from "../../services/api";
import { getToken } from "../../services/http";
import type {
  AgentStepRow,
  EventLogRow,
  Paginated,
  ScreenshotRow,
  ToolExecutionRow,
} from "../../services/api";
import { MarkdownRenderer } from "../../components/domain/MarkdownRenderer";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Skeleton } from "../../components/ui/Skeleton";
import { EmptyState } from "../../components/ui/EmptyState";
import { Table, THead, TBody, TH, TR, TD } from "../../components/ui/Table";
import { useToast } from "../../components/ui/feedback";
import { cn } from "../../lib/cn";

type Tab = "attack" | "tools" | "steps" | "screenshots" | "events";

const TABS: { id: Tab; label: string; icon: typeof Terminal }[] = [
  { id: "attack", label: "Attack Playbook", icon: Swords },
  { id: "tools", label: "Tool executions", icon: Terminal },
  { id: "steps", label: "Agent steps", icon: Activity },
  { id: "screenshots", label: "Screenshots", icon: ImageIcon },
  { id: "events", label: "Event log", icon: ListTree },
];

/**
 * One page of telemetry is 50 rows by default and a long hunt emits hundreds
 * of events. Ask for a page big enough that most runs arrive whole, and keep
 * the `next` link so the rest is one click away rather than silently dropped.
 */
const TELEMETRY_PAGE_SIZE = 200;

/** A paginated telemetry list: rows loaded so far + the server's total. */
interface Feed<T> {
  rows: T[];
  /** Total rows on the server (not the number loaded). */
  count: number;
  /** DRF link to the next page, or null when everything is loaded. */
  next: string | null;
}

const emptyFeed = <T,>(): Feed<T> => ({ rows: [], count: 0, next: null });
const toFeed = <T,>(p: Paginated<T>): Feed<T> => ({
  rows: p.results,
  count: p.count ?? p.results.length,
  next: p.next,
});

function statusVariant(status: string): "success" | "danger" | "warning" | "default" {
  if (status === "success" || status === "completed") return "success";
  if (status === "error" || status === "failed" || status === "blocked") return "danger";
  if (status === "running" || status === "queued") return "warning";
  return "default";
}

/**
 * "Showing N of M" + a Load more control. An audit view that quietly drops
 * rows is worse than no audit view, so the shortfall is always stated.
 */
function FeedFooter<T>({
  feed,
  noun,
  loading,
  onLoadMore,
}: {
  feed: Feed<T>;
  noun: string;
  loading: boolean;
  onLoadMore: () => void;
}) {
  const complete = feed.rows.length >= feed.count && !feed.next;
  return (
    <div className="flex items-center justify-between gap-3 border-t border-rw-border px-4 py-2.5">
      <p className="text-xs text-rw-dim">
        Showing{" "}
        <span className="font-mono tabular-nums text-rw-muted">{feed.rows.length}</span>
        {" of "}
        <span className="font-mono tabular-nums text-rw-muted">{feed.count}</span> {noun}
        {complete ? "" : " — more on the server"}
      </p>
      {!complete && (
        <Button size="sm" variant="secondary" loading={loading} onClick={onLoadMore}>
          Load more
        </Button>
      )}
    </div>
  );
}

function TableSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <Card padding="sm" className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </Card>
  );
}

/**
 * Behind-the-scenes debug view for a single run: raw tool output, agent
 * reasoning steps, screenshots, full event log, and the on-demand Attack
 * playbook (a separate red-team agent grounded in the knowledge
 * base + web research over the findings).
 */
export function DebugPage() {
  const { runId } = useParams<{ runId: string }>();
  const toast = useToast();
  const [tab, setTab] = useState<Tab>("attack");
  const [tools, setTools] = useState<Feed<ToolExecutionRow>>(emptyFeed);
  const [steps, setSteps] = useState<Feed<AgentStepRow>>(emptyFeed);
  const [shots, setShots] = useState<Feed<ScreenshotRow>>(emptyFeed);
  const [events, setEvents] = useState<Feed<EventLogRow>>(emptyFeed);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState<Tab | null>(null);

  const [attackStatus, setAttackStatus] = useState<string>("none");
  const [attackMd, setAttackMd] = useState<string>("");
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    Promise.all([
      api.debug.toolExecutions(runId, TELEMETRY_PAGE_SIZE),
      api.debug.agentSteps(runId, TELEMETRY_PAGE_SIZE),
      api.debug.screenshots(runId, TELEMETRY_PAGE_SIZE),
      api.debug.events(runId, undefined, TELEMETRY_PAGE_SIZE),
      api.runs.attackGet(runId),
    ])
      .then(([t, s, sh, e, off]) => {
        setTools(toFeed(t));
        setSteps(toFeed(s));
        setShots(toFeed(sh));
        setEvents(toFeed(e));
        setAttackStatus(off.status);
        setAttackMd(off.markdown || "");
      })
      .catch(() => toast.error("Failed to load run telemetry"))
      .finally(() => setLoading(false));
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [runId]);

  /** Append the next page of a feed, keeping the server's total intact. */
  const loadMore = useCallback(
    async <T,>(
      which: Tab,
      feed: Feed<T>,
      set: React.Dispatch<React.SetStateAction<Feed<T>>>,
    ) => {
      if (!feed.next || loadingMore) return;
      setLoadingMore(which);
      try {
        const page = await api.debug.page<T>(feed.next);
        set((prev) => ({
          rows: [...prev.rows, ...page.results],
          count: page.count ?? prev.count,
          next: page.next,
        }));
      } catch {
        toast.error("Could not load the next page");
      } finally {
        setLoadingMore(null);
      }
    },
    [loadingMore, toast],
  );

  const startAttack = useCallback(async () => {
    if (!runId) return;
    try {
      await api.runs.attackStart(runId);
    } catch {
      toast.error("Could not start the Attack playbook");
      return;
    }
    setAttackStatus("queued");
    toast.info("Attack operator is researching the findings…");
    if (pollRef.current) window.clearInterval(pollRef.current);
    pollRef.current = window.setInterval(async () => {
      const off = await api.runs.attackGet(runId);
      setAttackStatus(off.status);
      setAttackMd(off.markdown || "");
      if (off.status === "completed" || off.status === "failed") {
        if (pollRef.current) window.clearInterval(pollRef.current);
        if (off.status === "completed") toast.success("Attack playbook ready");
        if (off.status === "failed") toast.error("Attack playbook failed");
      }
    }, 3000);
  }, [runId, toast]);

  const downloadAttackLayer = async () => {
    if (!runId) return;
    const token = getToken();
    const res = await fetch(`/api/runs/${runId}/attack-navigator`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      toast.error("Could not export the ATT&CK layer");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `redweaver-${runId.slice(0, 8)}-attack-layer.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("ATT&CK Navigator layer downloaded");
  };

  const busy = attackStatus === "queued" || attackStatus === "running";
  // Tab counts state the server's total, not how many rows happen to be loaded.
  const count: Record<Tab, number | undefined> = {
    attack: undefined,
    tools: tools.count,
    steps: steps.count,
    screenshots: shots.count,
    events: events.count,
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-6xl p-6">
        <PageHeader title="Behind the scenes" subtitle={`run ${runId}`} />

        {/* Tabs */}
        <div
          role="tablist"
          aria-label="Run telemetry"
          className="mb-5 flex flex-wrap gap-1.5 border-b border-rw-border pb-3"
        >
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              role="tab"
              aria-selected={tab === id}
              onClick={() => setTab(id)}
              className={cn(
                "inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors",
                tab === id
                  ? "bg-rw-accent/15 font-medium text-rw-accent-hover"
                  : "text-rw-muted hover:bg-rw-surface hover:text-rw-text",
              )}
            >
              <Icon size={14} aria-hidden />
              {label}
              {count[id] != null && (
                <span className="font-mono tabular-nums text-rw-dim">({count[id]})</span>
              )}
            </button>
          ))}
        </div>

        {/* Attack */}
        {tab === "attack" && (
          <div>
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <Button
                variant="danger"
                onClick={startAttack}
                loading={busy}
                icon={!busy ? <Swords size={14} /> : undefined}
              >
                {busy ? "Generating…" : attackMd ? "Regenerate playbook" : "Generate Attack playbook"}
              </Button>
              <Button variant="secondary" onClick={downloadAttackLayer} icon={<Crosshair size={14} />}>
                ATT&CK layer
              </Button>
              <span className="flex items-center gap-1.5 text-xs text-rw-dim">
                Red-team agent · KB + web research over the findings · status:
                <Badge variant={statusVariant(attackStatus)}>{attackStatus}</Badge>
              </span>
            </div>
            {attackMd ? (
              <Card padding="lg" className="max-h-[72vh] overflow-y-auto">
                <MarkdownRenderer content={attackMd} variant="enhanced" className="attackPlaybook" />
              </Card>
            ) : (
              !busy && (
                <Card>
                  <EmptyState
                    icon={<Swords size={32} />}
                    title="No playbook yet"
                    description="Generate a per-finding attack playbook with commands and MITRE ATT&CK techniques, grounded in the knowledge base."
                  />
                </Card>
              )
            )}
          </div>
        )}

        {/* Tool executions */}
        {tab === "tools" &&
          (loading ? (
            <TableSkeleton />
          ) : tools.rows.length === 0 ? (
            <Card>
              <EmptyState
                icon={<Terminal size={32} />}
                title="No tool executions"
                description="This run did not record any CLI tool invocations."
              />
            </Card>
          ) : (
            <>
              <div className="flex flex-col gap-2">
                {tools.rows.map((t) => (
                  <details key={t.id} className="group rounded-lg border border-rw-border bg-rw-elevated">
                    <summary className="flex cursor-pointer list-none items-center gap-2 rounded-lg px-4 py-2.5 text-sm">
                      <ChevronDown
                        size={13}
                        aria-hidden
                        className="shrink-0 -rotate-90 text-rw-dim transition-transform group-open:rotate-0"
                      />
                      <span className="font-mono font-medium text-rw-accent-hover">{t.tool_name}</span>
                      <span className="text-rw-dim">·</span>
                      <span className="text-rw-muted">{t.agent_name}</span>
                      <span className="ml-auto flex items-center gap-2 text-xs text-rw-dim">
                        <span className="font-mono tabular-nums">exit {t.exit_code ?? "—"}</span>
                        <span className="font-mono tabular-nums">{t.duration_ms ?? "—"}ms</span>
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
                ))}
              </div>
              <Card padding="none" className="mt-2 overflow-hidden">
                <FeedFooter
                  feed={tools}
                  noun="tool executions"
                  loading={loadingMore === "tools"}
                  onLoadMore={() => loadMore("tools", tools, setTools)}
                />
              </Card>
            </>
          ))}

        {/* Agent steps */}
        {tab === "steps" &&
          (loading ? (
            <TableSkeleton />
          ) : steps.rows.length === 0 ? (
            <Card>
              <EmptyState
                icon={<Activity size={32} />}
                title="No agent steps recorded"
                description="Reasoning steps appear here once the agents start working on a run."
              />
            </Card>
          ) : (
            <Card padding="none" className="overflow-hidden">
              <Table>
                <THead>
                  <tr>
                    <TH className="w-12">#</TH>
                    <TH>Agent</TH>
                    <TH>Type</TH>
                    <TH>Summary</TH>
                    <TH className="text-right">Conf.</TH>
                  </tr>
                </THead>
                <TBody>
                  {steps.rows.map((s) => (
                    <TR key={s.id}>
                      <TD className="font-mono tabular-nums text-rw-dim">{s.sequence}</TD>
                      <TD className="text-rw-accent-hover">{s.agent_name}</TD>
                      <TD className="text-rw-muted">{s.step_type}</TD>
                      <TD className="max-w-xl truncate text-rw-text">
                        {s.output_summary || s.reasoning_text}
                      </TD>
                      <TD className="text-right font-mono tabular-nums text-rw-muted">
                        {s.confidence ?? "—"}
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
              <FeedFooter
                feed={steps}
                noun="agent steps"
                loading={loadingMore === "steps"}
                onLoadMore={() => loadMore("steps", steps, setSteps)}
              />
            </Card>
          ))}

        {/* Screenshots */}
        {tab === "screenshots" &&
          (loading ? (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-40 w-full rounded-lg" />
              ))}
            </div>
          ) : shots.rows.length === 0 ? (
            <Card>
              <EmptyState
                icon={<ImageIcon size={32} />}
                title="No screenshots captured"
                description="Browser-driving agents attach page captures here when they run."
              />
            </Card>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                {shots.rows.map((s) => (
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
              <Card padding="none" className="mt-2 overflow-hidden">
                <FeedFooter
                  feed={shots}
                  noun="screenshots"
                  loading={loadingMore === "screenshots"}
                  onLoadMore={() => loadMore("screenshots", shots, setShots)}
                />
              </Card>
            </>
          ))}

        {/* Event log */}
        {tab === "events" &&
          (loading ? (
            <TableSkeleton rows={12} />
          ) : events.rows.length === 0 ? (
            <Card>
              <EmptyState
                icon={<ListTree size={32} />}
                title="No events logged"
                description="Every agent hand-off and tool call for this run would appear here."
              />
            </Card>
          ) : (
            <Card padding="none" className="overflow-hidden">
              <Table>
                <THead>
                  <tr>
                    <TH className="w-12">#</TH>
                    <TH>Type</TH>
                    <TH>Agent</TH>
                    <TH>Time</TH>
                  </tr>
                </THead>
                <TBody>
                  {events.rows.map((e) => (
                    <TR key={e.id}>
                      <TD className="font-mono tabular-nums text-rw-dim">{e.sequence}</TD>
                      <TD className="font-mono text-rw-accent-hover">{e.event_type}</TD>
                      <TD className="text-rw-muted">{e.agent_name}</TD>
                      <TD className="tabular-nums text-rw-dim">{e.timestamp}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
              <FeedFooter
                feed={events}
                noun="events"
                loading={loadingMore === "events"}
                onLoadMore={() => loadMore("events", events, setEvents)}
              />
            </Card>
          ))}
      </div>
    </div>
  );
}

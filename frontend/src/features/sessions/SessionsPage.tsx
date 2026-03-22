import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  FolderOpen, Plus, Trash2, Globe, Server, Wifi, Code, Target,
  Layers, ChevronRight, RefreshCw, ArrowLeft, Crosshair, ExternalLink,
} from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Badge } from "../../components/ui/Badge";
import { EmptyState } from "../../components/ui/EmptyState";
import { IconButton } from "../../components/ui/IconButton";
import { Spinner } from "../../components/ui/Spinner";
import { PageHeader } from "../../components/layout/PageHeader";
import { api } from "../../services/api";
import type { WorkspaceResponse, SessionResponse, TargetResponse, HuntResponse } from "../../services/api";

/* ── Target type config ── */

const TARGET_ICONS: Record<string, typeof Globe> = {
  webapp: Globe, network: Wifi, host: Server, api: Code,
};
const TARGET_STYLES: Record<string, string> = {
  webapp: "bg-blue-500/15 text-blue-400",
  network: "bg-purple-500/15 text-purple-400",
  host: "bg-orange-500/15 text-orange-400",
  api: "bg-sky-500/15 text-sky-400",
  identity: "bg-pink-500/15 text-pink-400",
};

/* ── Inline Create Forms ── */

function CreateWorkspaceForm({ onDone }: { onDone: (created?: boolean) => void }) {
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try { await api.workspaces.create({ name: name.trim(), description: desc.trim() }); onDone(true); }
    catch { /* ignore */ } finally { setSaving(false); }
  };

  return (
    <Card className="animate-fade-in">
      <form onSubmit={submit} className="space-y-3">
        <h4 className="text-xs font-semibold text-rw-muted uppercase">New workspace</h4>
        <Input placeholder="Workspace name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        <Input placeholder="Description (optional)" value={desc} onChange={(e) => setDesc(e.target.value)} />
        <div className="flex gap-2">
          <Button type="submit" size="sm" loading={saving} disabled={!name.trim()}>Create</Button>
          <Button type="button" variant="ghost" size="sm" onClick={() => onDone()}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}

function CreateSessionForm({ workspaceId, onDone }: { workspaceId: string; onDone: (created?: boolean) => void }) {
  const [name, setName] = useState("");
  const [tags, setTags] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      await api.sessions.create({
        name: name.trim(),
        workspace_id: workspaceId,
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
      });
      onDone(true);
    } catch { /* ignore */ } finally { setSaving(false); }
  };

  return (
    <Card className="animate-fade-in">
      <form onSubmit={submit} className="space-y-3">
        <h4 className="text-xs font-semibold text-rw-muted uppercase">New session</h4>
        <Input placeholder="Session name (e.g. Q4 Pentest)" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        <Input placeholder="Tags — comma separated (optional)" value={tags} onChange={(e) => setTags(e.target.value)} />
        <div className="flex gap-2">
          <Button type="submit" size="sm" loading={saving} disabled={!name.trim()}>Create</Button>
          <Button type="button" variant="ghost" size="sm" onClick={() => onDone()}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}

function CreateTargetForm({ sessionId, onDone }: { sessionId: string; onDone: (created?: boolean) => void }) {
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [targetType, setTargetType] = useState("webapp");
  const [saving, setSaving] = useState(false);

  const addressLabel: Record<string, string> = {
    webapp: "URL (https://example.com)",
    api: "Base URL (https://api.example.com)",
    network: "CIDR range (10.10.10.0/24)",
    host: "IP address (10.10.14.5)",
    identity: "Domain (example.com)",
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !address.trim()) return;
    setSaving(true);

    // Map address to the correct field based on target type
    const body: Record<string, unknown> = {
      name: name.trim(),
      target_type: targetType,
      session_id: sessionId,
    };
    switch (targetType) {
      case "webapp": body.url = address.trim(); break;
      case "api": body.base_url = address.trim(); break;
      case "network": body.cidr_ranges = [address.trim()]; break;
      case "host": body.ip = address.trim(); break;
      case "identity": body.domain = address.trim(); break;
    }

    try { await api.targets.create(body as Parameters<typeof api.targets.create>[0]); onDone(true); }
    catch { /* ignore */ } finally { setSaving(false); }
  };

  return (
    <Card className="animate-fade-in">
      <form onSubmit={submit} className="space-y-3">
        <h4 className="text-xs font-semibold text-rw-muted uppercase">New target</h4>
        <Input placeholder="Target name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        <Input placeholder={addressLabel[targetType] || "Address"} value={address} onChange={(e) => setAddress(e.target.value)} />
        <div className="flex gap-1.5 flex-wrap">
          {(["webapp", "api", "network", "host", "identity"] as const).map((t) => {
            const Icon = TARGET_ICONS[t] || Globe;
            return (
              <button
                key={t}
                type="button"
                onClick={() => setTargetType(t)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border ${
                  targetType === t
                    ? `${TARGET_STYLES[t]} border-current`
                    : "bg-rw-surface text-rw-dim border-rw-border hover:text-rw-muted"
                }`}
              >
                <Icon size={12} /> {t}
              </button>
            );
          })}
        </div>
        <div className="flex gap-2">
          <Button type="submit" size="sm" loading={saving} disabled={!name.trim() || !address.trim()}>Add target</Button>
          <Button type="button" variant="ghost" size="sm" onClick={() => onDone()}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}

/* ── Session Detail View (targets + hunts) ── */

function SessionDetail({
  session,
  onBack,
  onRefresh,
}: {
  session: SessionResponse;
  onBack: () => void;
  onRefresh: () => void;
}) {
  const [targets, setTargets] = useState<TargetResponse[]>([]);
  const [hunts, setHunts] = useState<HuntResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateTarget, setShowCreateTarget] = useState(false);
  const [launching, setLaunching] = useState(false);

  const fetchTargets = () => {
    api.targets.list(session.id).then(setTargets).catch(() => setTargets([]));
  };
  const fetchHunts = () => {
    api.hunts.list(session.id).then(setHunts).catch(() => setHunts([]));
  };
  const fetchAll = () => {
    setLoading(true);
    Promise.all([
      api.targets.list(session.id).catch(() => []),
      api.hunts.list(session.id).catch(() => []),
    ]).then(([t, h]) => {
      setTargets(t); setHunts(h);
    }).finally(() => setLoading(false));
  };

  useEffect(() => { fetchAll(); }, [session.id]);

  const deleteTarget = async (id: string) => {
    if (!confirm("Delete this target?")) return;
    try { await api.targets.delete(id); fetchTargets(); onRefresh(); } catch { /* ignore */ }
  };

  const navigate = useNavigate();

  const launchHunt = async () => {
    if (targets.length === 0) return;
    setLaunching(true);
    try {
      const hunt = await api.hunts.create({
        session_id: session.id,
        target_ids: targets.map((t) => t.id),
        objective: "comprehensive",
      });
      // Start the hunt — this creates a Run and triggers execution
      const started = await api.hunts.start(hunt.id) as HuntResponse & { run_id?: string };
      fetchHunts();
      onRefresh();
      // Navigate to the hunt flow page if we got a run_id
      if (started.run_id) {
        navigate(`/hunt/${started.run_id}`);
      }
    } catch { /* ignore */ }
    finally { setLaunching(false); }
  };

  const deleteHunt = async (id: string) => {
    if (!confirm("Delete this hunt?")) return;
    try { await api.hunts.delete(id); fetchHunts(); onRefresh(); } catch { /* ignore */ }
  };

  const STATUS_VARIANT: Record<string, "success" | "accent" | "danger" | "warning" | "default"> = {
    completed: "success", running: "accent", failed: "danger", queued: "warning",
    paused: "default", cancelled: "default",
  };

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Button variant="ghost" size="sm" icon={<ArrowLeft size={14} />} onClick={onBack}>
          Back
        </Button>
        <div className="flex-1">
          <h2 className="text-lg font-semibold text-rw-text flex items-center gap-2">
            <FolderOpen size={18} className="text-rw-accent" />
            {session.name}
          </h2>
          <div className="flex items-center gap-3 mt-0.5">
            <Badge variant={session.status === "active" ? "success" : "default"} dot>
              {session.status}
            </Badge>
            <span className="text-xs text-rw-dim">{targets.length} targets · {hunts.length} hunts</span>
            {session.tags.length > 0 && (
              <div className="flex gap-1">
                {session.tags.map((t) => (
                  <span key={t} className="text-[10px] bg-rw-surface text-rw-dim px-1.5 py-0.5 rounded">{t}</span>
                ))}
              </div>
            )}
          </div>
        </div>
        <Button
          size="sm"
          icon={<Crosshair size={14} />}
          loading={launching}
          disabled={targets.length === 0}
          onClick={launchHunt}
        >
          Launch Hunt
        </Button>
        <Button variant="ghost" size="sm" icon={<RefreshCw size={14} />} onClick={fetchAll}>
          Refresh
        </Button>
      </div>

      {loading ? (
        <Spinner label="Loading..." />
      ) : (
        <>
          {/* ── Targets ── */}
          {showCreateTarget && (
            <div className="mb-4">
              <CreateTargetForm
                sessionId={session.id}
                onDone={(created) => { setShowCreateTarget(false); if (created) { fetchTargets(); onRefresh(); } }}
              />
            </div>
          )}

          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-rw-muted uppercase tracking-wider flex items-center gap-2">
              <Target size={14} /> Targets
            </h3>
            <Button variant="ghost" size="sm" icon={<Plus size={13} />} onClick={() => setShowCreateTarget(true)}>
              Add target
            </Button>
          </div>

          {targets.length === 0 ? (
            <Card className="mb-6">
              <EmptyState
                icon={<Target size={28} />}
                title="No targets in this session"
                description="Add a target — URL, IP, or network range — to start hunting."
                compact
                action={
                  !showCreateTarget ? (
                    <Button size="sm" variant="secondary" icon={<Plus size={13} />} onClick={() => setShowCreateTarget(true)}>
                      Add target
                    </Button>
                  ) : undefined
                }
              />
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
              {targets.map((t) => {
                const TypeIcon = TARGET_ICONS[t.target_type] || Globe;
                return (
                  <Card key={t.id} className="group hover:border-rw-accent/20 transition-colors">
                    <div className="flex items-center gap-3">
                      <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${TARGET_STYLES[t.target_type] || "bg-slate-500/15 text-slate-400"}`}>
                        <TypeIcon size={16} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-rw-text">{t.name}</div>
                        <div className="text-xs text-rw-dim font-mono mt-0.5 truncate">{t.address}</div>
                      </div>
                      <Badge variant="default">{t.target_type}</Badge>
                      <IconButton
                        icon={<Trash2 size={12} />}
                        label="Delete target"
                        variant="danger"
                        size="sm"
                        className="opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => deleteTarget(t.id)}
                      />
                    </div>
                  </Card>
                );
              })}
            </div>
          )}

          {/* ── Hunts ── */}
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-rw-muted uppercase tracking-wider flex items-center gap-2">
              <Crosshair size={14} /> Hunts
            </h3>
          </div>

          {hunts.length === 0 ? (
            <Card>
              <EmptyState
                icon={<Crosshair size={28} />}
                title="No hunts yet"
                description={targets.length > 0
                  ? "Click 'Launch Hunt' to start scanning all targets in this session."
                  : "Add targets first, then launch a hunt."
                }
                compact
                action={
                  targets.length > 0 ? (
                    <Button size="sm" icon={<Crosshair size={13} />} loading={launching} onClick={launchHunt}>
                      Launch Hunt
                    </Button>
                  ) : undefined
                }
              />
            </Card>
          ) : (
            <div className="space-y-2">
              {hunts.map((h) => {
                // Try to get run_id from graph_state
                const runId = (h as HuntResponse & { graph_state?: { run_id?: string } }).graph_state?.run_id;
                return (
                  <Card key={h.id} className="group hover:border-rw-accent/20 transition-colors" padding="md">
                    <div className="flex items-center gap-4">
                      <Crosshair size={16} className="text-rw-accent shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-rw-text">
                          {h.target || `Hunt ${h.id.slice(0, 8)}`}
                        </div>
                        <div className="text-xs text-rw-dim mt-0.5">
                          {h.objective} · {h.target_ids.length} target{h.target_ids.length !== 1 ? "s" : ""}
                          {h.finding_count > 0 && <> · <span className="text-rw-accent">{h.finding_count} findings</span></>}
                        </div>
                      </div>
                      <Badge variant={STATUS_VARIANT[h.status] || "default"} dot pulseDot={h.status === "running"}>
                        {h.status}
                      </Badge>
                      {runId && (
                        <IconButton
                          icon={<ExternalLink size={12} />}
                          label="View hunt flow"
                          onClick={() => navigate(`/hunt/${runId}`)}
                        />
                      )}
                      <IconButton
                        icon={<Trash2 size={12} />}
                        label="Delete hunt"
                        variant="danger"
                        size="sm"
                        className="opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => deleteHunt(h.id)}
                      />
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ── Main Sessions Page ── */

export function SessionsPage() {
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceResponse | null>(null);
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [activeSession, setActiveSession] = useState<SessionResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const [showCreateWorkspace, setShowCreateWorkspace] = useState(false);
  const [showCreateSession, setShowCreateSession] = useState(false);

  const fetchWorkspaces = () => {
    api.workspaces.list().then(setWorkspaces).catch(() => setWorkspaces([])).finally(() => setLoading(false));
  };

  const fetchSessions = (wsId: string) => {
    api.sessions.list(wsId).then(setSessions).catch(() => setSessions([]));
  };

  useEffect(() => { fetchWorkspaces(); }, []);

  // Auto-select first workspace
  useEffect(() => {
    if (workspaces.length > 0 && !activeWorkspace) {
      selectWorkspace(workspaces[0]);
    }
  }, [workspaces]);

  const selectWorkspace = (ws: WorkspaceResponse) => {
    setActiveWorkspace(ws);
    setActiveSession(null);
    fetchSessions(ws.id);
  };

  const deleteWorkspace = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Delete this workspace and all its sessions?")) return;
    try {
      await api.workspaces.delete(id);
      if (activeWorkspace?.id === id) { setActiveWorkspace(null); setSessions([]); }
      fetchWorkspaces();
    } catch { /* ignore */ }
  };

  const deleteSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Delete this session?")) return;
    try {
      await api.sessions.delete(id);
      if (activeSession?.id === id) setActiveSession(null);
      if (activeWorkspace) fetchSessions(activeWorkspace.id);
    } catch { /* ignore */ }
  };

  // If viewing a session's targets, show the detail view
  if (activeSession) {
    return (
      <div className="flex-1 overflow-y-auto p-6">
        <SessionDetail
          session={activeSession}
          onBack={() => setActiveSession(null)}
          onRefresh={() => { if (activeWorkspace) fetchSessions(activeWorkspace.id); }}
        />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 animate-fade-in">
      <PageHeader
        title="Sessions & Targets"
        subtitle={`${workspaces.length} workspace${workspaces.length !== 1 ? "s" : ""} · ${sessions.length} session${sessions.length !== 1 ? "s" : ""}`}
        actions={
          <Button variant="ghost" size="sm" icon={<RefreshCw size={14} />} onClick={() => { fetchWorkspaces(); if (activeWorkspace) fetchSessions(activeWorkspace.id); }}>
            Refresh
          </Button>
        }
      />

      <div className="flex gap-6">
        {/* Left: Workspaces */}
        <div className="w-64 shrink-0">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-rw-muted uppercase tracking-wider flex items-center gap-2">
              <Layers size={14} /> Workspaces
            </h2>
            <IconButton
              icon={<Plus size={14} />}
              label="New workspace"
              onClick={() => setShowCreateWorkspace(true)}
            />
          </div>

          {showCreateWorkspace && (
            <div className="mb-3">
              <CreateWorkspaceForm onDone={(created) => { setShowCreateWorkspace(false); if (created) fetchWorkspaces(); }} />
            </div>
          )}

          {loading ? (
            <Spinner label="Loading..." />
          ) : workspaces.length === 0 ? (
            <Card>
              <EmptyState icon={<Layers size={20} />} title="No workspaces" compact
                action={!showCreateWorkspace ? <Button size="sm" variant="secondary" icon={<Plus size={12} />} onClick={() => setShowCreateWorkspace(true)}>Create</Button> : undefined}
              />
            </Card>
          ) : (
            <div className="space-y-1">
              {workspaces.map((ws) => (
                <button
                  key={ws.id}
                  onClick={() => selectWorkspace(ws)}
                  className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors group flex items-center gap-2 ${
                    activeWorkspace?.id === ws.id
                      ? "bg-rw-accent/10 text-rw-accent border border-rw-accent/20"
                      : "text-rw-muted hover:bg-rw-surface border border-transparent"
                  }`}
                >
                  <Layers size={14} className="shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{ws.name}</div>
                    {ws.description && <div className="text-[10px] text-rw-dim truncate">{ws.description}</div>}
                  </div>
                  <IconButton
                    icon={<Trash2 size={11} />}
                    label="Delete"
                    variant="danger"
                    size="sm"
                    className="opacity-0 group-hover:opacity-100 shrink-0"
                    onClick={(e) => deleteWorkspace(ws.id, e)}
                  />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right: Sessions for selected workspace */}
        <div className="flex-1 min-w-0">
          {!activeWorkspace ? (
            <Card>
              <EmptyState
                icon={<FolderOpen size={28} />}
                title="Select a workspace"
                description="Choose a workspace from the left to view its sessions."
              />
            </Card>
          ) : (
            <>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-medium text-rw-muted uppercase tracking-wider flex items-center gap-2">
                  <FolderOpen size={14} /> Sessions in {activeWorkspace.name}
                </h2>
                <Button variant="ghost" size="sm" icon={<Plus size={13} />} onClick={() => setShowCreateSession(true)}>
                  New session
                </Button>
              </div>

              {showCreateSession && (
                <div className="mb-3">
                  <CreateSessionForm
                    workspaceId={activeWorkspace.id}
                    onDone={(created) => { setShowCreateSession(false); if (created) fetchSessions(activeWorkspace.id); }}
                  />
                </div>
              )}

              {sessions.length === 0 ? (
                <Card>
                  <EmptyState
                    icon={<FolderOpen size={28} />}
                    title="No sessions yet"
                    description="Create a session to organize targets and track hunts."
                    action={
                      !showCreateSession ? (
                        <Button size="sm" variant="secondary" icon={<Plus size={13} />} onClick={() => setShowCreateSession(true)}>
                          Create session
                        </Button>
                      ) : undefined
                    }
                  />
                </Card>
              ) : (
                <div className="space-y-2">
                  {sessions.map((s) => (
                    <Card key={s.id} className="group hover:border-rw-accent/20 transition-colors cursor-pointer" padding="md">
                      <div
                        className="flex items-center gap-4"
                        onClick={() => setActiveSession(s)}
                      >
                        <FolderOpen size={18} className="text-rw-accent shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-rw-text">{s.name}</div>
                          <div className="text-xs text-rw-dim mt-0.5">
                            {s.target_count} target{s.target_count !== 1 ? "s" : ""} · {s.hunt_count} hunt{s.hunt_count !== 1 ? "s" : ""}
                          </div>
                        </div>
                        <Badge variant={s.status === "active" ? "success" : "default"} dot>
                          {s.status}
                        </Badge>
                        {s.tags.length > 0 && (
                          <div className="flex gap-1">
                            {s.tags.map((t) => (
                              <span key={t} className="text-[10px] bg-rw-surface text-rw-dim px-1.5 py-0.5 rounded">{t}</span>
                            ))}
                          </div>
                        )}
                        <ChevronRight size={14} className="text-rw-dim shrink-0" />
                        <IconButton
                          icon={<Trash2 size={12} />}
                          label="Delete session"
                          variant="danger"
                          size="sm"
                          className="opacity-0 group-hover:opacity-100 shrink-0"
                          onClick={(e) => deleteSession(s.id, e)}
                        />
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

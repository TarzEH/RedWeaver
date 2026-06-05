import type {
  RunSummary,
  RunDetail,
  Finding,
  KeysStatus,
  ToolsAPIResponse,
  VulnerabilityReport,
} from "../types/api";
import { apiDelete, apiFetch } from "./http";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  return apiFetch<T>(path, options);
}

/* ── v0.6 insight + KB types ── */

export interface RunCompare {
  run_id: string;
  baseline_id: string;
  new: Finding[];
  fixed: Finding[];
  recurring: Finding[];
  summary: { new: number; fixed: number; recurring: number };
}

export interface AttackChain {
  id: string;
  name: string;
  description: string;
  severity: string;
  steps: string[];
  finding_ids: string[];
  created_at: string;
}

export interface AssetHost {
  host: string;
  findings: number;
  max_severity: string;
  ports: number[];
  technologies: string[];
  cves: string[];
  exploit_available: boolean;
  screenshot: string;
}

export interface PosturePoint {
  run_id: string;
  date: string;
  target: string;
  exposure: number;
  findings: number;
  by_severity: Record<string, number>;
}
export interface PostureSeries {
  session_id: string;
  points: PosturePoint[];
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  severity: string;
}
export interface AttackGraph {
  run_id: string;
  nodes: GraphNode[];
  edges: { source: string; target: string }[];
}

export interface AssetInventory {
  session_id: string;
  asset_count: number;
  assets: AssetHost[];
}

export interface KbResult {
  content: string;
  file: string;
  category: string;
  relevance_score: number;
}

export interface KbFile {
  file: string;
  category: string;
  chunks: number;
  title: string;
}

export interface KbDocument {
  file: string;
  category: string;
  title: string;
  content: string;
}

/* ── Types matching backend DTOs ── */

export interface WorkspaceResponse {
  id: string;
  name: string;
  description: string;
  owner_id: string;
  member_ids: string[];
  created_at: string;
}

export interface SessionResponse {
  id: string;
  name: string;
  description: string;
  workspace_id: string;
  status: string;
  target_count: number;
  hunt_count: number;
  finding_count: number;
  tags: string[];
  created_at: string;
}

export interface TargetResponse {
  id: string;
  name: string;
  target_type: string;
  session_id: string;
  address: string;
  notes: string;
  tags: string[];
  created_at: string;
}

export interface HuntResponse {
  id: string;
  session_id: string;
  target_ids: string[];
  status: string;
  target: string;
  objective: string;
  finding_count: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface HuntDetail extends HuntResponse {
  messages: Record<string, unknown>[];
  graph_state: Record<string, unknown>;
  error_message: string;
}

/* ── Observability / behind-the-scenes debug types ── */

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ToolExecutionRow {
  id: string;
  agent_name: string;
  tool_name: string;
  sequence: number;
  command_str: string;
  argv: string[];
  raw_stdout: string;
  raw_stderr: string;
  exit_code: number | null;
  parsed_result: unknown;
  status: string;
  duration_ms: number | null;
  started_at: string | null;
}

export interface AgentStepRow {
  id: string;
  agent_name: string;
  sequence: number;
  step_type: string;
  from_agent: string;
  to_agent: string;
  reasoning_text: string;
  output_summary: string;
  confidence: number | null;
}

export interface EventLogRow {
  id: string;
  sequence: number;
  event_type: string;
  agent_name: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface ScreenshotRow {
  id: string;
  agent_name: string;
  tool_name: string;
  url: string;
  image_url: string | null;
  page_title: string;
  http_status: number | null;
  taken_at: string;
}

/* ── API Client ── */

export const api = {
  runs: {
    list: () => request<RunSummary[]>("/api/runs"),
    get: (id: string) => request<RunDetail>(`/api/runs/${id}`),
    delete: (id: string) => apiDelete(`/api/runs/${id}`),
    report: (id: string) => request<VulnerabilityReport>(`/api/runs/${id}/report`),
    findings: (id: string) =>
      request<{ findings: Finding[] }>(`/api/runs/${id}/findings`).then(
        (d) => d.findings || (d as unknown as Finding[]) || [],
      ),
    offsecStart: (id: string) =>
      request<{ status: string }>(`/api/runs/${id}/offsec`, { method: "POST" }),
    offsecGet: (id: string) =>
      request<{ status: string; markdown: string }>(`/api/runs/${id}/offsec`),
    // v0.6: previously-orphaned insight endpoints
    compare: (id: string, baseline: string) =>
      request<RunCompare>(`/api/runs/${id}/compare?baseline=${baseline}`),
    attackChains: (id: string) =>
      request<AttackChain[]>(`/api/runs/${id}/attack-chains`),
    attackGraph: (id: string) =>
      request<AttackGraph>(`/api/runs/${id}/attack-graph`),
    ask: (id: string, question: string) =>
      request<{ answer: string; question: string }>(`/api/runs/${id}/ask`, {
        method: "POST",
        body: JSON.stringify({ question }),
      }),
  },

  insights: {
    assets: (sessionId: string) =>
      request<AssetInventory>(`/api/sessions/${sessionId}/assets`),
    posture: (sessionId: string) =>
      request<PostureSeries>(`/api/sessions/${sessionId}/posture`),
  },

  chat: {
    send: (body: Record<string, unknown>) =>
      request<{ reply: string; deferred?: boolean; created_run?: boolean; run_id?: string }>(
        "/api/chat",
        { method: "POST", body: JSON.stringify(body) },
      ),
  },

  settings: {
    getKeys: () => request<KeysStatus>("/api/settings/keys"),
    saveKeys: (body: Record<string, unknown>) =>
      request<KeysStatus>("/api/settings/keys", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    getTools: () => request<ToolsAPIResponse>("/api/tools"),
    getModels: (provider: string) =>
      request<{ models: { id: string; name: string }[] }>(`/api/settings/models/${provider}`),
    ollamaHealth: (url?: string) =>
      request<{ status: string }>(
        `/api/settings/ollama/health${url ? `?url=${encodeURIComponent(url)}` : ""}`,
      ),
    ollamaModels: (url?: string) =>
      request<{ models: { name: string; size?: number }[] }>(
        `/api/settings/ollama/models${url ? `?url=${encodeURIComponent(url)}` : ""}`,
      ),
  },

  workspaces: {
    list: () => request<WorkspaceResponse[]>("/api/workspaces"),
    get: (id: string) => request<WorkspaceResponse>(`/api/workspaces/${id}`),
    create: (body: { name: string; description?: string }) =>
      request<WorkspaceResponse>("/api/workspaces", { method: "POST", body: JSON.stringify(body) }),
    delete: (id: string) => apiDelete(`/api/workspaces/${id}`),
  },

  sessions: {
    list: (workspaceId?: string) =>
      request<SessionResponse[]>(
        `/api/sessions${workspaceId ? `?workspace_id=${workspaceId}` : ""}`,
      ),
    get: (id: string) => request<SessionResponse>(`/api/sessions/${id}`),
    create: (body: { name: string; description?: string; workspace_id: string; tags?: string[] }) =>
      request<SessionResponse>("/api/sessions", { method: "POST", body: JSON.stringify(body) }),
    update: (id: string, body: Record<string, unknown>) =>
      request<SessionResponse>(`/api/sessions/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    delete: (id: string) => apiDelete(`/api/sessions/${id}`),
    linkTarget: (sessionId: string, targetId: string) =>
      request(`/api/sessions/${sessionId}/targets/${targetId}`, { method: "POST" }),
  },

  targets: {
    list: (sessionId?: string) =>
      request<TargetResponse[]>(
        `/api/targets${sessionId ? `?session_id=${sessionId}` : ""}`,
      ),
    get: (id: string) => request<TargetResponse>(`/api/targets/${id}`),
    create: (body: {
      name: string;
      target_type: string;
      session_id: string;
      url?: string;
      base_url?: string;
      cidr_ranges?: string[];
      ip?: string;
      domain?: string;
      notes?: string;
      tags?: string[];
      ssh_host?: string;
      ssh_username?: string;
      ssh_password?: string;
      ssh_key_path?: string;
      ssh_port?: number;
    }) => request<TargetResponse>("/api/targets", { method: "POST", body: JSON.stringify(body) }),
    update: (id: string, body: Record<string, unknown>) =>
      request<TargetResponse>(`/api/targets/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    delete: (id: string) => apiDelete(`/api/targets/${id}`),
  },

  hunts: {
    list: (sessionId?: string) =>
      request<HuntResponse[]>(`/api/hunts${sessionId ? `?session_id=${sessionId}` : ""}`),
    get: (id: string) => request<HuntDetail>(`/api/hunts/${id}`),
    create: (body: {
      session_id: string;
      target_ids: string[];
      objective?: string;
      agent_selection?: string[];
      timeout_seconds?: number;
      ssh_config?: Record<string, unknown>;
    }) => request<HuntResponse>("/api/hunts", { method: "POST", body: JSON.stringify(body) }),
    start: (id: string) => request<HuntResponse>(`/api/hunts/${id}/start`, { method: "POST" }),
    stop: (id: string) => request<HuntResponse>(`/api/hunts/${id}/stop`, { method: "POST" }),
    delete: (id: string) => apiDelete(`/api/hunts/${id}`),
  },

  knowledge: {
    health: () =>
      request<{ status: string; documents_indexed: number; files_indexed: number }>(
        "/api/knowledge/health",
      ),
    query: (body: { query: string; top_k?: number; category?: string }) =>
      request<{ results: KbResult[] }>(
        "/api/knowledge/query",
        { method: "POST", body: JSON.stringify(body) },
      ),
    categories: () =>
      request<{ categories: { category: string; chunks: number; files: number }[] }>(
        "/api/knowledge/categories",
      ),
    files: (category?: string) =>
      request<{ files: KbFile[] }>(
        `/api/knowledge/files${category ? `?category=${encodeURIComponent(category)}` : ""}`,
      ),
    document: (file: string) =>
      request<KbDocument>(`/api/knowledge/document?file=${encodeURIComponent(file)}`),
    ask: (question: string) =>
      request<{ answer: string; sources: string[]; question: string }>(
        "/api/knowledge/ask",
        { method: "POST", body: JSON.stringify({ question }) },
      ),
  },

  /* Behind-the-scenes observability (the debug surface) */
  debug: {
    toolExecutions: (runId: string) =>
      request<Paginated<ToolExecutionRow>>(`/api/runs/${runId}/tool-executions`),
    agentSteps: (runId: string) =>
      request<Paginated<AgentStepRow>>(`/api/runs/${runId}/agent-steps`),
    events: (runId: string, after?: number) =>
      request<Paginated<EventLogRow>>(
        `/api/runs/${runId}/events${after ? `?after=${after}` : ""}`,
      ),
    screenshots: (runId: string) =>
      request<Paginated<ScreenshotRow>>(`/api/runs/${runId}/screenshots`),
  },
};

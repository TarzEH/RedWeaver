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
      request<{ results: { content: string; file: string; category: string; relevance_score: number }[] }>(
        "/api/knowledge/query",
        { method: "POST", body: JSON.stringify(body) },
      ),
  },
};

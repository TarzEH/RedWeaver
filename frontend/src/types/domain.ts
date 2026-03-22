/** Domain types matching backend domain models. */

// ── Auth ──

export interface User {
  id: string;
  email: string;
  username: string;
  role: "admin" | "operator" | "viewer";
  is_active: boolean;
  workspace_ids: string[];
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AuthResponse {
  user: User;
  tokens: TokenResponse;
}

// ── Workspace ──

export interface Workspace {
  id: string;
  name: string;
  description: string;
  owner_id: string;
  member_ids: string[];
  created_at: string;
}

// ── Session ──

export type SessionStatus = "active" | "completed" | "archived";

export interface Session {
  id: string;
  name: string;
  description: string;
  workspace_id: string;
  status: SessionStatus;
  target_count: number;
  hunt_count: number;
  finding_count: number;
  tags: string[];
  created_at: string;
}

export interface SessionDetail extends Session {
  target_ids: string[];
  hunt_ids: string[];
}

// ── Target ──

export type TargetType = "webapp" | "api" | "network" | "host" | "identity";

export interface Target {
  id: string;
  name: string;
  target_type: TargetType;
  session_id: string;
  notes: string;
  tags: string[];
  created_at: string;
  address: string;
}

export interface TargetCreate {
  name: string;
  target_type: TargetType;
  session_id: string;
  notes?: string;
  tags?: string[];
  // WebApp / API
  url?: string;
  base_url?: string;
  spec_url?: string;
  auth_config?: Record<string, unknown>;
  auth_headers?: Record<string, string>;
  tech_stack?: string[];
  // Network
  cidr_ranges?: string[];
  port_ranges?: string;
  // Host
  ip?: string;
  os_hint?: string;
  ssh_host?: string;
  ssh_username?: string;
  ssh_password?: string;
  ssh_key_path?: string;
  ssh_port?: number;
  // Identity
  domain?: string;
  email_patterns?: string[];
}

// ── Hunt ──

export type HuntStatus = "queued" | "running" | "paused" | "completed" | "failed" | "cancelled";

export interface Hunt {
  id: string;
  session_id: string;
  target_ids: string[];
  status: HuntStatus;
  target: string;
  objective: string;
  finding_count: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface HuntCreate {
  session_id: string;
  target_ids?: string[];
  objective?: string;
  agent_selection?: string[];
  timeout_seconds?: number;
  ssh_config?: Record<string, unknown>;
}

// ── Finding (enhanced) ──

export type FindingStatus = "new" | "confirmed" | "false_positive" | "accepted_risk" | "remediated";

export interface FindingDetail {
  id: string;
  title: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  description: string;
  affected_url: string;
  evidence: string | null;
  remediation: string | null;
  agent_source: string;
  tool_used: string | null;
  cvss_score: number | null;
  cve_ids: string[];
  status: FindingStatus;
  hunt_id: string;
  session_id: string;
  target_id: string;
  dedup_key: string;
  created_at: string;
}

export interface FindingAggregate {
  total: number;
  by_severity: Record<string, number>;
  by_status: Record<string, number>;
  by_agent: Record<string, number>;
  unique_count: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

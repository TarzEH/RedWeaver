/** API response types for RedWeaver backend. */

/**
 * Run lifecycle states. Mirrors the backend `RunStatus` choices
 * (backend/apps/hunts/models.py) plus the frontend-only "idle" placeholder.
 * `cancelled` covers both a user Stop and a budget-exceeded abort — omitting it
 * left those runs looking like they were still executing forever.
 */
export type RunStatus =
  | "queued"
  | "running"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled"
  | "idle";

export interface RunSummary {
  run_id: string;
  target: string;
  status: RunStatus;
  created_at: string;
  /** Set when this run was started from a workspace session hunt */
  hunt_id?: string;
  session_id?: string;
  workspace_id?: string;
  session_name?: string;
  workspace_name?: string;
}

export interface RunMessage {
  role: "user" | "assistant" | "system";
  content: string;
  status?: string;
}

export interface GraphState {
  current_node: string | null;
  active_nodes?: string[];
  completed_nodes: string[];
  plan?: string[];
  steps?: AgentStep[];
  findings?: Finding[];
  report_markdown?: string;
}

export interface RunDetail {
  run_id: string;
  target: string;
  status: RunStatus;
  created_at: string;
  messages: RunMessage[];
  graph_state?: GraphState;
  scope?: string | null;
  objective?: string;
  hunt_id?: string;
  session_id?: string;
  workspace_id?: string;
  session_name?: string;
  workspace_name?: string;
}

/**
 * Kinds of persisted agent step. Mirrors the backend `StepType` choices
 * (backend/apps/observability/models.py) — note these are NOT the SSE event
 * names: the backend persists "thinking"/"handoff" where the live stream sends
 * "agent_thinking"/"agent_handoff".
 */
export type AgentStepType =
  | "agent_start"
  | "thinking"
  | "tool_call"
  | "tool_result"
  | "agent_complete"
  | "handoff"
  | "finding"
  | "error";

/**
 * A persisted agent step exactly as the REST API serializes it
 * (backend/apps/hunts/serializers.py::_graph_state). The field names differ
 * from the live SSE payload, and reading the wrong ones silently blanks the
 * whole reasoning timeline on reload — so this type (not `Record<string,
 * unknown>`) is what hydration must consume, making the next rename a compile
 * error. No tool name is persisted here.
 */
export interface AgentStep {
  /** `AgentStep.agent_name`; may be "" for steps written without an agent. */
  agent: string;
  /** `AgentStep.step_type` — a backend StepType value, not an SSE event type. */
  action: AgentStepType;
  /** `output_summary` or `reasoning_text`; "" when the step recorded neither. */
  result?: string;
  /** ISO-8601 string (`created_at.isoformat()`), never an epoch number. */
  timestamp?: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
}

export interface GraphEdge {
  from: string;
  to: string;
  label?: string;
}

export interface GraphTopology {
  nodes: GraphNode[];
  edges: GraphEdge[];
  state?: {
    current_node: string | null;
    completed_nodes: string[];
  };
}

export interface ToolInfo {
  name: string;
  category: string;
  available: boolean;
  description?: string;
}

export interface ToolAvailabilityReport {
  tools: ToolInfo[];
  total: number;
  available: number;
}

/** Actual shape returned by GET /api/tools */
export interface ToolsAPIResponse {
  categories: Record<string, Omit<ToolInfo, "category">[]>;
  total_count: number;
  available_count: number;
}

export interface KeysStatus {
  openai_configured: boolean;
  anthropic_configured: boolean;
  google_configured: boolean;
  ollama_configured: boolean;
  ollama_base_url: string | null;
  model_provider: string | null;
  selected_model: string | null;
}

export interface EmbeddingModelOption {
  id: string;
  dim: number;
  label: string;
}

export interface EmbeddingProviderOption {
  id: string;
  label: string;
  needs_key: boolean;
  models: EmbeddingModelOption[];
}

export interface EmbeddingConfig {
  provider: string;
  model: string;
  dimension: number;
  device: string;
  status: "idle" | "running" | "done" | "error";
  last_error: string;
  last_indexed_at: string | null;
  chunk_count: number;
  openai_key_configured: boolean;
  providers: EmbeddingProviderOption[];
}

export interface OllamaModel {
  name: string;
  size: number;
  modified_at: string;
}

export interface OllamaModelsResponse {
  models: OllamaModel[];
  base_url: string;
}

export interface OllamaHealthResponse {
  status: "connected" | "disconnected";
  base_url: string;
}

export interface SSHConfig {
  host: string;
  username: string;
  password?: string;
  key_path?: string;
  port?: number;
}

export interface ChatResult {
  reply: string;
  run_id?: string;
  deferred?: boolean;
  created_run?: boolean;
}

/** Severity levels for vulnerability findings. */
export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface Finding {
  id: string;
  title: string;
  severity: Severity;
  description: string;
  affected_url: string;
  evidence?: string | null;
  remediation?: string | null;
  agent_source: string;
  tool_used?: string | null;
  cvss_score?: number | null;
  cve_ids: string[];
  timestamp: string;
  status?: string;
  confidence?: number | null;
  exploitability?: string;
  cisa_kev?: boolean;
  epss_score?: number | null;
  risk_score?: number | null;
  risk_decision?: string;
  /** Agent that adjudicated this finding (e.g. "verifier"); empty if never verified. */
  verified_by_agent?: string;
}

export interface ServiceInfo {
  host: string;
  port: number | null;
  service: string;
  version: string;
  technologies: string[];
  status_code: number | null;
}

export interface RemediationPriority {
  finding_id: string;
  title: string;
  severity: string;
  remediation: string;
  cvss_score: number | null;
}

/** OWASP Top 10 category coverage entry. */
export interface OwaspCategory {
  category: string;
  count: number;
}

/** MITRE ATT&CK technique coverage entry. */
export interface MitreTechnique {
  technique: string;
  count: number;
}

/** Compliance / framework mapping for the report. */
export interface ReportCompliance {
  owasp_top_10?: OwaspCategory[];
  mitre_attack?: MitreTechnique[];
}

/** White-label branding for the report header. */
export interface ReportBranding {
  name?: string;
  color?: string;
  logo_url?: string;
}

/** Optional LLM/token cost breakdown for the run. */
export interface ReportCost {
  total_usd?: number;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  model?: string;
  /** True when the model has no price entry, so total_usd is a rough guess. */
  is_estimate?: boolean;
  /** Effective spend ceiling for the run (per-run, else the install default). */
  budget_usd?: number | null;
  /** Fraction of the budget consumed (0..1+), when a budget was set. */
  budget_used_fraction?: number | null;
}

export interface VulnerabilityReport {
  run_id: string;
  target: string;
  executive_summary: string;
  scope: string;
  objective: string;
  methodology: string;
  findings: Finding[];
  total_by_severity?: Record<string, number>;
  findings_by_severity?: Record<string, number>;
  report_markdown: string;
  generated_at: string;
  risk_rating: string;
  discovered_services: ServiceInfo[];
  discovered_technologies: string[];
  total_endpoints: number;
  findings_by_agent: Record<string, number>;
  agents_executed: string[];
  tools_used: string[];
  remediation_priorities: RemediationPriority[];
  /** Framework coverage (OWASP Top 10 / MITRE ATT&CK). */
  compliance?: ReportCompliance;
  /** White-label branding for premium / pro reports. */
  branding?: ReportBranding;
  /** Optional token / dollar cost breakdown for the run. */
  cost?: ReportCost;
}

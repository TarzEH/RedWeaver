/** API response types for RedWeaver backend. */

export type RunStatus = "queued" | "running" | "completed" | "failed" | "idle";

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

export interface AgentStep {
  agent: string;
  action: string;
  result?: string;
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
}

/** SSE event types matching backend event constants. */

export const EVENT_AGENT_START = "agent_start";
export const EVENT_AGENT_THINKING = "agent_thinking";
export const EVENT_TOOL_CALL = "tool_call";
export const EVENT_TOOL_RESULT = "tool_result";
export const EVENT_AGENT_COMPLETE = "agent_complete";
export const EVENT_FINDING = "finding";
export const EVENT_GRAPH_STATE = "graph_state";
export const EVENT_HUNT_COMPLETE = "hunt_complete";
export const EVENT_HUNT_ERROR = "hunt_error";
export const EVENT_SUBAGENT_SPAWN = "subagent_spawn";
export const EVENT_TODO_UPDATE = "todo_update";
export const EVENT_AGENT_HANDOFF = "agent_handoff";

export type SSEEventType =
  | typeof EVENT_AGENT_START
  | typeof EVENT_AGENT_THINKING
  | typeof EVENT_TOOL_CALL
  | typeof EVENT_TOOL_RESULT
  | typeof EVENT_AGENT_COMPLETE
  | typeof EVENT_FINDING
  | typeof EVENT_GRAPH_STATE
  | typeof EVENT_HUNT_COMPLETE
  | typeof EVENT_HUNT_ERROR
  | typeof EVENT_SUBAGENT_SPAWN
  | typeof EVENT_TODO_UPDATE
  | typeof EVENT_AGENT_HANDOFF;

export interface SSEEvent {
  type: SSEEventType;
  data: Record<string, unknown>;
}

export interface AgentStartEvent {
  type: typeof EVENT_AGENT_START;
  data: { agent: string; run_id: string };
}

export interface AgentThinkingEvent {
  type: typeof EVENT_AGENT_THINKING;
  /** Backend may send `content` and/or `thinking` (both are the same text). */
  data: { agent: string; thinking?: string; content?: string };
}

export interface ToolCallEvent {
  type: typeof EVENT_TOOL_CALL;
  data: { agent: string; tool: string; input: string };
}

export interface ToolResultEvent {
  type: typeof EVENT_TOOL_RESULT;
  data: { agent: string; tool: string; output: string };
}

export interface AgentCompleteEvent {
  type: typeof EVENT_AGENT_COMPLETE;
  data: { agent: string; summary?: string };
}

export interface FindingEvent {
  type: typeof EVENT_FINDING;
  data: {
    id: string;
    title: string;
    severity: string;
    agent_source: string;
    affected_url: string;
  };
}

export interface GraphStateEvent {
  type: typeof EVENT_GRAPH_STATE;
  data: {
    current_node: string | null;
    completed_nodes: string[];
    plan?: string[];
  };
}

export interface HuntCompleteEvent {
  type: typeof EVENT_HUNT_COMPLETE;
  data: { run_id: string; findings_count: number };
}

export interface HuntErrorEvent {
  type: typeof EVENT_HUNT_ERROR;
  data: { run_id: string; error: string };
}

export interface SubAgentSpawnEvent {
  type: typeof EVENT_SUBAGENT_SPAWN;
  data: {
    parent_agent: string;
    subagent_name: string;
    task_description: string;
  };
}

export interface TodoUpdateEvent {
  type: typeof EVENT_TODO_UPDATE;
  data: {
    todos: Array<{ task?: string; content?: string; status?: string }>;
  };
}

export interface AgentHandoffEvent {
  type: typeof EVENT_AGENT_HANDOFF;
  data: {
    from_agent: string;
    to_agent: string;
    from_display: string;
    to_display: string;
  };
}

/** Union of all typed SSE events. */
export type TypedSSEEvent =
  | AgentStartEvent
  | AgentThinkingEvent
  | ToolCallEvent
  | ToolResultEvent
  | AgentCompleteEvent
  | FindingEvent
  | GraphStateEvent
  | HuntCompleteEvent
  | HuntErrorEvent
  | SubAgentSpawnEvent
  | TodoUpdateEvent
  | AgentHandoffEvent;

/** Shared graph state shape used by useRunStream and HuntContext. */
export interface GraphSSEState {
  current_node: string | null;
  active_nodes: string[];
  completed_nodes: string[];
  plan: string[];
}

/** A reasoning step displayed in the UI timeline. */
export interface ReasoningStep {
  id: string;
  agent: string;
  type: SSEEventType;
  content: string;
  tool?: string;
  timestamp: number;
}

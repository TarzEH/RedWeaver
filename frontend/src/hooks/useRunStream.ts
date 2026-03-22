import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import { getApiBase } from "../config/theme";
import { useSSE } from "./useSSE";
import type { Finding } from "../types/api";
import type {
  ReasoningStep,
  SSEEventType,
  GraphSSEState,
} from "../types/events";
import { AGENT_ORDER } from "../config/agents";
import {
  EVENT_AGENT_START,
  EVENT_AGENT_THINKING,
  EVENT_TOOL_CALL,
  EVENT_TOOL_RESULT,
  EVENT_AGENT_COMPLETE,
  EVENT_AGENT_HANDOFF,
  EVENT_FINDING,
  EVENT_GRAPH_STATE,
  EVENT_HUNT_COMPLETE,
  EVENT_HUNT_ERROR,
  EVENT_SUBAGENT_SPAWN,
  EVENT_TODO_UPDATE,
} from "../types/events";

interface RunStreamState {
  steps: ReasoningStep[];
  graphState: GraphSSEState;
  findings: Finding[];
  activeAgent: string | null;
  done: boolean;
  error: string | null;
}

function makeStreamStep(
  agent: string,
  type: SSEEventType,
  content: string,
  tool?: string
): ReasoningStep {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    agent,
    type,
    content,
    tool,
    timestamp: Date.now(),
  };
}

/**
 * Hook that connects to a run's SSE stream and accumulates:
 * - Reasoning steps (thinking, tool calls, tool results)
 * - Graph state (active nodes, completed nodes, plan)
 * - Findings (structured vulnerability findings)
 *
 * Supports parallel execution: multiple nodes can be active simultaneously.
 */
const emptyGraph = (): GraphSSEState => ({
  current_node: null,
  active_nodes: [],
  completed_nodes: [],
  plan: [],
});

export function useRunStream(runId: string | null, enabled: boolean = true) {
  const [state, setState] = useState<RunStreamState>({
    steps: [],
    graphState: emptyGraph(),
    findings: [],
    activeAgent: null,
    done: false,
    error: null,
  });

  const base = getApiBase();

  const url = useMemo(() => {
    if (!runId || !enabled) return null;
    return `${base}/api/runs/${runId}/stream`;
  }, [base, runId, enabled]);

  const thinkingQueueRef = useRef<{ agent: string; token: string }[]>([]);
  const thinkingRafRef = useRef<number | null>(null);

  // When switching hunts, clear accumulated stream state immediately so the previous run
  // does not merge with the next (hydration + SSE would otherwise mix runs).
  useEffect(() => {
    thinkingQueueRef.current = [];
    if (thinkingRafRef.current != null) {
      cancelAnimationFrame(thinkingRafRef.current);
      thinkingRafRef.current = null;
    }
    setState({
      steps: [],
      graphState: emptyGraph(),
      findings: [],
      activeAgent: null,
      done: false,
      error: null,
    });
  }, [runId]);

  const flushThinkingQueue = useCallback(() => {
    thinkingRafRef.current = null;
    const batch = thinkingQueueRef.current;
    thinkingQueueRef.current = [];
    if (batch.length === 0) return;
    setState((prev) => {
      let next = prev;
      for (const { agent, token } of batch) {
        if (!token) continue;
        const lastIdx = next.steps.length - 1;
        const last = lastIdx >= 0 ? next.steps[lastIdx] : null;
        if (last && last.type === EVENT_AGENT_THINKING && last.agent === agent) {
          const updated = [...next.steps];
          updated[lastIdx] = { ...last, content: last.content + token };
          next = { ...next, steps: updated };
        } else {
          next = {
            ...next,
            steps: [...next.steps, makeStreamStep(agent, EVENT_AGENT_THINKING, token)],
          };
        }
      }
      return next;
    });
  }, []);

  useEffect(() => {
    return () => {
      if (thinkingRafRef.current != null) {
        cancelAnimationFrame(thinkingRafRef.current);
      }
    };
  }, []);

  const onEvent = useCallback(
    (event: { type: string; data: Record<string, unknown> }) => {
      const { type, data } = event;
      const agent = (data.agent as string) || "unknown";

      if (type === EVENT_AGENT_THINKING) {
        const token =
          (data.thinking as string) ||
          (data.content as string) ||
          "";
        if (!token) return;
        thinkingQueueRef.current.push({ agent, token });
        if (thinkingRafRef.current == null) {
          thinkingRafRef.current = requestAnimationFrame(flushThinkingQueue);
        }
        return;
      }

      setState((prev) => {
        switch (type) {
          case EVENT_AGENT_START:
            return {
              ...prev,
              activeAgent: agent,
              steps: [
                ...prev.steps,
                makeStreamStep(agent, EVENT_AGENT_START, `${agent} started`),
              ],
            };

          case EVENT_TOOL_CALL:
            return {
              ...prev,
              steps: [
                ...prev.steps,
                makeStreamStep(
                  agent,
                  EVENT_TOOL_CALL,
                  (data.input as string) || "",
                  (data.tool as string) || undefined
                ),
              ],
            };

          case EVENT_TOOL_RESULT:
            return {
              ...prev,
              steps: [
                ...prev.steps,
                makeStreamStep(
                  agent,
                  EVENT_TOOL_RESULT,
                  (data.summary as string) || (data.output as string) || "",
                  (data.tool as string) || undefined
                ),
              ],
            };

          case EVENT_AGENT_COMPLETE:
            return {
              ...prev,
              activeAgent: null,
              steps: [
                ...prev.steps,
                makeStreamStep(
                  agent,
                  EVENT_AGENT_COMPLETE,
                  (data.summary as string) || `${agent} completed`
                ),
              ],
            };

          case EVENT_AGENT_HANDOFF: {
            const toAgent = (data.to_agent as string) || "";
            const fromDisplay = (data.from_display as string) || agent;
            const toDisplay = (data.to_display as string) || toAgent;
            return {
              ...prev,
              activeAgent: toAgent,
              steps: [
                ...prev.steps,
                makeStreamStep(
                  agent,
                  EVENT_AGENT_HANDOFF,
                  `Handoff: ${fromDisplay} → ${toDisplay}`
                ),
              ],
            };
          }

          case EVENT_FINDING: {
            const finding = data as unknown as Finding;
            return {
              ...prev,
              findings: [...prev.findings, finding],
              steps: [
                ...prev.steps,
                makeStreamStep(
                  (data.agent_source as string) || agent,
                  EVENT_FINDING,
                  `[${(data.severity as string || "info").toUpperCase()}] ${data.title as string}`
                ),
              ],
            };
          }

          case EVENT_GRAPH_STATE: {
            // Merge completed_nodes: use incoming if non-empty, else keep prev
            const incomingCompleted = data.completed_nodes as string[] | undefined;
            const mergedCompleted =
              incomingCompleted && incomingCompleted.length > 0
                ? incomingCompleted
                : prev.graphState.completed_nodes;

            const incomingPlan = data.plan as string[] | undefined;
            const mergedPlan =
              incomingPlan && incomingPlan.length > 0
                ? incomingPlan
                : prev.graphState.plan;

            // Support parallel execution: track active_nodes list
            const incomingActive = data.active_nodes as string[] | undefined;
            const activeNodes = incomingActive || [];

            return {
              ...prev,
              graphState: {
                current_node: (data.current_node as string) || activeNodes[0] || null,
                active_nodes: activeNodes,
                completed_nodes: mergedCompleted,
                plan: mergedPlan,
              },
            };
          }

          case EVENT_HUNT_COMPLETE: {
            // Mark all pipeline nodes as completed on hunt finish
            const allCompleted = [
              ...new Set([
                ...prev.graphState.completed_nodes,
                ...(prev.graphState.plan || []),
                ...AGENT_ORDER,
              ]),
            ];
            return {
              ...prev,
              done: true,
              activeAgent: null,
              graphState: {
                ...prev.graphState,
                current_node: "end",
                active_nodes: [],
                completed_nodes: allCompleted,
              },
            };
          }

          case EVENT_HUNT_ERROR:
            return {
              ...prev,
              done: true,
              activeAgent: null,
              error: (data.error as string) || "Hunt failed",
            };

          case EVENT_SUBAGENT_SPAWN: {
            const subName = (data.subagent_name as string) || "";
            return {
              ...prev,
              steps: [
                ...prev.steps,
                makeStreamStep(
                  agent,
                  EVENT_SUBAGENT_SPAWN,
                  `Spawning sub-agent: ${subName} — ${(data.task_description as string) || ""}`
                ),
              ],
            };
          }

          case EVENT_TODO_UPDATE: {
            const todos = (data.todos as Array<{ task?: string; content?: string; status?: string }>) || [];
            const planItems = todos.map(
              (t) => `${t.status === "completed" ? "[x]" : "[ ]"} ${t.task || t.content || ""}`
            );
            return {
              ...prev,
              graphState: {
                ...prev.graphState,
                plan: planItems,
              },
              steps: [
                ...prev.steps,
                makeStreamStep("orchestrator", EVENT_TODO_UPDATE, `Plan updated: ${todos.length} tasks`),
              ],
            };
          }

          default:
            return prev;
        }
      });

    },
    [flushThinkingQueue]
  );

  const { connected } = useSSE({
    url,
    onEvent,
  });

  // Hydrate state from persisted run data (supports page reload).
  // Merges API data with any SSE events that may have arrived first for *this* run only.
  useEffect(() => {
    if (!runId || !enabled) return;
    const expectedId = runId;
    let cancelled = false;

    fetch(`${base}/api/runs/${runId}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((run) => {
        if (cancelled || !run?.graph_state) return;
        if (run.run_id !== expectedId) return;

        const gs = run.graph_state;
        const isTerminal = run.status === "completed" || run.status === "failed";

        setState((prev) => {
          const hydratedFindings: Finding[] = [];
          for (const f of gs.findings || []) {
            hydratedFindings.push(f as unknown as Finding);
          }

          const rawPersisted = gs.steps;
          let restoredSteps: ReasoningStep[] = [];

          if (Array.isArray(rawPersisted) && rawPersisted.length > 0) {
            restoredSteps = rawPersisted.map((s: Record<string, unknown>) => ({
              id: String(s.id ?? `h-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`),
              agent: String(s.agent ?? "unknown"),
              type: (String(s.type || EVENT_AGENT_START)) as SSEEventType,
              content: String(s.content ?? ""),
              tool: s.tool != null && s.tool !== "" ? String(s.tool) : undefined,
              timestamp: typeof s.timestamp === "number" ? s.timestamp : Date.now(),
            }));
          } else {
            for (const node of gs.completed_nodes || []) {
              if (node === "end") continue;
              restoredSteps.push(
                makeStreamStep(node, EVENT_AGENT_START, `${node} started`)
              );
              restoredSteps.push(
                makeStreamStep(node, EVENT_AGENT_COMPLETE, `${node} completed`)
              );
            }
            for (const f of hydratedFindings) {
              restoredSteps.push(
                makeStreamStep(
                  f.agent_source || "unknown",
                  EVENT_FINDING,
                  `[${(f.severity || "info").toUpperCase()}] ${f.title}`
                )
              );
            }
          }

          const findingIds = new Set(hydratedFindings.map((f) => f.id));
          const newSseFindings = prev.findings.filter((f) => !findingIds.has(f.id));
          const mergedFindings = [...hydratedFindings, ...newSseFindings];

          const mergedCompleted = [
            ...new Set([
              ...(gs.completed_nodes || []),
              ...prev.graphState.completed_nodes,
            ]),
          ];

          return {
            steps: prev.steps.length > 0
              ? [...restoredSteps, ...prev.steps]
              : restoredSteps,
            graphState: {
              current_node: prev.graphState.current_node || gs.current_node || null,
              active_nodes: prev.graphState.active_nodes.length > 0
                ? prev.graphState.active_nodes
                : gs.active_nodes || [],
              completed_nodes: mergedCompleted,
              plan: prev.graphState.plan.length > 0
                ? prev.graphState.plan
                : gs.plan || [],
            },
            findings: mergedFindings,
            activeAgent: prev.activeAgent ?? (
              isTerminal ? null : gs.active_nodes?.[0] || gs.current_node || null
            ),
            done: prev.done || isTerminal,
            error: prev.error || (run.status === "failed" ? "Hunt failed" : null),
          };
        });
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, enabled, base]);

  const reset = useCallback(() => {
    thinkingQueueRef.current = [];
    if (thinkingRafRef.current != null) {
      cancelAnimationFrame(thinkingRafRef.current);
      thinkingRafRef.current = null;
    }
    setState({
      steps: [],
      graphState: emptyGraph(),
      findings: [],
      activeAgent: null,
      done: false,
      error: null,
    });
  }, []);

  return {
    ...state,
    connected,
    reset,
  };
}

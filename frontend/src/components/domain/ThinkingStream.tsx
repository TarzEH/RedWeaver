import { useMemo } from "react";
import { Brain, ChevronDown, ChevronRight, Shield } from "lucide-react";
import { AgentPanel } from "./AgentPanel";
import type { ReasoningStep } from "../../types/events";
import { EVENT_AGENT_COMPLETE, EVENT_AGENT_START, EVENT_FINDING } from "../../types/events";

interface ThinkingStreamProps {
  steps: ReasoningStep[];
  activeAgent: string | null;
  isActive: boolean;
  collapsed: boolean;
  onToggle: () => void;
}

export function ThinkingStream({ steps, activeAgent, isActive, collapsed, onToggle }: ThinkingStreamProps) {
  const agentGroups = useMemo(() => {
    const groups: Record<string, ReasoningStep[]> = {};
    const order: string[] = [];
    for (const step of steps) {
      const agent = step.agent || "unknown";
      if (!groups[agent]) { groups[agent] = []; order.push(agent); }
      groups[agent].push(step);
    }
    return { groups, order };
  }, [steps]);

  const completedAgents = useMemo(() => {
    const set = new Set<string>();
    for (const step of steps) {
      if (step.type === EVENT_AGENT_COMPLETE) set.add(step.agent);
    }
    return set;
  }, [steps]);

  const totalSteps = steps.filter((s) => s.type !== EVENT_AGENT_START).length;
  const totalFindings = steps.filter((s) => s.type === EVENT_FINDING).length;

  return (
    <div className={`bg-rw-elevated border rounded-xl overflow-hidden transition-all duration-200 ${
      isActive ? "border-rw-accent/20 shadow-[0_0_20px_rgba(59,130,246,0.06)]" : "border-rw-border"
    }`}>
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-rw-surface/30 transition-colors"
      >
        <Brain size={14} className="text-rw-accent shrink-0" />
        <span className="text-xs font-medium text-rw-text">Agent Reasoning</span>
        {totalSteps > 0 && <span className="text-[10px] text-rw-dim">{totalSteps} steps</span>}
        {totalFindings > 0 && (
          <span className="text-[10px] text-rw-accent font-medium flex items-center gap-0.5">
            <Shield size={8} /> {totalFindings}
          </span>
        )}
        {isActive && <div className="w-3 h-3 border border-rw-accent/30 border-t-rw-accent rounded-full animate-spin ml-1" />}
        <span className="ml-auto">
          {collapsed ? <ChevronRight size={13} className="text-rw-dim" /> : <ChevronDown size={13} className="text-rw-dim" />}
        </span>
      </button>

      {!collapsed && (
        <div className="border-t border-rw-border p-2 space-y-1.5 max-h-[60vh] overflow-y-auto">
          {agentGroups.order.length === 0 ? (
            <div className="px-2 py-3 text-xs text-rw-dim text-center">
              {isActive ? "Waiting for agent activity..." : "No activity recorded."}
            </div>
          ) : (
            agentGroups.order.map((agentId) => (
              <AgentPanel
                key={agentId}
                agentId={agentId}
                steps={agentGroups.groups[agentId]}
                isActive={activeAgent === agentId}
                isCompleted={completedAgents.has(agentId)}
                defaultExpanded={activeAgent === agentId}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}

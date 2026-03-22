import { useMemo } from "react";
import { Activity } from "lucide-react";
import { useHuntContext } from "../../contexts/HuntContext";
import { AGENT_CONFIG, AGENT_ORDER } from "../../config/agents";

type AgentStatus = "completed" | "running" | "idle";

interface Props {
  compact?: boolean;
}

export function AgentActivityDashboard({ compact = false }: Props) {
  const { steps, graphState, findings } = useHuntContext();
  const { active_nodes: activeNodes, completed_nodes: completedNodes } = graphState;

  const agentStats = useMemo(() => {
    const stats: Record<string, { toolCalls: number; findings: number; lastThinking: string }> = {};
    for (const agent of AGENT_ORDER) stats[agent] = { toolCalls: 0, findings: 0, lastThinking: "" };
    for (const step of steps) {
      const agent = step.agent || "unknown";
      if (!stats[agent]) stats[agent] = { toolCalls: 0, findings: 0, lastThinking: "" };
      if (step.type === "tool_call") stats[agent].toolCalls++;
      if (step.type === "agent_thinking" && step.content) stats[agent].lastThinking = step.content.slice(0, 80);
    }
    for (const f of findings) { if (stats[f.agent_source]) stats[f.agent_source].findings++; }
    return stats;
  }, [steps, findings]);

  const getStatus = (agent: string): AgentStatus => {
    if (completedNodes.includes(agent)) return "completed";
    if (activeNodes.includes(agent)) return "running";
    if (steps.some((s) => s.agent === agent)) return "completed";
    return "idle";
  };

  const visibleAgents = AGENT_ORDER.filter((a) => a !== "orchestrator");

  return (
    <div className={compact ? "p-3" : "flex-1 overflow-y-auto p-6"}>
      {!compact && (
        <div className="flex items-center gap-2 mb-4">
          <Activity size={18} className="text-rw-accent" />
          <h2 className="text-lg font-semibold text-rw-text">Agent Activity</h2>
          <span className="text-xs text-rw-dim ml-2">
            {completedNodes.filter((n) => n !== "end").length} completed
            {activeNodes.length > 0 && <> · <span className="text-rw-accent">{activeNodes.length} active</span></>}
          </span>
        </div>
      )}

      <div className={compact ? "space-y-1" : "grid grid-cols-2 lg:grid-cols-3 gap-3"}>
        {visibleAgents.map((agent) => {
          const config = AGENT_CONFIG[agent];
          if (!config) return null;
          const status = getStatus(agent);
          const stats = agentStats[agent] || { toolCalls: 0, findings: 0, lastThinking: "" };

          if (compact) {
            return (
              <div key={agent} className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-rw-surface transition-colors">
                <span className="w-2 h-2 rounded-full shrink-0" style={{ background: status === "completed" ? "#10b981" : status === "running" ? config.color : "#334155" }} />
                <span className={`text-xs flex-1 truncate ${status === "idle" ? "text-rw-dim" : "text-rw-text"}`}>{config.displayName}</span>
                {stats.findings > 0 && <span className="text-[10px] text-rw-accent bg-rw-accent/10 px-1.5 rounded">{stats.findings}</span>}
                {stats.toolCalls > 0 && <span className="text-[10px] text-rw-dim">{stats.toolCalls}t</span>}
              </div>
            );
          }

          return (
            <div key={agent} className={`bg-rw-elevated border rounded-xl p-3 transition-colors ${status === "running" ? "border-rw-accent/30" : "border-rw-border"}`}>
              <div className="flex items-center gap-2 mb-2">
                <span className={`w-2 h-2 rounded-full ${status === "running" ? "animate-pulse-dot" : ""}`} style={{ background: status === "completed" ? "#10b981" : status === "running" ? config.color : "#334155" }} />
                <span className="text-sm font-medium text-rw-text">{config.displayName}</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-rw-dim">Tools</span>
                  <span className="block text-rw-text font-medium">{stats.toolCalls}</span>
                </div>
                <div>
                  <span className="text-rw-dim">Findings</span>
                  <span className="block text-rw-text font-medium">{stats.findings}</span>
                </div>
              </div>
              {stats.lastThinking && <p className="text-[10px] text-rw-dim mt-2 truncate">{stats.lastThinking}</p>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

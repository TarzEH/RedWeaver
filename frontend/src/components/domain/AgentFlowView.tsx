import { useMemo } from "react";
import { CheckCircle2, Circle, Loader2, Zap, Shield } from "lucide-react";
import { AGENT_CONFIG } from "../../config/agents";
import type { GraphState, Finding } from "../../types/api";
import type { ReasoningStep } from "../../types/events";

interface Phase {
  id: string;
  label: string;
  agents: string[];
  color: string;
}

const HUNT_PHASES: Phase[] = [
  { id: "recon", label: "Reconnaissance", agents: ["recon", "fuzzer"], color: "#8b5cf6" },
  { id: "scan", label: "Scanning", agents: ["crawler", "vuln_scanner"], color: "#3b82f6" },
  { id: "intel", label: "Intelligence", agents: ["web_search"], color: "#f59e0b" },
  { id: "analysis", label: "Analysis", agents: ["exploit_analyst"], color: "#ec4899" },
  { id: "exploit", label: "Exploitation", agents: ["privesc", "tunnel_pivot", "post_exploit"], color: "#a855f7" },
  { id: "report", label: "Reporting", agents: ["report_writer"], color: "#10b981" },
];

type AgentStatus = "completed" | "active" | "idle";

interface AgentFlowViewProps {
  graphState: GraphState;
  steps: ReasoningStep[];
  findings: Finding[];
  isLive: boolean;
}

export function AgentFlowView({ graphState, steps, findings, isLive }: AgentFlowViewProps) {
  const agentStats = useMemo(() => {
    const stats: Record<string, { toolCalls: number; findings: number; lastThinking: string }> = {};
    for (const s of steps) {
      const agent = s.agent || "";
      if (!stats[agent]) stats[agent] = { toolCalls: 0, findings: 0, lastThinking: "" };
      if (s.type === "tool_call") stats[agent].toolCalls++;
      if (s.type === "agent_thinking" && s.content) stats[agent].lastThinking = s.content.slice(0, 60);
    }
    for (const f of findings) {
      const agent = f.agent_source || "";
      if (!stats[agent]) stats[agent] = { toolCalls: 0, findings: 0, lastThinking: "" };
      stats[agent].findings++;
    }
    return stats;
  }, [steps, findings]);

  const activeAgentSet = useMemo(() => {
    const set = new Set<string>();
    for (const n of graphState.completed_nodes || []) set.add(n);
    for (const n of graphState.active_nodes || []) set.add(n);
    for (const s of steps) if (s.agent) set.add(s.agent);
    return set;
  }, [graphState, steps]);

  const getStatus = (agentId: string): AgentStatus => {
    if ((graphState.completed_nodes || []).includes(agentId)) return "completed";
    if ((graphState.active_nodes || []).includes(agentId)) return "active";
    if (steps.some((s) => s.agent === agentId)) return "completed";
    return "idle";
  };

  const visiblePhases = HUNT_PHASES.filter((phase) =>
    phase.agents.some((a) => AGENT_CONFIG[a] && (activeAgentSet.size === 0 || activeAgentSet.has(a) || getStatus(a) !== "idle")),
  );
  const phases = visiblePhases.length > 0 ? visiblePhases : HUNT_PHASES.filter((p) => !["exploit"].includes(p.id));

  const getPhaseStatus = (phase: Phase): AgentStatus => {
    const statuses = phase.agents.filter((a) => AGENT_CONFIG[a]).map(getStatus);
    if (statuses.every((s) => s === "completed")) return "completed";
    if (statuses.some((s) => s === "active")) return "active";
    return "idle";
  };

  return (
    <div className="p-3 space-y-0">
      {phases.map((phase, phaseIdx) => {
        const phaseStatus = getPhaseStatus(phase);
        const phaseAgents = phase.agents.filter((a) => AGENT_CONFIG[a]);
        const isLastPhase = phaseIdx === phases.length - 1;

        return (
          <div key={phase.id}>
            <div className="flex items-center gap-2 mb-2 mt-1">
              <div className={`w-1.5 h-1.5 rounded-full ${
                phaseStatus === "completed" ? "bg-emerald-400"
                : phaseStatus === "active" ? "bg-rw-accent animate-pulse-dot"
                : "bg-rw-dim/30"
              }`} />
              <span className={`text-[10px] font-bold uppercase tracking-widest ${
                phaseStatus === "completed" ? "text-emerald-400/70"
                : phaseStatus === "active" ? "text-rw-accent"
                : "text-rw-dim/50"
              }`}>{phase.label}</span>
              {phaseStatus === "active" && isLive && (
                <div className="w-3 h-3 border border-rw-accent/30 border-t-rw-accent rounded-full animate-spin ml-auto" />
              )}
            </div>

            <div className={`grid gap-2 mb-1 ${phaseAgents.length > 1 ? "grid-cols-2" : "grid-cols-1"}`}>
              {phaseAgents.map((agentId) => {
                const config = AGENT_CONFIG[agentId];
                if (!config) return null;
                const status = getStatus(agentId);
                const stats = agentStats[agentId] || { toolCalls: 0, findings: 0, lastThinking: "" };

                return (
                  <div
                    key={agentId}
                    className={`rounded-lg border p-2.5 transition-all duration-300 ${
                      status === "active"
                        ? "border-rw-accent/40 bg-rw-accent/5 shadow-[0_0_12px_rgba(59,130,246,0.08)]"
                        : status === "completed"
                        ? "border-emerald-500/20 bg-emerald-500/[0.03]"
                        : "border-rw-border bg-rw-elevated/50"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1.5">
                      {status === "completed" ? <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />
                        : status === "active" ? <Loader2 size={14} className="text-rw-accent animate-spin shrink-0" />
                        : <Circle size={14} className="text-rw-dim/30 shrink-0" />}
                      <span className={`text-xs font-semibold truncate ${
                        status === "active" ? "text-rw-accent"
                        : status === "completed" ? "text-rw-text"
                        : "text-rw-dim"
                      }`}>{config.shortLabel}</span>
                    </div>

                    {(stats.toolCalls > 0 || stats.findings > 0) && (
                      <div className="flex items-center gap-2 mb-1">
                        {stats.toolCalls > 0 && (
                          <span className="flex items-center gap-0.5 text-[10px] text-rw-dim"><Zap size={9} /> {stats.toolCalls}</span>
                        )}
                        {stats.findings > 0 && (
                          <span className="flex items-center gap-0.5 text-[10px] text-rw-accent font-medium"><Shield size={9} /> {stats.findings}</span>
                        )}
                      </div>
                    )}

                    {stats.lastThinking && status !== "idle" && (
                      <p className={`text-[10px] truncate mt-0.5 ${status === "active" ? "text-rw-muted animate-pulse-dot" : "text-rw-dim"}`}>
                        {stats.lastThinking}
                      </p>
                    )}

                    {status === "idle" && <p className="text-[10px] text-rw-dim/40 mt-0.5">Waiting...</p>}
                  </div>
                );
              })}
            </div>

            {!isLastPhase && (
              <div className="flex justify-center py-0.5">
                <div className={`w-px h-4 ${phaseStatus === "completed" ? "bg-emerald-400/30" : "bg-rw-border"}`} />
              </div>
            )}
          </div>
        );
      })}

      {(graphState.completed_nodes?.length || 0) > 0 && (
        <div className="mt-3 pt-3 border-t border-rw-border flex items-center gap-3 text-[10px] text-rw-dim">
          <span className="text-emerald-400">{(graphState.completed_nodes || []).filter((n) => n !== "end").length} done</span>
          {(graphState.active_nodes?.length || 0) > 0 && (
            <span className="text-rw-accent">{graphState.active_nodes!.length} active</span>
          )}
          {findings.length > 0 && <span className="ml-auto">{findings.length} findings</span>}
        </div>
      )}
    </div>
  );
}

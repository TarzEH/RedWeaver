import { useState } from "react";
import { Shield, Workflow } from "lucide-react";
import { FindingsPanel } from "../../features/hunt/FindingsPanel";
import { AgentFlowView } from "../domain/AgentFlowView";
import { useHuntContext } from "../../contexts/HuntContext";

type DetailTab = "flow" | "findings";

export function DetailPanel({ runId }: { runId: string | null }) {
  const [detailTab, setDetailTab] = useState<DetailTab>("flow");
  const { steps, graphState, findings, done } = useHuntContext();

  const tabs: { id: DetailTab; label: string; icon: typeof Workflow; count?: number }[] = [
    { id: "flow", label: "Flow", icon: Workflow },
    { id: "findings", label: "Findings", icon: Shield, count: findings.length || undefined },
  ];

  return (
    <aside className="w-80 min-w-[20rem] border-l border-rw-border bg-rw-elevated flex flex-col shrink-0 min-h-0 overflow-hidden">
      <div className="flex border-b border-rw-border">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setDetailTab(t.id)}
            className={`
              flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors
              ${detailTab === t.id
                ? "text-rw-accent border-b-2 border-rw-accent"
                : "text-rw-dim hover:text-rw-muted"
              }
            `}
          >
            <t.icon size={13} />
            {t.label}
            {t.count != null && t.count > 0 && (
              <span className="bg-rw-accent/15 text-rw-accent text-[10px] font-bold px-1.5 rounded-full">
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
        {detailTab === "flow" && (
          <div className="flex-1 overflow-y-auto min-h-0">
            <AgentFlowView graphState={graphState} steps={steps} findings={findings} isLive={!done} />
          </div>
        )}
        {detailTab === "findings" && (
          <div className="flex-1 overflow-y-auto min-h-0">
            <FindingsPanel runId={runId} compact />
          </div>
        )}
      </div>
    </aside>
  );
}

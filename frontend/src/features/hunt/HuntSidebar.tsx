import { useMemo } from "react";
import { FolderOpen, PanelLeftClose, PanelLeftOpen, Plus } from "lucide-react";
import { formatRelativeDate } from "../../utils/formatDate";
import { statusLabel, statusColor } from "../../config/theme";
import type { RunSummary } from "../../types/api";

interface HuntSidebarProps {
  runs: RunSummary[];
  selectedRunId: string | null;
  open: boolean;
  onToggle: () => void;
  onSelectRun: (runId: string) => void;
  onNewHunt: () => void;
}

function RunListButton({
  r,
  selectedRunId,
  onSelectRun,
}: {
  r: RunSummary;
  selectedRunId: string | null;
  onSelectRun: (runId: string) => void;
}) {
  const sc = statusColor(r.status);
  return (
    <button
      onClick={() => onSelectRun(r.run_id)}
      className={`
        w-full text-left px-2.5 py-2 rounded-md transition-colors text-xs
        ${selectedRunId === r.run_id
          ? "bg-rw-surface text-rw-text"
          : "text-rw-muted hover:bg-rw-surface/50"
        }
      `}
    >
      <div className="truncate font-medium">{r.target}</div>
      <div className="flex items-center gap-1.5 mt-0.5">
        <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: sc.color }} />
        <span className="text-[10px] text-rw-dim">{statusLabel(r.status)}</span>
        <span className="text-[10px] text-rw-dim ml-auto">{formatRelativeDate(r.created_at)}</span>
      </div>
      {r.session_id && (r.workspace_name || r.session_name) && (
        <div className="mt-1 text-[10px] text-rw-dim truncate flex items-center gap-1">
          <FolderOpen size={10} className="shrink-0 text-rw-accent/80" />
          <span className="truncate">
            {r.workspace_name ? `${r.workspace_name} · ` : ""}{r.session_name ?? "Session"}
          </span>
        </div>
      )}
    </button>
  );
}

export function HuntSidebar({ runs, selectedRunId, open, onToggle, onSelectRun, onNewHunt }: HuntSidebarProps) {
  const { projectRuns, standaloneRuns } = useMemo(() => {
    const project: RunSummary[] = [];
    const standalone: RunSummary[] = [];
    for (const r of runs) {
      if (r.session_id) project.push(r);
      else standalone.push(r);
    }
    return { projectRuns: project, standaloneRuns: standalone };
  }, [runs]);

  if (!open) {
    return (
      <button
        onClick={onToggle}
        className="w-8 flex items-center justify-center border-r border-rw-border text-rw-dim hover:text-rw-muted hover:bg-rw-surface transition-colors"
      >
        <PanelLeftOpen size={14} />
      </button>
    );
  }

  return (
    <aside className="w-56 border-r border-rw-border bg-rw-bg flex flex-col shrink-0 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-rw-border">
        <span className="text-xs font-medium text-rw-muted uppercase tracking-wider">Hunts</span>
        <button onClick={onToggle} className="text-rw-dim hover:text-rw-muted p-1 rounded transition-colors">
          <PanelLeftClose size={14} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-1.5 space-y-3">
        <button
          onClick={onNewHunt}
          className="w-full flex items-center gap-2 px-2.5 py-2 text-xs text-rw-accent hover:bg-rw-surface rounded-md transition-colors"
        >
          <Plus size={13} /> New Hunt
        </button>

        {standaloneRuns.length > 0 && (
          <div>
            <div className="px-2.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-rw-dim">
              Hunts
            </div>
            <div className="space-y-0.5">
              {standaloneRuns.map((r) => (
                <RunListButton key={r.run_id} r={r} selectedRunId={selectedRunId} onSelectRun={onSelectRun} />
              ))}
            </div>
          </div>
        )}

        {projectRuns.length > 0 && (
          <div>
            <div className="px-2.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-rw-dim flex items-center gap-1.5">
              <FolderOpen size={11} className="text-rw-accent/90" />
              Projects
            </div>
            <div className="space-y-0.5">
              {projectRuns.map((r) => (
                <RunListButton key={r.run_id} r={r} selectedRunId={selectedRunId} onSelectRun={onSelectRun} />
              ))}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

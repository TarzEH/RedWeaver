import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ChatPanel } from "./ChatPanel";
import { HuntSidebar } from "./HuntSidebar";
import { DetailPanel } from "../../components/layout/DetailPanel";
import { HuntProvider } from "../../contexts/HuntContext";
import { api } from "../../services/api";
import type { RunSummary } from "../../types/api";

export function HuntPage() {
  const { runId } = useParams<{ runId?: string }>();
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const selectedRunId = runId ?? null;

  const fetchRuns = () => {
    api.runs.list().then(setRuns).catch(() => {});
  };

  useEffect(() => { fetchRuns(); }, []);

  // Refresh run list when a hunt completes
  useEffect(() => {
    const interval = setInterval(fetchRuns, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleSelectRun = (id: string | null) => {
    navigate(id ? `/hunt/${id}` : "/hunt");
  };

  const handleRunDeleted = () => {
    fetchRuns();
    navigate("/hunt");
  };

  const handleNewHunt = () => {
    navigate("/hunt");
  };

  return (
    <HuntProvider selectedRunId={selectedRunId}>
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <HuntSidebar
          runs={runs}
          selectedRunId={selectedRunId}
          open={sidebarOpen}
          onToggle={() => setSidebarOpen(!sidebarOpen)}
          onSelectRun={(id) => { handleSelectRun(id); fetchRuns(); }}
          onNewHunt={handleNewHunt}
        />
        <ChatPanel
          selectedRunId={selectedRunId}
          onSelectRun={(id) => { handleSelectRun(id); fetchRuns(); }}
          onRunDeleted={handleRunDeleted}
        />
        <DetailPanel runId={selectedRunId} />
      </div>
    </HuntProvider>
  );
}

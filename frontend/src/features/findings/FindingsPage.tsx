import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Swords } from "lucide-react";
import { FindingsPanel } from "../hunt/FindingsPanel";
import { Button } from "../../components/ui/Button";
import { HuntProvider } from "../../contexts/HuntContext";

/** Full-page findings triage: the non-compact FindingsPanel with severity
 * facets, search, expandable rows, and SSVC/risk badges. */
export function FindingsPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  return (
    <HuntProvider selectedRunId={runId ?? null}>
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center gap-3 border-b border-rw-border px-6 py-4">
        <button
          onClick={() => navigate(`/hunt/${runId}`)}
          className="text-rw-dim transition-colors hover:text-rw-text"
          aria-label="Back to hunt"
        >
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-lg font-semibold text-rw-text">Findings triage</h1>
        <Button
          variant="secondary"
          size="sm"
          className="ml-auto"
          icon={<Swords size={14} />}
          onClick={() => navigate(`/debug/${runId}`)}
        >
          Attack & debug
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto">
        <FindingsPanel runId={runId ?? null} />
      </div>
    </div>
    </HuntProvider>
  );
}

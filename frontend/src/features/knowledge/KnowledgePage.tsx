import { useEffect, useState } from "react";
import { BookOpen, Library, AlertCircle, ChevronDown, Grid3x3 } from "lucide-react";
import { Badge } from "../../components/ui/Badge";
import { Spinner } from "../../components/ui/Spinner";
import { EmptyState } from "../../components/ui/EmptyState";
import { MarkdownRenderer } from "../../components/domain/MarkdownRenderer";
import { KbAttackHeatmap } from "../../components/domain/KbAttackHeatmap";
import { api, type KbFile, type KbDocument } from "../../services/api";
import { CategoryTree, type CategoryNode } from "./CategoryTree";
import { SearchPanel } from "./SearchPanel";
import { categoryLabel } from "./kbUtils";
import { cn } from "../../lib/cn";

type HealthState = { status: string; documents_indexed: number; files_indexed: number };

export function KnowledgePage() {
  const [categories, setCategories] = useState<CategoryNode[]>([]);
  const [catLoading, setCatLoading] = useState(true);
  const [health, setHealth] = useState<HealthState | null>(null);

  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [doc, setDoc] = useState<KbDocument | null>(null);
  const [docLoading, setDocLoading] = useState(false);
  const [docError, setDocError] = useState(false);
  const [heatmapOpen, setHeatmapOpen] = useState(false);

  useEffect(() => {
    api.knowledge.health().then(setHealth).catch(() => {});
    api.knowledge
      .categories()
      .then((d) => setCategories(d.categories || []))
      .catch(() => setCategories([]))
      .finally(() => setCatLoading(false));
  }, []);

  // Load a document whenever the selected file changes.
  useEffect(() => {
    if (!selectedFile) {
      setDoc(null);
      return;
    }
    let cancelled = false;
    setDocLoading(true);
    setDocError(false);
    api.knowledge
      .document(selectedFile)
      .then((d) => {
        if (!cancelled) setDoc(d);
      })
      .catch(() => {
        if (!cancelled) {
          setDoc(null);
          setDocError(true);
        }
      })
      .finally(() => {
        if (!cancelled) setDocLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedFile]);

  const openFile = (file: KbFile | string) => {
    setSelectedFile(typeof file === "string" ? file : file.file);
  };

  const unavailable = health?.status === "unavailable";

  return (
    <div className="flex flex-1 min-h-0 flex-col overflow-hidden animate-fade-in">
      {/* Header */}
      <header className="flex shrink-0 items-center justify-between border-b border-rw-border px-6 py-4">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-rw-accent/15 text-rw-accent">
            <Library size={18} />
          </span>
          <div>
            <h1 className="text-lg font-semibold text-rw-text">Knowledge Base</h1>
            <p className="text-xs text-rw-dim">
              {health && !unavailable
                ? `${health.documents_indexed.toLocaleString()} chunks across ${health.files_indexed.toLocaleString()} files`
                : "Browse, search, and ask your pentest playbooks"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setHeatmapOpen((v) => !v)}
            aria-expanded={heatmapOpen}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
              heatmapOpen
                ? "border-rw-accent/40 bg-rw-accent/15 text-rw-accent"
                : "border-rw-border bg-rw-surface text-rw-muted hover:text-rw-text",
            )}
          >
            <Grid3x3 size={14} />
            ATT&CK Coverage
            <ChevronDown
              size={14}
              className={cn("transition-transform duration-150", heatmapOpen && "rotate-180")}
            />
          </button>
          {unavailable && <Badge variant="danger">Service unavailable</Badge>}
        </div>
      </header>

      {/* Collapsible ATT&CK coverage heatmap */}
      {heatmapOpen && (
        <div className="shrink-0 border-b border-rw-border px-6 py-4 animate-fade-in">
          <KbAttackHeatmap />
        </div>
      )}

      {/* 3-pane body */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* LEFT — category / file tree */}
        <aside className="hidden w-64 shrink-0 flex-col overflow-hidden border-r border-rw-border bg-rw-elevated/40 md:flex">
          <div className="border-b border-rw-border-subtle px-4 py-3">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-rw-dim">Categories</p>
          </div>
          <div className="flex-1 overflow-y-auto px-2 py-2">
            <CategoryTree
              categories={categories}
              loading={catLoading}
              selectedFile={selectedFile}
              onSelectFile={openFile}
            />
          </div>
        </aside>

        {/* CENTER — document viewer */}
        <main className="flex flex-1 min-w-0 flex-col overflow-hidden">
          <DocumentViewer doc={doc} loading={docLoading} error={docError} hasSelection={!!selectedFile} />
        </main>

        {/* RIGHT — search + ask */}
        <aside className="hidden w-80 shrink-0 flex-col overflow-hidden border-l border-rw-border bg-rw-elevated/40 p-4 lg:flex xl:w-96">
          <SearchPanel onOpenFile={(file) => openFile(file)} />
        </aside>
      </div>
    </div>
  );
}

function DocumentViewer({
  doc,
  loading,
  error,
  hasSelection,
}: {
  doc: KbDocument | null;
  loading: boolean;
  error: boolean;
  hasSelection: boolean;
}) {
  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Spinner size="md" label="Loading document" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center p-6">
        <EmptyState
          icon={<AlertCircle size={32} />}
          title="Could not load document"
          description="The selected knowledge file is unavailable. Try another document."
        />
      </div>
    );
  }

  if (!hasSelection || !doc) {
    return (
      <div className="flex flex-1 items-center justify-center p-6">
        <EmptyState
          icon={<BookOpen size={32} />}
          title="Select a document to read"
          description="Pick a file from a category on the left, or use search and Ask on the right to jump straight to the relevant playbook."
        />
      </div>
    );
  }

  return (
    <article className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl px-8 py-8">
        <div className="mb-6 border-b border-rw-border-subtle pb-5">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Badge variant="accent">{categoryLabel(doc.category)}</Badge>
            <span className="font-mono text-[10px] text-rw-dim">{doc.file}</span>
          </div>
          <h1 className="text-2xl font-bold text-rw-text">{doc.title || doc.file}</h1>
        </div>
        <MarkdownRenderer content={doc.content} variant="enhanced" />
      </div>
    </article>
  );
}

export default KnowledgePage;

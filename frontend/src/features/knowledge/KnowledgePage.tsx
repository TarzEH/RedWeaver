import { useEffect, useState } from "react";
import { BookOpen, Library, AlertCircle, ChevronDown, Grid3x3, FolderTree, Search } from "lucide-react";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Drawer } from "../../components/ui/Drawer";
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

/** Which side pane is currently open as an overlay (only when it can't dock). */
type OpenPane = "categories" | "search" | null;

/**
 * Knowledge base — a three-pane reader (categories / document / search+Ask).
 *
 * ── Responsive policy ────────────────────────────────────────────────────
 * Pane docking is driven by **container queries** on the page root, not by
 * viewport media queries. The page sits next to the global nav, so its usable
 * width is well below the viewport width; `md:` / `lg:` were measuring the
 * wrong box and both side panes disappeared with no way to reach them, leaving
 * a centre pane that said "pick a file from a category on the left" — with no
 * left. `@3xl` / `@6xl` measure the space this page actually has.
 *
 * Whenever a pane cannot dock it becomes a Drawer reachable from a header
 * toggle. Deferred behind one gesture is fine; absent is not.
 */
export function KnowledgePage() {
  const [categories, setCategories] = useState<CategoryNode[]>([]);
  const [catLoading, setCatLoading] = useState(true);
  const [health, setHealth] = useState<HealthState | null>(null);
  const [openPane, setOpenPane] = useState<OpenPane>(null);

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
    // Opening a document from an overlay pane is the end of that errand.
    setOpenPane(null);
  };

  const unavailable = health?.status === "unavailable";

  return (
    <div className="@container relative flex flex-1 min-h-0 flex-col overflow-hidden animate-fade-in">
      {/* Header */}
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-rw-border px-6 py-4">
        <div className="flex min-w-0 items-center gap-3">
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
        <div className="flex items-center gap-2">
          {/*
            Pane toggles mirror the docking breakpoints exactly: each is shown
            only while its pane is undocked, so a pane is never unreachable and
            never offered twice.
          */}
          <PaneToggle
            className="@3xl:hidden"
            icon={<FolderTree size={14} />}
            onClick={() => setOpenPane("categories")}
          >
            Categories
          </PaneToggle>
          <PaneToggle
            className="@6xl:hidden"
            icon={<Search size={14} />}
            onClick={() => setOpenPane("search")}
          >
            Search
          </PaneToggle>

          <button
            type="button"
            onClick={() => setHeatmapOpen((v) => !v)}
            aria-expanded={heatmapOpen}
            className={cn(
              "inline-flex min-h-6 items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
              heatmapOpen
                ? "border-rw-accent/40 bg-rw-accent/15 text-rw-accent"
                : "border-rw-border bg-rw-surface text-rw-muted hover:text-rw-text",
            )}
          >
            <Grid3x3 size={14} />
            <span className="hidden @lg:inline">ATT&CK Coverage</span>
            <span className="@lg:hidden">ATT&CK</span>
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
        {/* LEFT — category / file tree. Docks at @3xl, else lives in a drawer. */}
        <aside className="hidden w-64 shrink-0 flex-col overflow-hidden border-r border-rw-border bg-rw-elevated/40 @3xl:flex">
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
          <DocumentViewer
            doc={doc}
            loading={docLoading}
            error={docError}
            hasSelection={!!selectedFile}
            onBrowse={() => setOpenPane("categories")}
          />
        </main>

        {/* RIGHT — search + ask. Docks at @6xl, else lives in a drawer. */}
        <aside className="hidden w-80 shrink-0 flex-col overflow-hidden border-l border-rw-border bg-rw-elevated/40 p-4 @6xl:flex @7xl:w-96">
          <SearchPanel onOpenFile={(file) => openFile(file)} />
        </aside>
      </div>

      {/* Undocked panes stay one gesture away rather than disappearing. */}
      <Drawer
        open={openPane === "categories"}
        onClose={() => setOpenPane(null)}
        side="left"
        title="Categories"
      >
        <div className="px-2 py-2">
          <CategoryTree
            categories={categories}
            loading={catLoading}
            selectedFile={selectedFile}
            onSelectFile={openFile}
          />
        </div>
      </Drawer>

      <Drawer
        open={openPane === "search"}
        onClose={() => setOpenPane(null)}
        side="right"
        title={"Search & Ask"}
      >
        <div className="h-full p-4">
          <SearchPanel onOpenFile={(file) => openFile(file)} />
        </div>
      </Drawer>
    </div>
  );
}

/** Header affordance that reveals a pane the container is too narrow to dock. */
function PaneToggle({
  icon,
  children,
  className,
  onClick,
}: {
  icon: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        // 24px min target via padding — not by inflating the glyph (WCAG 2.2 SC 2.5.8).
        "inline-flex min-h-6 items-center gap-1.5 rounded-lg border border-rw-border bg-rw-surface",
        "px-3 py-1.5 text-xs font-medium text-rw-muted transition-colors hover:text-rw-text",
        className,
      )}
    >
      {icon}
      {children}
    </button>
  );
}

function DocumentViewer({
  doc,
  loading,
  error,
  hasSelection,
  onBrowse,
}: {
  doc: KbDocument | null;
  loading: boolean;
  error: boolean;
  hasSelection: boolean;
  onBrowse: () => void;
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
          /*
            Deliberately not "on the left" / "on the right": below @6xl those
            panes are drawers, so directional copy describes a layout the
            reader cannot see.
          */
          description="Pick a file from a category, or use Search and Ask to jump straight to the relevant playbook."
          action={
            // Only meaningful while the tree is undocked — otherwise it is
            // already on screen and this would be a second route to the same place.
            <span className="@3xl:hidden">
              <Button size="sm" variant="secondary" icon={<FolderTree size={14} />} onClick={onBrowse}>
                Browse categories
              </Button>
            </span>
          }
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
